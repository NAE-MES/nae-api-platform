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
  map.createPane('offlinePlaceLabels').style.zIndex = 550;
  map.createPane('offlineRoadLabels').style.zIndex = 540;
  const priority = { city: 0, town: 1, village: 2, hamlet: 3 };
  const placeFeatures = [...(cartography.places?.features || [])].sort((a, b) => priority[a.properties.kind] - priority[b.properties.kind]);
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
      pane: className.includes('road-label') ? 'offlineRoadLabels' : 'offlinePlaceLabels',
      icon: L.divIcon({ className, html: text.outerHTML, iconSize: [0, 0] })
    });
  }
  function redraw() {
    const zoom = map.getZoom();
    labels.clearLayers();
    roadLabels.clearLayers();
    const occupied = [];
    function reserveLabel(point, name) {
      const pixel = map.latLngToContainerPoint(point);
      const halfWidth = Math.min(150, Math.max(30, name.length * 6)) / 2 + 4;
      const rect = { left: pixel.x - halfWidth, right: pixel.x + halfWidth, top: pixel.y - 15, bottom: pixel.y + 15 };
      if (occupied.some(other => rect.left < other.right && rect.right > other.left && rect.top < other.bottom && rect.bottom > other.top)) return false;
      occupied.push(rect);
      return true;
    }
    if (zoom >= 8) municipalities.addTo(map);
    else map.removeLayer(municipalities);
    if (cartography.places && zoom >= 9) {
      placeFeatures.forEach((feature) => {
        const kind = feature.properties.kind;
        if (kind === 'village' && zoom < 11) return;
        if (kind === 'hamlet' && zoom < 14) return;
        const point = L.latLng(feature.geometry.coordinates[1], feature.geometry.coordinates[0]);
        if (map.getBounds().contains(point) && reserveLabel(point, feature.properties.name)) {
          label(point, feature.properties.name, 'offline-label municipality-label place-label').addTo(labels);
        }
      });
    } else {
      const collection = zoom >= 9 ? cartography.municipalities : cartography.provinces;
      collection.features.forEach((feature) => {
        const point = feature.properties.label;
        if (map.getBounds().contains(point)) {
          label(point, feature.properties.name, zoom >= 9 ? 'offline-label municipality-label' : 'offline-label province-label').addTo(labels);
        }
      });
    }
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
          if (name && names.size < 45 && !names.has(name) && map.getBounds().contains(point) && reserveLabel(point, name)) {
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
