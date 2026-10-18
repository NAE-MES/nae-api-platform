function configureSupportMapPopups(map, resetView, homeBounds) {
  if (!document.getElementById('support-map-expand-style')) {
    const style = document.createElement('style');
    style.id = 'support-map-expand-style';
    style.textContent = `
      .support-map-expanded { position:fixed !important; inset:0 !important; width:100% !important; height:100vh !important; height:100dvh !important; min-height:0 !important; z-index:5000 !important; border-radius:0 !important; }
      .map-expand-button { display:flex; align-items:center; justify-content:center; min-width:44px; min-height:44px; padding:0 10px; border:0; background:#fff; color:#173b75; font:700 14px Arial,sans-serif; cursor:pointer; }
      .map-expand-button span { font-size:24px; line-height:1; }
      .map-expand-button:disabled, #reset-map:disabled { opacity:.45; cursor:default; }
    `;
    document.head.appendChild(style);
  }
  const container = map.getContainer();
  let expanded = false;
  let previousOverflow = '';
  const expandButton = document.createElement('button');
  expandButton.type = 'button';
  expandButton.className = 'map-expand-button';
  expandButton.title = 'Ampliar mapa';
  expandButton.setAttribute('aria-label', 'Ampliar mapa');
  expandButton.setAttribute('aria-expanded', 'false');
  expandButton.innerHTML = '<span aria-hidden="true">&#x26F6;</span>';
  const resetButton = document.createElement('button');
  resetButton.type = 'button';
  resetButton.className = 'map-expand-button';
  resetButton.textContent = 'Restablecer';
  resetButton.style.display = 'none';
  resetButton.addEventListener('click', () => {
    map.closePopup();
    resetView();
  });
  function syncResetState() {
    const zoom = map.getBoundsZoom(homeBounds, false, [40, 40]);
    const center = map.project(homeBounds.getSouthWest(), zoom)
      .add(map.project(homeBounds.getNorthEast(), zoom)).divideBy(2);
    const limitedCenter = center.clone();
    const bounds = map.options.maxBounds;
    if (bounds) {
      const nw = map.project(bounds.getNorthWest(), zoom);
      const se = map.project(bounds.getSouthEast(), zoom);
      const half = map.getSize().divideBy(2);
      // Leaflet centers an oversized viewport within its navigation limits.
      for (const axis of ['x', 'y']) {
        const low = nw[axis] + half[axis];
        const high = se[axis] - half[axis];
        limitedCenter[axis] = low > high ? (nw[axis] + se[axis]) / 2
          : Math.max(low, Math.min(high, center[axis]));
      }
    }
    const current = map.project(map.getCenter(), zoom);
    const atHome = Math.abs(map.getZoom() - zoom) < 0.01
      && (current.distanceTo(center) <= 1 || current.distanceTo(limitedCenter) <= 1);
    resetButton.disabled = atHome;
    const externalReset = document.getElementById('reset-map');
    if (externalReset) externalReset.disabled = atHome;
  }
  map.on('moveend zoomend', syncResetState);
  map.whenReady(syncResetState);
  function toggleExpanded() {
    expanded = !expanded;
    if (expanded) previousOverflow = document.body.style.overflow;
    document.body.style.overflow = expanded ? 'hidden' : previousOverflow;
    container.classList.toggle('support-map-expanded', expanded);
    expandButton.title = expanded ? 'Salir del mapa ampliado' : 'Ampliar mapa';
    expandButton.setAttribute('aria-label', expandButton.title);
    expandButton.setAttribute('aria-expanded', String(expanded));
    expandButton.innerHTML = expanded ? 'Salir' : '<span aria-hidden="true">&#x26F6;</span>';
    resetButton.style.display = expanded ? 'flex' : 'none';
    requestAnimationFrame(() => map.invalidateSize({ pan: false }));
  }
  const ExpandControl = L.Control.extend({
    options: { position: 'bottomright' },
    onAdd() {
      const control = L.DomUtil.create('div', 'leaflet-bar');
      control.style.display = 'flex';
      control.appendChild(resetButton);
      control.appendChild(expandButton);
      L.DomEvent.disableClickPropagation(control);
      L.DomEvent.disableScrollPropagation(control);
      return control;
    }
  });
  map.addControl(new ExpandControl());
  expandButton.addEventListener('click', toggleExpanded);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && expanded) toggleExpanded();
  });
  const navigationBounds = map.options.maxBounds;
  const options = { autoPan: false, keepInView: false, maxWidth: 470 };
  function fitPopup(popup) {
    const element = popup.getElement();
    if (!element || !popup.isOpen()) return;
    const content = element.querySelector('.leaflet-popup-content');
    const size = map.getSize();
    const maxWidth = Math.min(popup.options.maxWidth || 470, size.x - 72);
    content.style.setProperty('width', maxWidth + 'px', 'important');
    content.style.setProperty('max-width', maxWidth + 'px', 'important');
    content.style.setProperty('max-height', Math.max(80, size.y - 148) + 'px', 'important');
    content.style.overflowY = 'auto';
    content.style.overflowWrap = 'anywhere';
    element.querySelectorAll('.popup-services-grid').forEach((grid) => {
      grid.style.overflowX = 'auto';
    });
    popup.update();
    const frame = container.getBoundingClientRect();
    const card = element.getBoundingClientRect();
    const dx = card.left < frame.left + 16 ? card.left - frame.left - 16
      : Math.max(0, card.right - frame.right + 16);
    const dy = card.top < frame.top + 16 ? card.top - frame.top - 16
      : Math.max(0, card.bottom - frame.bottom + 64);
    if (dx || dy) map.panBy([dx, dy], { animate: false });
  }
  map.on('popupopen', (event) => {
    // Leave room to place the whole card, including its close button, inside the map.
    map.setMaxBounds(null);
    if (map.zoomControl) map.zoomControl.getContainer().style.visibility = 'hidden';
    fitPopup(event.popup);
    requestAnimationFrame(() => fitPopup(event.popup));
    event.popup.getElement().querySelectorAll('img').forEach((image) => {
      if (!image.complete) image.addEventListener('load', () => fitPopup(event.popup), { once: true });
    });
  });
  map.on('popupclose', () => {
    if (map.zoomControl) map.zoomControl.getContainer().style.visibility = '';
    map.setMaxBounds(navigationBounds);
  });
  map.on('resize', () => {
    requestAnimationFrame(() => {
      const atOverview = map.getZoom() <= map.getMinZoom() + 0.01;
      if (atOverview) resetView();
      else {
        map.options.minZoom = 4;
        map.options.minZoom = map.getBoundsZoom(homeBounds, false, [40, 40]);
        if (map.getZoom() < map.getMinZoom()) map.setZoom(map.getMinZoom(), { animate: false });
        syncResetState();
      }
    });
    map.eachLayer((layer) => {
      if (layer instanceof L.Popup && layer.isOpen()) fitPopup(layer);
    });
  });
  const touchPointer = window.matchMedia('(pointer: coarse)');
  touchPointer.addEventListener('change', () => {
    map.scrollWheelZoom[touchPointer.matches ? 'disable' : 'enable']();
    map.doubleClickZoom[touchPointer.matches ? 'disable' : 'enable']();
  });
  return {
    options,
    focus(marker, zoom) {
      map.closePopup();
      map.setMaxBounds(null);
      map.stop();
      map.setView(marker.getLatLng(), zoom, { animate: false });
      marker.openPopup();
    }
  };
}
