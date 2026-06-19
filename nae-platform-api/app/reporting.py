from __future__ import annotations

from html import escape
from typing import Any, Dict, List

from sqlalchemy import text

from app.database import SessionLocal


def get_dashboard_data(limit: int = 10) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        total = db.execute(text("SELECT COUNT(*) FROM analytics.f_respuestas_encuesta")).scalar_one()

        por_estado = db.execute(
            text("""
                SELECT e.estado_validacion AS label, COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
                GROUP BY e.estado_validacion
                ORDER BY total DESC, label ASC
            """)
        ).mappings().all()

        por_provincia = db.execute(
            text("""
                SELECT t.provincia_nombre AS provincia,
                       t.municipio_nombre AS municipio,
                       COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                GROUP BY t.provincia_nombre, t.municipio_nombre
                ORDER BY total DESC, provincia ASC, municipio ASC
            """)
        ).mappings().all()

        por_genero = db.execute(
            text("""
                SELECT COALESCE(g.genero, 'Sin dato') AS label, COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                GROUP BY COALESCE(g.genero, 'Sin dato')
                ORDER BY total DESC, label ASC
            """)
        ).mappings().all()

        por_nivel_instruccion = db.execute(
            text("""
                SELECT COALESCE(rg.nivel_instruccion, 'Sin dato') AS label, COUNT(*)::int AS total
                FROM analytics.f_respuestas_encuesta f
                LEFT JOIN analytics.dim_respuesta_genero rg ON rg.id = f.respuesta_genero_id
                GROUP BY COALESCE(rg.nivel_instruccion, 'Sin dato')
                ORDER BY total DESC, label ASC
            """)
        ).mappings().all()

        temas_formacion = db.execute(
            text("""
                SELECT rt.tema_formacion AS label, COUNT(*)::int AS total
                FROM operational.respuestas_temas_formacion rt
                GROUP BY rt.tema_formacion
                ORDER BY total DESC, label ASC
                LIMIT 10
            """)
        ).mappings().all()

        ultimas_respuestas = db.execute(
            text("""
                SELECT f.id,
                       f.version_encuesta,
                       f.fecha_respuesta,
                       f.consentimiento,
                       t.provincia_nombre,
                       t.municipio_nombre,
                       i.nombre_institucion,
                       e.estado_validacion,
                       COALESCE(g.genero, 'Sin dato') AS genero
                FROM analytics.f_respuestas_encuesta f
                JOIN analytics.dim_territorio t ON t.id = f.territorio_id
                JOIN analytics.dim_institucion i ON i.id = f.institucion_id
                JOIN analytics.dim_estado_validacion e ON e.id = f.estado_validacion_id
                LEFT JOIN analytics.dim_genero g ON g.id = f.genero_id
                ORDER BY f.id DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).mappings().all()

        return {
            "total_respuestas": int(total),
            "por_estado": [dict(row) for row in por_estado],
            "por_provincia": [dict(row) for row in por_provincia],
            "por_genero": [dict(row) for row in por_genero],
            "por_nivel_instruccion": [dict(row) for row in por_nivel_instruccion],
            "temas_formacion": [dict(row) for row in temas_formacion],
            "ultimas_respuestas": [dict(row) for row in ultimas_respuestas],
        }
    finally:
        db.close()


def render_dashboard_html(data: Dict[str, Any]) -> str:
    def render_table(title: str, rows: List[Dict[str, Any]], headers: List[str]) -> str:
        head = "".join(f"<th>{escape(header)}</th>" for header in headers)
        body_rows = []
        for row in rows:
            cells = "".join(f"<td>{escape('' if row.get(header) is None else str(row.get(header)))}</td>" for header in headers)
            body_rows.append(f"<tr>{cells}</tr>")
        body = "".join(body_rows) or f"<tr><td colspan='{len(headers)}'>Sin datos</td></tr>"
        return f"""
            <section class="card">
              <h2>{escape(title)}</h2>
              <table>
                <thead><tr>{head}</tr></thead>
                <tbody>{body}</tbody>
              </table>
            </section>
        """

    cards = f"""
        <section class="kpis">
          <div class="kpi"><span>Total respuestas</span><strong>{data['total_respuestas']}</strong></div>
          <div class="kpi"><span>Estados</span><strong>{len(data['por_estado'])}</strong></div>
          <div class="kpi"><span>Provincias</span><strong>{len(data['por_provincia'])}</strong></div>
          <div class="kpi"><span>Temas</span><strong>{len(data['temas_formacion'])}</strong></div>
        </section>
    """

    html_parts = [
        "<!doctype html>",
        "<html lang='es'>",
        "<head>",
        "<meta charset='utf-8' />",
        "<meta name='viewport' content='width=device-width, initial-scale=1' />",
        "<title>NAE Platform - Resumen</title>",
        "<style>",
        "body{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f5f7fb;color:#162033}",
        "header{padding:24px 28px;background:#102a43;color:#fff}",
        "main{padding:24px;display:grid;gap:18px}",
        ".kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}",
        ".kpi,.card{background:#fff;border:1px solid #d9e2ec;border-radius:8px;padding:16px}",
        ".kpi span{display:block;font-size:12px;color:#52606d;text-transform:uppercase;letter-spacing:0}",
        ".kpi strong{display:block;font-size:28px;margin-top:6px}",
        "table{width:100%;border-collapse:collapse}",
        "th,td{padding:8px 10px;border-bottom:1px solid #e4e7eb;text-align:left;font-size:14px;vertical-align:top}",
        "th{background:#f8fafc}",
        ".grid{display:grid;grid-template-columns:1fr;gap:18px}",
        "@media(min-width:1000px){.grid{grid-template-columns:1fr 1fr}}",
        "</style>",
        "</head>",
        "<body>",
        "<header><h1>NAE Platform - Resumen operativo</h1><p>Vista rápida de los datos ya cargados en analytics.</p></header>",
        "<main>",
        cards,
        "<div class='grid'>",
        render_table("Por estado", data["por_estado"], ["label", "total"]),
        render_table("Por provincia y municipio", data["por_provincia"], ["provincia", "municipio", "total"]),
        render_table("Por género", data["por_genero"], ["label", "total"]),
        render_table("Por nivel de instrucción", data["por_nivel_instruccion"], ["label", "total"]),
        render_table("Temas prioritarios", data["temas_formacion"], ["label", "total"]),
        render_table("Últimas respuestas", data["ultimas_respuestas"], ["id", "version_encuesta", "fecha_respuesta", "estado_validacion", "provincia_nombre", "municipio_nombre", "nombre_institucion", "genero"]),
        "</div>",
        "</main>",
        "</body></html>",
    ]
    return "".join(html_parts)
