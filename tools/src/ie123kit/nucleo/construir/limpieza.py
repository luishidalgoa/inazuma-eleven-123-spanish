"""Limpieza de work/ según docs/ARQUITECTURA.md.

Borra lo que se puede regenerar o está superado: candidatas probe_ie1_vN que no sean las dos últimas,
imágenes de ROM reconstruidas de releases publicadas, volcados de texturas de auditorías antiguas,
descargas duplicadas de herramientas, cachés y temporales (.partial, .yuv, __pycache__, *_x2.png).
Nunca toca: shared/base_3ds, ieN/fuentes, Roms, capas vN con scripts, docs ni tools.
Uso: python tools/limpiar_work.py            (solo lista)
     python tools/limpiar_work.py --borrar   (borra)
"""
import re
import time

from ie123kit.nucleo.config.raiz import find_root

ROOT = find_root()
WORK = ROOT / 'work'

FIJOS = [
    'shared/releases/release_v35/base_rebuilt.3ds', 'shared/releases/release_v35/roundtrip_v35.3ds',
    'ie1/capas/v58/cinematicas/fuentes', 'ie1/legacy/pending/renders', 'ie1/legacy/pending/audit',
]
CANDIDATAS_A_CONSERVAR = 2


def objetivos():
    out = [WORK / p for p in FIJOS]
    probes = sorted((p for p in (WORK / 'shared/candidatas').glob('probe_ie1_v*') if re.fullmatch(r'probe_ie1_v\d+', p.name)),
                    key=lambda p: int(p.name.rsplit('v', 1)[1]))
    out += [p for p in probes[:-CANDIDATAS_A_CONSERVAR] if not (p / '.conservar').exists()]  # golden de #41
    out += list(WORK.rglob('__pycache__'))
    out += [p for pat in ('*.partial', '*.yuv', '*_x2.png', 'tmp_*.dat') for p in WORK.rglob(pat)]
    out += [p for p in (WORK / 'shared/trailer').glob('check*.*') if re.fullmatch(r'check\d*\.(err|json)', p.name)]
    out += [ROOT / 'sideloadlydaemon.log']
    return [p for p in dict.fromkeys(out) if p.exists()]


def tam(p):
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob('*') if f.is_file())


# --- Limpieza automática (hook) ------------------------------------------------------------------
# Política: solo se borra lo que se regenera solo o lo que ya está superado por una copia más reciente.
# Nunca se borra nada que no esté bajo ROOT, nunca se sigue un enlace simbólico y nunca se toca nada
# modificado hace menos de EDAD_MINIMA_S (una construcción en curso deja .partial y temporales).
EDAD_MINIMA_S = 3600
CACHES = ('__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache')
TEMPORALES = ('*.partial', '*.yuv', 'tmp_*.dat')
CARPETA_COPIAS_PREVIAS = 'shared/backups_instalado'
#: archive.fa.antes_x, ina_main1.cro.antes_y…: se conserva la más reciente de cada familia (la vuelta atrás).
COPIAS_A_CONSERVAR = 1
#: Ficheros de este tamaño o mayor fuera de las carpetas de originales se señalan en el informe.
UMBRAL_INFORME = 200 * 2**20
EXTENSIONES_PESADAS = {'.fa', '.3ds', '.cia', '.cci', '.nds'}
CARPETAS_DE_ORIGINALES = ('fuentes', 'base_3ds', 'backups_instalado')


def _seguro(p, raiz=None):
    """Una ruta solo es borrable si cuelga de la raíz del repositorio y no es un enlace simbólico."""
    raiz = (raiz or ROOT).resolve()
    try:
        if p.is_symlink():
            return False
        p.resolve().relative_to(raiz)
    except (OSError, ValueError):
        return False
    return p.resolve() != raiz


def _mtime_max(p):
    if p.is_file() or p.is_symlink():
        return p.lstat().st_mtime
    ms = [p.lstat().st_mtime]
    ms += [f.lstat().st_mtime for f in p.rglob('*')]
    return max(ms)


def objetivos_auto(raiz=None, ahora=None, edad_minima=EDAD_MINIMA_S):
    """Lista de (ruta, motivo) borrable sin preguntar: cachés, temporales y copias previas superadas."""
    raiz = raiz or ROOT
    ahora = time.time() if ahora is None else ahora
    work = raiz / 'work'
    out = []
    # Cachés regenerables en work/ y tools/ (no en .git ni en entornos virtuales).
    for base in (work, raiz / 'tools'):
        if not base.is_dir():
            continue
        for nombre in CACHES:
            out += [(p, 'caché regenerable') for p in base.rglob(nombre) if p.is_dir()]
    out += [(p, 'metadatos de instalación editable') for p in (raiz / 'tools' / 'src').glob('*.egg-info')]
    out += [(p, 'caché regenerable') for nombre in CACHES for p in raiz.glob(nombre) if p.is_dir()]
    # Temporales de construcciones, solo si llevan tiempo sin tocarse.
    if work.is_dir():
        out += [(p, 'temporal de construcción') for pat in TEMPORALES for p in work.rglob(pat) if p.is_file()]
    # Copias previas del instalado: queda la más reciente de cada familia.
    carpeta = work / CARPETA_COPIAS_PREVIAS
    if carpeta.is_dir():
        familias = {}
        for p in carpeta.iterdir():
            if p.is_file() and not p.is_symlink() and '.antes_' in p.name:
                familias.setdefault(p.name.split('.antes_')[0], []).append(p)
        for fam in familias.values():
            fam.sort(key=lambda p: (p.stat().st_mtime, p.name))
            out += [(p, 'copia previa superada por otra más reciente') for p in fam[:-COPIAS_A_CONSERVAR]]
    vistos, res = set(), []
    for p, motivo in out:
        if p in vistos or not p.exists() or not _seguro(p, raiz):
            continue
        vistos.add(p)
        if ahora - _mtime_max(p) < edad_minima:
            continue
        res.append((p, motivo))
    return res


def informe_espacio(raiz=None, umbral=UMBRAL_INFORME):
    """Ficheros pesados de ROM/archive fuera de las carpetas de originales: se señalan, no se borran."""
    raiz = raiz or ROOT
    work = raiz / 'work'
    res = []
    if not work.is_dir():
        return res
    for p in work.rglob('*'):
        if p.suffix.lower() in EXTENSIONES_PESADAS and p.is_file() and not p.is_symlink():
            if set(p.relative_to(work).parts) & set(CARPETAS_DE_ORIGINALES):
                continue
            if p.stat().st_size >= umbral:
                res.append((p, p.stat().st_size))
    return sorted(res, key=lambda x: -x[1])
