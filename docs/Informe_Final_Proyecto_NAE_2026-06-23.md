# Informe final del proyecto NAE Platform

Fecha: 23 de junio de 2026  
Estado: corte funcional para piloto  
URL de producción: https://mapeo-plataforma.mes.gob.cu

## 1. Resumen ejecutivo

NAE Platform es una plataforma de datos construida para capturar, validar, normalizar, analizar y visualizar las respuestas de la encuesta del proyecto de Apoyo a Nuevos Actores Económicos. El sistema conecta Google Forms con una API propia, almacena la respuesta original sin pérdida, ejecuta un pipeline de procesamiento por capas y publica un dashboard operativo para seguimiento del piloto.

El proyecto ya cuenta con un circuito funcional de extremo a extremo:

- Encuesta de referencia en `docs/Encuesta_NAE.docx`.
- Script de integración con Google Forms en `docs/google-apps-script-nae.gs`.
- API FastAPI para recepción, consulta y operación de pipelines.
- Base de datos PostgreSQL organizada en capas `raw`, `staging`, `operational`, `analytics` y `control`.
- Dashboard HTML con filtros, detalle por respuesta y exportación CSV.
- Despliegue en Ubuntu 22.04, con Nginx local y HAProxy remoto para publicación HTTPS.

El objetivo central ya fue alcanzado: una respuesta enviada desde Google Forms puede llegar a la API, ser almacenada, procesada automáticamente y quedar visible en el dashboard público.

## 2. Objetivo del proyecto

El proyecto tiene como propósito disponer de una plataforma técnica para el diagnóstico nacional sobre espacios de intercambio entre nuevos actores económicos, instituciones públicas, academia, sociedad civil y otros actores del ecosistema económico.

La solución permite:

- Capturar respuestas de la encuesta nacional.
- Preservar el payload original enviado por Google Forms.
- Validar campos obligatorios y catálogos críticos.
- Registrar observaciones y errores de carga.
- Transformar las respuestas hacia un modelo relacional operativo.
- Consolidar una capa analítica consultable.
- Visualizar resultados agregados y detalles individuales.
- Exportar información tabular para análisis externo.

## 3. Encuesta de referencia

La encuesta vigente del proyecto está definida en `docs/Encuesta_NAE.docx`, bajo el título "Propuesta de ENCUESTA FINAL SOBRE ESPACIOS DE INTERCAMBIO ENTRE NAE Y OTROS ACTORES - VERSION GOOGLE FORMS".

La encuesta está dirigida a personas, instituciones o negocios que desarrollan espacios de intercambio donde participan nuevos actores económicos. Su objetivo es mapear eventos, encuentros, iniciativas y capacidades disponibles para fortalecer formación, articulación y diálogo público-privado.

### Estructura de la encuesta

La versión de referencia contiene cinco bloques principales:

- Bloque 0: contexto del informante.
- Sección 1: identificación territorial e institucional.
- Sección 2: infraestructura y recursos.
- Sección 3: capacidades y necesidades formativas.
- Sección 4: articulación y limitaciones.

### Campos principales procesados

El backend procesa los siguientes grupos de datos:

- Datos territoriales: provincia y municipio.
- Perfil del informante: género, rol, nivel de instrucción y conocimiento del municipio.
- Datos institucionales: ámbito, tipo de institución, nombre oficial e involucramiento.
- Capacidades formativas: nivel de capacitación, temas prioritarios y principal necesidad.
- Enfoque de género: mayoría de titulares de emprendimientos, porcentaje de mujeres directivas y programas para mujeres emprendedoras.
- Articulación institucional: mecanismos de coordinación, instituciones participantes y limitaciones.

El sistema fue ajustado para trabajar con la versión real del Google Form, incluyendo preguntas que difieren en numeración o texto respecto a versiones anteriores del modelo.

## 4. Integración con Google Forms

La integración se realiza mediante Google Apps Script. El archivo de referencia es `docs/google-apps-script-nae.gs`.

Cuando una persona envía el formulario:

1. Google Forms dispara el trigger instalable `onFormSubmit`.
2. El script toma `e.namedValues` y construye un JSON con las respuestas.
3. Se genera un identificador único con `Utilities.getUuid()`.
4. Se envía un `POST` a `https://mapeo-plataforma.mes.gob.cu/api/v1/respuestas`.
5. La API guarda la respuesta en `raw.respuestas_formulario`.
6. La API ejecuta automáticamente la cadena de pipelines.
7. La respuesta queda disponible en el dashboard si supera las validaciones críticas.

La integración usa token Bearer mediante el encabezado:

```http
Authorization: Bearer <API_TOKEN>
```

### Consideraciones operativas

- El token real no debe quedar publicado en el repositorio.
- El script debe apuntar siempre a la URL pública de producción.
- Si se cambia el texto de una pregunta en Google Forms, debe revisarse el mapeo en el backend.
- El payload original se conserva completo para auditoría y recuperación ante cambios de mapeo.

## 5. API de recepción y consulta

La API está implementada con FastAPI y expone endpoints para operación y consulta.

### Endpoints principales

