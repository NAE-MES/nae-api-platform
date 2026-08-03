#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${DB_NAME:-nae}"

if [[ "${1:-}" != "--confirm" ]]; then
  cat <<USAGE
Uso:
  sudo -u postgres DB_NAME=nae ./scripts/clean_database.sh --confirm

Este script borra los datos operativos del proyecto y reinicia IDs.
No borra esquemas ni tablas. Ejecute backup antes de usarlo.
USAGE
  exit 1
fi

psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 <<'SQL'
TRUNCATE TABLE
    control.errores_carga,
    control.ejecucion_pipeline,
    raw.respuestas_formulario,
    staging.respuestas_formulario,
    operational.revisiones_datos,
    operational.respuestas_entidades_apoyo,
    operational.entidades_apoyo,
    operational.geocodificacion_entidades,
    operational.respuestas_mapeo_territorios_servicio,
    operational.respuestas_mapeo_recomendaciones,
    operational.respuestas_mapeo_perfiles,
    operational.respuestas_mapeo_espacios,
    operational.respuestas_mapeo_necesidades_fortalecimiento,
    operational.respuestas_mapeo_capacidades_tecnicas,
    operational.respuestas_mapeo_tipos_nae,
    operational.respuestas_mapeo_servicios,
    operational.respuestas_mapeo_entidad,
    operational.respuestas_temas_formacion,
    operational.respuestas_instituciones_participantes,
    operational.respuestas_limitaciones,
    operational.respuestas_encuesta,
    operational.municipios,
    operational.provincias,
    analytics.f_respuestas_encuesta,
    analytics.dim_respuesta_genero,
    analytics.dim_genero,
    analytics.dim_estado_validacion,
    analytics.dim_institucion,
    analytics.dim_territorio
RESTART IDENTITY CASCADE;
SQL

echo "Base de datos ${DB_NAME} limpiada correctamente."
