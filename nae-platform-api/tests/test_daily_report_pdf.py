import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "nae")
os.environ.setdefault("DB_USER", "nae")
os.environ.setdefault("DB_PASSWORD", "nae")
os.environ.setdefault("API_TOKEN", "test-token")
os.environ.setdefault("APP_TIMEZONE", "America/Havana")
os.environ.setdefault("ANALYTICS_USERNAME", "admin")
os.environ.setdefault("ANALYTICS_PASSWORD", "secret")
os.environ.setdefault("ANALYTICS_USERS", "")
os.environ.setdefault("ANALYTICS_REVIEW_USERS", "")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SESSION_MAX_AGE_SECONDS", "28800")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

from app.reporting import build_daily_progress_report_pdf


def test_daily_report_pdf_is_managerial_not_technical():
    pdf = build_daily_progress_report_pdf(
        {
            "fecha": "2026-08-12",
            "summary": {
                "respuestas_acumuladas": 25,
                "respuestas_dia": 5,
                "entidades_acumuladas": 18,
                "entidades_con_envio_dia": 4,
                "provincias_cubiertas": 3,
                "municipios_cubiertos": 7,
            },
            "daily_trend": [{"fecha": "2026-08-12", "total": 5}],
            "territorial": [{"provincia": "La Habana", "entidades": 10}],
            "territorial_municipal": [{"provincia": "La Habana", "municipio": "Playa", "envios": 4}],
            "structure_types": [{"label": "Trabajador/a por cuenta propia con servicios de apoyo a NAE", "total": 9}],
            "services_offered": [{"label": "Gestion empresarial", "total": 8}],
            "services_to_strengthen": [{"label": "Acceso a financiamiento", "total": 6}],
            "new_entities": [],
        }
    )

    assert pdf.startswith(b"%PDF-1.4")
    assert b"Reporte diario de avance" in pdf
    assert b"Generado por: NAE - Mapeo de Entidades de Apoyo" in pdf
    assert b"Fecha y hora de generaci" in pdf
    assert b"Cobertura territorial por provincia" in pdf
    assert b"Cantidad por tipo de estructura" in pdf
    assert b"Anexo territorial" in pdf
    assert b"La Habana" in pdf
    assert b"Playa" in pdf
    assert b"Trabajador/a por cuenta propia" in pdf
    assert b"servicios de apoyo a NAE" in pdf
    assert b"Calidad del dato" not in pdf
    assert b"Acciones administrativas" not in pdf
