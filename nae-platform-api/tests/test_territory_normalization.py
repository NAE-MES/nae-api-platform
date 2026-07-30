from app.territory_normalization import normalize_service_territories, split_territory_text


def test_split_territory_text_accepts_common_separators():
    assert split_territory_text("Santa Clara, Camajuaní; Remedios y Placetas") == [
        "Santa Clara",
        "Camajuaní",
        "Remedios",
        "Placetas",
    ]


def test_normalize_service_territories_resolves_exact_municipalities_with_province_context():
    matches = normalize_service_territories("Santa Clara, Camajuaní", "Villa Clara")

    assert [(match.provincia_resuelta, match.municipio_resuelto, match.requiere_revision) for match in matches] == [
        ("Villa Clara", "Santa Clara", False),
        ("Villa Clara", "Camajuaní", False),
    ]


def test_normalize_service_territories_resolves_high_similarity_typo():
    matches = normalize_service_territories("Santa Clra", "Villa Clara")

    assert matches[0].municipio_resuelto == "Santa Clara"
    assert matches[0].metodo_resolucion == "similitud"
    assert matches[0].requiere_revision is False


def test_normalize_service_territories_marks_uncertain_text_for_review():
    matches = normalize_service_territories("zona norte completa", "Villa Clara")

    assert matches[0].municipio_resuelto is None
    assert matches[0].metodo_resolucion == "sin_coincidencia"
    assert matches[0].requiere_revision is True
