CREATE TABLE IF NOT EXISTS operational.entidades_apoyo (
    id BIGSERIAL PRIMARY KEY,
    nombre_canonico TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    provincia_id BIGINT REFERENCES operational.provincias (id) ON DELETE SET NULL,
    municipio_id BIGINT REFERENCES operational.municipios (id) ON DELETE SET NULL,
    tipo_estructura_apoyo TEXT,
    cobertura_principal TEXT,
    direccion_fisica TEXT,
    telefonos TEXT,
    correo_electronico TEXT,
    sitio_web TEXT,
    redes_sociales TEXT,
    persona_contacto_cargo TEXT,
    estado_revision VARCHAR(30) NOT NULL DEFAULT 'activa',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (provincia_id, municipio_id, nombre_normalizado)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_entidades_apoyo (
    id BIGSERIAL PRIMARY KEY,
    entidad_apoyo_id BIGINT NOT NULL REFERENCES operational.entidades_apoyo (id) ON DELETE CASCADE,
    entidad_sugerida_id BIGINT REFERENCES operational.entidades_apoyo (id) ON DELETE SET NULL,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    nombre_reportado TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL,
    metodo_resolucion VARCHAR(40) NOT NULL,
    confianza NUMERIC(5,4) NOT NULL DEFAULT 0,
    requiere_revision BOOLEAN NOT NULL DEFAULT FALSE,
    observacion TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id)
);

ALTER TABLE operational.respuestas_entidades_apoyo
    ADD COLUMN IF NOT EXISTS entidad_sugerida_id BIGINT REFERENCES operational.entidades_apoyo (id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS operational.revisiones_datos (
    id BIGSERIAL PRIMARY KEY,
    tipo_revision VARCHAR(40) NOT NULL,
    tabla_origen TEXT NOT NULL,
    registro_origen_id BIGINT NOT NULL,
    valor_original TEXT,
    valor_sugerido TEXT,
    valor_aprobado TEXT,
    accion VARCHAR(40) NOT NULL,
    usuario VARCHAR(120),
    observacion TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_operational_entidades_apoyo_nombre_normalizado
    ON operational.entidades_apoyo (nombre_normalizado);

CREATE INDEX IF NOT EXISTS ix_operational_entidades_apoyo_territorio
    ON operational.entidades_apoyo (provincia_id, municipio_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_entidades_entidad_id
    ON operational.respuestas_entidades_apoyo (entidad_apoyo_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_entidades_revision
    ON operational.respuestas_entidades_apoyo (requiere_revision);

CREATE INDEX IF NOT EXISTS ix_operational_revisiones_datos_tipo
    ON operational.revisiones_datos (tipo_revision, created_at DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.entidades_apoyo TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_entidades_apoyo TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.revisiones_datos TO usuario_nae;

GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.entidades_apoyo_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_entidades_apoyo_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.revisiones_datos_id_seq TO usuario_nae;
