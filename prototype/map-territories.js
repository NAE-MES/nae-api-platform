function configureTerritoryMarkers(map, layer, popupController) {
  const detailZoom = 9;
  const normalized = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase();
  let groups = [];
  const expanded = new Set();
  let previousZoom = map.getZoom();
  let openingGroup = false;
  if (!document.getElementById('territory-popup-style')) {
    const style = document.createElement('style');
    style.id = 'territory-popup-style';
    style.textContent = '.territory-group-marker .nae-marker{box-shadow:0 3px 8px rgba(15,23,42,.25)}.territory-popup h3{font:700 16px Arial;margin:0 0 8px;color:#003247}.territory-popup p{margin:0 0 12px}.territory-popup button{min-height:40px;padding:0 14px;border:1px solid #003247;border-radius:6px;background:#003247;color:#fff;font:700 13px Arial;cursor:pointer}';
    style.textContent += '.territory-group-marker.has-count .nae-marker::after{display:none}.territory-group-marker .territory-count{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;transform:rotate(45deg);color:#fff;font:700 11px Arial;letter-spacing:0}';
    style.textContent += '.territory-group-popup .leaflet-popup-content{margin:14px 18px}.territory-popup h3{font:700 15px Calibri,"Segoe UI",Arial,sans-serif;line-height:1.3;margin:0 16px 5px 0}.territory-popup p{font:400 13px Calibri,"Segoe UI",Arial,sans-serif;line-height:1.4;margin:0 0 12px;color:#526574}.territory-popup button{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;min-height:36px;padding:6px 12px;font:600 13px Calibri,"Segoe UI",Arial,sans-serif}.territory-popup button:hover{background:#164d60}.territory-popup button:focus-visible{outline:2px solid #287da4;outline-offset:3px}';
    document.head.appendChild(style);
  }
  function refresh() {
    const wanted = new Set();
    groups.forEach((group) => {
      if (map.getZoom() >= detailZoom || expanded.has(group.key)) {
        group.entries.forEach((entry) => wanted.add(entry.marker));
      } else wanted.add(group.marker);
    });
    layer.eachLayer((marker) => { if (!wanted.has(marker)) layer.removeLayer(marker); });
    wanted.forEach((marker) => { if (!layer.hasLayer(marker)) layer.addLayer(marker); });
  }
  function openGroup(group) {
    expanded.add(group.key);
    openingGroup = true;
    map.closePopup();
    const bounds = L.latLngBounds(group.entries.map((entry) => entry.marker.getLatLng()));
    map.fitBounds(bounds.pad(0.15), { padding: [36, 36], maxZoom: 12, animate: false });
    openingGroup = false;
    refresh();
  }
  map.on('zoomend', () => {
    const zoom = map.getZoom();
    if (!openingGroup && zoom < previousZoom - 0.01) expanded.clear();
    previousZoom = zoom;
    refresh();
  });
  return {
    setEntries(entries) {
      expanded.clear();
      const grouped = new Map();
      entries.forEach((entry) => {
        const province = normalized(entry.province);
        const municipality = normalized(entry.municipality);
        const havana = province === 'la habana';
        const unknown = !municipality || ['sin municipio', 'sin dato'].includes(municipality);
        const key = havana ? 'province:la habana' : unknown ? `entity:${entry.id}` : `${province}|${municipality}`;
        if (!grouped.has(key)) grouped.set(key, { key, title: havana ? 'La Habana' : `${entry.province} · ${entry.municipality}`, entries: [] });
        grouped.get(key).entries.push(entry);
      });
      groups = [...grouped.values()];
      groups.forEach((group) => {
        const first = group.entries[0];
        const point = Number.isFinite(first.territoryLat) && Number.isFinite(first.territoryLng)
          ? [first.territoryLat, first.territoryLng]
          : L.latLngBounds(group.entries.map((entry) => entry.marker.getLatLng())).getCenter();
        const total = group.entries.length;
        const icon = L.divIcon({
          className: `territory-group-marker${total > 1 ? ' has-count' : ''}`,
          html: `<span class="nae-marker">${total > 1 ? `<span class="territory-count">${total}</span>` : ''}</span>`,
          iconSize: [30, 38], iconAnchor: [12, 24], popupAnchor: [0, -28]
        });
        const popup = document.createElement('div');
        popup.className = 'territory-popup';
        const title = document.createElement('h3');
        title.textContent = group.title;
        const count = document.createElement('p');
        count.textContent = `${group.entries.length} ${group.entries.length === 1 ? 'entidad de apoyo' : 'entidades de apoyo'}`;
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = 'Ver entidades';
        const arrow = document.createElement('span');
        arrow.setAttribute('aria-hidden', 'true');
        arrow.textContent = '\u2192';
        button.appendChild(arrow);
        button.addEventListener('click', () => openGroup(group));
        popup.append(title, count, button);
        const tooltip = document.createElement('span');
        tooltip.textContent = `${group.title} · ${count.textContent}`;
        group.marker = L.marker(point, { icon, title: tooltip.textContent })
          .bindPopup(popup, { ...popupController.options, maxWidth: 236, className: 'territory-group-popup' }).bindTooltip(tooltip);
      });
      refresh();
    },
    reveal(marker) {
      const group = groups.find((item) => item.entries.some((entry) => entry.marker === marker));
      if (group) expanded.add(group.key);
      refresh();
    },
    getGroups() {
      return groups.map((group) => ({ key: group.key, title: group.title, total: group.entries.length }));
    }
  };
}