| Endpoint | Uso |
| --- | --- |
| `GET /api/v1/salud` | Verificación básica de servicio |
| `POST /api/v1/respuestas` | Recepción de respuestas desde Google Forms |
| `GET /api/v1/resumen` | Datos agregados para dashboard |
| `GET /api/v1/resumen.csv` | Exportación CSV del resumen filtrado |
| `GET /api/v1/respuestas/{id}` | Detalle JSON de una respuesta |
| `GET /` | Dashboard HTML |
| `GET /respuestas/{id}` | Vista HTML de detalle |
| `POST /api/v1/pipelines/staging/raw-to-staging` | Ejecución manual del pipeline RAW a STAGING |
| `POST /api/v1/pipelines/operational/staging-to-operational` | Ejecución manual del pipeline STAGING a OPERATIONAL |
| `POST /api/v1/pipelines/analytics/operational-to-analytics` | Ejecución manual del pipeline OPERATIONAL a ANALYTICS |

### Recepción automática

El endpoint `POST /api/v1/respuestas` no solo almacena la respuesta: también ejecuta la cadena automática de procesamiento:

```text
raw -> staging -> operational -> analytics
```

Esto evita que el equipo tenga que ejecutar manualmente los pipelines después de cada envío real del formulario.

## 6. Modelo de base de datos

La base de datos está diseñada por capas para separar responsabilidades y facilitar auditoría, corrección y análisis.

### Capa RAW

Schema: `raw`

Tabla principal:

- `raw.respuestas_formulario`

Función:

- Recibir y conservar la respuesta original.
- Guardar `id_respuesta_origen`, fecha, formulario, versión y `payload` JSONB.
- Evitar duplicados mediante índice único.

Esta capa es la fuente de verdad histórica. Aunque cambie el modelo o falle una validación, el dato original queda preservado.

### Capa STAGING

Schema: `staging`

Tabla principal:

- `staging.respuestas_formulario`

Función:

- Extraer campos normalizados desde el payload.
- Validar obligatorios y catálogos base.
- Clasificar cada respuesta como `validada`, `con_observaciones` o `rechazada`.
- Mantener una copia del `raw_payload` para trazabilidad.

Las respuestas con errores críticos, como provincia, municipio o institución faltante, pueden quedar rechazadas. Las respuestas con faltantes no críticos pueden pasar como `con_observaciones`.

### Capa OPERATIONAL

Schema: `operational`

Tablas principales:

- `operational.provincias`
- `operational.municipios`
- `operational.respuestas_encuesta`
- `operational.respuestas_temas_formacion`
- `operational.respuestas_instituciones_participantes`
- `operational.respuestas_limitaciones`

Función:

- Resolver catálogos relacionales de provincia y municipio.
- Normalizar la respuesta principal.
- Separar campos multiselección en tablas hijas.
- Mantener relaciones por `raw_respuesta_id` y `staging_respuesta_id`.

Esta capa es la base operativa para consulta detallada y correcciones posteriores.

### Capa ANALYTICS

Schema: `analytics`

Tablas principales:

- `analytics.dim_territorio`
- `analytics.dim_institucion`
- `analytics.dim_estado_validacion`
- `analytics.dim_genero`
- `analytics.dim_respuesta_genero`
- `analytics.f_respuestas_encuesta`

Función:

- Consolidar dimensiones de análisis.
- Construir tabla de hechos para consultas agregadas.
- Alimentar el dashboard y la exportación CSV.

### Capa CONTROL

Schema: `control`

Tablas principales:

- `control.ejecucion_pipeline`
- `control.errores_carga`

Función:

- Registrar cada ejecución de pipeline.
- Guardar cantidad de registros procesados y errores.
- Registrar errores por campo, valor recibido, tipo y descripción.

Esta capa es clave para operación, diagnóstico y seguimiento del piloto.

## 7. Pipeline de procesamiento

El flujo de datos implementado tiene cuatro momentos:

```text
Google Forms
  -> API FastAPI
  -> raw.respuestas_formulario
  -> staging.respuestas_formulario
  -> operational.*
  -> analytics.*
  -> dashboard / CSV / detalle
```

### RAW a STAGING

El pipeline `raw_to_staging`:

- Lee respuestas con estado `recibida`.
- Extrae campos conocidos desde el payload.
- Aplica alias para manejar diferencias de texto entre versiones de encuesta.
- Valida campos obligatorios.
- Registra errores en `control.errores_carga`.
- Inserta o actualiza `staging.respuestas_formulario`.

### STAGING a OPERATIONAL

El pipeline `staging_to_operational`:

- Toma respuestas `validada` y `con_observaciones`.
- Resuelve provincia y municipio.
- Inserta o actualiza la respuesta operacional.
- Separa multiselecciones por tema, institución y limitación.
- Recupera valores desde `raw_payload` cuando una fila histórica de staging no tenía algún campo mapeado.

### OPERATIONAL a ANALYTICS

El pipeline `operational_to_analytics`:

- Lee respuestas operacionales válidas.
- Resuelve dimensiones de territorio, institución, género y estado.
- Inserta o actualiza la tabla de hechos.
- Mantiene la capa analítica actualizada para el dashboard.

