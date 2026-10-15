"""Real-data layout regression: long selects, reset, rotation and expanded maps."""
import json
from pathlib import Path
import sys
import argparse
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nae-platform-api/scripts'))
from export_static_map import build_static_map_html
from app.reporting import render_support_entities_html

snapshot = (ROOT/'reportes/mapa_exportable/mapa_entidades_apoyo.html').read_text(encoding='utf-8')
payload, _ = json.JSONDecoder().raw_decode(snapshot.split('const payload = ', 1)[1])
fields = {'id':'entidad_apoyo_id','name':'entidad_nombre','type':'tipo_estructura_apoyo',
          'province':'provincia','municipality':'municipio','coverage':'cobertura_descriptiva',
          'services':'servicios','contact':'persona_contacto_cargo','phone':'telefonos',
          'email':'correo_electronico','address':'direccion_fisica','lat':'lat','lng':'lng',
          'source':'coordinate_source','status':'coordinate_status'}
rows = [{target:entity.get(source) for source,target in fields.items()} for entity in payload['entities']]
lookups = {target:payload['lookups'][source] for source,target in [('provinces','provincias'),('municipalities','municipios'),('types','tipos'),('services','servicios')]}
data = {'entidades':rows,'total':len(rows),'lookups':lookups,'filters':{}}
out = ROOT/'reportes/validacion_claudia_14_10_2'
out.mkdir(parents=True,exist_ok=True)
results = []
parser = argparse.ArgumentParser()
parser.add_argument('--browser', choices=['chromium','firefox'])
args = parser.parse_args()

with sync_playwright() as p:
    for engine in ([args.browser] if args.browser else ['chromium','firefox']):
        browser = getattr(p,engine).launch()
        for version,html in [('online',render_support_entities_html(data,True,True)),
                             ('territorial',build_static_map_html(data)),
                             ('nacional',build_static_map_html(data,national_streets=True))]:
            for width,height in [(320,740),(390,844),(412,915),(844,390),(1440,900)]:
                mobile_options = {'is_mobile':width<1000} if engine=='chromium' else {}
                context = browser.new_context(viewport={'width':width,'height':height},has_touch=width<1000,**mobile_options)
                page = context.new_page()
                errors = []
                page.on('pageerror',lambda error:errors.append(str(error)))

                def serve(route):
                    path=urlparse(route.request.url).path
                    if path=='/': route.fulfill(body=html,content_type='text/html')
                    elif path.startswith('/prototype-assets/'):
                        route.fulfill(path=str(ROOT/'prototype'/path.removeprefix('/prototype-assets/')))
                    elif path.startswith('/images/'):
                        route.fulfill(path=str(ROOT/path.lstrip('/')))
                    else: route.abort()

                page.route('**/*',serve)
                page.goto('http://map-test.local/')
                page.wait_for_timeout(150)

                def check_fit(stage):
                    layout=page.evaluate('({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
                    assert layout['scroll']<=layout['width']+1,(engine,version,width,stage,layout)
                    assert abs(page.evaluate('visualViewport.scale')-1)<0.01,(engine,version,stage,'pagina auto-reducida')
                    controls=page.locator('.support-filters input,.support-filters select' if version=='online' else '.filters input,.filters select')
                    for box in controls.evaluate_all('(els)=>els.map(e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right}})'):
                        assert box['left']>=0 and box['right']<=layout['width']+1,(stage,box,layout)

                def reset_and_check():
                    page.evaluate('()=>{resetMapView();}')
                    assert page.evaluate('map.getBounds().contains(cubaBounds)'),(engine,version,width,'Cuba recortada')

                check_fit('initial')
                reset_and_check()
                assert page.locator('#reset-map').is_disabled()
                page.evaluate('()=>{map.setView([23.13,-82.38],12,{animate:false});}')
                reset = page.locator('#reset-map')
                reset.click()
                page.wait_for_timeout(350)
                assert reset.is_disabled()
                assert page.evaluate('map.getBounds().contains(cubaBounds)'),(engine,version,width,'reset not expanded')
                map_box = page.locator('#support-map' if version=='online' else '#map').bounding_box()
                reset_box = reset.bounding_box()
                assert reset_box['y'] >= map_box['y'] + map_box['height'],(engine,version,width,'reset below map')
                if width<500:
                    page.screenshot(path=str(out/f'{engine}-{version}-{width}-filtros.png'))
                page.locator('.map-expand-button[aria-expanded]').click()
                page.wait_for_timeout(100)
                page.evaluate('()=>{map.setView([23.13,-82.38],12,{animate:false});}')
                page.locator('.support-map-expanded').get_by_role('button',name='Restablecer',exact=True).click()
                page.wait_for_timeout(350)
                assert page.locator('.support-map-expanded').get_by_role('button',name='Restablecer',exact=True).is_disabled()
                assert page.evaluate('map.getBounds().contains(cubaBounds)'),(engine,version,width,'reset expanded')
                rect=page.locator('.support-map-expanded').bounding_box()
                assert abs(rect['width']-width)<=1 and abs(rect['height']-height)<=1,rect
                page.screenshot(path=str(out/f'{engine}-{version}-{width}-cuba.png'))
                if width==390:
                    page.evaluate("()=>{window.layoutEvents=[];map.on('resize moveend zoomend',e=>layoutEvents.push({type:e.type,center:map.getCenter(),zoom:map.getZoom()}));}")
                    page.set_viewport_size({'width':844,'height':390})
                    page.wait_for_timeout(150)
                    assert page.evaluate('map.getBounds().contains(cubaBounds)'),(engine,version,'rotation overview',page.evaluate('({zoom:map.getZoom(),min:map.getMinZoom(),size:map.getSize(),bounds:map.getBounds(),events:layoutEvents})'))
                page.get_by_role('button',name='Salir del mapa ampliado').click()
                page.wait_for_timeout(100)
                check_fit('exit expanded')
                reset_and_check()
                assert page.evaluate("document.body.style.overflow !== 'hidden'")
                assert not errors,errors
                results.append(dict(browser=engine,version=version,width=width,height=height,status='ok'))
                print('OK',engine,version,width,'sin desborde, Cuba completa, ampliar/salir',flush=True)
                context.close()
        browser.close()
(out/'resultados.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
