CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_entidad (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    entidad_nombre TEXT,
    rol_principal TEXT,
    municipio_responde_contexto TEXT,
    nivel_conocimiento_nae TEXT,
    datos_contacto_directo TEXT,
    direccion_fisica TEXT,
    telefonos TEXT,
    correo_electronico TEXT,
    sitio_web TEXT,
    redes_sociales TEXT,
    persona_contacto_cargo TEXT,
    territorios_servicio TEXT,
    cobertura_principal TEXT,
    modalidad_atencion TEXT,
    tipo_estructura_apoyo TEXT,
    presta_servicios_actualmente TEXT,
    nivel_involucramiento_apoyo TEXT,
    cantidad_nae_atendidos TEXT,
    antiguedad_servicios TEXT,
    capacidad_ampliar_cobertura TEXT,
    frecuencia_servicios TEXT,
    modalidad_pago_servicios TEXT,
    metodologia_apoyo TEXT,
    seguimiento_posterior TEXT,
    servicios_mas_demandados TEXT,
    servicios_mejor_funcionan TEXT,
    servicios_insuficientes TEXT,
    dispone_espacios_fisicos TEXT,
    disponibilidad_tecnologica TEXT,
    condiciones_conectividad TEXT,
    autonomia_energetica TEXT,
    mejoras_infraestructura TEXT,
    principal_brecha_ecosistema TEXT,
    actores_liderar_brecha TEXT,
    adecuacion_servicios TEXT,
    comentarios_servicios TEXT,
    mecanismos_coordinacion_apoyo TEXT,
    coordinador_articulacion TEXT,
    actividades_conjuntas TEXT,
    nivel_articulacion TEXT,
    capacidad_sostener_servicios TEXT,
    capacidad_actualizar_mapeo TEXT,
    apoyos_sostenibilidad TEXT,
    programas_especializados TEXT,
    descripcion_programas_especializados TEXT,
    observaciones_finales TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_servicios (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    servicio TEXT NOT NULL,
    ofrece_actualmente BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_fortalecer BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, servicio)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_tipos_nae (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    tipo_nae TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, tipo_nae)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_capacidades_tecnicas (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    capacidad_tecnica TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, capacidad_tecnica)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_necesidades_fortalecimiento (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    necesidad_fortalecimiento TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, necesidad_fortalecimiento)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_espacios (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    orden INTEGER NOT NULL,
    espacio TEXT,
    direccion_lugar TEXT,
    aforo_aprox TEXT,
    conectividad_tipo TEXT,
    energia_alternativa TEXT,
    aire_acondicionado TEXT,
    uso_posible TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, orden)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_perfiles (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    orden INTEGER NOT NULL,
    perfil TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, orden)
);

CREATE TABLE IF NOT EXISTS operational.respuestas_mapeo_recomendaciones (
    id BIGSERIAL PRIMARY KEY,
    operational_respuesta_id BIGINT NOT NULL REFERENCES operational.respuestas_encuesta (id) ON DELETE CASCADE,
    orden INTEGER NOT NULL,
    nombre_estructura TEXT,
    tipo_actor TEXT,
    servicios TEXT,
    municipio_territorio TEXT,
    contacto TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (operational_respuesta_id, orden)
);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_entidad_operational_id
    ON operational.respuestas_mapeo_entidad (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_servicios_operational_id
    ON operational.respuestas_mapeo_servicios (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_tipos_nae_operational_id
    ON operational.respuestas_mapeo_tipos_nae (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_capacidades_operational_id
    ON operational.respuestas_mapeo_capacidades_tecnicas (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_necesidades_operational_id
    ON operational.respuestas_mapeo_necesidades_fortalecimiento (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_espacios_operational_id
    ON operational.respuestas_mapeo_espacios (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_perfiles_operational_id
    ON operational.respuestas_mapeo_perfiles (operational_respuesta_id);

CREATE INDEX IF NOT EXISTS ix_operational_respuestas_mapeo_recomendaciones_operational_id
    ON operational.respuestas_mapeo_recomendaciones (operational_respuesta_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_entidad TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_servicios TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_tipos_nae TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_capacidades_tecnicas TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_necesidades_fortalecimiento TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_espacios TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_perfiles TO usuario_nae;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operational.respuestas_mapeo_recomendaciones TO usuario_nae;

GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_entidad_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_servicios_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_tipos_nae_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_capacidades_tecnicas_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_necesidades_fortalecimiento_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_espacios_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_perfiles_id_seq TO usuario_nae;
GRANT USAGE, SELECT, UPDATE ON SEQUENCE operational.respuestas_mapeo_recomendaciones_id_seq TO usuario_nae;
