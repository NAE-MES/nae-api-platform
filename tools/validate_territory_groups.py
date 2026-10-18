"""Exercise the local review server and its territorial marker groups."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reportes/validacion_agrupacion_territorial'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8010'
with sync_playwright() as p:
    for engine in ['chromium', 'firefox']:
        browser = getattr(p, engine).launch()
        for width, height in [(1440,1000),(390,844)]:
            context = browser.new_context(viewport={'width':width,'height':height}, has_touch=width<720)
            response = context.request.post(BASE+'/login', form={'username':'admin','password':'nae-local-2026','next':'/mapa-apoyo'})
            assert response.status == 200
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(BASE+'/mapa-apoyo', wait_until='domcontentloaded')
            page.wait_for_function('typeof territoryController !== "undefined"')
            page.wait_for_timeout(400)
            stats = page.evaluate('({entities:supportEntities.length,groups:territoryController.getGroups(),visible:markerLayer.getLayers().length})')
            assert stats['entities'] == 146
            expected = page.evaluate('new Set(supportEntities.map(e=>e.province==="La Habana"?"La Habana":e.province+"|"+e.municipality)).size')
            assert stats['visible'] == expected == len(stats['groups'])
            assert sum(group['total'] for group in stats['groups']) == 146
            assert len([g for g in stats['groups'] if g['title']=='La Habana']) == 1
            assert page.locator('.territory-count').count() == sum(g['total'] > 1 for g in stats['groups'])
            assert page.locator('.territory-count').filter(has_text='28').count() == 1
            assert page.locator('#support-list .support-item:visible').count() == 10
            page.locator('#support-map').scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            page.locator('.leaflet-panel').screenshot(path=str(OUT/f'{engine}-{width}-general.png'))
            page.evaluate('()=>{markerLayer.getLayers().find(m=>m.options.title?.startsWith("La Habana ·")).openPopup();}')
            assert 'entidades de apoyo' in page.locator('.territory-popup').inner_text()
            page.locator('.territory-popup button').click()
            assert page.evaluate('supportEntities.filter(e=>e.province==="La Habana").every(e=>markerLayer.hasLayer(markersByEntityId.get(String(e.id))))')
            page.locator('.leaflet-panel').screenshot(path=str(OUT/f'{engine}-{width}-habana.png'))
            page.locator('#reset-map').click()
            page.wait_for_timeout(400)
            assert page.evaluate('markerLayer.getLayers().length') == expected
            first = page.locator('.support-map-focus').first
            entity_id = first.get_attribute('data-entity-id')
            first.click()
            page.wait_for_timeout(600)
            assert page.evaluate('(id)=>markerLayer.hasLayer(markersByEntityId.get(id))', entity_id)
            selected_name = page.evaluate('(id)=>supportEntities.find(e=>String(e.id)===id).name', entity_id)
            assert selected_name in page.locator('.leaflet-popup-content').inner_text()
            page.locator('.leaflet-popup-close-button').click()
            page.goto(BASE+'/mapa-apoyo?provincia=La%20Habana', wait_until='domcontentloaded')
            page.wait_for_function('typeof territoryController !== "undefined"')
            assert page.evaluate('markerLayer.getLayers().length') == 1
            assert page.evaluate('territoryController.getGroups()[0].total === supportEntities.length')
            assert not errors, errors
            print('OK',engine,width,stats['entities'],'entidades;',expected,'grupos; Habana, detalle, listado y filtro',flush=True)
            context.close()
        for filename in ['mapa_agrupado_territorial.html', 'mapa_agrupado_calles_cuba.html']:
            context = browser.new_context(viewport={'width':390,'height':844}, offline=True, has_touch=True)
            page = context.new_page()
            errors, network = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: network.append(request.url) if request.url.startswith(('http:','https:')) else None)
            page.goto((ROOT/'reportes/vista_local'/filename).as_uri())
            page.wait_for_timeout(300)
            assert page.evaluate('payload.entities.length') == 146
            assert page.evaluate('markerLayer.getLayers().length') == 45
            assert page.evaluate('territoryController.getGroups().reduce((n,g)=>n+g.total,0)') == 146
            page.evaluate('()=>{map.setZoom(9,{animate:false});}')
            assert page.evaluate('markerLayer.getLayers().length') == 146
            page.locator('#reset-map').click()
            page.wait_for_timeout(400)
            assert page.evaluate('markerLayer.getLayers().length') == 45
            page.locator('#province').select_option('La Habana')
            page.evaluate('()=>{resetMapView();}')
            assert page.evaluate('markerLayer.getLayers().length') == 1
            assert page.evaluate('filtered.every(e=>e.province==="La Habana")')
            page.locator('[data-focus]').first.click()
            assert page.locator('.leaflet-popup-content').is_visible()
            assert not errors and not network, (errors,network)
            print('OK',engine,filename,'sin red; agrupacion, zoom, reset, filtro y detalle',flush=True)
            context.close()
        browser.close()
