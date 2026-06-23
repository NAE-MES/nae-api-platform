from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import text

from app.database import SessionLocal


PIPELINE_NAME = "staging_to_operational"

MULTISELECT_FIELDS = {
    "3.2 Temas prioritarios de formación": ("respuestas_temas_formacion", "tema_formacion"),
    "3.2 Temas prioritarios de formación que necesita": ("respuestas_temas_formacion", "tema_formacion"),
    "5.3 Instituciones que participan en actividades formativas": (
        "respuestas_instituciones_participantes",
        "institucion_participante",
    ),
    "4.3 Instituciones que participan en actividades formativas": (
        "respuestas_instituciones_participantes",
        "institucion_participante",
    ),
    "5.4 Principales limitaciones": ("respuestas_limitaciones", "limitacion"),
    "4.4 Principales limitaciones que existen para desarrollar actividades formativas": (
        "respuestas_limitaciones",
        "limitacion",
    ),
}


@dataclass
class OperationResult:
    status: str
    raw_respuesta_id: int
    staging_respuesta_id: int
    operational_respuesta_id: Optional[int] = None
    observaciones: List[str] = field(default_factory=list)


def _resolve_provincia(db, provincia: str) -> int:
    provincia_id = db.execute(
        text("""
            INSERT INTO operational.provincias (nombre)
            VALUES (:nombre)
            ON CONFLICT (nombre)
            DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id
        """),
        {"nombre": provincia},
    ).scalar_one()
    return provincia_id


def _resolve_municipio(db, provincia_id: int, municipio: str) -> int:
    municipio_id = db.execute(
        text("""
            INSERT INTO operational.municipios (provincia_id, nombre)
            VALUES (:provincia_id, :nombre)
            ON CONFLICT (provincia_id, nombre)
            DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id
        """),
        {"provincia_id": provincia_id, "nombre": municipio},
    ).scalar_one()
    return municipio_id


