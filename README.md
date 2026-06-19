# NAE Platform API

Plataforma de datos para la encuesta NAE. El repositorio contiene la API FastAPI y los scripts SQL para operar el flujo de datos desde captura hasta analítica:

- `raw` para ingesta inicial
- `staging` para validación y control
- `operational` para normalización relacional
- `analytics` para consumo analítico

## Estructura

- `nae-platform-api/app`: API y pipelines
- `nae-platform-api/sql`: scripts de creación y evolución del modelo
- `docs`: documentación funcional y de estado del proyecto

## Requisitos

- Python 3.12+
- PostgreSQL
- Variables de entorno en `nae-platform-api/.env`

Variables esperadas:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `API_TOKEN`

## Ejecución local

```bash
cd nae-platform-api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

La API expone la documentación interactiva en:

- `http://127.0.0.1:8000/docs`

## Endpoints principales

- `GET /api/v1/salud`
- `POST /api/v1/respuestas`
- `POST /api/v1/pipelines/staging/raw-to-staging`
- `POST /api/v1/pipelines/operational/staging-to-operational`
- `POST /api/v1/pipelines/analytics/operational-to-analytics`

Todos los endpoints protegidos usan `Authorization: Bearer <API_TOKEN>`.

## Scripts SQL

El orden recomendado para materializar el modelo es:

1. `sql/001_create_staging_layer.sql`
2. `sql/002_create_operational_layer.sql`
3. `sql/003_create_analytics_layer.sql`
4. `sql/004_create_operational_multiselect_tables.sql`
5. `sql/005_update_modelo_datos_v11.sql`

## Estado actual

El proyecto ya cuenta con:

- pipeline funcional de extremo a extremo
- actualización del modelo de datos v1.1
- ramas `dev` y `main`

La rama de trabajo activa es `dev`, y los cambios se promueven a `main` mediante pull request.

## Documentación relacionada

- `docs/Estado_Proyecto_NAE_2026-06-19.md`
- `docs/scripts-googleform.txt`
- `docs/NAE Platform - Actualización de Modelo de Datos.pdf`
