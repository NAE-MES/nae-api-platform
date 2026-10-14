function addOfflineBasemap(map, cartography) {
  const renderer = L.canvas({ padding: 0.3 });
  const provinces = L.geoJSON(cartography.provinces, {
    renderer,
    interactive: false,
    style: { color: '#47665b', weight: 1.8, fillColor: '#e2eddb', fillOpacity: 1 }
  }).addTo(map);
  const municipalities = L.geoJSON(cartography.municipalities, {
    renderer,
    interactive: false,
    style: { color: '#7c8c71', weight: 0.8, fill: false }
  });
  const labels = L.layerGroup().addTo(map);
  const roadLabels = L.layerGroup().addTo(map);
  let roads = null;
  if (cartography.streets) {
    roads = L.geoJSON(cartography.streets, {
      renderer,
      style(feature) {
        const major = /motorway|trunk|primary|secondary/.test(feature.properties.kind);
        return { color: major ? '#bd9257' : '#a9aaa2', weight: major ? 2.2 : 1.1, opacity: 0.9 };
      },
      onEachFeature(feature, layer) {
        if (feature.properties.name) layer.bindTooltip(feature.properties.name);
      }
    });
  }
  function label(latlng, name, className) {
    const text = document.createElement('span');
    text.textContent = name;
    return L.marker(latlng, {
      interactive: false,
      icon: L.divIcon({ className, html: text.outerHTML, iconSize: [0, 0] })
    });
  }
  function redraw() {
    const zoom = map.getZoom();
    labels.clearLayers();
    roadLabels.clearLayers();
    if (zoom >= 8) municipalities.addTo(map);
    else map.removeLayer(municipalities);
    const collection = zoom >= 9 ? cartography.municipalities : cartography.provinces;
    collection.features.forEach((feature) => {
      const point = feature.properties.label;
      if (map.getBounds().contains(point)) {
        label(point, feature.properties.name, zoom >= 9 ? 'offline-label municipality-label' : 'offline-label province-label').addTo(labels);
      }
    });
    if (roads) {
      if (zoom >= 11) roads.addTo(map);
      else map.removeLayer(roads);
      if (zoom >= 15) {
        const names = new Set();
        roads.eachLayer((layer) => {
          const name = layer.feature.properties.name;
          const point = layer.getBounds().getCenter();
          if (name && names.size < 45 && !names.has(name) && map.getBounds().contains(point)) {
            names.add(name);
            label(point, name, 'offline-label road-label').addTo(roadLabels);
          }
        });
      }
    }
  }
  map.on('zoomend moveend', redraw);
  map.attributionControl.addAttribution('Límites: <a href="https://www.geoboundaries.org/">geoBoundaries</a> / OpenStreetMap (ODbL)');
  if (roads) map.attributionControl.addAttribution('Calles: OpenStreetMap / Geofabrik (ODbL)');
  redraw();
  return { provinces, municipalities, roads };
}
