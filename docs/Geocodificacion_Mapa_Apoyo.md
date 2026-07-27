# Geocodificación del mapa de entidades de apoyo

## Objetivo

El mapa público usa coordenadas para ubicar las entidades encuestadas. La encuesta no debe pedir latitud y longitud a los usuarios; esos datos se derivan después de recibir la respuesta.

## Criterio operativo

1. Si existe una coordenada validada en `operational.geocodificacion_entidades`, el mapa usa esa coordenada.
2. Si no existe coordenada validada, el mapa usa la coordenada del municipio como ubicación estimada.
3. Las coordenadas exactas deben quedar trazables con fuente, confianza, estado y fecha de validación.

## Estados

- `pendiente_revision`: registro creado, pero aún sin coordenada confiable.
- `geocodificada`: coordenada obtenida por un proceso automático o semiautomático.
- `validada`: coordenada revisada y aprobada para uso público.
- `rechazada`: coordenada descartada.

## Aplicar estructura en producción

Desde el servidor:

```bash
cd /srv/nae/nae-api-platform/nae-platform-api
sudo -u postgres psql -d nae -f sql/007_create_geocoding_layer.sql
sudo systemctl restart nae-api
```

## Ejecutar geocodificación automática inicial

Primero probar sin escribir:

```bash
cd /srv/nae/nae-api-platform/nae-platform-api
python3 scripts/geocode_pending_entities.py --limit 5
```

Si los resultados tienen sentido, ejecutar guardando:

```bash
python3 scripts/geocode_pending_entities.py --limit 20 --apply
sudo systemctl restart nae-api
```

El script usa Nominatim/OpenStreetMap con baja frecuencia entre consultas. No debe ejecutarse como carga masiva agresiva. Para más volumen se debe usar un proveedor contratado, una instancia propia de Nominatim o una fuente institucional.

Parámetros útiles:

```bash
python3 scripts/geocode_pending_entities.py --limit 50 --delay 1.5 --min-confidence 0.70 --apply
```

- `--limit`: cantidad de entidades pendientes a procesar.
- `--delay`: segundos entre consultas.
- `--min-confidence`: confianza mínima para dejar el resultado como `geocodificada`.
- `--apply`: guarda en la BD; sin este parámetro solo muestra resultados.

## Consultar entidades sin coordenada exacta

```sql
SELECT
    op.id AS operational_respuesta_id,
    COALESCE(m.entidad_nombre, op.nombre_institucion) AS entidad,
    p.nombre AS provincia,
    mu.nombre AS municipio,
    m.direccion_fisica,
    m.telefonos,
    m.correo_electronico
FROM operational.respuestas_encuesta op
JOIN operational.provincias p ON p.id = op.provincia_id
JOIN operational.municipios mu ON mu.id = op.municipio_id
LEFT JOIN operational.respuestas_mapeo_entidad m ON m.operational_respuesta_id = op.id
LEFT JOIN operational.geocodificacion_entidades g ON g.operational_respuesta_id = op.id
WHERE COALESCE(op.version_encuesta, '') = 'mapeo_estructuras_v1'
  AND (
      g.id IS NULL
      OR g.estado NOT IN ('geocodificada', 'validada')
      OR g.lat IS NULL
      OR g.lng IS NULL
  )
ORDER BY p.nombre, mu.nombre, entidad;
```

## Registrar una coordenada validada manualmente

```sql
INSERT INTO operational.geocodificacion_entidades (
    operational_respuesta_id,
    direccion_original,
    provincia,
    municipio,
    lat,
    lng,
    fuente,
    confianza,
    estado,
    observacion,
    fecha_validacion,
    validado_por
)
VALUES (
    123,
    'Dirección exacta de la entidad',
    'La Habana',
    'Plaza de la Revolución',
    23.1250000,
    -82.3853000,
    'revision_manual',
    1.00,
    'validada',
    'Validada con mapa institucional',
    NOW(),
    'equipo_nae'
)
ON CONFLICT (operational_respuesta_id)
DO UPDATE SET
    direccion_original = EXCLUDED.direccion_original,
    provincia = EXCLUDED.provincia,
    municipio = EXCLUDED.municipio,
    lat = EXCLUDED.lat,
    lng = EXCLUDED.lng,
    fuente = EXCLUDED.fuente,
    confianza = EXCLUDED.confianza,
    estado = EXCLUDED.estado,
    observacion = EXCLUDED.observacion,
    fecha_validacion = EXCLUDED.fecha_validacion,
    validado_por = EXCLUDED.validado_por,
    updated_at = NOW();
```

## Próxima mejora recomendada

Crear una vista administrativa para revisar entidades pendientes, buscar coordenadas y aprobarlas sin ejecutar SQL manual. Esa vista debe escribir en `operational.geocodificacion_entidades`.
