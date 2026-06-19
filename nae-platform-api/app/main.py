from datetime import datetime
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.config import API_TOKEN
from app.database import SessionLocal
from app.reporting import get_dashboard_data, render_dashboard_html
from app.staging_pipeline import process_raw_to_staging
from app.operational_pipeline import process_staging_to_operational
from app.analytics_pipeline import process_operational_to_analytics


app = FastAPI(
    title="NAE Platform API",
    version="0.1.0"
)


class RespuestaFormulario(BaseModel):
    id_respuesta_origen: Optional[str] = None
    formulario_origen: Optional[str] = "Encuesta NAE"
    fecha_respuesta: Optional[datetime] = None
    version_encuesta: Optional[str] = None
    payload: Dict[str, Any]


@app.get("/api/v1/salud")
def salud():
    return {"status": "ok"}


@app.get("/api/v1/resumen")
def resumen(
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
):
    return get_dashboard_data(
        limit=limit,
        provincia=provincia,
        version_encuesta=version_encuesta,
        genero=genero,
        tema=tema,
    )


@app.get("/", response_class=HTMLResponse)
def panel_principal(
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
):
    data = get_dashboard_data(
        limit=limit,
        provincia=provincia,
        version_encuesta=version_encuesta,
        genero=genero,
        tema=tema,
    )
    data["filters"]["limit"] = limit
    return render_dashboard_html(data)


@app.post("/api/v1/respuestas")
def recibir_respuesta(
    data: RespuestaFormulario,
    authorization: Optional[str] = Header(None)
):
    expected = f"Bearer {API_TOKEN}"

    if authorization != expected:
        raise HTTPException(status_code=401, detail="Token inválido")

    db = SessionLocal()

    try:
        if data.id_respuesta_origen:
            duplicate = db.execute(
                text("""
                    SELECT 1
                    FROM raw.respuestas_formulario
                    WHERE id_respuesta_origen = :id_respuesta_origen
                    LIMIT 1
                """),
                {"id_respuesta_origen": data.id_respuesta_origen},
            ).scalar_one_or_none()

            if duplicate is not None:
                raise HTTPException(status_code=409, detail="Respuesta ya registrada")

        result = db.execute(
            text("""
                INSERT INTO raw.respuestas_formulario (
                    id_respuesta_origen,
                    formulario_origen,
                    fecha_respuesta,
                    version_encuesta,
                    payload,
                    estado
                )
                VALUES (
                    :id_respuesta_origen,
                    :formulario_origen,
                    :fecha_respuesta,
                    :version_encuesta,
                    CAST(:payload AS JSONB),
                    'recibida'
                )
                RETURNING id
            """),
            {
                "id_respuesta_origen": data.id_respuesta_origen,
                "formulario_origen": data.formulario_origen,
                "fecha_respuesta": data.fecha_respuesta or datetime.now(),
                "version_encuesta": data.version_encuesta,
                "payload": json.dumps(data.payload, ensure_ascii=False)
            }
        )

        raw_id = result.scalar()
        db.commit()

        return {
            "status": "ok",
            "raw_id": raw_id
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicto al guardar la respuesta")
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        db.close()


@app.post("/api/v1/pipelines/staging/raw-to-staging")
def ejecutar_raw_a_staging(limit: int = 100, authorization: Optional[str] = Header(None)):
    expected = f"Bearer {API_TOKEN}"

    if authorization != expected:
        raise HTTPException(status_code=401, detail="Token inválido")

    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")

    return process_raw_to_staging(limit=limit)


@app.post("/api/v1/pipelines/operational/staging-to-operational")
def ejecutar_staging_a_operational(limit: int = 100, authorization: Optional[str] = Header(None)):
    expected = f"Bearer {API_TOKEN}"

    if authorization != expected:
        raise HTTPException(status_code=401, detail="Token inválido")

    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")

    return process_staging_to_operational(limit=limit)


@app.post("/api/v1/pipelines/analytics/operational-to-analytics")
def ejecutar_operational_a_analytics(limit: int = 100, authorization: Optional[str] = Header(None)):
    expected = f"Bearer {API_TOKEN}"

    if authorization != expected:
        raise HTTPException(status_code=401, detail="Token inválido")

    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")

    return process_operational_to_analytics(limit=limit)
