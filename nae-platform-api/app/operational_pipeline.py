from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import text

from app.database import SessionLocal
from app.mapeo_survey import (
    SCALAR_FIELDS as MAPEO_SCALAR_FIELDS,
    extract_espacios,
    extract_named_lists,
    extract_perfiles,
    extract_recomendaciones,
    extract_scalar_fields,
    extract_servicios,
)


from app.entity_resolution import (
    REVIEW_THRESHOLD,
    classify_entity_match,
    entity_similarity,
    normalize_entity_name,
)
from app.territory_normalization import MunicipalityMatch, normalize_service_territories

PIPELINE_NAME = "staging_to_operational"

MULTISELECT_FIELDS = {
    "3.2 Temas prioritarios de formación": ("respuestas_temas_formacion", "tema_formacion"),
    "3.2 Temas prioritarios de formación que necesita": ("respuestas_temas_formacion", "tema_formacion"),
    "5.3 Instituciones que participan en actividades formativas": (
        "respuestas_instituciones_participantes",
        "institucion_participante",
    ),
    "4.3 Instituciones que participan en actividades formativas": (
        "respuestas_instituciones_participantes",
        "institucion_participante",
    ),
    "5.4 Principales limitaciones": ("respuestas_limitaciones", "limitacion"),
    "4.4 Principales limitaciones que existen para desarrollar actividades formativas": (
        "respuestas_limitaciones",
        "limitacion",
    ),
    "5.1* Principales necesidades de los NAE en el municipio o territorio atendido": (
        "respuestas_temas_formacion",
        "tema_formacion",
    ),
    "6.2* Actores con los que coordina o podría coordinar su entidad para apoyar a los NAE": (
        "respuestas_instituciones_participantes",
        "institucion_participante",
    ),
    "7.1* Principales limitaciones que enfrenta la entidad para brindar servicios de apoyo a NAE": (
        "respuestas_limitaciones",
        "limitacion",
    ),
}

SCALAR_FIELD_ALIASES = {
    "mayoria_titulares_emprendimientos": [
        "3.5 Según Ud. ha observado, la mayoría de las personas dueñas o titulares de emprendimientos son:",
        "4.2 Mayoría de titulares de emprendimientos",
    ],
    "porcentaje_mujeres_directivas": [
        "3.6 Según su percepción, el porcentaje aproximado de mujeres en otros cargos directivos está entre:",
        "4.3 Porcentaje de mujeres en cargos directivos",
    ],
    "programas_mujeres_emprendedoras": [
        "3.7 En su municipio, conoce si se han desarrollado programas dirigidos a mujeres emprendedoras",
        "4.4 Programas dirigidos a mujeres emprendedoras",
    ],
    "descripcion_programa_mujeres": [
        "Describa brevemente",
        "4.4.1 Si respondió “Sí”, describa brevemente el programa",
    ],
    "nombre_institucion": [
        "0.1* Entidad a la que pertenece",
    ],
    "nivel_conocimiento_municipio": [
        "0.4* Nivel de conocimiento sobre los NAE en el municipio",
    ],
    "ambito_actuacion": [
        "1.4* Cobertura principal de actuación",
    ],
    "tipo_institucion": [
        "1.6* Tipo de entidad o estructura de apoyo",
    ],
    "nivel_involucramiento": [
        "1.8* Nivel de involucramiento en la prestación de servicios de apoyo a NAE",
    ],
    "principal_necesidad": [
        "5.2* Principal brecha del ecosistema de apoyo a NAE en el municipio",
    ],
    "mecanismos_coordinacion": [
        "6.1* ¿Existen mecanismos de coordinación institucional orientados al apoyo a NAE y estructuras de apoyo?",
    ],
}

DYNAMIC_SCALAR_PREFIXES = {
    "municipio": [
        "1.2* Municipio donde se ubica la entidad o estructura de apoyo",
    ],
}


@dataclass
class OperationResult:
    status: str
    raw_respuesta_id: int
    staging_respuesta_id: int
    operational_respuesta_id: Optional[int] = None
    observaciones: List[str] = field(default_factory=list)


def _resolve_provincia(db, provincia: str) -> int:
    provincia_id = db.execute(
        text("""
            INSERT INTO operational.provincias (nombre)
            VALUES (:nombre)
            ON CONFLICT (nombre)
            DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id
        """),
        {"nombre": provincia},
    ).scalar_one()
    return provincia_id


def _resolve_municipio(db, provincia_id: int, municipio: str) -> int:
    municipio_id = db.execute(
        text("""
            INSERT INTO operational.municipios (provincia_id, nombre)
            VALUES (:provincia_id, :nombre)
            ON CONFLICT (provincia_id, nombre)
            DO UPDATE SET nombre = EXCLUDED.nombre
            RETURNING id
        """),
        {"provincia_id": provincia_id, "nombre": municipio},
    ).scalar_one()
    return municipio_id


