# Despliegue de NAE Platform en Ubuntu 22.04

Fecha: 2026-06-20

Este documento deja listo el despliegue de la API NAE sobre Ubuntu 22.04 con PostgreSQL, `systemd` y Nginx.

## Archivos incluidos

- `nae-platform-api/.env.example`
- `deploy/ubuntu-22.04/nae-api.service`
- `deploy/ubuntu-22.04/nginx/nae-api.conf`

## Supuestos

- El dominio o IP pública ya existe.
- PostgreSQL está disponible en el mismo servidor o en una red accesible.
- La base de datos de producción se crea antes de levantar la API.
- La ruta de instalación será `/srv/nae/nae-api-platform`.

## 1. Paquetes base

```bash
sudo apt update
sudo apt install -y git nginx postgresql postgresql-contrib \
  build-essential libpq-dev curl ca-certificates software-properties-common
```

Python 3.12:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

## 2. Usuario y ruta

```bash
sudo adduser nae
sudo usermod -aG www-data nae
sudo mkdir -p /srv/nae
sudo chown -R nae:nae /srv/nae
```

Clonado:

```bash
sudo -u nae git clone https://github.com/NAE-MES/nae-api-platform.git /srv/nae/nae-api-platform
cd /srv/nae/nae-api-platform
git checkout main
```

## 3. Entorno Python

```bash
cd /srv/nae/nae-api-platform/nae-platform-api
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Variables de entorno

Copiar `nae-platform-api/.env.example` a `nae-platform-api/.env` y ajustar valores reales.

Permisos recomendados:

```bash
chmod 600 /srv/nae/nae-api-platform/nae-platform-api/.env
chown nae:nae /srv/nae/nae-api-platform/nae-platform-api/.env
```

## 5. Base de datos

Crear usuario y base, si faltan:

```sql
CREATE USER nae WITH PASSWORD 'change-me';
CREATE DATABASE nae OWNER nae;
GRANT ALL PRIVILEGES ON DATABASE nae TO nae;
```

Ejecutar los scripts SQL en orden:

```bash
psql -U nae -d nae -h 127.0.0.1 -f sql/001_create_staging_layer.sql
psql -U nae -d nae -h 127.0.0.1 -f sql/002_create_operational_layer.sql
psql -U nae -d nae -h 127.0.0.1 -f sql/003_create_analytics_layer.sql
psql -U nae -d nae -h 127.0.0.1 -f sql/004_create_operational_multiselect_tables.sql
psql -U nae -d nae -h 127.0.0.1 -f sql/005_update_modelo_datos_v11.sql
```

## 6. Servicio systemd

Instalar la unidad:

```bash
sudo cp /srv/nae/nae-api-platform/deploy/ubuntu-22.04/nae-api.service /etc/systemd/system/nae-api.service
sudo systemctl daemon-reload
sudo systemctl enable nae-api
sudo systemctl start nae-api
sudo systemctl status nae-api
```

Logs:

```bash
journalctl -u nae-api -f
```

## 7. Nginx

Instalar el sitio:

```bash
sudo cp /srv/nae/nae-api-platform/deploy/ubuntu-22.04/nginx/nae-api.conf /etc/nginx/sites-available/nae-api
sudo ln -sf /etc/nginx/sites-available/nae-api /etc/nginx/sites-enabled/nae-api
sudo nginx -t
sudo systemctl reload nginx
```

Reemplazar `server_name _;` por el dominio real antes de producción.

## 8. TLS

Si hay dominio público:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tu-dominio.com
```

## 9. Validación

```bash
curl http://127.0.0.1:8000/api/v1/salud
curl http://127.0.0.1:8000/api/v1/resumen
curl -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8000/api/v1/respuestas/1
```

Validación mínima antes del corte:

- `GET /api/v1/salud`
- `GET /api/v1/resumen`
- `GET /api/v1/resumen.csv`
- `POST /api/v1/respuestas`
- `POST /api/v1/pipelines/staging/raw-to-staging`
- `POST /api/v1/pipelines/operational/staging-to-operational`
- `POST /api/v1/pipelines/analytics/operational-to-analytics`

## 10. Checklist de corte

- backup de la base de datos
- `dev` fusionada en `main`
- despliegue hecho desde `main`
- variables reales cargadas
- Nginx y TLS activos
- smoke test verde
- Google Apps Script apuntando a la URL pública

