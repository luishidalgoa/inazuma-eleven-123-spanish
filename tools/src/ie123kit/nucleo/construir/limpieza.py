"""Limpieza de work/ según docs/ARQUITECTURA.md.

Borra lo que se puede regenerar o está superado: candidatas probe_ie1_vN que no sean las dos últimas,
imágenes de ROM reconstruidas de releases publicadas, volcados de texturas de auditorías antiguas,
descargas duplicadas de herramientas, cachés y temporales (.partial, .yuv, __pycache__, *_x2.png).
Nunca toca: shared/base_3ds, cualquier carpeta `fuentes`, Roms, los congelados del bloqueo v20,
candidatas con `.conservar`, docs ni tools. La lista de PROTEGIDOS es la última palabra: filtra la
salida entera, también los FIJOS, para que `limpiar` no pueda proponer nada de ahí por descuido.

Los cinco ámbitos de work/ son `shared`, `juego_principal`, `ie1`, `ie2` e `ie3`; fuera de ellos
no debe haber nada (docs/ARQUITECTURA.md, regla 1) y esta limpieza no mira ahí.

Uso: python tools/limpiar_work.py            (solo lista)
     python tools/limpiar_work.py --borrar   (borra)
"""
import re
import shutil
from pathlib import Path

from ie123kit.nucleo.config.raiz import find_root

# ROOT y WORK los sirve `__getattr__` (PEP 562) para que importar este módulo no busque la raíz
# del repo; `from ... import *` los resuelve con getattr, así que la fachada de _legado los ve.
__all__ = [  # noqa: F822 - ROOT y WORK son atributos diferidos de módulo
    'AMBITOS', 'CANDIDATAS_A_CONSERVAR', 'FIJOS', 'PROTEGIDOS', 'ROOT', 'WORK',
    'borrar', 'esta_protegido', 'objetivos', 'raiz', 'tam', 'work',
]

#: Ámbitos de work/ (docs/ARQUITECTURA.md). `juego_principal` es uno más, como shared/ie1/ie2/ie3.
AMBITOS = ('shared', 'juego_principal', 'ie1', 'ie2', 'ie3')

FIJOS = [
    'shared/releases/release_v35/base_rebuilt.3ds', 'shared/releases/release_v35/roundtrip_v35.3ds',
    # Protegido por PROTEGIDOS (toda carpeta `fuentes` lo está); se deja escrito para que se vea
    # que era un objetivo histórico y por qué ya no se lista.
    'ie1/capas/media/cinematicas/fuentes', 'ie1/legacy/pending/renders', 'ie1/legacy/pending/audit',
]
CANDIDATAS_A_CONSERVAR = 2

#: Rutas relativas a work/ que NUNCA se listan ni se borran. `fuentes` va por nombre de carpeta
#: (a cualquier profundidad) y `base_3ds` por prefijo: son las dos que no se pueden regenerar.
PROTEGIDOS = ('shared/base_3ds',)
#: Nombres de carpeta intocables en cualquier punto del árbol.
CARPETAS_PROTEGIDAS = ('fuentes',)
#: Congelados del bloqueo tipográfico v20: ni se listan ni se borran jamás (AGENTS.md).
CONGELADOS = ('dialogue_typography.py', 'font_patch.py', 'dialogue_lock.py',
              'build_ie1_probe.py', 'build_ui_revision.py')


def raiz():
    """Raíz del repositorio. Es una función para que importar este módulo no haga E/S."""
    return find_root()


def work():
    """Carpeta work/ del repositorio."""
    return raiz() / 'work'


def __getattr__(nombre):
    """`ROOT` y `WORK` siguen existiendo como atributos (los usa la fachada de _legado)."""
    if nombre == 'ROOT':
        return raiz()
    if nombre == 'WORK':
        return work()
    raise AttributeError(nombre)


def esta_protegido(p, base=None):
    """¿Esta ruta cae en algo que no se puede borrar nunca?"""
    p = Path(p)
    base = Path(base) if base is not None else work()
    if p.name in CONGELADOS or p.name == '.conservar':
        return True
    if any(parte in CARPETAS_PROTEGIDAS for parte in p.parts):
        return True
    try:
        rel = p.relative_to(base).as_posix()
    except ValueError:
        return False
    if any(rel == q or rel.startswith(q + '/') for q in PROTEGIDOS):
        return True
    # Una candidata marcada .conservar protege todo lo que cuelga de ella (golden de #41).
    partes = rel.split('/')
    if len(partes) >= 3 and partes[0] == 'shared' and partes[1] == 'candidatas':
        return (base / 'shared' / 'candidatas' / partes[2] / '.conservar').exists()
    return False


def objetivos():
    """Rutas de work/ que se pueden borrar, ya filtradas por PROTEGIDOS."""
    WORK = work()
    ROOT = raiz()
    out = [WORK / p for p in FIJOS]
    candidatas = WORK / 'shared/candidatas'
    probes = sorted((p for p in candidatas.glob('probe_ie1_v*') if re.fullmatch(r'probe_ie1_v\d+', p.name)),
                    key=lambda p: int(p.name.rsplit('v', 1)[1])) if candidatas.is_dir() else []
    out += [p for p in probes[:-CANDIDATAS_A_CONSERVAR] if not (p / '.conservar').exists()]  # golden de #41
    for ambito in AMBITOS:
        base = WORK / ambito
        if not base.is_dir():
            continue
        out += list(base.rglob('__pycache__'))
        out += [p for pat in ('*.partial', '*.yuv', '*_x2.png', 'tmp_*.dat') for p in base.rglob(pat)]
    trailer = WORK / 'shared/trailer'
    if trailer.is_dir():
        out += [p for p in trailer.glob('check*.*') if re.fullmatch(r'check\d*\.(err|json)', p.name)]
    out += [ROOT / 'sideloadlydaemon.log']
    return [p for p in dict.fromkeys(out) if p.exists() and not esta_protegido(p, WORK)]


def tam(p):
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob('*') if f.is_file())


def borrar():
    """Borra todo lo que devuelve `objetivos()` y devuelve las rutas borradas."""
    borradas = []
    for p in objetivos():
        if not p.exists():
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
        borradas.append(p)
    return borradas
