from __future__ import annotations

import csv
from io import StringIO
from urllib.parse import urlencode
from html import escape
from typing import Any, Dict, List, Optional

from sqlalchemy import text

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
                       op.consentimiento,
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
                       op.mecanismos_coordinacion
                FROM analytics.f_respuestas_encuesta f
                JOIN operational.respuestas_encuesta op ON op.id = f.operational_respuesta_id
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                JOIN analytics.dim_institucion i ON i.id = f.institucion_id
                JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                LEFT JOIN analytics.dim_respuesta_genero rg ON rg.id = f.respuesta_genero_id
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

    return f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>NAE Platform - Respuesta {escape(str(data.get('respuesta_id')))}</title>
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
        header {{
          padding: 18px 24px;
          background: linear-gradient(180deg, var(--accent-deep) 0%, #133f7a 100%);
          color: #fff;
          border-bottom: 1px solid #0b2f5e;
        }}
        header h1 {{ margin: 0; font-size: 22px; line-height: 1.2; }}
        header p {{ margin: 6px 0 0; color: #dbeafe; font-size: 13px; }}
        main {{ padding: 24px; display: grid; gap: 18px; }}
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
      <header>
        <h1>Respuesta {value("respuesta_id")}</h1>
        <p>{value("provincia_nombre")} - {value("municipio_nombre")} - {value("nombre_institucion")}</p>
      </header>
      <main>
        <div class="nav">
          <a class="back" href="/">Volver al panel</a>
          {"<a href='/respuestas/" + str(data["previous_id"]) + "'>Anterior</a>" if data.get("previous_id") else "<a class='disabled' href='#'>Anterior</a>"}
          {"<a href='/respuestas/" + str(data["next_id"]) + "'>Siguiente</a>" if data.get("next_id") else "<a class='disabled' href='#'>Siguiente</a>"}
        </div>
        <section class="card">
          <div class="grid">
            <div class="field"><span>Estado</span><strong>{value("estado_validacion")}</strong></div>
            <div class="field"><span>Versión</span><strong>{value("version_encuesta")}</strong></div>
            <div class="field"><span>Provincia</span><strong>{value("provincia_nombre")}</strong></div>
            <div class="field"><span>Municipio</span><strong>{value("municipio_nombre")}</strong></div>
            <div class="field"><span>Institución</span><strong>{value("nombre_institucion")}</strong></div>
            <div class="field"><span>Tipo de institución</span><strong>{value("tipo_institucion")}</strong></div>
            <div class="field"><span>Género</span><strong>{value("genero")}</strong></div>
            <div class="field"><span>Nivel de instrucción</span><strong>{value("nivel_instruccion")}</strong></div>
          </div>
        </section>
        <section class="card">
          <div class="grid">
            <div class="field"><span>Consentimiento</span><strong>{value("consentimiento")}</strong></div>
            <div class="field"><span>Ámbito</span><strong>{value("ambito_actuacion")}</strong></div>
            <div class="field"><span>Nivel involucramiento</span><strong>{value("nivel_involucramiento")}</strong></div>
            <div class="field"><span>Capacitación formadores</span><strong>{value("nivel_capacitacion_formadores")}</strong></div>
            <div class="field"><span>Principal necesidad</span><strong>{value("principal_necesidad")}</strong></div>
            <div class="field"><span>Interés gobierno</span><strong>{value("nivel_interes_gobierno")}</strong></div>
            <div class="field"><span>Mecanismos coordinación</span><strong>{value("mecanismos_coordinacion")}</strong></div>
            <div class="field"><span>Conocimiento municipio</span><strong>{value("nivel_conocimiento_municipio")}</strong></div>
          </div>
        </section>
        <section class="card">
          <h2>Temas prioritarios</h2>
          {pill_list(data.get("temas_formacion", []))}
        </section>
        <section class="card">
          <h2>Instituciones participantes</h2>
          {pill_list(data.get("instituciones_participantes", []))}
        </section>
        <section class="card">
          <h2>Limitaciones</h2>
          {pill_list(data.get("limitaciones", []))}
        </section>
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
    export_params = {
        key: value
        for key, value in {
            "provincia": selected.get("provincia"),
            "version_encuesta": selected.get("version_encuesta"),
            "genero": selected.get("genero"),
            "tema": selected.get("tema"),
            "limit": selected.get("limit") or 10,
        }.items()
        if value not in (None, "")
    }
    export_url = "/api/v1/resumen.csv"
    if export_params:
        export_url = f"{export_url}?{urlencode(export_params)}"

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
            <a class="export-inline" href="{escape(export_url)}">Exportar CSV</a>
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
