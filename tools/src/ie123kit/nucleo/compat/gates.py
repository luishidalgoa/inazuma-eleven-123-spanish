"""Gates de la migración que ejecuta ``ie123 compat comprobar [--golden]``.

Sin ``--golden`` (rápido, no necesita ROM):

- ``bloqueados``: los cinco ficheros congelados v20 siguen byte a byte (``guardia.comprobar_bloqueados``);
- ``congelados``: grupo golden ``congelados.sha256``;
- ``importaciones``: ningún import nuevo sin resolver en las capas de ``work/`` respecto a la línea
  base (``tests/compat/baseline_importaciones.json``). Sin ``work/`` se omite.

Con ``--golden`` (necesita ``work/``), además:

- ``capa_referencia``: la capa ``graficos/titulo_logo`` se regenera byte a byte;
- ``candidatas``: hashes de ``base_3ds`` y de la candidata vigente;
- ``referencia``: base + capa con ``build_ui_revision.py`` da ``ARCHIVE_REFERENCIA`` y la CRO de la base;
- ``bloqueo_candidata``: bloqueo tipográfico de la candidata vigente. Desde el 2026-09-19 (#80) los
  ``FONT_HASHES`` son los de ``probe_ie2_v34`` y el gate debe pasar. ``BLOQUEO_PENDIENTE`` solo existe
  para marcar un fallo como conocido si en el futuro hubiera otra decisión pendiente; hoy es False.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

__all__ = ["BLOQUEO_PENDIENTE", "comprobar"]

#: #80 resuelto (2026-09-19): el bloqueo aprueba las fuentes de probe_ie2_v34; un fallo ya es real.
BLOQUEO_PENDIENTE = False


def _gate(nombre: str, ok: bool, detalle: str = "", conocido: bool = False) -> dict:
    return {"gate": nombre, "ok": bool(ok), "detalle": detalle, "conocido": conocido}


def _silencioso(funcion, *args):
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        valor = funcion(*args)
    return valor, salida.getvalue().strip()


def comprobar(raiz: Path, golden: bool = False) -> list[dict]:
    """Lista de ``{gate, ok, detalle, conocido}``; nunca lanza (un error es un gate fallido)."""
    from ie123kit.nucleo.compat import golden as G
    from ie123kit.nucleo.compat import guardia

    raiz = Path(raiz)
    gates = []

    def intentar(nombre: str, funcion) -> None:
        try:
            gates.append(funcion())
        except Exception as exc:  # noqa: BLE001 - un gate que revienta es un gate fallido
            gates.append(_gate(nombre, False, f"{type(exc).__name__}: {exc}"))

    def bloqueados():
        codigo, texto = _silencioso(guardia.comprobar_bloqueados, raiz)
        return _gate("bloqueados", codigo == 0, texto[-400:])

    def congelados():
        total, malos = G.comprobar_grupo("congelados.sha256", raiz)
        return _gate("congelados", not malos, f"{total - len(malos)}/{total} OK " + "; ".join(malos))

    def importaciones():
        from ie123kit.nucleo.compat import importaciones as I

        work = raiz / "work"
        if not work.is_dir():
            return _gate("importaciones", True, "sin work/: omitido")
        base = raiz / "tools/tests/compat/baseline_importaciones.json"
        previos = set(json.loads(base.read_text(encoding="utf-8"))) if base.is_file() else set()
        total, fallos = I.analizar(work)
        nuevos = [f for f in fallos if f not in previos]
        return _gate("importaciones", not nuevos, f"{total} scripts; {len(nuevos)} nuevos " + "; ".join(nuevos[:5]))

    intentar("bloqueados", bloqueados)
    intentar("congelados", congelados)
    intentar("importaciones", importaciones)
    if not golden:
        return gates

    def capa_referencia():
        total, malos = G.regenerar_capa(raiz)
        return _gate("capa_referencia", not malos, f"{total - len(malos)}/{total} OK " + "; ".join(malos))

    def candidatas():
        total, malos = G.comprobar_grupo("candidatas.sha256", raiz)
        return _gate("candidatas", not malos, f"{total - len(malos)}/{total} OK " + "; ".join(malos))

    def referencia():
        fallos, texto = _silencioso(G.comprobar_referencia, raiz)
        return _gate("referencia", fallos == 0, texto)

    def bloqueo_candidata():
        from ie123kit.nucleo.errores import BloqueoTipograficoError
        from ie123kit.nucleo.validar import bloqueo

        candidata = raiz / "work/shared/candidatas" / G.CANDIDATA_VIGENTE
        try:
            bloqueo.comprobar(candidata, raiz)
        except BloqueoTipograficoError as exc:
            return _gate("bloqueo_candidata", False, f"{G.CANDIDATA_VIGENTE}: {exc}", conocido=BLOQUEO_PENDIENTE)
        return _gate("bloqueo_candidata", True, G.CANDIDATA_VIGENTE)

    for nombre, funcion in (("capa_referencia", capa_referencia), ("candidatas", candidatas),
                            ("referencia", referencia), ("bloqueo_candidata", bloqueo_candidata)):
        intentar(nombre, funcion)
    return gates
