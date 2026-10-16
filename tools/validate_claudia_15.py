"""Visual regression for the October 15 header, login and filter revisions."""
from pathlib import Path
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nae-platform-api'))
from app.main import _render_login_html
from app.reporting import render_admin_review_html, render_dashboard_html, render_support_entities_html

data = dict(lookups={}, filters={}, total_respuestas=146)
for key in ['por_estado', 'tipos_estructura', 'por_provincia', 'cobertura',
            'servicios_ofrecidos', 'servicios_fortalecer', 'tipos_nae', 'capacidades',
            'conectividad', 'sostenibilidad', 'actualizacion_mapa', 'limitaciones',
            'ultimas_respuestas']:
    data[key] = []
map_data = dict(entidades=[], total=0, lookups={}, filters={})
pages = {
    'login': _render_login_html().body.decode(),
    'analitica': render_dashboard_html(data),
    'admin': render_admin_review_html({}),
    'mapa': render_support_entities_html(map_data, True, True),
    'lector': render_support_entities_html(map_data, True, False),
}
output = ROOT / 'reportes/validacion_claudia_15_10'
output.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    for engine in ['chromium', 'firefox']:
        browser = getattr(p, engine).launch()
        for name, html in pages.items():
            for width, height in [(320, 740), (390, 844), (441, 758), (1440, 1000)]:
                page = browser.new_page(viewport=dict(width=width, height=height))
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))

                def serve(route):
                    path = urlparse(route.request.url).path
                    if path == '/':
                        route.fulfill(body=html, content_type='text/html')
                    elif path.startswith('/prototype-assets/'):
                        route.fulfill(path=str(ROOT / 'prototype' / path.removeprefix('/prototype-assets/')))
                    elif path.startswith('/images/'):
                        route.fulfill(path=str(ROOT / path.lstrip('/')))
                    else:
                        route.abort()

                page.route('**/*', serve)
                page.goto('http://layout-test.local/')
                page.wait_for_timeout(200)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (engine, name, width)
                if name == 'login':
                    assert page.locator('.login-logo').evaluate('(e)=>e.complete && e.naturalWidth > 0')
                    username = page.locator('#username').bounding_box()
                    password = page.locator('#password').bounding_box()
                    assert password['y'] > username['y'] + username['height']
                else:
                    assert page.locator('.platform-primary a[href="/"]').is_visible()
                    assert page.locator('.platform-primary a[href="/analitica"]').is_visible()
                    assert page.locator('.platform-logout').is_visible()
                    assert page.locator('.platform-logout').inner_text() == ''
                    brand = page.locator('.platform-brand img').bounding_box()
                    assert brand['width'] <= (154 if width <= 720 else 230) + 1, brand
                    assert page.locator('.platform-primary a').first.evaluate('(e)=>getComputedStyle(e).fontSize') == '13px'
                    if width > 720:
                        assert not page.locator('.platform-more').is_visible()
                    if name != 'mapa' and name != 'lector':
                        banner = page.locator('.platform-banner img')
                        assert banner.evaluate('(e)=>e.complete && e.naturalWidth > 0')
                        assert banner.evaluate('(e)=>e.currentSrc.endsWith("banner_movil.webp")') == (width <= 720)
                        assert banner.evaluate('(e)=>Math.abs(e.getBoundingClientRect().width/e.getBoundingClientRect().height-e.naturalWidth/e.naturalHeight)<0.01')
                        assert banner.bounding_box()['width'] <= width + 1
                    if name == 'lector':
                        assert page.locator('a[href="/admin/administracion"]').count() == 0
                    elif width < 720:
                        page.locator('.platform-more summary').click()
                        assert page.locator('.platform-dropdown a').is_visible()
                        page.locator('.platform-more summary').click()
                    if name == 'mapa' and width == 1440:
                        boxes = page.locator('.support-filters select,.support-filters input,.support-filters button[type=submit],.support-filters .actions a').evaluate_all('(els)=>els.map(e=>e.getBoundingClientRect().bottom)')
                        assert max(boxes) - min(boxes) <= 1, boxes
                assert not errors, errors
                page.screenshot(path=str(output / f'{engine}-{name}-{width}.png'))
                print('OK', engine, name, width, flush=True)
                page.close()
        browser.close()
