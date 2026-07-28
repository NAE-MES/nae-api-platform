from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app.cuba_geo import get_coordinates  # noqa: E402
from app.database import SessionLocal  # noqa: E402


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PLUS_CODE_ALPHABET = "23456789CFGHJMPQRVWX"
PLUS_CODE_SEPARATOR = "+"
PLUS_CODE_SEPARATOR_POSITION = 8
PAIR_RESOLUTIONS = (20.0, 1.0, 0.05, 0.0025, 0.000125)
PLUS_CODE_PATTERN = re.compile(r"\b([23456789CFGHJMPQRVWX]{2,8}\+[23456789CFGHJMPQRVWX]{2,})\b", re.IGNORECASE)


@dataclass
class PendingEntity:
    operational_respuesta_id: int
    entidad: str
    direccion_fisica: str | None
    provincia: str
    municipio: str


@dataclass
class GeocodeResult:
    lat: float | None
    lng: float | None
    confidence: float
    status: str
    display_name: str | None
    raw: dict[str, Any] | None
    source: str = "nominatim"


def compact(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def build_query(entity: PendingEntity) -> str:
    parts = [
        entity.entidad,
        entity.direccion_fisica,
        entity.municipio,
        entity.provincia,
        "Cuba",
    ]
    return ", ".join(part for part in (compact(item) for item in parts) if part)


def extract_plus_code(value: str | None) -> str | None:
    match = PLUS_CODE_PATTERN.search(compact(value).upper())
    return match.group(1) if match else None


def encode_plus_code(lat: float, lng: float, code_length: int = 10) -> str:
    lat = min(90.0, max(-90.0, lat)) + 90.0
    lng = (lng + 180.0) % 360.0
    code = []
    for resolution in PAIR_RESOLUTIONS:
        lat_digit = int(lat / resolution)
        lng_digit = int(lng / resolution)
        code.append(PLUS_CODE_ALPHABET[lat_digit])
        code.append(PLUS_CODE_ALPHABET[lng_digit])
        lat -= lat_digit * resolution
        lng -= lng_digit * resolution
        if len(code) >= code_length:
            break
    joined = "".join(code[:code_length])
    return f"{joined[:PLUS_CODE_SEPARATOR_POSITION]}+{joined[PLUS_CODE_SEPARATOR_POSITION:]}"


def decode_full_plus_code(code: str) -> tuple[float, float]:
    clean = code.upper().replace(PLUS_CODE_SEPARATOR, "")
    if len(clean) < 10:
        clean = clean.ljust(10, "2")

    lat = -90.0
    lng = -180.0
    last_resolution = PAIR_RESOLUTIONS[0]
    for pair_index, resolution in enumerate(PAIR_RESOLUTIONS):
        lat_char = clean[pair_index * 2]
        lng_char = clean[(pair_index * 2) + 1]
        lat += PLUS_CODE_ALPHABET.index(lat_char) * resolution
        lng += PLUS_CODE_ALPHABET.index(lng_char) * resolution
        last_resolution = resolution

    return lat + (last_resolution / 2), lng + (last_resolution / 2)


def recover_plus_code(short_code: str, reference_lat: float, reference_lng: float) -> str:
    code = short_code.upper()
    separator_position = code.index(PLUS_CODE_SEPARATOR)
    if separator_position >= PLUS_CODE_SEPARATOR_POSITION:
        return code

    padding_length = PLUS_CODE_SEPARATOR_POSITION - separator_position
    reference_code = encode_plus_code(reference_lat, reference_lng)
    recovered = reference_code[:padding_length] + code

    lat, lng = decode_full_plus_code(recovered)
    resolution = 20 ** (2 - (padding_length / 2))
    area_to_edge = resolution / 2

    if reference_lat + area_to_edge < lat and lat - resolution >= -90:
        lat -= resolution
    elif reference_lat - area_to_edge > lat and lat + resolution <= 90:
        lat += resolution

    if reference_lng + area_to_edge < lng:
        lng -= resolution
    elif reference_lng - area_to_edge > lng:
        lng += resolution

    return encode_plus_code(lat, lng)


def geocode_plus_code(entity: PendingEntity) -> GeocodeResult | None:
    plus_code = extract_plus_code(entity.direccion_fisica)
    if not plus_code:
        return None

    reference = get_coordinates(entity.provincia, entity.municipio)
    if not reference:
        return GeocodeResult(
            lat=None,
            lng=None,
            confidence=0,
            status="pendiente_revision",
            display_name=f"Plus Code sin municipio de referencia: {plus_code}",
            raw={"plus_code": plus_code},
            source="plus_code",
        )

    recovered = recover_plus_code(plus_code, reference["lat"], reference["lng"])
    lat, lng = decode_full_plus_code(recovered)
    return GeocodeResult(
        lat=round(lat, 7),
        lng=round(lng, 7),
        confidence=1.0,
        status="geocodificada",
        display_name=f"Plus Code {plus_code} recuperado como {recovered}",
        raw={
            "plus_code": plus_code,
            "recovered_plus_code": recovered,
            "reference": reference,
        },
        source="plus_code",
    )


def score_result(result: dict[str, Any], entity: PendingEntity) -> float:
    display_name = compact(result.get("display_name")).lower()
    importance = float(result.get("importance") or 0)
    score = min(max(importance, 0), 1)

    if compact(entity.provincia).lower() in display_name:
        score += 0.20
    if compact(entity.municipio).lower() in display_name:
        score += 0.25
    if "cuba" in display_name:
        score += 0.20

    place_type = compact(result.get("type")).lower()
    place_class = compact(result.get("class")).lower()
    if place_class in {"amenity", "office", "building", "shop", "tourism"}:
        score += 0.10
    if place_type in {"yes", "house", "building", "office", "university", "school", "government"}:
        score += 0.10

    return min(score, 1.0)


def geocode_nominatim(entity: PendingEntity, user_agent: str, timeout: int = 30) -> GeocodeResult:
    query = build_query(entity)
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": "1",
        "countrycodes": "cu",
        "addressdetails": "1",
    }
    request = Request(
        f"{NOMINATIM_URL}?{urlencode(params)}",
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not payload:
        return GeocodeResult(
            lat=None,
            lng=None,
            confidence=0,
            status="pendiente_revision",
            display_name=None,
            raw=None,
        )

    best = payload[0]
    confidence = score_result(best, entity)
    return GeocodeResult(
        lat=float(best["lat"]),
        lng=float(best["lon"]),
        confidence=round(confidence, 2),
        status="geocodificada",
        display_name=best.get("display_name"),
        raw=best,
    )


def geocode_entity(entity: PendingEntity, user_agent: str) -> GeocodeResult:
    plus_code_result = geocode_plus_code(entity)
    if plus_code_result is not None:
        return plus_code_result
    return geocode_nominatim(entity, user_agent=user_agent)


def fetch_pending_entities(limit: int) -> list[PendingEntity]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    op.id AS operational_respuesta_id,
                    COALESCE(m.entidad_nombre, op.nombre_institucion) AS entidad,
                    COALESCE(g.direccion_original, m.direccion_fisica) AS direccion_fisica,
                    p.nombre AS provincia,
                    mu.nombre AS municipio
                FROM operational.respuestas_encuesta op
                JOIN operational.provincias p ON p.id = op.provincia_id
                JOIN operational.municipios mu ON mu.id = op.municipio_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = op.id
                LEFT JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = op.id
                WHERE COALESCE(op.version_encuesta, '') = 'mapeo_estructuras_v1'
                  AND (
                      g.id IS NULL
                      OR g.estado NOT IN ('geocodificada', 'validada')
                      OR g.lat IS NULL
                      OR g.lng IS NULL
                  )
                ORDER BY op.id
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
        return [
            PendingEntity(
                operational_respuesta_id=row["operational_respuesta_id"],
                entidad=row["entidad"] or "Sin nombre",
                direccion_fisica=row["direccion_fisica"],
                provincia=row["provincia"],
                municipio=row["municipio"],
            )
            for row in rows
        ]
    finally:
        db.close()


def save_result(entity: PendingEntity, result: GeocodeResult, min_confidence: float) -> None:
    estado = "geocodificada" if result.lat is not None and result.confidence >= min_confidence else "pendiente_revision"
    observacion = result.display_name or "Sin resultado de geocodificación"
    raw_payload = json.dumps(result.raw or {}, ensure_ascii=False)

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO operational.geocodificacion_entidades (
                    operational_respuesta_id,
                    direccion_original,
                    provincia,
                    municipio,
                    lat,
                    lng,
                    fuente,
                    confianza,
                    estado,
                    observacion,
                    fecha_validacion,
                    validado_por
                )
                VALUES (
                    :operational_respuesta_id,
                    :direccion_original,
                    :provincia,
                    :municipio,
                    :lat,
                    :lng,
                    :fuente,
                    :confianza,
                    :estado,
                    :observacion,
                    CASE WHEN :estado = 'geocodificada' THEN NOW() ELSE NULL END,
                    CASE WHEN :estado = 'geocodificada' THEN :validado_por ELSE NULL END
                )
                ON CONFLICT (operational_respuesta_id)
                DO UPDATE SET
                    direccion_original = EXCLUDED.direccion_original,
                    provincia = EXCLUDED.provincia,
                    municipio = EXCLUDED.municipio,
                    lat = EXCLUDED.lat,
                    lng = EXCLUDED.lng,
                    fuente = EXCLUDED.fuente,
                    confianza = EXCLUDED.confianza,
                    estado = EXCLUDED.estado,
                    observacion = EXCLUDED.observacion || E'\nraw=' || :raw_payload,
                    fecha_validacion = EXCLUDED.fecha_validacion,
                    validado_por = EXCLUDED.validado_por,
                    updated_at = NOW()
                """
            ),
            {
                "operational_respuesta_id": entity.operational_respuesta_id,
                "direccion_original": entity.direccion_fisica,
                "provincia": entity.provincia,
                "municipio": entity.municipio,
                "lat": result.lat,
                "lng": result.lng,
                "fuente": result.source,
                "confianza": result.confidence,
                "estado": estado,
                "observacion": observacion,
                "validado_por": f"geocoder_{result.source}",
                "raw_payload": raw_payload,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Geocodifica entidades pendientes del mapa de apoyo NAE")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.2, help="Segundos entre consultas a Nominatim")
    parser.add_argument("--apply", action="store_true", help="Guarda resultados en BD. Sin esto solo muestra dry-run.")
    parser.add_argument("--min-confidence", type=float, default=0.65)
    parser.add_argument(
        "--user-agent",
        default="NAE Platform geocoder/1.0 (contacto: administracion-nae)",
        help="User-Agent requerido por Nominatim",
    )
    args = parser.parse_args()

    if args.limit < 1:
        print("El límite debe ser mayor que cero", file=sys.stderr)
        return 2

    try:
        entities = fetch_pending_entities(args.limit)
    except Exception as exc:
        print(f"No se pudieron leer entidades pendientes: {exc}", file=sys.stderr)
        return 1

    if not entities:
        print("No hay entidades pendientes de geocodificación.")
        return 0

    print(f"Entidades pendientes: {len(entities)}")
    print("Modo:", "APLICAR" if args.apply else "DRY-RUN")

    for index, entity in enumerate(entities, start=1):
        query = build_query(entity)
        print(f"\n[{index}/{len(entities)}] {entity.operational_respuesta_id} - {entity.entidad}")
        print(f"Query: {query}")

        try:
            result = geocode_entity(entity, user_agent=args.user_agent)
        except HTTPError as exc:
            print(f"HTTP error {exc.code}: {exc.reason}")
            continue
        except URLError as exc:
            print(f"Error de conexión: {exc.reason}")
            continue
        except Exception as exc:
            print(f"Error inesperado: {exc}")
            continue

        print(f"Fuente: {result.source}")
        print(f"Resultado: lat={result.lat} lng={result.lng} confianza={result.confidence}")
        print(f"Nombre: {result.display_name or 'Sin resultado'}")

        if args.apply:
            save_result(entity, result, min_confidence=args.min_confidence)
            print("Guardado en operational.geocodificacion_entidades")
        else:
            print("No guardado. Use --apply para escribir en BD.")

        if index < len(entities) and result.source == "nominatim":
            time.sleep(args.delay)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

