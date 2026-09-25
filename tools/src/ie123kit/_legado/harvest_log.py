#!/usr/bin/env python3
"""Cosechador de errores de runtime de Azahar.

IDEA (peticion del usuario): CADA vez que se arranca el juego, recoger
automaticamente el log de errores de Azahar y acumularlo en NUESTRO PROPIO
registro persistente, para detectar cosas que mejorar en la siguiente version
SIN depender de que alguien este mirando el log en vivo (mas eficiente que
"escuchar" en directo: se acumula solo, partida tras partida).

Que hace:
  1. Lee el log de Azahar (por defecto el actual + el .old).
  2. Extrae las lineas <Error>/<Critical>. Las de memoria
     ('unmapped ReadN @ 0xADDR at PC 0xPC') se agrupan por (op, tamano, PC):
     el PC es la posicion de codigo -> firma ESTABLE del mismo bug; la direccion
     leida varia y se descarta. El resto se normaliza (se quitan numeros/hex) por
     subsistema+mensaje.
  3. Funde el resultado en logs/runtime_errors.json (registro persistente): cada
     firma guarda primera/ultima vez, veces totales, nº de sesiones, estado y una
     nota nuestra. Anota PCs ya diagnosticados desde KNOWN_PCS.
  4. Imprime (y escribe logs/INFORME_ERRORES.md) un informe: firmas NUEVAS de esta
     sesion (candidatas a mejorar), las mas frecuentes y el total abierto.

Para no contar dos veces el mismo log, se guarda una "huella" (tamano+mtime) de
cada fichero ya procesado; jugar.ps1 ademas vacia el log antes de cada partida,
asi que cada cosecha = una partida limpia.

Uso:
  python tools/harvest_log.py                 # log actual + .old, registra
  python tools/harvest_log.py --session NAME  # solo el actual (lo usa jugar.ps1)
  python tools/harvest_log.py --report        # solo reimprime el informe
  python tools/harvest_log.py --force         # ignora la huella (re-procesa)
"""
import os, re, sys, json, argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

from ie123kit.nucleo.construir.registro_azahar import *  # noqa: F401,F403
from ie123kit.nucleo.construir.registro_azahar import _classify, _line, _now, _relevancia, _stamp  # noqa: F401


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", metavar="NAME", nargs="?", const="?",
                    help="solo el log actual (no el .old); marca la build")
    ap.add_argument("--report", action="store_true", help="solo reimprime el informe")
    ap.add_argument("--force", action="store_true", help="ignora la huella (re-procesa)")
    ap.add_argument("--warnings", action="store_true", help="incluye <Warning>")
    ap.add_argument("--logdir", default=LOGDIR)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(REG), exist_ok=True)
    reg = json.load(open(REG, encoding="utf-8")) if os.path.exists(REG) else {}

    if args.report:
        print(informe(reg))
        return

    levels = LEVELS + ("Warning",) if args.warnings else LEVELS
    logs = [os.path.join(args.logdir, "azahar_log.txt")]
    if not args.session:
        logs.append(os.path.join(args.logdir, "azahar_log.old.txt"))

    procesado = reg.setdefault("_procesado", {})
    found, algo = {}, False
    for lp in logs:
        st = _stamp(lp)
        if st is None:
            continue
        if not args.force and procesado.get(lp) == st:
            print(f"(sin cambios desde la ultima cosecha: {os.path.basename(lp)})")
            continue
        algo = True
        procesado[lp] = st
        for sig, e in parse(lp, levels).items():
            if sig in found:
                found[sig]["veces"] += e["veces"]
            else:
                found[sig] = dict(e)

    if not algo:
        print("\nNada nuevo que cosechar.\n")
        print(informe(reg))
        return

    nuevas = merge(reg, found, args.session if args.session != "?" else None)
    json.dump(reg, open(REG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    txt = informe(reg, nuevas)
    open(INFORME, "w", encoding="utf-8").write(txt)
    print(txt)
    print(f"\nSesion: {len(found)} firmas ({len(nuevas)} nuevas). Registro: {REG}")


if __name__ == "__main__":
    main()