def _upsert_operational_response(db, row: Dict[str, Any], provincia_id: int, municipio_id: int) -> int:
    operational_id = db.execute(
        text("""
            INSERT INTO operational.respuestas_encuesta (
                staging_respuesta_id,
                raw_respuesta_id,
                id_respuesta_origen,
                formulario_origen,
                fecha_respuesta,
                consentimiento,
                version_encuesta,
                genero,
                nivel_conocimiento_municipio,
                nivel_instruccion,
                provincia_id,
                municipio_id,
                ambito_actuacion,
                tipo_institucion,
                nombre_institucion,
                nivel_involucramiento,
                nivel_capacitacion_formadores,
                mayoria_titulares_emprendimientos,
                porcentaje_mujeres_directivas,
                programas_mujeres_emprendedoras,
                descripcion_programa_mujeres,
                principal_necesidad,
                nivel_interes_gobierno,
                mecanismos_coordinacion,
                estado_validacion,
                created_at,
                updated_at
            )
            VALUES (
                :staging_respuesta_id,
                :raw_respuesta_id,
                :id_respuesta_origen,
                :formulario_origen,
                :fecha_respuesta,
                :consentimiento,
                :version_encuesta,
                :genero,
                :nivel_conocimiento_municipio,
                :nivel_instruccion,
                :provincia_id,
                :municipio_id,
                :ambito_actuacion,
                :tipo_institucion,
                :nombre_institucion,
                :nivel_involucramiento,
                :nivel_capacitacion_formadores,
                :mayoria_titulares_emprendimientos,
                :porcentaje_mujeres_directivas,
                :programas_mujeres_emprendedoras,
                :descripcion_programa_mujeres,
                :principal_necesidad,
                :nivel_interes_gobierno,
                :mecanismos_coordinacion,
                :estado_validacion,
                NOW(),
                NOW()
            )
            ON CONFLICT (staging_respuesta_id)
            DO UPDATE SET
                raw_respuesta_id = EXCLUDED.raw_respuesta_id,
                id_respuesta_origen = EXCLUDED.id_respuesta_origen,
                formulario_origen = EXCLUDED.formulario_origen,
                fecha_respuesta = EXCLUDED.fecha_respuesta,
                consentimiento = EXCLUDED.consentimiento,
                version_encuesta = EXCLUDED.version_encuesta,
                genero = EXCLUDED.genero,
                nivel_conocimiento_municipio = EXCLUDED.nivel_conocimiento_municipio,
                nivel_instruccion = EXCLUDED.nivel_instruccion,
                provincia_id = EXCLUDED.provincia_id,
                municipio_id = EXCLUDED.municipio_id,
                ambito_actuacion = EXCLUDED.ambito_actuacion,
                tipo_institucion = EXCLUDED.tipo_institucion,
                nombre_institucion = EXCLUDED.nombre_institucion,
                nivel_involucramiento = EXCLUDED.nivel_involucramiento,
                nivel_capacitacion_formadores = EXCLUDED.nivel_capacitacion_formadores,
                mayoria_titulares_emprendimientos = EXCLUDED.mayoria_titulares_emprendimientos,
                porcentaje_mujeres_directivas = EXCLUDED.porcentaje_mujeres_directivas,
                programas_mujeres_emprendedoras = EXCLUDED.programas_mujeres_emprendedoras,
                descripcion_programa_mujeres = EXCLUDED.descripcion_programa_mujeres,
                principal_necesidad = EXCLUDED.principal_necesidad,
                nivel_interes_gobierno = EXCLUDED.nivel_interes_gobierno,
                mecanismos_coordinacion = EXCLUDED.mecanismos_coordinacion,
                estado_validacion = EXCLUDED.estado_validacion,
                updated_at = NOW()
            RETURNING id
        """),
        {
            "staging_respuesta_id": row["id"],
            "raw_respuesta_id": row["raw_respuesta_id"],
            "id_respuesta_origen": row["id_respuesta_origen"],
            "formulario_origen": row["formulario_origen"],
            "fecha_respuesta": row["fecha_respuesta"],
            "consentimiento": row["consentimiento"],
            "version_encuesta": row["version_encuesta"],
            "genero": row["genero"],
            "nivel_conocimiento_municipio": row["nivel_conocimiento_municipio"],
            "nivel_instruccion": row["nivel_instruccion"],
            "provincia_id": provincia_id,
            "municipio_id": municipio_id,
            "ambito_actuacion": row["ambito_actuacion"],
            "tipo_institucion": row["tipo_institucion"],
            "nombre_institucion": row["nombre_institucion"],
            "nivel_involucramiento": row["nivel_involucramiento"],
            "nivel_capacitacion_formadores": row["nivel_capacitacion_formadores"],
            "mayoria_titulares_emprendimientos": row["mayoria_titulares_emprendimientos"],
            "porcentaje_mujeres_directivas": row["porcentaje_mujeres_directivas"],
            "programas_mujeres_emprendedoras": row["programas_mujeres_emprendedoras"],
            "descripcion_programa_mujeres": row["descripcion_programa_mujeres"],
            "principal_necesidad": row["principal_necesidad"],
            "nivel_interes_gobierno": row["nivel_interes_gobierno"],
            "mecanismos_coordinacion": row["mecanismos_coordinacion"],
            "estado_validacion": row["estado_validacion"],
        },
    ).scalar_one()
    return operational_id


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        items = value
    else:
        items = [value]

    normalized: List[str] = []
    for item in items:
        text_value = str(item).strip()
        if not text_value:
            continue
        if " | " in text_value:
            normalized.extend([part.strip() for part in text_value.split(" | ") if part.strip()])
        elif ", " in text_value:
            normalized.extend([part.strip() for part in text_value.split(", ") if part.strip()])
        else:
            normalized.append(text_value)
    return normalized


def _extract_multiselects(raw_payload: Dict[str, Any]) -> Dict[str, List[str]]:
    extracted: Dict[str, List[str]] = {}
    for question, (table_name, column_name) in MULTISELECT_FIELDS.items():
        values = _coerce_list(raw_payload.get(question))
        if values or table_name not in extracted:
            extracted[table_name] = values
    return extracted


