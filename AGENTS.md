# Procesar grabaciones de clase

## Objetivo

Este proyecto se dedica exclusivamente a procesar grabaciones de clase. Transcribe la grabación completa y devuelve por chat lo que el usuario necesita saber para seguir el curso. Prioriza tareas, plazos, evaluaciones y avisos. Resume los temas y ejemplos importantes de la clase.

## Configuración inicial

- Trabaja con archivos de audio locales como M4A, MP3, WAV o WebM. Acepta la ruta del archivo tal como la entrega el usuario, sin exigir una URL ni un nombre específico.
- Usa el transcriptor del proyecto, `python transcribir.py "ruta del audio"`. La carpeta `audios` está disponible para colocar las grabaciones. El script requiere Python 3.11 o posterior, FFmpeg con `ffprobe`, acceso de red y `GROQ_API_KEY` en el entorno o en el `.env` de la raíz excluido de Git. La clave se configura una vez y se mantiene fuera del chat y de los resultados.
- Usa Groq como proveedor preferido si está configurado y el envío del audio está autorizado. Si el entorno requiere autorización para enviar una grabación a un servicio externo, solicítala antes de transmitirla. Usa otro proveedor solo cuando el usuario lo indique.
- Si falta el transcriptor, prepara o configura uno que acepte la ruta del audio y permita guardar el progreso. Esta guía define el flujo de trabajo. La herramienta de transcripción se configura aparte.

## Al recibir el audio

1. Cuando el usuario avise que hay un audio nuevo, búscalo en `audios` o usa la ruta que indique. Antes de enviarlo, el transcriptor compara su huella SHA-256 con la de los TXT completos. Si encuentra una copia idéntica, reutiliza esa transcripción aunque el audio tenga otro nombre. Para un audio nuevo, mide su duración y conserva el original hasta el cierre de la sesión. Toma el nombre del curso y la fecha de la sesión del contenido o de datos confirmados por el usuario, cuando estén disponibles.
2. Para grabaciones largas, ejecuta primero `python transcribir.py "ruta del audio" --primer-fragmento` y revisa la coherencia y el idioma de la muestra. Después ejecuta el mismo comando sin `--primer-fragmento` para continuar. El script divide el audio en fragmentos consecutivos de hasta cinco minutos y guarda cada respuesta con su posición para reanudar desde la primera parte faltante. Si conoces el idioma, puedes añadir `--idioma es` (o el código correspondiente) a ambas ejecuciones.
3. Verifica que las partes cubran toda la grabación y estén en orden. El TXT completo guarda las marcas de tiempo y la huella del audio en su última línea. Usa el SRT, el JSON y el progreso de los fragmentos como archivos auxiliares mientras dure el trabajo. Identifica claramente cualquier resultado parcial.
4. Analiza la sesión completa, incluido el inicio y el cierre. Usa la transcripción y sus marcas de tiempo para respaldar el resumen. Si un detalle importante queda confuso, revisa el contexto y, cuando sea posible, el tramo del audio.

## Qué devolver en el chat

1. **Tareas y entregas.** Para cada actividad anunciada, anota qué hay que hacer, qué se entrega, modalidad, integrantes, responsable de subirla, formato, plataforma, ubicación y fecha u hora límite, según lo que diga la fuente. Si la profesora confirma el plazo al cierre, incorpora esa aclaración.
2. **Evaluaciones y avisos.** Registra fechas o semanas de evaluación, acuerdos de grupos, próxima sesión, materiales que se deben revisar y avisos que requieran acción. Si se menciona un enlace compartido en el chat de clase, indica dónde dijeron que estaba. Incluye la URL cuando el usuario la pida y la fuente la contenga.
3. **Temas de clase.** Resume cada tema principal con sus puntos clave, en palabras sencillas. Incluye uno o dos ejemplos si ayudan a entender el concepto.
4. **Detalles por confirmar.** Distingue las fechas de entrega de los plazos para formar grupos. Si solo se menciona «este viernes» o «semana 3», conserva esa referencia hasta confirmar la fecha exacta. Si faltan el formato, la hora límite o una parte de la consigna, indica qué dato quedó por confirmar.

Prioriza lo que tiene plazo o requiere acción. Separa las entregas obligatorias de los ejercicios hechos durante la sesión y de los materiales recomendados. Si la grabación no permite identificar ninguna entrega, dilo. Si el usuario pide únicamente transcribir, entrega la transcripción.

Responde en lenguaje natural para escuchar en voz alta. Incluye rutas, enlaces a archivos locales y marcas de tiempo en el chat solo si el usuario los pide. Usa el TXT conservado para responder consultas posteriores sobre una clase cerrada.

## Cerrar una sesión

- Cuando el usuario dé por terminada la revisión, verifica que el TXT cubra la grabación completa y tenga su huella SHA-256. Si el trabajo está incompleto, conserva el audio y el progreso para reanudar.
- Conserva el TXT como único archivo de la sesión. Elimina el audio, el SRT, el JSON, los archivos de progreso y los temporales de esa grabación. Mantén el transcriptor, la configuración de Groq y los archivos de otras clases.
- **Sesión cerrada.** `Class recordings (1).m4a` se transcribió por completo en 34 fragmentos. La copia de consulta es `Class recordings (1).m4a.txt`, con la huella del original en la última línea. La clase trató sobre ingesta de datos desde API REST.

## Cuando aparezca una tarea

- Por defecto, registra y explica lo que pide. Desarrolla la actividad cuando el usuario lo solicite.
- Si el usuario adjunta la consigna, compárala con la grabación. Usa el documento para precisar el entregable, el formato y la rúbrica. Usa la clase para incorporar aclaraciones sobre la coordinación y la entrega. Señala cualquier discrepancia que siga abierta.
- Cuando el usuario pida ayuda para desarrollar la tarea, respeta el alcance, el formato y el nivel del curso. Usa fuentes externas cuando la tarea lo requiera o el usuario lo pida, y cita las fuentes de los datos que se incorporen.
