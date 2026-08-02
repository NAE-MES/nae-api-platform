# Contingencia Google Forms - API NAE

## Objetivo

Evitar pérdida operativa de respuestas si la API de la plataforma no está disponible temporalmente durante la aplicación nacional de la encuesta.

## Principio de operación

Google Forms conserva la respuesta original en el formulario. El Apps Script intenta enviarla a la API. Si la API falla, el script guarda una copia temporal en propiedades del script y registra el evento en logs.

## Funciones disponibles

### `onFormSubmit(e)`

Se ejecuta automáticamente con cada envío. Si la API responde correctamente, limpia cualquier pendiente asociado. Si la API falla, deja la respuesta en cola local.

### `reenviarPendientesNae()`

Reintenta enviar solo las respuestas que quedaron pendientes por fallo previo.

Uso recomendado cuando la API vuelve a estar disponible:

1. Abrir el editor de Apps Script del formulario.
2. Seleccionar la función `reenviarPendientesNae`.
3. Ejecutar.
4. Revisar el registro de ejecución.

### `reenviarTodasLasRespuestasNae()`

Recorre todas las respuestas almacenadas en Google Forms y las intenta sincronizar con la API. Es la función de recuperación completa.

Uso recomendado si hubo una caída larga o dudas sobre sincronización:

1. Abrir el editor de Apps Script del formulario.
2. Seleccionar `reenviarTodasLasRespuestasNae`.
3. Ejecutar.
4. La API ignorará duplicados mediante `id_respuesta_origen`.

## Qué revisar después de una caída

En la plataforma:

```sql
SELECT COUNT(*) FROM raw.respuestas_formulario;
```

En Apps Script:

- Revisar logs de `onFormSubmit`.
- Ejecutar `reenviarPendientesNae()`.
- Si aún hay dudas, ejecutar `reenviarTodasLasRespuestasNae()`.

## Nota técnica

El mecanismo no sustituye la disponibilidad de la API, pero evita que una caída temporal obligue a repetir encuestas. La fuente primaria durante la contingencia sigue siendo Google Forms.
