# cibertec_resumidor

Transcribe grabaciones locales de clase mediante Groq y guarda un TXT con marcas de tiempo. Para grabaciones largas, procesa el audio en fragmentos y conserva el progreso para poder reanudar.

## Requisitos

- Python 3.11 o posterior.
- FFmpeg y `ffprobe` disponibles en el `PATH`.
- Acceso a Internet y una clave de Groq en la variable `GROQ_API_KEY` o en un archivo `.env` en la raíz del proyecto.

## Uso

Coloca la grabación en `audios` o indica su ruta local.

```powershell
python transcribir.py "audios/clase.m4a" --idioma es
```

Para revisar solo el primer fragmento, añade `--primer-fragmento`. Ejecuta el comando original para continuar.

Las grabaciones y el archivo `.env` se excluyen de Git.
