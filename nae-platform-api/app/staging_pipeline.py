from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import text

from app.database import SessionLocal


ALLOWED_PROVINCES = {
    "Pinar del Río",
    "Artemisa",
    "La Habana",
    "Mayabeque",
    "Matanzas",
    "Cienfuegos",
    "Villa Clara",
    "Sancti Spíritus",
    "Ciego de Ávila",
    "Camagüey",
    "Las Tunas",
    "Holguín",
    "Granma",
    "Santiago de Cuba",
    "Guantánamo",
    "Isla de la Juventud",
}


PIPELINE_NAME = "raw_to_staging"

CONSENT_QUESTION = (
    "¿Acepta participar voluntariamente en esta encuesta y autoriza el uso de la "
    "información con fines de diagnóstico y planificación del proyecto?"
)
FIELD_MAP = {
    CONSENT_QUESTION: "consentimiento",
    "1.1 Provincia": "provincia",
    "1.2 Municipio": "municipio",
    "1.3 Ámbito principal de actuación de la entidad": "ambito_actuacion",
    "1.4 Tipo de institución que representa": "tipo_institucion",
    "1.5 Nombre oficial de la institución": "nombre_institucion",
    "1.6 Nivel de involucramiento en actividades de formación sobre NAE": "nivel_involucramiento",
    "3.1 Nivel de capacitación de formadores locales": "nivel_capacitacion_formadores",
    "3.3 Principal necesidad del municipio": "principal_necesidad",
    "4.1 Nivel de interés de los actores de gobierno en formación sobre NAE": "nivel_interes_gobierno",
    "5.1 Existencia de mecanismos de coordinación institucional": "mecanismos_coordinacion",
}

REQUIRED_FIELDS = {
    "consentimiento",
    "provincia",
    "municipio",
    "ambito_actuacion",
    "tipo_institucion",
    "nombre_institucion",
    "nivel_involucramiento",
    "nivel_capacitacion_formadores",
    "principal_necesidad",
    "nivel_interes_gobierno",
    "mecanismos_coordinacion",
}


@dataclass
class ValidationResult:
    state: str
    observaciones: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    normalized: Dict[str, Any] = field(default_factory=dict)


def _scalar_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        if not items:
            return None
        return " | ".join(items)
    text_value = str(value).strip()
    return text_value or None


def _payload_as_dict(raw_payload: Any) -> Dict[str, Any]:
    if raw_payload is None:
        return {}
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str):
        return json.loads(raw_payload)
    raise HTTPException(status_code=500, detail="Formato de payload no soportado")


def _extract_normalized_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for question, field_name in FIELD_MAP.items():
        normalized[field_name] = _scalar_value(payload.get(question))
    return normalized


def validate_payload(payload: Dict[str, Any]) -> ValidationResult:
    normalized = _extract_normalized_fields(payload)
    errors: List[Dict[str, str]] = []
    observaciones: List[str] = []

    for field_name in REQUIRED_FIELDS:
        if not normalized.get(field_name):
            errors.append(
                {
                    "campo": field_name,
                    "tipo_error": "obligatorio",
                    "descripcion": f"Falta el campo obligatorio {field_name}",
                }
            )

    provincia = normalized.get("provincia")
    if provincia and provincia not in ALLOWED_PROVINCES:
        errors.append(
            {
                "campo": "provincia",
                "tipo_error": "catalogo",
                "descripcion": f"Provincia no reconocida: {provincia}",
            }
        )

    if normalized.get("consentimiento") not in {"Sí, acepto", "Sí"}:
        errors.append(
            {
                "campo": "consentimiento",
                "tipo_error": "consentimiento",
                "descripcion": "La persona no aceptó participar o la respuesta es inválida",
            }
        )

    if not errors:
        state = "validada"
    else:
        critical_fields = {"consentimiento", "provincia", "municipio", "tipo_institucion", "nombre_institucion"}
        critical_error = any(error["campo"] in critical_fields for error in errors)
        state = "rechazada" if critical_error else "con_observaciones"
        if state == "con_observaciones":
            observaciones.append("Respuesta válida con observaciones menores")

    return ValidationResult(
        state=state,
        observaciones=observaciones,
        errors=errors,
        normalized=normalized,
    )


