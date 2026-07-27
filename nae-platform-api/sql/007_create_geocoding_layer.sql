CREATE TABLE IF NOT EXISTS operational.geocodificacion_entidades (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta(id) ON DELETE CASCADE,
    direccion_original TEXT,
    provincia VARCHAR(120),
    municipio VARCHAR(120),
    lat NUMERIC(10, 7),
    lng NUMERIC(10, 7),
    fuente VARCHAR(80) NOT NULL DEFAULT 'manual',
    confianza NUMERIC(5, 2),
    estado VARCHAR(30) NOT NULL DEFAULT 'pendiente_revision',
    observacion TEXT,
    fecha_validacion TIMESTAMP NULL,
    validado_por VARCHAR(120),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_geocodificacion_entidades_operational_respuesta_id UNIQUE (operational_respuesta_id),
    CONSTRAINT ck_geocodificacion_entidades_estado CHECK (
        estado IN ('pendiente_revision', 'geocodificada', 'validada', 'rechazada')
    ),
    CONSTRAINT ck_geocodificacion_entidades_lat CHECK (lat IS NULL OR lat BETWEEN -90 AND 90),
    CONSTRAINT ck_geocodificacion_entidades_lng CHECK (lng IS NULL OR lng BETWEEN -180 AND 180),
    CONSTRAINT ck_geocodificacion_entidades_confianza CHECK (confianza IS NULL OR confianza BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS ix_geocodificacion_entidades_estado
    ON operational.geocodificacion_entidades (estado);

CREATE INDEX IF NOT EXISTS ix_geocodificacion_entidades_provincia_municipio
    ON operational.geocodificacion_entidades (provincia, municipio);

CREATE INDEX IF NOT EXISTS ix_geocodificacion_entidades_lat_lng
    ON operational.geocodificacion_entidades (lat, lng)
    WHERE lat IS NOT NULL AND lng IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.geocodificacion_entidades TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.geocodificacion_entidades_id_seq TO usuario_nae;
