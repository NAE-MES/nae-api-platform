"""Resize the same document between desktop and mobile without reloading it."""
from pathlib import Path
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nae-platform-api'))
sys.path.insert(0, str(ROOT / 'nae-platform-api/scripts'))
from app.reporting import render_support_entities_html
from export_static_map import build_static_map_html

data = dict(entidades=[], total=0, lookups={}, filters={})
output = ROOT / 'reportes/validacion_cambio_vista'
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    for engine in ['firefox', 'chromium']:
        browser = getattr(p, engine).launch()
        for version, html in [('online', render_support_entities_html(data, True, True)),
                              ('offline', build_static_map_html(data))]:
            page = browser.new_page(viewport={'width':1440,'height':900})
            errors = []
            requests = []
            page.on('pageerror', lambda error: errors.append(str(error)))

            def serve(route):
                path = urlparse(route.request.url).path
                if path == '/':
                    requests.append(path)
                    route.fulfill(body=html, content_type='text/html')
                elif path.startswith('/prototype-assets/'):
                    route.fulfill(path=str(ROOT / 'prototype' / path.removeprefix('/prototype-assets/')))
                elif path.startswith('/images/'):
                    route.fulfill(path=str(ROOT / path.lstrip('/')))
                else:
                    route.abort()

            page.route('**/*', serve)
            page.goto('http://resize-test.local/')
            page.wait_for_timeout(400)
            for width, height in [(441,758),(390,844),(844,390),(1440,900)]:
                page.set_viewport_size({'width':width,'height':height})
                page.wait_for_timeout(500)
                assert page.evaluate('map.getBounds().contains(cubaBounds)'), (engine,version,width,page.evaluate('({size:map.getSize(),zoom:map.getZoom(),min:map.getMinZoom(),home:map.getBoundsZoom(cubaBounds,false,[40,40])})'))
                if version == 'online' and width < 720:
                    assert not page.locator('.platform-more').is_visible()
                    assert not page.locator('.platform-admin').is_visible()
                assert page.locator('#reset-map').is_disabled(), (engine,version,width,page.evaluate('({zoom:map.getZoom(),min:map.getMinZoom(),center:map.getCenter()})'))
                page.screenshot(path=str(output / f'{engine}-{version}-{width}.png'))
                print('OK sin recargar:',engine,version,width,flush=True)
            assert requests == ['/'], requests
            page.evaluate('()=>{map.setView([23.13,-82.38],12,{animate:false});}')
            center = page.evaluate('map.getCenter()')
            page.set_viewport_size({'width':390,'height':844})
            page.wait_for_timeout(500)
            assert page.evaluate('map.getZoom()') == 12
            assert page.evaluate('(center)=>map.distance(map.getCenter(),center)', center) < 10
            page.locator('#reset-map').click()
            page.wait_for_timeout(500)
            assert page.evaluate('map.getBounds().contains(cubaBounds)')
            assert page.locator('#reset-map').is_disabled()
            assert not errors, errors
            page.close()
        browser.close()
