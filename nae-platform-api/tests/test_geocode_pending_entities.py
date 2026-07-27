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
