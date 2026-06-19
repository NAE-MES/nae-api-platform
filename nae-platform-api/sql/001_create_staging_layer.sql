CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.respuestas_formulario (
    id BIGSERIAL PRIMARY KEY,
    raw_respuesta_id BIGINT NOT NULL REFERENCES raw.respuestas_formulario (id) ON DELETE CASCADE,
    id_respuesta_origen VARCHAR(100),
    formulario_origen VARCHAR(200),
    fecha_respuesta TIMESTAMP NULL,
    consentimiento VARCHAR(50),
    provincia VARCHAR(100),
    municipio VARCHAR(150),
    ambito_actuacion VARCHAR(50),
    tipo_institucion VARCHAR(150),
    nombre_institucion VARCHAR(200),
    nivel_involucramiento VARCHAR(50),
    nivel_capacitacion_formadores VARCHAR(50),
    principal_necesidad VARCHAR(100),
    nivel_interes_gobierno VARCHAR(50),
    mecanismos_coordinacion VARCHAR(120),
    estado_validacion VARCHAR(30) NOT NULL DEFAULT 'pendiente',
    observaciones TEXT,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_staging_respuestas_formulario_raw_respuesta_id
    ON staging.respuestas_formulario (raw_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_staging_respuestas_formulario_estado_validacion
    ON staging.respuestas_formulario (estado_validacion);

CREATE INDEX IF NOT EXISTS ix_staging_respuestas_formulario_provincia_municipio
    ON staging.respuestas_formulario (provincia, municipio);

GRANT USAGE ON SCHEMA staging TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE staging.respuestas_formulario TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE staging.respuestas_formulario_id_seq TO usuario_nae;
