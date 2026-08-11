import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "nae")
os.environ.setdefault("DB_USER", "nae")
os.environ.setdefault("DB_PASSWORD", "nae")
os.environ.setdefault("API_TOKEN", "test-token")
os.environ.setdefault("ANALYTICS_USERNAME", "admin")
os.environ.setdefault("ANALYTICS_PASSWORD", "secret")
os.environ.setdefault("ANALYTICS_USERS", "")
os.environ.setdefault("ANALYTICS_REVIEW_USERS", "")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SESSION_MAX_AGE_SECONDS", "28800")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from fastapi.testclient import TestClient

import app.main as main


client = TestClient(main.app)


def test_salud_endpoint():
    response = client.get("/api/v1/salud")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_resumen_endpoint_forwards_filters(monkeypatch):
    captured = {}

    def fake_get_dashboard_data(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "filters": kwargs}

    monkeypatch.setattr(main, "get_dashboard_data", fake_get_dashboard_data)

    response = client.get(
        "/api/v1/resumen",
        headers={"Authorization": "Bearer test-token"},
        params={
            "limit": 7,
            "provincia": "La Habana",
            "version_encuesta": "1.1",
            "genero": "Mujer",
            "tema": "Género y NAE",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "filters": {
            "limit": 7,
            "provincia": "La Habana",
            "version_encuesta": "1.1",
            "genero": "Mujer",
            "tema": "Género y NAE",
        },
    }
    assert captured == {
        "limit": 7,
        "provincia": "La Habana",
        "version_encuesta": "1.1",
        "genero": "Mujer",
        "tema": "Género y NAE",
    }


def test_resumen_csv_endpoint_returns_download(monkeypatch):
    captured = {}

    def fake_get_dashboard_data(**kwargs):
        captured.update(kwargs)
        return {"filters": kwargs}

    monkeypatch.setattr(main, "get_dashboard_data", fake_get_dashboard_data)
    monkeypatch.setattr(main, "build_resumen_csv", lambda data: "id,valor\n1,ok\n")

    response = client.get(
        "/api/v1/resumen.csv",
        headers={"Authorization": "Bearer test-token"},
        params={"limit": 2},
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="nae_resumen.csv"'
    assert response.text == "id,valor\n1,ok\n"
    assert captured == {"limit": 2, "provincia": None, "version_encuesta": None, "genero": None, "tema": None}


def test_resumen_html_endpoint_uses_renderer(monkeypatch):
    captured = {}

    def fake_get_dashboard_data(**kwargs):
        captured.update(kwargs)
        return {
            "filters": {"provincia": None, "version_encuesta": None, "genero": None, "tema": None, "limit": 10},
            "lookups": {"provincias": [], "versiones": [], "generos": [], "temas": []},
            "total_respuestas": 0,
            "por_estado": [],
            "por_provincia": [],
            "por_genero": [],
            "por_nivel_instruccion": [],
            "temas_formacion": [],
            "limitaciones": [],
            "instituciones": [],
            "ultimas_respuestas": [],
        }

    monkeypatch.setattr(main, "get_dashboard_data", fake_get_dashboard_data)
    monkeypatch.setattr(main, "render_dashboard_html", lambda data, can_review=True: "<html>panel</html>")
    monkeypatch.setattr(main, "_has_analytics_access", lambda request, authorization=None: True)

    response = client.get("/analitica?limit=4")

    assert response.status_code == 200
    assert response.text == "<html>panel</html>"
    assert captured == {
        "limit": 4,
        "provincia": None,
        "version_encuesta": None,
        "genero": None,
        "tema": None,
        "tipo": None,
        "servicio": None,
    }


def test_analitica_requires_login():
    client.cookies.clear()
    response = client.get("/analitica", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?")


def test_login_sets_session_cookie():
    client.cookies.clear()
    response = client.post(
        "/login",
        data={"username": "admin", "password": "secret", "next": "/analitica"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/analitica"
    assert main.AUTH_COOKIE_NAME in response.cookies


def test_login_accepts_review_users_with_password(monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(main, "ANALYTICS_USERS", "")
    monkeypatch.setattr(main, "ANALYTICS_REVIEW_USERS", "denys:clave-denys;julia:clave-julia")

    response = client.post(
        "/login",
        data={"username": "denys", "password": "clave-denys", "next": "/admin/administracion"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/administracion"
    assert main.AUTH_COOKIE_NAME in response.cookies

    cookie = response.cookies[main.AUTH_COOKIE_NAME]
    assert main._session_username_from_cookie(cookie) == "denys"
    assert "denys" in main._configured_review_users()


def test_login_accepts_additional_configured_users(monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(main, "ANALYTICS_USERS", "jefe1:clave-jefe-1;jefe2:clave-jefe-2")

    response = client.post(
        "/login",
        data={"username": "jefe1", "password": "clave-jefe-1", "next": "/admin/administracion"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/administracion"
    assert main.AUTH_COOKIE_NAME in response.cookies


def test_session_cookie_expires(monkeypatch):
    monkeypatch.setattr(main, "AUTH_COOKIE_MAX_AGE", 1)
    issued_at = int(main.time.time()) - 10
    payload = main._b64encode(f"admin:{issued_at}".encode("utf-8"))
    cookie = f"{payload}.{main._session_signature(payload)}"

    assert main._is_valid_session_cookie(cookie) is False


def test_public_navigation_keeps_private_links_when_logged_in():
    client.cookies.clear()
    cookie = main._create_session_cookie("admin")
    client.cookies.set(main.AUTH_COOKIE_NAME, cookie)

    response = client.get("/")

    assert response.status_code == 200
    assert "Mapa" in response.text
    assert "Documentación" in response.text
    assert "Administración" in response.text
    assert "Cerrar sesión" in response.text


def test_public_navigation_hides_private_links_without_login():
    client.cookies.clear()

    response = client.get("/")

    assert response.status_code == 200
    assert "Mapa" not in response.text
    assert "Documentación" not in response.text
    assert "Administración" not in response.text
    assert "Cerrar sesión" not in response.text

def test_public_navigation_hides_review_for_non_reviewer(monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(main, "ANALYTICS_USERS", "jefe1:clave-jefe-1")
    monkeypatch.setattr(main, "ANALYTICS_REVIEW_USERS", "")
    cookie = main._create_session_cookie("jefe1")
    client.cookies.set(main.AUTH_COOKIE_NAME, cookie)

    response = client.get("/")

    assert response.status_code == 200
    assert "Administración" not in response.text
    assert "Cerrar sesión" in response.text


def test_admin_administracion_forbidden_for_non_reviewer(monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(main, "ANALYTICS_USERS", "jefe1:clave-jefe-1")
    monkeypatch.setattr(main, "ANALYTICS_REVIEW_USERS", "")
    cookie = main._create_session_cookie("jefe1")
    client.cookies.set(main.AUTH_COOKIE_NAME, cookie)

    response = client.get("/admin/administracion", follow_redirects=False)

    assert response.status_code == 403


def test_admin_administracion_requires_login():
    client.cookies.clear()
    response = client.get("/admin/administracion", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?")


def test_admin_administracion_page_uses_renderer(monkeypatch):
    monkeypatch.setattr(main, "_has_analytics_access", lambda request, authorization=None: True)
    monkeypatch.setattr(main, "_has_review_access", lambda request: True)
    monkeypatch.setattr(main, "get_admin_review_data", lambda: {"territories": [], "entity_reviews": []})
    monkeypatch.setattr(main, "render_admin_review_html", lambda data: "<html>administracion</html>")

    response = client.get("/admin/administracion")

    assert response.status_code == 200
    assert response.text == "<html>administracion</html>"


def test_support_map_requires_login():
    client.cookies.clear()

    response = client.get("/mapa-apoyo", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?")


def test_support_map_allows_authenticated_user(monkeypatch):
    client.cookies.clear()
    cookie = main._create_session_cookie("admin")
    client.cookies.set(main.AUTH_COOKIE_NAME, cookie)
    monkeypatch.setattr(main, "get_support_entities", lambda **kwargs: {"entidades": [], "lookups": {}, "filters": {}, "total": 0})
    monkeypatch.setattr(main, "render_support_entities_html", lambda data, authenticated=False, can_review=False: "<html>mapa</html>")

    response = client.get("/mapa-apoyo")

    assert response.status_code == 200
    assert response.text == "<html>mapa</html>"


def test_documentation_requires_login():
    client.cookies.clear()

    response = client.get("/documentacion", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?")


def test_documentation_allows_authenticated_user():
    client.cookies.clear()
    cookie = main._create_session_cookie("admin")
    client.cookies.set(main.AUTH_COOKIE_NAME, cookie)

    response = client.get("/documentacion")

    assert response.status_code == 200
    assert "Documentación" in response.text


def test_response_detail_endpoints(monkeypatch):
    detail = {
        "respuesta_id": 3,
        "operational_respuesta_id": 5,
        "raw_respuesta_id": 3,
        "staging_respuesta_id": 3,
        "id_respuesta_origen": "codex-v11-002",
        "formulario_origen": "Encuesta NAE v1.1",
        "version_encuesta": "1.1",
        "fecha_respuesta": "2026-06-19T08:22:07.996288",
        "consentimiento": "Sí, acepto",
        "provincia_nombre": "La Habana",
        "municipio_nombre": "Plaza de la Revolución",
        "tipo_institucion": "Gobierno municipal",
        "nombre_institucion": "NAE Codex Prueba",
        "estado_validacion": "validada",
        "genero": "Mujer",
        "nivel_instruccion": "Universitario",
        "nivel_conocimiento_municipio": "Sin dato",
        "mayoria_titulares_emprendimientos": "Mujeres",
        "porcentaje_mujeres_directivas": "31–50%",
        "programas_mujeres_emprendedoras": "Sí",
        "descripcion_programa_mujeres": "Programa piloto de acompañamiento",
        "ambito_actuacion": "Municipal",
        "nivel_involucramiento": "Medio",
        "nivel_capacitacion_formadores": "Medianamente capacitados",
        "principal_necesidad": "Coordinación institucional",
        "nivel_interes_gobierno": "Medio",
        "mecanismos_coordinacion": "Existen con poca coordinación",
        "temas_formacion": ["Género y NAE"],
        "instituciones_participantes": ["Gobierno municipal"],
        "limitaciones": ["Falta de coordinación"],
        "previous_id": 1,
        "next_id": None,
    }

    monkeypatch.setattr(main, "get_response_detail", lambda respuesta_id: detail if respuesta_id == 3 else None)
    monkeypatch.setattr(main, "render_response_detail_html", lambda data: "<html>detalle</html>")
    monkeypatch.setattr(main, "_has_analytics_access", lambda request, authorization=None: True)

    api_response = client.get("/api/v1/respuestas/3", headers={"Authorization": "Bearer test-token"})
    html_response = client.get("/respuestas/3")

    assert api_response.status_code == 200
    assert api_response.json()["respuesta_id"] == 3
    assert html_response.status_code == 200
    assert html_response.text == "<html>detalle</html>"


def test_support_entities_pdf_endpoint(monkeypatch):
    monkeypatch.setattr(main, "get_support_entities", lambda **kwargs: {"entidades": []})

    response = client.get("/api/v1/entidades-apoyo.pdf", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-1.4")


def test_support_entities_api_requires_authentication():
    client.cookies.clear()

    response = client.get("/api/v1/entidades-apoyo", follow_redirects=False)

    assert response.status_code == 401


def test_response_detail_missing_returns_404(monkeypatch):
    monkeypatch.setattr(main, "get_response_detail", lambda respuesta_id: None)

    response = client.get("/api/v1/respuestas/9999", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 404


def test_recibir_respuesta_dispara_pipelines_automaticamente(monkeypatch):
    class FakeResult:
        def scalar_one_or_none(self):
            return None

        def scalar(self):
            return 42

    class FakeDB:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.closed = False
            self.calls = []

        def execute(self, query, params=None):
            self.calls.append({"query": str(query), "params": params})
            return FakeResult()

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed = True

    order = []

    monkeypatch.setattr(main, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(main, "process_raw_to_staging", lambda limit=100: (order.append(("raw", limit, None)) or {"stats": {"total": 1}}))
    monkeypatch.setattr(main, "process_staging_to_operational", lambda limit=100, only_pending=False: (order.append(("operational", limit, only_pending)) or {"stats": {"total": 1}}))
    monkeypatch.setattr(main, "process_operational_to_analytics", lambda limit=100, only_pending=False: (order.append(("analytics", limit, only_pending)) or {"stats": {"total": 1}}))

    fake_db = FakeDB()

    response = client.post(
        "/api/v1/respuestas",
        headers={"Authorization": "Bearer test-token"},
        json={
            "formulario_origen": "Encuesta NAE v1.1",
            "payload": {"1.1 Provincia": "La Habana"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "raw_id": 42,
        "pipeline": {
            "staging": {"total": 1},
            "operational": {"total": 1},
            "analytics": {"total": 1},
        },
    }
    assert order == [("raw", 100, None), ("operational", 100, True), ("analytics", 100, True)]
    assert fake_db.commits == 1
    assert fake_db.closed is True


def test_admin_review_municipality_selector_uses_full_catalog():
    from app.cuba_geo import CUBA_GEO
    from app.reporting import render_admin_review_html

    municipalities = [
        {"provincia": province_name, "municipio": item["nombre"]}
        for province_name, items in CUBA_GEO.items()
        for item in items
    ]
    html = render_admin_review_html({
        "territories": [{
            "id": 1,
            "texto_original": "Plalla",
            "provincia_resuelta": "La Habana",
            "municipio_resuelto": "Playa",
            "confianza": 0.7273,
            "nombre_institucion": "UCI",
            "provincia_contexto": "La Habana",
        }],
        "municipalities": municipalities,
        "entity_reviews": [],
        "recent_decisions": [],
    })

    assert "La Habana / Playa" in html
    assert "value='La Habana||Playa' selected" in html



def test_admin_review_coordinates_form_is_rendered():
    from app.reporting import render_admin_review_html

    html = render_admin_review_html({
        "territories": [],
        "municipalities": [],
        "entity_reviews": [],
        "coordinate_reviews": [{
            "operational_respuesta_id": 4,
            "entidad_nombre": "Universidad de prueba",
            "provincia": "La Habana",
            "municipio": "Playa",
            "direccion_fisica": "Calle de prueba",
            "lat": 23.1,
            "lng": -82.4,
            "fuente": "municipio",
            "estado_coordenada": "estimada",
        }],
        "recent_decisions": [],
    })

    assert "Coordenadas de entidades" in html
    assert "/admin/administracion/coordenadas/4" in html
    assert "23.1" in html
    assert "-82.4" in html


def test_admin_administracion_coordinates_post_updates_geocoding(monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(main, "_has_analytics_access", lambda request, authorization=None: True)
    monkeypatch.setattr(main, "_has_review_access", lambda request: True)
    monkeypatch.setattr(main, "_session_username", lambda request: "denys")

    class OneOrNoneResult:
        def __init__(self, row):
            self.row = row

        def mappings(self):
            return self

        def one_or_none(self):
            return self.row

    class ExecuteResult:
        def mappings(self):
            return self

        def one_or_none(self):
            return None

    class FakeDB:
        def __init__(self):
            self.calls = []
            self.commits = 0
            self.rollbacks = 0
            self.closed = False

        def execute(self, query, params=None):
            self.calls.append({"query": str(query), "params": params or {}})
            if "FROM operational.respuestas_encuesta op" in str(query):
                return OneOrNoneResult({
                    "id": 4,
                    "nombre_institucion": "Universidad de prueba",
                    "provincia": "La Habana",
                    "municipio": "Playa",
                    "direccion_fisica": "Calle de prueba",
                    "lat_actual": None,
                    "lng_actual": None,
                    "fuente_actual": None,
                    "estado_actual": None,
                })
            return ExecuteResult()

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed = True

    fake_db = FakeDB()
    monkeypatch.setattr(main, "SessionLocal", lambda: fake_db)

    response = client.post(
        "/admin/administracion/coordenadas/4",
        data={"lat": "22.446234", "lng": "-79.894646", "observacion": "Validado en Google Maps"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/administracion"
    geocoding_call = next(call for call in fake_db.calls if "INSERT INTO operational.geocodificacion_entidades" in call["query"])
    history_call = next(call for call in fake_db.calls if "INSERT INTO operational.revisiones_datos" in call["query"])
    assert geocoding_call["params"]["lat"] == 22.446234
    assert geocoding_call["params"]["lng"] == -79.894646
    assert geocoding_call["params"]["validado_por"] == "denys"
    assert history_call["params"]["valor_aprobado"] == "22.4462340, -79.8946460"
    assert fake_db.commits == 1
    assert fake_db.closed is True


def test_recibir_respuesta_duplicada_reprocesa_pendientes(monkeypatch):
    class DuplicateResult:
        def mappings(self):
            return self

        def one_or_none(self):
            return {"id": 6, "estado": "recibida"}

    class FakeDB:
        def __init__(self):
            self.commits = 0
            self.rollbacks = 0
            self.closed = False
            self.calls = []

        def execute(self, query, params=None):
            self.calls.append({"query": str(query), "params": params})
            return DuplicateResult()

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed = True

    order = []
    fake_db = FakeDB()

    monkeypatch.setattr(main, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(main, "process_raw_to_staging", lambda limit=100: (order.append(("raw", limit, None)) or {"stats": {"total": 1}}))
    monkeypatch.setattr(main, "process_staging_to_operational", lambda limit=100, only_pending=False: (order.append(("operational", limit, only_pending)) or {"stats": {"total": 1}}))
    monkeypatch.setattr(main, "process_operational_to_analytics", lambda limit=100, only_pending=False: (order.append(("analytics", limit, only_pending)) or {"stats": {"total": 1}}))

    response = client.post(
        "/api/v1/respuestas",
        headers={"Authorization": "Bearer test-token"},
        json={
            "id_respuesta_origen": "sheet:row:7",
            "formulario_origen": "Formulario para el Mapeo de estructuras de apoyo a los NAE",
            "version_encuesta": "mapeo_estructuras_v1",
            "payload": {"1.1* Provincia": "La Habana"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "raw_id": 6,
        "duplicate": True,
        "raw_estado": "recibida",
        "pipeline": {
            "staging": {"total": 1},
            "operational": {"total": 1},
            "analytics": {"total": 1},
        },
    }
    assert order == [("raw", 100, None), ("operational", 100, True), ("analytics", 100, True)]
    assert fake_db.commits == 1
    assert fake_db.closed is True
