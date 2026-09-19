"""Entorno de una capa de ``work/`` sin el bootstrap copiado en 110 scripts.

Cada capa de ``work/`` rehacía lo mismo: subir N niveles desde ``__file__`` para dar con la raíz,
``sys.path.insert`` de ``tools``, ``os.chdir(ROOT)``, ``sys.stdout.reconfigure('utf-8')`` y
``HERE/'extra'/rel`` con ``mkdir(parents=True)``. :class:`Capa` lo sustituye para las capas
NUEVAS (las existentes no se reescriben): la raíz se localiza con ``nucleo.config.raiz.find_root``
(marcador AGENTS.md + tools/pyproject.toml, con ``IE123_ROOT``), nunca contando niveles, y como
todas las rutas que devuelve son absolutas no hace falta ningún ``chdir``.
"""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

__all__ = ["HISTORIAL", "TEMAS", "Capa", "ejecutar", "listar_capas", "ubicacion"]

#: Temas de ``work/<juego>/capas/<tema>/<linea>/`` (docs/ARQUITECTURA.md, reorganización del 2026-09-19).
TEMAS = ("dialogo", "nombres", "rotulos_objetivos", "menus_cro", "graficos", "media", "fuentes",
         "teclado", "candidata")
#: Carpeta de versiones sustituidas: ``capas/historial/<tema>/vNN_<linea>/`` (solo consulta).
HISTORIAL = "historial"
_RX_TANDA = re.compile(r"v\d+(?:\.\d+)?")
_RX_HISTORICA = re.compile(r"(v\d+(?:\.\d+)?)_(.+)")


def ubicacion(partes: tuple[str, ...] | list[str]) -> dict[str, str]:
    """``tema``, ``version`` y ``linea`` de las partes de ruta que siguen a ``capas``.

    Admite las tres formas: ``<tema>/<linea>`` (vigente, sin versión), ``historial/<tema>/vNN_<linea>``
    y la antigua ``vNN/<linea>`` (antes de la reorganización; sin tema).
    """
    partes = list(partes)
    tema = version = linea = ""
    if partes and partes[0] == HISTORIAL:
        tema = partes[1] if len(partes) > 1 else ""
        if len(partes) > 2:
            m = _RX_HISTORICA.fullmatch(partes[2])
            version, linea = (m.group(1), m.group(2)) if m else ("", partes[2])
    elif partes and _RX_TANDA.fullmatch(partes[0]):
        version = partes[0]
        linea = partes[1] if len(partes) > 1 else ""
    elif partes:
        tema = partes[0]
        linea = partes[1] if len(partes) > 1 else ""
    return {"tema": tema, "version": version, "linea": linea}


def listar_capas(raiz_capas: str | os.PathLike[str], *, historial: bool = False) -> list[Path]:
    """Carpetas de capa bajo ``work/<juego>/capas`` (dos niveles), ordenadas.

    Sirve para la disposición por tema (``<tema>/<linea>``) y para la antigua por tanda
    (``vNN/<linea>``). ``historial/`` se omite salvo que se pida (tres niveles).
    """
    raiz = Path(raiz_capas)
    if not raiz.is_dir():
        return []
    salida: list[Path] = []
    for grupo in sorted(p for p in raiz.iterdir() if p.is_dir()):
        if grupo.name == HISTORIAL:
            if historial:
                salida += [c for tema in sorted(p for p in grupo.iterdir() if p.is_dir())
                           for c in sorted(p for p in tema.iterdir() if p.is_dir())]
            continue
        salida += sorted(p for p in grupo.iterdir() if p.is_dir())
    return salida

#: Subcarpeta de eventos por paquete (eve.pkb / mch.pkb).
_CARPETA_EVENTOS = {"eve": "events", "mch": "events_mch"}


