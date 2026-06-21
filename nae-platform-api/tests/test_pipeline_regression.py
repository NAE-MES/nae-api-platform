from __future__ import annotations

import json
import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "nae")
os.environ.setdefault("DB_USER", "nae")
os.environ.setdefault("DB_PASSWORD", "nae")
os.environ.setdefault("API_TOKEN", "test-token")

import app.analytics_pipeline as analytics_pipeline
import app.operational_pipeline as operational_pipeline
import app.staging_pipeline as staging_pipeline


class FakeResult:
    def __init__(self, scalar_one_value=None, scalar_one_or_none_value=None, scalar_value=None, rows=None):
        self._scalar_one_value = scalar_one_value
        self._scalar_one_or_none_value = scalar_one_or_none_value
        self._scalar_value = scalar_value
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar_one_value

    def scalar_one_or_none(self):
        return self._scalar_one_or_none_value

    def scalar(self):
        return self._scalar_value

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def one_or_none(self):
        if not self._rows:
            return None
        return self._rows[0]

    def scalars(self):
        return self


class FakeDB:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def execute(self, query, params=None):
        self.calls.append({"query": str(query), "params": params})
        if not self.results:
            raise AssertionError("Unexpected DB execute call")
        return self.results.pop(0)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


SAMPLE_PAYLOAD = {
    "0.3 Género de la persona que responde": "Mujer",
    "0.4 Nivel de instrucción terminado": "Universitario",
    "1.1 Provincia": "La Habana",
    "1.2 Municipio": "Plaza de la Revolución",
    "1.3 Ámbito principal de actuación de la entidad": "Municipal",
    "1.4 Tipo de institución que representa": "Gobierno municipal",
    "1.5 Nombre oficial de la institución": "NAE Smoke Test",
    "1.6 Nivel de involucramiento en actividades de formación sobre NAE": "Medio",
    "3.1 Nivel de capacitación de formadores locales": "Medianamente capacitados",
    "3.3 Principal necesidad del municipio": "Coordinación institucional",
    "4.1 Nivel de interés de los actores de gobierno en formación sobre NAE": "Medio",
    "5.1 Existencia de mecanismos de coordinación institucional": "Existen con poca coordinación",
    "3.2 Temas prioritarios de formación": ["Género y NAE", "Gestión empresarial"],
    "5.3 Instituciones que participan en actividades formativas": ["Gobierno municipal", "Universidad"],
    "5.4 Principales limitaciones": ["Falta de coordinación", "Limitaciones financieras"],
}


def test_validate_payload_infers_version_and_accepts_realistic_payload():
    result = staging_pipeline.validate_payload(SAMPLE_PAYLOAD)

    assert result.state == "validada"
    assert result.normalized["version_encuesta"] == "1.1"
    assert result.normalized["provincia"] == "La Habana"
    assert result.normalized["nivel_instruccion"] == "Universitario"
    assert not result.errors


def test_validate_payload_keeps_current_form_values_when_legacy_aliases_are_missing():
    payload = dict(SAMPLE_PAYLOAD)
    payload.pop("4.1 Nivel de interés de los actores de gobierno en formación sobre NAE")
    payload.pop("5.1 Existencia de mecanismos de coordinación institucional")
    payload["3.4 Nivel de interés de los actores de gobierno en formación sobre NAE"] = "Medio"
    payload["4.1 Conoce la existencia de mecanismos de coordinación institucional"] = "Sí, funcionan sistemáticamente"

    result = staging_pipeline.validate_payload(payload)

    assert result.state == "validada"
    assert result.normalized["nivel_interes_gobierno"] == "Medio"
    assert result.normalized["mecanismos_coordinacion"] == "Sí, funcionan sistemáticamente"
    assert not result.errors


def test_validate_payload_rejects_invalid_catalogs():
    payload = dict(SAMPLE_PAYLOAD)
    payload["1.1 Provincia"] = "Atlantis"
    payload["0.3 Género de la persona que responde"] = "Otro mundo"

    result = staging_pipeline.validate_payload(payload)

    assert result.state == "rechazada"
    assert any(error["campo"] == "provincia" for error in result.errors)
    assert any(error["campo"] == "genero" for error in result.errors)


def test_process_raw_to_staging_persists_validated_row(monkeypatch):
    raw_payload = json.dumps(SAMPLE_PAYLOAD, ensure_ascii=False)
    fake_db = FakeDB(
        [
            FakeResult(scalar_one_value=11),
            FakeResult(rows=[
                {
                    "id": 5,
                    "id_respuesta_origen": "smoke-1",
                    "formulario_origen": "Encuesta NAE v1.1",
                    "fecha_respuesta": "2026-06-20T10:00:00",
                    "payload": raw_payload,
                }
            ]),
            FakeResult(),
            FakeResult(),
            FakeResult(),
        ]
    )
    monkeypatch.setattr(staging_pipeline, "SessionLocal", lambda: fake_db)

    result = staging_pipeline.process_raw_to_staging(limit=10)

    assert result["stats"] == {
        "total": 1,
        "validada": 1,
        "con_observaciones": 0,
        "rechazada": 0,
        "errores_registrados": 0,
    }
    assert fake_db.commits >= 2
    assert fake_db.closed is True
    assert any(
        call["params"] and call["params"].get("estado") == "validada"
        for call in fake_db.calls
        if "UPDATE raw.respuestas_formulario" in call["query"]
    )


