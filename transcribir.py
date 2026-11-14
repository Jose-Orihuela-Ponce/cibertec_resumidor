import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
import wave


GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3"
SAMPLE_RATE = 16_000
CHUNK_FRAMES = SAMPLE_RATE * 300
MIN_FRAMES = SAMPLE_RATE // 100
AUDIO_DIGEST_LABEL = "SHA-256 del audio: "
PROJECT_ROOT = Path(__file__).resolve().parent
INBOX = PROJECT_ROOT / "audios"
COURSES = (
    "Gestión de procesos de negocio",
    "Lenguaje de ciencia de datos 2",
    "Gestión de servicios de TI",
)
MEDIA_EXTENSIONS = frozenset(
    ".m4a .m4v .mp3 .mp4 .wav .webm .mov .mkv .avi .aac .flac .ogg .wma .wmv .mpeg .mpg .3gp".split()
)


def api_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    dotenv = Path(__file__).with_name(".env")
    if not key and dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8-sig").splitlines():
            match = re.fullmatch(
                r"\s*(?:export\s+)?GROQ_API_KEY\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s#]+))\s*(?:#.*)?",
                line,
            )
            if match:
                key = next(value for value in match.groups() if value is not None)
    if not key:
        raise ValueError("Configura GROQ_API_KEY en el entorno o en el .env de la raíz.")
    if not re.fullmatch(r"[!-~]+", key):
        raise ValueError("GROQ_API_KEY contiene espacios o caracteres inválidos.")
    return key


def run_media_tool(*args):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"{args[0]} no pudo leer el audio. {result.stderr.strip()}")
    return result.stdout


