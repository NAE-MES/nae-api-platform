# Actualización por encuesta aprobada de mapeo NAE

Fecha: 2026-07-25

## Fuente considerada válida

La versión operativa publicada en Google Forms se tomó desde:

- `scritps/crear_formulario_mapeo_estructuras_nae_v3.gs`

El documento de referencia funcional es:

- `docs/Encuesta_mapeo_entidad_apoyo_nae.docx`

La encuesta cambia el enfoque del levantamiento anterior. Ahora el objetivo es el mapeo de estructuras de apoyo a los nuevos actores económicos (NAE), con información para diagnóstico, mapa interactivo y directorio.

## Cambios funcionales aplicados

Se actualizó el pipeline para reconocer la versión:

- `mapeo_estructuras_v1`

Se ajustó la validación de staging para que la encuesta nueva no exija campos de la encuesta anterior, por ejemplo género, nivel de instrucción, consentimiento, capacitación de formadores o nivel de interés del gobierno.

Se incorporó soporte para el municipio con título dinámico de Google Forms:

- `1.2* Municipio donde se ubica la entidad o estructura de apoyo — {Provincia}`

Se mapearon los campos principales de la encuesta nueva hacia el modelo actual para mantener operativo el dashboard:

| Encuesta nueva | Campo operativo actual |
| --- | --- |
| `0.1* Entidad a la que pertenece` | `nombre_institucion` |
| `0.4* Nivel de conocimiento sobre los NAE en el municipio` | `nivel_conocimiento_municipio` |
| `1.1* Provincia` | `provincia` |
| `1.2* Municipio donde se ubica...` | `municipio` |
| `1.4* Cobertura principal de actuación` | `ambito_actuacion` |
| `1.6* Tipo de entidad o estructura de apoyo` | `tipo_institucion` |
| `1.8* Nivel de involucramiento...` | `nivel_involucramiento` |
| `5.2* Principal brecha del ecosistema...` | `principal_necesidad` |
| `6.1* ¿Existen mecanismos de coordinación...` | `mecanismos_coordinacion` |

También se conectaron preguntas multiselección nuevas a las tablas usadas por el panel:

| Encuesta nueva | Tabla operacional actual |
| --- | --- |
| `5.1* Principales necesidades de los NAE...` | `operational.respuestas_temas_formacion` |
| `6.2* Actores con los que coordina...` | `operational.respuestas_instituciones_participantes` |
| `7.1* Principales limitaciones...` | `operational.respuestas_limitaciones` |

## Modelo ampliado creado

Se agregó la migración:

- `nae-platform-api/sql/006_create_mapeo_estructuras_v1.sql`

Esta migración crea tablas operacionales específicas para la encuesta de mapeo:

- `operational.respuestas_mapeo_entidad`: datos de contacto, cobertura, modalidad de atención, infraestructura, sostenibilidad, programas especializados y observaciones.
- `operational.respuestas_mapeo_servicios`: matriz de servicios ofrecidos y servicios que requieren fortalecimiento.
- `operational.respuestas_mapeo_tipos_nae`: tipos de NAE atendidos o potencialmente atendidos.
- `operational.respuestas_mapeo_capacidades_tecnicas`: capacidades técnicas del equipo.
- `operational.respuestas_mapeo_necesidades_fortalecimiento`: necesidades de fortalecimiento del equipo.
- `operational.respuestas_mapeo_espacios`: espacios físicos disponibles o potenciales.
- `operational.respuestas_mapeo_perfiles`: personas formadoras, mentoras o expertas disponibles.
- `operational.respuestas_mapeo_recomendaciones`: otras estructuras de apoyo recomendadas.

## API y visualización

Se agregaron endpoints para la futura sección de mapa/directorio:

- `GET /api/v1/entidades-apoyo`
- `GET /api/v1/entidades-apoyo.csv`

La vista de detalle de respuesta ahora muestra bloques específicos para `mapeo_estructuras_v1`:

- Contacto para mapa y directorio.
- Cobertura y atención.
- Tipos de NAE.
- Servicios de apoyo.
- Funcionamiento de servicios.
- Recursos e infraestructura.
- Espacios disponibles.
- Capacidades, perfiles y necesidades de fortalecimiento.
- Articulación y sostenibilidad.
- Inclusión y estructuras recomendadas.

## Paso de despliegue requerido

Antes de procesar respuestas nuevas en producción con esta versión, ejecutar:

```bash
cd /srv/nae/nae-api-platform/nae-platform-api
sudo -u nae psql -d nae -f sql/006_create_mapeo_estructuras_v1.sql
sudo systemctl restart nae-api
```

Después de aplicar la migración, se pueden reprocesar pendientes con:

```bash
export API_TOKEN='TOKEN_REAL'

curl -X POST "http://127.0.0.1:8000/api/v1/pipelines/staging/raw-to-staging?limit=1000" \
  -H "Authorization: Bearer $API_TOKEN"

curl -X POST "http://127.0.0.1:8000/api/v1/pipelines/operational/staging-to-operational?limit=1000" \
  -H "Authorization: Bearer $API_TOKEN"

curl -X POST "http://127.0.0.1:8000/api/v1/pipelines/analytics/operational-to-analytics?limit=1000" \
  -H "Authorization: Bearer $API_TOKEN"
```

## Integración Google Forms

Se actualizó:

- `docs/google-apps-script-nae.gs`

Cambios realizados:

- Título del formulario actualizado.
- Versión enviada al API: `mapeo_estructuras_v1`.
- Detección de versión por campos de la encuesta nueva.
- Detección del municipio aunque Google Forms cambie el título según la provincia.

## Cambios pendientes recomendados

Lo pendiente ya no es preservar los datos, sino construir las interfaces finales:

- Pantalla pública de mapa/directorio usando `GET /api/v1/entidades-apoyo`.
- Exportación PDF del directorio.
- Control de acceso para la sección privada de analítica.
- Ajuste final del dashboard al nuevo objetivo de mapeo.
