from __future__ import annotations

import csv
import json
import textwrap
from io import StringIO
from html import escape
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.cuba_geo import CUBA_GEO, get_coordinates
from app.database import SessionLocal


def _build_filters(
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    clauses = ["1=1"]
    params: Dict[str, Any] = {}

    if provincia:
        clauses.append("t.provincia_nombre = :provincia")
        params["provincia"] = provincia

    if version_encuesta:
        clauses.append("COALESCE(f.version_encuesta, '1.0') = :version_encuesta")
        params["version_encuesta"] = version_encuesta

    if genero:
        clauses.append("COALESCE(g.genero, 'Sin dato') = :genero")
        params["genero"] = genero

    if tema:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM operational.respuestas_temas_formacion rt2
                WHERE rt2.operational_respuesta_id = f.operational_respuesta_id
                  AND rt2.tema_formacion = :tema
            )
            """
        )
        params["tema"] = tema

    return " AND ".join(clauses), params


def _fetch_lookup_options() -> Dict[str, List[str]]:
    db = SessionLocal()
    try:
        provincias = db.execute(
            text("""
                SELECT DISTINCT t.provincia_nombre
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                ORDER BY t.provincia_nombre
            """)
        ).scalars().all()

        versiones = db.execute(
            text("""
                SELECT DISTINCT COALESCE(version_encuesta, '1.0') AS version_encuesta
                FROM analytics.f_respuestas_encuesta
                ORDER BY version_encuesta DESC
            """)
        ).scalars().all()

        generos = db.execute(
            text("""
                SELECT DISTINCT COALESCE(g.genero, 'Sin dato') AS genero
                FROM analytics.f_respuestas_encuesta f
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                ORDER BY genero
            """)
        ).scalars().all()

        temas = db.execute(
            text("""
                SELECT DISTINCT rt.tema_formacion
                FROM operational.respuestas_temas_formacion rt
                ORDER BY rt.tema_formacion
            """)
        ).scalars().all()

        return {
            "provincias": list(provincias),
            "versiones": list(versiones),
            "generos": list(generos),
            "temas": list(temas),
        }
    finally:
        db.close()


def get_dashboard_data(
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        where_clause, params = _build_filters(provincia, version_encuesta, genero, tema)

        total = db.execute(
            text(f"""
                SELECT COUNT(*)
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                WHERE {where_clause}
            """),
            params,
        ).scalar_one()

        por_estado = db.execute(
            text(f"""
                SELECT e.estado_validacion AS label, COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                WHERE {where_clause}
                GROUP BY e.estado_validacion
                ORDER BY total DESC, label ASC
            """),
            params,
        ).mappings().all()

        por_provincia = db.execute(
            text(f"""
                SELECT t.provincia_nombre AS provincia,
                       t.municipio_nombre AS municipio,
                       COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                WHERE {where_clause}
                GROUP BY t.provincia_nombre, t.municipio_nombre
                ORDER BY total DESC, provincia ASC, municipio ASC
            """),
            params,
        ).mappings().all()

        por_genero = db.execute(
            text(f"""
                SELECT COALESCE(g.genero, 'Sin dato') AS label, COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                WHERE {where_clause}
                GROUP BY COALESCE(g.genero, 'Sin dato')
                ORDER BY total DESC, label ASC
            """),
            params,
        ).mappings().all()

        por_nivel_instruccion = db.execute(
            text(f"""
                SELECT COALESCE(rg.nivel_instruccion, 'Sin dato') AS label, COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                LEFT JOIN analytics.dim_respuesta_genero rg ON rg.id = f.respuesta_genero_id
                WHERE {where_clause}
                GROUP BY COALESCE(rg.nivel_instruccion, 'Sin dato')
                ORDER BY total DESC, label ASC
            """),
            params,
        ).mappings().all()

        temas_formacion = db.execute(
            text(f"""
                SELECT rt.tema_formacion AS label, COUNT(*)::int AS total
                FROM operational.respuestas_temas_formacion rt
                JOIN operational.respuestas_encuesta o ON o.id = rt.operational_respuesta_id
                JOIN analytics.f_respuestas_encuesta f ON f.operational_respuesta_id = o.id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                WHERE {where_clause}
                GROUP BY rt.tema_formacion
                ORDER BY total DESC, label ASC
                LIMIT 10
            """),
            params,
        ).mappings().all()

        limitaciones = db.execute(
            text(f"""
                SELECT rl.limitacion AS label, COUNT(*)::int AS total
                FROM operational.respuestas_limitaciones rl
                JOIN operational.respuestas_encuesta o ON o.id = rl.operational_respuesta_id
                JOIN analytics.f_respuestas_encuesta f ON f.operational_respuesta_id = o.id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                WHERE {where_clause}
                GROUP BY rl.limitacion
                ORDER BY total DESC, label ASC
                LIMIT 10
            """),
            params,
        ).mappings().all()

        instituciones = db.execute(
            text(f"""
                SELECT i.nombre_institucion AS label, COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_institucion i ON i.id = f.institucion_id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                WHERE {where_clause}
                GROUP BY i.nombre_institucion
                ORDER BY total DESC, label ASC
                LIMIT 10
            """),
            params,
        ).mappings().all()

        ultimas_respuestas = db.execute(
            text(f"""
                SELECT f.id,
                       COALESCE(f.version_encuesta, '1.0') AS version_encuesta,
                       f.fecha_respuesta,
                       f.consentimiento,
                       t.provincia_nombre,
                       t.municipio_nombre,
                       i.nombre_institucion,
                       e.estado_validacion,
                       COALESCE(g.genero, 'Sin dato') AS genero,
                       COALESCE(rg.nivel_instruccion, 'Sin dato') AS nivel_instruccion
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                JOIN analytics.dim_institucion i ON i.id = f.institucion_id
                JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                LEFT JOIN analytics.dim_respuesta_genero rg ON rg.id = f.respuesta_genero_id
                WHERE {where_clause}
                ORDER BY f.id DESC
                LIMIT :limit
            """),
            {**params, "limit": limit},
        ).mappings().all()

        return {
            "filters": {
                "provincia": provincia,
                "version_encuesta": version_encuesta,
                "genero": genero,
                "tema": tema,
            },
            "lookups": _fetch_lookup_options(),
            "total_respuestas": int(total),
            "por_estado": [dict(row) for row in por_estado],
            "por_provincia": [dict(row) for row in por_provincia],
            "por_genero": [dict(row) for row in por_genero],
            "por_nivel_instruccion": [dict(row) for row in por_nivel_instruccion],
            "temas_formacion": [dict(row) for row in temas_formacion],
            "limitaciones": [dict(row) for row in limitaciones],
            "instituciones": [dict(row) for row in instituciones],
            "ultimas_respuestas": [dict(row) for row in ultimas_respuestas],
        }
    finally:
        db.close()


def _bar_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p class='empty'>Sin datos</p>"
    max_total = max(int(row.get("total", 0) or 0) for row in rows) or 1
    items = []
    for row in rows:
        label = escape(str(row.get("label", "")))
        total = int(row.get("total", 0) or 0)
        width = max(6, int((total / max_total) * 100))
        items.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{label}</div>
              <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
              <div class="bar-value">{total}</div>
            </div>
            """
        )
    return "".join(items)


