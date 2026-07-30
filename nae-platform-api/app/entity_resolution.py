from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from app.territory_normalization import normalize_text


AUTO_THRESHOLD = 0.9
REVIEW_THRESHOLD = 0.78

LEGAL_NOISE_WORDS = {
    "centro",
    "entidad",
    "institucion",
    "estructura",
    "apoyo",
    "nae",
    "los",
    "las",
    "del",
    "de",
    "la",
    "el",
}

ABBREVIATIONS = {
    "univ": "universidad",
    "u": "universidad",
}

KNOWN_ACRONYMS = {
    "uclv": ("universidad", "central", "villas"),
    "uci": ("universidad", "ciencias", "informaticas"),
}


@dataclass(frozen=True)
class EntityMatch:
    entidad_apoyo_id: Optional[int]
    nombre_canonico: Optional[str]
    confianza: float
    metodo_resolucion: str
    requiere_revision: bool


def normalize_entity_name(value: str | None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""

    tokens = []
    for token in normalized.split():
        token = ABBREVIATIONS.get(token, token)
        if token in LEGAL_NOISE_WORDS:
            continue
        tokens.append(token)
    return " ".join(tokens) or normalized


def entity_similarity(left: str | None, right: str | None) -> float:
    left_norm = normalize_entity_name(left)
    right_norm = normalize_entity_name(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0

    score = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        score = max(score, overlap)

    acronym = "".join(token[0] for token in re.findall(r"[a-z0-9]+", right_norm) if token)
    if left_norm == acronym or right_norm == acronym:
        score = max(score, 0.92)
    for acronym_value, required_tokens in KNOWN_ACRONYMS.items():
        if left_norm == acronym_value and all(token in right_norm.split() for token in required_tokens):
            score = max(score, 0.94)
        if right_norm == acronym_value and all(token in left_norm.split() for token in required_tokens):
            score = max(score, 0.94)

    return round(score, 4)


def classify_entity_match(
    entity_id: Optional[int],
    canonical_name: Optional[str],
    score: float,
) -> EntityMatch:
    if entity_id is None:
        return EntityMatch(None, None, 0.0, "nueva", False)
    if score >= AUTO_THRESHOLD:
        method = "exacta" if score == 1.0 else "similitud"
        return EntityMatch(entity_id, canonical_name, score, method, False)
    if score >= REVIEW_THRESHOLD:
        return EntityMatch(entity_id, canonical_name, score, "similitud_revision", True)
    return EntityMatch(None, None, score, "nueva", False)
