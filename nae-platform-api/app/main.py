from datetime import datetime
import base64
import hashlib
import hmac
from html import escape
import logging
import json
from pathlib import Path
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.config import ANALYTICS_PASSWORD, ANALYTICS_USERNAME, API_TOKEN, SESSION_SECRET
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
AUTH_COOKIE_NAME = "nae_analytics_session"
AUTH_COOKIE_MAX_AGE = 8 * 60 * 60


class RespuestaFormulario(BaseModel):
    id_respuesta_origen: Optional[str] = None
    formulario_origen: Optional[str] = "Encuesta NAE"
    fecha_respuesta: Optional[datetime] = None
    version_encuesta: Optional[str] = None
    payload: Dict[str, Any]


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _session_signature(payload: str) -> str:
    digest = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def _create_session_cookie(username: str) -> str:
    issued_at = str(int(time.time()))
    payload = _b64encode(f"{username}:{issued_at}".encode("utf-8"))
    return f"{payload}.{_session_signature(payload)}"


def _is_valid_session_cookie(cookie_value: Optional[str]) -> bool:
    if not cookie_value or "." not in cookie_value:
        return False

    payload, signature = cookie_value.rsplit(".", 1)
    if not hmac.compare_digest(signature, _session_signature(payload)):
        return False

    try:
        raw_payload = _b64decode(payload).decode("utf-8")
        username, issued_at = raw_payload.rsplit(":", 1)
        age = int(time.time()) - int(issued_at)
    except Exception:
        return False

    return username == ANALYTICS_USERNAME and 0 <= age <= AUTH_COOKIE_MAX_AGE


def _has_analytics_access(request: Request, authorization: Optional[str] = None) -> bool:
    if authorization == f"Bearer {API_TOKEN}":
        return True
    return _is_valid_session_cookie(request.cookies.get(AUTH_COOKIE_NAME))


def _require_analytics_access(request: Request, authorization: Optional[str] = None) -> None:
    if not _has_analytics_access(request, authorization):
        raise HTTPException(status_code=401, detail="Autenticación requerida")


def _redirect_to_login(request: Request) -> RedirectResponse:
    next_url = str(request.url.path)
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    return RedirectResponse(url=f"/login?{urlencode({'next': next_url})}", status_code=303)


