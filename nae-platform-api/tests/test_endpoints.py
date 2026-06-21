import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "nae")
os.environ.setdefault("DB_USER", "nae")
os.environ.setdefault("DB_PASSWORD", "nae")
os.environ.setdefault("API_TOKEN", "test-token")

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

    response = client.get("/api/v1/resumen.csv", params={"limit": 2})

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
    monkeypatch.setattr(main, "render_dashboard_html", lambda data: "<html>panel</html>")

    response = client.get("/?limit=4")

    assert response.status_code == 200
    assert response.text == "<html>panel</html>"
    assert captured == {
        "limit": 4,
        "provincia": None,
        "version_encuesta": None,
        "genero": None,
        "tema": None,
    }


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

    api_response = client.get("/api/v1/respuestas/3")
    html_response = client.get("/respuestas/3")

    assert api_response.status_code == 200
    assert api_response.json()["respuesta_id"] == 3
    assert html_response.status_code == 200
    assert html_response.text == "<html>detalle</html>"


def test_response_detail_missing_returns_404(monkeypatch):
    monkeypatch.setattr(main, "get_response_detail", lambda respuesta_id: None)

    response = client.get("/api/v1/respuestas/9999")

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
    monkeypatch.setattr(main, "process_raw_to_staging", lambda limit=100: order.append(("raw", limit)))
    monkeypatch.setattr(main, "process_staging_to_operational", lambda limit=100: order.append(("operational", limit)))
    monkeypatch.setattr(main, "process_operational_to_analytics", lambda limit=100: order.append(("analytics", limit)))

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
    assert response.json() == {"status": "ok", "raw_id": 42}
    assert order == [("raw", 100), ("operational", 100), ("analytics", 100)]
    assert fake_db.commits == 1
    assert fake_db.closed is True
