-- Hotfix: widen legacy denormalized survey fields used by the approved mapping survey.
-- Google Forms stores the full choice text. Some approved choices exceed the older VARCHAR(50) limits.

ALTER TABLE IF EXISTS staging.respuestas_formulario
    ALTER COLUMN consentimiento TYPE TEXT,
    ALTER COLUMN ambito_actuacion TYPE TEXT,
    ALTER COLUMN tipo_institucion TYPE TEXT,
    ALTER COLUMN nombre_institucion TYPE TEXT,
    ALTER COLUMN nivel_involucramiento TYPE TEXT,
    ALTER COLUMN nivel_capacitacion_formadores TYPE TEXT,
    ALTER COLUMN principal_necesidad TYPE TEXT,
    ALTER COLUMN nivel_interes_gobierno TYPE TEXT,
    ALTER COLUMN mecanismos_coordinacion TYPE TEXT,
    ALTER COLUMN genero TYPE TEXT,
    ALTER COLUMN nivel_conocimiento_municipio TYPE TEXT,
    ALTER COLUMN nivel_instruccion TYPE TEXT,
    ALTER COLUMN mayoria_titulares_emprendimientos TYPE TEXT,
    ALTER COLUMN porcentaje_mujeres_directivas TYPE TEXT,
    ALTER COLUMN programas_mujeres_emprendedoras TYPE TEXT;

ALTER TABLE IF EXISTS operational.respuestas_encuesta
    ALTER COLUMN consentimiento TYPE TEXT,
    ALTER COLUMN ambito_actuacion TYPE TEXT,
    ALTER COLUMN tipo_institucion TYPE TEXT,
    ALTER COLUMN nombre_institucion TYPE TEXT,
    ALTER COLUMN nivel_involucramiento TYPE TEXT,
    ALTER COLUMN nivel_capacitacion_formadores TYPE TEXT,
    ALTER COLUMN principal_necesidad TYPE TEXT,
    ALTER COLUMN nivel_interes_gobierno TYPE TEXT,
    ALTER COLUMN mecanismos_coordinacion TYPE TEXT,
    ALTER COLUMN genero TYPE TEXT,
    ALTER COLUMN nivel_conocimiento_municipio TYPE TEXT,
    ALTER COLUMN nivel_instruccion TYPE TEXT,
    ALTER COLUMN mayoria_titulares_emprendimientos TYPE TEXT,
    ALTER COLUMN porcentaje_mujeres_directivas TYPE TEXT,
    ALTER COLUMN programas_mujeres_emprendedoras TYPE TEXT;

ALTER TABLE IF EXISTS analytics.f_respuestas_encuesta
    ALTER COLUMN consentimiento TYPE TEXT,
    ALTER COLUMN ambito_actuacion TYPE TEXT,
    ALTER COLUMN nivel_involucramiento TYPE TEXT,
    ALTER COLUMN nivel_capacitacion_formadores TYPE TEXT,
    ALTER COLUMN principal_necesidad TYPE TEXT,
    ALTER COLUMN nivel_interes_gobierno TYPE TEXT,
    ALTER COLUMN mecanismos_coordinacion TYPE TEXT;

ALTER TABLE IF EXISTS analytics.dim_genero
    ALTER COLUMN genero TYPE TEXT;

ALTER TABLE IF EXISTS analytics.dim_respuesta_genero
    ALTER COLUMN nivel_instruccion TYPE TEXT,
    ALTER COLUMN nivel_conocimiento_municipio TYPE TEXT,
    ALTER COLUMN mayoria_titulares_emprendimientos TYPE TEXT,
    ALTER COLUMN porcentaje_mujeres_directivas TYPE TEXT,
    ALTER COLUMN programas_mujeres_emprendedoras TYPE TEXT;