def _table(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape('' if row.get(header) is None else str(row.get(header)))}</td>" for header in headers)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows) or f"<tr><td colspan='{len(headers)}'>Sin datos</td></tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _table_with_links(
    headers: List[str],
    rows: List[Dict[str, Any]],
    link_column: str,
    link_prefix: str,
) -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = []
        for header in headers:
            value = "" if row.get(header) is None else str(row.get(header))
            if header == link_column and value:
                cells.append(
                    f"<td><a href='{escape(f'{link_prefix}{value}')}'>{escape(value)}</a></td>"
                )
            else:
                cells.append(f"<td>{escape(value)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    body = "".join(body_rows) or f"<tr><td colspan='{len(headers)}'>Sin datos</td></tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def get_response_detail(respuesta_id: int) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        core = db.execute(
            text("""
                SELECT f.id AS respuesta_id,
                       f.operational_respuesta_id,
                       op.raw_respuesta_id,
                       op.staging_respuesta_id,
                       op.id_respuesta_origen,
                       op.formulario_origen,
                       COALESCE(op.version_encuesta, f.version_encuesta, '1.0') AS version_encuesta,
                       op.fecha_respuesta,
                       t.provincia_nombre,
                       t.municipio_nombre,
                       i.tipo_institucion,
                       i.nombre_institucion,
                       e.estado_validacion,
                       COALESCE(g.genero, 'Sin dato') AS genero,
                       COALESCE(rg.nivel_instruccion, 'Sin dato') AS nivel_instruccion,
                       COALESCE(rg.nivel_conocimiento_municipio, 'Sin dato') AS nivel_conocimiento_municipio,
                       COALESCE(rg.mayoria_titulares_emprendimientos, 'Sin dato') AS mayoria_titulares_emprendimientos,
                       COALESCE(rg.porcentaje_mujeres_directivas, 'Sin dato') AS porcentaje_mujeres_directivas,
                       COALESCE(rg.programas_mujeres_emprendedoras, 'Sin dato') AS programas_mujeres_emprendedoras,
                       COALESCE(rg.descripcion_programa_mujeres, 'Sin dato') AS descripcion_programa_mujeres,
                       op.ambito_actuacion,
                       op.nivel_involucramiento,
                       op.nivel_capacitacion_formadores,
                       op.principal_necesidad,
                       op.nivel_interes_gobierno,
                       op.mecanismos_coordinacion,
                       COALESCE(m.direccion_fisica, 'Sin dato') AS direccion_fisica,
                       COALESCE(m.telefonos, 'Sin dato') AS telefonos,
                       COALESCE(m.correo_electronico, 'Sin dato') AS correo_electronico,
                       COALESCE(m.sitio_web, 'Sin dato') AS sitio_web,
                       COALESCE(m.redes_sociales, 'Sin dato') AS redes_sociales,
                       COALESCE(m.persona_contacto_cargo, 'Sin dato') AS persona_contacto_cargo,
                       COALESCE(m.territorios_servicio, 'Sin dato') AS territorios_servicio,
                       COALESCE(m.modalidad_atencion, 'Sin dato') AS modalidad_atencion,
                       COALESCE(m.presta_servicios_actualmente, 'Sin dato') AS presta_servicios_actualmente,
                       COALESCE(m.cantidad_nae_atendidos, 'Sin dato') AS cantidad_nae_atendidos,
                       COALESCE(m.antiguedad_servicios, 'Sin dato') AS antiguedad_servicios,
                       COALESCE(m.capacidad_ampliar_cobertura, 'Sin dato') AS capacidad_ampliar_cobertura,
                       COALESCE(m.frecuencia_servicios, 'Sin dato') AS frecuencia_servicios,
                       COALESCE(m.modalidad_pago_servicios, 'Sin dato') AS modalidad_pago_servicios,
                       COALESCE(m.metodologia_apoyo, 'Sin dato') AS metodologia_apoyo,
                       COALESCE(m.seguimiento_posterior, 'Sin dato') AS seguimiento_posterior,
                       COALESCE(m.servicios_mas_demandados, 'Sin dato') AS servicios_mas_demandados,
                       COALESCE(m.servicios_mejor_funcionan, 'Sin dato') AS servicios_mejor_funcionan,
                       COALESCE(m.servicios_insuficientes, 'Sin dato') AS servicios_insuficientes,
                       COALESCE(m.dispone_espacios_fisicos, 'Sin dato') AS dispone_espacios_fisicos,
                       COALESCE(m.disponibilidad_tecnologica, 'Sin dato') AS disponibilidad_tecnologica,
                       COALESCE(m.condiciones_conectividad, 'Sin dato') AS condiciones_conectividad,
                       COALESCE(m.autonomia_energetica, 'Sin dato') AS autonomia_energetica,
                       COALESCE(m.mejoras_infraestructura, 'Sin dato') AS mejoras_infraestructura,
                       COALESCE(m.actores_liderar_brecha, 'Sin dato') AS actores_liderar_brecha,
                       COALESCE(m.adecuacion_servicios, 'Sin dato') AS adecuacion_servicios,
                       COALESCE(m.comentarios_servicios, 'Sin dato') AS comentarios_servicios,
                       COALESCE(m.coordinador_articulacion, 'Sin dato') AS coordinador_articulacion,
                       COALESCE(m.actividades_conjuntas, 'Sin dato') AS actividades_conjuntas,
                       COALESCE(m.nivel_articulacion, 'Sin dato') AS nivel_articulacion,
                       COALESCE(m.capacidad_sostener_servicios, 'Sin dato') AS capacidad_sostener_servicios,
                       COALESCE(m.capacidad_actualizar_mapeo, 'Sin dato') AS capacidad_actualizar_mapeo,
                       COALESCE(m.apoyos_sostenibilidad, 'Sin dato') AS apoyos_sostenibilidad,
                       COALESCE(m.programas_especializados, 'Sin dato') AS programas_especializados,
                       COALESCE(m.descripcion_programas_especializados, 'Sin dato') AS descripcion_programas_especializados,
                       COALESCE(m.observaciones_finales, 'Sin dato') AS observaciones_finales
                FROM analytics.f_respuestas_encuesta f
                JOIN operational.respuestas_encuesta op ON op.id = f.operational_respuesta_id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                JOIN analytics.dim_institucion i ON i.id = f.institucion_id
                JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                LEFT JOIN analytics.dim_respuesta_genero rg ON rg.id = f.respuesta_genero_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = op.id
                WHERE f.id = :respuesta_id
            """),
            {"respuesta_id": respuesta_id},
        ).mappings().one_or_none()

        if core is None:
            return None

        temas = db.execute(
            text("""
                SELECT tema_formacion
                FROM operational.respuestas_temas_formacion
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY tema_formacion
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).scalars().all()

        instituciones_participantes = db.execute(
            text("""
                SELECT institucion_participante
                FROM operational.respuestas_instituciones_participantes
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY institucion_participante
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).scalars().all()

        limitaciones = db.execute(
            text("""
                SELECT limitacion
                FROM operational.respuestas_limitaciones
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY limitacion
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).scalars().all()

        tipos_nae = db.execute(
            text("""
                SELECT tipo_nae
                FROM operational.respuestas_mapeo_tipos_nae
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY tipo_nae
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).scalars().all()

        capacidades_tecnicas = db.execute(
            text("""
                SELECT capacidad_tecnica
                FROM operational.respuestas_mapeo_capacidades_tecnicas
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY capacidad_tecnica
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).scalars().all()

        necesidades_fortalecimiento = db.execute(
            text("""
                SELECT necesidad_fortalecimiento
                FROM operational.respuestas_mapeo_necesidades_fortalecimiento
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY necesidad_fortalecimiento
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).scalars().all()

        servicios_mapeo = db.execute(
            text("""
                SELECT servicio, ofrece_actualmente, requiere_fortalecer
                FROM operational.respuestas_mapeo_servicios
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY servicio
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).mappings().all()

        espacios = db.execute(
            text("""
                SELECT orden, espacio, direccion_lugar, aforo_aprox, conectividad_tipo,
                       energia_alternativa, aire_acondicionado, uso_posible
                FROM operational.respuestas_mapeo_espacios
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY orden
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).mappings().all()

        perfiles = db.execute(
            text("""
                SELECT orden, perfil
                FROM operational.respuestas_mapeo_perfiles
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY orden
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).mappings().all()

        recomendaciones = db.execute(
            text("""
                SELECT orden, nombre_estructura, tipo_actor, servicios, municipio_territorio, contacto
                FROM operational.respuestas_mapeo_recomendaciones
                WHERE operational_respuesta_id = :operational_respuesta_id
                ORDER BY orden
            """),
            {"operational_respuesta_id": core["operational_respuesta_id"]},
        ).mappings().all()

        previous_id = db.execute(
            text("""
                SELECT MAX(id)
                FROM analytics.f_respuestas_encuesta
                WHERE id < :respuesta_id
            """),
            {"respuesta_id": respuesta_id},
        ).scalar_one()

        next_id = db.execute(
            text("""
                SELECT MIN(id)
                FROM analytics.f_respuestas_encuesta
                WHERE id > :respuesta_id
            """),
            {"respuesta_id": respuesta_id},
        ).scalar_one()

        return {
            **dict(core),
            "temas_formacion": list(temas),
            "instituciones_participantes": list(instituciones_participantes),
            "limitaciones": list(limitaciones),
            "tipos_nae": list(tipos_nae),
            "capacidades_tecnicas": list(capacidades_tecnicas),
            "necesidades_fortalecimiento": list(necesidades_fortalecimiento),
            "servicios_mapeo": [dict(row) for row in servicios_mapeo],
            "espacios": [dict(row) for row in espacios],
            "perfiles": [dict(row) for row in perfiles],
            "recomendaciones": [dict(row) for row in recomendaciones],
            "previous_id": previous_id,
            "next_id": next_id,
        }
    finally:
        db.close()


def render_response_detail_html(data: Dict[str, Any]) -> str:
    def value(name: str) -> str:
        raw_value = data.get(name)
        return escape("" if raw_value is None else str(raw_value))

    def pill_list(items: List[str]) -> str:
        if not items:
            return "<p class='empty'>Sin datos</p>"
        pills = "".join(f"<span>{escape(item)}</span>" for item in items)
        return f"<div class='pills'>{pills}</div>"

    is_mapeo = data.get("version_encuesta") == "mapeo_estructuras_v1"
    identity_extra = "" if is_mapeo else f"""
            <div class="field"><span>Género</span><strong>{value("genero")}</strong></div>
            <div class="field"><span>Nivel de instrucción</span><strong>{value("nivel_instruccion")}</strong></div>
    """
    context_extra = "" if is_mapeo else f"""
            <div class="field"><span>Capacitación formadores</span><strong>{value("nivel_capacitacion_formadores")}</strong></div>
            <div class="field"><span>Interés gobierno</span><strong>{value("nivel_interes_gobierno")}</strong></div>
    """
    gender_section = "" if is_mapeo else f"""
        <section class="card">
          <div class="grid">
            <div class="field"><span>Mayoría titulares emprendimientos</span><strong>{value("mayoria_titulares_emprendimientos")}</strong></div>
            <div class="field"><span>Mujeres en cargos directivos</span><strong>{value("porcentaje_mujeres_directivas")}</strong></div>
            <div class="field"><span>Programas mujeres emprendedoras</span><strong>{value("programas_mujeres_emprendedoras")}</strong></div>
            <div class="field"><span>Descripción programa</span><strong>{value("descripcion_programa_mujeres")}</strong></div>
          </div>
        </section>
    """
    topics_title = "Necesidades principales" if is_mapeo else "Temas prioritarios"
    institutions_title = "Actores de coordinación" if is_mapeo else "Instituciones participantes"
    limitation_title = "Limitaciones de apoyo" if is_mapeo else "Limitaciones"
    servicios_rows = [
        {
            "Servicio": row.get("servicio"),
            "Ofrece": "Sí" if row.get("ofrece_actualmente") else "No",
            "Requiere fortalecer": "Sí" if row.get("requiere_fortalecer") else "No",
        }
        for row in data.get("servicios_mapeo", [])
    ]
    espacios_rows = [
        {
            "Espacio": row.get("espacio"),
            "Dirección": row.get("direccion_lugar"),
            "Aforo": row.get("aforo_aprox"),
            "Conectividad": row.get("conectividad_tipo"),
            "Energía": row.get("energia_alternativa"),
            "Uso": row.get("uso_posible"),
        }
        for row in data.get("espacios", [])
    ]
    perfiles_rows = [
        {"Orden": row.get("orden"), "Perfil": row.get("perfil")}
        for row in data.get("perfiles", [])
    ]
    recomendaciones_rows = [
        {
            "Nombre": row.get("nombre_estructura"),
            "Tipo": row.get("tipo_actor"),
            "Servicios": row.get("servicios"),
            "Municipio": row.get("municipio_territorio"),
            "Contacto": row.get("contacto"),
        }
        for row in data.get("recomendaciones", [])
    ]
    mapeo_sections = "" if not is_mapeo else f"""
        <section class="card">
          <h2>Contacto para mapa y directorio</h2>
          <div class="grid">
            <div class="field"><span>Dirección</span><strong>{value("direccion_fisica")}</strong></div>
            <div class="field"><span>Teléfono(s)</span><strong>{value("telefonos")}</strong></div>
            <div class="field"><span>Correo</span><strong>{value("correo_electronico")}</strong></div>
            <div class="field"><span>Sitio web</span><strong>{value("sitio_web")}</strong></div>
            <div class="field"><span>Redes sociales</span><strong>{value("redes_sociales")}</strong></div>
            <div class="field"><span>Persona de contacto</span><strong>{value("persona_contacto_cargo")}</strong></div>
          </div>
        </section>
        <section class="card">
          <h2>Cobertura y atención</h2>
          <div class="grid">
            <div class="field"><span>Territorios donde presta servicios</span><strong>{value("territorios_servicio")}</strong></div>
            <div class="field"><span>Modalidad de atención</span><strong>{value("modalidad_atencion")}</strong></div>
            <div class="field"><span>Presta servicios actualmente</span><strong>{value("presta_servicios_actualmente")}</strong></div>
            <div class="field"><span>NAE atendidos últimos 12 meses</span><strong>{value("cantidad_nae_atendidos")}</strong></div>
            <div class="field"><span>Antigüedad de servicios</span><strong>{value("antiguedad_servicios")}</strong></div>
            <div class="field"><span>Capacidad de ampliar cobertura</span><strong>{value("capacidad_ampliar_cobertura")}</strong></div>
          </div>
        </section>
        <section class="card">
          <h2>Tipos de NAE</h2>
          {pill_list(data.get("tipos_nae", []))}
        </section>
        <section class="card">
          <h2>Servicios de apoyo</h2>
          {_table(["Servicio", "Ofrece", "Requiere fortalecer"], servicios_rows)}
        </section>
        <section class="card">
          <h2>Funcionamiento de servicios</h2>
          <div class="grid">
            <div class="field"><span>Frecuencia</span><strong>{value("frecuencia_servicios")}</strong></div>
            <div class="field"><span>Modalidad de pago</span><strong>{value("modalidad_pago_servicios")}</strong></div>
            <div class="field"><span>Metodología</span><strong>{value("metodologia_apoyo")}</strong></div>
            <div class="field"><span>Seguimiento posterior</span><strong>{value("seguimiento_posterior")}</strong></div>
            <div class="field"><span>Más demandados</span><strong>{value("servicios_mas_demandados")}</strong></div>
            <div class="field"><span>Funcionan mejor</span><strong>{value("servicios_mejor_funcionan")}</strong></div>
            <div class="field"><span>Insuficientes</span><strong>{value("servicios_insuficientes")}</strong></div>
          </div>
        </section>
        <section class="card">
          <h2>Recursos e infraestructura</h2>
          <div class="grid">
            <div class="field"><span>Espacios físicos</span><strong>{value("dispone_espacios_fisicos")}</strong></div>
            <div class="field"><span>Tecnología</span><strong>{value("disponibilidad_tecnologica")}</strong></div>
            <div class="field"><span>Conectividad</span><strong>{value("condiciones_conectividad")}</strong></div>
            <div class="field"><span>Autonomía energética</span><strong>{value("autonomia_energetica")}</strong></div>
            <div class="field"><span>Mejoras necesarias</span><strong>{value("mejoras_infraestructura")}</strong></div>
          </div>
        </section>
        <section class="card">
          <h2>Espacios disponibles</h2>
          {_table(["Espacio", "Dirección", "Aforo", "Conectividad", "Energía", "Uso"], espacios_rows)}
        </section>
        <section class="card">
          <h2>Capacidades y perfiles</h2>
          {pill_list(data.get("capacidades_tecnicas", []))}
          <h3>Perfiles disponibles</h3>
          {_table(["Orden", "Perfil"], perfiles_rows)}
          <h3>Necesidades de fortalecimiento</h3>
          {pill_list(data.get("necesidades_fortalecimiento", []))}
        </section>
        <section class="card">
          <h2>Articulación y sostenibilidad</h2>
          <div class="grid">
            <div class="field"><span>Actores para liderar brecha</span><strong>{value("actores_liderar_brecha")}</strong></div>
            <div class="field"><span>Adecuación de servicios</span><strong>{value("adecuacion_servicios")}</strong></div>
            <div class="field"><span>Comentarios sobre servicios</span><strong>{value("comentarios_servicios")}</strong></div>
            <div class="field"><span>Coordinador articulación</span><strong>{value("coordinador_articulacion")}</strong></div>
            <div class="field"><span>Actividades conjuntas</span><strong>{value("actividades_conjuntas")}</strong></div>
            <div class="field"><span>Nivel articulación</span><strong>{value("nivel_articulacion")}</strong></div>
            <div class="field"><span>Sostenibilidad</span><strong>{value("capacidad_sostener_servicios")}</strong></div>
            <div class="field"><span>Actualización del mapa</span><strong>{value("capacidad_actualizar_mapeo")}</strong></div>
            <div class="field"><span>Apoyos necesarios</span><strong>{value("apoyos_sostenibilidad")}</strong></div>
          </div>
        </section>
        <section class="card">
          <h2>Inclusión y recomendaciones</h2>
          <div class="grid">
            <div class="field"><span>Programas especializados</span><strong>{value("programas_especializados")}</strong></div>
            <div class="field"><span>Descripción</span><strong>{value("descripcion_programas_especializados")}</strong></div>
            <div class="field"><span>Observaciones finales</span><strong>{value("observaciones_finales")}</strong></div>
          </div>
          <h3>Estructuras recomendadas</h3>
          {_table(["Nombre", "Tipo", "Servicios", "Municipio", "Contacto"], recomendaciones_rows)}
        </section>
    """

    return f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>NAE Platform - Respuesta {escape(str(data.get('respuesta_id')))}</title>
      <link rel="stylesheet" href="/prototype-assets/styles.css" />
      <style>
        :root {{
          --bg: #f5f7fb;
          --panel: #ffffff;
          --line: #d9e2ec;
          --text: #102a43;
          --muted: #627d98;
          --accent: #1d4ed8;
          --accent-deep: #0f3d73;
        }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); }}
        main.detail-main {{ display: grid; gap: 18px; }}
        .back {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 40px;
          width: fit-content;
          padding: 0 14px;
          border-radius: 8px;
          text-decoration: none;
          color: var(--text);
          background: #fff;
          border: 1px solid var(--line);
        }}
        .nav {{
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }}
        .nav a {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 40px;
          padding: 0 14px;
          border-radius: 8px;
          text-decoration: none;
          border: 1px solid var(--line);
          color: var(--text);
          background: #fff;
        }}
        .nav a.disabled {{
          pointer-events: none;
          color: #9fb3c8;
          background: #f8fafc;
        }}
        .card {{
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: 16px;
        }}
        .grid {{
          display: grid;
          grid-template-columns: 1fr;
          gap: 12px;
        }}
        @media(min-width: 900px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
        .field {{
          display: grid;
          gap: 4px;
        }}
        .field span {{
          font-size: 12px;
          color: var(--muted);
          text-transform: uppercase;
        }}
        .field strong {{
          font-size: 14px;
          font-weight: 600;
          word-break: break-word;
        }}
        .pills {{
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }}
        .pills span {{
          display: inline-flex;
          align-items: center;
          min-height: 32px;
          padding: 0 10px;
          border-radius: 999px;
          background: #dbeafe;
          color: #0f3d73;
          font-size: 13px;
        }}
        .empty {{ color: var(--muted); margin: 0; }}
      </style>
    </head>
      <body>
      <nav class="site-nav">
        <div class="nav-inner">
          <a class="nav-title" href="/"><strong>NAE</strong><span>Mapeo de Entidades de Apoyo</span></a>
          <div class="nav-links">
            <a href="/">Inicio</a>
            <a href="/encuesta">Encuesta</a>
            <a href="/mapa-apoyo">Mapa de apoyo</a>
            <a href="/documentacion">Documentación</a>
            <a class="active locked" href="/analitica">Analítica</a>
            <a class="locked" href="/admin/revision">Revisión</a>
            <a href="/logout">Salir</a>
          </div>
        </div>
      </nav>
      <img class="brand-strip" src="/images/banner-mapeo.jpeg" alt="NAE - Proyecto de cooperación internacional" />
      <main class="page detail-main">
        <header class="page-header">
          <div>
            <p class="eyebrow">Detalle de respuesta</p>
            <h1>Respuesta {value("respuesta_id")}</h1>
            <p class="lead">{value("provincia_nombre")} · {value("municipio_nombre")} · {value("nombre_institucion")}</p>
          </div>
        </header>
        <div class="nav">
          <a class="back" href="/analitica">Volver al panel</a>
          {"<a href='/respuestas/" + str(data["previous_id"]) + "'>Anterior</a>" if data.get("previous_id") else "<a class='disabled' href='#'>Anterior</a>"}
          {"<a href='/respuestas/" + str(data["next_id"]) + "'>Siguiente</a>" if data.get("next_id") else "<a class='disabled' href='#'>Siguiente</a>"}
        </div>
        <section class="card">
          <div class="grid">
            <div class="field"><span>Estado</span><strong>{value("estado_validacion")}</strong></div>
            <div class="field"><span>Versión</span><strong>{value("version_encuesta")}</strong></div>
            <div class="field"><span>Provincia</span><strong>{value("provincia_nombre")}</strong></div>
            <div class="field"><span>Municipio</span><strong>{value("municipio_nombre")}</strong></div>
            <div class="field"><span>Entidad</span><strong>{value("nombre_institucion")}</strong></div>
            <div class="field"><span>Tipo de estructura</span><strong>{value("tipo_institucion")}</strong></div>
            {identity_extra}
          </div>
        </section>
        <section class="card">
          <div class="grid">
            <div class="field"><span>Cobertura</span><strong>{value("ambito_actuacion")}</strong></div>
            <div class="field"><span>Nivel involucramiento</span><strong>{value("nivel_involucramiento")}</strong></div>
            {context_extra}
            <div class="field"><span>Principal brecha</span><strong>{value("principal_necesidad")}</strong></div>
            <div class="field"><span>Mecanismos coordinación</span><strong>{value("mecanismos_coordinacion")}</strong></div>
            <div class="field"><span>Conocimiento sobre NAE</span><strong>{value("nivel_conocimiento_municipio")}</strong></div>
          </div>
        </section>
        {gender_section}
        <section class="card">
          <h2>{topics_title}</h2>
          {pill_list(data.get("temas_formacion", []))}
        </section>
        <section class="card">
          <h2>{institutions_title}</h2>
          {pill_list(data.get("instituciones_participantes", []))}
        </section>
        <section class="card">
          <h2>{limitation_title}</h2>
          {pill_list(data.get("limitaciones", []))}
        </section>
        {mapeo_sections}
      </main>
    </body>
    </html>
    """



def render_dashboard_html(data: Dict[str, Any]) -> str:
    lookups = data["lookups"]
    selected = data["filters"]
    estado_totals = {row.get("label"): row.get("total", 0) for row in data["por_estado"]}
    validadas = estado_totals.get("validada", 0)
    observaciones = estado_totals.get("con_observaciones", 0)
    rechazadas = estado_totals.get("rechazada", 0)
    def option_list(values: List[str], selected_value: Optional[str]) -> str:
        options = ['<option value="">Todos</option>']
        for value in values:
            mark = " selected" if value == selected_value else ""
            options.append(f"<option value='{escape(value)}'{mark}>{escape(value)}</option>")
        return "".join(options)

    filters_html = f"""
        <form class="filters" method="get" action="/">
          <div class="filter-title">
            <strong>Filtros</strong>
            <span>Lectura operativa de respuestas procesadas</span>
          </div>
          <label><span>Provincia</span><select name="provincia">{option_list(lookups["provincias"], selected.get("provincia"))}</select></label>
          <label><span>Versión</span><select name="version_encuesta">{option_list(lookups["versiones"], selected.get("version_encuesta"))}</select></label>
          <label><span>Género</span><select name="genero">{option_list(lookups["generos"], selected.get("genero"))}</select></label>
          <label><span>Tema</span><select name="tema">{option_list(lookups["temas"], selected.get("tema"))}</select></label>
          <label><span>Límite</span><input type="number" name="limit" min="1" max="50" value="{escape(str(selected.get('limit') or 10))}" /></label>
          <div class="filter-actions">
            <button type="submit">Aplicar</button>
            <a href="/">Limpiar</a>
          </div>
        </form>
    """

    metrics = f"""
        <section class="kpis">
          <div class="kpi primary"><span>Total respuestas</span><strong>{data['total_respuestas']}</strong><small>Registros visibles en analytics</small></div>
          <div class="kpi"><span>Validadas</span><strong>{validadas}</strong><small>Sin observaciones de carga</small></div>
          <div class="kpi attention"><span>Con observaciones</span><strong>{observaciones}</strong><small>Revisar calidad del dato</small></div>
          <div class="kpi danger"><span>Rechazadas</span><strong>{rechazadas}</strong><small>No avanzan al análisis</small></div>
        </section>
    """

    html = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>NAE Platform - Panel</title>
      <style>
        :root {{
          --bg: #f4f6f9;
          --panel: #ffffff;
          --panel-soft: #f8fafc;
          --line: #d8dee8;
          --line-strong: #b8c2d1;
          --text: #172033;
          --muted: #66758a;
          --muted-strong: #46566f;
          --accent: #185abc;
          --accent-deep: #0b376d;
          --accent-soft: #e8f1ff;
          --ok: #18794e;
          --warn: #9a5b00;
          --danger: #b42318;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          margin: 0;
          font-family: Arial, Helvetica, sans-serif;
          background: var(--bg);
          color: var(--text);
          line-height: 1.45;
        }}
        header {{
          background: var(--accent-deep);
          color: #fff;
          border-bottom: 1px solid #06284f;
        }}
        .shell {{
          width: min(1440px, 100%);
          margin: 0 auto;
          padding: 0 24px;
        }}
        .topbar {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
          min-height: 72px;
        }}
        .brand {{
          display: flex;
          align-items: center;
          gap: 12px;
          min-width: 0;
        }}
        .brand-mark {{
          width: 38px;
          height: 38px;
          border-radius: 8px;
          display: grid;
          place-items: center;
          background: #ffffff;
          color: var(--accent-deep);
          font-weight: 700;
          letter-spacing: 0;
          flex: 0 0 auto;
        }}
        .brand h1 {{
          margin: 0;
          font-size: 20px;
          line-height: 1.1;
        }}
        .brand p {{
          margin: 3px 0 0;
          color: #c9d9ef;
          font-size: 13px;
        }}
        .header-meta {{
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }}
        .status-pill {{
          display: inline-flex;
          align-items: center;
          min-height: 32px;
          padding: 0 10px;
          border: 1px solid rgba(255,255,255,.22);
          border-radius: 8px;
          color: #eaf2ff;
          font-size: 12px;
          background: rgba(255,255,255,.08);
          white-space: nowrap;
        }}
        main {{
          padding: 22px 0 34px;
        }}
        .layout {{
          display: grid;
          gap: 16px;
        }}
        .filters {{
          display: grid;
          grid-template-columns: minmax(180px, 1.2fr) repeat(5, minmax(120px, 1fr)) auto;
          gap: 10px;
          align-items: end;
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: 14px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
        }}
        .filter-title {{
          display: grid;
          gap: 2px;
          align-self: center;
        }}
        .filter-title strong {{
          font-size: 14px;
        }}
        .filter-title span {{
          color: var(--muted);
          font-size: 12px;
        }}
        .filters label {{
          display: grid;
          gap: 5px;
          min-width: 0;
        }}
        .filters label span {{
          color: var(--muted-strong);
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0;
        }}
        .filters select,
        .filters input {{
          width: 100%;
          min-height: 38px;
          padding: 8px 10px;
          border: 1px solid var(--line-strong);
          border-radius: 8px;
          background: #fff;
          color: var(--text);
          font-size: 13px;
        }}
        .filters select:focus,
        .filters input:focus {{
          outline: 2px solid var(--accent-soft);
          border-color: var(--accent);
        }}
        .filter-actions {{
          display: flex;
          gap: 8px;
          align-items: end;
          white-space: nowrap;
        }}
        .filter-actions button,
        .filter-actions a {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 38px;
          padding: 0 12px;
          border-radius: 8px;
          text-decoration: none;
          font-size: 13px;
          font-weight: 700;
          border: 1px solid var(--line-strong);
          cursor: pointer;
        }}
        .filter-actions button {{
          background: var(--accent);
          color: #fff;
          border-color: var(--accent);
        }}
        .filter-actions a {{
          color: var(--text);
          background: #fff;
        }}
        .filter-actions .export-inline {{
          background: var(--accent-soft);
          color: var(--accent-deep);
          border-color: #bfd5f6;
        }}
        .kpis {{
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
        }}
        .kpi,
        .card {{
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 8px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
        }}
        .kpi {{
          min-height: 112px;
          padding: 15px;
          display: grid;
          align-content: space-between;
          border-left: 4px solid #9eb5d1;
        }}
        .kpi.primary {{ border-left-color: var(--accent); }}
        .kpi.attention {{ border-left-color: var(--warn); }}
        .kpi.danger {{ border-left-color: var(--danger); }}
        .kpi span {{
          color: var(--muted-strong);
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0;
        }}
        .kpi strong {{
          display: block;
          color: var(--text);
          font-size: 30px;
          line-height: 1;
          margin-top: 8px;
        }}
        .kpi small {{
          display: block;
          color: var(--muted);
          font-size: 12px;
          margin-top: 8px;
        }}
        .grid {{ display: grid; grid-template-columns: 1fr; gap: 18px; }}
        @media(min-width: 1100px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
        .card {{
          padding: 0;
          overflow: hidden;
        }}
        .card-head {{
          padding: 15px 16px 12px;
          border-bottom: 1px solid var(--line);
          background: var(--panel-soft);
        }}
        .card-body {{
          padding: 14px 16px 16px;
        }}
        .card h2 {{
          margin: 3px 0 0;
          font-size: 16px;
          line-height: 1.25;
        }}
        .section-lead {{
          margin: 0;
          color: var(--accent);
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0;
        }}
        .bar-row {{
          display: grid;
          grid-template-columns: minmax(140px, 1.3fr) minmax(160px, 2fr) 48px;
          gap: 10px;
          align-items: center;
          padding: 7px 0;
          border-bottom: 1px solid #edf1f6;
        }}
        .bar-row:last-child {{ border-bottom: 0; }}
        .bar-label, .bar-value {{ font-size: 13px; }}
        .bar-label {{ color: var(--text); }}
        .bar-value {{ text-align: right; color: var(--muted-strong); font-weight: 700; }}
        .bar-track {{ height: 10px; background: #edf2f7; border-radius: 999px; overflow: hidden; }}
        .bar-fill {{ height: 100%; background: var(--accent); border-radius: 999px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 9px 10px; border-bottom: 1px solid #e4e9f0; text-align: left; font-size: 13px; vertical-align: top; }}
        th {{
          background: #f7f9fc;
          color: var(--muted-strong);
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0;
        }}
        tr:hover td {{ background: #fbfdff; }}
        td a {{
          color: var(--accent);
          font-weight: 700;
          text-decoration: none;
        }}
        .empty {{ color: var(--muted); margin: 0; }}
        .wide {{ grid-column: 1 / -1; }}
        .subgrid {{ display: grid; grid-template-columns: 1fr; gap: 18px; }}
        @media(min-width: 1100px) {{ .subgrid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
        .bar-label, .bar-value, th, td {{ word-break: break-word; }}
        .card h2, .card .section-lead {{ overflow-wrap: anywhere; }}
        .table-wrap {{ overflow-x: auto; }}
        @media(max-width: 1180px) {{
          .filters {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
          .filter-title {{ grid-column: 1 / -1; }}
          .filter-actions {{ grid-column: 1 / -1; }}
          .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        @media(max-width: 720px) {{
          .shell {{ padding: 0 14px; }}
          .topbar {{ align-items: flex-start; flex-direction: column; padding: 14px 0; }}
          .header-meta {{ justify-content: flex-start; }}
          main {{ padding: 16px 0 26px; }}
          .filters {{ grid-template-columns: 1fr; }}
          .filter-actions {{ flex-wrap: wrap; }}
          .filter-actions button, .filter-actions a {{ width: 100%; }}
          .kpis {{ grid-template-columns: 1fr; }}
          .bar-row {{ grid-template-columns: minmax(0, 1.6fr) minmax(0, 2fr) 42px; }}
        }}
      </style>
    </head>
    <body>
      <header>
        <div class="shell">
          <div class="topbar">
            <div class="brand">
              <div class="brand-mark">NAE</div>
              <div>
                <h1>Panel operativo</h1>
                <p>Respuestas procesadas desde Google Forms hacia analytics.</p>
              </div>
            </div>
            <div class="header-meta">
              <span class="status-pill">Operational + Analytics</span>
              <span class="status-pill">{data['total_respuestas']} respuestas</span>
            </div>
          </div>
        </div>
      </header>
      <main>
        <div class="shell layout">
          {filters_html}
          {metrics}
          <section class="grid">
            <section class="card">
              <div class="card-head"><p class="section-lead">Calidad</p><h2>Estado de validación</h2></div>
              <div class="card-body">{_bar_rows(data["por_estado"])}</div>
            </section>
            <section class="card">
              <div class="card-head"><p class="section-lead">Territorio</p><h2>Provincias y municipios</h2></div>
              <div class="card-body table-wrap">{_table(["provincia", "municipio", "total"], data["por_provincia"])}</div>
            </section>
          </section>
          <section class="grid">
            <section class="card">
              <div class="card-head"><p class="section-lead">Perfil</p><h2>Género</h2></div>
              <div class="card-body">{_bar_rows(data["por_genero"])}</div>
            </section>
            <section class="card">
              <div class="card-head"><p class="section-lead">Perfil</p><h2>Nivel de instrucción</h2></div>
              <div class="card-body">{_bar_rows(data["por_nivel_instruccion"])}</div>
            </section>
          </section>
          <section class="grid">
            <section class="card">
              <div class="card-head"><p class="section-lead">Formación</p><h2>Temas prioritarios</h2></div>
              <div class="card-body">{_bar_rows(data["temas_formacion"])}</div>
            </section>
            <section class="card">
              <div class="card-head"><p class="section-lead">Restricciones</p><h2>Limitaciones reportadas</h2></div>
              <div class="card-body">{_bar_rows(data["limitaciones"])}</div>
            </section>
          </section>
          <section class="card wide">
            <div class="card-head"><p class="section-lead">Cobertura</p><h2>Instituciones más presentes</h2></div>
            <div class="card-body">{_bar_rows(data["instituciones"])}</div>
          </section>
          <section class="card wide">
            <div class="card-head"><p class="section-lead">Detalle</p><h2>Últimas respuestas</h2></div>
            <div class="card-body table-wrap">{_table_with_links(["id", "version_encuesta", "fecha_respuesta", "estado_validacion", "provincia_nombre", "municipio_nombre", "nombre_institucion", "genero", "nivel_instruccion"], data["ultimas_respuestas"], "id", "/respuestas/")}</div>
          </section>
        </div>
      </main>
    </body>
    </html>
    """
    return html


def build_resumen_csv(data: Dict[str, Any]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "version_encuesta",
        "fecha_respuesta",
        "estado_validacion",
        "provincia_nombre",
        "municipio_nombre",
        "nombre_institucion",
        "genero",
        "nivel_instruccion",
    ])
    for row in data["ultimas_respuestas"]:
        writer.writerow([
            row.get("id"),
            row.get("version_encuesta"),
            row.get("fecha_respuesta"),
            row.get("estado_validacion"),
            row.get("provincia_nombre"),
            row.get("municipio_nombre"),
            row.get("nombre_institucion"),
            row.get("genero"),
            row.get("nivel_instruccion"),
        ])
    return output.getvalue()


def get_support_entities(
    limit: int = 200,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
) -> Dict[str, Any]:
    clauses = ["COALESCE(op.version_encuesta, '') = 'mapeo_estructuras_v1'"]
    params: Dict[str, Any] = {"limit": limit}
    if provincia:
        clauses.append("p.nombre = :provincia")
        params["provincia"] = provincia
    if municipio:
        clauses.append("mu.nombre = :municipio")
        params["municipio"] = municipio
    if tipo:
        clauses.append("COALESCE(m.tipo_estructura_apoyo, op.tipo_institucion) = :tipo")
        params["tipo"] = tipo
    if q:
        clauses.append("""
            (
                COALESCE(m.entidad_nombre, op.nombre_institucion, '') ILIKE :q
                OR COALESCE(m.tipo_estructura_apoyo, op.tipo_institucion, '') ILIKE :q
                OR COALESCE(m.direccion_fisica, '') ILIKE :q
                OR COALESCE(m.persona_contacto_cargo, '') ILIKE :q
                OR COALESCE(m.territorios_servicio, '') ILIKE :q
                OR COALESCE(mu.nombre, '') ILIKE :q
                OR COALESCE(p.nombre, '') ILIKE :q
            )
        """)
        params["q"] = f"%{q}%"

    where_clause = " AND ".join(clauses)
    db = SessionLocal()
    try:
        has_entity_resolution = db.execute(
            text("SELECT to_regclass('operational.entidades_apoyo') IS NOT NULL")
        ).scalar()
        if has_entity_resolution:
            return _get_support_entities_canonical(db, limit, provincia, municipio, tipo, q)

        has_geocoding_table = db.execute(
            text("SELECT to_regclass('operational.geocodificacion_entidades') IS NOT NULL")
        ).scalar()
        geocoding_select = """
                       g.lat AS geocoding_lat,
                       g.lng AS geocoding_lng,
                       g.fuente AS geocoding_fuente,
                       g.confianza AS geocoding_confianza,
                       g.estado AS geocoding_estado,
                       g.fecha_validacion AS geocoding_fecha_validacion,
        """ if has_geocoding_table else """
                       NULL::numeric AS geocoding_lat,
                       NULL::numeric AS geocoding_lng,
                       NULL::text AS geocoding_fuente,
                       NULL::numeric AS geocoding_confianza,
                       NULL::text AS geocoding_estado,
                       NULL::timestamp AS geocoding_fecha_validacion,
        """
        geocoding_join = """
                LEFT JOIN operational.geocodificacion_entidades g
                    ON g.operational_respuesta_id = op.id
                   AND g.estado IN ('geocodificada', 'validada')
                   AND g.lat IS NOT NULL
                   AND g.lng IS NOT NULL
        """ if has_geocoding_table else ""

        rows = db.execute(
            text(f"""
                SELECT op.id AS operational_respuesta_id,
                       op.raw_respuesta_id,
                       op.id_respuesta_origen,
                       op.fecha_respuesta,
                       p.nombre AS provincia,
                       mu.nombre AS municipio,
                       COALESCE(m.entidad_nombre, op.nombre_institucion) AS entidad_nombre,
                       COALESCE(m.tipo_estructura_apoyo, op.tipo_institucion) AS tipo_estructura_apoyo,
                       COALESCE(m.cobertura_principal, op.ambito_actuacion) AS cobertura_principal,
                       m.modalidad_atencion,
                       m.direccion_fisica,
                       m.telefonos,
                       m.correo_electronico,
                       m.sitio_web,
                       m.redes_sociales,
                       m.persona_contacto_cargo,
                       m.territorios_servicio,
                       m.presta_servicios_actualmente,
                       m.capacidad_ampliar_cobertura,
                       m.condiciones_conectividad,
                       m.autonomia_energetica,
                       {geocoding_select}
                       (
                         SELECT STRING_AGG(s.servicio, ', ' ORDER BY s.servicio)
                         FROM operational.respuestas_mapeo_servicios s
                         WHERE s.operational_respuesta_id = op.id
                           AND (s.ofrece_actualmente = TRUE OR s.requiere_fortalecer = TRUE)
                       ) AS servicios,
                       op.estado_validacion
                FROM operational.respuestas_encuesta op
                JOIN operational.provincias p ON p.id = op.provincia_id
                JOIN operational.municipios mu ON mu.id = op.municipio_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = op.id
                {geocoding_join}
                WHERE {where_clause}
                ORDER BY p.nombre, mu.nombre, entidad_nombre
                LIMIT :limit
            """),
            params,
        ).mappings().all()

        lookups = db.execute(
            text("""
                SELECT DISTINCT p.nombre AS provincia,
                       mu.nombre AS municipio,
                       COALESCE(m.tipo_estructura_apoyo, op.tipo_institucion) AS tipo
                FROM operational.respuestas_encuesta op
                JOIN operational.provincias p ON p.id = op.provincia_id
                JOIN operational.municipios mu ON mu.id = op.municipio_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = op.id
                WHERE COALESCE(op.version_encuesta, '') = 'mapeo_estructuras_v1'
            """)
        ).mappings().all()

        return {
            "lookups": {
                "provincias": sorted({row["provincia"] for row in lookups if row["provincia"]}),
                "municipios": sorted({row["municipio"] for row in lookups if row["municipio"]}),
                "tipos": sorted({row["tipo"] for row in lookups if row["tipo"]}),
            },
            "filters": {
                "provincia": provincia,
                "municipio": municipio,
                "tipo": tipo,
                "q": q,
                "limit": limit,
            },
            "total": len(rows),
            "entidades": [_with_coordinates(dict(row)) for row in rows],
        }
    except ProgrammingError:
        db.rollback()
        return {
            "lookups": {"provincias": [], "municipios": [], "tipos": []},
            "filters": {"provincia": provincia, "municipio": municipio, "tipo": tipo, "q": q, "limit": limit},
            "total": 0,
            "entidades": [],
        }
    finally:
        db.close()


def _get_support_entities_canonical(
    db,
    limit: int = 200,
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    tipo: Optional[str] = None,
    q: Optional[str] = None,
) -> Dict[str, Any]:
    clauses = ["ea.estado_revision <> 'descartada'"]
    params: Dict[str, Any] = {"limit": limit}
    if provincia:
        clauses.append("p.nombre = :provincia")
        params["provincia"] = provincia
    if municipio:
        clauses.append("mu.nombre = :municipio")
        params["municipio"] = municipio
    if tipo:
        clauses.append("COALESCE(ea.tipo_estructura_apoyo, '') = :tipo")
        params["tipo"] = tipo
    if q:
        clauses.append("""
            (
                COALESCE(ea.nombre_canonico, '') ILIKE :q
                OR COALESCE(ea.tipo_estructura_apoyo, '') ILIKE :q
                OR COALESCE(ea.direccion_fisica, '') ILIKE :q
                OR COALESCE(ea.persona_contacto_cargo, '') ILIKE :q
                OR COALESCE(mu.nombre, '') ILIKE :q
                OR COALESCE(p.nombre, '') ILIKE :q
            )
        """)
        params["q"] = f"%{q}%"

    where_clause = " AND ".join(clauses)
    has_geocoding_table = db.execute(
        text("SELECT to_regclass('operational.geocodificacion_entidades') IS NOT NULL")
    ).scalar()
    geocoding_select = """
                       (
                         SELECT g.lat
                         FROM operational.respuestas_entidades_apoyo rel_geo
                         JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = rel_geo.operational_respuesta_id
                         WHERE rel_geo.entidad_apoyo_id = ea.id
                           AND g.estado IN ('geocodificada', 'validada')
                           AND g.lat IS NOT NULL
                           AND g.lng IS NOT NULL
                         ORDER BY g.confianza DESC NULLS LAST, g.fecha_validacion DESC NULLS LAST
                         LIMIT 1
                       ) AS geocoding_lat,
                       (
                         SELECT g.lng
                         FROM operational.respuestas_entidades_apoyo rel_geo
                         JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = rel_geo.operational_respuesta_id
                         WHERE rel_geo.entidad_apoyo_id = ea.id
                           AND g.estado IN ('geocodificada', 'validada')
                           AND g.lat IS NOT NULL
                           AND g.lng IS NOT NULL
                         ORDER BY g.confianza DESC NULLS LAST, g.fecha_validacion DESC NULLS LAST
                         LIMIT 1
                       ) AS geocoding_lng,
                       (
                         SELECT g.fuente
                         FROM operational.respuestas_entidades_apoyo rel_geo
                         JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = rel_geo.operational_respuesta_id
                         WHERE rel_geo.entidad_apoyo_id = ea.id
                           AND g.estado IN ('geocodificada', 'validada')
                           AND g.lat IS NOT NULL
                           AND g.lng IS NOT NULL
                         ORDER BY g.confianza DESC NULLS LAST, g.fecha_validacion DESC NULLS LAST
                         LIMIT 1
                       ) AS geocoding_fuente,
                       (
                         SELECT g.confianza
                         FROM operational.respuestas_entidades_apoyo rel_geo
                         JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = rel_geo.operational_respuesta_id
                         WHERE rel_geo.entidad_apoyo_id = ea.id
                           AND g.estado IN ('geocodificada', 'validada')
                           AND g.lat IS NOT NULL
                           AND g.lng IS NOT NULL
                         ORDER BY g.confianza DESC NULLS LAST, g.fecha_validacion DESC NULLS LAST
                         LIMIT 1
                       ) AS geocoding_confianza,
                       (
                         SELECT g.estado
                         FROM operational.respuestas_entidades_apoyo rel_geo
                         JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = rel_geo.operational_respuesta_id
                         WHERE rel_geo.entidad_apoyo_id = ea.id
                           AND g.estado IN ('geocodificada', 'validada')
                           AND g.lat IS NOT NULL
                           AND g.lng IS NOT NULL
                         ORDER BY g.confianza DESC NULLS LAST, g.fecha_validacion DESC NULLS LAST
                         LIMIT 1
                       ) AS geocoding_estado,
                       NULL::timestamp AS geocoding_fecha_validacion,
    """ if has_geocoding_table else """
                       NULL::numeric AS geocoding_lat,
                       NULL::numeric AS geocoding_lng,
                       NULL::text AS geocoding_fuente,
                       NULL::numeric AS geocoding_confianza,
                       NULL::text AS geocoding_estado,
                       NULL::timestamp AS geocoding_fecha_validacion,
    """

    rows = db.execute(
        text(f"""
            SELECT ea.id AS entidad_apoyo_id,
                   MIN(op.id) AS operational_respuesta_id,
                   MIN(op.raw_respuesta_id) AS raw_respuesta_id,
                   MIN(op.id_respuesta_origen) AS id_respuesta_origen,
                   MAX(op.fecha_respuesta) AS fecha_respuesta,
                   p.nombre AS provincia,
                   mu.nombre AS municipio,
                   ea.nombre_canonico AS entidad_nombre,
                   ea.tipo_estructura_apoyo,
                   ea.cobertura_principal,
                   NULL::text AS modalidad_atencion,
                   ea.direccion_fisica,
                   ea.telefonos,
                   ea.correo_electronico,
                   ea.sitio_web,
                   ea.redes_sociales,
                   ea.persona_contacto_cargo,
                   NULL::text AS territorios_servicio,
                   NULL::text AS presta_servicios_actualmente,
                   NULL::text AS capacidad_ampliar_cobertura,
                   NULL::text AS condiciones_conectividad,
                   NULL::text AS autonomia_energetica,
                   {geocoding_select}
                   (
                     SELECT STRING_AGG(DISTINCT s.servicio, ', ' ORDER BY s.servicio)
                     FROM operational.respuestas_entidades_apoyo rel_s
                     JOIN operational.respuestas_mapeo_servicios s ON s.operational_respuesta_id = rel_s.operational_respuesta_id
                     WHERE rel_s.entidad_apoyo_id = ea.id
                       AND (s.ofrece_actualmente = TRUE OR s.requiere_fortalecer = TRUE)
                   ) AS servicios,
                   CASE WHEN BOOL_OR(rel.requiere_revision) THEN 'requiere_revision' ELSE 'validada' END AS estado_validacion,
                   COUNT(DISTINCT op.id)::int AS respuestas_recibidas,
                   BOOL_OR(rel.requiere_revision) AS requiere_revision
            FROM operational.entidades_apoyo ea
            JOIN operational.provincias p ON p.id = ea.provincia_id
            JOIN operational.municipios mu ON mu.id = ea.municipio_id
            LEFT JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
            LEFT JOIN operational.respuestas_encuesta op ON op.id = rel.operational_respuesta_id
            WHERE {where_clause}
            GROUP BY ea.id, p.nombre, mu.nombre
            ORDER BY p.nombre, mu.nombre, ea.nombre_canonico
            LIMIT :limit
        """),
        params,
    ).mappings().all()

    lookups = db.execute(
        text("""
            SELECT DISTINCT p.nombre AS provincia,
                   mu.nombre AS municipio,
                   ea.tipo_estructura_apoyo AS tipo
            FROM operational.entidades_apoyo ea
            JOIN operational.provincias p ON p.id = ea.provincia_id
            JOIN operational.municipios mu ON mu.id = ea.municipio_id
            WHERE ea.estado_revision <> 'descartada'
        """)
    ).mappings().all()

    return {
        "lookups": {
            "provincias": sorted({row["provincia"] for row in lookups if row["provincia"]}),
            "municipios": sorted({row["municipio"] for row in lookups if row["municipio"]}),
            "tipos": sorted({row["tipo"] for row in lookups if row["tipo"]}),
        },
        "filters": {
            "provincia": provincia,
            "municipio": municipio,
            "tipo": tipo,
            "q": q,
            "limit": limit,
        },
        "total": len(rows),
        "entidades": [_with_coordinates(dict(row)) for row in rows],
    }


def _with_coordinates(row: Dict[str, Any]) -> Dict[str, Any]:
    if row.get("geocoding_lat") is not None and row.get("geocoding_lng") is not None:
        row.update({
            "lat": float(row["geocoding_lat"]),
            "lng": float(row["geocoding_lng"]),
            "coordinate_source": row.get("geocoding_fuente") or "geocodificacion",
            "coordinate_status": row.get("geocoding_estado") or "geocodificada",
            "coordinate_confidence": row.get("geocoding_confianza"),
        })
        return row

    coordinates = get_coordinates(row.get("provincia"), row.get("municipio"))
    if coordinates:
        row.update(coordinates)
        row.update({
            "coordinate_source": "municipio",
            "coordinate_status": "estimada",
            "coordinate_confidence": None,
        })
    else:
        row.update({
            "lat": None,
            "lng": None,
            "coordinate_source": None,
            "coordinate_status": "sin_coordenada",
            "coordinate_confidence": None,
        })
    return row


def build_support_entities_csv(data: Dict[str, Any]) -> str:
    output = StringIO()
    headers = [
        "operational_respuesta_id",
        "provincia",
        "municipio",
        "entidad_nombre",
        "tipo_estructura_apoyo",
        "cobertura_principal",
        "modalidad_atencion",
        "direccion_fisica",
        "telefonos",
        "correo_electronico",
        "sitio_web",
        "redes_sociales",
        "persona_contacto_cargo",
        "territorios_servicio",
        "presta_servicios_actualmente",
        "capacidad_ampliar_cobertura",
        "condiciones_conectividad",
        "autonomia_energetica",
        "servicios",
        "lat",
        "lng",
        "coordinate_source",
        "coordinate_status",
        "coordinate_confidence",
        "estado_validacion",
    ]
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for row in data.get("entidades", []):
        writer.writerow({key: row.get(key) for key in headers})
    return output.getvalue()


def _pdf_escape(value: Any) -> str:
    text_value = str(value or "")
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "-",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        text_value = text_value.replace(source, target)
    encoded = text_value.encode("cp1252", errors="replace").decode("cp1252")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_wrap(value: Any, width: int = 92) -> List[str]:
    return textwrap.wrap(str(value or "Sin dato"), width=width, break_long_words=True) or ["Sin dato"]


def build_support_entities_pdf(data: Dict[str, Any]) -> bytes:
    lines: List[tuple[str, int, bool]] = [
        ("Directorio de entidades de apoyo a los NAE", 16, True),
        ("Mapeo de Entidades de Apoyo", 10, False),
        ("", 10, False),
    ]

    rows = sorted(
        data.get("entidades", []),
        key=lambda row: (
            str(row.get("provincia") or ""),
            str(row.get("municipio") or ""),
            str(row.get("entidad_nombre") or ""),
        ),
    )
    current_group = None
    if not rows:
        lines.append(("No hay entidades para los filtros seleccionados.", 10, False))

    for row in rows:
        group = f"{row.get('provincia') or 'Sin provincia'} / {row.get('municipio') or 'Sin municipio'}"
        if group != current_group:
            lines.extend([("", 10, False), (group, 12, True)])
            current_group = group

        lines.append((str(row.get("entidad_nombre") or "Sin nombre"), 11, True))
        detail_parts = [
            f"Tipo: {row.get('tipo_estructura_apoyo') or 'Sin dato'}",
            f"Cobertura: {row.get('cobertura_principal') or 'Sin dato'}",
            f"Contacto: {row.get('persona_contacto_cargo') or 'Sin dato'}",
            f"Telefono: {row.get('telefonos') or 'Sin dato'}",
            f"Correo: {row.get('correo_electronico') or 'Sin dato'}",
            f"Direccion: {row.get('direccion_fisica') or 'Sin dato'}",
            f"Servicios: {row.get('servicios') or 'Sin servicios registrados'}",
        ]
        for part in detail_parts:
            for wrapped in _pdf_wrap(part):
                lines.append((wrapped, 9, False))
        lines.append(("", 9, False))

    page_width = 595
    page_height = 842
    margin_x = 46
    top_y = 795
    bottom_y = 46
    line_gap = 14
    pages: List[List[str]] = []
    page_commands: List[str] = []
    y = top_y

    def new_page() -> None:
        nonlocal page_commands, y
        if page_commands:
            pages.append(page_commands)
        page_commands = [
            "0.000 0.196 0.278 rg 0 792 595 50 re f",
            f"BT /F2 13 Tf {margin_x} 812 Td (NAE - Directorio de entidades de apoyo) Tj ET",
            "0.850 0.890 0.920 rg 46 786 503 1 re f",
        ]
        y = 766

    new_page()
    for text_value, size, bold in lines:
        if y < bottom_y:
            new_page()
        if not text_value:
            y -= line_gap // 2
            continue
        font = "F2" if bold else "F1"
        color = "0.063 0.165 0.263" if bold else "0.180 0.235 0.294"
        page_commands.append(f"{color} rg BT /{font} {size} Tf {margin_x} {y} Td ({_pdf_escape(text_value)}) Tj ET")
        y -= line_gap if size <= 10 else line_gap + 3
    if page_commands:
        pages.append(page_commands)

    objects: List[bytes] = []

    def add_object(content: bytes) -> int:
        objects.append(content)
        return len(objects)

    font_regular = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_bold = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    page_ids: List[int] = []
    for commands in pages:
        stream = "\n".join(commands).encode("cp1252", errors="replace")
        content_id = add_object(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = add_object(
            (
                f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii"))
    for index, obj in enumerate(objects):
        if b"/Parent 0 0 R" in obj:
            objects[index] = obj.replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode("ascii"))
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def get_admin_review_data() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        has_entity_resolution = db.execute(
            text("SELECT to_regclass('operational.respuestas_entidades_apoyo') IS NOT NULL")
        ).scalar()

        territories = db.execute(
            text("""
                SELECT ts.id,
                       ts.operational_respuesta_id,
                       ts.texto_original,
                       ts.provincia_resuelta,
                       ts.municipio_resuelto,
                       ts.metodo_resolucion,
                       ts.confianza,
                       ts.requiere_revision,
                       p.nombre AS provincia_contexto,
                       mu.nombre AS municipio_contexto,
                       op.nombre_institucion
                FROM operational.respuestas_mapeo_territorios_servicio ts
                JOIN operational.respuestas_encuesta op ON op.id = ts.operational_respuesta_id
                LEFT JOIN operational.provincias p ON p.id = op.provincia_id
                LEFT JOIN operational.municipios mu ON mu.id = op.municipio_id
                WHERE ts.requiere_revision = TRUE
                ORDER BY ts.confianza DESC, ts.id DESC
                LIMIT 100
            """)
        ).mappings().all()

        municipalities = [
            {"provincia": province_name, "municipio": item["nombre"]}
            for province_name, items in CUBA_GEO.items()
            for item in items
        ]

        entity_reviews = []
        if has_entity_resolution:
            entity_reviews = db.execute(
                text("""
                    SELECT rel.id,
                           rel.operational_respuesta_id,
                           rel.nombre_reportado,
                           rel.metodo_resolucion,
                           rel.confianza,
                           actual.id AS entidad_actual_id,
                           actual.nombre_canonico AS entidad_actual,
                           sugerida.id AS entidad_sugerida_id,
                           sugerida.nombre_canonico AS entidad_sugerida,
                           p.nombre AS provincia,
                           mu.nombre AS municipio
                    FROM operational.respuestas_entidades_apoyo rel
                    JOIN operational.entidades_apoyo actual ON actual.id = rel.entidad_apoyo_id
                    LEFT JOIN operational.entidades_apoyo sugerida ON sugerida.id = rel.entidad_sugerida_id
                    LEFT JOIN operational.provincias p ON p.id = actual.provincia_id
                    LEFT JOIN operational.municipios mu ON mu.id = actual.municipio_id
                    WHERE rel.requiere_revision = TRUE
                    ORDER BY rel.confianza DESC, rel.id DESC
                    LIMIT 100
                """)
            ).mappings().all()

        recent_decisions = []
        if has_entity_resolution:
            recent_decisions = db.execute(
                text("""
                    SELECT tipo_revision,
                           valor_original,
                           valor_sugerido,
                           valor_aprobado,
                           accion,
                           usuario,
                           created_at
                    FROM operational.revisiones_datos
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
            ).mappings().all()

        return {
            "territories": [dict(row) for row in territories],
            "municipalities": municipalities,
            "entity_reviews": [dict(row) for row in entity_reviews],
            "recent_decisions": [dict(row) for row in recent_decisions],
        }
    except ProgrammingError:
        db.rollback()
        return {"territories": [], "municipalities": [], "entity_reviews": [], "recent_decisions": []}
    finally:
        db.close()


def render_admin_review_html(data: Dict[str, Any]) -> str:
    municipalities = data.get("municipalities", [])

    def municipality_options(selected_name: Optional[str] = None) -> str:
        options = ['<option value="">Seleccionar municipio</option>']
        for row in municipalities:
            label = f"{row.get('provincia')} / {row.get('municipio')}"
            selected = " selected" if selected_name and row.get("municipio") == selected_name else ""
            value = f"{row.get('provincia')}||{row.get('municipio')}"
            options.append(f"<option value='{escape(value, quote=True)}'{selected}>{escape(label)}</option>")
        return "".join(options)

    territory_rows = []
    for row in data.get("territories", []):
        suggested = " / ".join(
            value for value in [row.get("provincia_resuelta"), row.get("municipio_resuelto")] if value
        ) or "Sin sugerencia"
        territory_rows.append(f"""
          <article class="review-card">
            <div>
              <p class="eyebrow">Territorio pendiente</p>
              <h3>{escape(str(row.get('texto_original') or 'Sin texto'))}</h3>
              <p>{escape(str(row.get('nombre_institucion') or 'Sin entidad'))} · {escape(str(row.get('provincia_contexto') or 'Sin provincia'))}</p>
              <p><strong>Sugerencia:</strong> {escape(suggested)} · <strong>Confianza:</strong> {escape(str(row.get('confianza') or '0'))}</p>
            </div>
            <form method="post" action="/admin/revision/territorios/{row.get('id')}">
              <label class="field"><span>Municipio correcto</span><select name="municipio_key">{municipality_options(row.get('municipio_resuelto'))}</select></label>
              <label class="field"><span>Observación</span><input name="observacion" placeholder="Opcional" /></label>
              <div class="actions">
                <button class="button primary" name="action" value="resolve" type="submit">Guardar municipio</button>
                <button class="button secondary" name="action" value="descriptive" type="submit">Es territorio descriptivo</button>
              </div>
            </form>
          </article>
        """)
    if not territory_rows:
        territory_rows.append("<article class='card pad'><h3>Sin territorios pendientes</h3><p>No hay municipios o territorios por revisar.</p></article>")

    entity_rows = []
    for row in data.get("entity_reviews", []):
        entity_rows.append(f"""
          <article class="review-card">
            <div>
              <p class="eyebrow">Posible duplicado</p>
              <h3>{escape(str(row.get('nombre_reportado') or 'Sin nombre'))}</h3>
              <p>{escape(str(row.get('provincia') or 'Sin provincia'))} · {escape(str(row.get('municipio') or 'Sin municipio'))}</p>
              <p><strong>Entidad actual:</strong> {escape(str(row.get('entidad_actual') or 'Sin dato'))}</p>
              <p><strong>Sugerida:</strong> {escape(str(row.get('entidad_sugerida') or 'Sin sugerencia'))} · <strong>Confianza:</strong> {escape(str(row.get('confianza') or '0'))}</p>
            </div>
            <form method="post" action="/admin/revision/entidades/{row.get('id')}">
              <label class="field"><span>Observación</span><input name="observacion" placeholder="Opcional" /></label>
              <div class="actions">
                <button class="button primary" name="action" value="merge" type="submit">Unir con sugerida</button>
                <button class="button secondary" name="action" value="separate" type="submit">Mantener separada</button>
              </div>
            </form>
          </article>
        """)
    if not entity_rows:
        entity_rows.append("<article class='card pad'><h3>Sin duplicados pendientes</h3><p>No hay entidades que requieran decisión manual.</p></article>")

    decision_rows = []
    for row in data.get("recent_decisions", []):
        decision_rows.append(f"""
          <tr>
            <td>{escape(str(row.get('created_at') or ''))}</td>
            <td>{escape(str(row.get('tipo_revision') or ''))}</td>
            <td>{escape(str(row.get('accion') or ''))}</td>
            <td>{escape(str(row.get('valor_original') or ''))}</td>
            <td>{escape(str(row.get('valor_aprobado') or ''))}</td>
          </tr>
        """)
    if not decision_rows:
        decision_rows.append("<tr><td colspan='5'>Aún no hay decisiones registradas.</td></tr>")

    return f"""
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>NAE - Revisión de datos</title>
    <link rel="stylesheet" href="/prototype-assets/styles.css" />
    <style>
      .review-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; align-items: start; }}
      .review-stack {{ display: grid; gap: 12px; }}
      .review-card {{ display: grid; gap: 14px; border: 1px solid var(--line); border-radius: 8px; background: #fff; box-shadow: var(--shadow); padding: 16px; }}
      .review-card h3 {{ margin-bottom: 6px; color: var(--nae-navy); }}
      .review-card p {{ margin-bottom: 6px; color: #435466; }}
      .review-card form {{ display: grid; gap: 10px; }}
      .review-card .actions {{ justify-content: flex-start; }}
      .review-history {{ margin-top: 22px; }}
      @media (max-width: 900px) {{ .review-grid {{ grid-template-columns: 1fr; }} }}
    </style>
  </head>
  <body>
    <nav class="site-nav">
      <div class="nav-inner">
        <a class="nav-title" href="/"><strong>NAE</strong><span>Mapeo de Entidades de Apoyo</span></a>
        <div class="nav-links">
          <a href="/">Inicio</a>
          <a href="/mapa-apoyo">Mapa de apoyo</a>
          <a href="/analitica">Analítica</a>
          <a class="active" href="/admin/revision">Revisión</a>
          <a href="/logout">Salir</a>
        </div>
      </div>
    </nav>
    <img class="brand-strip" src="/images/banner-mapeo.jpeg" alt="NAE - Proyecto de cooperación internacional" />
    <main class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Administración</p>
          <h1>Revisión de datos pendientes</h1>
          <p class="lead">Corrección controlada de municipios escritos de forma ambigua y consolidación de entidades posiblemente duplicadas.</p>
        </div>
      </header>
      <section class="review-grid">
        <div>
          <h2>Territorios</h2>
          <div class="review-stack">{''.join(territory_rows)}</div>
        </div>
        <div>
          <h2>Entidades duplicadas</h2>
          <div class="review-stack">{''.join(entity_rows)}</div>
        </div>
      </section>
      <section class="card pad review-history">
        <h2>Historial reciente</h2>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Fecha</th><th>Tipo</th><th>Acción</th><th>Original</th><th>Aprobado</th></tr></thead>
            <tbody>{''.join(decision_rows)}</tbody>
          </table>
        </div>
      </section>
    </main>
  </body>
</html>
    """


def render_support_entities_html(data: Dict[str, Any]) -> str:
    lookups = data.get("lookups", {})
    selected = data.get("filters", {})
    pdf_params = {
        key: value
        for key, value in {
            "provincia": selected.get("provincia"),
            "municipio": selected.get("municipio"),
            "tipo": selected.get("tipo"),
            "q": selected.get("q"),
            "limit": selected.get("limit") or 200,
        }.items()
        if value not in (None, "")
    }
    pdf_url = "/api/v1/entidades-apoyo.pdf"
    if pdf_params:
        pdf_url = f"{pdf_url}?{urlencode(pdf_params)}"


    def option_list(values: List[str], selected_value: Optional[str]) -> str:
        options = ['<option value="">Todos</option>']
        for value in values:
            mark = " selected" if value == selected_value else ""
            options.append(f"<option value='{escape(value)}'{mark}>{escape(value)}</option>")
        return "".join(options)

    def entity_cards() -> str:
        rows = data.get("entidades", [])
        if not rows:
            return "<div class='empty-state'>No hay entidades para los filtros seleccionados.</div>"
        cards = []
        for row in rows:
            title = escape(str(row.get("entidad_nombre") or "Sin nombre"))
            tipo = escape(str(row.get("tipo_estructura_apoyo") or "Sin tipo"))
            location = escape(f"{row.get('provincia') or ''} / {row.get('municipio') or ''}")
            cobertura = escape(str(row.get("cobertura_principal") or "Sin dato"))
            contacto = escape(str(row.get("persona_contacto_cargo") or "Sin dato"))
            telefonos = escape(str(row.get("telefonos") or "Sin dato"))
            correo = escape(str(row.get("correo_electronico") or "Sin dato"))
            direccion = escape(str(row.get("direccion_fisica") or "Sin dato"))
            servicios = escape(str(row.get("servicios") or "Sin servicios registrados"))
            cards.append(f"""
              <article class="entity-card">
                <div class="entity-head">
                  <div>
                    <h3>{title}</h3>
                    <p>{location}</p>
                  </div>
                  <span>{tipo}</span>
                </div>
                <dl>
                  <div><dt>Cobertura</dt><dd>{cobertura}</dd></div>
                  <div><dt>Contacto</dt><dd>{contacto}</dd></div>
                  <div><dt>Teléfono</dt><dd>{telefonos}</dd></div>
                  <div><dt>Correo</dt><dd>{correo}</dd></div>
                  <div><dt>Dirección</dt><dd>{direccion}</dd></div>
                  <div class="wide"><dt>Servicios</dt><dd>{servicios}</dd></div>
                </dl>
              </article>
            """)
        return "".join(cards)

    return f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>NAE Platform - Mapa de apoyo</title>
      <style>
        :root {{
          --bg:#f4f6f9; --panel:#fff; --line:#d8dee8; --text:#172033; --muted:#66758a;
          --accent:#185abc; --accent-deep:#0b376d; --accent-soft:#e8f1ff; --ok:#18794e;
        }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; font-family:Arial, Helvetica, sans-serif; background:var(--bg); color:var(--text); line-height:1.45; }}
        header {{ background:var(--accent-deep); color:#fff; border-bottom:1px solid #06284f; }}
        .shell {{ width:min(1280px, 100%); margin:0 auto; padding:0 22px; }}
        .topbar {{ min-height:70px; display:flex; justify-content:space-between; align-items:center; gap:16px; }}
        .brand strong {{ display:block; font-size:19px; }}
        .brand span {{ display:block; color:#c9d9ef; font-size:13px; margin-top:2px; }}
        .nav {{ display:flex; gap:10px; flex-wrap:wrap; }}
        .nav a {{ color:#eaf2ff; text-decoration:none; border:1px solid rgba(255,255,255,.22); border-radius:8px; padding:8px 10px; font-size:13px; }}
        .nav a.active {{ background:#fff; color:var(--accent-deep); }}
        main {{ padding:24px 0 36px; }}
        .hero {{ display:grid; gap:18px; grid-template-columns:minmax(0, 1.1fr) minmax(360px, .9fr); align-items:stretch; margin-bottom:16px; }}
        .intro, .map-panel, .filters, .entity-card, .summary-card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 1px 2px rgba(15,23,42,.04); }}
        .intro {{ padding:20px; display:grid; gap:8px; }}
        .eyebrow {{ margin:0; color:var(--accent); font-weight:700; font-size:12px; text-transform:uppercase; }}
        h1 {{ margin:0; font-size:30px; line-height:1.12; letter-spacing:0; }}
        .lead {{ margin:0; color:var(--muted); font-size:15px; max-width:760px; }}
        .summary {{ display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:10px; margin-top:10px; }}
        .summary-card {{ padding:12px; }}
        .summary-card span {{ display:block; color:var(--muted); font-size:12px; }}
        .summary-card strong {{ display:block; margin-top:4px; font-size:24px; }}
        .map-panel {{ min-height:300px; padding:18px; position:relative; overflow:hidden; }}
        .cuba-svg {{ width:100%; height:260px; display:block; }}
        .cuba-shape {{ fill:#dbeafe; stroke:#185abc; stroke-width:3; }}
        .province-line, .sea-line {{ fill:none; stroke:#7aa3e5; stroke-width:2; opacity:.7; }}
        .pin {{ position:absolute; width:12px; height:12px; border-radius:999px; background:var(--ok); border:2px solid #fff; box-shadow:0 0 0 4px rgba(24,121,78,.18); }}
        .pin.p1 {{ left:31%; top:48%; }} .pin.p2 {{ left:48%; top:43%; }} .pin.p3 {{ left:67%; top:39%; }} .pin.p4 {{ left:79%; top:35%; }}
        .filters {{ padding:14px; display:grid; grid-template-columns:repeat(5, minmax(0,1fr)) auto; gap:10px; align-items:end; margin-bottom:16px; }}
        label {{ display:grid; gap:5px; color:#46566f; font-size:11px; font-weight:700; text-transform:uppercase; }}
        select, input {{ min-height:38px; width:100%; border:1px solid #b8c2d1; border-radius:8px; background:#fff; color:var(--text); padding:8px 10px; font-size:13px; }}
        button, .button {{ min-height:38px; display:inline-flex; align-items:center; justify-content:center; border-radius:8px; padding:0 12px; border:1px solid #b8c2d1; background:var(--accent); color:#fff; text-decoration:none; font-weight:700; font-size:13px; cursor:pointer; }}
        .button.secondary {{ background:#fff; color:var(--text); }}
        .filter-actions {{ display:flex; gap:8px; }}
        .entities {{ display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:14px; }}
        .entity-card {{ padding:16px; display:grid; gap:14px; }}
        .entity-head {{ display:flex; justify-content:space-between; gap:14px; align-items:start; }}
        .entity-head h3 {{ margin:0; font-size:18px; line-height:1.2; }}
        .entity-head p {{ margin:5px 0 0; color:var(--muted); font-size:13px; }}
        .entity-head span {{ flex:0 0 auto; max-width:210px; border-radius:999px; background:var(--accent-soft); color:var(--accent-deep); padding:6px 9px; font-size:12px; font-weight:700; text-align:right; }}
        dl {{ margin:0; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
        dl div.wide {{ grid-column:1 / -1; }}
        dt {{ color:var(--muted); font-size:11px; font-weight:700; text-transform:uppercase; }}
        dd {{ margin:3px 0 0; font-size:13px; word-break:break-word; }}
        .empty-state {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:18px; color:var(--muted); }}
        @media (max-width: 980px) {{ .hero, .entities, .filters {{ grid-template-columns:1fr; }} .filter-actions {{ justify-content:flex-start; }} }}
      </style>
    </head>
    <body>
      <header>
        <div class="shell topbar">
          <div class="brand"><strong>NAE</strong><span>Mapeo de Entidades de Apoyo</span></div>
          <nav class="nav"><a href="/mapa-apoyo" class="active">Mapa de apoyo</a><a href="/">Analítica</a><a href="/api/v1/entidades-apoyo">API</a></nav>
        </div>
      </header>
      <main class="shell">
        <section class="hero">
          <div class="intro">
            <p class="eyebrow">Consulta pública</p>
            <h1>Mapa de estructuras de apoyo a los NAE</h1>
            <p class="lead">Directorio territorial de entidades, capacidades y contactos identificados mediante la encuesta nacional de mapeo.</p>
            <div class="summary">
              <div class="summary-card"><span>Entidades visibles</span><strong>{data.get('total', 0)}</strong></div>
              <div class="summary-card"><span>Provincias</span><strong>{len(lookups.get('provincias', []))}</strong></div>
              <div class="summary-card"><span>Tipos</span><strong>{len(lookups.get('tipos', []))}</strong></div>
            </div>
          </div>
          <div class="map-panel">
            <svg class="cuba-svg" viewBox="0 0 900 420" role="img" aria-label="Mapa aproximado de Cuba">
              <path class="sea-line" d="M65 235 C160 165 260 160 370 165 C520 171 650 120 815 155" />
              <path class="cuba-shape" d="M70 236 C100 214 132 198 168 188 C208 177 254 177 303 184 C349 190 390 187 428 172 C462 159 496 143 532 139 C569 135 604 149 638 151 C676 153 713 132 756 128 C790 125 825 136 845 158 C817 170 783 174 746 173 C707 172 674 183 641 196 C603 211 560 211 519 202 C482 194 449 198 414 213 C377 229 338 236 294 232 C246 228 210 234 174 251 C136 268 100 264 70 236Z" />
              <path class="province-line" d="M202 187 C210 205 210 223 205 242" />
              <path class="province-line" d="M328 187 C335 201 333 218 326 232" />
              <path class="province-line" d="M454 162 C462 176 462 191 454 207" />
              <path class="province-line" d="M588 145 C594 162 593 181 584 200" />
              <path class="province-line" d="M720 143 C724 154 723 166 718 177" />
            </svg>
            <span class="pin p1"></span><span class="pin p2"></span><span class="pin p3"></span><span class="pin p4"></span>
          </div>
        </section>
        <form class="filters" method="get" action="/mapa-apoyo">
          <label>Provincia<select name="provincia">{option_list(lookups.get('provincias', []), selected.get('provincia'))}</select></label>
          <label>Municipio<select name="municipio">{option_list(lookups.get('municipios', []), selected.get('municipio'))}</select></label>
          <label>Tipo<select name="tipo">{option_list(lookups.get('tipos', []), selected.get('tipo'))}</select></label>
          <label>Búsqueda<input name="q" value="{escape(str(selected.get('q') or ''))}" placeholder="Entidad, contacto, territorio" /></label>
          <label>Límite<input type="number" min="1" max="1000" name="limit" value="{escape(str(selected.get('limit') or 200))}" /></label>
          <div class="filter-actions"><button type="submit">Aplicar</button><a class="button secondary" href="/mapa-apoyo">Limpiar</a></div>
        </form>
        <section class="entities">{entity_cards()}</section>
      </main>
    </body>
    </html>
    """

def render_support_entities_html(data: Dict[str, Any]) -> str:
    lookups = data.get("lookups", {})
    selected = data.get("filters", {})
    pdf_params = {
        key: value
        for key, value in {
            "provincia": selected.get("provincia"),
            "municipio": selected.get("municipio"),
            "tipo": selected.get("tipo"),
            "q": selected.get("q"),
            "limit": selected.get("limit") or 200,
        }.items()
        if value not in (None, "")
    }
    pdf_url = "/api/v1/entidades-apoyo.pdf"
    if pdf_params:
        pdf_url = f"{pdf_url}?{urlencode(pdf_params)}"

    def option_list(values: List[str], selected_value: Optional[str]) -> str:
        options = ['<option value="">Todos</option>']
        for item in values:
            mark = " selected" if item == selected_value else ""
            options.append(f"<option value='{escape(str(item))}'{mark}>{escape(str(item))}</option>")
        return "".join(options)

    rows = data.get("entidades", [])
    map_entities = []
    for row in rows:
        lat = row.get("lat")
        lng = row.get("lng")
        if lat is None or lng is None:
            continue
        visible_services = str(row.get("servicios") or "").strip() or "Sin servicios registrados"
        map_entities.append({
            "id": row.get("operational_respuesta_id"),
            "name": row.get("entidad_nombre") or "Sin nombre",
            "type": row.get("tipo_estructura_apoyo") or "Sin tipo",
            "province": row.get("provincia") or "Sin provincia",
            "municipality": row.get("municipio") or "Sin municipio",
            "coverage": row.get("cobertura_principal") or "Sin dato",
            "services": visible_services,
            "lat": float(lat),
            "lng": float(lng),
            "source": row.get("coordinate_source") or "municipio",
            "status": row.get("coordinate_status") or "estimada",
            "confidence": str(row.get("coordinate_confidence") or ""),
        })
    map_entities_json = json.dumps(map_entities, ensure_ascii=False).replace("</", "<\\/")

    entity_cards = []
    for row in rows:
        entity_cards.append(f"""
        <article class="doc-item support-item">
          <div>
            <h3>{escape(str(row.get('entidad_nombre') or 'Sin nombre'))}</h3>
            <p>{escape(str(row.get('provincia') or ''))} · {escape(str(row.get('municipio') or ''))}</p>
            <p><strong>Tipo:</strong> {escape(str(row.get('tipo_estructura_apoyo') or 'Sin dato'))}</p>
            <p><strong>Cobertura:</strong> {escape(str(row.get('cobertura_principal') or 'Sin dato'))}</p>
            <p><strong>Contacto:</strong> {escape(str(row.get('persona_contacto_cargo') or 'Sin dato'))}</p>
            <p><strong>Teléfono:</strong> {escape(str(row.get('telefonos') or 'Sin dato'))}</p>
            <p><strong>Correo:</strong> {escape(str(row.get('correo_electronico') or 'Sin dato'))}</p>
            <p><strong>Servicios:</strong> {escape(str(row.get('servicios') or 'Sin servicios registrados'))}</p>
          </div>
        </article>
        """)
    if not entity_cards:
        entity_cards.append("<article class='card pad'><h2>Sin datos</h2><p>No hay entidades para los filtros seleccionados.</p></article>")

    return f"""
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>NAE Platform - Mapa de apoyo</title>
    <link rel="stylesheet" href="/prototype-assets/vendor/leaflet/leaflet.css" />
    <link rel="stylesheet" href="/prototype-assets/styles.css" />
    <style>
      .support-filters {{ margin-bottom: 18px; }}
      .support-filters .toolbar {{ grid-template-columns: repeat(5, minmax(120px, 1fr)) auto; }}
      .support-list {{ display: grid; gap: 12px; margin-top: 18px; }}
      .support-item {{ align-items: start; grid-template-columns: minmax(0, 1fr); }}
      .support-item p {{ margin-bottom: 6px; }}
      .map-shell {{ display: block; }}
      .leaflet-panel {{ position: relative; overflow: hidden; border-radius: 8px; border: 1px solid var(--line); background: #fff; box-shadow: var(--shadow); }}
      .map-caption {{ display: flex; justify-content: space-between; gap: 18px; align-items: center; border-bottom: 1px solid var(--line); background: #fff; padding: 14px 16px; }}
      .map-caption h3 {{ margin-bottom: 4px; color: var(--nae-navy); }}
      .map-caption p {{ margin: 0; color: #435466; font-size: 13px; }}
      .map-caption .map-note {{ max-width: 620px; }}
      #support-map {{ width: 100%; height: min(68vh, 680px); min-height: 520px; background: #eaf3f8; }}
      .map-legend {{ position: absolute; left: 18px; bottom: 18px; z-index: 500; display: flex; flex-wrap: wrap; gap: 8px; }}
      .map-legend span {{ display: inline-flex; align-items: center; gap: 7px; min-height: 30px; padding: 0 10px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,.94); color: #435466; font-size: 12px; font-weight: 800; }}
      .entity-dot, .fallback-dot {{ width: 10px; height: 10px; border-radius: 999px; display: inline-block; background: #cf142b; box-shadow: 0 0 0 3px rgba(207,20,43,.16); }}
      .fallback-dot {{ opacity: .72; }}
      .nae-marker {{ position: relative; display: block; width: 24px; height: 24px; background: #cf142b; border: 3px solid #fff; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-shadow: 0 9px 18px rgba(15,23,42,.30), 0 0 0 5px rgba(207,20,43,.18); }}
      .nae-marker::after {{ content: ""; position: absolute; width: 8px; height: 8px; left: 5px; top: 5px; border-radius: 999px; background: #fff; }}
      .nae-marker.fallback {{ opacity: .82; }}
      .leaflet-popup-content {{ margin: 12px 14px; width: min(280px, 72vw) !important; max-height: 220px; overflow-y: auto; }}
      .leaflet-popup-content strong {{ color: var(--nae-navy); font-size: 14px; }}
      .leaflet-popup-content p {{ margin: 6px 0 0; color: #435466; font-size: 12px; }}
      .leaflet-popup-content .popup-services {{ max-height: 70px; overflow-y: auto; padding-right: 4px; }}
      .leaflet-container {{ font-family: Arial, Helvetica, sans-serif; }}
      @media (max-width: 900px) {{ .support-filters .toolbar {{ grid-template-columns: 1fr; }} .map-caption {{ align-items: flex-start; flex-direction: column; }} }}
      @media (max-width: 720px) {{ #support-map {{ min-height: 460px; height: 460px; }} .map-legend {{ left: 12px; bottom: 12px; }} }}
    </style>
  </head>
  <body>
    <nav class="site-nav">
      <div class="nav-inner">
        <a class="nav-title" href="/"><strong>NAE</strong><span>Mapeo de Entidades de Apoyo</span></a>
        <div class="nav-links">
          <a href="/">Inicio</a>
          <a href="/encuesta">Encuesta</a>
          <a class="active" href="/mapa-apoyo">Mapa de apoyo</a>
          <a href="/documentacion">Documentación</a>
          <a class="locked" href="/analitica">Analítica</a>
        </div>
      </div>
    </nav>
    <img class="brand-strip" src="/images/banner-mapeo.jpeg" alt="NAE - Proyecto de cooperación internacional" />

    <main class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Consulta pública</p>
          <h1>Mapa de estructuras de apoyo</h1>
          <p class="lead">Visualización territorial de estructuras encuestadas y capacidades de apoyo identificadas para nuevos actores económicos.</p>
        </div>
        <div class="actions">
          <a class="button secondary" href="{escape(pdf_url)}">Directorio PDF</a>
        </div>
      </header>

      <section class="card pad support-filters">
        <form class="toolbar" method="get" action="/mapa-apoyo">
          <label class="field"><span>Provincia</span><select name="provincia">{option_list(lookups.get('provincias', []), selected.get('provincia'))}</select></label>
          <label class="field"><span>Municipio</span><select name="municipio">{option_list(lookups.get('municipios', []), selected.get('municipio'))}</select></label>
          <label class="field"><span>Tipo entidad</span><select name="tipo">{option_list(lookups.get('tipos', []), selected.get('tipo'))}</select></label>
          <label class="field"><span>Búsqueda</span><input name="q" value="{escape(str(selected.get('q') or ''))}" /></label>
          <label class="field"><span>Límite</span><input type="number" min="1" max="1000" name="limit" value="{escape(str(selected.get('limit') or 200))}" /></label>
          <div class="actions"><button class="button primary" type="submit">Aplicar</button><a class="button secondary" href="/mapa-apoyo">Limpiar</a></div>
        </form>
      </section>

      <section class="map-shell">
        <div class="leaflet-panel">
          <div class="map-caption">
            <div><h3>{data.get('total', 0)} estructuras visibles</h3><p>Mapa interactivo de Cuba con las estructuras de apoyo identificadas.</p></div>
            <p class="map-note">Ubicación actual por municipio. La coordenada exacta por dirección se integrará con geocodificación controlada.</p>
          </div>
          <div id="support-map" role="img" aria-label="Mapa interactivo de Cuba con estructuras de apoyo identificadas"></div>
          <div class="map-legend"><span><i class="entity-dot"></i>Entidad ubicada</span><span><i class="fallback-dot"></i>Ubicación municipal estimada</span></div>
        </div>
      </section>

      <section class="support-list">{''.join(entity_cards)}</section>
    </main>
    <script src="/prototype-assets/vendor/leaflet/leaflet.js"></script>
    <script>
      const supportEntities = {map_entities_json};
      const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({{
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }}[char]));
      const map = L.map('support-map', {{
        scrollWheelZoom: false,
        zoomControl: true
      }}).setView([21.85, -79.55], 6);

      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap'
      }}).addTo(map);

      const bounds = [];
      const markerLayer = L.layerGroup().addTo(map);
      const markerIcon = (isFallback) => L.divIcon({{
        className: '',
        html: `<span class="nae-marker ${{isFallback ? 'fallback' : ''}}"></span>`,
        iconSize: [30, 38],
        iconAnchor: [12, 24],
        popupAnchor: [0, -28]
      }});

      supportEntities.forEach((entity) => {{
        const services = escapeHtml(entity.services);
        const marker = L.marker([entity.lat, entity.lng], {{
          icon: markerIcon(entity.source === 'municipio')
        }}).bindPopup(`
          <strong>${{escapeHtml(entity.name)}}</strong>
          <p>${{escapeHtml(entity.type)}}</p>
          <p>${{escapeHtml(entity.municipality)}}, ${{escapeHtml(entity.province)}}</p>
          <p><b>Cobertura:</b> ${{escapeHtml(entity.coverage)}}</p>
          <p class="popup-services"><b>Servicios:</b> ${{services}}</p>
        `);
        marker.addTo(markerLayer);
        bounds.push([entity.lat, entity.lng]);
      }});

      if (bounds.length > 1) {{
        map.fitBounds(bounds, {{ padding: [48, 48], maxZoom: 7 }});
      }} else {{
        map.setView([21.85, -79.55], 6);
      }}
    </script>
  </body>
</html>
    """


def _mapeo_filters_clause(
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    tipo: Optional[str] = None,
    servicio: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    clauses = ["COALESCE(f.version_encuesta, '1.0') = 'mapeo_estructuras_v1'"]
    params: Dict[str, Any] = {}

    if provincia:
        clauses.append("t.provincia_nombre = :provincia")
        params["provincia"] = provincia

    if version_encuesta:
        clauses.append("COALESCE(f.version_encuesta, '1.0') = :version_encuesta")
        params["version_encuesta"] = version_encuesta

    if tipo:
        clauses.append("COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion) = :tipo")
        params["tipo"] = tipo

    if servicio:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM operational.respuestas_mapeo_servicios sf
                WHERE sf.operational_respuesta_id = o.id
                  AND sf.servicio = :servicio
            )
            """
        )
        params["servicio"] = servicio

    return " AND ".join(clauses), params


def _fetch_mapeo_lookup_options() -> Dict[str, List[str]]:
    db = SessionLocal()
    try:
        provincias = db.execute(
            text("""
                SELECT DISTINCT t.provincia_nombre
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                WHERE COALESCE(f.version_encuesta, '1.0') = 'mapeo_estructuras_v1'
                ORDER BY t.provincia_nombre
            """)
        ).scalars().all()

        versiones = db.execute(
            text("""
                SELECT DISTINCT COALESCE(version_encuesta, '1.0') AS version_encuesta
                FROM analytics.f_respuestas_encuesta
                ORDER BY version_encuesta DESC
            """)
        ).scalars().all()

        tipos = db.execute(
            text("""
                SELECT DISTINCT COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion) AS tipo
                FROM operational.respuestas_encuesta o
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
                WHERE COALESCE(o.version_encuesta, '') = 'mapeo_estructuras_v1'
                  AND COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion) IS NOT NULL
                ORDER BY tipo
            """)
        ).scalars().all()

        servicios = db.execute(
            text("""
                SELECT DISTINCT servicio
                FROM operational.respuestas_mapeo_servicios
                ORDER BY servicio
            """)
        ).scalars().all()

        return {
            "provincias": list(provincias),
            "versiones": list(versiones),
            "tipos": list(tipos),
            "servicios": list(servicios),
        }
    except ProgrammingError:
        db.rollback()
        return {"provincias": [], "versiones": [], "tipos": [], "servicios": []}
    finally:
        db.close()




def _mapeo_entity_filters_clause(
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    tipo: Optional[str] = None,
    servicio: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    clauses = ["ea.estado_revision <> 'descartada'"]
    params: Dict[str, Any] = {}

    if provincia:
        clauses.append("p.nombre = :provincia")
        params["provincia"] = provincia

    if version_encuesta:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM operational.respuestas_entidades_apoyo rel_v
                JOIN operational.respuestas_encuesta o_v ON o_v.id = rel_v.operational_respuesta_id
                WHERE rel_v.entidad_apoyo_id = ea.id
                  AND COALESCE(o_v.version_encuesta, '1.0') = :version_encuesta
            )
            """
        )
        params["version_encuesta"] = version_encuesta
    else:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM operational.respuestas_entidades_apoyo rel_v
                JOIN operational.respuestas_encuesta o_v ON o_v.id = rel_v.operational_respuesta_id
                WHERE rel_v.entidad_apoyo_id = ea.id
                  AND COALESCE(o_v.version_encuesta, '') = 'mapeo_estructuras_v1'
            )
            """
        )

    if tipo:
        clauses.append("COALESCE(ea.tipo_estructura_apoyo, '') = :tipo")
        params["tipo"] = tipo

    if servicio:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM operational.respuestas_entidades_apoyo rel_s
                JOIN operational.respuestas_mapeo_servicios s ON s.operational_respuesta_id = rel_s.operational_respuesta_id
                WHERE rel_s.entidad_apoyo_id = ea.id
                  AND s.servicio = :servicio
                  AND (s.ofrece_actualmente IS TRUE OR s.requiere_fortalecer IS TRUE)
            )
            """
        )
        params["servicio"] = servicio

    return " AND ".join(clauses), params


def _query_rows(db, sql: str, params: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    return [dict(row) for row in db.execute(text(sql), {**params, **(extra or {})}).mappings().all()]


def _get_dashboard_data_canonical(
    db,
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
    tipo: Optional[str] = None,
    servicio: Optional[str] = None,
) -> Dict[str, Any]:
    entity_where, entity_params = _mapeo_entity_filters_clause(provincia, version_encuesta, tipo, servicio)
    response_where, response_params = _mapeo_filters_clause(provincia, version_encuesta, tipo, servicio)

    total_entities = db.execute(
        text(f"""
            SELECT COUNT(DISTINCT ea.id)::int
            FROM operational.entidades_apoyo ea
            JOIN operational.provincias p ON p.id = ea.provincia_id
            JOIN operational.municipios mu ON mu.id = ea.municipio_id
            WHERE {entity_where}
        """),
        entity_params,
    ).scalar_one()

    total_responses = db.execute(
        text(f"""
            SELECT COUNT(*)::int
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {response_where}
        """),
        response_params,
    ).scalar_one()

    kpis = dict(db.execute(
        text(f"""
            SELECT COUNT(DISTINCT p.nombre)::int AS provincias,
                   COUNT(DISTINCT mu.nombre)::int AS municipios,
                   COUNT(DISTINCT ea.tipo_estructura_apoyo)::int AS tipos_estructura,
                   COUNT(DISTINCT ea.id) FILTER (WHERE NULLIF(TRIM(COALESCE(ea.telefonos, ea.correo_electronico, '')), '') IS NOT NULL)::int AS con_contacto,
                   COUNT(DISTINCT ea.id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM operational.respuestas_entidades_apoyo rel_a
                       JOIN operational.respuestas_mapeo_entidad m_a ON m_a.operational_respuesta_id = rel_a.operational_respuesta_id
                       WHERE rel_a.entidad_apoyo_id = ea.id AND COALESCE(m_a.capacidad_actualizar_mapeo, '') ILIKE 'Sí%%'
                   ))::int AS actualizan_mapeo,
                   COUNT(DISTINCT ea.id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM operational.respuestas_entidades_apoyo rel_c
                       JOIN operational.respuestas_mapeo_entidad m_c ON m_c.operational_respuesta_id = rel_c.operational_respuesta_id
                       WHERE rel_c.entidad_apoyo_id = ea.id AND COALESCE(m_c.capacidad_ampliar_cobertura, '') ILIKE 'Sí%%'
                   ))::int AS amplian_cobertura
            FROM operational.entidades_apoyo ea
            JOIN operational.provincias p ON p.id = ea.provincia_id
            JOIN operational.municipios mu ON mu.id = ea.municipio_id
            WHERE {entity_where}
        """),
        entity_params,
    ).mappings().one())
    kpis["envios_recibidos"] = int(total_responses)

    def entity_rows(sql: str, extra: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return _query_rows(db, sql, entity_params, extra)

    def response_rows(sql: str, extra: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return _query_rows(db, sql, response_params, extra)

    respuestas_por_dia = response_rows(f"""
        SELECT f.fecha_respuesta::date AS fecha, COUNT(*)::int AS total
        FROM analytics.f_respuestas_encuesta f
        JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
        JOIN analytics.dim_territorio t ON t.id = f.territorio_id
        LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
        WHERE {response_where}
        GROUP BY f.fecha_respuesta::date
        ORDER BY fecha ASC
    """)

    por_estado = response_rows(f"""
        SELECT e.estado_validacion AS label, COUNT(*)::int AS total
        FROM analytics.f_respuestas_encuesta f
        JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
        JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
        JOIN analytics.dim_territorio t ON t.id = f.territorio_id
        LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
        WHERE {response_where}
        GROUP BY e.estado_validacion
        ORDER BY total DESC, label ASC
    """)

    por_provincia = entity_rows(f"""
        SELECT p.nombre AS provincia, mu.nombre AS municipio, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        WHERE {entity_where}
        GROUP BY p.nombre, mu.nombre
        ORDER BY total DESC, provincia ASC, municipio ASC
    """)

    simple_entity_groups = {
        "tipos_estructura": ("COALESCE(ea.tipo_estructura_apoyo, 'Sin dato')", "operational.entidades_apoyo ea JOIN operational.provincias p ON p.id = ea.provincia_id JOIN operational.municipios mu ON mu.id = ea.municipio_id", ""),
        "cobertura": ("COALESCE(ea.cobertura_principal, 'Sin dato')", "operational.entidades_apoyo ea JOIN operational.provincias p ON p.id = ea.provincia_id JOIN operational.municipios mu ON mu.id = ea.municipio_id", ""),
    }
    grouped = {}
    for key, (expr, joins, extra_where) in simple_entity_groups.items():
        grouped[key] = entity_rows(f"""
            SELECT {expr} AS label, COUNT(DISTINCT ea.id)::int AS total
            FROM {joins}
            WHERE {entity_where} {extra_where}
            GROUP BY {expr}
            ORDER BY total DESC, label ASC
            LIMIT 12
        """)

    modalidad_atencion = entity_rows(f"""
        SELECT COALESCE(m.modalidad_atencion, 'Sin dato') AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where}
        GROUP BY COALESCE(m.modalidad_atencion, 'Sin dato')
        ORDER BY total DESC, label ASC
    """)

    servicios_ofrecidos = entity_rows(f"""
        SELECT s.servicio AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        JOIN operational.respuestas_mapeo_servicios s ON s.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where} AND s.ofrece_actualmente IS TRUE
        GROUP BY s.servicio
        ORDER BY total DESC, label ASC
        LIMIT 12
    """)

    servicios_fortalecer = entity_rows(f"""
        SELECT s.servicio AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        JOIN operational.respuestas_mapeo_servicios s ON s.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where} AND s.requiere_fortalecer IS TRUE
        GROUP BY s.servicio
        ORDER BY total DESC, label ASC
        LIMIT 12
    """)

    tipos_nae = entity_rows(f"""
        SELECT tn.tipo_nae AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        JOIN operational.respuestas_mapeo_tipos_nae tn ON tn.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where}
        GROUP BY tn.tipo_nae
        ORDER BY total DESC, label ASC
        LIMIT 12
    """)

    capacidades = entity_rows(f"""
        SELECT ct.capacidad_tecnica AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        JOIN operational.respuestas_mapeo_capacidades_tecnicas ct ON ct.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where}
        GROUP BY ct.capacidad_tecnica
        ORDER BY total DESC, label ASC
        LIMIT 12
    """)

    limitaciones = entity_rows(f"""
        SELECT rl.limitacion AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        JOIN operational.respuestas_limitaciones rl ON rl.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where}
        GROUP BY rl.limitacion
        ORDER BY total DESC, label ASC
        LIMIT 12
    """)

    conectividad = entity_rows(f"""
        SELECT COALESCE(m.condiciones_conectividad, 'Sin dato') AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where}
        GROUP BY COALESCE(m.condiciones_conectividad, 'Sin dato')
        ORDER BY total DESC, label ASC
    """)

    sostenibilidad = entity_rows(f"""
        SELECT COALESCE(m.capacidad_sostener_servicios, 'Sin dato') AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where}
        GROUP BY COALESCE(m.capacidad_sostener_servicios, 'Sin dato')
        ORDER BY total DESC, label ASC
    """)

    actualizacion_mapa = entity_rows(f"""
        SELECT COALESCE(m.capacidad_actualizar_mapeo, 'Sin dato') AS label, COUNT(DISTINCT ea.id)::int AS total
        FROM operational.entidades_apoyo ea
        JOIN operational.provincias p ON p.id = ea.provincia_id
        JOIN operational.municipios mu ON mu.id = ea.municipio_id
        JOIN operational.respuestas_entidades_apoyo rel ON rel.entidad_apoyo_id = ea.id
        LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = rel.operational_respuesta_id
        WHERE {entity_where}
        GROUP BY COALESCE(m.capacidad_actualizar_mapeo, 'Sin dato')
        ORDER BY total DESC, label ASC
    """)

    ultimas_respuestas = response_rows(f"""
        SELECT f.id,
               COALESCE(f.version_encuesta, '1.0') AS version_encuesta,
               f.fecha_respuesta,
               t.provincia_nombre,
               t.municipio_nombre,
               COALESCE(m.entidad_nombre, o.nombre_institucion) AS nombre_institucion,
               COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion) AS tipo_estructura,
               COALESCE(m.cobertura_principal, o.ambito_actuacion) AS cobertura,
               COALESCE(m.capacidad_actualizar_mapeo, 'Sin dato') AS actualizacion_mapa,
               e.estado_validacion
        FROM analytics.f_respuestas_encuesta f
        JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
        JOIN analytics.dim_territorio t ON t.id = f.territorio_id
        JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
        LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
        WHERE {response_where}
        ORDER BY f.id DESC
        LIMIT :limit
    """, {"limit": limit})

    return {
        "filters": {"provincia": provincia, "version_encuesta": version_encuesta, "genero": genero, "tema": tema, "tipo": tipo, "servicio": servicio},
        "lookups": _fetch_mapeo_lookup_options(),
        "total_respuestas": int(total_entities),
        "total_envios": int(total_responses),
        "kpis": kpis,
        "respuestas_por_dia": respuestas_por_dia,
        "por_estado": por_estado,
        "por_provincia": por_provincia,
        "tipos_estructura": grouped["tipos_estructura"],
        "cobertura": grouped["cobertura"],
        "modalidad_atencion": modalidad_atencion,
        "servicios_ofrecidos": servicios_ofrecidos,
        "servicios_fortalecer": servicios_fortalecer,
        "tipos_nae": tipos_nae,
        "capacidades": capacidades,
        "limitaciones": limitaciones,
        "conectividad": conectividad,
        "sostenibilidad": sostenibilidad,
        "actualizacion_mapa": actualizacion_mapa,
        "instituciones": [{"label": row["nombre_institucion"], "total": 1} for row in ultimas_respuestas[:10]],
        "temas_formacion": servicios_fortalecer,
        "por_genero": grouped["tipos_estructura"],
        "por_nivel_instruccion": grouped["cobertura"],
        "ultimas_respuestas": ultimas_respuestas,
    }

def get_dashboard_data(
    limit: int = 10,
    provincia: Optional[str] = None,
    version_encuesta: Optional[str] = None,
    genero: Optional[str] = None,
    tema: Optional[str] = None,
    tipo: Optional[str] = None,
    servicio: Optional[str] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        has_entity_resolution = db.execute(
            text("SELECT to_regclass('operational.entidades_apoyo') IS NOT NULL")
        ).scalar()
        if has_entity_resolution:
            return _get_dashboard_data_canonical(
                db,
                limit=limit,
                provincia=provincia,
                version_encuesta=version_encuesta,
                genero=genero,
                tema=tema,
                tipo=tipo,
                servicio=servicio,
            )

        where_clause, params = _mapeo_filters_clause(provincia, version_encuesta, tipo, servicio)

        total = db.execute(
            text(f"""
                SELECT COUNT(*)::int
                FROM analytics.f_respuestas_encuesta f
                JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
                WHERE {where_clause}
            """),
            params,
        ).scalar_one()

        kpis = db.execute(
            text(f"""
                SELECT COUNT(DISTINCT t.provincia_nombre)::int AS provincias,
                       COUNT(DISTINCT t.municipio_nombre)::int AS municipios,
                       COUNT(DISTINCT COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion))::int AS tipos_estructura,
                       COUNT(*) FILTER (WHERE NULLIF(TRIM(COALESCE(m.telefonos, m.correo_electronico, '')), '') IS NOT NULL)::int AS con_contacto,
                       COUNT(*) FILTER (WHERE COALESCE(m.capacidad_actualizar_mapeo, '') ILIKE 'Sí%%')::int AS actualizan_mapeo,
                       COUNT(*) FILTER (WHERE COALESCE(m.capacidad_ampliar_cobertura, '') ILIKE 'Sí%%')::int AS amplian_cobertura
                FROM analytics.f_respuestas_encuesta f
                JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
                WHERE {where_clause}
            """),
            params,
        ).mappings().one()

        def rows(sql: str, extra: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
            return [dict(row) for row in db.execute(text(sql), {**params, **(extra or {})}).mappings().all()]

        respuestas_por_dia = rows(f"""
            SELECT f.fecha_respuesta::date AS fecha, COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY f.fecha_respuesta::date
            ORDER BY fecha ASC
        """)

        por_estado = rows(f"""
            SELECT e.estado_validacion AS label, COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY e.estado_validacion
            ORDER BY total DESC, label ASC
        """)

        por_provincia = rows(f"""
            SELECT t.provincia_nombre AS provincia,
                   t.municipio_nombre AS municipio,
                   COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY t.provincia_nombre, t.municipio_nombre
            ORDER BY total DESC, provincia ASC, municipio ASC
        """)

        tipos_estructura = rows(f"""
            SELECT COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion, 'Sin dato') AS label,
                   COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion, 'Sin dato')
            ORDER BY total DESC, label ASC
            LIMIT 12
        """)

        cobertura = rows(f"""
            SELECT COALESCE(m.cobertura_principal, o.ambito_actuacion, 'Sin dato') AS label,
                   COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY COALESCE(m.cobertura_principal, o.ambito_actuacion, 'Sin dato')
            ORDER BY total DESC, label ASC
        """)

        modalidad_atencion = rows(f"""
            SELECT COALESCE(m.modalidad_atencion, 'Sin dato') AS label,
                   COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY COALESCE(m.modalidad_atencion, 'Sin dato')
            ORDER BY total DESC, label ASC
        """)

        servicios_ofrecidos = rows(f"""
            SELECT s.servicio AS label, COUNT(*)::int AS total
            FROM operational.respuestas_mapeo_servicios s
            JOIN operational.respuestas_encuesta o ON o.id = s.operational_respuesta_id
            JOIN analytics.f_respuestas_encuesta f ON f.operational_respuesta_id = o.id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause} AND s.ofrece_actualmente IS TRUE
            GROUP BY s.servicio
            ORDER BY total DESC, label ASC
            LIMIT 12
        """)

        servicios_fortalecer = rows(f"""
            SELECT s.servicio AS label, COUNT(*)::int AS total
            FROM operational.respuestas_mapeo_servicios s
            JOIN operational.respuestas_encuesta o ON o.id = s.operational_respuesta_id
            JOIN analytics.f_respuestas_encuesta f ON f.operational_respuesta_id = o.id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause} AND s.requiere_fortalecer IS TRUE
            GROUP BY s.servicio
            ORDER BY total DESC, label ASC
            LIMIT 12
        """)

        tipos_nae = rows(f"""
            SELECT tn.tipo_nae AS label, COUNT(*)::int AS total
            FROM operational.respuestas_mapeo_tipos_nae tn
            JOIN operational.respuestas_encuesta o ON o.id = tn.operational_respuesta_id
            JOIN analytics.f_respuestas_encuesta f ON f.operational_respuesta_id = o.id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY tn.tipo_nae
            ORDER BY total DESC, label ASC
            LIMIT 12
        """)

        capacidades = rows(f"""
            SELECT ct.capacidad_tecnica AS label, COUNT(*)::int AS total
            FROM operational.respuestas_mapeo_capacidades_tecnicas ct
            JOIN operational.respuestas_encuesta o ON o.id = ct.operational_respuesta_id
            JOIN analytics.f_respuestas_encuesta f ON f.operational_respuesta_id = o.id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY ct.capacidad_tecnica
            ORDER BY total DESC, label ASC
            LIMIT 12
        """)

        limitaciones = rows(f"""
            SELECT rl.limitacion AS label, COUNT(*)::int AS total
            FROM operational.respuestas_limitaciones rl
            JOIN operational.respuestas_encuesta o ON o.id = rl.operational_respuesta_id
            JOIN analytics.f_respuestas_encuesta f ON f.operational_respuesta_id = o.id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY rl.limitacion
            ORDER BY total DESC, label ASC
            LIMIT 12
        """)

        conectividad = rows(f"""
            SELECT COALESCE(m.condiciones_conectividad, 'Sin dato') AS label, COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY COALESCE(m.condiciones_conectividad, 'Sin dato')
            ORDER BY total DESC, label ASC
        """)

        sostenibilidad = rows(f"""
            SELECT COALESCE(m.capacidad_sostener_servicios, 'Sin dato') AS label, COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY COALESCE(m.capacidad_sostener_servicios, 'Sin dato')
            ORDER BY total DESC, label ASC
        """)

        actualizacion_mapa = rows(f"""
            SELECT COALESCE(m.capacidad_actualizar_mapeo, 'Sin dato') AS label, COUNT(*)::int AS total
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            GROUP BY COALESCE(m.capacidad_actualizar_mapeo, 'Sin dato')
            ORDER BY total DESC, label ASC
        """)

        ultimas_respuestas = rows(f"""
            SELECT f.id,
                   COALESCE(f.version_encuesta, '1.0') AS version_encuesta,
                   f.fecha_respuesta,
                   t.provincia_nombre,
                   t.municipio_nombre,
                   COALESCE(m.entidad_nombre, o.nombre_institucion) AS nombre_institucion,
                   COALESCE(m.tipo_estructura_apoyo, o.tipo_institucion) AS tipo_estructura,
                   COALESCE(m.cobertura_principal, o.ambito_actuacion) AS cobertura,
                   COALESCE(m.capacidad_actualizar_mapeo, 'Sin dato') AS actualizacion_mapa,
                   e.estado_validacion
            FROM analytics.f_respuestas_encuesta f
            JOIN operational.respuestas_encuesta o ON o.id = f.operational_respuesta_id
            JOIN analytics.dim_territorio t ON t.id = f.territorio_id
            JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
            LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = o.id
            WHERE {where_clause}
            ORDER BY f.id DESC
            LIMIT :limit
        """, {"limit": limit})

        return {
            "filters": {
                "provincia": provincia,
                "version_encuesta": version_encuesta,
                "genero": genero,
                "tema": tema,
                "tipo": tipo,
                "servicio": servicio,
            },
            "lookups": _fetch_mapeo_lookup_options(),
            "total_respuestas": int(total),
            "kpis": dict(kpis),
            "respuestas_por_dia": respuestas_por_dia,
            "por_estado": por_estado,
            "por_provincia": por_provincia,
            "tipos_estructura": tipos_estructura,
            "cobertura": cobertura,
            "modalidad_atencion": modalidad_atencion,
            "servicios_ofrecidos": servicios_ofrecidos,
            "servicios_fortalecer": servicios_fortalecer,
            "tipos_nae": tipos_nae,
            "capacidades": capacidades,
            "limitaciones": limitaciones,
            "conectividad": conectividad,
            "sostenibilidad": sostenibilidad,
            "actualizacion_mapa": actualizacion_mapa,
            "instituciones": [{"label": row["nombre_institucion"], "total": 1} for row in ultimas_respuestas[:10]],
            "temas_formacion": servicios_fortalecer,
            "por_genero": tipos_estructura,
            "por_nivel_instruccion": cobertura,
            "ultimas_respuestas": ultimas_respuestas,
        }
    except ProgrammingError:
        db.rollback()
        return {
            "filters": {"provincia": provincia, "version_encuesta": version_encuesta, "genero": genero, "tema": tema, "tipo": tipo, "servicio": servicio},
            "lookups": {"provincias": [], "versiones": [], "tipos": [], "servicios": []},
            "total_respuestas": 0,
            "kpis": {"provincias": 0, "municipios": 0, "tipos_estructura": 0, "con_contacto": 0, "actualizan_mapeo": 0, "amplian_cobertura": 0},
            "respuestas_por_dia": [],
            "por_estado": [], "por_provincia": [], "tipos_estructura": [], "cobertura": [], "modalidad_atencion": [],
            "servicios_ofrecidos": [], "servicios_fortalecer": [], "tipos_nae": [], "capacidades": [], "limitaciones": [],
            "conectividad": [], "sostenibilidad": [], "actualizacion_mapa": [], "instituciones": [], "temas_formacion": [],
            "por_genero": [], "por_nivel_instruccion": [], "ultimas_respuestas": [],
        }
    finally:
        db.close()


def _donut_chart(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p class='empty'>Sin datos</p>"
    colors = ["#0f6fa6", "#20d79f", "#b8871b", "#b64b4b", "#64748b", "#7c3aed", "#0f766e"]
    total = sum(int(row.get("total", 0) or 0) for row in rows) or 1
    start = 0.0
    segments = []
    legend = []
    for index, row in enumerate(rows[:7]):
        value = int(row.get("total", 0) or 0)
        end = start + (value / total) * 100
        color = colors[index % len(colors)]
        segments.append(f"{color} {start:.2f}% {end:.2f}%")
        label = escape(str(row.get("label") or "Sin dato"))
        legend.append(f"<li><span style='background:{color}'></span><strong>{value}</strong>{label}</li>")
        start = end
    return f"""
      <div class="donut-wrap">
        <div class="donut" style="background: conic-gradient({', '.join(segments)});"><span>{total}</span></div>
        <ul class="donut-legend">{''.join(legend)}</ul>
      </div>
    """


def _tile_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p class='empty'>Sin datos</p>"
    return "".join(
        f"""
        <div class="tile-row">
          <strong>{escape(str(row.get('total') or 0))}</strong>
          <span>{escape(str(row.get('label') or 'Sin dato'))}</span>
        </div>
        """
        for row in rows[:8]
    )


def _daily_chart(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p class='empty'>Sin datos</p>"
    series = rows[-30:]
    totals = [int(row.get("total", 0) or 0) for row in series]
    max_total = max(totals) or 1
    width = 760
    height = 220
    pad_x = 42
    pad_top = 24
    pad_bottom = 44
    chart_w = width - (pad_x * 2)
    chart_h = height - pad_top - pad_bottom
    count = len(series)

    points = []
    for index, row in enumerate(series):
        x = pad_x + (chart_w * index / max(count - 1, 1))
        y = pad_top + chart_h - ((int(row.get("total", 0) or 0) / max_total) * chart_h)
        points.append((x, y, row))

    line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    area_points = f"{pad_x},{height - pad_bottom} {line_points} {width - pad_x},{height - pad_bottom}"
    markers = []
    for x, y, row in points:
        fecha = escape(str(row.get("fecha") or ""))
        total = int(row.get("total", 0) or 0)
        markers.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.2"><title>{fecha}: {total} respuestas</title></circle>'
        )

    first_date = escape(str(series[0].get("fecha") or ""))
    last_date = escape(str(series[-1].get("fecha") or ""))
    total_period = sum(totals)
    peak = max_total
    return f"""
      <div class="trend-chart">
        <div class="trend-summary">
          <div><span>Periodo</span><strong>{total_period}</strong><small>respuestas</small></div>
          <div><span>Pico diario</span><strong>{peak}</strong><small>respuestas</small></div>
        </div>
        <svg class="trend-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Tendencia diaria de respuestas enviadas">
          <line class="axis" x1="{pad_x}" y1="{height - pad_bottom}" x2="{width - pad_x}" y2="{height - pad_bottom}" />
          <line class="axis" x1="{pad_x}" y1="{pad_top}" x2="{pad_x}" y2="{height - pad_bottom}" />
          <text class="axis-label" x="{pad_x}" y="{height - 14}" text-anchor="start">{first_date}</text>
          <text class="axis-label" x="{width - pad_x}" y="{height - 14}" text-anchor="end">{last_date}</text>
          <text class="axis-label" x="{pad_x - 10}" y="{pad_top + 4}" text-anchor="end">{peak}</text>
          <polygon class="trend-area" points="{area_points}" />
          <polyline class="trend-line" points="{line_points}" />
          <g class="trend-points">{''.join(markers)}</g>
        </svg>
      </div>
    """


def render_dashboard_html(data: Dict[str, Any]) -> str:
    lookups = data["lookups"]
    selected = data["filters"]
    kpis = data.get("kpis", {})
    estado_totals = {row.get("label"): row.get("total", 0) for row in data["por_estado"]}
    validadas = estado_totals.get("validada", 0)
    observaciones = estado_totals.get("con_observaciones", 0)
    rechazadas = estado_totals.get("rechazada", 0)
    def option_list(values: List[str], selected_value: Optional[str]) -> str:
        options = ['<option value="">Todos</option>']
        for value in values:
            mark = " selected" if value == selected_value else ""
            options.append(f"<option value='{escape(str(value))}'{mark}>{escape(str(value))}</option>")
        return "".join(options)

    filters_html = f"""
        <form class="filters" method="get" action="/analitica">
          <div class="filter-title">
            <strong>Filtros</strong>
            <span>Lectura operativa del mapeo de estructuras de apoyo</span>
          </div>
          <label><span>Provincia</span><select name="provincia">{option_list(lookups.get('provincias', []), selected.get('provincia'))}</select></label>
          <label><span>Versión</span><select name="version_encuesta">{option_list(lookups.get('versiones', []), selected.get('version_encuesta'))}</select></label>
          <label><span>Tipo estructura</span><select name="tipo">{option_list(lookups.get('tipos', []), selected.get('tipo'))}</select></label>
          <label><span>Servicio</span><select name="servicio">{option_list(lookups.get('servicios', []), selected.get('servicio'))}</select></label>
          <label><span>Límite</span><input type="number" name="limit" min="1" max="50" value="{escape(str(selected.get('limit') or 10))}" /></label>
          <div class="filter-actions">
            <button type="submit">Aplicar</button>
            <a href="/analitica">Limpiar</a>
          </div>
        </form>
    """

    metrics = f"""
        <section class="kpis">
          <div class="kpi primary"><span>Entidades mapeadas</span><strong>{data['total_respuestas']}</strong><small>Entidades consolidadas, sin duplicar envíos</small></div>
          <div class="kpi"><span>Envíos recibidos</span><strong>{kpis.get('envios_recibidos', data.get('total_envios', data['total_respuestas']))}</strong><small>Respuestas individuales conservadas</small></div>
          <div class="kpi"><span>Provincias</span><strong>{kpis.get('provincias', 0)}</strong><small>Cobertura territorial capturada</small></div>
          <div class="kpi"><span>Municipios</span><strong>{kpis.get('municipios', 0)}</strong><small>Ubicaciones con estructuras reportadas</small></div>
          <div class="kpi"><span>Tipos de estructura</span><strong>{kpis.get('tipos_estructura', 0)}</strong><small>Diversidad institucional registrada</small></div>
          <div class="kpi"><span>Con contacto</span><strong>{kpis.get('con_contacto', 0)}</strong><small>Teléfono o correo disponible</small></div>
          <div class="kpi"><span>Actualizan mapa</span><strong>{kpis.get('actualizan_mapeo', 0)}</strong><small>Capacidad declarada de actualización</small></div>
          <div class="kpi"><span>Amplían cobertura</span><strong>{kpis.get('amplian_cobertura', 0)}</strong><small>Posibilidad de atender otros territorios</small></div>
          <div class="kpi attention"><span>Observaciones</span><strong>{observaciones}</strong><small>Revisar calidad del dato</small></div>
        </section>
    """

    html = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>NAE Platform - Analítica</title>
      <link rel="stylesheet" href="/prototype-assets/styles.css" />
      <style>
        :root {{
          --bg: #f4f6f9; --panel: #ffffff; --panel-soft: #f8fafc; --line: #d8dee8; --line-strong: #b8c2d1;
          --text: #172033; --muted: #66758a; --muted-strong: #46566f; --accent: #0f6fa6; --accent-deep: #003247;
          --accent-soft: #e8f3f8; --ok: #087456; --warn: #b8871b; --danger: #b64b4b;
        }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); line-height: 1.45; }}
        .shell {{ width: min(1440px, 100%); margin: 0 auto; padding: 0 24px; }}
        main.analytics-main {{ padding: 22px 0 34px; }}
        .layout {{ display: grid; gap: 16px; }}
        .filters {{ display: grid; grid-template-columns: minmax(180px, 1.2fr) repeat(5, minmax(120px, 1fr)) auto; gap: 10px; align-items: end; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; box-shadow: 0 1px 2px rgba(15, 23, 42, .04); }}
        .filter-title {{ display: grid; gap: 2px; align-self: center; }}
        .filter-title strong {{ font-size: 14px; }} .filter-title span {{ color: var(--muted); font-size: 12px; }}
        .filters label {{ display: grid; gap: 5px; min-width: 0; }}
        .filters label span {{ color: var(--muted-strong); font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .filters select, .filters input {{ width: 100%; min-height: 38px; padding: 8px 10px; border: 1px solid var(--line-strong); border-radius: 8px; background: #fff; color: var(--text); font-size: 13px; }}
        .filter-actions {{ display: flex; gap: 8px; align-items: end; white-space: nowrap; }}
        .filter-actions button, .filter-actions a {{ display: inline-flex; align-items: center; justify-content: center; min-height: 38px; padding: 0 12px; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 700; border: 1px solid var(--line-strong); cursor: pointer; }}
        .filter-actions button {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
        .filter-actions a {{ color: var(--text); background: #fff; }}
        .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
        .kpi, .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 1px 2px rgba(15, 23, 42, .04); }}
        .kpi {{ min-height: 112px; padding: 15px; display: grid; align-content: space-between; border-left: 4px solid #9eb5d1; }}
        .kpi.primary {{ border-left-color: var(--accent); }} .kpi.attention {{ border-left-color: var(--warn); }} .kpi.danger {{ border-left-color: var(--danger); }}
        .kpi span {{ color: var(--muted-strong); font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .kpi strong {{ display: block; color: var(--text); font-size: 30px; line-height: 1; margin-top: 8px; }}
        .kpi small {{ display: block; color: var(--muted); font-size: 12px; margin-top: 8px; }}
        .grid {{ display: grid; grid-template-columns: 1fr; gap: 18px; }}
        @media(min-width: 1100px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
        .card {{ padding: 0; overflow: hidden; }}
        .card-head {{ padding: 15px 16px 12px; border-bottom: 1px solid var(--line); background: var(--panel-soft); }}
        .card-body {{ padding: 14px 16px 16px; }}
        .card h2 {{ margin: 3px 0 0; font-size: 16px; line-height: 1.25; }}
        .section-lead {{ margin: 0; color: var(--accent); font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .bar-row {{ display: grid; grid-template-columns: minmax(140px, 1.3fr) minmax(160px, 2fr) 48px; gap: 10px; align-items: center; padding: 7px 0; border-bottom: 1px solid #edf1f6; }}
        .bar-row:last-child {{ border-bottom: 0; }} .bar-label, .bar-value {{ font-size: 13px; }} .bar-value {{ text-align: right; color: var(--muted-strong); font-weight: 700; }}
        .bar-track {{ height: 10px; background: #edf2f7; border-radius: 999px; overflow: hidden; }} .bar-fill {{ height: 100%; background: var(--accent); border-radius: 999px; }}
        .donut-wrap {{ display: grid; grid-template-columns: 170px minmax(0,1fr); gap: 16px; align-items: center; }}
        .donut {{ width: 156px; height: 156px; border-radius: 50%; display: grid; place-items: center; position: relative; }}
        .donut::after {{ content: ''; position: absolute; inset: 32px; border-radius: 50%; background: #fff; }}
        .donut span {{ position: relative; z-index: 1; font-size: 26px; font-weight: 800; color: var(--accent-deep); }}
        .donut-legend {{ margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }}
        .donut-legend li {{ display: grid; grid-template-columns: 12px 36px minmax(0,1fr); gap: 8px; align-items: center; font-size: 13px; }}
        .donut-legend span {{ width: 12px; height: 12px; border-radius: 3px; }}
        .trend-chart {{ display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 16px; align-items: stretch; }}
        .trend-summary {{ display: grid; gap: 10px; align-content: center; }}
        .trend-summary div {{ min-height: 78px; border: 1px solid var(--line); border-radius: 8px; background: #fbfdff; padding: 12px; }}
        .trend-summary span {{ display: block; color: var(--muted-strong); font-size: 11px; font-weight: 700; text-transform: uppercase; }}
        .trend-summary strong {{ display: inline-block; margin-top: 7px; color: var(--accent-deep); font-size: 30px; line-height: 1; }}
        .trend-summary small {{ margin-left: 5px; color: var(--muted); font-size: 12px; }}
        .trend-svg {{ width: 100%; min-height: 240px; display: block; }}
        .axis {{ stroke: #c9d4e2; stroke-width: 1.2; }}
        .axis-label {{ fill: var(--muted); font-size: 12px; }}
        .trend-area {{ fill: rgba(15, 111, 166, .12); }}
        .trend-line {{ fill: none; stroke: var(--accent); stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }}
        .trend-points circle {{ fill: #fff; stroke: var(--accent); stroke-width: 3; }}
        .trend-points circle:hover {{ fill: var(--nae-teal, #20d79f); }}
        .tile-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }}
        .tile-row {{ min-height: 74px; border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfdff; }}
        .tile-row strong {{ display: block; color: var(--accent-deep); font-size: 22px; line-height: 1; }}
        .tile-row span {{ display: block; margin-top: 8px; color: var(--muted-strong); font-size: 13px; }}
        table {{ width: 100%; border-collapse: collapse; }} th, td {{ padding: 9px 10px; border-bottom: 1px solid #e4e9f0; text-align: left; font-size: 13px; vertical-align: top; }}
        th {{ background: #f7f9fc; color: var(--muted-strong); font-size: 11px; text-transform: uppercase; }} tr:hover td {{ background: #fbfdff; }} td a {{ color: var(--accent); font-weight: 700; text-decoration: none; }}
        .empty {{ color: var(--muted); margin: 0; }} .wide {{ grid-column: 1 / -1; }} .table-wrap {{ overflow-x: auto; }}
        @media(max-width: 1180px) {{ .filters {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} .filter-title, .filter-actions {{ grid-column: 1 / -1; }} .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
        @media(max-width: 720px) {{ .shell {{ padding: 0 14px; }} main {{ padding: 16px 0 26px; }} .filters, .kpis, .tile-grid, .donut-wrap {{ grid-template-columns: 1fr; }} .filter-actions {{ flex-wrap: wrap; }} .filter-actions button, .filter-actions a {{ width: 100%; }} }}
      </style>
    </head>
    <body>
      <nav class="site-nav">
        <div class="nav-inner">
          <a class="nav-title" href="/"><strong>NAE</strong><span>Mapeo de Entidades de Apoyo</span></a>
          <div class="nav-links">
            <a href="/">Inicio</a>
            <a href="/encuesta">Encuesta</a>
            <a href="/mapa-apoyo">Mapa de apoyo</a>
            <a href="/documentacion">Documentación</a>
            <a class="active locked" href="/analitica">Analítica</a>
            <a class="locked" href="/admin/revision">Revisión</a>
            <a href="/logout">Salir</a>
          </div>
        </div>
      </nav>
      <img class="brand-strip" src="/images/banner-mapeo.jpeg" alt="NAE - Proyecto de cooperación internacional" />
      <main class="analytics-main">
        <div class="shell layout">
          {filters_html}
          {metrics}
          <section class="card wide"><div class="card-head"><p class="section-lead">Tendencia</p><h2>Respuestas enviadas por día</h2></div><div class="card-body">{_daily_chart(data.get('respuestas_por_dia', []))}</div></section>
          <section class="grid">
            <section class="card"><div class="card-head"><p class="section-lead">Calidad</p><h2>Estado de validación</h2></div><div class="card-body">{_donut_chart(data['por_estado'])}</div></section>
            <section class="card"><div class="card-head"><p class="section-lead">Cobertura</p><h2>Tipos de estructura</h2></div><div class="card-body">{_donut_chart(data['tipos_estructura'])}</div></section>
          </section>
          <section class="grid">
            <section class="card"><div class="card-head"><p class="section-lead">Territorio</p><h2>Provincias y municipios</h2></div><div class="card-body table-wrap">{_table(['provincia', 'municipio', 'total'], data['por_provincia'])}</div></section>
            <section class="card"><div class="card-head"><p class="section-lead">Atención</p><h2>Cobertura principal</h2></div><div class="card-body">{_bar_rows(data['cobertura'])}</div></section>
          </section>
          <section class="grid">
            <section class="card"><div class="card-head"><p class="section-lead">Servicios</p><h2>Servicios ofrecidos actualmente</h2></div><div class="card-body">{_bar_rows(data['servicios_ofrecidos'])}</div></section>
            <section class="card"><div class="card-head"><p class="section-lead">Brechas</p><h2>Servicios que requieren fortalecimiento</h2></div><div class="card-body">{_bar_rows(data['servicios_fortalecer'])}</div></section>
          </section>
          <section class="grid">
            <section class="card"><div class="card-head"><p class="section-lead">Beneficiarios</p><h2>Tipos de NAE atendidos</h2></div><div class="card-body tile-grid">{_tile_rows(data['tipos_nae'])}</div></section>
            <section class="card"><div class="card-head"><p class="section-lead">Capacidades</p><h2>Capacidades técnicas disponibles</h2></div><div class="card-body tile-grid">{_tile_rows(data['capacidades'])}</div></section>
          </section>
          <section class="grid">
            <section class="card"><div class="card-head"><p class="section-lead">Infraestructura</p><h2>Condiciones de conectividad</h2></div><div class="card-body">{_donut_chart(data['conectividad'])}</div></section>
            <section class="card"><div class="card-head"><p class="section-lead">Continuidad</p><h2>Sostenibilidad de servicios</h2></div><div class="card-body">{_donut_chart(data['sostenibilidad'])}</div></section>
          </section>
          <section class="grid">
            <section class="card"><div class="card-head"><p class="section-lead">Mapa</p><h2>Capacidad de actualizar información</h2></div><div class="card-body">{_bar_rows(data['actualizacion_mapa'])}</div></section>
            <section class="card"><div class="card-head"><p class="section-lead">Riesgos</p><h2>Limitaciones reportadas</h2></div><div class="card-body">{_bar_rows(data['limitaciones'])}</div></section>
          </section>
          <section class="card wide"><div class="card-head"><p class="section-lead">Detalle</p><h2>Últimas entidades procesadas</h2></div><div class="card-body table-wrap">{_table_with_links(['id', 'fecha_respuesta', 'estado_validacion', 'provincia_nombre', 'municipio_nombre', 'nombre_institucion', 'tipo_estructura', 'cobertura', 'actualizacion_mapa'], data['ultimas_respuestas'], 'id', '/respuestas/')}</div></section>
        </div>
      </main>
    </body>
    </html>
    """
    return html