class Capa:
    """Rutas y metadatos de la capa a la que pertenece ``fichero`` (normalmente ``__file__``)."""

    def __init__(self, fichero: str | os.PathLike[str], *, raiz: str | os.PathLike[str] | None = None) -> None:
        from ie123kit.nucleo.config.raiz import find_root

        ruta = Path(fichero).resolve()
        # Una carpeta que existe ES la capa aunque su nombre lleve un punto (``ie2.comun``,
        # ``v67.1``): mirar solo el sufijo haría de capa a su carpeta padre.
        self.aqui: Path = ruta if ruta.is_dir() else (ruta.parent if ruta.is_file() or ruta.suffix else ruta)
        self.raiz: Path = Path(raiz).resolve() if raiz is not None else find_root()
        self._meta: dict | None = None

    # -- metadatos --------------------------------------------------------
    @property
    def fichero_meta(self) -> Path:
        return self.aqui / "capa.toml"

    def _deducir(self) -> dict:
        """Metadatos deducidos de la ruta (ver :func:`ubicacion`).

        ``work/<objetivo>/capas/<tema>/<linea>``, ``.../capas/historial/<tema>/vNN_<linea>`` o la
        antigua ``.../capas/vNN/<linea>``. Una capa vigente no lleva versión en la ruta: la da su
        ``capa.toml``.
        """
        try:
            partes = self.aqui.relative_to(self.raiz).parts
        except ValueError:
            partes = self.aqui.parts
        objetivo = ""
        lugar = {"tema": "", "version": "", "linea": ""}
        if "capas" in partes:
            i = partes.index("capas")
            objetivo = "/".join(partes[1:i]) if i >= 2 and partes[0] == "work" else "/".join(partes[:i])
            lugar = ubicacion(partes[i + 1:])
        return {
            "objetivo": objetivo,
            "tema": lugar["tema"],
            "version": lugar["version"],
            "linea": lugar["linea"] or self.aqui.name,
            "base": "",
            "descripcion": "",
            "aportaciones": [],
        }

    @property
    def meta(self) -> dict:
        """``capa.toml`` fusionado sobre los valores deducidos de la ruta."""
        if self._meta is None:
            datos = self._deducir()
            fichero = self.fichero_meta
            if fichero.is_file():
                with fichero.open("rb") as fh:
                    leido = tomllib.load(fh)
                tabla = leido.get("capa") if isinstance(leido.get("capa"), dict) else leido
                datos.update({k: v for k, v in tabla.items() if v is not None})
            self._meta = datos
        return dict(self._meta)

    @property
    def version(self) -> str:
        return str(self.meta["version"])

    @property
    def tema(self) -> str:
        return str(self.meta.get("tema", ""))

    @property
    def objetivo(self) -> str:
        return str(self.meta["objetivo"])

    @property
    def linea(self) -> str:
        return str(self.meta["linea"])

    # -- rutas ------------------------------------------------------------
    def extra(self, rel: str | os.PathLike[str] = "") -> Path:
        """Ruta dentro de ``<capa>/extra`` (ficheros relativos al archive), creando carpetas."""
        destino = self.aqui / "extra" / Path(rel)
        padre = destino if not Path(rel).name else destino.parent
        padre.mkdir(parents=True, exist_ok=True)
        return destino

    def eventos(self, pack: str = "eve") -> Path:
        """Carpeta de scripts ``.ssd`` del paquete ``eve`` o ``mch`` (se crea)."""
        if pack not in _CARPETA_EVENTOS:
            raise ValueError(f"paquete de eventos desconocido: {pack!r}; válidos: eve, mch")
        destino = self.aqui / _CARPETA_EVENTOS[pack]
        destino.mkdir(parents=True, exist_ok=True)
        return destino

    def romfs(self, rel: str | os.PathLike[str] = "") -> Path:
        """Ruta dentro de ``<capa>/romfs`` (por ejemplo ``cro/ina_main1.cro``), creando carpetas."""
        destino = self.aqui / "romfs" / Path(rel)
        padre = destino if not Path(rel).name else destino.parent
        padre.mkdir(parents=True, exist_ok=True)
        return destino

    def informe(self, nombre: str) -> Path:
        """Ruta de un informe de la capa (``<capa>/informes/<nombre>``)."""
        destino = self.aqui / "informes" / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino

    def aportacion(self) -> dict:
        """Aportación de esta capa lista para ``construir(..., aportaciones=[...])``."""
        eventos = {p: self.aqui / c for p, c in _CARPETA_EVENTOS.items() if (self.aqui / c).is_dir()}
        cro = sorted((self.aqui / "romfs" / "cro").glob("*.cro")) if (self.aqui / "romfs" / "cro").is_dir() else []
        return {
            "objetivo": self.objetivo or self.linea,
            "extra": self.aqui / "extra",
            "eventos": eventos or None,
            "cro": cro,
        }

    def __repr__(self) -> str:  # pragma: no cover - diagnóstico
        return f"Capa(aqui={self.aqui!s}, version={self.version!r}, objetivo={self.objetivo!r})"


def ejecutar(main) -> int:
    """Ejecuta ``main()`` con stdout en UTF-8 y errores de validación en una línea.

    ``AssertionError`` y ``ValueError`` se convierten en un mensaje a stderr y código 1;
    el resto de excepciones se dejan propagar (traza completa) porque son fallos del código.
    """
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar is not None:
        reconfigurar(encoding="utf-8")
    try:
        resultado = main()
    except (AssertionError, ValueError) as err:
        sys.stderr.write(f"FALLO: {type(err).__name__}: {err}\n")
        return 1
    return 0 if resultado is None else int(resultado)
