# Estado del proyecto NAE

Fecha: 2026-06-19

## Estado actual

La plataforma quedó validada con el modelo de datos v1.1:

- `raw -> staging` funcionando
- `staging -> operational` funcionando
- `operational -> analytics` funcionando

La rama `dev` ya fue publicada en `origin/dev`.

Se habilitó además una primera capa de consumo:

- `GET /api/v1/resumen`
- `GET /` con un panel HTML de resumen y filtros
- `GET /api/v1/resumen.csv` para exportar el resumen filtrado
- `GET /api/v1/respuestas/{respuesta_id}` y `/respuestas/{respuesta_id}` para ver el detalle de una respuesta

El panel ya quedó con:

- encabezado azul compacto
- bloques visibles de territorio, estados, género, temas, nivel de instrucción e instituciones
- exportación CSV separada en una barra superior para no romper el bloque de filtros
- detalle navegable desde la tabla de últimas respuestas

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
- paneles más ricos sobre territorios, temas y género
- exportaciones adicionales para seguimiento operativo

## Corte nocturno

La rama `dev` quedó lista para promoverse a `main` mediante pull request. El siguiente paso operativo es revisar y aprobar ese corte.