def _upsert_operational_response(db, row: Dict[str, Any], provincia_id: int, municipio_id: int) -> int:
    operational_id = db.execute(
        text("""
            INSERT INTO operational.respuestas_encuesta (
                staging_respuesta_id,
                raw_respuesta_id,
                id_respuesta_origen,
                formulario_origen,
                fecha_respuesta,
                consentimiento,
                version_encuesta,
                genero,
                nivel_conocimiento_municipio,
                nivel_instruccion,
                provincia_id,
                municipio_id,
                ambito_actuacion,
                tipo_institucion,
                nombre_institucion,
                nivel_involucramiento,
                nivel_capacitacion_formadores,
                mayoria_titulares_emprendimientos,
                porcentaje_mujeres_directivas,
                programas_mujeres_emprendedoras,
                descripcion_programa_mujeres,
                principal_necesidad,
                nivel_interes_gobierno,
                mecanismos_coordinacion,
                estado_validacion,
                created_at,
                updated_at
            )
            VALUES (
                :staging_respuesta_id,
                :raw_respuesta_id,
                :id_respuesta_origen,
                :formulario_origen,
                :fecha_respuesta,
                :consentimiento,
                :version_encuesta,
                :genero,
                :nivel_conocimiento_municipio,
                :nivel_instruccion,
                :provincia_id,
                :municipio_id,
                :ambito_actuacion,
                :tipo_institucion,
                :nombre_institucion,
                :nivel_involucramiento,
                :nivel_capacitacion_formadores,
                :mayoria_titulares_emprendimientos,
                :porcentaje_mujeres_directivas,
                :programas_mujeres_emprendedoras,
                :descripcion_programa_mujeres,
                :principal_necesidad,
                :nivel_interes_gobierno,
                :mecanismos_coordinacion,
                :estado_validacion,
                NOW(),
                NOW()
            )
            ON CONFLICT (staging_respuesta_id)
            DO UPDATE SET
                raw_respuesta_id = EXCLUDED.raw_respuesta_id,
                id_respuesta_origen = EXCLUDED.id_respuesta_origen,
                formulario_origen = EXCLUDED.formulario_origen,
                fecha_respuesta = EXCLUDED.fecha_respuesta,
                consentimiento = EXCLUDED.consentimiento,
                version_encuesta = EXCLUDED.version_encuesta,
                genero = EXCLUDED.genero,
                nivel_conocimiento_municipio = EXCLUDED.nivel_conocimiento_municipio,
                nivel_instruccion = EXCLUDED.nivel_instruccion,
                provincia_id = EXCLUDED.provincia_id,
                municipio_id = EXCLUDED.municipio_id,
                ambito_actuacion = EXCLUDED.ambito_actuacion,
                tipo_institucion = EXCLUDED.tipo_institucion,
                nombre_institucion = EXCLUDED.nombre_institucion,
                nivel_involucramiento = EXCLUDED.nivel_involucramiento,
                nivel_capacitacion_formadores = EXCLUDED.nivel_capacitacion_formadores,
                mayoria_titulares_emprendimientos = EXCLUDED.mayoria_titulares_emprendimientos,
                porcentaje_mujeres_directivas = EXCLUDED.porcentaje_mujeres_directivas,
                programas_mujeres_emprendedoras = EXCLUDED.programas_mujeres_emprendedoras,
                descripcion_programa_mujeres = EXCLUDED.descripcion_programa_mujeres,
                principal_necesidad = EXCLUDED.principal_necesidad,
                nivel_interes_gobierno = EXCLUDED.nivel_interes_gobierno,
                mecanismos_coordinacion = EXCLUDED.mecanismos_coordinacion,
                estado_validacion = EXCLUDED.estado_validacion,
                updated_at = NOW()
            RETURNING id
        """),
        {
            "staging_respuesta_id": row["id"],
            "raw_respuesta_id": row["raw_respuesta_id"],
            "id_respuesta_origen": row["id_respuesta_origen"],
            "formulario_origen": row["formulario_origen"],
            "fecha_respuesta": row["fecha_respuesta"],
            "consentimiento": row["consentimiento"],
            "version_encuesta": row["version_encuesta"],
            "genero": row["genero"],
            "nivel_conocimiento_municipio": row["nivel_conocimiento_municipio"],
            "nivel_instruccion": row["nivel_instruccion"],
            "provincia_id": provincia_id,
            "municipio_id": municipio_id,
            "ambito_actuacion": row["ambito_actuacion"],
            "tipo_institucion": row["tipo_institucion"],
            "nombre_institucion": row["nombre_institucion"],
            "nivel_involucramiento": row["nivel_involucramiento"],
            "nivel_capacitacion_formadores": row["nivel_capacitacion_formadores"],
            "mayoria_titulares_emprendimientos": row["mayoria_titulares_emprendimientos"],
            "porcentaje_mujeres_directivas": row["porcentaje_mujeres_directivas"],
            "programas_mujeres_emprendedoras": row["programas_mujeres_emprendedoras"],
            "descripcion_programa_mujeres": row["descripcion_programa_mujeres"],
            "principal_necesidad": row["principal_necesidad"],
            "nivel_interes_gobierno": row["nivel_interes_gobierno"],
            "mecanismos_coordinacion": row["mecanismos_coordinacion"],
            "estado_validacion": row["estado_validacion"],
        },
    ).scalar_one()
    return operational_id


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        items = value
    else:
        items = [value]

    normalized: List[str] = []
    for item in items:
        text_value = str(item).strip()
        if not text_value:
            continue
        if " | " in text_value:
            normalized.extend([part.strip() for part in text_value.split(" | ") if part.strip()])
        elif ", " in text_value:
            normalized.extend([part.strip() for part in text_value.split(", ") if part.strip()])
        else:
            normalized.append(text_value)
    return normalized


