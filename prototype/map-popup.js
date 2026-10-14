function configureSupportMapPopups(map) {
  const navigationBounds = map.options.maxBounds;
  const options = { autoPan: true, keepInView: false, maxWidth: 470, autoPanPadding: [16, 16] };
  function fitPopup(popup) {
    const element = popup.getElement();
    if (!element) return;
    const content = element.querySelector('.leaflet-popup-content');
    const size = map.getSize();
    content.style.setProperty('width', Math.min(470, size.x - 72) + 'px', 'important');
    content.style.setProperty('max-width', Math.min(470, size.x - 72) + 'px', 'important');
    content.style.setProperty('max-height', Math.max(80, size.y - 100) + 'px', 'important');
    content.style.overflowY = 'auto';
    content.style.overflowWrap = 'anywhere';
    element.querySelectorAll('.popup-services-grid').forEach((grid) => {
      grid.style.overflowX = 'auto';
    });
    popup.update();
  }
  map.on('popupopen', (event) => {
    // Let auto-pan place the whole card, including its close button, inside the map.
    map.setMaxBounds(null);
    if (map.zoomControl) map.zoomControl.getContainer().style.visibility = 'hidden';
    fitPopup(event.popup);
    event.popup.getElement().querySelectorAll('img').forEach((image) => {
      if (!image.complete) image.addEventListener('load', () => fitPopup(event.popup), { once: true });
    });
  });
  map.on('popupclose', () => {
    if (map.zoomControl) map.zoomControl.getContainer().style.visibility = '';
    map.setMaxBounds(navigationBounds);
  });
  map.on('resize', () => {
    map.eachLayer((layer) => {
      if (layer instanceof L.Popup && layer.isOpen()) fitPopup(layer);
    });
  });
  return {
    options,
    focus(marker, zoom) {
      map.closePopup();
      map.stop();
      map.setView(marker.getLatLng(), zoom, { animate: false });
      marker.openPopup();
    }
  };
}
