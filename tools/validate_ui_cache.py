"""Ensure a cached pre-redesign stylesheet cannot break the current header."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'nae-platform-api'))
from app.reporting import _platform_header
from app.ui_assets import STYLESHEET_URL

old_css = subprocess.check_output(['git', 'show', 'f5e25f2:prototype/styles.css'], cwd=ROOT)
new_css = (ROOT / 'prototype/styles.css').read_bytes()
assert old_css != new_css
requested = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requested.append(self.path)
        path = urlparse(self.path).path
        mime = 'text/html; charset=utf-8'
        if path == '/seed':
            body = b'<link rel="stylesheet" href="/prototype-assets/styles.css"><p>Previous version</p>'
        elif path == '/current':
            body = f'<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="{STYLESHEET_URL}">{_platform_header("analitica", True)}'.encode()
        elif path == '/prototype-assets/styles.css':
            body = new_css if urlparse(self.path).query else old_css
            mime = 'text/css'
        elif path.startswith('/prototype-assets/icons/'):
            body = (ROOT / 'prototype' / path.removeprefix('/prototype-assets/')).read_bytes()
            mime = 'image/svg+xml'
        elif path.startswith('/images/'):
            body = (ROOT / path.lstrip('/')).read_bytes()
            mime = 'image/svg+xml' if path.endswith('.svg') else 'image/webp'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        if mime == 'text/css':
            self.send_header('Cache-Control', 'public, max-age=86400')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
url = f'http://127.0.0.1:{server.server_port}'
try:
    with sync_playwright() as p:
        for engine in ['chromium', 'firefox']:
            browser = getattr(p, engine).launch()
            for width in [441, 1440]:
                page = browser.new_page(viewport={'width': width, 'height': 900})
                requested.clear()
                page.goto(url + '/seed')
                page.goto(url + '/seed')
                assert requested.count('/prototype-assets/styles.css') == 1, requested
                page.goto(url + '/current')
                assert STYLESHEET_URL in requested, requested
                assert page.locator('.platform-brand img').bounding_box()['width'] <= (154 if width < 720 else 230) + 1
                assert page.locator('.platform-logout').inner_text() == ''
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                if width > 720:
                    assert not page.locator('.platform-more').is_visible()
                print('OK warm cache:', engine, width, flush=True)
                page.close()
            browser.close()
finally:
    server.shutdown()
    server.server_close()
    thread.join()
