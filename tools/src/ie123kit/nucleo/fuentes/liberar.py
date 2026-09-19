"""Informe de códigos de bigrama recuperables (SOLO INFORME: no cambia ninguna fuente ni ningún texto).

El registro de bigramas (``registro.json`` de la última capa de fuentes) casi no tiene códigos libres
(queda ~1) y la traducción de IE3 necesitará más. Esta herramienta lista candidatos para liberar, con
dos criterios independientes:

1. **Sin uso en la candidata**: el código no aparece en ningún texto escaneado de la candidata
   (``*/script/*.pkh``+``.pkb`` descomprimidos, todos los ``*.STR``, los ``*.dat`` de ``logic/`` y de
   ``movie/txt/`` y las CRO). Suele ser
   un código que solo usaba una capa ya sustituida. La cuenta es de pares de bytes en crudo, sin
   alinear: un falso «en uso» es posible, un falso «sin uso» en lo escaneado no. Lo que no se escanea
   (otros formatos, literales de ``code.bin``) hay que revisarlo antes de liberar nada.
2. **Celda duplicada**: dos o más códigos cuyo dibujo (píxeles y CWDH) es idéntico en TODAS las fuentes
   en que está dibujado alguno de ellos. Basta uno: los demás se liberan recodificando sus textos.

Liberar un código de verdad (redibujarlo, recodificar textos y regenerar fuentes) toca la tipografía:
necesita una petición explícita del usuario (AGENTS.md, bloqueo tipográfico) y una capa nueva.

Uso::

    python -m ie123kit.nucleo.fuentes.liberar \\
        --candidata work/shared/candidatas/probe_ie2_v34 \\
        --registro work/ie2/shared/capas/menus_cro/menus/registro.json [--json informe.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

__all__ = ["FUENTES", "duplicados", "fuentes_de_texto", "informe", "main", "resumen", "usos"]

FUENTES = ("font/FONT12.bcfnt", "font/FONT8.bcfnt", "font/FONT12T.bcfnt")


def usos(codigos: Iterable[str], textos: Mapping[str, bytes]) -> dict[str, dict[str, int]]:
    """``{código: {fuente: n}}``: apariciones en crudo (sin alinear) de cada código en cada texto."""
    import numpy as np

    lista = sorted({c.upper() for c in codigos})
    cand = np.array([int(c, 16) for c in lista], dtype=np.uint16)
    res: dict[str, dict[str, int]] = {c: {} for c in lista}
    for nombre, buf in textos.items():
        if len(buf) < 2:
            continue
        a = np.frombuffer(buf, dtype=np.uint8).astype(np.uint16)
        w = (a[:-1] << 8) | a[1:]
        valores, cuentas = np.unique(w[np.isin(w, cand)], return_counts=True)
        for v, n in zip(valores.tolist(), cuentas.tolist()):
            res[f"{v:04X}"][nombre] = int(n)
    return res


def _huella(fuente: Any, gi: int) -> str:
    px = sorted((x, y, v) for y, row in enumerate(fuente.bitmap(gi)) for x, v in enumerate(row) if v)
    return hashlib.sha1(json.dumps([list(fuente.metrics[gi]), px]).encode()).hexdigest()


def duplicados(registro: Iterable[Mapping[str, Any]], fuentes: Mapping[str, Any]) -> list[list[str]]:
    """Grupos de códigos con el mismo dibujo en todas las fuentes en que alguno está dibujado."""
    grupos: dict[tuple, list[str]] = defaultdict(list)
    for e in registro:
        dibujadas = tuple(sorted(f for f in e.get("fuentes", {}) if f in fuentes))
        if not dibujadas:
            continue
        cp = ord(bytes.fromhex(e["sjis"]).decode("cp932"))
        clave = []
        for f in dibujadas:
            gi = fuentes[f].gi(cp)
            if gi is None:
                break
            clave.append((f, _huella(fuentes[f], gi)))
        else:
            grupos[tuple(clave)].append(e["sjis"].upper())
    return sorted(sorted(g) for g in grupos.values() if len(g) > 1)


def fuentes_de_texto(candidata: Path, base_cro: Path | None = None) -> dict[str, bytes]:
    """Textos de una candidata: eventos descomprimidos, ``*.STR``, ``*.dat`` de logic/ y txt/ y las CRO."""
    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.nucleo.eventos import packnum

    arc = FaArchive(str(candidata / "archive.fa"))
    idx = {p: (o, s) for p, o, s in arc.entries}
    textos: dict[str, bytes] = {}
    for ruta, (o, s) in sorted(idx.items()):
        if ruta.endswith(".STR") or (ruta.endswith(".dat") and ("/logic/" in ruta or "/txt/" in ruta)):
            textos[ruta] = arc.file_bytes(o, s)
        elif "/script/" in ruta and ruta.endswith(".pkh"):
            pkb = ruta[:-4] + ".pkb"
            if pkb not in idx:
                continue
            pkh_datos = arc.file_bytes(*idx[ruta])
            pkb_datos = arc.file_bytes(*idx[pkb])
            try:
                indice = packnum.parse_index(pkh_datos)
            except AssertionError:
                continue
            textos[pkb] = b"".join(packnum.entry_data(pkb_datos, off, size) + b"\0\0" for _, off, size in indice)
    cros = {p.name: p for p in sorted((base_cro or Path()).glob("*.cro"))} if base_cro else {}
    cros.update({p.name: p for p in sorted((candidata / "romfs/cro").glob("*.cro"))})
    for nombre, p in cros.items():
        textos[f"cro/{nombre}"] = p.read_bytes()
    return textos


def informe(registro_doc: Mapping[str, Any], textos: Mapping[str, bytes],
            fuentes: Mapping[str, Any]) -> dict[str, Any]:
    """Informe de códigos recuperables (no cambia nada)."""
    reg = list(registro_doc.get("bigramas", ()))
    por_codigo = {e["sjis"].upper(): e for e in reg}
    cuenta = usos(por_codigo, textos)
    sin_uso = sorted(c for c, v in cuenta.items() if not v)
    dups = duplicados(reg, fuentes)
    libres = sorted({c for k, v in registro_doc.items() if k.startswith("libres") and isinstance(v, list)
                     for c in v})

    def fila(c: str) -> dict[str, Any]:
        e = por_codigo[c]
        return {"sjis": c, "par": e.get("par"), "clave": e.get("clave", e.get("par")),
                "campos": e.get("campos", []), "origen": e.get("origen"), "fuentes": sorted(e.get("fuentes", {}))}

    liberables_dup = sorted(c for g in dups for c in g[1:])
    return {
        "solo_informe": True,
        "registro_version": registro_doc.get("version"),
        "codigos_en_registro": len(reg),
        "libres_anotados": libres,
        "textos_escaneados": {k: len(v) for k, v in sorted(textos.items())},
        "sin_uso": [fila(c) for c in sin_uso],
        "duplicados": [[fila(c) for c in g] for g in dups],
        "recuperables": sorted(set(sin_uso) | set(liberables_dup)),
        "nota": ("Candidatos, no decisiones: liberar un código cambia fuentes y textos (bloqueo "
                 "tipográfico, AGENTS.md) y exige revisar lo no escaneado (literales de code.bin)."),
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    ap = argparse.ArgumentParser(prog="python -m ie123kit.nucleo.fuentes.liberar",
                                 description="Informe de códigos de bigrama recuperables (no cambia nada).")
    ap.add_argument("--candidata", type=Path, required=True, help="carpeta de la candidata (archive.fa + romfs/cro)")
    ap.add_argument("--registro", type=Path, required=True, help="registro.json vigente")
    ap.add_argument("--base-cro", type=Path, default=None,
                    help="CRO de la base para las que la candidata no trae (p. ej. work/shared/base_3ds/romfs/cro)")
    ap.add_argument("--json", type=Path, default=None, help="escribe el informe completo en este fichero")
    args = ap.parse_args(argv)

    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.nucleo.fuentes import celdas

    doc = json.loads(args.registro.read_text(encoding="utf-8"))
    arc = FaArchive(str(args.candidata / "archive.fa"))
    fuentes = {f: celdas.FuenteBCFNT.desde_bytes(arc.read(f), Path(f).name) for f in FUENTES}
    res = informe(doc, fuentes_de_texto(args.candidata, args.base_cro), fuentes)
    if args.json is not None:
        args.json.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def resumen(res: Mapping[str, Any], limite: int = 40) -> list[str]:
    """Líneas de texto con lo esencial del informe."""
    lineas = [
        (f"registro {res['registro_version']}: {res['codigos_en_registro']} códigos; "
         f"libres anotados {res['libres_anotados']}"),
        (f"sin uso en la candidata: {len(res['sin_uso'])}; grupos duplicados: {len(res['duplicados'])}; "
         f"recuperables en total: {len(res['recuperables'])}"),
    ]
    lineas += [f"  sin uso  {f['sjis']}  {f['clave']!r}  campos={f['campos']}" for f in res["sin_uso"][:limite]]
    lineas += ["  duplicado " + ", ".join(f"{f['sjis']} {f['clave']!r}" for f in g)
               for g in res["duplicados"][:limite]]
    return lineas


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(resumen(main())))
