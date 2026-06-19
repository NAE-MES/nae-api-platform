from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.database import SessionLocal


HEADER_BANNER_PATH = Path(__file__).resolve().parents[2] / "images" / "Baner NAE (Google Forms).png"


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


def _load_header_banner() -> Optional[str]:
    if not HEADER_BANNER_PATH.exists():
        return None
    return base64.b64encode(HEADER_BANNER_PATH.read_bytes()).decode("ascii")


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


def render_dashboard_html(data: Dict[str, Any]) -> str:
    lookups = data["lookups"]
    selected = data["filters"]
    banner_data = _load_header_banner()

    def option_list(values: List[str], selected_value: Optional[str]) -> str:
        options = ['<option value="">Todos</option>']
        for value in values:
            mark = " selected" if value == selected_value else ""
            options.append(f"<option value='{escape(value)}'{mark}>{escape(value)}</option>")
        return "".join(options)

    filters_html = f"""
        <form class="filters" method="get" action="/">
          <label>Provincia
            <select name="provincia">{option_list(lookups["provincias"], selected.get("provincia"))}</select>
          </label>
          <label>Versión
            <select name="version_encuesta">{option_list(lookups["versiones"], selected.get("version_encuesta"))}</select>
          </label>
          <label>Género
            <select name="genero">{option_list(lookups["generos"], selected.get("genero"))}</select>
          </label>
          <label>Tema
            <select name="tema">{option_list(lookups["temas"], selected.get("tema"))}</select>
          </label>
          <label>Límite
            <input type="number" name="limit" min="1" max="50" value="{escape(str(selected.get('limit') or 10))}" />
          </label>
          <div class="filter-actions">
            <button type="submit">Aplicar</button>
            <a href="/">Limpiar</a>
          </div>
        </form>
    """

    metrics = f"""
        <section class="kpis">
          <div class="kpi"><span>Total respuestas</span><strong>{data['total_respuestas']}</strong></div>
          <div class="kpi"><span>Estados</span><strong>{len(data['por_estado'])}</strong></div>
          <div class="kpi"><span>Provincias</span><strong>{len(data['por_provincia'])}</strong></div>
          <div class="kpi"><span>Temas</span><strong>{len(data['temas_formacion'])}</strong></div>
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
          --bg: #f5f7fb;
          --panel: #ffffff;
          --line: #d9e2ec;
          --text: #102a43;
          --muted: #627d98;
          --accent: #1d4ed8;
          --accent-soft: #dbeafe;
        }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); }}
        header {{ padding: 24px 28px; background: #102a43; color: #fff; }}
        header h1 {{ margin: 0 0 8px; font-size: 28px; }}
        header p {{ margin: 0; color: #d9e2ec; }}
        .banner {{
          width: 100%;
          max-width: 1600px;
          height: auto;
          display: block;
          border-radius: 8px;
          margin: 0 0 18px;
        }}
        main {{ padding: 24px; display: grid; gap: 18px; }}
        .filters {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 12px;
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: 16px;
        }}
        .filters label {{ display: grid; gap: 6px; font-size: 12px; color: var(--muted); text-transform: uppercase; }}
        .filters select, .filters input {{
          width: 100%;
          padding: 10px 12px;
          border: 1px solid var(--line);
          border-radius: 8px;
          background: #fff;
          color: var(--text);
        }}
        .filter-actions {{ display: flex; gap: 10px; align-items: end; }}
        .filter-actions button, .filter-actions a {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 40px;
          padding: 0 14px;
          border-radius: 8px;
          text-decoration: none;
          font-size: 14px;
          border: 1px solid var(--line);
        }}
        .filter-actions button {{
          background: var(--accent);
          color: #fff;
          border-color: var(--accent);
        }}
        .filter-actions a {{ color: var(--text); background: #fff; }}
        .kpis {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 12px;
        }}
        .kpi, .card {{
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: 16px;
        }}
        .kpi span {{ display: block; font-size: 12px; color: var(--muted); text-transform: uppercase; }}
        .kpi strong {{ display: block; font-size: 28px; margin-top: 6px; }}
        .grid {{ display: grid; grid-template-columns: 1fr; gap: 18px; }}
        @media(min-width: 1100px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
        .card h2 {{ margin: 0 0 12px; font-size: 16px; }}
        .bar-row {{
          display: grid;
          grid-template-columns: minmax(140px, 1.3fr) minmax(160px, 2fr) 48px;
          gap: 10px;
          align-items: center;
          margin: 8px 0;
        }}
        .bar-label, .bar-value {{ font-size: 13px; }}
        .bar-track {{ height: 12px; background: #edf2f7; border-radius: 999px; overflow: hidden; }}
        .bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent), #60a5fa); border-radius: 999px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #e4e7eb; text-align: left; font-size: 14px; vertical-align: top; }}
        th {{ background: #f8fafc; }}
        .empty {{ color: var(--muted); margin: 0; }}
        .wide {{ grid-column: 1 / -1; }}
        .subgrid {{ display: grid; grid-template-columns: 1fr; gap: 18px; }}
        @media(min-width: 1100px) {{ .subgrid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
      </style>
    </head>
    <body>
      <header>
        {f'<img class="banner" src="data:image/png;base64,{banner_data}" alt="Banner NAE" />' if banner_data else ''}
        <h1>NAE Platform - Panel operativo</h1>
        <p>Resumen filtrable de respuestas cargadas en analytics y operational.</p>
      </header>
      <main>
        {filters_html}
        {metrics}
        <div class="grid">
          <section class="card">
            <h2>Estados</h2>
            {_bar_rows(data["por_estado"])}
          </section>
          <section class="card">
            <h2>Género</h2>
            {_bar_rows(data["por_genero"])}
          </section>
          <section class="card">
            <h2>Nivel de instrucción</h2>
            {_bar_rows(data["por_nivel_instruccion"])}
          </section>
          <section class="card">
            <h2>Provincias y municipios</h2>
            {_table(["provincia", "municipio", "total"], data["por_provincia"])}
          </section>
          <section class="card">
            <h2>Temas prioritarios</h2>
            {_bar_rows(data["temas_formacion"])}
          </section>
          <section class="card">
            <h2>Limitaciones</h2>
            {_bar_rows(data["limitaciones"])}
          </section>
          <section class="card wide">
            <h2>Instituciones más presentes</h2>
            {_bar_rows(data["instituciones"])}
          </section>
          <section class="card wide">
            <h2>Últimas respuestas</h2>
            {_table(["id", "version_encuesta", "fecha_respuesta", "estado_validacion", "provincia_nombre", "municipio_nombre", "nombre_institucion", "genero", "nivel_instruccion"], data["ultimas_respuestas"])}
          </section>
        </div>
      </main>
    </body>
    </html>
    """
    return html
