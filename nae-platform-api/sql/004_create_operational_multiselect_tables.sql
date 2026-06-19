CREATE TABLE IF NOT EXISTS operational.respuestas_temas_formacion (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    tema_formacion VARCHAR(200) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, tema_formacion)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_instituciones_participantes (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    institucion_participante VARCHAR(200) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, institucion_participante)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_limitaciones (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    limitacion VARCHAR(200) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, limitacion)
);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_temas_formacion_respuesta_id
    ON operational.respuestas_temas_formacion (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_instituciones_participantes_respuesta_id
    ON operational.respuestas_instituciones_participantes (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_limitaciones_respuesta_id
    ON operational.respuestas_limitaciones (operational_respuesta_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_temas_formacion TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_instituciones_participantes TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_limitaciones TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_temas_formacion_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_instituciones_participantes_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_limitaciones_id_seq TO usuario_nae;
