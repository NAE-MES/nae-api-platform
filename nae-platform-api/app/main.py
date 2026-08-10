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

from app.config import (
    ANALYTICS_PASSWORD,
    ANALYTICS_REVIEW_USERS,
    ANALYTICS_USERNAME,
    ANALYTICS_USERS,
    API_TOKEN,
    SESSION_COOKIE_SECURE,
    SESSION_MAX_AGE_SECONDS,
    SESSION_SECRET,
)
from app.cuba_geo import CUBA_GEO
from app.database import SessionLocal
from app.entity_resolution import normalize_entity_name
from app.reporting import (
    build_support_entities_csv,
    build_support_entities_pdf,
    build_resumen_csv,
    get_admin_review_data,
    get_dashboard_data,
    get_response_detail,
    get_support_entities,
    render_admin_review_html,
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
AUTH_COOKIE_MAX_AGE = SESSION_MAX_AGE_SECONDS


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


def _parse_user_password_entries(raw_value: str) -> Dict[str, str]:
    users: Dict[str, str] = {}
    for item in raw_value.split(";"):
        if not item.strip():
            continue
        if ":" not in item:
            continue
        username, password = item.split(":", 1)
        username = username.strip()
        password = password.strip()
        if username and password:
            users[username] = password
    return users


def _configured_analytics_users() -> Dict[str, str]:
    users = {ANALYTICS_USERNAME: ANALYTICS_PASSWORD}
    users.update(_parse_user_password_entries(ANALYTICS_USERS))
    users.update(_parse_user_password_entries(ANALYTICS_REVIEW_USERS))
    return users


def _valid_analytics_credentials(username: str, password: str) -> bool:
    configured_password = _configured_analytics_users().get(username)
    if configured_password is None:
        return False
    return hmac.compare_digest(password, configured_password)


def _session_username_from_cookie(cookie_value: Optional[str]) -> Optional[str]:
    if not cookie_value or "." not in cookie_value:
        return None

    payload, signature = cookie_value.rsplit(".", 1)
    if not hmac.compare_digest(signature, _session_signature(payload)):
        return None

    try:
        raw_payload = _b64decode(payload).decode("utf-8")
        username, issued_at = raw_payload.rsplit(":", 1)
        age = int(time.time()) - int(issued_at)
    except Exception:
        return None

    if username not in _configured_analytics_users():
        return None
    if not 0 <= age <= AUTH_COOKIE_MAX_AGE:
        return None
    return username



def _configured_review_users() -> set[str]:
    users = {ANALYTICS_USERNAME}
    for item in ANALYTICS_REVIEW_USERS.split(";"):
        item = item.strip()
        if not item:
            continue
        username = item.split(":", 1)[0].strip()
        if username:
            users.add(username)
    return users


def _user_can_review(username: Optional[str]) -> bool:
    return bool(username and username in _configured_review_users())


def _has_review_access(request: Request) -> bool:
    return _user_can_review(_session_username(request))
def _is_valid_session_cookie(cookie_value: Optional[str]) -> bool:
    return _session_username_from_cookie(cookie_value) is not None


def _session_username(request: Request) -> Optional[str]:
    return _session_username_from_cookie(request.cookies.get(AUTH_COOKIE_NAME))


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
  <link rel="stylesheet" href="/prototype-assets/styles.css" />
  <style>
    .login-wrap {{ min-height: 46vh; display: grid; place-items: center; padding-top: 34px; padding-bottom: 42px; }}
    .login-panel {{ width: min(460px, 100%); }}
    .login-panel form {{ display: block; width: 100%; }}
    .login-panel h1 {{ font-size: 25px; margin-bottom: 10px; }}
    .login-panel p {{ color: #4b5b6b; }}
    .login-panel label {{ display: block; width: 100%; margin: 14px 0 6px; color: #657383; font-size: 12px; font-weight: 800; text-transform: uppercase; }}
    .login-panel input {{ display: block; width: 100%; min-height: 42px; border: 1px solid #d9e1e8; border-radius: 6px; padding: 0 10px; font: inherit; }}
    .login-panel button {{ width: 100%; margin-top: 18px; }}
    .error {{ border:1px solid #f2b8b5; background:#fff0f0; color:#b42318; border-radius:6px; padding:10px 12px; margin-bottom:14px; font-size:14px; }}
    .login-actions {{ margin-top: 16px; }}
  </style>
</head>
<body>
  <nav class="site-nav">
    <div class="nav-inner">
      <a class="nav-title" href="/"><strong>NAE</strong><span>Mapeo de Entidades de Apoyo</span></a>
      <div class="nav-links">
        <a href="/">Inicio</a>
        <a href="/encuesta">Encuesta</a>
        <a href="/mapa-apoyo">Mapa</a>
        <a href="/documentacion">Documentación</a>
        <a class="active locked" href="/analitica">Analítica</a>
      </div>
    </div>
  </nav>
  <img class="brand-strip" style="height:auto;max-height:none;object-fit:contain;" src="/images/banner-mapeo.jpeg" alt="NAE - Proyecto de cooperación internacional" />
  <main class="page login-wrap">
    <section class="login-panel card pad">
      <p class="eyebrow">Área privada</p>
      <h1>Acceso a analítica</h1>
      <p>Ingrese sus credenciales para consultar el panel operativo.</p>
      {error_html}
      <form method="post" action="/login">
        <input type="hidden" name="next" value="{safe_next_url}" />
        <label for="username">Usuario</label>
        <input id="username" name="username" autocomplete="username" required />
        <label for="password">Contraseña</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required />
        <button class="button primary" type="submit">Entrar</button>
      </form>
      <div class="login-actions"><a class="button secondary" href="/">Volver al inicio</a></div>
    </section>
  </main>
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



def _private_nav_links(is_authenticated: bool, can_review: bool = False) -> str:
    if not is_authenticated:
        return ""
    links = ""
    if can_review:
        links += '\n          <a class="locked" href="/admin/administracion">Administración</a>'
    links += '\n          <a class="locked" href="/logout">Cerrar sesión</a>'
    return links


def _render_prototype_page(filename: str, active_path: str, request: Optional[Request] = None) -> HTMLResponse:
    html = (PROJECT_ROOT / "prototype" / filename).read_text(encoding="utf-8")
    replacements = {
        'href="styles.css"': 'href="/prototype-assets/styles.css"',
        'src="../images/header.png"': 'src="/images/banner-mapeo.jpeg"',
        'src="../images/banner-mapeo.jpeg"': 'src="/images/banner-mapeo.jpeg"',
        'href="index.html"': 'href="/"',
        'href="encuesta.html"': 'href="/encuesta"',
        'href="mapa-entidades.html"': 'href="/mapa-apoyo"',
        'href="documentacion.html"': 'href="/documentacion"',
        'href="login.html"': 'href="/analitica"',
        'href="analitica.html"': 'href="/analitica"',
        '<strong>NAE Platform</strong>': '<strong>NAE</strong>',
        'Prototipo institucional': 'Mapeo de Entidades de Apoyo',
        'Prototipo visual no funcional para revisión de diseño. Proyecto NAE.': '',
        'formulario pendiente de confirmación final': 'formulario aprobado',
        'href="#"': 'href="https://forms.gle/faFwt1dSGdngtXvU7" target="_blank" rel="noopener"' if filename == "encuesta.html" else 'href="#"',
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    if request is not None and _has_analytics_access(request):
        analytics_link = '<a class="locked" href="/analitica">Analítica</a>'
        active_analytics_link = '<a class="active locked" href="/analitica">Analítica</a>'
        private_links = _private_nav_links(True, _has_review_access(request))
        if active_analytics_link in html and "/admin/administracion" not in html:
            html = html.replace(active_analytics_link, f"{active_analytics_link}{private_links}")
        elif analytics_link in html and "/admin/administracion" not in html:
            html = html.replace(analytics_link, f"{analytics_link}{private_links}")
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

    if not _valid_analytics_credentials(username, password):
        return _render_login_html(error="Usuario o contraseña incorrectos.", next_url=next_url)

    response = RedirectResponse(url=next_url, status_code=303)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        _create_session_cookie(username),
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
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


@app.get("/api/v1/entidades-apoyo.pdf")
def entidades_apoyo_pdf(
    limit: int = 200,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")
    data = get_support_entities(limit=limit, provincia=provincia, municipio=municipio, tipo=tipo, q=q)
    pdf_content = build_support_entities_pdf(data)
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="directorio_entidades_apoyo_nae.pdf"'},
    )



@app.get("/mapa-apoyo", response_class=HTMLResponse)
def mapa_apoyo(
    request: Request,
    limit: int = 200,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="El límite debe estar entre 1 y 1000")
    data = get_support_entities(limit=limit, provincia=provincia, municipio=municipio, tipo=tipo, q=q)
    return render_support_entities_html(data, authenticated=_has_analytics_access(request), can_review=_has_review_access(request))

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
def inicio_publico(request: Request):
    return _render_prototype_page("index.html", "/", request)


@app.get("/encuesta", response_class=HTMLResponse)
def encuesta_publica(request: Request):
    return _render_prototype_page("encuesta.html", "/encuesta", request)


@app.get("/documentacion", response_class=HTMLResponse)
def documentacion_publica(request: Request):
    return _render_prototype_page("documentacion.html", "/documentacion", request)


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
    return render_dashboard_html(data, can_review=_has_review_access(request))


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


@app.get("/admin/administracion", response_class=HTMLResponse)
def admin_administracion(request: Request):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)
    if not _has_review_access(request):
        raise HTTPException(status_code=403, detail="No tiene permisos para administrar datos")
    return render_admin_review_html(get_admin_review_data())


@app.get("/admin/revision")
def admin_revision_redirect():
    return RedirectResponse(url="/admin/administracion", status_code=303)


@app.post("/admin/revision/territorios/{territorio_id}")
@app.post("/admin/administracion/territorios/{territorio_id}")
async def admin_revision_territorio(request: Request, territorio_id: int):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)
    if not _has_review_access(request):
        raise HTTPException(status_code=403, detail="No tiene permisos para administrar datos")
    review_user = _session_username(request) or ANALYTICS_USERNAME

    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    action = form.get("action", [""])[0]
    municipio_key = form.get("municipio_key", [""])[0]
    municipio_id_raw = form.get("municipio_id", [""])[0]
    observacion = form.get("observacion", [""])[0] or None

    db = SessionLocal()
    try:
        current = db.execute(
            text("""
                SELECT id, texto_original, provincia_resuelta, municipio_resuelto
                FROM operational.respuestas_mapeo_territorios_servicio
                WHERE id = :id
            """),
            {"id": territorio_id},
        ).mappings().one_or_none()
        if current is None:
            raise HTTPException(status_code=404, detail="Territorio pendiente no encontrado")

        if action == "resolve":
            if not municipio_key and not municipio_id_raw:
                raise HTTPException(status_code=400, detail="Debe seleccionar un municipio")

            if municipio_key:
                if "||" not in municipio_key:
                    raise HTTPException(status_code=400, detail="Municipio no válido")
                provincia_nombre, municipio_nombre = municipio_key.split("||", 1)
                valid_municipality = any(
                    provincia_nombre == province_name and municipio_nombre == item["nombre"]
                    for province_name, items in CUBA_GEO.items()
                    for item in items
                )
                if not valid_municipality:
                    raise HTTPException(status_code=400, detail="Municipio no válido")
                provincia_id = db.execute(
                    text("""
                        INSERT INTO operational.provincias (nombre)
                        VALUES (:nombre)
                        ON CONFLICT (nombre)
                        DO UPDATE SET nombre = EXCLUDED.nombre
                        RETURNING id
                    """),
                    {"nombre": provincia_nombre},
                ).scalar_one()
                municipio_id = db.execute(
                    text("""
                        INSERT INTO operational.municipios (provincia_id, nombre)
                        VALUES (:provincia_id, :nombre)
                        ON CONFLICT (provincia_id, nombre)
                        DO UPDATE SET nombre = EXCLUDED.nombre
                        RETURNING id
                    """),
                    {"provincia_id": provincia_id, "nombre": municipio_nombre},
                ).scalar_one()
                municipio = {
                    "id": municipio_id,
                    "provincia": provincia_nombre,
                    "municipio": municipio_nombre,
                }
            else:
                municipio = db.execute(
                    text("""
                        SELECT mu.id, mu.nombre AS municipio, p.nombre AS provincia
                        FROM operational.municipios mu
                        JOIN operational.provincias p ON p.id = mu.provincia_id
                        WHERE mu.id = :id
                    """),
                    {"id": int(municipio_id_raw)},
                ).mappings().one_or_none()
            if municipio is None:
                raise HTTPException(status_code=400, detail="Municipio no válido")

            approved_value = f"{municipio['provincia']} / {municipio['municipio']}"
            db.execute(
                text("""
                    UPDATE operational.respuestas_mapeo_territorios_servicio
                    SET provincia_resuelta = :provincia,
                        municipio_resuelto = :municipio,
                        municipio_id = :municipio_id,
                        metodo_resolucion = 'manual',
                        confianza = 1,
                        requiere_revision = FALSE
                    WHERE id = :id
                """),
                {
                    "id": territorio_id,
                    "provincia": municipio["provincia"],
                    "municipio": municipio["municipio"],
                    "municipio_id": municipio["id"],
                },
            )
        elif action == "descriptive":
            approved_value = "Territorio descriptivo"
            db.execute(
                text("""
                    UPDATE operational.respuestas_mapeo_territorios_servicio
                    SET metodo_resolucion = 'territorio_descriptivo',
                        requiere_revision = FALSE
                    WHERE id = :id
                """),
                {"id": territorio_id},
            )
        else:
            raise HTTPException(status_code=400, detail="Acción no válida")

        db.execute(
            text("""
                INSERT INTO operational.revisiones_datos (
                    tipo_revision,
                    tabla_origen,
                    registro_origen_id,
                    valor_original,
                    valor_sugerido,
                    valor_aprobado,
                    accion,
                    usuario,
                    observacion
                )
                VALUES (
                    'territorio_servicio',
                    'operational.respuestas_mapeo_territorios_servicio',
                    :registro_origen_id,
                    :valor_original,
                    :valor_sugerido,
                    :valor_aprobado,
                    :accion,
                    :usuario,
                    :observacion
                )
            """),
            {
                "registro_origen_id": territorio_id,
                "valor_original": current["texto_original"],
                "valor_sugerido": " / ".join(
                    value for value in [current["provincia_resuelta"], current["municipio_resuelto"]] if value
                ),
                "valor_aprobado": approved_value,
                "accion": action,
                "usuario": review_user,
                "observacion": observacion,
            },
        )
        db.commit()
        return RedirectResponse(url="/admin/administracion", status_code=303)
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


@app.post("/admin/revision/entidades/{revision_id}")
@app.post("/admin/administracion/entidades/{revision_id}")
async def admin_revision_entidad(request: Request, revision_id: int):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)
    if not _has_review_access(request):
        raise HTTPException(status_code=403, detail="No tiene permisos para administrar datos")
    review_user = _session_username(request) or ANALYTICS_USERNAME

    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    action = form.get("action", [""])[0]
    observacion = form.get("observacion", [""])[0] or None

    db = SessionLocal()
    try:
        current = db.execute(
            text("""
                SELECT rel.id,
                       rel.entidad_apoyo_id,
                       rel.entidad_sugerida_id,
                       rel.nombre_reportado,
                       actual.nombre_canonico AS entidad_actual,
                       sugerida.nombre_canonico AS entidad_sugerida
                FROM operational.respuestas_entidades_apoyo rel
                JOIN operational.entidades_apoyo actual ON actual.id = rel.entidad_apoyo_id
                LEFT JOIN operational.entidades_apoyo sugerida ON sugerida.id = rel.entidad_sugerida_id
                WHERE rel.id = :id
            """),
            {"id": revision_id},
        ).mappings().one_or_none()
        if current is None:
            raise HTTPException(status_code=404, detail="Revisión de entidad no encontrada")

        if action == "merge":
            if current["entidad_sugerida_id"] is None:
                raise HTTPException(status_code=400, detail="No hay entidad sugerida para unir")
            approved_value = current["entidad_sugerida"]
            old_entity_id = current["entidad_apoyo_id"]
            db.execute(
                text("""
                    UPDATE operational.respuestas_entidades_apoyo
                    SET entidad_apoyo_id = :entidad_sugerida_id,
                        entidad_sugerida_id = NULL,
                        metodo_resolucion = 'manual_unida',
                        confianza = 1,
                        requiere_revision = FALSE,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": revision_id, "entidad_sugerida_id": current["entidad_sugerida_id"]},
            )
            remaining_links = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM operational.respuestas_entidades_apoyo
                    WHERE entidad_apoyo_id = :entidad_apoyo_id
                """),
                {"entidad_apoyo_id": old_entity_id},
            ).scalar_one()
            if remaining_links == 0:
                db.execute(
                    text("""
                        UPDATE operational.entidades_apoyo
                        SET estado_revision = 'fusionada',
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": old_entity_id},
                )
        elif action == "separate":
            approved_value = current["entidad_actual"]
            db.execute(
                text("""
                    UPDATE operational.respuestas_entidades_apoyo
                    SET entidad_sugerida_id = NULL,
                        metodo_resolucion = 'manual_separada',
                        requiere_revision = FALSE,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": revision_id},
            )
        else:
            raise HTTPException(status_code=400, detail="Acción no válida")

        db.execute(
            text("""
                INSERT INTO operational.revisiones_datos (
                    tipo_revision,
                    tabla_origen,
                    registro_origen_id,
                    valor_original,
                    valor_sugerido,
                    valor_aprobado,
                    accion,
                    usuario,
                    observacion
                )
                VALUES (
                    'entidad_duplicada',
                    'operational.respuestas_entidades_apoyo',
                    :registro_origen_id,
                    :valor_original,
                    :valor_sugerido,
                    :valor_aprobado,
                    :accion,
                    :usuario,
                    :observacion
                )
            """),
            {
                "registro_origen_id": revision_id,
                "valor_original": current["entidad_actual"],
                "valor_sugerido": current["entidad_sugerida"],
                "valor_aprobado": approved_value,
                "accion": action,
                "usuario": review_user,
                "observacion": observacion,
            },
        )
        db.commit()
        return RedirectResponse(url="/admin/administracion", status_code=303)
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()



@app.post("/admin/administracion/entidades-canonicas/{entity_id}")
async def admin_administracion_entidad_canonica(request: Request, entity_id: int):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)
    if not _has_review_access(request):
        raise HTTPException(status_code=403, detail="No tiene permisos para administrar datos")
    review_user = _session_username(request) or ANALYTICS_USERNAME

    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    nombre_canonico = form.get("nombre_canonico", [""])[0].strip()
    if not nombre_canonico:
        raise HTTPException(status_code=400, detail="El nombre de la entidad es obligatorio")

    fields = {
        "nombre_canonico": nombre_canonico,
        "nombre_normalizado": normalize_entity_name(nombre_canonico),
        "tipo_estructura_apoyo": form.get("tipo_estructura_apoyo", [""])[0].strip() or None,
        "cobertura_principal": form.get("cobertura_principal", [""])[0].strip() or None,
        "direccion_fisica": form.get("direccion_fisica", [""])[0].strip() or None,
        "telefonos": form.get("telefonos", [""])[0].strip() or None,
        "correo_electronico": form.get("correo_electronico", [""])[0].strip() or None,
        "sitio_web": form.get("sitio_web", [""])[0].strip() or None,
        "redes_sociales": form.get("redes_sociales", [""])[0].strip() or None,
        "persona_contacto_cargo": form.get("persona_contacto_cargo", [""])[0].strip() or None,
        "observacion": form.get("observacion", [""])[0].strip() or None,
    }

    db = SessionLocal()
    try:
        current = db.execute(
            text("""
                SELECT id, nombre_canonico, tipo_estructura_apoyo, cobertura_principal,
                       direccion_fisica, telefonos, correo_electronico, sitio_web,
                       redes_sociales, persona_contacto_cargo
                FROM operational.entidades_apoyo
                WHERE id = :id
            """),
            {"id": entity_id},
        ).mappings().one_or_none()
        if current is None:
            raise HTTPException(status_code=404, detail="Entidad no encontrada")

        db.execute(
            text("""
                UPDATE operational.entidades_apoyo
                SET nombre_canonico = :nombre_canonico,
                    nombre_normalizado = :nombre_normalizado,
                    tipo_estructura_apoyo = :tipo_estructura_apoyo,
                    cobertura_principal = :cobertura_principal,
                    direccion_fisica = :direccion_fisica,
                    telefonos = :telefonos,
                    correo_electronico = :correo_electronico,
                    sitio_web = :sitio_web,
                    redes_sociales = :redes_sociales,
                    persona_contacto_cargo = :persona_contacto_cargo,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"id": entity_id, **fields},
        )
        db.execute(
            text("""
                INSERT INTO operational.revisiones_datos (
                    tipo_revision, tabla_origen, registro_origen_id, valor_original,
                    valor_sugerido, valor_aprobado, accion, usuario, observacion
                )
                VALUES (
                    'entidad_canonica', 'operational.entidades_apoyo', :registro_origen_id,
                    :valor_original, NULL, :valor_aprobado, 'editar_entidad', :usuario, :observacion
                )
            """),
            {
                "registro_origen_id": entity_id,
                "valor_original": current["nombre_canonico"],
                "valor_aprobado": nombre_canonico,
                "usuario": review_user,
                "observacion": fields["observacion"],
            },
        )
        db.commit()
        return RedirectResponse(url="/admin/administracion#entidades", status_code=303)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una entidad con ese nombre normalizado en el mismo municipio") from exc
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


@app.post("/admin/administracion/enlaces-entidad/{link_id}")
async def admin_administracion_enlace_entidad(request: Request, link_id: int):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)
    if not _has_review_access(request):
        raise HTTPException(status_code=403, detail="No tiene permisos para administrar datos")
    review_user = _session_username(request) or ANALYTICS_USERNAME

    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    action = form.get("action", [""])[0]
    if action != "split_new":
        raise HTTPException(status_code=400, detail="Acción no válida")

    nombre_canonico = form.get("nombre_canonico", [""])[0].strip()
    observacion = form.get("observacion", [""])[0].strip() or None
    if not nombre_canonico:
        raise HTTPException(status_code=400, detail="Debe indicar el nombre correcto de la entidad")
    nombre_normalizado = normalize_entity_name(nombre_canonico)

    db = SessionLocal()
    try:
        current = db.execute(
            text("""
                SELECT rel.id,
                       rel.entidad_apoyo_id,
                       rel.operational_respuesta_id,
                       rel.nombre_reportado,
                       ea.nombre_canonico AS entidad_actual,
                       p.id AS provincia_id,
                       p.nombre AS provincia,
                       mu.id AS municipio_id,
                       mu.nombre AS municipio,
                       COALESCE(m.tipo_estructura_apoyo, op.tipo_institucion) AS tipo_estructura_apoyo,
                       COALESCE(m.cobertura_principal, op.ambito_actuacion) AS cobertura_principal,
                       m.direccion_fisica,
                       m.telefonos,
                       m.correo_electronico,
                       m.sitio_web,
                       m.redes_sociales,
                       m.persona_contacto_cargo
                FROM operational.respuestas_entidades_apoyo rel
                JOIN operational.entidades_apoyo ea ON ea.id = rel.entidad_apoyo_id
                JOIN operational.respuestas_encuesta op ON op.id = rel.operational_respuesta_id
                JOIN operational.provincias p ON p.id = op.provincia_id
                JOIN operational.municipios mu ON mu.id = op.municipio_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = op.id
                WHERE rel.id = :id
            """),
            {"id": link_id},
        ).mappings().one_or_none()
        if current is None:
            raise HTTPException(status_code=404, detail="Enlace de entidad no encontrado")

        new_entity_id = db.execute(
            text("""
                INSERT INTO operational.entidades_apoyo (
                    nombre_canonico, nombre_normalizado, provincia_id, municipio_id,
                    tipo_estructura_apoyo, cobertura_principal, direccion_fisica,
                    telefonos, correo_electronico, sitio_web, redes_sociales,
                    persona_contacto_cargo, estado_revision, created_at, updated_at
                )
                VALUES (
                    :nombre_canonico, :nombre_normalizado, :provincia_id, :municipio_id,
                    :tipo_estructura_apoyo, :cobertura_principal, :direccion_fisica,
                    :telefonos, :correo_electronico, :sitio_web, :redes_sociales,
                    :persona_contacto_cargo, 'activa', NOW(), NOW()
                )
                ON CONFLICT (provincia_id, municipio_id, nombre_normalizado)
                DO UPDATE SET updated_at = NOW()
                RETURNING id
            """),
            {
                "nombre_canonico": nombre_canonico,
                "nombre_normalizado": nombre_normalizado,
                "provincia_id": current["provincia_id"],
                "municipio_id": current["municipio_id"],
                "tipo_estructura_apoyo": current["tipo_estructura_apoyo"],
                "cobertura_principal": current["cobertura_principal"],
                "direccion_fisica": current["direccion_fisica"],
                "telefonos": current["telefonos"],
                "correo_electronico": current["correo_electronico"],
                "sitio_web": current["sitio_web"],
                "redes_sociales": current["redes_sociales"],
                "persona_contacto_cargo": current["persona_contacto_cargo"],
            },
        ).scalar_one()

        if int(new_entity_id) == int(current["entidad_apoyo_id"]):
            raise HTTPException(status_code=409, detail="El nombre indicado normaliza igual que la entidad actual; use un nombre más específico")

        db.execute(
            text("""
                UPDATE operational.respuestas_entidades_apoyo
                SET entidad_apoyo_id = :new_entity_id,
                    entidad_sugerida_id = NULL,
                    metodo_resolucion = 'manual_nueva_entidad',
                    confianza = 1,
                    requiere_revision = FALSE,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"id": link_id, "new_entity_id": new_entity_id},
        )
        remaining_links = db.execute(
            text("""
                SELECT COUNT(*)
                FROM operational.respuestas_entidades_apoyo
                WHERE entidad_apoyo_id = :old_entity_id
            """),
            {"old_entity_id": current["entidad_apoyo_id"]},
        ).scalar_one()
        if remaining_links == 0:
            db.execute(
                text("""
                    UPDATE operational.entidades_apoyo
                    SET estado_revision = 'descartada', updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": current["entidad_apoyo_id"]},
            )

        db.execute(
            text("""
                INSERT INTO operational.revisiones_datos (
                    tipo_revision, tabla_origen, registro_origen_id, valor_original,
                    valor_sugerido, valor_aprobado, accion, usuario, observacion
                )
                VALUES (
                    'entidad_enlace', 'operational.respuestas_entidades_apoyo', :registro_origen_id,
                    :valor_original, :valor_sugerido, :valor_aprobado,
                    'separar_nueva_entidad', :usuario, :observacion
                )
            """),
            {
                "registro_origen_id": link_id,
                "valor_original": current["nombre_reportado"],
                "valor_sugerido": current["entidad_actual"],
                "valor_aprobado": nombre_canonico,
                "usuario": review_user,
                "observacion": observacion,
            },
        )
        db.commit()
        return RedirectResponse(url="/admin/administracion#enlaces", status_code=303)
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()


@app.post("/admin/revision/coordenadas/{operational_respuesta_id}")
@app.post("/admin/administracion/coordenadas/{operational_respuesta_id}")
async def admin_revision_coordenadas(request: Request, operational_respuesta_id: int):
    if not _has_analytics_access(request):
        return _redirect_to_login(request)
    if not _has_review_access(request):
        raise HTTPException(status_code=403, detail="No tiene permisos para administrar datos")
    review_user = _session_username(request) or ANALYTICS_USERNAME

    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    lat_raw = form.get("lat", [""])[0].strip().replace(",", ".")
    lng_raw = form.get("lng", [""])[0].strip().replace(",", ".")
    observacion = form.get("observacion", [""])[0] or None

    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Latitud y longitud deben ser números") from exc

    if not -90 <= lat <= 90:
        raise HTTPException(status_code=400, detail="Latitud fuera de rango")
    if not -180 <= lng <= 180:
        raise HTTPException(status_code=400, detail="Longitud fuera de rango")

    db = SessionLocal()
    try:
        current = db.execute(
            text("""
                SELECT op.id,
                       op.nombre_institucion,
                       p.nombre AS provincia,
                       mu.nombre AS municipio,
                       m.direccion_fisica,
                       g.lat AS lat_actual,
                       g.lng AS lng_actual,
                       g.fuente AS fuente_actual,
                       g.estado AS estado_actual
                FROM operational.respuestas_encuesta op
                JOIN operational.provincias p ON p.id = op.provincia_id
                JOIN operational.municipios mu ON mu.id = op.municipio_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = op.id
                LEFT JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = op.id
                WHERE op.id = :id
            """),
            {"id": operational_respuesta_id},
        ).mappings().one_or_none()
        if current is None:
            raise HTTPException(status_code=404, detail="Entidad no encontrada")

        original = "Sin coordenadas"
        if current["lat_actual"] is not None and current["lng_actual"] is not None:
            original = f"{current['lat_actual']}, {current['lng_actual']} ({current['fuente_actual'] or current['estado_actual'] or 'sin fuente'})"
        approved = f"{lat:.7f}, {lng:.7f}"

        db.execute(
            text("""
                INSERT INTO operational.geocodificacion_entidades (
                    operational_respuesta_id,
                    direccion_original,
                    provincia,
                    municipio,
                    lat,
                    lng,
                    fuente,
                    confianza,
                    estado,
                    observacion,
                    fecha_validacion,
                    validado_por,
                    updated_at
                )
                VALUES (
                    :operational_respuesta_id,
                    :direccion_original,
                    :provincia,
                    :municipio,
                    :lat,
                    :lng,
                    'revision_manual',
                    1,
                    'validada',
                    :observacion,
                    NOW(),
                    :validado_por,
                    NOW()
                )
                ON CONFLICT (operational_respuesta_id)
                DO UPDATE SET
                    direccion_original = EXCLUDED.direccion_original,
                    provincia = EXCLUDED.provincia,
                    municipio = EXCLUDED.municipio,
                    lat = EXCLUDED.lat,
                    lng = EXCLUDED.lng,
                    fuente = EXCLUDED.fuente,
                    confianza = EXCLUDED.confianza,
                    estado = EXCLUDED.estado,
                    observacion = EXCLUDED.observacion,
                    fecha_validacion = EXCLUDED.fecha_validacion,
                    validado_por = EXCLUDED.validado_por,
                    updated_at = NOW()
            """),
            {
                "operational_respuesta_id": operational_respuesta_id,
                "direccion_original": current["direccion_fisica"],
                "provincia": current["provincia"],
                "municipio": current["municipio"],
                "lat": lat,
                "lng": lng,
                "observacion": observacion,
                "validado_por": review_user,
            },
        )
        db.execute(
            text("""
                INSERT INTO operational.revisiones_datos (
                    tipo_revision,
                    tabla_origen,
                    registro_origen_id,
                    valor_original,
                    valor_sugerido,
                    valor_aprobado,
                    accion,
                    usuario,
                    observacion
                )
                VALUES (
                    'coordenada_entidad',
                    'operational.geocodificacion_entidades',
                    :registro_origen_id,
                    :valor_original,
                    NULL,
                    :valor_aprobado,
                    'actualizar_coordenadas',
                    :usuario,
                    :observacion
                )
            """),
            {
                "registro_origen_id": operational_respuesta_id,
                "valor_original": original,
                "valor_aprobado": approved,
                "usuario": review_user,
                "observacion": observacion,
            },
        )
        db.commit()
        return RedirectResponse(url="/admin/administracion", status_code=303)
    except HTTPException:
        db.rollback()
        raise
    finally:
        db.close()

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
                    SELECT id, estado
                    FROM raw.respuestas_formulario
                    WHERE id_respuesta_origen = :id_respuesta_origen
                    LIMIT 1
                """),
                {"id_respuesta_origen": data.id_respuesta_origen},
            ).mappings().one_or_none()

            if duplicate is not None:
                db.commit()
                pipeline_result = _run_pipeline_chain()
                return {
                    "status": "ok",
                    "raw_id": duplicate["id"],
                    "duplicate": True,
                    "raw_estado": duplicate["estado"],
                    "pipeline": pipeline_result,
                }
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






