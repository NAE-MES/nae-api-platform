"""Browser checks for long cards, map focus and close controls at Cuba's edges."""
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nae-platform-api"))
sys.path.insert(0, str(ROOT / "nae-platform-api" / "scripts"))
from app.reporting import render_support_entities_html
from export_static_map import build_static_map_html

rows = [
    {
        "entidad_apoyo_id": index,
        "entidad_nombre": "Entidad de prueba " + name,
        "provincia": name,
        "municipio": name,
        "tipo_estructura_apoyo": "Centro de apoyo",
        "lat": lat,
        "lng": lng,
        "cobertura_descriptiva": "Todos los municipios del país. " * 25,
        "direccion_fisica": "Dirección extensa de prueba " * 12,
        "servicios": "Gestión empresarial",
    }
    for index, (name, lat, lng) in enumerate([
        ("Pinar del Río", 22.42, -83.7),
        ("La Habana", 23.13, -82.38),
        ("Guantánamo", 20.14, -74.96),
    ], 1)
]
data = {"entidades": rows, "total": len(rows), "lookups": {}, "filters": {}}
screenshots = ROOT / "reportes" / "validacion_claudia_14_10"
screenshots.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.firefox.launch()
    for width, height in [(320, 740), (390, 844), (1440, 1000)]:
        for version, html in [
            ("online", render_support_entities_html(data, authenticated=True, can_review=True)),
            ("offline", build_static_map_html(data)),
        ]:
            page = browser.new_page(viewport={"width": width, "height": height}, has_touch=width < 720)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def serve(route):
                from urllib.parse import urlparse
                path = urlparse(route.request.url).path
                if path == "/":
                    route.fulfill(body=html, content_type="text/html")
                elif path.startswith("/prototype-assets/"):
                    route.fulfill(path=str(ROOT / "prototype" / path.removeprefix("/prototype-assets/")))
                elif path.startswith("/images/"):
                    route.fulfill(path=str(ROOT / path.lstrip("/")))
                else:
                    route.abort()

            page.route("**/*", serve)
            page.goto("http://map-test.local/")
            page.wait_for_timeout(400)
            for index in range(1, 4):
                selector = f'[data-entity-id="{index}"].support-map-focus' if version == "online" else f'[data-focus="{index}"]'
                page.locator(selector).click()
                page.wait_for_timeout(600)
                box = page.locator('.leaflet-popup').bounding_box()
                frame = page.locator('#support-map' if version == 'online' else '#map').bounding_box()
                assert box and frame
                assert box['x'] >= frame['x'] - 2 and box['y'] >= frame['y'] - 2, (version, width, index, box, frame)
                assert box['x'] + box['width'] <= frame['x'] + frame['width'] + 2, (version, width, box, frame)
                assert box['y'] + box['height'] <= frame['y'] + frame['height'] + 2, (version, width, box, frame)
                center = page.evaluate('map.getCenter()')
                page.wait_for_timeout(250)
                assert center == page.evaluate('map.getCenter()'), 'Popup caused repeated map movement'
                if index == 2:
                    page.screenshot(path=str(screenshots / f'{version}-{width}.png'))
                page.locator('.leaflet-popup-close-button').click()
                page.locator('.leaflet-popup').wait_for(state='detached')
            if version == 'online' and width < 720:
                page.locator('.mobile-menu-toggle').click()
                assert page.locator('#map-nav-links').is_visible()
            assert not errors, errors
            print(f'OK Firefox {version} {width}px: 3 long cards visible, stable and closable')
            page.close()
    browser.close()
