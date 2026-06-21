CREATE SCHEMA IF NOT EXISTS control;

CREATE TABLE IF NOT EXISTS control.ejecucion_pipeline (
    id BIGSERIAL PRIMARY KEY,
    tipo_pipeline VARCHAR(100) NOT NULL,
    fecha_inicio TIMESTAMP NOT NULL DEFAULT NOW(),
    fecha_fin TIMESTAMP NULL,
    estado VARCHAR(30) NOT NULL,
    registros_procesados INTEGER NOT NULL DEFAULT 0,
    registros_error INTEGER NOT NULL DEFAULT 0,
    mensaje_error TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_control_ejecucion_pipeline_tipo_pipeline
    ON control.ejecucion_pipeline (tipo_pipeline);

CREATE INDEX IF NOT EXISTS ix_control_ejecucion_pipeline_estado
    ON control.ejecucion_pipeline (estado);

CREATE TABLE IF NOT EXISTS control.errores_carga (
    id BIGSERIAL PRIMARY KEY,
    respuesta_raw_id BIGINT NOT NULL,
    campo VARCHAR(150) NOT NULL,
    valor_recibido TEXT NULL,
    tipo_error VARCHAR(100) NOT NULL,
    descripcion TEXT NOT NULL,
    estado_correccion VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_control_errores_carga_respuesta_raw_id
    ON control.errores_carga (respuesta_raw_id);

CREATE INDEX IF NOT EXISTS ix_control_errores_carga_estado_correccion
    ON control.errores_carga (estado_correccion);

GRANT USAGE ON SCHEMA control TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE control.ejecucion_pipeline TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE control.errores_carga TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE control.ejecucion_pipeline_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE control.errores_carga_id_seq TO usuario_nae;
