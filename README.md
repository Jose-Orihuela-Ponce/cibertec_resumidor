# cibertec_resumidor

Transcribe grabaciones de clase mediante Groq, guarda un TXT por sesión y organiza las consignas y soluciones por curso.

## Estructura

```text
audios/                                  Grabaciones nuevas y archivos de trabajo
├── .gitkeep
└── Procesos de negocio - Semana 2/      Original, SRT, JSON y progreso .groq
Gestión de procesos de negocio/          Transcripciones TXT del curso
Lenguaje de ciencia de datos 2/           Transcripciones TXT del curso
Gestión de servicios de TI/               Transcripciones TXT del curso
Tareas/
├── Tareas - Gestión de procesos de negocio/
│   ├── Actividad 1 - Semana 1/           Informe presentado en PDF
│   └── Actividad 2 - Semana 2/           Consigna en PDF y solución en Word o PDF
├── Tareas - Lenguaje de ciencia de datos 2/
└── Tareas - Gestión de servicios de TI/
transcribir.py
AGENTS.md
README.md
```

Las grabaciones, los archivos de trabajo de `audios` y la clave del archivo `.env` se excluyen de Git. El marcador vacío `.gitkeep` conserva la carpeta de entrada en el repositorio.

## Requisitos

- Python 3.11 o posterior.
- FFmpeg y `ffprobe` disponibles en el `PATH`.
- Acceso a Internet y una clave de Groq en la variable `GROQ_API_KEY` o en un archivo `.env` en la raíz del proyecto.

El transcriptor usa la biblioteca estándar de Python. Para configurar la clave, copia `.env.example` a `.env` y completa `GROQ_API_KEY` con tu clave de Groq. Puedes revisar la configuración local con `python transcribir.py --verificar`.

## Grabaciones y transcripciones

Coloca la grabación de audio o video en `audios`. Si solo hay una grabación en la carpeta, puedes omitir la ruta.

```powershell
python transcribir.py --idioma es --primer-fragmento
python transcribir.py --idioma es
```

Revisa la muestra antes de continuar con el segundo comando. Si hay varias grabaciones o si el archivo está en otra carpeta, indica su ruta local como primer argumento.

El TXT se genera junto al original. Una vez verificada la transcripción completa, archiva ese único TXT en la carpeta del curso confirmado. Para sesiones nuevas, identifica la semana si se conoce. El transcriptor también busca en las tres carpetas de curso para reutilizar transcripciones de grabaciones idénticas.

Mientras la sesión siga en revisión, reúne el original, el SRT, el JSON y el progreso en una subcarpeta de `audios` identificada por curso y semana o sesión. Cuando el usuario dé por cerrada la revisión, elimina esos archivos de trabajo y conserva el TXT archivado.

## Tareas

Crea una subcarpeta por actividad dentro de `Tareas/Tareas - <curso>`. Identifícala por número y semana cuando estén confirmados. Guarda ahí la consigna original, los materiales necesarios y la solución. El formato habitual para desarrollar la tarea es **Word editable (`.docx`)**. Conserva también los PDF de las consignas, los informes previos y las versiones de entrega disponibles en la carpeta de la actividad correspondiente.
