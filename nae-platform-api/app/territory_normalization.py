from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List, Optional

from app.cuba_geo import CUBA_GEO


AUTO_THRESHOLD = 0.86
REVIEW_THRESHOLD = 0.72


@dataclass(frozen=True)
class MunicipalityMatch:
    texto_original: str
    provincia_resuelta: Optional[str]
    municipio_resuelto: Optional[str]
    confianza: float
    metodo_resolucion: str
    requiere_revision: bool


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", str(value).strip())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", normalized)
    return " ".join(normalized.lower().split())


def split_territory_text(value: str | None) -> List[str]:
    if not value:
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[\n;,/|]+|\s+y\s+", text, flags=re.IGNORECASE)
    return [part.strip(" .:-") for part in parts if part.strip(" .:-")]


def official_municipalities(province_hint: str | None = None) -> List[tuple[str, str]]:
    province_norm = normalize_text(province_hint)
    candidates: List[tuple[str, str]] = []
    for province_name, municipalities in CUBA_GEO.items():
        if province_norm and normalize_text(province_name) != province_norm:
            continue
        for item in municipalities:
            candidates.append((province_name, item["nombre"]))
    return candidates


def _best_match(text: str, candidates: Iterable[tuple[str, str]]) -> MunicipalityMatch:
    original_norm = normalize_text(text)
    best_province: Optional[str] = None
    best_municipality: Optional[str] = None
    best_score = 0.0

    for province_name, municipality_name in candidates:
        municipality_norm = normalize_text(municipality_name)
        if original_norm == municipality_norm:
            return MunicipalityMatch(
                texto_original=text,
                provincia_resuelta=province_name,
                municipio_resuelto=municipality_name,
                confianza=1.0,
                metodo_resolucion="exacto",
                requiere_revision=False,
            )

        score = SequenceMatcher(None, original_norm, municipality_norm).ratio()
        if original_norm and (original_norm in municipality_norm or municipality_norm in original_norm):
            score = max(score, min(len(original_norm), len(municipality_norm)) / max(len(original_norm), len(municipality_norm)))

        if score > best_score:
            best_score = score
            best_province = province_name
            best_municipality = municipality_name

    if best_score >= AUTO_THRESHOLD:
        return MunicipalityMatch(
            texto_original=text,
            provincia_resuelta=best_province,
            municipio_resuelto=best_municipality,
            confianza=round(best_score, 4),
            metodo_resolucion="similitud",
            requiere_revision=False,
        )

    if best_score >= REVIEW_THRESHOLD:
        return MunicipalityMatch(
            texto_original=text,
            provincia_resuelta=best_province,
            municipio_resuelto=best_municipality,
            confianza=round(best_score, 4),
            metodo_resolucion="similitud_revision",
            requiere_revision=True,
        )

    return MunicipalityMatch(
        texto_original=text,
        provincia_resuelta=None,
        municipio_resuelto=None,
        confianza=round(best_score, 4),
        metodo_resolucion="sin_coincidencia",
        requiere_revision=True,
    )


def normalize_service_territories(value: str | None, province_hint: str | None = None) -> List[MunicipalityMatch]:
    parts = split_territory_text(value)
    if not parts:
        return []

    candidates = official_municipalities(province_hint) or official_municipalities(None)
    matches: List[MunicipalityMatch] = []
    seen: set[tuple[str, Optional[str], Optional[str]]] = set()
    for part in parts:
        match = _best_match(part, candidates)
        key = (normalize_text(match.texto_original), match.provincia_resuelta, match.municipio_resuelto)
        if key in seen:
            continue
        seen.add(key)
        matches.append(match)
    return matches