@contextmanager
def lock_recording(state):
    state.mkdir(exist_ok=True)
    with (state / "ejecucion.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("Ya hay una ejecución para esta grabación.") from None
        yield


def save(path, content):
    if os.name == "nt":
        # The temporary filename can push a course checkpoint past MAX_PATH.
        absolute = str(path.resolve())
        if absolute.startswith("\\\\"):
            path = Path("\\\\?\\UNC\\" + absolute[2:])
        else:
            path = Path("\\\\?\\" + absolute)
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp.write_text(content, encoding="utf-8", newline="\n")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def upload_chunk(chunk, key, language):
    boundary = uuid4().hex
    fields = {
        "model": MODEL,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "segment",
    }
    if language:
        fields["language"] = language
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    parts.extend([
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{chunk.name}"\r\n'
        'Content-Type: audio/flac\r\n\r\n'.encode(),
        chunk.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    request = Request(GROQ_URL, data=b"".join(parts), headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "User-Agent": "cibertec-resumidor/1.0",
    })
    request.add_unredirected_header("Authorization", f"Bearer {key}")
    for attempt in range(4):
        try:
            with urlopen(request, timeout=120) as response:
                return json.load(response)
        except HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After", "")
            error.close()
            if status == 429 and attempt < 3:
                delay = math.ceil(float(retry_after)) if re.fullmatch(r"\d+(?:\.\d+)?", retry_after) else 60
                delay = max(1, delay)
                print(f"  Groq alcanzó su límite. Reintento en {delay} s.", flush=True)
                time.sleep(delay)
                continue
            hints = {
                401: "Revisa la clave de Groq.",
                403: "Revisa el acceso a la API de Groq.",
                429: "Se alcanzó un límite de Groq. Espera y vuelve a ejecutar el comando.",
            }
            raise ValueError(f"Groq devolvió HTTP {status}. {hints.get(status, '')}".rstrip()) from None
        except (URLError, TimeoutError):
            raise ValueError("Falló la conexión con Groq. Revisa la red y vuelve a ejecutar el comando.") from None


def timestamp(seconds, separator="."):
    whole, millis = divmod(round(seconds * 1000), 1000)
    minutes, second = divmod(whole, 60)
    hour, minute = divmod(minutes, 60)
    return f"{hour:02}:{minute:02}:{second:02}{separator}{millis:03}"


def timed_segments(part):
    response = part["respuesta"]
    segments = response.get("segments")
    if segments is None and not response.get("text", "").strip():
        return []
    if not isinstance(segments, list) or (not segments and response.get("text", "").strip()):
        raise ValueError("Groq no devolvió las marcas de tiempo solicitadas.")

    cues = []
    for segment in segments:
        start, end = segment["start"], segment["end"]
        if not math.isfinite(start) or not math.isfinite(end) or start > end:
            raise ValueError("Groq devolvió marcas de tiempo inválidas.")
        start = max(part["inicio"], part["inicio"] + start)
        end = min(part["fin"], part["inicio"] + end)
        text = " ".join(segment["text"].split())
        if text and round(end * 1000) > round(start * 1000):
            cues.append((start, end, text))
    return sorted(cues)


def completed_transcript(audio, digest):
    marker = (AUDIO_DIGEST_LABEL + digest).encode("ascii")
    folders = dict.fromkeys((audio.parent, INBOX, *(PROJECT_ROOT / course for course in COURSES)))
    for folder in folders:
        for transcript in folder.glob("*.txt"):
            try:
                with transcript.open("rb") as stream:
                    size = stream.seek(0, os.SEEK_END)
                    stream.seek(max(0, size - 128))
                    if stream.read().splitlines()[-1:] == [marker]:
                        return transcript
            except (FileNotFoundError, IsADirectoryError):
                continue
    return None


def check_media_tools():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise ValueError(f"Agrega {tool} al PATH.")


def audio_from_inbox():
    candidates = sorted(
        path for path in INBOX.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    ) if INBOX.is_dir() else []
    if not candidates:
        raise ValueError("Coloca una grabación en audios o indica su ruta.")
    if len(candidates) > 1:
        names = "\n".join(f"  {path.name}" for path in candidates)
        raise ValueError(f"Hay varias grabaciones en audios. Indica la ruta de la que quieres transcribir.\n{names}")
    return candidates[0]


def transcribe(audio, language, preview_only):
    original_stat = audio.stat()
    with audio.open("rb") as original:
        digest = hashlib.file_digest(original, "sha256").hexdigest()
    existing = completed_transcript(audio, digest)
    if existing:
        print(f"Esta grabación ya se transcribió. Usa el TXT existente: {existing}")
        return

    check_media_tools()
    if not run_media_tool("ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                          "stream=index", "-of", "csv=p=0", str(audio)).strip():
        raise ValueError("El archivo no contiene una pista de audio.")

    state = audio.with_name(audio.name + ".groq")
    with lock_recording(state), tempfile.TemporaryDirectory(prefix="clase-") as temp_dir:
        existing = completed_transcript(audio, digest)
        if existing:
            print(f"Esta grabación ya se transcribió. Usa el TXT existente: {existing}")
            return
        normalized = Path(temp_dir) / "audio.wav"
        chunk = Path(temp_dir) / "fragmento.wav"
        run_media_tool("ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(audio),
                       "-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(normalized))
        current_stat = audio.stat()
        if (original_stat.st_size, original_stat.st_mtime_ns) != (current_stat.st_size, current_stat.st_mtime_ns):
            raise ValueError("El archivo cambió durante la lectura. Espera a que se termine de copiar.")

        checkpoints = state / f"v1-{MODEL}-{language or 'auto'}-{digest}"
        checkpoints.mkdir(exist_ok=True)
        with wave.open(str(normalized), "rb") as wav:
            total_frames = wav.getnframes()
            if not total_frames:
                raise ValueError("La pista de audio está vacía.")
            total_parts = (total_frames + CHUNK_FRAMES - 1) // CHUNK_FRAMES
            print(f"Duración {timestamp(total_frames / SAMPLE_RATE)}. Fragmentos {total_parts}.", flush=True)
            process_parts(audio, wav, total_frames, total_parts, checkpoints, chunk, digest, language, preview_only)


def process_parts(audio, wav, total_frames, total_parts, checkpoints, chunk, digest, language, preview_only):
    parts, cues = [], []
    key = None
    for index in range(1 if preview_only else total_parts):
        start_frame = index * CHUNK_FRAMES
        frames = min(CHUNK_FRAMES, total_frames - start_frame)
        start, end = start_frame / SAMPLE_RATE, (start_frame + frames) / SAMPLE_RATE
        checkpoint = checkpoints / f"{index + 1:05}.json"
        cached = checkpoint.is_file()
        print(f"Fragmento {index + 1}/{total_parts} [{timestamp(start)} a {timestamp(end)}]", flush=True)
        if cached:
            part = json.loads(checkpoint.read_text(encoding="utf-8"))
            if (part["inicio"], part["fin"]) != (start, end):
                raise ValueError(f"El archivo de progreso tiene tiempos distintos: {checkpoint}")
            print("  Recuperado del progreso guardado.", flush=True)
        else:
            key = key or api_key()
            wav.setpos(start_frame)
            samples = wav.readframes(frames)
            if len(samples) != 2 * frames:
                raise ValueError("El audio decodificado termina antes del tiempo esperado.")
            with wave.open(str(chunk), "wb") as fragment:
                fragment.setparams(wav.getparams())
                fragment.writeframes(samples.ljust(2 * MIN_FRAMES, b"\x00"))
            compressed = chunk.with_suffix(".flac")
            run_media_tool("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(chunk),
                           "-c:a", "flac", str(compressed))
            part = {"inicio": start, "fin": end, "respuesta": upload_chunk(compressed, key, language)}

        cues.extend(timed_segments(part))
        if not cached:
            save(checkpoint, json.dumps(part, ensure_ascii=False, indent=2))
        parts.append(part)
        if index == 0:
            detected = part["respuesta"].get("language") or "sin identificar"
            sample = " ".join(part["respuesta"].get("text", "").split())[:400]
            print(f"  Idioma informado: {detected}. Muestra: {sample or '(sin texto)'}", flush=True)

    if len(parts) < total_parts:
        print("Resultado parcial guardado. Ejecuta el comando sin --primer-fragmento para continuar.")
        return

    txt = [f"{audio.name}\nDuración: {timestamp(total_frames / SAMPLE_RATE)}\nFragmentos: {total_parts}\n"]
    srt = []
    for number, (start, end, text) in enumerate(cues, 1):
        txt.append(f"[{timestamp(start)} - {timestamp(end)}] {text}")
        srt.append(f"{number}\n{timestamp(start, ',')} --> {timestamp(end, ',')}\n{text}\n")
    metadata = {
        "archivo": audio.name, "sha256": digest, "modelo": MODEL, "idioma_solicitado": language,
        "duracion": total_frames / SAMPLE_RATE, "fragmentos": parts,
    }
    base = audio.name
    if audio.with_name(f"{base}.txt").exists():
        base = f"{base}.{digest}"
    txt.extend(["", AUDIO_DIGEST_LABEL + digest])
    for suffix, content in (("srt", "\n".join(srt)), ("json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"),
                            ("txt", "\n".join(txt) + "\n")):
        output = audio.with_name(f"{base}.{suffix}")
        save(output, content)
        print(f"Guardado {output}")


def main():
    parser = argparse.ArgumentParser(description="Transcribe una grabación local con Groq.")
    parser.add_argument("audio", nargs="?", type=Path, help="Ruta de la grabación. Si se omite, busca un único archivo en audios.")
    parser.add_argument("--verificar", action="store_true", help="Comprueba FFmpeg, ffprobe y la presencia de la clave sin enviar audio.")
    parser.add_argument("--idioma", help="Código ISO de dos letras, por ejemplo es. Se detecta si se omite.")
    parser.add_argument("--primer-fragmento", action="store_true", help="Procesa solo el primer fragmento para revisión")
    args = parser.parse_args()
    if args.idioma and not re.fullmatch(r"[a-z]{2}", args.idioma):
        parser.error("--idioma debe tener dos letras minúsculas, por ejemplo es.")
    try:
        if args.verificar:
            check_media_tools()
            api_key()
            print("FFmpeg, ffprobe y GROQ_API_KEY están configurados.")
            return 0
        audio = (args.audio or audio_from_inbox()).expanduser().resolve(strict=True)
        if not audio.is_file():
            raise ValueError("La ruta debe apuntar a un archivo de audio.")
        transcribe(audio, args.idioma, args.primer_fragmento)
    except (OSError, ValueError, KeyError, TypeError, wave.Error) as error:
        print(f"Error: {error}\nSi se guardaron fragmentos, el mismo comando permite reanudar.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrumpido. El mismo comando permite reanudar.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
