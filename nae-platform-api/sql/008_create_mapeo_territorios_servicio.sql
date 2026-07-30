CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_territorios_servicio (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    texto_original TEXT NOT NULL,
    provincia_resuelta VARCHAR(100),
    municipio_resuelto VARCHAR(150),
    municipio_id BIGINT REFERENCES operational.municipios (id) ON DELETE SET NULL,
    metodo_resolucion VARCHAR(40) NOT NULL,
    confianza NUMERIC(5,4) NOT NULL DEFAULT 0,
    requiere_revision BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, texto_original, provincia_resuelta, municipio_resuelto)
);

CREATE INDEX IF NOT EXISTS ix_operational_mapeo_territorios_operational_id
    ON operational.respuestas_mapeo_territorios_servicio (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_mapeo_territorios_municipio_id
    ON operational.respuestas_mapeo_territorios_servicio (municipio_id);

CREATE INDEX IF NOT EXISTS ix_operational_mapeo_territorios_revision
    ON operational.respuestas_mapeo_territorios_servicio (requiere_revision);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_territorios_servicio TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_territorios_servicio_id_seq TO usuario_nae;
