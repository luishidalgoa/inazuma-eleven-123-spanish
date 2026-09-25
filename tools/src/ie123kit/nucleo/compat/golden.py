"""Hashes golden de la migración del toolkit (#41): ficheros congelados, capa de referencia y candidatas.

Uso:
  python -m ie123kit.nucleo.compat.golden capturar
  python -m ie123kit.nucleo.compat.golden comprobar [--capa work/ie1/capas/graficos/titulo_logo] [--referencia]
  python -m ie123kit.nucleo.compat.golden comprobar --capa <capa> --candidata <probe_…>

Referencia (desde 2026-09-19, #49): las candidatas probe_ie1_v66/v67 se borraron, así que los gates
ya no dependen de candidatas desechables. La base es la extracción de la ROM
(``work/shared/base_3ds/romfs``, que existe siempre que haya work/) y la capa es
``work/ie1/capas/graficos/titulo_logo`` (la antigua v67/titulo_logo).

- ``--capa``: regenera en un temporal la textura ``ie01_title_t_tlogo`` de la capa con
  ``texturas.apply_plan`` sobre la base, tomando la imagen de la propia capa, y exige que el .arc
  salga byte a byte igual al golden (``capa_referencia.sha256``). Nunca escribe en la capa: el
  apply.py original depende de probe_ie1_v66 y de un PNG de Descargas que ya no existen.
- ``--referencia``: construye base + capa con el script congelado build_ui_revision.py en un
  temporal y exige ``ARCHIVE_REFERENCIA`` y la CRO de la base.
- ``--candidata``: reconstruye una candidata cuya base (según su archive.build.json) siga en
  work/shared/candidatas; útil para candidatas nuevas, no forma parte del gate.
Nunca se escribe en work/shared/candidatas. Solo se versionan hashes, nunca datos del juego (Norma 2).
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PureWindowsPath

CONGELADOS = ['tools/dialogue_typography.py', 'tools/font_patch.py', 'tools/dialogue_lock.py',
              'tools/build_ie1_probe.py', 'tools/build_ui_revision.py']
BASE_REFERENCIA = 'work/shared/base_3ds/romfs'
CAPA = 'work/ie1/capas/graficos/titulo_logo'
RUTA_ARC = 'inazuma1/data_iz/a_title/title_t.arc'
TEXTURA = 'ie01_title_t_tlogo.tga'
# sha256 de archive.fa = base_3ds + capa de referencia (build_ui_revision.py y construir coinciden).
ARCHIVE_REFERENCIA = '6f23e4d5debb8e9a6c634b7e280c6918ef60b92811c03d7b2755122e42b0d7f1'
# Candidata vigente cuya integridad se vigila (se actualiza al fijar una candidata nueva).
CANDIDATA_VIGENTE = 'probe_ie2_v34'
CANDIDATAS = [f'work/shared/candidatas/{CANDIDATA_VIGENTE}']
# La base extraída lleva las fuentes originales y el bloqueo v20 de `construir` la rechaza; la
# construcción con bloqueo se prueba reaplicando la capa (ya incluida) sobre la candidata vigente:
# mismo contenido entrada a entrada y este sha (el reempaquetado compacta el archive).
ARCHIVE_VIGENTE_REAPLICADA = '5f52d315af4df8f070b833493e7e6e34847c619f7989db2be3caf99002b27948'
GRUPO_CAPA = 'capa_referencia.sha256'


def _raiz():
    from ie123kit.nucleo.config.raiz import find_root
    return find_root()


def _golden(raiz):
    return raiz / 'tools' / 'tests' / 'compat' / 'golden'


def grupos(raiz):
    base = raiz / BASE_REFERENCIA
    return {
        'congelados.sha256': lambda: [raiz / p for p in CONGELADOS],
        GRUPO_CAPA: lambda: sorted(p for p in (raiz / CAPA / 'extra').rglob('*') if p.is_file()),
        'candidatas.sha256': lambda: [base / 'archive.fa', *sorted((base / 'cro').glob('*.cro'))]
        + [f for c in CANDIDATAS for f in [raiz / c / 'archive.fa', *sorted((raiz / c / 'romfs').rglob('*.cro'))]],
    }


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def comprobar_grupo(nombre, raiz=None):
    raiz = raiz or _raiz()
    esperado = (_golden(raiz) / nombre).read_text(encoding='utf-8').splitlines()
    malos = []
    for linea in esperado:
        h, rel = linea.split('  ', 1)
        p = raiz / rel
        if not p.is_file():
            malos.append(f'ausente {rel}')
        elif sha(p) != h:
            malos.append(f'distinto {rel}')
    return len(esperado), malos


def _imagen_de_capa(arc_bytes):
    """Imagen RGBA de la textura de referencia dentro del .arc (SSZL) de la capa."""
    from ie123kit.nucleo.graficos import ctpk, texturas
    return ctpk.decode(texturas.find_texture(arc_bytes, TEXTURA).blob).convert('RGBA')


def regenerar_capa(raiz=None):
    """Regenera en un temporal el .arc de la capa de referencia y lo compara con el golden."""
    raiz = raiz or _raiz()
    from ie123kit.nucleo.graficos import texturas
    total, malos = comprobar_grupo(GRUPO_CAPA, raiz)
    base = raiz / BASE_REFERENCIA / 'archive.fa'
    esperado = raiz / CAPA / 'extra' / RUTA_ARC
    if not base.is_file() or not esperado.is_file():
        return total, [*malos, f'falta {base.relative_to(raiz).as_posix() if not base.is_file() else esperado}']
    imagen = _imagen_de_capa(esperado.read_bytes())
    tmp = Path(tempfile.mkdtemp(prefix='ie123_golden_'))
    try:
        def poner_logo(_antes):
            return imagen
        texturas.apply_plan(base, {RUTA_ARC: {TEXTURA: poner_logo}}, tmp, rewrap='sszl')
        if sha(tmp / RUTA_ARC) != sha(esperado):
            malos.append(f'regenerado distinto {RUTA_ARC}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return total, malos


def _reconstruir(raiz, base, capa, salida, cro=None):
    # F2.7: sin shims en tools/, el congelado se lanza con los alias de congelados.preparar.
    orden = [sys.executable, '-X', 'utf8', '-m', 'ie123kit.nucleo.compat.congelados', 'build_ui_revision',
             '--base', str(base), '--ui', str(raiz / capa), '--output', str(salida)]
    if cro is not None:
        orden += ['--cro', str(cro)]
    return subprocess.run(orden, cwd=raiz, check=False, stdout=subprocess.DEVNULL).returncode


def comprobar_referencia(raiz=None):
    """Construye base_3ds + capa de referencia en un temporal; devuelve el número de fallos."""
    raiz = raiz or _raiz()
    base = raiz / BASE_REFERENCIA
    cro_base = base / 'cro' / 'ina_main1.cro'
    if not (base / 'archive.fa').is_file() or not cro_base.is_file():
        print(f'referencia: falta {BASE_REFERENCIA}/archive.fa o su cro/ina_main1.cro')
        return 1
    tmp = Path(tempfile.mkdtemp(prefix='ie123_ref_'))
    try:
        salida = tmp / 'referencia' / 'archive.fa'
        rc = _reconstruir(raiz, base / 'archive.fa', CAPA, salida, cro_base)
        fallos = int(rc != 0)
        archive_ok = salida.is_file() and sha(salida) == ARCHIVE_REFERENCIA
        cro = salida.parent / 'romfs' / 'cro' / 'ina_main1.cro'
        cro_ok = cro.is_file() and sha(cro) == sha(cro_base)
        fallos += (not archive_ok) + (not cro_ok)
        print(f'referencia: build_ui_revision {rc}, archive {"OK" if archive_ok else "DISTINTO"}, '
              f'cro {"OK" if cro_ok else "DISTINTA"}')
        return fallos
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def comprobar_candidata(raiz, nombre, capa):
    """Reconstruye la candidata en un temporal y la compara con la instalada; devuelve el número de fallos."""
    candidatas = raiz / 'work' / 'shared' / 'candidatas'
    carpeta = candidatas / nombre
    meta = json.loads((carpeta / 'archive.build.json').read_text(encoding='utf-8'))
    # Solo el nombre de la carpeta base: la ruta absoluta del JSON es de la máquina que la construyó.
    base = candidatas / PureWindowsPath(meta['base']).parent.name / 'archive.fa'
    if not base.is_file() or sha(base) != meta['base_sha256']:
        print(f'candidata {nombre}: base {base.parent.name}/archive.fa ausente o con sha256 distinto')
        return 1
    tmp = Path(tempfile.mkdtemp(prefix='ie123_regen_'))
    try:
        salida = tmp / nombre / 'archive.fa'
        # Si la capa no trae CRO, la candidata heredó el de su base: se le pasa el mismo (solo lectura).
        cro_base = base.parent / 'romfs' / 'cro' / 'ina_main1.cro'
        cro = cro_base if not (raiz / capa / 'romfs' / 'cro' / 'ina_main1.cro').is_file() and cro_base.is_file() \
            else None
        rc = _reconstruir(raiz, base, capa, salida, cro)
        fallos = 0
        if rc:
            print(f'candidata {nombre}: build_ui_revision.py devolvió {rc}')
            fallos += 1
        archive_ok = salida.is_file() and sha(salida) == meta['archive_sha256']
        if not archive_ok:
            fallos += 1
        cros = sorted((carpeta / 'romfs').rglob('*.cro'))
        cro_ok = 0
        for cro in cros:
            homologo = tmp / nombre / 'romfs' / cro.relative_to(carpeta / 'romfs')
            if homologo.is_file() and sha(homologo) == sha(cro):
                cro_ok += 1
            else:
                print(f'candidata {nombre}: CRO distinto o ausente {cro.relative_to(carpeta).as_posix()}')
                fallos += 1
        print(f'candidata {nombre}: archive {"OK" if archive_ok else "DISTINTO"}, cro {cro_ok}/{len(cros)} OK')
        return fallos
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['capturar', 'comprobar'])
    ap.add_argument('--capa', help=f'regenera la capa en un temporal (solo {CAPA} tiene golden)')
    ap.add_argument('--referencia', action='store_true',
                    help=f'construye {BASE_REFERENCIA} + la capa y exige el sha de referencia')
    ap.add_argument('--candidata', help='reconstruye esta candidata en un temporal desde su base; exige --capa')
    args = ap.parse_args()
    if args.candidata and (args.accion != 'comprobar' or not args.capa):
        print('--candidata solo es válida con comprobar y exige --capa')
        return 2
    raiz = _raiz()
    golden = _golden(raiz)
    if args.accion == 'capturar':
        golden.mkdir(exist_ok=True)
        for nombre, ficheros in grupos(raiz).items():
            lineas = [f'{sha(p)}  {p.relative_to(raiz).as_posix()}' for p in ficheros()]
            (golden / nombre).write_text('\n'.join(lineas) + '\n', encoding='utf-8')
            print('capturado', nombre, len(lineas))
        return 0
    if args.capa and Path(args.capa).as_posix().rstrip('/') != CAPA and not args.candidata:
        print(f'--capa {args.capa}: no hay golden para esa capa')
        return 1
    fallos = 0
    for nombre in grupos(raiz):
        total, malos = (regenerar_capa(raiz) if args.capa and not args.candidata and nombre == GRUPO_CAPA
                        else comprobar_grupo(nombre, raiz))
        for m in malos:
            print(nombre, m)
        print(f'{nombre}: {total - len(malos)}/{total} OK')
        fallos += len(malos)
    if args.referencia:
        fallos += comprobar_referencia(raiz)
    if args.candidata:
        fallos += comprobar_candidata(raiz, args.candidata, args.capa)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
