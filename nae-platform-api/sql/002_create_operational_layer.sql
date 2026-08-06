CREATE SCHEMA IF NOT EXISTS operational;

CREATE TABLE IF NOT EXISTS operational.provincias (
    id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operational.municipios (
    id BIGSERIAL PRIMARY KEY,
    provincia_id BIGINT NOT NULL REFERENCES operational.provincias (id) ON DELETE RESTRICT,
    nombre VARCHAR(150) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (provincia_id, nombre)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_encuesta (
    id BIGSERIAL PRIMARY KEY,
    staging_respuesta_id BIGINT NOT NULL REFERENCES staging.respuestas_formulario (id) ON DELETE CASCADE,
    raw_respuesta_id BIGINT NOT NULL REFERENCES raw.respuestas_formulario (id) ON DELETE CASCADE,
    id_respuesta_origen VARCHAR(100),
    formulario_origen VARCHAR(200),
    fecha_respuesta TIMESTAMP NULL,
    consentimiento TEXT,
    provincia_id BIGINT NOT NULL REFERENCES operational.provincias (id),
    municipio_id BIGINT NOT NULL REFERENCES operational.municipios (id),
    ambito_actuacion TEXT,
    tipo_institucion TEXT,
    nombre_institucion TEXT,
    nivel_involucramiento TEXT,
    nivel_capacitacion_formadores TEXT,
    principal_necesidad TEXT,
    nivel_interes_gobierno TEXT,
    mecanismos_coordinacion TEXT,
    estado_validacion VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (staging_respuesta_id)
);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_encuesta_provincia_id
    ON operational.respuestas_encuesta (provincia_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_encuesta_municipio_id
    ON operational.respuestas_encuesta (municipio_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_encuesta_estado_validacion
    ON operational.respuestas_encuesta (estado_validacion);

GRANT USAGE ON SCHEMA operational TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.provincias TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.municipios TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_encuesta TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.provincias_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.municipios_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_encuesta_id_seq TO usuario_nae;
