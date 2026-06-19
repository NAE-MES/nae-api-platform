CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.dim_territorio (
    id BIGSERIAL PRIMARY KEY,
    provincia_id BIGINT NOT NULL REFERENCES operational.provincias (id) ON DELETE RESTRICT,
    municipio_id BIGINT NOT NULL REFERENCES operational.municipios (id) ON DELETE RESTRICT,
    provincia_nombre VARCHAR(100) NOT NULL,
    municipio_nombre VARCHAR(150) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (provincia_id, municipio_id)
);

CREATE TABLE IF NOT EXISTS analytics.dim_institucion (
    id BIGSERIAL PRIMARY KEY,
    tipo_institucion VARCHAR(150),
    nombre_institucion VARCHAR(200),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (tipo_institucion, nombre_institucion)
);

CREATE TABLE IF NOT EXISTS analytics.dim_estado_validacion (
    id BIGSERIAL PRIMARY KEY,
    estado_validacion VARCHAR(30) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics.f_respuestas_encuesta (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    territorio_id BIGINT NOT NULL REFERENCES analytics.dim_territorio (id),
    institucion_id BIGINT NOT NULL REFERENCES analytics.dim_institucion (id),
    estado_validacion_id BIGINT NOT NULL REFERENCES analytics.dim_estado_validacion (id),
    fecha_respuesta TIMESTAMP NULL,
    consentimiento VARCHAR(50),
    ambito_actuacion VARCHAR(50),
    nivel_involucramiento VARCHAR(50),
    nivel_capacitacion_formadores VARCHAR(50),
    principal_necesidad VARCHAR(100),
    nivel_interes_gobierno VARCHAR(50),
    mecanismos_coordinacion VARCHAR(120),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id)
);

CREATE INDEX IF NOT EXISTS ix_f_respuestas_encuesta_territorio_id
    ON analytics.f_respuestas_encuesta (territorio_id);

CREATE INDEX IF NOT EXISTS ix_f_respuestas_encuesta_institucion_id
    ON analytics.f_respuestas_encuesta (institucion_id);

CREATE INDEX IF NOT EXISTS ix_f_respuestas_encuesta_estado_validacion_id
    ON analytics.f_respuestas_encuesta (estado_validacion_id);

GRANT USAGE ON SCHEMA analytics TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE analytics.dim_territorio TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE analytics.dim_institucion TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE analytics.dim_estado_validacion TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE analytics.f_respuestas_encuesta TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE analytics.dim_territorio_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE analytics.dim_institucion_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE analytics.dim_estado_validacion_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE analytics.f_respuestas_encuesta_id_seq TO usuario_nae;
