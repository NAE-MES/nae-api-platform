from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import text

from app.database import SessionLocal


PIPELINE_NAME = "operational_to_analytics"


def _resolve_territorio(db, provincia_id: int, municipio_id: int, provincia_nombre: str, municipio_nombre: str) -> int:
    return db.execute(
        text("""
            INSERT INTO analytics.dim_territorio (
                provincia_id,
                municipio_id,
                provincia_nombre,
                municipio_nombre
            )
            VALUES (
                :provincia_id,
                :municipio_id,
                :provincia_nombre,
                :municipio_nombre
            )
            ON CONFLICT (provincia_id, municipio_id)
            DO UPDATE SET
                provincia_nombre = EXCLUDED.provincia_nombre,
                municipio_nombre = EXCLUDED.municipio_nombre
            RETURNING id
        """),
        {
            "provincia_id": provincia_id,
            "municipio_id": municipio_id,
            "provincia_nombre": provincia_nombre,
            "municipio_nombre": municipio_nombre,
        },
    ).scalar_one()


def _resolve_institucion(db, tipo_institucion: Optional[str], nombre_institucion: Optional[str]) -> int:
    return db.execute(
        text("""
            INSERT INTO analytics.dim_institucion (
                tipo_institucion,
                nombre_institucion
            )
            VALUES (
                :tipo_institucion,
                :nombre_institucion
            )
            ON CONFLICT (tipo_institucion, nombre_institucion)
            DO UPDATE SET
                tipo_institucion = EXCLUDED.tipo_institucion,
                nombre_institucion = EXCLUDED.nombre_institucion
            RETURNING id
        """),
        {
            "tipo_institucion": tipo_institucion,
            "nombre_institucion": nombre_institucion,
        },
    ).scalar_one()


def _resolve_estado_validacion(db, estado_validacion: str) -> int:
    return db.execute(
        text("""
            INSERT INTO analytics.dim_estado_validacion (estado_validacion)
            VALUES (:estado_validacion)
            ON CONFLICT (estado_validacion)
            DO UPDATE SET estado_validacion = EXCLUDED.estado_validacion
            RETURNING id
        """),
        {"estado_validacion": estado_validacion},
    ).scalar_one()


def _resolve_genero(db, genero: Optional[str]) -> Optional[int]:
    if not genero:
        return None
    return db.execute(
        text("""
            INSERT INTO analytics.dim_genero (genero)
            VALUES (:genero)
            ON CONFLICT (genero)
            DO UPDATE SET genero = EXCLUDED.genero
            RETURNING id
        """),
        {"genero": genero},
    ).scalar_one()


def _resolve_respuesta_genero(
    db,
    nivel_instruccion: Optional[str],
    nivel_conocimiento_municipio: Optional[str],
    mayoria_titulares_emprendimientos: Optional[str],
    porcentaje_mujeres_directivas: Optional[str],
    programas_mujeres_emprendedoras: Optional[str],
    descripcion_programa_mujeres: Optional[str],
) -> Optional[int]:
    values = (
        nivel_instruccion,
        nivel_conocimiento_municipio,
        mayoria_titulares_emprendimientos,
        porcentaje_mujeres_directivas,
        programas_mujeres_emprendedoras,
        descripcion_programa_mujeres,
    )
    if not any(values):
        return None

    return db.execute(
        text("""
            INSERT INTO analytics.dim_respuesta_genero (
                nivel_instruccion,
                nivel_conocimiento_municipio,
                mayoria_titulares_emprendimientos,
                porcentaje_mujeres_directivas,
                programas_mujeres_emprendedoras,
                descripcion_programa_mujeres
            )
            VALUES (
                :nivel_instruccion,
                :nivel_conocimiento_municipio,
                :mayoria_titulares_emprendimientos,
                :porcentaje_mujeres_directivas,
                :programas_mujeres_emprendedoras,
                :descripcion_programa_mujeres
            )
            ON CONFLICT (
                nivel_instruccion,
                nivel_conocimiento_municipio,
                mayoria_titulares_emprendimientos,
                porcentaje_mujeres_directivas,
                programas_mujeres_emprendedoras,
                descripcion_programa_mujeres
            )
            DO UPDATE SET
                nivel_instruccion = EXCLUDED.nivel_instruccion,
                nivel_conocimiento_municipio = EXCLUDED.nivel_conocimiento_municipio,
                mayoria_titulares_emprendimientos = EXCLUDED.mayoria_titulares_emprendimientos,
                porcentaje_mujeres_directivas = EXCLUDED.porcentaje_mujeres_directivas,
                programas_mujeres_emprendedoras = EXCLUDED.programas_mujeres_emprendedoras,
                descripcion_programa_mujeres = EXCLUDED.descripcion_programa_mujeres
            RETURNING id
        """),
        {
            "nivel_instruccion": nivel_instruccion,
            "nivel_conocimiento_municipio": nivel_conocimiento_municipio,
            "mayoria_titulares_emprendimientos": mayoria_titulares_emprendimientos,
            "porcentaje_mujeres_directivas": porcentaje_mujeres_directivas,
            "programas_mujeres_emprendedoras": programas_mujeres_emprendedoras,
            "descripcion_programa_mujeres": descripcion_programa_mujeres,
        },
    ).scalar_one()


