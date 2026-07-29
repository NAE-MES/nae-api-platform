from __future__ import annotations

from typing import Any, Dict, List, Optional


MAPEO_VERSION = "mapeo_estructuras_v1"

SCALAR_FIELDS = {
    "entidad_nombre": ["0.1* Entidad a la que pertenece"],
    "rol_principal": ["0.2* Rol principal en la entidad"],
    "municipio_responde_contexto": ["0.3* Municipio sobre el que responde"],
    "nivel_conocimiento_nae": ["0.4* Nivel de conocimiento sobre los NAE en el municipio"],
    "datos_contacto_directo": ["0.5* Datos de contacto directo para el mapa y el directorio"],
    "direccion_fisica": ["Dirección física exacta"],
    "telefonos": ["Teléfono(s)"],
    "correo_electronico": ["Correo electrónico"],
    "sitio_web": ["Sitio web"],
    "redes_sociales": ["Redes sociales"],
    "persona_contacto_cargo": ["Persona de contacto y cargo"],
    "territorios_servicio": ["1.3* Municipios o territorios donde presta servicios a NAE"],
    "cobertura_principal": ["1.4* Cobertura principal de actuación"],
    "modalidad_atencion": ["1.5* Modalidad principal de atención a NAE"],
    "tipo_estructura_apoyo": ["1.6* Tipo de entidad o estructura de apoyo"],
    "presta_servicios_actualmente": ["1.7* ¿La entidad presta actualmente servicios de apoyo a NAE?"],
    "nivel_involucramiento_apoyo": ["1.8* Nivel de involucramiento en la prestación de servicios de apoyo a NAE"],
    "cantidad_nae_atendidos": ["1.9 Cantidad aproximada de NAE atendidos en los últimos 12 meses"],
    "antiguedad_servicios": ["1.10 Desde cuándo presta servicios de apoyo a NAE"],
    "capacidad_ampliar_cobertura": ["1.11 ¿Tiene capacidad para atender NAE de otros municipios o ampliar cobertura?"],
    "frecuencia_servicios": ["2.3 Frecuencia habitual de los servicios"],
    "modalidad_pago_servicios": ["2.4 ¿Los servicios son gratuitos, de pago o mixtos?"],
    "metodologia_apoyo": ["2.5 ¿La entidad utiliza metodología, herramientas o protocolos propios para apoyar a los NAE?"],
    "seguimiento_posterior": ["2.6 ¿Realiza seguimiento posterior a la atención o servicio prestado?"],
    "servicios_mas_demandados": ["2.7 Servicios más demandados por los NAE"],
    "servicios_mejor_funcionan": ["2.8 Servicios que funcionan mejor actualmente y por qué"],
    "servicios_insuficientes": ["2.9 Servicios que no existen o son insuficientes en el municipio"],
    "dispone_espacios_fisicos": ["3.1* ¿La entidad dispone de espacios físicos para realizar actividades de apoyo a NAE?"],
    "disponibilidad_tecnologica": ["3.3* Disponibilidad de computadoras o recursos tecnológicos para acceso público o actividades con NAE"],
    "condiciones_conectividad": ["3.4* Condiciones de conectividad"],
    "autonomia_energetica": ["3.5* Autonomía energética para sostener actividades presenciales u online"],
    "mejoras_infraestructura": ["3.6 Principales mejoras necesarias en infraestructura, conectividad o energía"],
    "principal_brecha_ecosistema": ["5.2* Principal brecha del ecosistema de apoyo a NAE en el municipio"],
    "actores_liderar_brecha": ["5.3 ¿Qué actores o estructuras podrían liderar la respuesta a esa brecha?"],
    "adecuacion_servicios": ["5.4 Adecuación de los servicios existentes al contexto local de los NAE"],
    "comentarios_servicios": ["5.5 Comentarios sobre calidad, pertinencia o limitaciones de los servicios actuales"],
    "mecanismos_coordinacion_apoyo": [
        "6.1* ¿Existen mecanismos de coordinación institucional orientados al apoyo a NAE y estructuras de apoyo?"
    ],
    "coordinador_articulacion": ["6.3 ¿Quién coordina actualmente esa articulación y cómo funciona?"],
    "actividades_conjuntas": ["6.4 Actividades conjuntas realizadas o previstas para apoyar a NAE"],
    "nivel_articulacion": ["6.5 Nivel de articulación institucional alrededor de los servicios de apoyo a NAE"],
    "capacidad_sostener_servicios": ["7.2* Capacidad de sostener los servicios en el tiempo"],
    "capacidad_actualizar_mapeo": ["7.3* Capacidad de mantener actualizada la información para el mapa/directorio"],
    "apoyos_sostenibilidad": ["7.4 Apoyos necesarios para mejorar la sostenibilidad de la estructura de apoyo"],
    "programas_especializados": [
        "8.1 ¿Existen programas, centros, proyectos o servicios específicos para mujeres, jóvenes u otros grupos de NAE?"
    ],
    "descripcion_programas_especializados": [
        "8.2 Si respondió “Sí”, describa cuáles son y quién los gestiona"
    ],
    "observaciones_finales": ["8.4 Observaciones finales o información adicional relevante para el diagnóstico nacional"],
}

