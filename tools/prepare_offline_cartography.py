"""Download licensed source data and generate embedded-map layers reproducibly."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess
import unicodedata
from urllib.request import urlopen

from shapely.geometry import box, mapping, shape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'prototype' / 'maps'
CACHE = ROOT / 'reportes' / 'cartografia_fuentes'


def normalized(text):
    text = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in text if not unicodedata.combining(c)).lower().strip()


def download(url, path):
    if not path.exists() or path.stat().st_size == 0:
        print('Descargando', url, flush=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.part')
        if sys.platform == 'win32' and url.startswith('https://download.geofabrik.de/'):
            # Native curl uses the Windows certificate store for this source.
            subprocess.run(['curl.exe','--fail','--location','--silent','--show-error','--max-time','240',url,'--output',str(temporary)],check=True)
        else:
            with urlopen(url, timeout=90) as response, temporary.open('wb') as target:
                while chunk := response.read(1024 * 1024):
                    target.write(chunk)
        temporary.replace(path)
    return path


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def compact_geometry(geometry, tolerance):
    # Preserve topology; coordinate rounding removes irrelevant sub-metre precision.
    geometry = geometry.simplify(tolerance, preserve_topology=True)
    rounded = json.loads(json.dumps(mapping(geometry)), parse_float=lambda value: round(float(value), 5))
    return rounded if shape(rounded).is_valid else mapping(geometry)


def boundaries():
    catalog = {}
    province = None
    for line in (ROOT / 'docs' / 'provincias_municipios_cuba.txt').read_text(encoding='utf-8').splitlines():
        match = re.match(r'^(\d{2}|\d{4})\s*[—–-]\s*(.+)$', line)
        if not match:
            continue
        code, name = match.groups()
        if len(code) == 2:
            province = 'Isla de la Juventud' if code == '40' else name
        else:
            catalog.setdefault(normalized(province), {})[normalized(name)] = name
    sys.path.insert(0, str(ROOT / 'nae-platform-api'))
    from app.cuba_geo import CUBA_GEO
    provinces = {normalized(name): name for name in CUBA_GEO}
    collections = {}
    provenance = []
    for level in ['ADM1', 'ADM2']:
        api = f'https://www.geoboundaries.org/api/current/gbOpen/CUB/{level}/'
        metadata_path = download(api, CACHE / f'{level}-metadata.json')
        meta = json.loads(metadata_path.read_text(encoding='utf-8'))
        raw_path = download(meta['gjDownloadURL'], CACHE / f'{level}.geojson')
        collections[level] = json.loads(raw_path.read_text(encoding='utf-8'))
        provenance.append(dict(level=level, api=api, source=meta['gjDownloadURL'],
                               license=meta['boundaryLicense'], year=meta['boundaryYearRepresented'],
                               sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest()))
    areas = []
    for feature in collections['ADM1']['features']:
        original = feature['properties']['shapeName']
        province_aliases = {'isle of youth': 'isla de la juventud', 'havana': 'la habana'}
        name = provinces.get(province_aliases.get(normalized(original), normalized(original)))
        if not name:
            raise ValueError('Provincia no identificada: ' + original)
        geometry = shape(feature['geometry'])
        areas.append((name, geometry))
        point = geometry.representative_point()
        feature['properties'] = dict(name=name, special=name == 'Isla de la Juventud', label=[point.y, point.x])
        feature['geometry'] = compact_geometry(geometry, 0.0008)
    aliases = {'cespedes': 'carlos manuel de cespedes', 'calixto garcia iniguez': 'calixto garcia',
               'santa isabel de las lajas': 'lajas', 'songo - la maya': 'songo-la maya',
               'habana del este': 'la habana del este', 'isle of youth': 'isla de la juventud'}
    seen = set()
    audit = []
    for feature in collections['ADM2']['features']:
        original = feature['properties']['shapeName']
        geometry = shape(feature['geometry'])
        point = geometry.representative_point()
        province = next((name for name, area in areas if area.covers(point)), None)
        if not province:
            province = max(areas, key=lambda item: item[1].intersection(geometry).area)[0]
        choices = catalog.get(normalized(province), {})
        key = aliases.get(normalized(original), normalized(original))
        name = choices.get(key)
        if not name:
            raise ValueError(f'Municipio no identificado: {province} / {original}. Opciones: {list(choices.values())}')
        pair = (normalized(province), normalized(name))
        if pair in seen:
            raise ValueError('Municipio repetido: ' + str(pair))
        seen.add(pair)
        feature['properties'] = dict(name=name, province=province, label=[point.y, point.x])
        feature['geometry'] = compact_geometry(geometry, 0.0004)
        audit.append(dict(province=province, source_name=original, name=name))
    expected = {(province, name) for province, names in catalog.items() for name in names}
    if seen != expected:
        raise ValueError(f'Catalogo incompleto. Faltan: {expected-seen}. Sobran: {seen-expected}')
    for level, name in [('ADM1', 'cuba-provincias.geojson'), ('ADM2', 'cuba-municipios.geojson')]:
        write_json(OUT / name, collections[level])
    write_json(OUT / 'fuentes.json', dict(generated_at=datetime.now(timezone.utc).isoformat(), sources=provenance,
               provinces=15, special_municipalities=1, municipalities=len(seen), audit=audit))
    print('Validado: 15 provincias, Isla de la Juventud y', len(seen), 'municipios', flush=True)


def streets():
    import osmium
    source = 'https://download.geofabrik.de/central-america/cuba-latest.osm.pbf'
    pbf = download(source, CACHE / 'cuba-latest.osm.pbf')
    region = box(-82.55, 22.96, -82.28, 23.20)
    roads = []

    class Roads(osmium.SimpleHandler):
        def way(self, way):
            highway = way.tags.get('highway')
            if highway not in {'motorway','trunk','primary','secondary','tertiary','residential','unclassified','living_street','service','motorway_link','trunk_link','primary_link','secondary_link','tertiary_link'}:
                return
            try:
                geometry = shape(json.loads(factory.create_linestring(way)))
                if not geometry.intersects(region):
                    return
                geometry = geometry.intersection(region)
                if geometry.geom_type not in {'LineString', 'MultiLineString'}:
                    return
                roads.append(dict(type='Feature', properties=dict(name=way.tags.get('name', ''), kind=highway), geometry=compact_geometry(geometry, 0.00002)))
            except (RuntimeError, ValueError):
                return

    factory = osmium.geom.GeoJSONFactory()
    Roads().apply_file(str(pbf), locations=True, idx='flex_mem')
    with osmium.io.Reader(str(pbf)) as reader:
        source_timestamp = reader.header().get('osmosis_replication_timestamp')
    write_json(OUT / 'muestra-calles-habana.geojson', dict(type='FeatureCollection', features=roads))
    write_json(OUT / 'muestra-calles-fuentes.json', dict(source=source, license='ODbL 1.0', attribution='OpenStreetMap contributors',
               generated_at=datetime.now(timezone.utc).isoformat(), bbox=list(region.bounds), features=len(roads),
               source_timestamp=source_timestamp,
               sha256=hashlib.sha256(pbf.read_bytes()).hexdigest()))
    print('Muestra La Habana:', len(roads), 'tramos de calles', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--streets', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    boundaries()
    if args.streets:
        streets()
