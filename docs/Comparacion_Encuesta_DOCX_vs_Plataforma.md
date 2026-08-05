# Comparación Encuesta DOCX vs Plataforma

Archivo revisado: `docs/Encuesta_mapeo_apoyo_nae.docx`.

Resultado general: no se identificaron preguntas de negocio faltantes en la plataforma respecto al documento de encuesta. La diferencia principal está en la forma de implementación en Google Forms, no en el contenido sustantivo de la encuesta.

## Ajustes documentados en amarillo dentro del DOCX

- Indicacion inicial de la plataforma para escribir, siempre que sea posible, en MAYUSCULAS y sin acentos, excepto correos, sitios web, enlaces y usuarios de redes sociales.
- Pregunta 1.2: en Google Forms se implementa mediante ramificacion territorial; primero se selecciona provincia y luego se muestran solo sus municipios.
- Pregunta 2.1: la matriz conserva el asterisco del cuestionario aprobado, pero tecnicamente no obliga a completar todas las filas.
- Pregunta 3.2: bloque implementado como opcional; se pueden registrar espacios si existen.
- Pregunta 4.2: bloque implementado como opcional; se pueden registrar perfiles si la entidad los conoce.
- Pregunta 8.3: bloque implementado como opcional; se pueden recomendar estructuras si la persona dispone de esa informacion.

## Observaciones

- Los campos de contacto del bloque 0.5 existen en el DOCX y en la plataforma. En Google Forms se implementan como preguntas individuales para facilitar la captura.
- No se modifico la encuesta historica `Encuesta_mapeo_entidad_apoyo_nae.docx`; se trabajo sobre `Encuesta_mapeo_apoyo_nae.docx`.
