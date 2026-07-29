import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "geocode_pending_entities.py"
SPEC = importlib.util.spec_from_file_location("geocode_pending_entities", SCRIPT_PATH)
geocoder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["geocode_pending_entities"] = geocoder
SPEC.loader.exec_module(geocoder)


def test_build_query_includes_entity_address_and_cuba():
    entity = geocoder.PendingEntity(
        operational_respuesta_id=1,
        entidad="Centro de Apoyo NAE",
        direccion_fisica="Calle 23 entre L y M",
        provincia="La Habana",
        municipio="Plaza de la Revolución",
    )

    assert geocoder.build_query(entity) == (
        "Centro de Apoyo NAE, Calle 23 entre L y M, Plaza de la Revolución, La Habana, Cuba"
    )


def test_score_result_rewards_expected_location():
    entity = geocoder.PendingEntity(
        operational_respuesta_id=1,
        entidad="Centro de Apoyo NAE",
        direccion_fisica="Calle 23",
        provincia="La Habana",
        municipio="Plaza de la Revolución",
    )
    result = {
        "display_name": "Plaza de la Revolución, La Habana, Cuba",
        "importance": 0.35,
        "class": "amenity",
        "type": "office",
    }

    assert geocoder.score_result(result, entity) >= 0.85

def test_extract_plus_code_from_google_address():
    assert geocoder.extract_plus_code("C4W4+F4X, Santa Clara, Cuba") == "C4W4+F4X"


def test_extract_coordinates_from_google_maps_text():
    assert geocoder.extract_coordinates("22.446234, -79.894646") == (22.446234, -79.894646)
    assert geocoder.extract_coordinates("https://maps.google.com/?q=22.446234,-79.894646") == (
        22.446234,
        -79.894646,
    )


def test_geocode_coordinates_takes_precedence_over_plus_code():
    entity = geocoder.PendingEntity(
        operational_respuesta_id=3,
        entidad="Universidad Central Marta Abreu de Las Villas",
        direccion_fisica="C4W4+F4X, Santa Clara, Cuba 22.446234, -79.894646",
        provincia="Villa Clara",
        municipio="Santa Clara",
    )

    result = geocoder.geocode_entity(entity, user_agent="test")

    assert result.source == "coordenadas"
    assert result.lat == 22.446234
    assert result.lng == -79.894646


def test_geocode_plus_code_uses_municipality_reference():
    entity = geocoder.PendingEntity(
        operational_respuesta_id=3,
        entidad="Universidad Central Marta Abreu de Las Villas",
        direccion_fisica="C4W4+F4X, Santa Clara, Cuba",
        provincia="Villa Clara",
        municipio="Santa Clara",
    )

    result = geocoder.geocode_plus_code(entity)

    assert result is not None
    assert result.source == "plus_code"
    assert result.confidence == 1.0
    assert abs(result.lat - 22.446234) < 0.001
    assert abs(result.lng - -79.894646) < 0.001

def test_fetch_pending_entities_prefers_geocoding_original_address(monkeypatch):
    captured = {}

    class FakeResult:
        def mappings(self):
            return self

        def all(self):
            return []

    class FakeDB:
        def execute(self, query, params=None):
            captured["query"] = str(query)
            captured["params"] = params
            return FakeResult()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(geocoder, "SessionLocal", lambda: FakeDB())

    assert geocoder.fetch_pending_entities(5) == []
    assert "COALESCE(g.direccion_original, m.direccion_fisica) AS direccion_fisica" in captured["query"]
    assert captured["params"] == {"limit": 5}
    assert captured["closed"] is True

