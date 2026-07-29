import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "nae")
os.environ.setdefault("DB_USER", "nae")
os.environ.setdefault("DB_PASSWORD", "nae")
os.environ.setdefault("API_TOKEN", "test-token")

from app.reporting import _with_coordinates, build_support_entities_pdf, render_support_entities_html


def test_with_coordinates_prefers_validated_geocoding():
    row = {
        "provincia": "La Habana",
        "municipio": "Plaza de la Revolución",
        "geocoding_lat": 23.1411111,
        "geocoding_lng": -82.3892222,
        "geocoding_fuente": "revision_manual",
        "geocoding_estado": "validada",
        "geocoding_confianza": 1,
    }

    result = _with_coordinates(row)

    assert result["lat"] == 23.1411111
    assert result["lng"] == -82.3892222
    assert result["coordinate_source"] == "revision_manual"
    assert result["coordinate_status"] == "validada"
    assert result["coordinate_confidence"] == 1


def test_with_coordinates_falls_back_to_municipality():
    row = {
        "provincia": "La Habana",
        "municipio": "Plaza de la Revolución",
        "geocoding_lat": None,
        "geocoding_lng": None,
    }

    result = _with_coordinates(row)

    assert result["lat"] == 23.125
    assert result["lng"] == -82.3853
    assert result["coordinate_source"] == "municipio"
    assert result["coordinate_status"] == "estimada"


def test_support_map_popup_uses_filtered_services_only():
    html = render_support_entities_html({
        "lookups": {"provincias": ["Villa Clara"], "municipios": ["Santa Clara"], "tipos": ["Universidad"]},
        "filters": {"limit": 200},
        "total": 1,
        "entidades": [{
            "operational_respuesta_id": 4,
            "entidad_nombre": "Entidad de prueba",
            "tipo_estructura_apoyo": "Universidad",
            "provincia": "Villa Clara",
            "municipio": "Santa Clara",
            "cobertura_principal": "Provincial",
            "persona_contacto_cargo": "Contacto",
            "telefonos": "123",
            "correo_electronico": "nae@example.test",
            "servicios": "Gestión empresarial, Asesoría legal o normativa",
            "lat": 22.4,
            "lng": -79.9,
            "coordinate_source": "geocodificacion",
            "coordinate_status": "validada",
        }],
    })

    assert "Gestión empresarial, Asesoría legal o normativa" in html
    assert "Acceso a financiamiento o preparación para financiamiento" not in html
    assert "Directorio PDF" in html


def test_support_entities_pdf_starts_with_pdf_header():
    pdf = build_support_entities_pdf({
        "entidades": [{
            "provincia": "Villa Clara",
            "municipio": "Santa Clara",
            "entidad_nombre": "Entidad de prueba",
            "tipo_estructura_apoyo": "Universidad",
            "servicios": "Gestión empresarial",
        }]
    })

    assert pdf.startswith(b"%PDF-1.4")
