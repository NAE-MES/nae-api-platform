# Estado de puesta en producción NAE

Fecha: 2026-06-21

## Estado

La plataforma quedó visible en la URL externa:

- `https://nae-plataforma.mes.gob.cu`

El despliegue quedó montado con este esquema:

- HAProxy remoto termina TLS
- Nginx local publica la app por `8080`
- Uvicorn corre en `127.0.0.1:8000`
- PostgreSQL aloja `raw`, `staging`, `operational`, `analytics` y `control`

## Validaciones realizadas

- `GET /api/v1/salud` responde `200`
- `GET /api/v1/resumen` responde sin error
- `POST /api/v1/respuestas` acepta un payload de prueba
- `POST /api/v1/pipelines/staging/raw-to-staging` ejecuta la carga
- `POST /api/v1/pipelines/operational/staging-to-operational` ejecuta la normalización
- `POST /api/v1/pipelines/analytics/operational-to-analytics` ejecuta la consolidación
- `GET /api/v1/resumen.csv` queda disponible para exportación

## Base de datos

Se materializó el esquema completo en la base `nae`:

- `control`
- `raw`
- `staging`
- `operational`
- `analytics`

## Cambios operativos importantes

- Se agregó el bootstrap de `control` en `sql/000_create_control_layer.sql`
- Se dejó el despliegue preparado para HAProxy remoto
- Se corrigió Nginx para publicar en `8080`
- Se dejó el documento de despliegue en `docs/Despliegue_Ubuntu_22_04.md`

## Estado del corte

El sistema ya quedó accesible desde la URL pública y listo para uso operativo.

Lo siguiente ya es gestión de operación:

- monitoreo de los primeros envíos reales
- respaldo de base antes de cambios futuros
- ajuste del formulario solo si cambian preguntas o catálogos
- promoción formal de `main` como rama estable de referencia

