"""Esquemas JSON del contrato del toolkit (draft 2020-12).

`validar()` usa `jsonschema` si está instalado y, si no, un validador mínimo
propio: `servicio` no puede adquirir dependencias de ejecución nuevas.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

__all__ = ["DATOS", "NOMBRES", "TODOS", "cargar", "ejemplos", "validar"]

NOMBRES: tuple[str, ...] = (
    "incidencia",
    "progreso",
    "assetref",
    "resultado",
    "info_objetivo",
    "manifiesto_candidata",
    "registro_activos",
    "evento_trabajo",
)

#: Esquemas de ``Resultado.datos`` de cada método del ciclo de la GUI (F2.5, API 1.0). Admiten
#: propiedades adicionales: una versión menor de la API puede añadir campos, nunca quitarlos.
DATOS: tuple[str, ...] = (
    "datos_objetivos",
    "datos_activos",
    "datos_exportar",
    "datos_importar",
    "datos_construir",
    "datos_verificar",
    "datos_instalar",
)

TODOS: tuple[str, ...] = NOMBRES + DATOS


def cargar(nombre: str) -> dict[str, Any]:
    """Devuelve el esquema `<nombre>.schema.json` de este paquete."""
    if nombre not in TODOS:
        raise ValueError(f"esquema desconocido: {nombre!r}; disponibles: {list(TODOS)}")
    recurso = files(__name__).joinpath(f"{nombre}.schema.json")
    return json.loads(recurso.read_text(encoding="utf-8"))


def ejemplos(nombre: str) -> list[Any]:
    """Ejemplos publicados en el esquema (palabra clave ``examples``)."""
    return list(cargar(nombre).get("examples", []))


def validar(instancia: Any, nombre: str) -> list[str]:
    """Valida `instancia` contra el esquema `nombre`; devuelve la lista de errores."""
    esquema = cargar(nombre)
    try:
        # Dependencia opcional: solo se usa si el entorno la tiene instalada.
        import jsonschema
    except ImportError:
        return _validar_minimo(instancia, esquema, esquema, "$")
    validador = jsonschema.Draft202012Validator(esquema)
    return [f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in validador.iter_errors(instancia)]


# --------------------------------------------------------------------- validador mínimo de respaldo

_TIPOS: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
    "null": type(None),
}


def _tipo_ok(valor: Any, tipo: str) -> bool:
    esperado = _TIPOS.get(tipo)
    if esperado is None:
        return True
    if tipo in ("number", "integer") and isinstance(valor, bool):
        return False
    if tipo == "boolean":
        return isinstance(valor, bool)
    return isinstance(valor, esperado)


def _resolver(esquema: dict[str, Any], raiz: dict[str, Any]) -> dict[str, Any]:
    """Resuelve un `$ref` local del estilo `#/$defs/x` (una sola indirección por nivel)."""
    visto = 0
    while isinstance(esquema, dict) and "$ref" in esquema and visto < 16:
        ref = esquema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            break
        destino: Any = raiz
        for parte in ref[2:].split("/"):
            if not isinstance(destino, dict) or parte not in destino:
                return {}
            destino = destino[parte]
        esquema = destino if isinstance(destino, dict) else {}
        visto += 1
    return esquema


def _validar_minimo(instancia: Any, esquema: dict[str, Any], raiz: dict[str, Any], ruta: str) -> list[str]:
    """Validador de respaldo: type, required, enum, properties, items y additionalProperties."""
    esquema = _resolver(esquema, raiz)
    errores: list[str] = []
    if not esquema:
        return errores

    tipo = esquema.get("type")
    tipos = [tipo] if isinstance(tipo, str) else list(tipo or [])
    if tipos and not any(_tipo_ok(instancia, t) for t in tipos):
        errores.append(f"{ruta}: se esperaba tipo {'/'.join(tipos)}, llegó {type(instancia).__name__}")
        return errores

    if "enum" in esquema and instancia not in esquema["enum"]:
        errores.append(f"{ruta}: {instancia!r} no está en {esquema['enum']}")

    if isinstance(instancia, dict):
        propiedades = esquema.get("properties", {})
        for clave in esquema.get("required", []):
            if clave not in instancia:
                errores.append(f"{ruta}: falta la propiedad obligatoria {clave!r}")
        if esquema.get("additionalProperties") is False:
            for clave in instancia:
                if clave not in propiedades:
                    errores.append(f"{ruta}: propiedad no permitida {clave!r}")
        for clave, subesquema in propiedades.items():
            if clave in instancia and isinstance(subesquema, dict):
                errores += _validar_minimo(instancia[clave], subesquema, raiz, f"{ruta}.{clave}")
        adicionales = esquema.get("additionalProperties")
        if isinstance(adicionales, dict):
            for clave, valor in instancia.items():
                if clave not in propiedades:
                    errores += _validar_minimo(valor, adicionales, raiz, f"{ruta}.{clave}")

    if isinstance(instancia, list):
        items = esquema.get("items")
        if isinstance(items, dict):
            for i, valor in enumerate(instancia):
                errores += _validar_minimo(valor, items, raiz, f"{ruta}[{i}]")

    return errores
