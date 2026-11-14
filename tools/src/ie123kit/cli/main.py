"""Orden `ie123`: adaptador argparse 1:1 sobre `ServicioToolkit`. Sin lógica propia.

F2.2 adelanta solo los verbos que el gate de la subfase ejecuta literalmente:
`construir`, `parche` y `doctor`. F2.4 amplía la CLI al resto de verbos de
docs/toolkit/ESPECIFICACION.md (proyecto, objetivos, extraer, verificar, instalar,
work limpiar, compat, acciones por objetivo) y añade los alias en inglés con su
tabla de equivalencias. No añadir aquí ninguna regla de negocio: si algo falta,
va en `nucleo` y se expone por `servicio`.

Códigos de salida (docs/toolkit/ESPECIFICACION.md, spec.cli):
0 ok · 1 incidencias de validación · 2 uso incorrecto · 3 bloqueo tipográfico
4 falta una herramienta externa · 5 operación no soportada.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ie123kit.servicio.api import ServicioToolkit, SolicitudConstruccion

__all__ = ["CODIGOS_SALIDA", "abrir_servicio", "construir_parser", "main"]

OK = 0
VALIDACION = 1
USO = 2
BLOQUEO = 3
HERRAMIENTA = 4
NO_SOPORTADO = 5

#: Código de incidencia → código de salida del proceso.
CODIGOS_SALIDA: dict[str, int] = {
    "BLOQUEO_V20": BLOQUEO,
    "HERRAMIENTA_AUSENTE": HERRAMIENTA,
    "NOT_SUPPORTED": NO_SOPORTADO,
}


def abrir_servicio(raiz: str | None = None) -> ServicioToolkit:
    """Fábrica de la fachada; los tests la sustituyen para no tocar disco."""
    return ServicioToolkit.abrir(raiz)


def construir_parser() -> argparse.ArgumentParser:
    """Parser de la CLI mínima de F2.2."""
    p = argparse.ArgumentParser(prog="ie123", description="Herramientas de la traducción de Inazuma Eleven 1·2·3.")
    p.add_argument("--proyecto", metavar="RUTA", default=None, help="Raíz del repositorio (por defecto se busca).")
    p.add_argument("--json", action="store_true", dest="json_", help="Imprime el Resultado serializado.")
    sub = p.add_subparsers(dest="orden", required=True)

    c = sub.add_parser("construir", help="Construye una candidata de toda la recopilación.")
    c.add_argument("--base", required=True, help="Candidata base (nombre o ruta).")
    c.add_argument("--objetivos", default="", help="Lista separada por comas (por defecto, ninguno).")
    c.add_argument("--capas", action="append", default=[], metavar="RUTA", help="Capa a aplicar (repetible).")
    c.add_argument("--salida", required=True, help="Candidata de salida (nombre o ruta).")
    c.add_argument("--sin-sincronia-usearch", action="store_true", dest="sin_sincronia_usearch",
                   help="NO sincroniza usearch.dat con unitbase.dat al construir (hook de nombres, activo por "
                        "defecto). Solo para reproducir un hash anterior al hook (p. ej. probe_ie1_v67); la candidata "
                        "resultante no pasa verificar/instalar si usearch queda desincronizado.")

    x = sub.add_parser("parche", help="Genera el .xdelta entre la ROM base y la parcheada.")
    x.add_argument("--rom-base", required=True, dest="rom_base")
    x.add_argument("--rom-parcheada", required=True, dest="rom_parcheada")
    x.add_argument("--salida", required=True)

    sub.add_parser("doctor", help="Comprueba el entorno local.")
    return p


def _codigo(resultado: Any) -> int:
    if getattr(resultado, "ok", False):
        return OK
    codigos = [getattr(i, "codigo", "") for i in getattr(resultado, "incidencias", ())]
    for codigo in ("BLOQUEO_V20", "HERRAMIENTA_AUSENTE", "NOT_SUPPORTED"):
        if codigo in codigos:
            return CODIGOS_SALIDA[codigo]
    return VALIDACION


def _imprimir(resultado: Any, como_json: bool) -> None:
    salida = sys.stdout
    reconfigurar = getattr(salida, "reconfigure", None)
    if reconfigurar is not None:
        try:
            reconfigurar(encoding="utf-8")
        except (OSError, ValueError):
            pass
    if como_json:
        print(json.dumps(resultado.to_json(), ensure_ascii=False, indent=2))
        return
    print("ok" if getattr(resultado, "ok", False) else "FALLO")
    for clave, valor in (getattr(resultado, "datos", {}) or {}).items():
        if clave != "informe":
            print(f"  {clave}: {valor}")
    for incidencia in getattr(resultado, "incidencias", ()):
        print(f"  [{incidencia.severidad}] {incidencia.codigo}: {incidencia.mensaje}")
    for artefacto in getattr(resultado, "artefactos", ()):
        print(f"  -> {artefacto}")


def _ejecutar(args: argparse.Namespace) -> Any:
    servicio = abrir_servicio(args.proyecto)
    if args.orden == "construir":
        objetivos = tuple(o.strip() for o in args.objetivos.split(",") if o.strip())
        solicitud = SolicitudConstruccion(
            base=args.base, objetivos=objetivos, capas=tuple(args.capas), salida=args.salida
        )
        if args.sin_sincronia_usearch:
            return servicio.construir(solicitud, omitir_sincronia_usearch=True)
        return servicio.construir(solicitud)
    if args.orden == "parche":
        return servicio.parche(args.rom_base, args.rom_parcheada, args.salida)
    return servicio.doctor()


def main(argv: list[str] | None = None) -> int:
    """Analiza `argv`, llama a la fachada e imprime su Resultado."""
    parser = construir_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse ya ha impreso el error
        codigo = exc.code
        if codigo in (0, None):
            return OK
        return USO
    resultado = _ejecutar(args)
    _imprimir(resultado, args.json_)
    return _codigo(resultado)
