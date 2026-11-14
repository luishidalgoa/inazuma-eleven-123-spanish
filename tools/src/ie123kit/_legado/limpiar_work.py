"""Limpieza de work/ según docs/ARQUITECTURA.md.

Borra lo que se puede regenerar o está superado: candidatas probe_ie1_vN que no sean las dos últimas,
imágenes de ROM reconstruidas de releases publicadas, volcados de texturas de auditorías antiguas,
descargas duplicadas de herramientas, cachés y temporales (.partial, .yuv, __pycache__, *_x2.png).
Nunca toca: shared/base_3ds, ieN/fuentes, Roms, capas vN con scripts, docs ni tools.
Uso: python tools/limpiar_work.py            (solo lista)
     python tools/limpiar_work.py --borrar   (borra)
     python tools/limpiar_work.py --auto     (hook: borra solo cachés, temporales viejos y copias previas
                                              superadas; silencioso, deja una línea en logs/limpieza.log)
     python tools/limpiar_work.py --informe  (señala ficheros pesados fuera de las carpetas de originales)
"""
import shutil
import sys
import time

from ie123kit.nucleo.construir.limpieza import *  # noqa: F401,F403


def auto():
    """Limpieza del hook: nunca falla ni imprime (un hook roto no debe entorpecer la sesión)."""
    try:
        borrados = liberado = 0
        for p, _motivo in objetivos_auto():
            s = tam(p)
            try:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            except OSError:
                continue
            borrados += 1
            liberado += s
        if borrados:
            log = ROOT / 'logs' / 'limpieza.log'
            log.parent.mkdir(exist_ok=True)
            with log.open('a', encoding='utf-8') as f:
                f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} borrados={borrados} liberado_mb={liberado / 2**20:.1f}\n')
    except Exception:  # noqa: BLE001
        pass
    return 0


def informe():
    pesados = informe_espacio()
    for p, s in pesados:
        print(f'{s / 2**30:6.2f} GB  {p.relative_to(ROOT)}')
    print(f'{len(pesados)} ficheros pesados fuera de originales y copias previas (revisar a mano; no se borran)')
    for p, motivo in objetivos_auto(edad_minima=0):
        print(f'auto: {tam(p) / 2**20:9.1f} MB  {p.relative_to(ROOT)}  [{motivo}]')


def main():
    if '--auto' in sys.argv:
        raise SystemExit(auto())
    if '--informe' in sys.argv:
        return informe()
    borrar = '--borrar' in sys.argv
    total = 0
    for p in objetivos():
        s = tam(p)
        total += s
        print(f'{s / 2**20:9.1f} MB  {p.relative_to(ROOT)}')
        if borrar and p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    print(f'{"borrados" if borrar else "a borrar"}: {total / 2**30:.2f} GB')


if __name__ == '__main__':
    main()