LIST_FIELDS = {
    "tipos_nae": "2.2* Tipo de NAE a los que presta o puede prestar apoyo",
    "capacidades_tecnicas": "4.1* Capacidades técnicas con las que cuenta el equipo de la entidad para apoyar a los NAE",
    "necesidades_fortalecimiento": "4.3 Necesidades prioritarias de fortalecimiento del equipo",
}

SERVICIOS_GRID_TITLES = (
    "2.1 Servicios que ofrece la entidad y servicios que necesita fortalecer",
    "2.1* Servicios que ofrece la entidad y servicios que necesita fortalecer",
)


def scalar_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return " | ".join(items) if items else None
    text_value = str(value).strip()
    return text_value or None


def coerce_list(value: Any) -> List[str]:
    text = scalar_value(value)
    if not text:
        return []

    separators = [" | ", "\n", ";", ", "]
    values = [text]
    for separator in separators:
        next_values: List[str] = []
        for item in values:
            next_values.extend(item.split(separator))
        values = next_values
    return [item.strip() for item in values if item.strip()]


def scalar_from_payload(payload: Dict[str, Any], aliases: List[str]) -> Optional[str]:
    for alias in aliases:
        if alias in payload:
            return scalar_value(payload.get(alias))
    return None


def extract_scalar_fields(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {
        field_name: scalar_from_payload(payload, aliases)
        for field_name, aliases in SCALAR_FIELDS.items()
    }


def extract_named_lists(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    return {
        field_name: coerce_list(payload.get(question))
        for field_name, question in LIST_FIELDS.items()
    }


def extract_espacios(payload: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
    rows: List[Dict[str, Optional[str]]] = []
    for index in range(1, 6):
        row = {
            "orden": index,
            "espacio": scalar_value(payload.get(f"3.2.{index}.1 Espacio")),
            "direccion_lugar": scalar_value(payload.get(f"3.2.{index}.2 Dirección / lugar")),
            "aforo_aprox": scalar_value(payload.get(f"3.2.{index}.3 Aforo aprox.")),
            "conectividad_tipo": scalar_value(payload.get(f"3.2.{index}.4 Conectividad / tipo")),
            "energia_alternativa": scalar_value(payload.get(f"3.2.{index}.5 Energía alternativa")),
            "aire_acondicionado": scalar_value(payload.get(f"3.2.{index}.6 Aire acondicionado")),
            "uso_posible": scalar_value(payload.get(f"3.2.{index}.7 Uso posible")),
        }
        if any(value for key, value in row.items() if key != "orden"):
            rows.append(row)
    return rows


def extract_perfiles(payload: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
    rows: List[Dict[str, Optional[str]]] = []
    for index in range(1, 6):
        perfil = scalar_value(payload.get(f"4.2 Perfil {index}"))
        if perfil:
            rows.append({"orden": index, "perfil": perfil})
    return rows


def extract_recomendaciones(payload: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
    rows: List[Dict[str, Optional[str]]] = []
    for index in range(1, 7):
        row = {
            "orden": index,
            "nombre_estructura": scalar_value(payload.get(f"8.3.{index}.1 Nombre de la estructura")),
            "tipo_actor": scalar_value(payload.get(f"8.3.{index}.2 Tipo de actor")),
            "servicios": scalar_value(payload.get(f"8.3.{index}.3 Servicios que ofrece")),
            "municipio_territorio": scalar_value(payload.get(f"8.3.{index}.4 Municipio / territorio")),
            "contacto": scalar_value(payload.get(f"8.3.{index}.5 Contacto disponible")),
        }
        if any(value for key, value in row.items() if key != "orden"):
            rows.append(row)
    return rows


def extract_servicios(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    servicios: Dict[str, Dict[str, Any]] = {}
    for key, value in payload.items():
        if not any(key.startswith(title) for title in SERVICIOS_GRID_TITLES):
            continue

        servicio = key
        if "[" in key and "]" in key:
            servicio = key[key.find("[") + 1:key.rfind("]")]
        elif " - " in key:
            servicio = key.split(" - ", 1)[1]
        elif ":" in key:
            servicio = key.split(":", 1)[1]

        selected = coerce_list(value)
        servicios[servicio.strip()] = {
            "servicio": servicio.strip(),
            "ofrece_actualmente": "Ofrece actualmente" in selected,
            "requiere_fortalecer": "Requiere fortalecer" in selected,
        }

    otro_servicio = scalar_value(payload.get("2.1 Otro servicio: nombre"))
    if otro_servicio:
        selected = coerce_list(payload.get("2.1 Otro servicio: situación"))
        servicios[otro_servicio] = {
            "servicio": otro_servicio,
            "ofrece_actualmente": "Ofrece actualmente" in selected,
            "requiere_fortalecer": "Requiere fortalecer" in selected,
        }

    return list(servicios.values())