def _insert_child_values(db, operational_respuesta_id: int, table_name: str, column_name: str, values: List[str]) -> None:
    db.execute(
        text(f"""
            DELETE FROM operational.{table_name}
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )

    for value in values:
        db.execute(
            text(f"""
                INSERT INTO operational.{table_name} (
                    operational_respuesta_id,
                    {column_name}
                )
                VALUES (
                    :operational_respuesta_id,
                    :value
                )
                ON CONFLICT (operational_respuesta_id, {column_name})
                DO UPDATE SET
                    {column_name} = EXCLUDED.{column_name}
            """),
            {
                "operational_respuesta_id": operational_respuesta_id,
                "value": value,
            },
        )


def process_staging_to_operational(limit: int = 100) -> Dict[str, Any]:
    db = SessionLocal()
    pipeline_run_id: Optional[int] = None
    stats = {
        "total": 0,
        "cargada": 0,
        "saltada": 0,
        "errores_registrados": 0,
    }

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

        staging_rows = db.execute(
            text("""
                SELECT id,
                       raw_respuesta_id,
                       id_respuesta_origen,
                       formulario_origen,
                       fecha_respuesta,
                       raw_payload,
                       consentimiento,
                       version_encuesta,
                       genero,
                       nivel_conocimiento_municipio,
                       nivel_instruccion,
                       provincia,
                       municipio,
                       ambito_actuacion,
                       tipo_institucion,
                       nombre_institucion,
                       nivel_involucramiento,
                       nivel_capacitacion_formadores,
                       mayoria_titulares_emprendimientos,
                       porcentaje_mujeres_directivas,
                       programas_mujeres_emprendedoras,
                       descripcion_programa_mujeres,
                       principal_necesidad,
                       nivel_interes_gobierno,
                       mecanismos_coordinacion,
                       estado_validacion
                FROM staging.respuestas_formulario
                WHERE estado_validacion IN ('validada', 'con_observaciones')
                ORDER BY id
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

        for row in staging_rows:
            stats["total"] += 1
            provincia = row["provincia"]
            municipio = row["municipio"]

            if not provincia or not municipio:
                stats["saltada"] += 1
                stats["errores_registrados"] += 1
                db.execute(
                    text("""
                        INSERT INTO control.errores_carga (
                            respuesta_raw_id,
                            campo,
                            valor_recibido,
                            tipo_error,
                            descripcion,
                            estado_correccion
                        )
                        VALUES (
                            :respuesta_raw_id,
                            :campo,
                            :valor_recibido,
                            :tipo_error,
                            :descripcion,
                            'pendiente'
                        )
                    """),
                    {
                        "respuesta_raw_id": row["raw_respuesta_id"],
                        "campo": "ubicacion",
                        "valor_recibido": f"{provincia} / {municipio}",
                        "tipo_error": "operational_missing_reference",
                        "descripcion": "No se pudo resolver provincia o municipio",
                    },
                )
                continue

            provincia_id = _resolve_provincia(db, provincia)
            municipio_id = _resolve_municipio(db, provincia_id, municipio)
            operational_id = _upsert_operational_response(db, row, provincia_id, municipio_id)

            raw_payload = row["raw_payload"] or {}
            if isinstance(raw_payload, str):
                raw_payload = json.loads(raw_payload)

            multiselects = _extract_multiselects(raw_payload)
            for table_name, values in multiselects.items():
                if table_name == "respuestas_temas_formacion":
                    _insert_child_values(db, operational_id, table_name, "tema_formacion", values)
                elif table_name == "respuestas_instituciones_participantes":
                    _insert_child_values(db, operational_id, table_name, "institucion_participante", values)
                elif table_name == "respuestas_limitaciones":
                    _insert_child_values(db, operational_id, table_name, "limitacion", values)

            stats["cargada"] += 1
            db.execute(
                text("""
                    UPDATE raw.respuestas_formulario
                    SET estado = 'cargada_operational'
                    WHERE id = :raw_id
                """),
                {"raw_id": row["raw_respuesta_id"]},
            )

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
        return {
            "status": "ok",
            "pipeline_run_id": pipeline_run_id,
            "stats": stats,
        }

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