def process_raw_to_staging(limit: int = 100) -> Dict[str, Any]:
    db = SessionLocal()
    pipeline_run_id: Optional[int] = None
    stats = {
        "total": 0,
        "validada": 0,
        "con_observaciones": 0,
        "rechazada": 0,
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

        raw_rows = db.execute(
            text("""
                SELECT id,
                       id_respuesta_origen,
                       formulario_origen,
                       fecha_respuesta,
                       payload
                FROM raw.respuestas_formulario
                WHERE estado = 'recibida'
                ORDER BY id
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

        for raw_row in raw_rows:
            stats["total"] += 1
            payload = _payload_as_dict(raw_row["payload"])
            result = validate_payload(payload)

            if result.errors:
                stats["errores_registrados"] += len(result.errors)
                for error in result.errors:
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
                            "respuesta_raw_id": raw_row["id"],
                            "campo": error["campo"],
                            "valor_recibido": json.dumps(payload.get(error["campo"]), ensure_ascii=False),
                            "tipo_error": error["tipo_error"],
                            "descripcion": error["descripcion"],
                        },
                    )

            db.execute(
                text("""
                    INSERT INTO staging.respuestas_formulario (
                        raw_respuesta_id,
                        id_respuesta_origen,
                        formulario_origen,
                        fecha_respuesta,
                        consentimiento,
                        provincia,
                        municipio,
                        ambito_actuacion,
                        tipo_institucion,
                        nombre_institucion,
                        nivel_involucramiento,
                        nivel_capacitacion_formadores,
                        principal_necesidad,
                        nivel_interes_gobierno,
                        mecanismos_coordinacion,
                        estado_validacion,
                        observaciones,
                        raw_payload,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :raw_respuesta_id,
                        :id_respuesta_origen,
                        :formulario_origen,
                        :fecha_respuesta,
                        :consentimiento,
                        :provincia,
                        :municipio,
                        :ambito_actuacion,
                        :tipo_institucion,
                        :nombre_institucion,
                        :nivel_involucramiento,
                        :nivel_capacitacion_formadores,
                        :principal_necesidad,
                        :nivel_interes_gobierno,
                        :mecanismos_coordinacion,
                        :estado_validacion,
                        :observaciones,
                        CAST(:raw_payload AS JSONB),
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (raw_respuesta_id)
                    DO UPDATE SET
                        id_respuesta_origen = EXCLUDED.id_respuesta_origen,
                        formulario_origen = EXCLUDED.formulario_origen,
                        fecha_respuesta = EXCLUDED.fecha_respuesta,
                        consentimiento = EXCLUDED.consentimiento,
                        provincia = EXCLUDED.provincia,
                        municipio = EXCLUDED.municipio,
                        ambito_actuacion = EXCLUDED.ambito_actuacion,
                        tipo_institucion = EXCLUDED.tipo_institucion,
                        nombre_institucion = EXCLUDED.nombre_institucion,
                        nivel_involucramiento = EXCLUDED.nivel_involucramiento,
                        nivel_capacitacion_formadores = EXCLUDED.nivel_capacitacion_formadores,
                        principal_necesidad = EXCLUDED.principal_necesidad,
                        nivel_interes_gobierno = EXCLUDED.nivel_interes_gobierno,
                        mecanismos_coordinacion = EXCLUDED.mecanismos_coordinacion,
                        estado_validacion = EXCLUDED.estado_validacion,
                        observaciones = EXCLUDED.observaciones,
                        raw_payload = EXCLUDED.raw_payload,
                        updated_at = NOW()
                """),
                {
                    "raw_respuesta_id": raw_row["id"],
                    "id_respuesta_origen": raw_row["id_respuesta_origen"],
                    "formulario_origen": raw_row["formulario_origen"],
                    "fecha_respuesta": raw_row["fecha_respuesta"],
                    "consentimiento": result.normalized.get("consentimiento"),
                    "provincia": result.normalized.get("provincia"),
                    "municipio": result.normalized.get("municipio"),
                    "ambito_actuacion": result.normalized.get("ambito_actuacion"),
                    "tipo_institucion": result.normalized.get("tipo_institucion"),
                    "nombre_institucion": result.normalized.get("nombre_institucion"),
                    "nivel_involucramiento": result.normalized.get("nivel_involucramiento"),
                    "nivel_capacitacion_formadores": result.normalized.get("nivel_capacitacion_formadores"),
                    "principal_necesidad": result.normalized.get("principal_necesidad"),
                    "nivel_interes_gobierno": result.normalized.get("nivel_interes_gobierno"),
                    "mecanismos_coordinacion": result.normalized.get("mecanismos_coordinacion"),
                    "estado_validacion": result.state,
                    "observaciones": " | ".join(result.observaciones) if result.observaciones else None,
                    "raw_payload": json.dumps(payload, ensure_ascii=False),
                },
            )

            db.execute(
                text("""
                    UPDATE raw.respuestas_formulario
                    SET estado = :estado
                    WHERE id = :raw_id
                """),
                {
                    "estado": result.state,
                    "raw_id": raw_row["id"],
                },
            )

            stats[result.state] += 1

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
