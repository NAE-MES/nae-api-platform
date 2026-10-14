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
  let streetFeatures = [];
  if (cartography.streets) {
    streetFeatures = cartography.streets.features;
    streetFeatures.forEach((feature) => {
      if (!feature.bbox) {
        const bounds = L.geoJSON(feature).getBounds();
        feature.bbox = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()];
      }
    });
    roads = L.geoJSON(null, {
      renderer,
      style(feature) {
        const major = /motorway|trunk|primary|secondary/.test(feature.properties.kind);
        const pedestrian = /^(footway|path|track|steps|bridleway|cycleway)$/.test(feature.properties.kind);
        return { color: major ? '#bd9257' : '#a9aaa2', weight: major ? 2.2 : 1.1, opacity: 0.9, dashArray: pedestrian ? '3 3' : null };
      },
      onEachFeature(feature, layer) {
        if (feature.properties.name) {
          const text = document.createElement('span');
          text.textContent = feature.properties.name;
          layer.bindTooltip(text);
        }
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
      roads.clearLayers();
      if (zoom >= 7) {
        const bounds = map.getBounds().pad(0.1);
        const west = bounds.getWest(), east = bounds.getEast();
        const south = bounds.getSouth(), north = bounds.getNorth();
        // Only instantiate paths in the viewport; rural and city detail grows with zoom.
        streetFeatures.forEach((feature) => {
          const box = feature.bbox;
          if (box[2] < west || box[0] > east || box[3] < south || box[1] > north) return;
          const kind = feature.properties.kind;
          if (zoom < 16 && /^(footway|path|track|steps|bridleway|cycleway)$/.test(kind)) return;
          if (zoom < 10 && !/^(motorway|trunk|primary)(_link)?$/.test(kind)) return;
          if (zoom < 12 && !/^(motorway|trunk|primary|secondary)(_link)?$/.test(kind)) return;
          if (zoom < 13 && !/^(motorway|trunk|primary|secondary|tertiary)(_link)?$/.test(kind)) return;
          roads.addData(feature);
        });
        roads.addTo(map);
      }
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