def _upsert_fact(
    db,
    row: Dict[str, Any],
    territorio_id: int,
    institucion_id: int,
    estado_id: int,
    genero_id: Optional[int],
    respuesta_genero_id: Optional[int],
) -> int:
    return db.execute(
        text("""
            INSERT INTO analytics.f_respuestas_encuesta (
                operational_respuesta_id,
                territorio_id,
                institucion_id,
                estado_validacion_id,
                genero_id,
                respuesta_genero_id,
                version_encuesta,
                fecha_respuesta,
                consentimiento,
                ambito_actuacion,
                nivel_involucramiento,
                nivel_capacitacion_formadores,
                principal_necesidad,
                nivel_interes_gobierno,
                mecanismos_coordinacion,
                created_at,
                updated_at
            )
            VALUES (
                :operational_respuesta_id,
                :territorio_id,
                :institucion_id,
                :estado_validacion_id,
                :genero_id,
                :respuesta_genero_id,
                :version_encuesta,
                :fecha_respuesta,
                :consentimiento,
                :ambito_actuacion,
                :nivel_involucramiento,
                :nivel_capacitacion_formadores,
                :principal_necesidad,
                :nivel_interes_gobierno,
                :mecanismos_coordinacion,
                NOW(),
                NOW()
            )
            ON CONFLICT (operational_respuesta_id)
            DO UPDATE SET
                territorio_id = EXCLUDED.territorio_id,
                institucion_id = EXCLUDED.institucion_id,
                estado_validacion_id = EXCLUDED.estado_validacion_id,
                genero_id = EXCLUDED.genero_id,
                respuesta_genero_id = EXCLUDED.respuesta_genero_id,
                version_encuesta = EXCLUDED.version_encuesta,
                fecha_respuesta = EXCLUDED.fecha_respuesta,
                consentimiento = EXCLUDED.consentimiento,
                ambito_actuacion = EXCLUDED.ambito_actuacion,
                nivel_involucramiento = EXCLUDED.nivel_involucramiento,
                nivel_capacitacion_formadores = EXCLUDED.nivel_capacitacion_formadores,
                principal_necesidad = EXCLUDED.principal_necesidad,
                nivel_interes_gobierno = EXCLUDED.nivel_interes_gobierno,
                mecanismos_coordinacion = EXCLUDED.mecanismos_coordinacion,
                updated_at = NOW()
            RETURNING id
        """),
        {
            "operational_respuesta_id": row["id"],
            "territorio_id": territorio_id,
            "institucion_id": institucion_id,
            "estado_validacion_id": estado_id,
            "genero_id": genero_id,
            "respuesta_genero_id": respuesta_genero_id,
            "version_encuesta": row["version_encuesta"],
            "fecha_respuesta": row["fecha_respuesta"],
            "consentimiento": row["consentimiento"],
            "ambito_actuacion": row["ambito_actuacion"],
            "nivel_involucramiento": row["nivel_involucramiento"],
            "nivel_capacitacion_formadores": row["nivel_capacitacion_formadores"],
            "principal_necesidad": row["principal_necesidad"],
            "nivel_interes_gobierno": row["nivel_interes_gobierno"],
            "mecanismos_coordinacion": row["mecanismos_coordinacion"],
        },
    ).scalar_one()