## 8. Validaciones y control de calidad

El sistema valida campos obligatorios y catálogos críticos. Entre los campos base se incluyen:

- Provincia.
- Municipio.
- Tipo y nombre de institución.
- Género.
- Nivel de instrucción o conocimiento del municipio.
- Nivel de involucramiento.
- Nivel de capacitación de formadores.
- Principal necesidad.
- Nivel de interés de gobierno.
- Mecanismos de coordinación.

La clasificación de una respuesta depende del tipo de error:

- `validada`: no presenta errores.
- `con_observaciones`: tiene faltantes no críticos, pero puede usarse en análisis.
- `rechazada`: tiene errores críticos que impiden su uso operativo.

Durante el piloto se detectaron diferencias reales entre la encuesta, el script de Google Forms y el backend. Se corrigieron los alias de campos para evitar pérdida de datos y se reforzó la recuperación desde el payload original.

## 9. Dashboard operativo

El dashboard está disponible en:

```text
https://mapeo-plataforma.mes.gob.cu
```

Incluye:

- Total de respuestas.
- Conteo por estado de validación.
- Distribución por provincia y municipio.
- Distribución por género.
- Nivel de instrucción.
- Temas prioritarios.
- Limitaciones reportadas.
- Instituciones con mayor presencia.
- Últimas respuestas recibidas.
- Filtros por provincia, versión de encuesta, género, tema y límite de registros.
- Exportación CSV.
- Vista de detalle por respuesta.

La vista de detalle permite revisar una respuesta específica con información institucional, territorial, formativa, de género, articulación y multiselecciones.

## 10. Despliegue en producción

El sistema quedó publicado con el siguiente esquema:

```text
Internet / usuarios
  -> HAProxy remoto con TLS
  -> Nginx local en puerto 8080
  -> Uvicorn en 127.0.0.1:8000
  -> PostgreSQL
```

La URL pública es:

```text
https://mapeo-plataforma.mes.gob.cu
```

El servidor de aplicación usa:

- Ubuntu 22.04.
- Python 3.12.
- FastAPI / Uvicorn.
- PostgreSQL.
- Nginx.
- systemd.

La guía operativa de despliegue está en `docs/Despliegue_Ubuntu_22_04.md`.

## 11. Repositorio y organización de código

El repositorio principal es:

```text
https://github.com/NAE-MES/nae-api-platform.git
```

Estructura relevante:

- `nae-platform-api/app`: API, pipelines y dashboard.
- `nae-platform-api/sql`: scripts de creación y actualización de base de datos.
- `nae-platform-api/tests`: pruebas de endpoints y regresión de pipeline.
- `deploy/ubuntu-22.04`: archivos para systemd y Nginx.
- `docs`: documentos de proyecto, integración, despliegue y encuesta.

La estrategia de ramas definida es:

- `dev`: trabajo y validación previa.
- `main`: base estable para producción.

## 12. Pruebas implementadas

El proyecto cuenta con pruebas automatizadas mínimas para reducir el riesgo de regresión:

- Pruebas de endpoints.
- Pruebas del flujo de pipeline.
- Validación de payload.
- Separación de campos multiselección.
- Mapeo de dimensiones analíticas.
- Recuperación de campos desde payload original.

Comando de ejecución:

```bash
cd nae-platform-api
.venv\Scripts\python.exe -m pytest -q
```

## 13. Estado actual del corte

Al 23 de junio de 2026, el sistema se encuentra listo para piloto operativo con las siguientes capacidades:

- Producción visible desde la URL pública.
- Recepción automática desde Google Forms.
- Procesamiento automático hasta capa analítica.
- Dashboard funcional.
- Detalle por respuesta.
- Exportación CSV.
- Modelo de datos completo para la versión actual de la encuesta.
- Registro de errores y ejecuciones.
- Procedimiento de despliegue documentado.
- Procedimiento para limpiar la base antes del piloto.

## 14. Riesgos y recomendaciones

### Riesgos principales

- Cambios manuales en textos de preguntas del Google Form pueden romper mapeos.
- El token de API debe mantenerse protegido.
- La base de datos debe respaldarse antes de ajustes de modelo o limpieza.
- Las respuestas con observaciones deben revisarse durante los primeros envíos reales.

### Recomendaciones

- Congelar la encuesta durante el piloto.
- No modificar títulos de preguntas sin actualizar backend y script.
- Revisar diariamente `control.errores_carga`.
- Hacer backup antes y después de la jornada piloto.
- Mantener `main` como rama de producción.
- Registrar cualquier cambio de encuesta como nueva versión controlada.

## 15. Conclusión

NAE Platform ya cuenta con una base técnica sólida para operar el piloto. La solución cubre el ciclo completo desde la encuesta hasta el dashboard, preserva datos originales, permite control de calidad y ofrece una vista operativa para seguimiento institucional.

El sistema no es solo un formulario publicado: es una plataforma de datos con trazabilidad, procesamiento por capas, controles de error, analítica y despliegue productivo. Esto deja al equipo en condiciones de iniciar el piloto, monitorear las respuestas y tomar decisiones de mejora sobre datos reales.