def _render_login_html(error: Optional[str] = None, next_url: str = "/analitica") -> HTMLResponse:
    error_html = f'<div class="error">{error}</div>' if error else ""
    safe_next_url = escape(next_url, quote=True)
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Acceso | NAE Platform</title>
  <style>
    :root {{ color-scheme: light; --blue:#0b4f8a; --ink:#162033; --muted:#667085; --line:#d9e2ec; --bg:#f4f7fb; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100vh; font-family: Arial, Helvetica, sans-serif; background:var(--bg); color:var(--ink); display:flex; flex-direction:column; }}
    header, footer {{ background:#fff; }}
    header {{ border-bottom:1px solid var(--line); }}
    footer {{ border-top:1px solid var(--line); margin-top:auto; }}
    .image-strip {{ width:100%; display:block; object-fit:contain; }}
    .header-strip {{ min-height:128px; padding:14px 0 10px; background:#003247; }}
    .footer-strip {{ min-height:82px; padding:18px 0 20px; background:#fff; }}
    main {{ width:100%; max-width:420px; margin:46px auto; padding:0 20px; }}
    .panel {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:28px; box-shadow:0 16px 40px rgba(22,32,51,.08); }}
    h1 {{ margin:0 0 8px; font-size:24px; line-height:1.2; color:var(--blue); }}
    p {{ margin:0 0 22px; color:var(--muted); line-height:1.5; }}
    label {{ display:block; font-size:13px; font-weight:700; margin:16px 0 6px; }}
    input {{ width:100%; border:1px solid var(--line); border-radius:6px; padding:12px; font-size:15px; }}
    button {{ width:100%; margin-top:22px; border:0; border-radius:6px; padding:12px 14px; background:var(--blue); color:#fff; font-weight:700; cursor:pointer; }}
    .error {{ border:1px solid #f2b8b5; background:#fff0f0; color:#b42318; border-radius:6px; padding:10px 12px; margin-bottom:14px; font-size:14px; }}
    .back {{ display:inline-block; margin-top:16px; color:var(--blue); text-decoration:none; font-size:14px; }}
  </style>
</head>
<body>
  <header><img class="image-strip header-strip" src="/images/header.png" alt="NAE" /></header>
  <main>
    <section class="panel">
      <h1>Acceso a analítica</h1>
      <p>Ingrese sus credenciales para consultar el panel operativo.</p>
      {error_html}
      <form method="post" action="/login">
        <input type="hidden" name="next" value="{safe_next_url}" />
        <label for="username">Usuario</label>
        <input id="username" name="username" autocomplete="username" required />
        <label for="password">Contraseña</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button type="submit">Entrar</button>
      </form>
      <a class="back" href="/">Volver al inicio</a>
    </section>
  </main>
  <footer><img class="image-strip footer-strip" src="/images/footer.png" alt="" /></footer>
</body>
</html>"""
    return HTMLResponse(html)


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
        'Prototipo visual no funcional para revisión de diseño. Proyecto NAE.': '',
        'formulario pendiente de confirmación final': 'formulario aprobado',
        'href="#"': 'href="https://forms.gle/faFwt1dSGdngtXvU7" target="_blank" rel="noopener"' if filename == "encuesta.html" else 'href="#"',
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    return HTMLResponse(html)


@app.get("/api/v1/salud")
def salud():
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
def login_page(next: str = "/analitica"):
    return _render_login_html(next_url=next)


@app.post("/login")
async def login_submit(request: Request):
    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    username = form.get("username", [""])[0]
    password = form.get("password", [""])[0]
    next_url = form.get("next", ["/analitica"])[0] or "/analitica"

    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/analitica"

    valid_user = hmac.compare_digest(username, ANALYTICS_USERNAME)
    valid_password = hmac.compare_digest(password, ANALYTICS_PASSWORD)
    if not valid_user or not valid_password:
        return _render_login_html(error="Usuario o contraseña incorrectos.", next_url=next_url)

    response = RedirectResponse(url=next_url, status_code=303)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        _create_session_cookie(username),
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@app.get("/api/v1/resumen")
def resumen(
    request: Request,
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    _require_analytics_access(request, authorization)
    return get_dashboard_data(
        limit=limit,
        provincia=provincia,
        version_encuesta=version_encuesta,
        genero=genero,
        tema=tema,
    )


@app.get("/api/v1/resumen.csv")
def resumen_csv(
    request: Request,
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    _require_analytics_access(request, authorization)
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
def detalle_respuesta_api(
    request: Request,
    respuesta_id: int,
    authorization: Optional[str] = Header(None),
):
    _require_analytics_access(request, authorization)
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
    request: Request,
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
    tipo: Optional[str] = None,
    servicio: Optional[str] = None,
):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)

    data = get_dashboard_data(
        limit=limit,
        provincia=provincia,
        version_encuesta=version_encuesta,
        genero=genero,
        tema=tema,
        tipo=tipo,
        servicio=servicio,
    )
    data["filters"]["limit"] = limit
    return render_dashboard_html(data)


@app.get("/dashboard", response_class=HTMLResponse)
def panel_dashboard(
    request: Request,
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
    tipo: Optional[str] = None,
    servicio: Optional[str] = None,
):
    return panel_analitico(
        request=request,
        limit=limit,
        provincia=provincia,
        version_encuesta=version_encuesta,
        genero=genero,
        tema=tema,
        tipo=tipo,
        servicio=servicio,
    )

@app.get("/respuestas/{respuesta_id}", response_class=HTMLResponse)
def detalle_respuesta_html(request: Request, respuesta_id: int):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)

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
