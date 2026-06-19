# Estado del proyecto NAE

Fecha: 2026-06-19

## Resumen ejecutivo

La plataforma NAE ya tiene un circuito funcional de datos desde la captura hasta la capa analítica:

- `raw` para ingesta inicial
- `staging` para validación y control de errores
- `operational` para normalización relacional
- `analytics` para consumo analítico

La API local está levantada y respondiendo en:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/v1/salud`

## Estado de base de datos

Schemas existentes:

- `raw`
- `staging`
- `control`
- `operational`
- `analytics`
- `metadata`
- `public`

Tablas ya creadas:

- `raw.respuestas_formulario`
- `staging.respuestas_formulario`
- `control.ejecucion_pipeline`
- `control.errores_carga`
- `operational.provincias`
- `operational.municipios`
- `operational.respuestas_encuesta`
- `analytics.dim_territorio`
- `analytics.dim_institucion`
- `analytics.dim_estado_validacion`
- `analytics.f_respuestas_encuesta`

Índices y llaves relevantes:

- `raw.respuestas_formulario`: índice único por `id_respuesta_origen`
- `staging.respuestas_formulario`: índice único por `raw_respuesta_id`
- `operational.respuestas_encuesta`: índice único por `staging_respuesta_id`
- `analytics.f_respuestas_encuesta`: índice único por `operational_respuesta_id`

## Estado funcional

### 1) Captura RAW

Implementado en la API:

- `POST /api/v1/respuestas`

Comportamiento:

- valida token Bearer
- inserta la respuesta en `raw.respuestas_formulario`
- evita duplicados por `id_respuesta_origen`
- guarda el `payload` JSON original

### 2) Validación STAGING

Implementado en la API:

- `POST /api/v1/pipelines/staging/raw-to-staging`

Comportamiento:

- toma respuestas con estado `recibida`
- valida consentimiento, provincia, municipio y campos base
- registra errores en `control.errores_carga`
- marca cada fila como `validada`, `con_observaciones` o `rechazada`
- inserta o actualiza `staging.respuestas_formulario`

### 3) Normalización OPERATIONAL

Implementado en la API:

- `POST /api/v1/pipelines/operational/staging-to-operational`

Comportamiento:

- toma filas válidas desde `staging`
- resuelve provincia y municipio como catálogos
- carga `operational.respuestas_encuesta`
- actualiza estado en `raw`

### 4) Capa ANALYTICS

Implementado en la API:

- `POST /api/v1/pipelines/analytics/operational-to-analytics`

Comportamiento:

- construye dimensiones de territorio, institución y estado de validación
- carga la tabla de hechos `analytics.f_respuestas_encuesta`

## Pruebas ejecutadas

Se probaron estos escenarios:

- caso válido
- caso inválido
- corrida de `raw -> staging`
- corrida de `staging -> operational`
- corrida de `operational -> analytics`

Resultado:

- el caso válido quedó cargado hasta `analytics`
- el caso inválido quedó rechazado y con errores registrados

## Corridas registradas

- `raw_to_staging`: 3 corridas
- `staging_to_operational`: 1 corrida
- `operational_to_analytics`: 1 corrida

## Estado operativo actual

La API está levantada localmente y la base de datos ya está materializada con el primer circuito completo.

## Actualización de modelo de datos 1.1

Se incorporó el ajuste del documento `NAE Platform - Actualización de Modelo de Datos.pdf` en el código y en una migración nueva:

- `sql/005_update_modelo_datos_v11.sql`

Cambios incluidos:

- soporte para `version_encuesta`
- nuevo campo `nivel_instruccion`
- catálogo de género ampliado con `Persona trans`
- nueva pregunta `Mayoría de titulares de emprendimientos`
- preguntas de género y emprendimiento en staging, operational y analytics
- nuevas dimensiones analíticas `analytics.dim_genero` y `analytics.dim_respuesta_genero`

## Siguiente paso recomendado

Ejecutar como admin la migración `sql/005_update_modelo_datos_v11.sql`, reiniciar la API si hace falta y volver a correr:

- `POST /api/v1/pipelines/staging/raw-to-staging`
- `POST /api/v1/pipelines/operational/staging-to-operational`
- `POST /api/v1/pipelines/analytics/operational-to-analytics`

Luego conviene validar conteos en:

- `staging.respuestas_formulario`
- `operational.respuestas_encuesta`
- `analytics.f_respuestas_encuesta`
