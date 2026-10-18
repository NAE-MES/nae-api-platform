"""Check real input gestures against the local map preview."""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8010'
OUT = Path(__file__).resolve().parents[1] / 'reportes/validacion_agrupacion_territorial'

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True)
    context.request.post(BASE + '/login', form={'username': 'admin', 'password': 'nae-local-2026', 'next': '/mapa-apoyo'})
    page = context.new_page()
    page.goto(BASE + '/mapa-apoyo', wait_until='domcontentloaded')
    page.wait_for_function('typeof territoryController !== "undefined"')
    page.locator('#support-map').scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    page.evaluate('window.scrollBy(0,document.getElementById("support-map").getBoundingClientRect().top-120)')
    page.evaluate('markerLayer.getLayers().find(m=>m.options.title?.startsWith("La Habana ")).openPopup()')
    page.wait_for_timeout(200)
    assert page.locator('.territory-group-popup .leaflet-popup-content').bounding_box()['width'] <= 237
    page.screenshot(path=str(OUT / 'mobile-group-compact.png'))
    page.locator('.leaflet-popup-close-button').click()
    page.locator('#support-map').scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    cdp = context.new_cdp_session(page)
    box = page.locator('#support-map').bounding_box()
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    initial_zoom = page.evaluate('map.getZoom()')
    scale = page.evaluate('visualViewport.scale')

    def touch(kind, points):
        cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': points})

    touch('touchStart', [{'x': x-30, 'y': y, 'id': 1}, {'x': x+30, 'y': y, 'id': 2}])
    for distance in range(36, 126, 9):
        touch('touchMove', [{'x': x-distance, 'y': y, 'id': 1}, {'x': x+distance, 'y': y, 'id': 2}])
        page.wait_for_timeout(30)
    touch('touchEnd', [])
    page.wait_for_timeout(800)
    assert page.evaluate('map.getZoom()') > initial_zoom, 'Pinch did not zoom the map'
    assert page.evaluate('visualViewport.scale') == scale, 'Pinch zoomed the whole page'
    before = page.evaluate('map.getCenter().lng')
    touch('touchStart', [{'x': x, 'y': y+80, 'id': 1}])
    for offset in range(10, 91, 10):
        touch('touchMove', [{'x': x+offset, 'y': y+80, 'id': 1}])
        page.wait_for_timeout(30)
    touch('touchEnd', [])
    page.wait_for_timeout(800)
    assert abs(page.evaluate('map.getCenter().lng') - before) > 0.01, 'Touch drag did not pan'
    print('OK mobile: compact popup, pinch zooms map (not page), one-finger drag', flush=True)
    context.close()

    for engine in ['chromium', 'firefox']:
        desktop_browser = getattr(p, engine).launch()
        ctx = desktop_browser.new_context(viewport={'width': 1440, 'height': 1000})
        ctx.request.post(BASE + '/login', form={'username': 'admin', 'password': 'nae-local-2026', 'next': '/mapa-apoyo'})
        tab = ctx.new_page()
        tab.goto(BASE + '/mapa-apoyo', wait_until='domcontentloaded')
        tab.wait_for_function('typeof territoryController !== "undefined"')
        tab.set_viewport_size({'width': 390, 'height': 844})
        tab.locator('#support-map').scroll_into_view_if_needed()
        tab.wait_for_timeout(500)
        tab.locator('.leaflet-control-zoom-in').click()
        tab.wait_for_timeout(400)
        box = tab.locator('#support-map').bounding_box()
        x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2 + 80
        before = tab.evaluate('map.getCenter().lng')
        tab.mouse.move(x, y)
        tab.mouse.down()
        tab.mouse.move(x+80, y, steps=12)
        tab.mouse.up()
        tab.wait_for_timeout(800)
        assert abs(tab.evaluate('map.getCenter().lng') - before) > 0.01
        print('OK', engine, 'resize to mobile: mouse drag', flush=True)
        desktop_browser.close()
    browser.close()
