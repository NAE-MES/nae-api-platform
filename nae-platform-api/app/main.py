from datetime import datetime
import logging
import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.config import API_TOKEN
from app.database import SessionLocal
from app.reporting import (
    build_support_entities_csv,
    build_resumen_csv,
    get_dashboard_data,
    get_response_detail,
    get_support_entities,
    render_dashboard_html,
    render_response_detail_html,
    render_support_entities_html,
)
from app.staging_pipeline import process_raw_to_staging
from app.operational_pipeline import process_staging_to_operational
from app.analytics_pipeline import process_operational_to_analytics


app = FastAPI(
    title="NAE Platform API",
    version="0.1.0"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
app.mount("/images", StaticFiles(directory=str(PROJECT_ROOT / "images")), name="images")
app.mount("/prototype-assets", StaticFiles(directory=str(PROJECT_ROOT / "prototype")), name="prototype-assets")

logger = logging.getLogger(__name__)


class RespuestaFormulario(BaseModel):
    id_respuesta_origen: Optional[str] = None
    formulario_origen: Optional[str] = "Encuesta NAE"
    fecha_respuesta: Optional[datetime] = None
    version_encuesta: Optional[str] = None
    payload: Dict[str, Any]


def _run_pipeline_chain(limit: int = 100) -> None:
    logger.info("Iniciando cadena automatica de pipelines para %s registros", limit)
    staging_result = process_raw_to_staging(limit=limit)
    operational_result = process_staging_to_operational(limit=limit, only_pending=True)
    analytics_result = process_operational_to_analytics(limit=limit, only_pending=True)
    logger.info("Cadena automatica de pipelines completada")
    return {
        "staging": staging_result.get("stats", {}),
        "operational": operational_result.get("stats", {}),
        "analytics": analytics_result.get("stats", {}),
    }



def _render_prototype_page(filename: str, active_path: str) -> HTMLResponse:
    html = (PROJECT_ROOT / "prototype" / filename).read_text(encoding="utf-8")
    replacements = {
        'href="styles.css"': 'href="/prototype-assets/styles.css"',
        'src="../images/header.png"': 'src="/images/header.png"',
        'src="../images/footer.png"': 'src="/images/footer.png"',
        'href="index.html"': 'href="/"',
        'href="encuesta.html"': 'href="/encuesta"',
        'href="mapa-entidades.html"': 'href="/mapa-apoyo"',
        'href="documentacion.html"': 'href="/documentacion"',
        'href="login.html"': 'href="/analitica"',
        'href="analitica.html"': 'href="/analitica"',
        'Prototipo institucional': 'Plataforma institucional',
        'Prototipo visual no funcional para revisión de diseño. Proyecto NAE.': 'Proyecto NAE. Mapeo de estructuras de apoyo a los nuevos actores económicos.',
        'formulario pendiente de confirmación final': 'formulario aprobado',
        'href="#"': 'href="/mapa-apoyo"' if filename == "encuesta.html" else 'href="#"',
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    return HTMLResponse(html)
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


@app.get("/api/v1/resumen.csv")
def resumen_csv(
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
    csv_content = build_resumen_csv(data)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nae_resumen.csv"'},
    )


@app.get("/api/v1/entidades-apoyo")
def entidades_apoyo(
    limit: int = 200,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")
    return get_support_entities(limit=limit, provincia=provincia, municipio=municipio, tipo=tipo, q=q)


@app.get("/api/v1/entidades-apoyo.csv")
def entidades_apoyo_csv(
    limit: int = 200,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")
    data = get_support_entities(limit=limit, provincia=provincia, municipio=municipio, tipo=tipo, q=q)
    csv_content = build_support_entities_csv(data)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="nae_entidades_apoyo.csv"'},
    )



@app.get("/mapa-apoyo", response_class=HTMLResponse)
def mapa_apoyo(
    limit: int = 200,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")
    data = get_support_entities(limit=limit, provincia=provincia, municipio=municipio, tipo=tipo, q=q)
    return render_support_entities_html(data)

@app.get("/api/v1/respuestas/{respuesta_id}")
def detalle_respuesta_api(respuesta_id: int):
    data = get_response_detail(respuesta_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")
    return data


@app.get("/", response_class=HTMLResponse)
def inicio_publico():
    return _render_prototype_page("index.html", "/")


@app.get("/encuesta", response_class=HTMLResponse)
def encuesta_publica():
    return _render_prototype_page("encuesta.html", "/encuesta")


@app.get("/documentacion", response_class=HTMLResponse)
def documentacion_publica():
    return _render_prototype_page("documentacion.html", "/documentacion")


@app.get("/analitica", response_class=HTMLResponse)
def panel_analitico(
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


@app.get("/dashboard", response_class=HTMLResponse)
def panel_dashboard(
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
):
    return panel_analitico(
        limit=limit,
        provincia=provincia,
        version_encuesta=version_encuesta,
        genero=genero,
        tema=tema,
    )

@app.get("/respuestas/{respuesta_id}", response_class=HTMLResponse)
def detalle_respuesta_html(respuesta_id: int):
    data = get_response_detail(respuesta_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")
    return render_response_detail_html(data)


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
        pipeline_result = _run_pipeline_chain()

        return {
            "status": "ok",
            "raw_id": raw_id,
            "pipeline": pipeline_result,
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
