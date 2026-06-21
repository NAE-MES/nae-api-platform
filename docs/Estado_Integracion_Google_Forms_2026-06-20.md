# Estado de la integración con Google Forms

Fecha: 2026-06-20

## Estado actual

Ya quedó preparado el script base `docs/google-apps-script-nae.gs` para enviar respuestas desde Google Forms hacia la API NAE usando `onFormSubmit(e)` y `UrlFetchApp.fetch`.

La versión vigente del formulario debe construirse desde `docs/Encuesta_NAE.docx`, que define la encuesta de referencia.
El trigger instalable de envío ya fue creado.

## Decisión operativa

No se realizará la prueba todavía en local.

La validación real de este flujo requiere publicar el proyecto en la nube para que el script de Google Apps Script tenga una URL pública accesible por Google.

## Próximo paso

1. Verificar que `NAE_API_URL` y `NAE_API_TOKEN` ya estén cargados en el script real de Google Apps Script.
2. Ejecutar una respuesta real de prueba desde Google Forms.
3. Confirmar la llegada de la respuesta a `POST /api/v1/respuestas`.
4. Revisar en la API que la respuesta pase por `raw -> staging -> operational -> analytics`.

## Notas

- No usar `127.0.0.1` como destino del script.
- Revisar el mapeo de preguntas si cambia el texto de la encuesta.
- Mantener el `API_TOKEN` fuera del repositorio.
- Esta versión de la encuesta no incluye consentimiento como pregunta separada; el backend no debe exigirlo.
- Si Google Forms no coincide con `docs/Encuesta_NAE.docx`, la integración debe corregirse antes de validar nuevos envíos.
- Si la prueba falla, revisar primero el log de Apps Script y luego la respuesta de `POST /api/v1/respuestas`.