def _scalar_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return " | ".join(items) if items else None
    text_value = str(value).strip()
    return text_value or None


def _with_raw_scalar_fallbacks(row: Dict[str, Any], raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(row)
    for field_name, aliases in SCALAR_FIELD_ALIASES.items():
        if enriched.get(field_name):
            continue
        for alias in aliases:
            value = _scalar_value(raw_payload.get(alias))
            if value:
                enriched[field_name] = value
                break
    for field_name, prefixes in DYNAMIC_SCALAR_PREFIXES.items():
        if enriched.get(field_name):
            continue
        for prefix in prefixes:
            for key, raw_value in raw_payload.items():
                if key.startswith(prefix) and _scalar_value(raw_value):
                    value = _scalar_value(raw_value)
                    if value:
                        enriched[field_name] = value
                        break
            if enriched.get(field_name):
                break
    return enriched


def _extract_multiselects(raw_payload: Dict[str, Any]) -> Dict[str, List[str]]:
    extracted: Dict[str, List[str]] = {}
    for question, (table_name, column_name) in MULTISELECT_FIELDS.items():
        values = _coerce_list(raw_payload.get(question))
        if values or table_name not in extracted:
            extracted[table_name] = values
    return extracted


def _insert_child_values(db, operational_respuesta_id: int, table_name: str, column_name: str, values: List[str]) -> None:
    db.execute(
        text(f"""
            DELETE FROM operational.{table_name}
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )

    for value in values:
        db.execute(
            text(f"""
                INSERT INTO operational.{table_name} (
                    operational_respuesta_id,
                    {column_name}
                )
                VALUES (
                    :operational_respuesta_id,
                    :value
                )
                ON CONFLICT (operational_respuesta_id, {column_name})
                DO UPDATE SET
                    {column_name} = EXCLUDED.{column_name}
            """),
            {
                "operational_respuesta_id": operational_respuesta_id,
                "value": value,
            },
        )


def _upsert_mapeo_detail(db, operational_respuesta_id: int, raw_payload: Dict[str, Any]) -> None:
    values = extract_scalar_fields(raw_payload)
    columns = list(MAPEO_SCALAR_FIELDS.keys())
    insert_columns = ["operational_respuesta_id", *columns, "created_at", "updated_at"]
    value_tokens = [":operational_respuesta_id", *[f":{column}" for column in columns], "NOW()", "NOW()"]
    update_tokens = [f"{column} = EXCLUDED.{column}" for column in columns]
    query = f"""
        INSERT INTO operational.respuestas_mapeo_entidad (
            {", ".join(insert_columns)}
        )
        VALUES (
            {", ".join(value_tokens)}
        )
        ON CONFLICT (operational_respuesta_id)
        DO UPDATE SET
            {", ".join(update_tokens)},
            updated_at = NOW()
    """
    db.execute(
        text(query),
        {
            "operational_respuesta_id": operational_respuesta_id,
            **values,
        },
    )


def _replace_mapeo_list_values(
    db,
    operational_respuesta_id: int,
    table_name: str,
    column_name: str,
    values: List[str],
) -> None:
    db.execute(
        text(f"""
            DELETE FROM operational.{table_name}
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )
    for value in values:
        db.execute(
            text(f"""
                INSERT INTO operational.{table_name} (
                    operational_respuesta_id,
                    {column_name}
                )
                VALUES (
                    :operational_respuesta_id,
                    :value
                )
                ON CONFLICT (operational_respuesta_id, {column_name})
                DO UPDATE SET {column_name} = EXCLUDED.{column_name}
            """),
            {
                "operational_respuesta_id": operational_respuesta_id,
                "value": value,
            },
        )


def _replace_mapeo_servicios(db, operational_respuesta_id: int, rows: List[Dict[str, Any]]) -> None:
    db.execute(
        text("""
            DELETE FROM operational.respuestas_mapeo_servicios
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )
    for row in rows:
        if not row.get("ofrece_actualmente") and not row.get("requiere_fortalecer"):
            continue

        db.execute(
            text("""
                INSERT INTO operational.respuestas_mapeo_servicios (
                    operational_respuesta_id,
                    servicio,
                    ofrece_actualmente,
                    requiere_fortalecer
                )
                VALUES (
                    :operational_respuesta_id,
                    :servicio,
                    :ofrece_actualmente,
                    :requiere_fortalecer
                )
                ON CONFLICT (operational_respuesta_id, servicio)
                DO UPDATE SET
                    ofrece_actualmente = EXCLUDED.ofrece_actualmente,
                    requiere_fortalecer = EXCLUDED.requiere_fortalecer
            """),
            {"operational_respuesta_id": operational_respuesta_id, **row},
        )


def _replace_mapeo_espacios(db, operational_respuesta_id: int, rows: List[Dict[str, Any]]) -> None:
    db.execute(
        text("""
            DELETE FROM operational.respuestas_mapeo_espacios
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )
    for row in rows:
        db.execute(
            text("""
                INSERT INTO operational.respuestas_mapeo_espacios (
                    operational_respuesta_id,
                    orden,
                    espacio,
                    direccion_lugar,
                    aforo_aprox,
                    conectividad_tipo,
                    energia_alternativa,
                    aire_acondicionado,
                    uso_posible
                )
                VALUES (
                    :operational_respuesta_id,
                    :orden,
                    :espacio,
                    :direccion_lugar,
                    :aforo_aprox,
                    :conectividad_tipo,
                    :energia_alternativa,
                    :aire_acondicionado,
                    :uso_posible
                )
                ON CONFLICT (operational_respuesta_id, orden)
                DO UPDATE SET
                    espacio = EXCLUDED.espacio,
                    direccion_lugar = EXCLUDED.direccion_lugar,
                    aforo_aprox = EXCLUDED.aforo_aprox,
                    conectividad_tipo = EXCLUDED.conectividad_tipo,
                    energia_alternativa = EXCLUDED.energia_alternativa,
                    aire_acondicionado = EXCLUDED.aire_acondicionado,
                    uso_posible = EXCLUDED.uso_posible
            """),
            {"operational_respuesta_id": operational_respuesta_id, **row},
        )


def _replace_mapeo_perfiles(db, operational_respuesta_id: int, rows: List[Dict[str, Any]]) -> None:
    db.execute(
        text("""
            DELETE FROM operational.respuestas_mapeo_perfiles
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )
    for row in rows:
        db.execute(
            text("""
                INSERT INTO operational.respuestas_mapeo_perfiles (
                    operational_respuesta_id,
                    orden,
                    perfil
                )
                VALUES (
                    :operational_respuesta_id,
                    :orden,
                    :perfil
                )
                ON CONFLICT (operational_respuesta_id, orden)
                DO UPDATE SET perfil = EXCLUDED.perfil
            """),
            {"operational_respuesta_id": operational_respuesta_id, **row},
        )


def _replace_mapeo_recomendaciones(db, operational_respuesta_id: int, rows: List[Dict[str, Any]]) -> None:
    db.execute(
        text("""
            DELETE FROM operational.respuestas_mapeo_recomendaciones
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )
    for row in rows:
        db.execute(
            text("""
                INSERT INTO operational.respuestas_mapeo_recomendaciones (
                    operational_respuesta_id,
                    orden,
                    nombre_estructura,
                    tipo_actor,
                    servicios,
                    municipio_territorio,
                    contacto
                )
                VALUES (
                    :operational_respuesta_id,
                    :orden,
                    :nombre_estructura,
                    :tipo_actor,
                    :servicios,
                    :municipio_territorio,
                    :contacto
                )
                ON CONFLICT (operational_respuesta_id, orden)
                DO UPDATE SET
                    nombre_estructura = EXCLUDED.nombre_estructura,
                    tipo_actor = EXCLUDED.tipo_actor,
                    servicios = EXCLUDED.servicios,
                    municipio_territorio = EXCLUDED.municipio_territorio,
                    contacto = EXCLUDED.contacto
            """),
            {"operational_respuesta_id": operational_respuesta_id, **row},
        )


def _resolve_existing_municipio_id(db, province_name: Optional[str], municipality_name: Optional[str]) -> Optional[int]:
    if not province_name or not municipality_name:
        return None
    return db.execute(
        text("""
            SELECT mu.id
            FROM operational.municipios mu
            JOIN operational.provincias p ON p.id = mu.provincia_id
            WHERE p.nombre = :provincia
              AND mu.nombre = :municipio
            LIMIT 1
        """),
        {"provincia": province_name, "municipio": municipality_name},
    ).scalar_one_or_none()


def _replace_mapeo_territorios_servicio(
    db,
    operational_respuesta_id: int,
    matches: List[MunicipalityMatch],
) -> None:
    db.execute(
        text("""
            DELETE FROM operational.respuestas_mapeo_territorios_servicio
            WHERE operational_respuesta_id = :operational_respuesta_id
        """),
        {"operational_respuesta_id": operational_respuesta_id},
    )
    for match in matches:
        municipio_id = _resolve_existing_municipio_id(
            db,
            match.provincia_resuelta,
            match.municipio_resuelto,
        )
        db.execute(
            text("""
                INSERT INTO operational.respuestas_mapeo_territorios_servicio (
                    operational_respuesta_id,
                    texto_original,
                    provincia_resuelta,
                    municipio_resuelto,
                    municipio_id,
                    metodo_resolucion,
                    confianza,
                    requiere_revision
                )
                VALUES (
                    :operational_respuesta_id,
                    :texto_original,
                    :provincia_resuelta,
                    :municipio_resuelto,
                    :municipio_id,
                    :metodo_resolucion,
                    :confianza,
                    :requiere_revision
                )
                ON CONFLICT (operational_respuesta_id, texto_original, provincia_resuelta, municipio_resuelto)
                DO UPDATE SET
                    municipio_id = EXCLUDED.municipio_id,
                    metodo_resolucion = EXCLUDED.metodo_resolucion,
                    confianza = EXCLUDED.confianza,
                    requiere_revision = EXCLUDED.requiere_revision
            """),
            {
                "operational_respuesta_id": operational_respuesta_id,
                "texto_original": match.texto_original,
                "provincia_resuelta": match.provincia_resuelta,
                "municipio_resuelto": match.municipio_resuelto,
                "municipio_id": municipio_id,
                "metodo_resolucion": match.metodo_resolucion,
                "confianza": match.confianza,
                "requiere_revision": match.requiere_revision,
            },
        )


def _entity_resolution_tables_exist(db) -> bool:
    return bool(
        db.execute(
            text("SELECT to_regclass('operational.entidades_apoyo') IS NOT NULL")
        ).scalar()
    )


def _find_best_entity_candidate(
    db,
    nombre_reportado: str,
    provincia_id: int,
    municipio_id: int,
) -> tuple[Optional[int], Optional[str], float]:
    candidates = db.execute(
        text("""
            SELECT id, nombre_canonico
            FROM operational.entidades_apoyo
            WHERE provincia_id = :provincia_id
              AND municipio_id = :municipio_id
              AND estado_revision <> 'descartada'
        """),
        {"provincia_id": provincia_id, "municipio_id": municipio_id},
    ).mappings().all()

    best_id: Optional[int] = None
    best_name: Optional[str] = None
    best_score = 0.0
    for candidate in candidates:
        score = entity_similarity(nombre_reportado, candidate["nombre_canonico"])
        if score > best_score:
            best_id = candidate["id"]
            best_name = candidate["nombre_canonico"]
            best_score = score
    return best_id, best_name, best_score


def _upsert_canonical_entity(
    db,
    values: Dict[str, Any],
    provincia_id: int,
    municipio_id: int,
) -> int:
    nombre = values.get("entidad_nombre") or "Sin nombre"
    nombre_normalizado = normalize_entity_name(nombre)
    return db.execute(
        text("""
            INSERT INTO operational.entidades_apoyo (
                nombre_canonico,
                nombre_normalizado,
                provincia_id,
                municipio_id,
                tipo_estructura_apoyo,
                cobertura_principal,
                direccion_fisica,
                telefonos,
                correo_electronico,
                sitio_web,
                redes_sociales,
                persona_contacto_cargo,
                updated_at
            )
            VALUES (
                :nombre_canonico,
                :nombre_normalizado,
                :provincia_id,
                :municipio_id,
                :tipo_estructura_apoyo,
                :cobertura_principal,
                :direccion_fisica,
                :telefonos,
                :correo_electronico,
                :sitio_web,
                :redes_sociales,
                :persona_contacto_cargo,
                NOW()
            )
            ON CONFLICT (provincia_id, municipio_id, nombre_normalizado)
            DO UPDATE SET
                tipo_estructura_apoyo = COALESCE(EXCLUDED.tipo_estructura_apoyo, operational.entidades_apoyo.tipo_estructura_apoyo),
                cobertura_principal = COALESCE(EXCLUDED.cobertura_principal, operational.entidades_apoyo.cobertura_principal),
                direccion_fisica = COALESCE(EXCLUDED.direccion_fisica, operational.entidades_apoyo.direccion_fisica),
                telefonos = COALESCE(EXCLUDED.telefonos, operational.entidades_apoyo.telefonos),
                correo_electronico = COALESCE(EXCLUDED.correo_electronico, operational.entidades_apoyo.correo_electronico),
                sitio_web = COALESCE(EXCLUDED.sitio_web, operational.entidades_apoyo.sitio_web),
                redes_sociales = COALESCE(EXCLUDED.redes_sociales, operational.entidades_apoyo.redes_sociales),
                persona_contacto_cargo = COALESCE(EXCLUDED.persona_contacto_cargo, operational.entidades_apoyo.persona_contacto_cargo),
                updated_at = NOW()
            RETURNING id
        """),
        {
            "nombre_canonico": nombre,
            "nombre_normalizado": nombre_normalizado,
            "provincia_id": provincia_id,
            "municipio_id": municipio_id,
            "tipo_estructura_apoyo": values.get("tipo_estructura_apoyo"),
            "cobertura_principal": values.get("cobertura_principal"),
            "direccion_fisica": values.get("direccion_fisica"),
            "telefonos": values.get("telefonos"),
            "correo_electronico": values.get("correo_electronico"),
            "sitio_web": values.get("sitio_web"),
            "redes_sociales": values.get("redes_sociales"),
            "persona_contacto_cargo": values.get("persona_contacto_cargo"),
        },
    ).scalar_one()


def _upsert_entity_resolution(
    db,
    operational_respuesta_id: int,
    raw_payload: Dict[str, Any],
    provincia_id: int,
    municipio_id: int,
) -> None:
    if not _entity_resolution_tables_exist(db):
        return

    values = extract_scalar_fields(raw_payload)
    nombre_reportado = values.get("entidad_nombre")
    if not nombre_reportado:
        return

    best_id, best_name, best_score = _find_best_entity_candidate(
        db,
        nombre_reportado,
        provincia_id,
        municipio_id,
    )
    match = classify_entity_match(best_id, best_name, best_score)
    should_auto_link = match.entidad_apoyo_id is not None and not match.requiere_revision

    if should_auto_link:
        entidad_apoyo_id = match.entidad_apoyo_id
        entidad_sugerida_id = None
    else:
        entidad_apoyo_id = _upsert_canonical_entity(db, values, provincia_id, municipio_id)
        entidad_sugerida_id = best_id if best_score >= REVIEW_THRESHOLD else None

    requiere_revision = bool(match.requiere_revision)
    if entidad_sugerida_id and entidad_sugerida_id != entidad_apoyo_id:
        requiere_revision = True

    revision_action = None
    revision_suggested = None
    revision_approved = None
    if should_auto_link and match.metodo_resolucion in {"exacta", "similitud"}:
        revision_action = "auto_link"
        revision_suggested = match.nombre_canonico
        revision_approved = match.nombre_canonico
    elif entidad_sugerida_id and requiere_revision:
        revision_action = "auto_review"
        revision_suggested = match.nombre_canonico
        revision_approved = None

    db.execute(
        text("""
            INSERT INTO operational.respuestas_entidades_apoyo (
                entidad_apoyo_id,
                entidad_sugerida_id,
                operational_respuesta_id,
                nombre_reportado,
                nombre_normalizado,
                metodo_resolucion,
                confianza,
                requiere_revision,
                updated_at
            )
            VALUES (
                :entidad_apoyo_id,
                :entidad_sugerida_id,
                :operational_respuesta_id,
                :nombre_reportado,
                :nombre_normalizado,
                :metodo_resolucion,
                :confianza,
                :requiere_revision,
                NOW()
            )
            ON CONFLICT (operational_respuesta_id)
            DO UPDATE SET
                entidad_apoyo_id = EXCLUDED.entidad_apoyo_id,
                entidad_sugerida_id = EXCLUDED.entidad_sugerida_id,
                nombre_reportado = EXCLUDED.nombre_reportado,
                nombre_normalizado = EXCLUDED.nombre_normalizado,
                metodo_resolucion = EXCLUDED.metodo_resolucion,
                confianza = EXCLUDED.confianza,
                requiere_revision = EXCLUDED.requiere_revision,
                updated_at = NOW()
        """),
        {
            "entidad_apoyo_id": entidad_apoyo_id,
            "entidad_sugerida_id": entidad_sugerida_id,
            "operational_respuesta_id": operational_respuesta_id,
            "nombre_reportado": nombre_reportado,
            "nombre_normalizado": normalize_entity_name(nombre_reportado),
            "metodo_resolucion": match.metodo_resolucion,
            "confianza": match.confianza,
            "requiere_revision": requiere_revision,
        },
    )

    if revision_action:
        already_logged = db.execute(
            text("""
                SELECT 1
                FROM operational.revisiones_datos
                WHERE tipo_revision = 'entidad_duplicada'
                  AND tabla_origen = 'operational.respuestas_entidades_apoyo'
                  AND registro_origen_id = :registro_origen_id
                  AND accion = :accion
                LIMIT 1
            """),
            {"registro_origen_id": operational_respuesta_id, "accion": revision_action},
        ).scalar_one_or_none()
        if already_logged is None:
            db.execute(
                text("""
                    INSERT INTO operational.revisiones_datos (
                        tipo_revision,
                        tabla_origen,
                        registro_origen_id,
                        valor_original,
                        valor_sugerido,
                        valor_aprobado,
                        accion,
                        usuario,
                        observacion
                    )
                    VALUES (
                        'entidad_duplicada',
                        'operational.respuestas_entidades_apoyo',
                        :registro_origen_id,
                        :valor_original,
                        :valor_sugerido,
                        :valor_aprobado,
                        :accion,
                        'sistema',
                        :observacion
                    )
                """),
                {
                    "registro_origen_id": operational_respuesta_id,
                    "valor_original": nombre_reportado,
                    "valor_sugerido": revision_suggested,
                    "valor_aprobado": revision_approved,
                    "accion": revision_action,
                    "observacion": f"Resolucion automatica con confianza {match.confianza}",
                },
            )


def _upsert_mapeo_children(db, operational_respuesta_id: int, raw_payload: Dict[str, Any], provincia_contexto: Optional[str] = None) -> None:
    named_lists = extract_named_lists(raw_payload)
    _replace_mapeo_list_values(
        db,
        operational_respuesta_id,
        "respuestas_mapeo_tipos_nae",
        "tipo_nae",
        named_lists["tipos_nae"],
    )
    _replace_mapeo_list_values(
        db,
        operational_respuesta_id,
        "respuestas_mapeo_capacidades_tecnicas",
        "capacidad_tecnica",
        named_lists["capacidades_tecnicas"],
    )
    _replace_mapeo_list_values(
        db,
        operational_respuesta_id,
        "respuestas_mapeo_necesidades_fortalecimiento",
        "necesidad_fortalecimiento",
        named_lists["necesidades_fortalecimiento"],
    )
    scalar_fields = extract_scalar_fields(raw_payload)
    _replace_mapeo_territorios_servicio(
        db,
        operational_respuesta_id,
        normalize_service_territories(scalar_fields.get("territorios_servicio"), provincia_contexto),
    )
    _replace_mapeo_servicios(db, operational_respuesta_id, extract_servicios(raw_payload))
    _replace_mapeo_espacios(db, operational_respuesta_id, extract_espacios(raw_payload))
    _replace_mapeo_perfiles(db, operational_respuesta_id, extract_perfiles(raw_payload))
    _replace_mapeo_recomendaciones(db, operational_respuesta_id, extract_recomendaciones(raw_payload))


def process_staging_to_operational(limit: int = 100, only_pending: bool = False) -> Dict[str, Any]:
    db = SessionLocal()
    pipeline_run_id: Optional[int] = None
    stats = {
        "total": 0,
        "cargada": 0,
        "saltada": 0,
        "errores_registrados": 0,
    }

    try:
        pipeline_run_id = db.execute(
            text("""
                INSERT INTO control.ejecucion_pipeline (
                    tipo_pipeline,
                    fecha_inicio,
                    estado,
                    registros_procesados,
                    registros_error
                )
                VALUES (
                    :tipo_pipeline,
                    NOW(),
                    'en_ejecucion',
                    0,
                    0
                )
                RETURNING id
            """),
            {"tipo_pipeline": PIPELINE_NAME},
        ).scalar_one()
        db.commit()

        pending_filter = """
                  AND NOT EXISTS (
                      SELECT 1
                      FROM operational.respuestas_encuesta existing
                      WHERE existing.staging_respuesta_id = staging.respuestas_formulario.id
                  )
            """ if only_pending else ""

        staging_rows = db.execute(
            text(f"""
                SELECT id,
                       raw_respuesta_id,
                       id_respuesta_origen,
                       formulario_origen,
                       fecha_respuesta,
                       raw_payload,
                       consentimiento,
                       version_encuesta,
                       genero,
                       nivel_conocimiento_municipio,
                       nivel_instruccion,
                       provincia,
                       municipio,
                       ambito_actuacion,
                       tipo_institucion,
                       nombre_institucion,
                       nivel_involucramiento,
                       nivel_capacitacion_formadores,
                       mayoria_titulares_emprendimientos,
                       porcentaje_mujeres_directivas,
                       programas_mujeres_emprendedoras,
                       descripcion_programa_mujeres,
                       principal_necesidad,
                       nivel_interes_gobierno,
                       mecanismos_coordinacion,
                       estado_validacion
                FROM staging.respuestas_formulario
                WHERE estado_validacion IN ('validada', 'con_observaciones')
                {pending_filter}
                ORDER BY id
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

        for row in staging_rows:
            stats["total"] += 1
            raw_payload = row["raw_payload"] or {}
            if isinstance(raw_payload, str):
                raw_payload = json.loads(raw_payload)

            row_data = _with_raw_scalar_fallbacks(dict(row), raw_payload)
            provincia = row_data["provincia"]
            municipio = row_data["municipio"]

            if not provincia or not municipio:
                stats["saltada"] += 1
                stats["errores_registrados"] += 1
                db.execute(
                    text("""
                        INSERT INTO control.errores_carga (
                            respuesta_raw_id,
                            campo,
                            valor_recibido,
                            tipo_error,
                            descripcion,
                            estado_correccion
                        )
                        VALUES (
                            :respuesta_raw_id,
                            :campo,
                            :valor_recibido,
                            :tipo_error,
                            :descripcion,
                            'pendiente'
                        )
                    """),
                    {
                        "respuesta_raw_id": row_data["raw_respuesta_id"],
                        "campo": "ubicacion",
                        "valor_recibido": f"{provincia} / {municipio}",
                        "tipo_error": "operational_missing_reference",
                        "descripcion": "No se pudo resolver provincia o municipio",
                    },
                )
                continue

            provincia_id = _resolve_provincia(db, provincia)
            municipio_id = _resolve_municipio(db, provincia_id, municipio)
            operational_id = _upsert_operational_response(db, row_data, provincia_id, municipio_id)

            multiselects = _extract_multiselects(raw_payload)
            for table_name, values in multiselects.items():
                if table_name == "respuestas_temas_formacion":
                    _insert_child_values(db, operational_id, table_name, "tema_formacion", values)
                elif table_name == "respuestas_instituciones_participantes":
                    _insert_child_values(db, operational_id, table_name, "institucion_participante", values)
                elif table_name == "respuestas_limitaciones":
                    _insert_child_values(db, operational_id, table_name, "limitacion", values)

            if row_data.get("version_encuesta") == "mapeo_estructuras_v1":
                _upsert_mapeo_detail(db, operational_id, raw_payload)
                _upsert_mapeo_children(db, operational_id, raw_payload, provincia)
                _upsert_entity_resolution(db, operational_id, raw_payload, provincia_id, municipio_id)

            stats["cargada"] += 1
            db.execute(
                text("""
                    UPDATE raw.respuestas_formulario
                    SET estado = 'cargada_operational'
                    WHERE id = :raw_id
                """),
                {"raw_id": row_data["raw_respuesta_id"]},
            )

        if pipeline_run_id is not None:
            db.execute(
                text("""
                    UPDATE control.ejecucion_pipeline
                    SET fecha_fin = NOW(),
                        estado = 'completado',
                        registros_procesados = :registros_procesados,
                        registros_error = :registros_error
                    WHERE id = :id
                """),
                {
                    "id": pipeline_run_id,
                    "registros_procesados": stats["total"],
                    "registros_error": stats["errores_registrados"],
                },
            )

        db.commit()
        return {
            "status": "ok",
            "pipeline_run_id": pipeline_run_id,
            "stats": stats,
        }

    except Exception as exc:
        db.rollback()
        if pipeline_run_id is not None:
            try:
                db.execute(
                    text("""
                        UPDATE control.ejecucion_pipeline
                        SET fecha_fin = NOW(),
                            estado = 'fallido',
                            mensaje_error = :mensaje_error,
                            registros_procesados = :registros_procesados,
                            registros_error = :registros_error
                        WHERE id = :id
                    """),
                    {
                        "id": pipeline_run_id,
                        "mensaje_error": str(exc),
                        "registros_procesados": stats["total"],
                        "registros_error": stats["errores_registrados"],
                    },
                )
                db.commit()
            except Exception:
                db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    finally:
        db.close()