def process_operational_to_analytics(limit: int = 100) -> Dict[str, Any]:
    db = SessionLocal()
    pipeline_run_id: Optional[int] = None
    stats = {"total": 0, "cargada": 0, "saltada": 0, "errores_registrados": 0}

    try:
        pipeline_run_id = db.execute(
            text("""
                INSERT INTO control.ejecucion_pipeline (
                    tipo_pipeline,
                    fecha_inicio,
                    estado,
                    registros_procesados,
                    registros_error
                )
                VALUES (
                    :tipo_pipeline,
                    NOW(),
                    'en_ejecucion',
                    0,
                    0
                )
                RETURNING id
            """),
            {"tipo_pipeline": PIPELINE_NAME},
        ).scalar_one()
        db.commit()

        rows = db.execute(
            text("""
                SELECT o.id,
                       o.raw_respuesta_id,
                       o.staging_respuesta_id,
                       o.fecha_respuesta,
                       o.consentimiento,
                       o.version_encuesta,
                       o.genero,
                       o.ambito_actuacion,
                       o.tipo_institucion,
                       o.nombre_institucion,
                       o.nivel_involucramiento,
                       o.nivel_capacitacion_formadores,
                       o.nivel_conocimiento_municipio,
                       o.nivel_instruccion,
                       o.porcentaje_mujeres_directivas,
                       o.programas_mujeres_emprendedoras,
                       o.descripcion_programa_mujeres,
                       o.mayoria_titulares_emprendimientos,
                       o.principal_necesidad,
                       o.nivel_interes_gobierno,
                       o.mecanismos_coordinacion,
                       o.estado_validacion,
                       p.id AS provincia_id,
                       p.nombre AS provincia_nombre,
                       m.id AS municipio_id,
                       m.nombre AS municipio_nombre
                FROM operational.respuestas_encuesta o
                JOIN operational.provincias p ON p.id = o.provincia_id
                JOIN operational.municipios m ON m.id = o.municipio_id
                WHERE o.estado_validacion IN ('validada', 'con_observaciones')
                ORDER BY o.id
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

        for row in rows:
            stats["total"] += 1
            territorio_id = _resolve_territorio(
                db,
                row["provincia_id"],
                row["municipio_id"],
                row["provincia_nombre"],
                row["municipio_nombre"],
            )
            institucion_id = _resolve_institucion(db, row["tipo_institucion"], row["nombre_institucion"])
            estado_id = _resolve_estado_validacion(db, row["estado_validacion"])
            genero_id = _resolve_genero(db, row["genero"])
            respuesta_genero_id = _resolve_respuesta_genero(
                db,
                row["nivel_instruccion"],
                row["nivel_conocimiento_municipio"],
                row["mayoria_titulares_emprendimientos"],
                row["porcentaje_mujeres_directivas"],
                row["programas_mujeres_emprendedoras"],
                row["descripcion_programa_mujeres"],
            )
            _upsert_fact(db, row, territorio_id, institucion_id, estado_id, genero_id, respuesta_genero_id)
            stats["cargada"] += 1

        if pipeline_run_id is not None:
            db.execute(
                text("""
                    UPDATE control.ejecucion_pipeline
                    SET fecha_fin = NOW(),
                        estado = 'completado',
                        registros_procesados = :registros_procesados,
                        registros_error = :registros_error
                    WHERE id = :id
                """),
                {
                    "id": pipeline_run_id,
                    "registros_procesados": stats["total"],
                    "registros_error": stats["errores_registrados"],
                },
            )

        db.commit()
        return {"status": "ok", "pipeline_run_id": pipeline_run_id, "stats": stats}

    except Exception as exc:
        db.rollback()
        if pipeline_run_id is not None:
            try:
                db.execute(
                    text("""
                        UPDATE control.ejecucion_pipeline
                        SET fecha_fin = NOW(),
                            estado = 'fallido',
                            mensaje_error = :mensaje_error,
                            registros_procesados = :registros_procesados,
                            registros_error = :registros_error
                        WHERE id = :id
                    """),
                    {
                        "id": pipeline_run_id,
                        "mensaje_error": str(exc),
                        "registros_procesados": stats["total"],
                        "registros_error": stats["errores_registrados"],
                    },
                )
                db.commit()
            except Exception:
                db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        db.close()
