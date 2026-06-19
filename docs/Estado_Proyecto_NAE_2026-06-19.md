# Estado del proyecto NAE

Fecha: 2026-06-19

## Estado actual

La plataforma quedó validada con el modelo de datos v1.1:

- `raw -> staging` funcionando
- `staging -> operational` funcionando
- `operational -> analytics` funcionando

La rama `dev` ya fue publicada en `origin/dev` con el commit `4c82726`.

## Cambios ya incorporados

- `version_encuesta` en `raw`, `staging`, `operational` y `analytics`
- `nivel_instruccion`
- catálogo de género ampliado con `Persona trans`
- bloque de género y emprendimiento en la encuesta
- nuevas dimensiones analíticas de género
- tablas hijas de multiselección en `operational`

## Próximo paso

Promover `dev` a `main` tras una revisión mínima del diff.

Después de ese corte, el siguiente trabajo útil es construir consumo analítico:

- vistas para BI
- consultas base de control
- validaciones de regresión para nuevas versiones de la encuesta
