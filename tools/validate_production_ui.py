"""Read-only browser smoke checks against the deployed, authenticated pages."""
from hashlib import sha256
from pathlib import Path
import re
import shlex
from urllib.parse import parse_qs, urljoin, urlparse

import paramiko
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://mapeo-plataforma.mes.gob.cu'
OUTPUT = ROOT / 'reportes/reparacion_interfaz_15_10'
OUTPUT.mkdir(parents=True, exist_ok=True)


def session_cookie():
    sections = (ROOT / 'acceso.txt').read_text(encoding='utf-8').split('VM Mapeo')

    def credentials(section):
        return (re.search(r'\b\d+\.\d+\.\d+\.\d+\b', section).group(),
                re.search(r'user:\s*(\S+)', section).group(1),
                re.search(r'pass:\s*(\S+)', section).group(1))

    bh, bu, bp = credentials(sections[0])
    th, tu, tp = credentials(sections[1])
    bastion, target = paramiko.SSHClient(), paramiko.SSHClient()
    for client in [bastion, target]:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        bastion.connect(bh, username=bu, password=bp, timeout=20)
        channel = bastion.get_transport().open_channel('direct-tcpip', (th, 22), ('127.0.0.1', 0))
        target.connect(th, username=tu, password=tp, sock=channel, timeout=20)
        code = 'from app.main import _create_session_cookie; from app.config import ANALYTICS_USERNAME; print(_create_session_cookie(ANALYTICS_USERNAME))'
        script = 'set -e\ncd /srv/nae/nae-api-platform/nae-platform-api\n./.venv/bin/python -c ' + shlex.quote(code)
        stdin, stdout, stderr = target.exec_command("sudo -S -p '' bash -c " + shlex.quote(script), timeout=60)
        stdin.write(tp + '\n')
        stdin.flush()
        stdin.channel.shutdown_write()
        cookie = stdout.read().decode().strip()
        assert stdout.channel.recv_exit_status() == 0, 'No se pudo preparar la sesion de prueba'
        assert cookie and '\n' not in cookie
        return cookie
    finally:
        target.close()
        bastion.close()


cookie = session_cookie()
with sync_playwright() as p:
    for engine in ['firefox', 'chromium']:
        browser = getattr(p, engine).launch()
        for width, height in [(441, 758), (1468, 900)]:
            context = browser.new_context(viewport={'width': width, 'height': height})
            context.add_cookies([dict(name='nae_analytics_session', value=cookie,
                                     domain=urlparse(BASE).hostname, path='/', secure=True, httpOnly=True)])
            page = context.new_page()
            for name, path in [('mapa', '/mapa-apoyo'), ('analitica', '/analitica'), ('admin', '/admin/administracion')]:
                response = page.goto(BASE + path, wait_until='domcontentloaded', timeout=60000)
                assert response.status == 200 and '/login' not in page.url, (name, response.status)
                page.wait_for_function('document.querySelector(".platform-brand img")?.complete && getComputedStyle(document.querySelector(".platform-primary a")).fontSize==="13px"')
                sheet = page.locator('link[rel=stylesheet][href*="styles.css"]').get_attribute('href')
                version = parse_qs(urlparse(sheet).query)['v'][0]
                css_response = context.request.get(urljoin(BASE, sheet))
                assert css_response.status == 200
                assert sha256(css_response.body()).hexdigest()[:12] == version
                brand = page.locator('.platform-brand img').bounding_box()
                page.locator('.platform-brand img').evaluate('(e)=>e.decode()')
                assert brand['width'] <= (154 if width <= 720 else 230) + 1, (name, brand)
                logout = page.locator('.platform-logout')
                assert logout.inner_text() == '' and logout.is_visible()
                assert logout.bounding_box()['width'] <= 41
                if width > 720:
                    assert not page.locator('.platform-more').is_visible()
                else:
                    assert not page.locator('.platform-more').is_visible()
                    assert not page.locator('.platform-admin').is_visible()
                banner = page.locator('.map-banner' if name == 'mapa' else '.platform-banner img')
                banner.evaluate('(e)=>e.decode()')
                assert banner.evaluate('(e)=>Math.abs(e.getBoundingClientRect().width/e.getBoundingClientRect().height-e.naturalWidth/e.naturalHeight)<0.01')
                assert banner.bounding_box()['width'] <= width + 1
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                page.evaluate('()=>document.fonts.ready')
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                page.wait_for_timeout(250)
                if name == 'mapa' and width == 1468 and engine == 'firefox':
                    page.locator('.platform-brand img').screenshot(path=str(OUTPUT / 'firefox-logo-desktop.png'))
                    banner.screenshot(path=str(OUTPUT / 'firefox-banner-desktop.png'))
                page.screenshot(path=str(OUTPUT / f'{engine}-{name}-{width}.png'))
                print('OK produccion:', engine, name, width, 'CSS versionado, banner completo, salida solo icono', flush=True)
                if name == 'mapa' and width == 1468:
                    for next_width, next_height in [(441,758),(390,844),(844,390),(1468,900)]:
                        page.set_viewport_size({'width':next_width,'height':next_height})
                        page.wait_for_timeout(600)
                        assert page.evaluate('map.getBounds().contains(cubaBounds)'), (engine,next_width,'resize without reload')
                        assert page.locator('#reset-map').is_disabled()
                        if next_width < 720:
                            assert not page.locator('.platform-admin').is_visible()
                            assert not page.locator('.platform-more').is_visible()
                    print('OK produccion sin recargar:',engine,'escritorio/movil/rotacion/escritorio',flush=True)
            context.close()
        browser.close()
