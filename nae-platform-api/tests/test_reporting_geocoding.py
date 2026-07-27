import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "nae")
os.environ.setdefault("DB_USER", "nae")
os.environ.setdefault("DB_PASSWORD", "nae")
os.environ.setdefault("API_TOKEN", "test-token")

from app.reporting import _with_coordinates


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
