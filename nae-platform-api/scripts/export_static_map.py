from __future__ import annotations

import argparse
import base64
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
from app.reporting import SERVICE_ICON_FILES, _service_icon_key, _support_service_details, get_support_entities  # noqa: E402


DEFAULT_OUTPUT = PROJECT_ROOT / "reportes" / "mapa_exportable" / "mapa_entidades_apoyo.html"
LEAFLET_CSS = PROJECT_ROOT / "prototype" / "vendor" / "leaflet" / "leaflet.css"
LEAFLET_JS = PROJECT_ROOT / "prototype" / "vendor" / "leaflet" / "leaflet.js"
SERVICE_ICON_DIR = PROJECT_ROOT / "prototype" / "icons" / "services"
BANNER_DESKTOP = PROJECT_ROOT / "images" / "mapeo" / "banner_desktop.webp"
BANNER_MOBILE = PROJECT_ROOT / "images" / "mapeo" / "banner_movil.webp"
IDENTIFIER_DESKTOP = PROJECT_ROOT / "images" / "mapeo" / "identificador_desktop.svg"
IDENTIFIER_MOBILE = PROJECT_ROOT / "images" / "mapeo" / "identificador_movil.svg"


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
        service_details = _support_service_details(row)
        service_list = [item["name"] for item in service_details if not item.get("is_other")]
        other_services = [item["name"] for item in service_details if item.get("is_other")]
        if not service_list and not other_services and services != "Sin servicios registrados":
            other_services = [services]
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
                "serviceList": service_list,
                "otherServices": other_services,
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


def _asset_data_uri(path: Path, mime_type: str) -> str:
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{content}"


