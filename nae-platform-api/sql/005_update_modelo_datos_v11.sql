ALTER TABLE IF EXISTS raw.respuestas_formulario
    ADD COLUMN IF NOT EXISTS version_encuesta VARCHAR(20);

ALTER TABLE IF EXISTS staging.respuestas_formulario
    ADD COLUMN IF NOT EXISTS version_encuesta VARCHAR(20),
    ADD COLUMN IF NOT EXISTS genero VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nivel_conocimiento_municipio VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nivel_instruccion VARCHAR(50),
    ADD COLUMN IF NOT EXISTS mayoria_titulares_emprendimientos VARCHAR(50),
    ADD COLUMN IF NOT EXISTS porcentaje_mujeres_directivas VARCHAR(20),
    ADD COLUMN IF NOT EXISTS programas_mujeres_emprendedoras VARCHAR(20),
    ADD COLUMN IF NOT EXISTS descripcion_programa_mujeres TEXT;

ALTER TABLE IF EXISTS operational.respuestas_encuesta
    ADD COLUMN IF NOT EXISTS version_encuesta VARCHAR(20),
    ADD COLUMN IF NOT EXISTS genero VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nivel_conocimiento_municipio VARCHAR(50),
    ADD COLUMN IF NOT EXISTS nivel_instruccion VARCHAR(50),
    ADD COLUMN IF NOT EXISTS mayoria_titulares_emprendimientos VARCHAR(50),
    ADD COLUMN IF NOT EXISTS porcentaje_mujeres_directivas VARCHAR(20),
    ADD COLUMN IF NOT EXISTS programas_mujeres_emprendedoras VARCHAR(20),
    ADD COLUMN IF NOT EXISTS descripcion_programa_mujeres TEXT;

CREATE TABLE IF NOT EXISTS analytics.dim_genero (
    id BIGSERIAL PRIMARY KEY,
    genero VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics.dim_respuesta_genero (
    id BIGSERIAL PRIMARY KEY,
    nivel_instruccion VARCHAR(50),
    nivel_conocimiento_municipio VARCHAR(50),
    mayoria_titulares_emprendimientos VARCHAR(50),
    porcentaje_mujeres_directivas VARCHAR(20),
    programas_mujeres_emprendedoras VARCHAR(20),
    descripcion_programa_mujeres TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (
        nivel_instruccion,
        nivel_conocimiento_municipio,
        mayoria_titulares_emprendimientos,
        porcentaje_mujeres_directivas,
        programas_mujeres_emprendedoras,
        descripcion_programa_mujeres
    )
);

ALTER TABLE IF EXISTS analytics.f_respuestas_encuesta
    ADD COLUMN IF NOT EXISTS genero_id BIGINT REFERENCES analytics.dim_genero (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS respuesta_genero_id BIGINT REFERENCES analytics.dim_respuesta_genero (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS version_encuesta VARCHAR(20);

CREATE INDEX IF NOT EXISTS ix_analytics_f_respuestas_encuesta_genero_id
    ON analytics.f_respuestas_encuesta (genero_id);

CREATE INDEX IF NOT EXISTS ix_analytics_f_respuestas_encuesta_respuesta_genero_id
    ON analytics.f_respuestas_encuesta (respuesta_genero_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE analytics.dim_genero TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE analytics.dim_respuesta_genero TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE analytics.f_respuestas_encuesta TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE analytics.dim_genero_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE analytics.dim_respuesta_genero_id_seq TO usuario_nae;
