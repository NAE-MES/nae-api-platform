from app.entity_resolution import classify_entity_match, entity_similarity, normalize_entity_name


def test_normalize_entity_name_removes_noise_words_and_accents():
    assert normalize_entity_name("Centro de Apoyo NAE de Santa Clara") == "santa clara"


def test_entity_similarity_matches_acronym_for_canonical_name():
    score = entity_similarity("UCLV", "Universidad Central Marta Abreu de Las Villas")

    assert score >= 0.9


def test_classify_entity_match_marks_uncertain_duplicates_for_review():
    match = classify_entity_match(10, "Universidad Central Marta Abreu", 0.8)

    assert match.entidad_apoyo_id == 10
    assert match.metodo_resolucion == "similitud_revision"
    assert match.requiere_revision is True


def test_classify_entity_match_accepts_high_similarity_automatically():
    match = classify_entity_match(10, "Universidad Central Marta Abreu", 0.95)

    assert match.entidad_apoyo_id == 10
    assert match.metodo_resolucion == "similitud"
    assert match.requiere_revision is False
