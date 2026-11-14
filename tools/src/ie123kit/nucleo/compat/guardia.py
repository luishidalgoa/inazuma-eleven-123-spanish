"""Guardia de integridad del repositorio (bloqueo v20 y Norma 2).

Órdenes (``python -m ie123kit.nucleo.compat.guardia <orden>``):

- ``bloqueados``: comprueba que los 5 ficheros congelados coinciden byte a byte
  con ``tools/tests/compat/golden/congelados.sha256`` y con el diccionario
  ``SOURCE_HASHES`` de ``tools/dialogue_lock.py`` (leído por AST, sin importar).
- ``git``: falla si algún fichero rastreado por git parece una ROM o contenido
  extraído (Norma 2 de CLAUDE.md, ver LEGAL.md).
- ``version``: comprueba que ``[release] version`` de ``ie123.toml`` es la única fuente
  de la versión que enseña la pantalla de créditos (``render.py`` no puede llevarla
  escrita a mano) y, con ``--tag vX.Y``, que el tag que se va a publicar coincide.
- ``todo``: ejecuta las tres.

Importar este módulo no produce E/S.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
import sys
from pathlib import Path, PurePosixPath

__all__ = [
    "CARPETAS_PNG_AUTORIZADAS",
    "EXTENSIONES_PROHIBIDAS",
    "LIMITE_PNG",
    "PREFIJOS_PROHIBIDOS",
    "RUTA_CONGELADOS",
    "RUTA_LOCK",
    "comprobar_bloqueados",
    "comprobar_git",
    "comprobar_version",
    "leer_congelados",
    "leer_source_hashes",
    "main",
    "rutas_prohibidas",
]

#: Extensiones de ROM o de contenido extraído que nunca pueden rastrearse.
EXTENSIONES_PROHIBIDAS: frozenset[str] = frozenset(
    {".3ds", ".cia", ".nds", ".cci", ".cxi", ".fa", ".arc", ".lzs", ".str", ".dat",
     ".pkb", ".pkh", ".bcfnt", ".nftr", ".moflex", ".mods", ".sad"}
)
#: Prefijos de carpeta (en minúsculas) reservados a ROMs y datos de trabajo.
PREFIJOS_PROHIBIDOS: tuple[str, ...] = ("roms/", "work/")
#: Tamaño máximo (bytes) de un .png rastreado fuera de las carpetas autorizadas.
LIMITE_PNG: int = 262144
#: Nombres de carpeta en los que se admiten .png grandes (logos propios del proyecto).
CARPETAS_PNG_AUTORIZADAS: frozenset[str] = frozenset({"logos"})

RUTA_CONGELADOS = "tools/tests/compat/golden/congelados.sha256"
RUTA_LOCK = "tools/dialogue_lock.py"
RUTA_CREDITOS = "work/ie1/capas/graficos/creditos_javiju/render.py"
NUM_CONGELADOS = 5


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def leer_congelados(texto: str) -> dict[str, str]:
    """Convierte el contenido de congelados.sha256 en {ruta: sha}."""
    res: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        sha, _, ruta = linea.partition(" ")
        res[ruta.strip().lstrip("*")] = sha.lower()
    return res


def leer_source_hashes(codigo: str) -> dict[str, str]:
    """Extrae por AST el dict literal SOURCE_HASHES de dialogue_lock.py."""
    for nodo in ast.parse(codigo).body:
        if isinstance(nodo, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SOURCE_HASHES" for t in nodo.targets
        ):
            valor = ast.literal_eval(nodo.value)
            if not isinstance(valor, dict):
                raise ValueError("SOURCE_HASHES no es un dict literal")
            return {str(k): str(v).lower() for k, v in valor.items()}
    raise ValueError("SOURCE_HASHES no encontrado")


def comprobar_bloqueados(raiz: Path, salida=None) -> int:
    """Devuelve 0 si los congelados coinciden; 1 si hay diferencias."""
    salida = salida or sys.stdout
    fallos = 0
    manifiesto = raiz / RUTA_CONGELADOS
    if not manifiesto.is_file():
        print(f"AUSENTE {RUTA_CONGELADOS}", file=salida)
        return 1
    congelados = leer_congelados(manifiesto.read_text(encoding="utf-8"))
    if len(congelados) != NUM_CONGELADOS:
        print(f"DISTINTO {RUTA_CONGELADOS}: {len(congelados)} entradas, se esperan {NUM_CONGELADOS}", file=salida)
        fallos += 1
    for rel, sha in congelados.items():
        p = raiz / PurePosixPath(rel)
        if not p.is_file():
            print(f"AUSENTE {rel}", file=salida)
            fallos += 1
        elif _sha256(p) != sha:
            print(f"DISTINTO {rel}", file=salida)
            fallos += 1
        else:
            print(f"OK {rel}", file=salida)
    lock = raiz / RUTA_LOCK
    if not lock.is_file():
        print(f"AUSENTE {RUTA_LOCK} (SOURCE_HASHES)", file=salida)
        return 1
    try:
        fuentes = leer_source_hashes(lock.read_text(encoding="utf-8"))
    except (ValueError, SyntaxError) as e:
        print(f"DISTINTO {RUTA_LOCK}: {e}", file=salida)
        return 1
    for rel, sha in fuentes.items():
        p = raiz / PurePosixPath(rel)
        if not p.is_file():
            print(f"AUSENTE {rel} (SOURCE_HASHES)", file=salida)
            fallos += 1
        elif _sha256(p) != sha or congelados.get(rel) != sha:
            print(f"DISTINTO {rel} (SOURCE_HASHES)", file=salida)
            fallos += 1
        else:
            print(f"OK {rel} (SOURCE_HASHES)", file=salida)
    return 1 if fallos else 0


def rutas_prohibidas(rutas: list[str], tamanos: dict[str, int] | None = None) -> list[tuple[str, str]]:
    """Lógica pura: devuelve [(ruta, motivo)] de las rutas rastreadas prohibidas.

    ``tamanos`` asocia rutas .png a su tamaño en bytes (los ausentes se ignoran).
    """
    tamanos = tamanos or {}
    malas: list[tuple[str, str]] = []
    for ruta in rutas:
        norm = ruta.replace("\\", "/")
        baja = norm.lower()
        if baja.startswith(PREFIJOS_PROHIBIDOS):
            malas.append((ruta, "carpeta prohibida"))
            continue
        ext = PurePosixPath(baja).suffix
        if ext in EXTENSIONES_PROHIBIDAS:
            malas.append((ruta, f"extensión {ext}"))
            continue
        if ext == ".png":
            carpetas = {c for c in PurePosixPath(baja).parts[:-1]}
            tam = tamanos.get(ruta)
            if tam is not None and tam > LIMITE_PNG and not (carpetas & CARPETAS_PNG_AUTORIZADAS):
                malas.append((ruta, f"png de {tam} bytes > {LIMITE_PNG}"))
    return malas


def _git(raiz: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=raiz, check=True, capture_output=True).stdout


def comprobar_git(raiz: Path, salida=None) -> int:
    """Revisa ``git ls-files``; devuelve 1 si hay ficheros prohibidos."""
    salida = salida or sys.stdout
    try:
        rutas = [r for r in _git(raiz, "ls-files", "-z").decode("utf-8").split("\0") if r]
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"ERROR git ls-files: {e}", file=salida)
        return 1
    tamanos: dict[str, int] = {}
    for r in rutas:
        if r.lower().endswith(".png"):
            p = raiz / PurePosixPath(r)
            try:
                tamanos[r] = int(_git(raiz, "cat-file", "-s", f":{r}").strip())
            except (OSError, subprocess.CalledProcessError, ValueError):
                if p.is_file():
                    tamanos[r] = p.stat().st_size
    malas = rutas_prohibidas(rutas, tamanos)
    for ruta, motivo in malas:
        print(f"PROHIBIDO {ruta}: {motivo}", file=salida)
    print(f"{len(rutas)} ficheros rastreados, {len(malas)} prohibidos", file=salida)
    return 1 if malas else 0


def comprobar_version(raiz: Path, tag: str | None = None, salida=None) -> int:
    """Versión de release coherente entre ``ie123.toml``, la pantalla de créditos y el tag.

    ``work/`` no está en git: si ``render.py`` no existe (CI) solo se valida el toml y el tag.
    """
    import re
    import tomllib

    salida = salida or sys.stdout
    try:
        version = tomllib.loads((raiz / "ie123.toml").read_text(encoding="utf-8"))["release"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as e:
        print(f"ERROR ie123.toml [release] version: {e!r}", file=salida)
        return 1
    if not re.fullmatch(r"\d+\.\d+(\.\d+)?", str(version)):
        print(f"ERROR version {version!r} no es X.Y ni X.Y.Z", file=salida)
        return 1
    codigo = 0
    render = raiz / RUTA_CREDITOS
    if render.is_file():
        fuente = render.read_text(encoding="utf-8")
        if re.search(r"VERSION\s*=\s*['\"]v?\d", fuente):
            print(f"ERROR {RUTA_CREDITOS}: la versión está escrita a mano; debe leerse de ie123.toml", file=salida)
            codigo = 1
        elif "ie123.toml" not in fuente:
            print(f"ERROR {RUTA_CREDITOS}: no lee ie123.toml", file=salida)
            codigo = 1
    if tag is not None and tag.lstrip("v") != str(version):
        print(f"ERROR el tag {tag} no coincide con ie123.toml [release] version = {version}: "
              "sube la versión, reconstruye los créditos y vuelve a intentarlo", file=salida)
        codigo = 1
    if codigo == 0:
        print(f"versión {version} coherente" + (f" con el tag {tag}" if tag else ""), file=salida)
    return codigo


def main(argv: list[str] | None = None) -> int:
    from ie123kit.nucleo.config.raiz import find_root

    ap = argparse.ArgumentParser(prog="python -m ie123kit.nucleo.compat.guardia", description=__doc__.splitlines()[0])
    ap.add_argument("orden", choices=["bloqueados", "git", "version", "todo"])
    ap.add_argument("--tag", help="con 'version': tag de release que debe coincidir con ie123.toml")
    a = ap.parse_args(argv)
    raiz = find_root()
    codigo = 0
    if a.orden in ("bloqueados", "todo"):
        codigo |= comprobar_bloqueados(raiz)
    if a.orden in ("git", "todo"):
        codigo |= comprobar_git(raiz)
    if a.orden in ("version", "todo"):
        codigo |= comprobar_version(raiz, a.tag)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