def test_process_staging_to_operational_splits_multiselect_values(monkeypatch):
    raw_payload = json.dumps(
        {
            "3.2 Temas prioritarios de formación": "Género y NAE | Gestión empresarial",
            "5.3 Instituciones que participan en actividades formativas": ["Gobierno municipal", "Universidad"],
            "5.4 Principales limitaciones": "Falta de coordinación | Limitaciones financieras",
        },
        ensure_ascii=False,
    )
    fake_db = FakeDB(
        [
            FakeResult(scalar_one_value=21),
            FakeResult(rows=[
                {
                    "id": 7,
                    "raw_respuesta_id": 5,
                    "id_respuesta_origen": "smoke-1",
                    "formulario_origen": "Encuesta NAE v1.1",
                    "fecha_respuesta": "2026-06-20T10:00:00",
                    "raw_payload": raw_payload,
                    "consentimiento": "Sí, acepto",
                    "version_encuesta": "1.1",
                    "genero": "Mujer",
                    "nivel_conocimiento_municipio": None,
                    "nivel_instruccion": "Universitario",
                    "provincia": "La Habana",
                    "municipio": "Plaza de la Revolución",
                    "ambito_actuacion": "Municipal",
                    "tipo_institucion": "Gobierno municipal",
                    "nombre_institucion": "NAE Smoke Test",
                    "nivel_involucramiento": "Medio",
                    "nivel_capacitacion_formadores": "Medianamente capacitados",
                    "mayoria_titulares_emprendimientos": "Mujeres",
                    "porcentaje_mujeres_directivas": "31–50%",
                    "programas_mujeres_emprendedoras": "Sí",
                    "descripcion_programa_mujeres": "Programa piloto",
                    "principal_necesidad": "Coordinación institucional",
                    "nivel_interes_gobierno": "Medio",
                    "mecanismos_coordinacion": "Existen con poca coordinación",
                    "estado_validacion": "validada",
                }
            ]),
            FakeResult(),
            FakeResult(),
        ]
    )
    captured = []

    monkeypatch.setattr(operational_pipeline, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(operational_pipeline, "_resolve_provincia", lambda db, provincia: 101)
    monkeypatch.setattr(operational_pipeline, "_resolve_municipio", lambda db, provincia_id, municipio: 202)
    monkeypatch.setattr(operational_pipeline, "_upsert_operational_response", lambda db, row, provincia_id, municipio_id: 303)

    def capture_insert(db, operational_respuesta_id, table_name, column_name, values):
        captured.append((table_name, column_name, values))

    monkeypatch.setattr(operational_pipeline, "_insert_child_values", capture_insert)

    result = operational_pipeline.process_staging_to_operational(limit=10)

    assert result["stats"] == {
        "total": 1,
        "cargada": 1,
        "saltada": 0,
        "errores_registrados": 0,
    }
    assert ("respuestas_temas_formacion", "tema_formacion", ["Género y NAE", "Gestión empresarial"]) in captured
    assert ("respuestas_instituciones_participantes", "institucion_participante", ["Gobierno municipal", "Universidad"]) in captured
    assert ("respuestas_limitaciones", "limitacion", ["Falta de coordinación", "Limitaciones financieras"]) in captured


def test_process_operational_to_analytics_maps_dimensions(monkeypatch):
    fake_db = FakeDB(
        [
            FakeResult(scalar_one_value=31),
            FakeResult(rows=[
                {
                    "id": 9,
                    "raw_respuesta_id": 5,
                    "staging_respuesta_id": 7,
                    "fecha_respuesta": "2026-06-20T10:00:00",
                    "consentimiento": "Sí, acepto",
                    "version_encuesta": "1.1",
                    "genero": "Mujer",
                    "ambito_actuacion": "Municipal",
                    "tipo_institucion": "Gobierno municipal",
                    "nombre_institucion": "NAE Smoke Test",
                    "nivel_involucramiento": "Medio",
                    "nivel_capacitacion_formadores": "Medianamente capacitados",
                    "nivel_conocimiento_municipio": None,
                    "nivel_instruccion": "Universitario",
                    "porcentaje_mujeres_directivas": "31–50%",
                    "programas_mujeres_emprendedoras": "Sí",
                    "descripcion_programa_mujeres": "Programa piloto",
                    "mayoria_titulares_emprendimientos": "Mujeres",
                    "principal_necesidad": "Coordinación institucional",
                    "nivel_interes_gobierno": "Medio",
                    "mecanismos_coordinacion": "Existen con poca coordinación",
                    "estado_validacion": "validada",
                    "provincia_id": 1,
                    "provincia_nombre": "La Habana",
                    "municipio_id": 2,
                    "municipio_nombre": "Plaza de la Revolución",
                }
            ]),
            FakeResult(),
            FakeResult(),
            FakeResult(),
            FakeResult(),
            FakeResult(),
        ]
    )
    resolved = []

    monkeypatch.setattr(analytics_pipeline, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(analytics_pipeline, "_resolve_territorio", lambda db, provincia_id, municipio_id, provincia_nombre, municipio_nombre: 1001)
    monkeypatch.setattr(analytics_pipeline, "_resolve_institucion", lambda db, tipo_institucion, nombre_institucion: 1002)
    monkeypatch.setattr(analytics_pipeline, "_resolve_estado_validacion", lambda db, estado_validacion: 1003)
    monkeypatch.setattr(analytics_pipeline, "_resolve_genero", lambda db, genero: 1004)
    monkeypatch.setattr(analytics_pipeline, "_resolve_respuesta_genero", lambda db, *args: 1005)
    monkeypatch.setattr(analytics_pipeline, "_upsert_fact", lambda db, row, territorio_id, institucion_id, estado_id, genero_id, respuesta_genero_id: resolved.append(
        (territorio_id, institucion_id, estado_id, genero_id, respuesta_genero_id)
    ))

    result = analytics_pipeline.process_operational_to_analytics(limit=10)

    assert result["stats"] == {"total": 1, "cargada": 1, "saltada": 0, "errores_registrados": 0}
    assert resolved == [(1001, 1002, 1003, 1004, 1005)]
