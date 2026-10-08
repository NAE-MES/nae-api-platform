from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import quote

from dotenv import load_dotenv


API_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_DIR.parent
sys.path.insert(0, str(API_DIR))

load_dotenv(API_DIR / ".env")

from app.mapeo_survey import SERVICIOS_GRID_ROWS  # noqa: E402
from app.reporting import SERVICE_ICON_FILES, _service_icon_key, get_support_entities  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "reportes" / "mapa_exportable" / "mapa_entidades_apoyo.html"
LEAFLET_CSS = PROJECT_ROOT / "prototype" / "vendor" / "leaflet" / "leaflet.css"
LEAFLET_JS = PROJECT_ROOT / "prototype" / "vendor" / "leaflet" / "leaflet.js"
SERVICE_ICON_DIR = PROJECT_ROOT / "prototype" / "icons" / "services"


def _clean_text(value: Any, default: str = "Sin dato") -> str:
    text = " ".join(str(value or "").split())
    return text or default


def _entity_id(row: Dict[str, Any]) -> str:
    return str(row.get("entidad_apoyo_id") or row.get("operational_respuesta_id") or "")


def _normalize_entities(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    for row in rows:
        lat = row.get("lat")
        lng = row.get("lng")
        if lat is None or lng is None:
            continue

        services = _clean_text(row.get("servicios"), "Sin servicios registrados")
        entities.append(
            {
                "id": _entity_id(row),
                "name": _clean_text(row.get("entidad_nombre"), "Sin nombre"),
                "type": _clean_text(row.get("tipo_estructura_apoyo"), "Sin tipo"),
                "province": _clean_text(row.get("provincia"), "Sin provincia"),
                "municipality": _clean_text(row.get("municipio"), "Sin municipio"),
                "coverage": _clean_text(
                    row.get("cobertura_descriptiva") or row.get("cobertura_principal"),
                    "Sin dato",
                ),
                "services": services,
                "serviceList": [item.strip() for item in services.split(",") if item.strip()],
                "contact": _clean_text(row.get("persona_contacto_cargo")),
                "phone": _clean_text(row.get("telefonos"), "Sin telefono"),
                "email": _clean_text(row.get("correo_electronico"), "Sin correo"),
                "address": _clean_text(row.get("direccion_fisica")),
                "lat": float(lat),
                "lng": float(lng),
                "source": _clean_text(row.get("coordinate_source"), "municipio"),
                "status": _clean_text(row.get("coordinate_status"), "estimada"),
            }
        )
    return entities


def _unique(values: Iterable[str]) -> List[str]:
    return sorted({value for value in values if value and value != "Sin dato"})


def _load_service_icons(services: Iterable[str]) -> Dict[str, str]:
    icons: Dict[str, str] = {}
    for service in services:
        icon_key = _service_icon_key(service)
        icon_file = SERVICE_ICON_FILES.get(icon_key, SERVICE_ICON_FILES["otro"])
        icon_path = SERVICE_ICON_DIR / icon_file
        if not icon_path.exists():
            icon_path = SERVICE_ICON_DIR / SERVICE_ICON_FILES["otro"]
        svg = icon_path.read_text(encoding="utf-8")
        icons[service] = f"data:image/svg+xml;utf8,{quote(svg)}"
    return icons


def build_static_map_html(data: Dict[str, Any]) -> str:
    entities = _normalize_entities(data.get("entidades", []))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    leaflet_css = LEAFLET_CSS.read_text(encoding="utf-8")
    leaflet_js = LEAFLET_JS.read_text(encoding="utf-8")
    canonical_services = list(SERVICIOS_GRID_ROWS)
    all_services = _unique(set(canonical_services) | {service for entity in entities for service in entity["serviceList"]})
    payload = json.dumps(
        {
            "generatedAt": generated_at,
            "total": len(entities),
            "entities": entities,
            "lookups": {
                "provinces": _unique(entity["province"] for entity in entities),
                "municipalities": _unique(entity["municipality"] for entity in entities),
                "types": _unique(entity["type"] for entity in entities),
                "services": canonical_services,
            },
            "serviceIcons": _load_service_icons(all_services),
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Mapa exportable - Entidades de apoyo a los NAE</title>
    <style>
{leaflet_css}
      :root {{
        --blue: #173b75;
        --blue-2: #0f2d5b;
        --red: #c8142f;
        --ink: #102033;
        --muted: #5c6b7c;
        --line: #d9e1ea;
        --paper: #f4f7fb;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: Calibri, "Segoe UI", Arial, sans-serif; color: var(--ink); background: var(--paper); }}
      header {{ background: #fff; border-bottom: 1px solid var(--line); }}
      .wrap {{ max-width: 1320px; margin: 0 auto; padding: 0 24px; }}
      .top {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 18px 0; }}
      h1 {{ margin: 0; color: var(--blue); font-size: 26px; line-height: 1.15; }}
      .subtitle {{ margin: 4px 0 0; color: var(--muted); font-size: 14px; }}
      .badge {{ border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; color: var(--blue-2); font-weight: 700; background: #f8fbff; white-space: nowrap; }}
      main {{ padding: 20px 0 32px; }}
      .panel {{ background: #fff; border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 14px 34px rgba(14, 31, 56, .08); }}
      .filters {{ display: grid; grid-template-columns: 1.5fr repeat(4, minmax(150px, 1fr)) auto; gap: 10px; padding: 14px; border-bottom: 1px solid var(--line); }}
      input, select, button {{ min-height: 38px; border-radius: 8px; border: 1px solid var(--line); padding: 0 10px; font: inherit; background: #fff; }}
      button {{ cursor: pointer; border-color: var(--blue); background: var(--blue); color: #fff; font-weight: 700; }}
      button.secondary {{ background: #fff; color: var(--blue); }}
      #map {{ height: min(68vh, 680px); min-height: 520px; background: #d8e8f1; }}
      #map .leaflet-tile-pane {{ filter: contrast(1.08) saturate(1.04) brightness(.99); }}
      .summary {{ display: flex; justify-content: space-between; gap: 16px; padding: 12px 14px; border-top: 1px solid var(--line); color: var(--muted); font-size: 14px; }}
      .nae-marker {{ position: relative; display: block; width: 24px; height: 24px; background: var(--red); border: 3px solid #fff; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-shadow: 0 9px 18px rgba(15,23,42,.30), 0 0 0 5px rgba(200,20,47,.18); }}
      .nae-marker::after {{ content: ""; position: absolute; width: 8px; height: 8px; left: 5px; top: 5px; border-radius: 999px; background: #fff; }}
      .popup h3 {{ margin: 0 0 6px; color: var(--blue); font-size: 17px; }}
      .popup p {{ margin: 4px 0; font-size: 13px; }}
      .popup .services {{ max-height: 90px; overflow-y: auto; padding-right: 4px; }}
      .popup-services-title {{ margin-top: 8px; color: #000; font-size: 12px; font-weight: 800; }}
      .popup-services-grid {{ display: grid; grid-template-columns: repeat(10, 28px); gap: 4px; align-items: center; margin-top: 5px; }}
      .service-icons {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
      .service-icon {{ width: 26px; height: 26px; display: inline-flex; align-items: center; justify-content: center; border: 2px solid #B55E36; border-radius: 4px; background: #fff; padding: 3px; }}
      .service-icon img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
      .service-icon.more {{ color: var(--blue); font-size: 11px; font-weight: 800; }}
      .map-legend {{ border-top: 1px solid var(--line); background: #fff; padding: 12px 14px 14px; }}
      .map-legend h2 {{ margin: 0; color: #000; font-size: 21px; line-height: 1; text-transform: uppercase; }}
      .map-legend .legend-subtitle {{ color: #B55E36; font-size: 14px; font-weight: 700; margin: 4px 0 8px; }}
      .legend-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px 18px; }}
      .legend-item {{ display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 6px; align-items: center; min-width: 0; color: #000; font-size: 13px; line-height: 1.2; }}
      .legend-item span {{ overflow-wrap: anywhere; }}
      .list-head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 18px 0 10px; }}
      .list-head h2 {{ margin: 0; color: var(--blue); font-size: 20px; }}
      .list {{ display: grid; gap: 10px; }}
      .card {{ background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 14px; }}
      .card h3 {{ margin: 0 0 5px; color: var(--blue-2); font-size: 17px; }}
      .card p {{ margin: 5px 0; color: #26384d; }}
      .card details {{ margin-top: 8px; }}
      .card summary {{ cursor: pointer; color: var(--blue); font-weight: 800; }}
      .card-actions {{ margin-top: 10px; }}
      .pager {{ display: flex; justify-content: center; gap: 8px; align-items: center; margin-top: 14px; }}
      .pager span {{ min-width: 120px; text-align: center; color: var(--muted); }}
      @media (max-width: 980px) {{
        .filters {{ grid-template-columns: 1fr 1fr; }}
        .filters input {{ grid-column: 1 / -1; }}
        .legend-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      }}
      @media (max-width: 620px) {{
        .wrap {{ padding: 0 14px; }}
        .top, .summary, .list-head {{ flex-direction: column; align-items: flex-start; }}
        .filters {{ grid-template-columns: 1fr; }}
        #map {{ min-height: 460px; }}
        .legend-grid {{ grid-template-columns: 1fr; }}
        .popup-services-grid {{ grid-template-columns: repeat(6, 28px); }}
      }}
    </style>
  </head>
  <body>
    <header>
      <div class="wrap top">
        <div>
          <h1>Mapa de Entidades de Apoyo a NAE</h1>
          <p class="subtitle">Versión exportable generada desde la base de datos de la plataforma.</p>
        </div>
        <div class="badge">Generado: {escape(generated_at)}</div>
      </div>
    </header>
    <main class="wrap">
      <section class="panel">
        <div class="filters">
          <input id="q" type="search" placeholder="Buscar por nombre, servicio, contacto o municipio" />
          <select id="province"></select>
          <select id="municipality"></select>
          <select id="type"></select>
          <select id="service"></select>
          <button id="clear" type="button" class="secondary">Limpiar</button>
        </div>
        <div id="map"></div>
        <div class="summary">
          <span id="result-count">0 entidades visibles</span>
          <span>Los marcadores usan coordenadas validadas cuando existen; si no, ubicación municipal estimada.</span>
        </div>
        <div class="map-legend" aria-label="Leyenda de servicios">
          <h2>Leyenda</h2>
          <div class="legend-subtitle">Servicios registrados:</div>
          <div id="service-legend" class="legend-grid"></div>
        </div>
      </section>
      <section>
        <div class="list-head">
          <h2>Entidades</h2>
          <span id="page-info"></span>
        </div>
        <div id="list" class="list"></div>
        <div class="pager">
          <button id="prev" class="secondary" type="button">Anterior</button>
          <span id="pager-label"></span>
          <button id="next" class="secondary" type="button">Siguiente</button>
        </div>
      </section>
    </main>
    <script>
{leaflet_js}
    </script>
    <script>
      const payload = {payload};
      const pageSize = 10;
      let currentPage = 1;
      let filtered = [...payload.entities];
      let markers = new Map();

      const map = L.map('map', {{ zoomControl: true }}).setView([21.9, -79.5], 7);
      const tileProviders = [
        {{
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}',
          attribution: 'Tiles &copy; Esri'
        }},
        {{
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}',
          attribution: 'Tiles &copy; Esri'
        }},
        {{
          url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}',
          attribution: 'Tiles &copy; Esri'
        }},
        {{
          url: 'https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
          attribution: '&copy; OpenStreetMap contributors'
        }}
      ];
      let tileProviderIndex = 0;
      let tileLayer = null;
      function addTileLayer(index) {{
        if (tileLayer) {{
          map.removeLayer(tileLayer);
        }}
        const provider = tileProviders[index];
        tileLayer = L.tileLayer(provider.url, {{
          maxZoom: 18,
          attribution: provider.attribution
        }});
        tileLayer.on('tileerror', () => {{
          if (tileProviderIndex < tileProviders.length - 1) {{
            tileProviderIndex += 1;
            addTileLayer(tileProviderIndex);
          }}
        }});
        tileLayer.addTo(map);
      }}
      addTileLayer(tileProviderIndex);
      const markerLayer = L.layerGroup().addTo(map);
      const markerIcon = L.divIcon({{ className: '', html: '<span class="nae-marker"></span>', iconSize: [24, 24], iconAnchor: [12, 24], popupAnchor: [0, -24] }});

      const els = {{
        q: document.getElementById('q'),
        province: document.getElementById('province'),
        municipality: document.getElementById('municipality'),
        type: document.getElementById('type'),
        service: document.getElementById('service'),
        clear: document.getElementById('clear'),
        count: document.getElementById('result-count'),
        list: document.getElementById('list'),
        pageInfo: document.getElementById('page-info'),
        pager: document.getElementById('pager-label'),
        prev: document.getElementById('prev'),
        next: document.getElementById('next'),
      }};

      function escapeHtml(value) {{
        return String(value ?? '').replace(/[&<>"']/g, (ch) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[ch]));
      }}
      function optionList(items, label) {{
        return `<option value="">${{label}}</option>` + items.map((item) => `<option value="${{escapeHtml(item)}}">${{escapeHtml(item)}}</option>`).join('');
      }}
      function serviceIcon(service) {{
        const src = payload.serviceIcons[service];
        if (!src) return '';
        return `<span class="service-icon" title="${{escapeHtml(service)}}"><img src="${{src}}" alt="" /></span>`;
      }}
      function serviceIconStrip(entity, limit = 8) {{
        const icons = entity.serviceList.slice(0, limit).map(serviceIcon).join('');
        const remaining = entity.serviceList.length - limit;
        return `<div class="service-icons">${{icons}}${{remaining > 0 ? `<span class="service-icon more" title="${{remaining}} servicios adicionales">+${{remaining}}</span>` : ''}}</div>`;
      }}
      function serviceIconGrid(entity) {{
        const icons = entity.serviceList.map(serviceIcon).filter(Boolean).join('');
        return icons || `<span>${{escapeHtml(entity.services || 'Sin servicios registrados')}}</span>`;
      }}
      function textMatch(entity, q) {{
        if (!q) return true;
        const haystack = [entity.name, entity.type, entity.province, entity.municipality, entity.coverage, entity.services, entity.contact, entity.phone, entity.email, entity.address].join(' ').toLocaleLowerCase('es');
        return haystack.includes(q.toLocaleLowerCase('es'));
      }}
      function matches(entity) {{
        return textMatch(entity, els.q.value.trim())
          && (!els.province.value || entity.province === els.province.value)
          && (!els.municipality.value || entity.municipality === els.municipality.value)
          && (!els.type.value || entity.type === els.type.value)
          && (!els.service.value || entity.serviceList.includes(els.service.value));
      }}
      function popupHtml(entity) {{
        return `<div class="popup">
          <h3>${{escapeHtml(entity.name)}}</h3>
          <p><b>Tipo:</b> ${{escapeHtml(entity.type)}}</p>
          <p><b>Ubicación:</b> ${{escapeHtml(entity.province)}} / ${{escapeHtml(entity.municipality)}}</p>
          <p><b>Cobertura:</b> ${{escapeHtml(entity.coverage)}}</p>
          <div class="popup-services-title">Servicios registrados:</div>
          <div class="popup-services-grid">${{serviceIconGrid(entity)}}</div>
          <p><b>Contacto:</b> ${{escapeHtml(entity.contact)}} · ${{escapeHtml(entity.phone)}} · ${{escapeHtml(entity.email)}}</p>
          <p><b>Dirección:</b> ${{escapeHtml(entity.address)}}</p>
        </div>`;
      }}
      function focusEntity(id) {{
        const marker = markers.get(String(id));
        if (!marker) return;
        map.setView(marker.getLatLng(), Math.max(map.getZoom(), 12), {{ animate: true }});
        marker.openPopup();
        window.scrollTo({{ top: document.getElementById('map').getBoundingClientRect().top + window.scrollY - 12, behavior: 'smooth' }});
      }}
      function renderMarkers() {{
        markerLayer.clearLayers();
        markers = new Map();
        filtered.forEach((entity) => {{
          const marker = L.marker([entity.lat, entity.lng], {{ icon: markerIcon }}).bindPopup(popupHtml(entity), {{ maxWidth: 360 }});
          marker.addTo(markerLayer);
          markers.set(String(entity.id), marker);
        }});
        if (filtered.length) {{
          const bounds = L.latLngBounds(filtered.map((entity) => [entity.lat, entity.lng]));
          map.fitBounds(bounds.pad(0.14), {{ maxZoom: 9 }});
        }} else {{
          map.setView([21.9, -79.5], 7);
        }}
      }}
      function renderList() {{
        const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
        currentPage = Math.min(currentPage, pages);
        const start = (currentPage - 1) * pageSize;
        const items = filtered.slice(start, start + pageSize);
        els.list.innerHTML = items.map((entity) => `<article class="card">
          <h3>${{escapeHtml(entity.name)}}</h3>
          <p>${{escapeHtml(entity.province)}} · ${{escapeHtml(entity.municipality)}}</p>
          <p><strong>Tipo:</strong> ${{escapeHtml(entity.type)}}</p>
          <p><strong>Cobertura:</strong> ${{escapeHtml(entity.coverage)}}</p>
          <p><strong>Contacto:</strong> ${{escapeHtml(entity.contact)}} · ${{escapeHtml(entity.phone)}} · ${{escapeHtml(entity.email)}}</p>
          <details><summary>Servicios</summary><p>${{escapeHtml(entity.services)}}</p></details>
          <div class="card-actions"><button class="secondary" type="button" data-focus="${{escapeHtml(entity.id)}}">Ver en mapa</button></div>
        </article>`).join('') || '<article class="card"><h3>Sin resultados</h3><p>No hay entidades para los filtros aplicados.</p></article>';
        els.count.textContent = `${{filtered.length}} entidades visibles`;
        els.pageInfo.textContent = filtered.length ? `Mostrando ${{start + 1}}-${{Math.min(start + pageSize, filtered.length)}} de ${{filtered.length}}` : '';
        els.pager.textContent = `Página ${{currentPage}} de ${{pages}}`;
        els.prev.disabled = currentPage <= 1;
        els.next.disabled = currentPage >= pages;
        els.list.querySelectorAll('[data-focus]').forEach((button) => button.addEventListener('click', () => focusEntity(button.dataset.focus)));
      }}
      function applyFilters(resetPage = true) {{
        if (resetPage) currentPage = 1;
        filtered = payload.entities.filter(matches);
        renderMarkers();
        renderList();
      }}
      els.province.innerHTML = optionList(payload.lookups.provinces, 'Todas las provincias');
      els.municipality.innerHTML = optionList(payload.lookups.municipalities, 'Todos los municipios');
      els.type.innerHTML = optionList(payload.lookups.types, 'Todos los tipos');
      els.service.innerHTML = optionList(payload.lookups.services, 'Todos los servicios');
      document.getElementById('service-legend').innerHTML = payload.lookups.services.map((service) => `<div class="legend-item">${{serviceIcon(service)}}<span>${{escapeHtml(service)}}</span></div>`).join('');
      [els.q, els.province, els.municipality, els.type, els.service].forEach((el) => el.addEventListener('input', () => applyFilters(true)));
      els.clear.addEventListener('click', () => {{
        [els.q, els.province, els.municipality, els.type, els.service].forEach((el) => el.value = '');
        applyFilters(true);
      }});
      els.prev.addEventListener('click', () => {{ currentPage -= 1; renderList(); }});
      els.next.addEventListener('click', () => {{ currentPage += 1; renderList(); }});
      applyFilters(true);
    </script>
  </body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta el mapa de entidades NAE como HTML estatico.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Ruta del HTML a generar.")
    parser.add_argument("--limit", type=int, default=1000, help="Cantidad maxima de entidades a exportar.")
    args = parser.parse_args()

    data = get_support_entities(limit=args.limit)
    html = build_static_map_html(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"HTML generado: {args.output}")
    print(f"Entidades exportadas: {len(_normalize_entities(data.get('entidades', [])))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
