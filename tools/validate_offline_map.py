"""Exercise a fresh local HTML file with the browser network disabled."""
import json
from pathlib import Path
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nae-platform-api' / 'scripts'))
from export_static_map import build_static_map_html

output = ROOT / 'reportes' / 'mapa_exportable'
snapshot = (output / 'mapa_entidades_apoyo.html').read_text(encoding='utf-8')
payload, _ = json.JSONDecoder().raw_decode(snapshot.split('const payload = ', 1)[1])
fields = {'id':'entidad_apoyo_id', 'name':'entidad_nombre', 'type':'tipo_estructura_apoyo',
          'province':'provincia', 'municipality':'municipio', 'coverage':'cobertura_descriptiva',
          'services':'servicios', 'contact':'persona_contacto_cargo', 'phone':'telefonos',
          'email':'correo_electronico', 'address':'direccion_fisica', 'lat':'lat', 'lng':'lng',
          'source':'coordinate_source', 'status':'coordinate_status'}
rows = []
measurements = []
for entity in payload['entities']:
    row = {target:entity.get(source) for source, target in fields.items()}
    row['servicios_detalle'] = [{'name':name} for name in entity['serviceList'] + entity.get('otherServices', [])]
    rows.append(row)

with sync_playwright() as p:
    browser = p.firefox.launch()
    for sample in [False, True]:
        if sample and not (ROOT/'prototype/maps/muestra-calles-habana.geojson').exists():
            continue
        filename = 'mapa_muestra_calles_habana.html' if sample else 'mapa_offline_territorial.html'
        path = output / filename
        path.write_text(build_static_map_html({'entidades':rows}, streets_sample=sample), encoding='utf-8')
        for width, height in [(390,844), (1440,1000)]:
            context = browser.new_context(viewport={'width':width,'height':height}, offline=True, has_touch=width<720)
            page = context.new_page()
            errors, network = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: network.append(request.url) if request.url.startswith(('http:', 'https:')) else None)
            started = time.perf_counter()
            page.goto(path.as_uri())
            page.wait_for_timeout(400)
            load_ms = round((time.perf_counter() - started) * 1000)
            assert page.evaluate('offlineBasemap.provinces.getLayers().length') == 16
            assert page.evaluate('offlineBasemap.municipalities.getLayers().length') == 168
            assert page.evaluate('payload.entities.length') == len(rows)
            page.locator('.map-expand-button[aria-expanded]').click()
            page.evaluate('map.setView([21.85,-79.55],6,{animate:false})')
            page.wait_for_timeout(250)
            pixels = page.evaluate('''() => {
              const canvas=document.querySelector('#map canvas');
              const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
              let drawn=0; for(let i=3;i<pixels.length;i+=4) if(pixels[i]) drawn++;
              return drawn;
            }''')
            assert pixels > 1000, 'Blank basemap'
            page.screenshot(path=str(output / f'{"calles" if sample else "territorial"}-{width}.png'))
            if sample:
                page.evaluate('map.setView([23.115,-82.38],15,{animate:false})')
                page.wait_for_timeout(350)
                assert page.evaluate('map.hasLayer(offlineBasemap.roads)')
                assert page.evaluate('offlineBasemap.roads.getLayers().length') > 100
                page.screenshot(path=str(output / f'calles-detalle-{width}.png'))
            page.get_by_role('button',name='Salir del mapa ampliado').click()
            page.locator('[data-focus]').first.click()
            page.locator('.leaflet-popup-close-button').click()
            page.locator('.leaflet-popup').wait_for(state='detached')
            page.locator('#q').fill('zzzz_no_existe')
            assert page.locator('#result-count').inner_text() == '0 entidades visibles'
            page.locator('#clear').click()
            assert page.evaluate('filtered.length') == len(rows)
            assert not errors, errors
            assert not network, network
            measurements.append(dict(file=filename, bytes=path.stat().st_size, viewport_width=width,
                                     entities=len(rows), load_ms=load_ms, network_requests=len(network)))
            print(f'OK {filename} {width}px: {len(rows)} entidades, mapa dibujado, filtros y fichas; cero solicitudes de red', flush=True)
            context.close()
        print(filename, path.stat().st_size, 'bytes', flush=True)
    browser.close()
(output / 'validacion_sin_conexion.json').write_text(json.dumps(measurements,ensure_ascii=False,indent=2),encoding='utf-8')