def build_static_map_html(data: Dict[str, Any], streets_sample: bool = False, national_streets: bool = False) -> str:
    entities = _normalize_entities(data.get("entidades", []))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    leaflet_css = LEAFLET_CSS.read_text(encoding="utf-8")
    leaflet_js = LEAFLET_JS.read_text(encoding="utf-8")
    popup_js = (PROJECT_ROOT / "prototype" / "map-popup.js").read_text(encoding="utf-8")
    basemap_js = (PROJECT_ROOT / "prototype" / "offline-basemap.js").read_text(encoding="utf-8")
    maps_dir = PROJECT_ROOT / "prototype" / "maps"
    cartography = {
        "provinces": json.loads((maps_dir / "cuba-provincias.geojson").read_text(encoding="utf-8")),
        "municipalities": json.loads((maps_dir / "cuba-municipios.geojson").read_text(encoding="utf-8")),
    }
    inflate_js = ""
    streets_loader = ""
    if national_streets:
        vendor_dir = PROJECT_ROOT / "prototype" / "vendor" / "pako"
        notices = "\n\n".join((vendor_dir / name).read_text(encoding="utf-8") for name in ("LICENSE", "LICENSE.zlib"))
        inflate_js = "/*\n" + notices + "\n*/\n" + (vendor_dir / "pako_inflate.min.js").read_text(encoding="utf-8")
        compressed = base64.b64encode((maps_dir / "calles-cuba.geojson.gz").read_bytes()).decode("ascii")
        streets_loader = f"offlineCartography.streets = JSON.parse(pako.ungzip(Uint8Array.from(atob('{compressed}'), c => c.charCodeAt(0)), {{to: 'string'}}));"
    elif streets_sample:
        cartography["streets"] = json.loads((maps_dir / "muestra-calles-habana.geojson").read_text(encoding="utf-8"))
    if national_streets or streets_sample:
        cartography["places"] = json.loads((maps_dir / "poblaciones-cuba.geojson").read_text(encoding="utf-8"))
    cartography_json = json.dumps(cartography, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    map_variant = "Calles y carreteras de Cuba" if national_streets else ("Detalle de calles: La Habana (muestra)" if streets_sample else "Cartografía territorial de Cuba")
    banner_desktop = _asset_data_uri(BANNER_DESKTOP, "image/webp")
    banner_mobile = _asset_data_uri(BANNER_MOBILE, "image/webp")
    identifier_desktop = _asset_data_uri(IDENTIFIER_DESKTOP, "image/svg+xml")
    identifier_mobile = _asset_data_uri(IDENTIFIER_MOBILE, "image/svg+xml")
    canonical_services = list(SERVICIOS_GRID_ROWS)
    legend_services = canonical_services + ["Otro servicio"]
    all_services = _unique(
        set(legend_services)
        | {service for entity in entities for service in entity["serviceList"]}
        | {service for entity in entities for service in entity["otherServices"]}
    )
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
                "legendServices": legend_services,
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
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; base-uri 'none';" />
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
      .wrap {{ max-width: min(1600px, calc(100vw - 32px)); margin: 0 auto; padding: 0; }}
      .top {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 18px 0; }}
      .brand-id {{ display:block; width:230px; max-width:32vw; height:auto; }}
      .hero-banner {{ display:block; width:100%; height:auto; background:#203747; }}
      .page-title {{ padding: 28px 0 18px; }}
      .eyebrow {{ margin:0 0 8px; color:#3A8DB8; font-size:13px; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }}
      h1 {{ margin: 0; color: var(--blue); font-size: 26px; line-height: 1.15; }}
      .subtitle {{ margin: 10px 0 0; color: var(--muted); font-size: 15px; max-width:760px; }}
      .badge {{ border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; color: var(--blue-2); font-weight: 700; background: #f8fbff; white-space: nowrap; }}
      main {{ padding: 20px 0 32px; }}
      .panel {{ background: #fff; border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 14px 34px rgba(14, 31, 56, .08); }}
      .filters {{ display: grid; grid-template-columns: minmax(0,1.5fr) repeat(4, minmax(0,1fr)) auto; min-width:0; gap: 10px; padding: 14px; border-bottom: 1px solid var(--line); }}
      .filters > * {{ min-width:0; }}
      .filters input, .filters select {{ display:block; width:100%; max-width:100%; min-width:0; }}
      input, select, button {{ min-height: 38px; border-radius: 8px; border: 1px solid var(--line); padding: 0 10px; font: inherit; background: #fff; }}
      button {{ cursor: pointer; border-color: var(--blue); background: var(--blue); color: #fff; font-weight: 700; }}
      button.secondary {{ background: #fff; color: var(--blue); }}
      #map {{ height: min(68vh, 680px); min-height: 520px; background: #d8e8f1; }}
      #map .leaflet-tile-pane {{ filter: contrast(1.08) saturate(1.04) brightness(.99); }}
      .offline-label {{ border:0; background:transparent; pointer-events:none; }}
      .offline-label span {{ display:block; width:max-content; max-width:150px; transform:translate(-50%,-50%); text-align:center; color:#354a42; font-size:12px; font-weight:700; line-height:1.1; text-shadow:1px 1px 2px #fff,-1px -1px 2px #fff; }}
      .municipality-label span {{ font-size:11px; font-weight:400; }}
      .place-label span {{ font-size:12px; font-weight:700; }}
      .road-label span {{ color:#64615b; font-size:10px; font-weight:400; }}
      .summary {{ display: flex; justify-content: space-between; align-items:center; gap: 16px; padding: 12px 14px; border-top: 1px solid var(--line); color: var(--muted); font-size: 14px; }}
      .summary-text {{ display:flex; flex-direction:column; gap:4px; }}
      .reset-map {{ min-height:34px; padding:0 12px; white-space:nowrap; }}
      .nae-marker {{ position: relative; display: block; width: 24px; height: 24px; background: var(--red); border: 3px solid #fff; border-radius: 50% 50% 50% 0; transform: rotate(-45deg); box-shadow: 0 9px 18px rgba(15,23,42,.30), 0 0 0 5px rgba(200,20,47,.18); }}
      .nae-marker::after {{ content: ""; position: absolute; width: 8px; height: 8px; left: 5px; top: 5px; border-radius: 999px; background: #fff; }}
      .popup h3 {{ margin: 0 0 6px; color: var(--blue); font-size: 17px; }}
      .popup p {{ margin: 4px 0; font-size: 13px; }}
      .popup .services {{ max-height: 90px; overflow-y: auto; padding-right: 4px; }}
      .popup-services-title {{ margin-top: 8px; color: #000; font-size: 12px; font-weight: 800; }}
      .popup-services-grid {{ display: grid; grid-template-columns: repeat(10, 24px); gap: 4px; align-items: center; margin-top: 5px; }}
      .popup-other-services {{ display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 6px; align-items: start; margin-top: 7px; color: #7c5608; font-size: 12px; line-height: 1.25; }}
      .service-icons {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
      .service-icon {{ width: 26px; height: 26px; display: inline-flex; align-items: center; justify-content: center; border: 2px solid #B55E36; border-radius: 4px; background: #fff; padding: 3px; }}
      .service-icon img {{ width: 100%; height: 100%; object-fit: contain; display: block; }}
      .popup-services-grid .service-icon, .popup-other-services .service-icon {{ width: 24px; height: 24px; border: 0; border-radius: 0; background: transparent; padding: 0; }}
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
      .card {{ min-width:0; overflow-wrap:anywhere; background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 14px; }}
      .card h3 {{ margin: 0 0 5px; color: var(--blue-2); font-size: 17px; }}
      .card p {{ margin: 5px 0; color: #26384d; }}
      .card details {{ margin-top: 8px; }}
      .card summary {{ cursor: pointer; color: var(--blue); font-weight: 800; }}
      .card-actions {{ margin-top: 10px; }}
      .pager {{ display: flex; justify-content: center; gap: 8px; align-items: center; margin-top: 14px; }}
      .pager span {{ min-width: 120px; text-align: center; color: var(--muted); }}
      @media (max-width: 980px) {{
        .filters {{ grid-template-columns: minmax(0,1fr) minmax(0,1fr); }}
        .filters input {{ grid-column: 1 / -1; }}
        .legend-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      }}
      @media (max-width: 620px) {{
        .wrap {{ max-width: none; padding: 0 14px; }}
        .brand-id {{ width:154px; max-width:42vw; }}
        .top, .summary, .list-head {{ flex-direction: column; align-items: flex-start; }}
        .filters {{ grid-template-columns: minmax(0,1fr); }}
        #map {{ min-height: 460px; }}
        .leaflet-popup-content {{ max-height: min(58vh, 330px); overflow-x: hidden; overflow-y: auto; scrollbar-width: thin; }}
        .legend-grid {{ grid-template-columns: 1fr; }}
        .popup-services-grid {{ grid-template-columns: repeat(10, 24px); }}
      }}
    </style>
  </head>
  <body>
    <header>
      <div class="wrap top">
        <picture>
          <source media="(max-width: 620px)" srcset="{identifier_mobile}" />
          <img class="brand-id" src="{identifier_desktop}" alt="Mapeo de Entidades de Apoyo NAE" />
        </picture>
        <div class="badge">Generado: {escape(generated_at)}</div>
      </div>
      <picture>
        <source media="(max-width: 620px)" srcset="{banner_mobile}" />
        <img class="hero-banner" src="{banner_desktop}" alt="Fortalecimiento de capacidades" />
      </picture>
    </header>
    <main class="wrap">
      <section class="page-title">
        <p class="eyebrow">Mapa sin conexión</p>
        <h1>Mapa de estructuras de apoyo</h1>
        <p class="subtitle">Visualización territorial de estructuras encuestadas y capacidades de apoyo identificadas para nuevos actores económicos.</p>
        <p class="subtitle">{map_variant} · Datos al {escape(generated_at)}</p>
      </section>
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
          <div class="summary-text">
            <span id="result-count">0 entidades visibles</span>
            <span>Los marcadores usan coordenadas validadas cuando existen; si no, ubicación municipal estimada.</span>
          </div>
          <button id="reset-map" class="secondary reset-map" type="button">Restablecer</button>
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
{popup_js}
{basemap_js}
{inflate_js}
    </script>
    <script>
      const payload = {payload};
      const pageSize = 10;
      let currentPage = 1;
      let filtered = [...payload.entities];
      let markers = new Map();

      const cubaBounds = L.latLngBounds([[19.2, -85.4], [23.7, -73.8]]);
      const isTouchMap = window.matchMedia('(pointer: coarse)').matches;
      const map = L.map('map', {{
        zoomControl: true,
        scrollWheelZoom: !isTouchMap,
        dragging: true,
        touchZoom: true,
        doubleClickZoom: !isTouchMap,
        tap: false,
        bounceAtZoomLimits: false,
        minZoom: 4,
        zoomSnap: 0.25,
        maxBounds: cubaBounds.pad(0.75),
        maxBoundsViscosity: 0.25,
        wheelDebounceTime: 120,
        wheelPxPerZoomLevel: 140
      }}).setView([21.9, -79.5], 7);
      const popupController = configureSupportMapPopups(map, () => resetMapView(), cubaBounds);
      const offlineCartography = {cartography_json};
      {streets_loader}
      const offlineBasemap = addOfflineBasemap(map, offlineCartography);
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
        const src = payload.serviceIcons[service] || payload.serviceIcons['Otro servicio'];
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
      function otherServiceLabel(entity) {{
        const otherServices = entity.otherServices || [];
        if (!otherServices.length) return '';
        return `<div class="popup-other-services">${{serviceIcon('Otro servicio')}}<span>${{escapeHtml(otherServices.join(', '))}}</span></div>`;
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
          <p><b>Contacto:</b> ${{escapeHtml(entity.contact)}} · ${{escapeHtml(entity.phone)}} · ${{escapeHtml(entity.email)}}</p>
          <p><b>Dirección:</b> ${{escapeHtml(entity.address)}}</p>
          <div class="popup-services-title">Servicios registrados:</div>
          <div class="popup-services-grid">${{serviceIconGrid(entity)}}</div>
          ${{otherServiceLabel(entity)}}
        </div>`;
      }}
      function focusEntity(id) {{
        const marker = markers.get(String(id));
        if (!marker) return;
        popupController.focus(marker, Math.max(map.getZoom(), 12));
        window.scrollTo({{ top: document.getElementById('map').getBoundingClientRect().top + window.scrollY - 12, behavior: 'smooth' }});
      }}
      function resetMapView() {{
        map.closePopup();
        const navigationBounds = map.options.maxBounds;
        map.setMaxBounds(null);
        map.stop();
        map.invalidateSize({{ pan: false }});
        map.options.minZoom = 4;
        // Avoid a second animated zoom while restoring the view after a resize.
        map.options.minZoom = map.getBoundsZoom(cubaBounds, false, [40, 40]);
        map.fitBounds(cubaBounds, {{ padding: [20, 20], animate: false }});
        map.setMaxBounds(navigationBounds);
      }}
      function renderMarkers() {{
        markerLayer.clearLayers();
        markers = new Map();
        filtered.forEach((entity) => {{
          const marker = L.marker([entity.lat, entity.lng], {{ icon: markerIcon }}).bindPopup(popupHtml(entity), popupController.options);
          marker.addTo(markerLayer);
          markers.set(String(entity.id), marker);
        }});
        if (filtered.length && filtered.length < payload.entities.length) {{
          const bounds = L.latLngBounds(filtered.map((entity) => [entity.lat, entity.lng]));
          map.fitBounds(bounds.pad(0.14), {{ maxZoom: 9 }});
        }} else {{
          resetMapView();
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
      document.getElementById('service-legend').innerHTML = payload.lookups.legendServices.map((service) => `<div class="legend-item">${{serviceIcon(service)}}<span>${{escapeHtml(service)}}</span></div>`).join('');
      [els.q, els.province, els.municipality, els.type, els.service].forEach((el) => el.addEventListener('input', () => applyFilters(true)));
      els.clear.addEventListener('click', () => {{
        [els.q, els.province, els.municipality, els.type, els.service].forEach((el) => el.value = '');
        applyFilters(true);
      }});
      els.prev.addEventListener('click', () => {{ currentPage -= 1; renderList(); }});
      els.next.addEventListener('click', () => {{ currentPage += 1; renderList(); }});
      document.getElementById('reset-map').addEventListener('click', resetMapView);
      applyFilters(true);
    </script>
  </body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta el mapa de entidades NAE como HTML estatico.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Ruta del HTML a generar.")
    parser.add_argument("--limit", type=int, default=1000, help="Cantidad maxima de entidades a exportar.")
    variants = parser.add_mutually_exclusive_group()
    variants.add_argument("--streets-sample", action="store_true", help="Incluye muestra de calles de La Habana.")
    variants.add_argument("--national-streets", action="store_true", help="Incluye calles y carreteras de Cuba.")
    args = parser.parse_args()

    data = get_support_entities(limit=args.limit)
    html = build_static_map_html(data, streets_sample=args.streets_sample, national_streets=args.national_streets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"HTML generado: {args.output}")
    print(f"Entidades exportadas: {len(_normalize_entities(data.get('entidades', [])))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
