# Cartografia para el mapa sin conexion

Estos GeoJSON se incrustan en el HTML exportado. Abrirlo no requiere un servidor,
una instalacion, una visita previa ni conexion a internet. La cartografia no
depende de imagenes de Esri, Carto ni de tile.openstreetmap.org.

## Version territorial

- `cuba-provincias.geojson`: 15 provincias y el municipio especial Isla de la Juventud.
- `cuba-municipios.geojson`: 168 municipios, incluido el municipio especial.
- `fuentes.json`: URL de origen, licencia, ano representado, hashes y auditoria de nombres.

Fuente: geoBoundaries gbOpen CUB ADM1/ADM2, geometria que representa 2017,
basada en OpenStreetMap/Wambacher. No se presenta como un levantamiento oficial
actualizado. Los nombres se contrastaron uno a uno con el catalogo territorial
del proyecto. Se tradujeron Havana e Isle of Youth y se normalizaron variantes
de nombres. No se modificaron las coberturas ni los datos de entidades de la BD.

La geometria fue simplificada preservando topologia para reducir el tamano.
Los puntos de las etiquetas son puntos interiores de los poligonos, no coordenadas
de cabeceras municipales. Los municipios y sus etiquetas aparecen al ampliar.

## Muestra con calles

`muestra-calles-habana.geojson` incorpora calles y carreteras del rectangulo
[-82.55, 22.96, -82.28, 23.20]. Es una muestra de La Habana, no una cobertura
de calles de toda Cuba. Fuera de ella se mantiene el mapa territorial nacional.
`muestra-calles-fuentes.json` identifica origen, fecha y hash del extracto OSM.

Las calles aparecen desde zoom 11; sus nombres, cuando existen en OSM, se pueden
consultar y algunos se muestran desde zoom 15. La ausencia de una calle en los
datos no significa que no exista. La muestra no incluye imagenes satelitales,
edificios, navegacion de rutas ni busqueda de direcciones.

## Licencia y atribucion

Las capas derivadas mantienen **Open Database License (ODbL) 1.0**. La aplicacion
muestra la atribucion a geoBoundaries y OpenStreetMap; la muestra de calles
anade Geofabrik. La licencia de las capas no cambia la del codigo ni la de los
datos de entidades de apoyo.

- geoBoundaries: https://www.geoboundaries.org/api.html
- Fuentes originales y hashes: `fuentes.json`
- Geofabrik Cuba: https://download.geofabrik.de/central-america/cuba.html
- OpenStreetMap: https://www.openstreetmap.org/copyright
- Licencia: https://opendatacommons.org/licenses/odbl/1-0/

## Regeneracion

La preparacion es local y requiere `shapely` y, para calles, `osmium`:

```powershell
python -m pip install shapely osmium
python tools/prepare_offline_cartography.py --streets
```

Se necesita el catalogo `docs/provincias_municipios_cuba.txt` del proyecto.
Los originales se guardan en `reportes/cartografia_fuentes/`, fuera del paquete
publicado. No es necesario instalar estas dependencias para exportar el mapa:
el exportador usa los GeoJSON ya preparados.

Desde `nae-platform-api`, con el entorno configurado:

```bash
./.venv/bin/python scripts/export_static_map.py --output ../reportes/mapa_exportable/mapa_entidades_apoyo.html
./.venv/bin/python scripts/export_static_map.py --streets-sample --output ../reportes/mapa_exportable/mapa_muestra_calles_habana.html
```

El primer archivo es la descarga habitual de la plataforma. El segundo es una
muestra separada para evaluar el detalle y el rendimiento antes de preparar
calles para todo el pais.

Prueba local con una exportacion existente como fuente de entidades:

```powershell
python tools/validate_offline_map.py
```

La prueba abre archivos `file://` en contextos nuevos con la red desactivada,
comprueba dibujo en canvas, filtros, fichas y ampliacion en movil/escritorio,
y exige cero solicitudes HTTP/HTTPS. La politica de contenido del HTML bloquea
recursos externos como proteccion adicional.
