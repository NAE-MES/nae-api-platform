# Estado de la integración con Google Forms

Fecha: 2026-06-20

## Estado actual

Ya quedó preparado el script base `docs/google-apps-script-nae.gs` para enviar respuestas desde Google Forms hacia la API NAE usando `onFormSubmit(e)` y `UrlFetchApp.fetch`.

## Decisión operativa

No se realizará la prueba todavía en local.

La validación real de este flujo requiere publicar el proyecto en la nube para que el script de Google Apps Script tenga una URL pública accesible por Google.

## Próximo paso

1. Publicar la API NAE en un entorno accesible desde Internet.
2. Sustituir `NAE_API_URL` en el script por la URL pública real.
3. Crear el trigger instalable `On form submit` sobre la hoja vinculada al formulario.
4. Ejecutar una respuesta real de prueba desde Google Forms.
5. Confirmar la llegada de la respuesta a `POST /api/v1/respuestas`.

## Notas

- No usar `127.0.0.1` como destino del script.
- Revisar el mapeo de preguntas si cambia el texto de la encuesta.
- Mantener el `API_TOKEN` fuera del repositorio.
