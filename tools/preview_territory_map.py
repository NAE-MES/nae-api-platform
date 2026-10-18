"""Local map review using an exported snapshot, without any DB access."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

from dotenv import load_dotenv
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'nae-platform-api'
sys.path.insert(0, str(API))
sys.path.insert(0, str(API / 'scripts'))
load_dotenv(API / '.env')
os.environ.update(ANALYTICS_USERNAME='admin', ANALYTICS_PASSWORD='nae-local-2026',
                  ANALYTICS_USERS='', ANALYTICS_REVIEW_USERS='', SESSION_COOKIE_SECURE='false',
                  SESSION_SECRET=secrets.token_urlsafe(48), API_TOKEN=secrets.token_urlsafe(32))
from app import main
from app.reporting import _entity_sort_key

snapshot = (ROOT / 'reportes/mapa_exportable/mapa_entidades_apoyo.html').read_text(encoding='utf-8')
payload, _ = json.JSONDecoder().raw_decode(snapshot.split('const payload = ', 1)[1])
fields = dict(id='entidad_apoyo_id', name='entidad_nombre', type='tipo_estructura_apoyo',
              province='provincia', municipality='municipio', coverage='cobertura_descriptiva',
              services='servicios', contact='persona_contacto_cargo', phone='telefonos',
              email='correo_electronico', address='direccion_fisica', lat='lat', lng='lng',
              source='coordinate_source', status='coordinate_status')
rows = []
for entity in payload['entities']:
    row = {target: entity.get(source) for source, target in fields.items()}
    row['servicios_detalle'] = [{'servicio': service, 'ofrece_actualmente': True}
                               for service in [*entity.get('serviceList', []), *entity.get('otherServices', [])]]
    rows.append(row)
rows.sort(key=_entity_sort_key)


def snapshot_entities(limit=200, provincia=None, municipio=None, tipo=None, servicio=None, q=None):
    selected = [row for row in rows if (not provincia or row['provincia'] == provincia)
                and (not municipio or row['municipio'] == municipio)
                and (not tipo or row['tipo_estructura_apoyo'] == tipo)
                and (not servicio or any(item['servicio'] == servicio for item in row['servicios_detalle']))
                and (not q or q.casefold() in ' '.join(str(value) for value in row.values()).casefold())]
    return dict(entidades=selected[:limit], total=min(len(selected), limit),
                filters=dict(provincia=provincia, municipio=municipio, tipo=tipo, servicio=servicio, q=q, limit=limit),
                lookups=dict(provincias=payload['lookups']['provinces'],
                             municipios=sorted({row['municipio'] for row in rows if not provincia or row['provincia'] == provincia}),
                             tipos=payload['lookups']['types'], servicios=payload['lookups']['services']))


main.get_support_entities = snapshot_entities
PREVIEW = ROOT / 'reportes/vista_local'
OFFLINE = {'/mapa-offline.html': ('mapa_agrupado_territorial.html', False),
           '/mapa-offline-calles.html': ('mapa_agrupado_calles_cuba.html', True)}


@main.app.middleware('http')
async def map_review_only(request, call_next):
    if request.url.path in OFFLINE:
        if not main._has_analytics_access(request):
            return main._redirect_to_login(request)
        name, _ = OFFLINE[request.url.path]
        return FileResponse(PREVIEW / name, media_type='text/html', filename=name)
    blocked = request.method not in {'GET', 'HEAD'} and request.url.path != '/login'
    blocked = blocked or request.url.path.startswith(('/admin/', '/analitica', '/respuestas/', '/api/v1/pipelines'))
    if blocked:
        return JSONResponse({'detail': 'Vista local de revision del mapa: base de datos desconectada y operaciones de escritura bloqueadas.'}, status_code=403)
    return await call_next(request)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8010)
    args = parser.parse_args()
    from export_static_map import build_static_map_html
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name, national_streets in OFFLINE.values():
        (PREVIEW / name).write_text(build_static_map_html(snapshot_entities(limit=1000), national_streets=national_streets), encoding='utf-8')
    uvicorn.run(main.app, host='127.0.0.1', port=args.port)
