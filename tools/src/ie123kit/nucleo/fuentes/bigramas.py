"""Registro de bigramas (casilla de texto -> código kanji reasignado) y su dibujo en las fuentes.

Portado de las capas de fuentes de ``work/`` (F2.5, #51):

- el registro es el ``registro.json`` de ``ie1/capas/fuentes/bigramas_ritmo`` (IE1 v89) y sus
  sucesores de IE2 (``nombres/nombres_compactos`` v08, ``menus_cro/menus`` v23). Las fuentes
  ``font/*.bcfnt`` están en la raíz de ``archive.fa`` y las comparten IE1, IE2 e IE3: un código del
  registro no puede usarse como kanji en ningún juego y el registro solo crece por el final;
- :func:`dibujar_trozos` es el bucle de dibujo FONT12 de ``bigramas_ritmo/apply.py``: cada código
  se redibuja con la maqueta de :mod:`ie123kit.nucleo.fuentes.ritmo` y se le ponen sus métricas.

Portear este código no cambia ninguna fuente del proyecto (bloqueo tipográfico, AGENTS.md): trabaja
sobre la copia en memoria que se le pasa. Los tests ``requiere_rom`` prueban que, desde la fuente base
de la capa, se obtiene byte a byte la fuente que la capa dejó en ``extra/``.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ie123kit.nucleo.fuentes import celdas, ritmo

__all__ = [
    "Entrada",
    "Registro",
    "RegistroInvalido",
    "clave_de",
    "dibujar_trozos",
    "sha1_pixeles",
]


class RegistroInvalido(ValueError):
    """El registro de bigramas no cumple sus invariantes (código repetido, reasignado, etc.)."""


def clave_de(e: Mapping[str, Any]) -> str:
    """Clave de casilla de una entrada: ``clave`` (variantes, piezas de menú) o el ``par``."""
    return e.get("clave", e["par"])


def sha1_pixeles(px: Mapping[tuple[int, int], int]) -> str:
    """Huella de un dibujo, la misma que anotan las capas en ``pixeles_sha1``."""
    return hashlib.sha1(json.dumps(sorted(px.items())).encode()).hexdigest()


@dataclass(frozen=True)
class Entrada:
    """Una fila del registro: código Shift-JIS (hex), texto de la casilla y clave."""

    sjis: str
    par: str
    clave: str
    campos: tuple[str, ...] = ()
    fuentes: tuple[str, ...] = ()

    @property
    def codigo(self) -> bytes:
        return bytes.fromhex(self.sjis)

    @property
    def kanji(self) -> str:
        return self.codigo.decode("cp932")

    @property
    def codepoint(self) -> int:
        return ord(self.kanji)


@dataclass
class Registro:
    """Registro de bigramas en memoria (el JSON completo se conserva en ``documento``)."""

    documento: dict[str, Any]
    entradas: list[Entrada] = field(default_factory=list)

    @classmethod
    def desde_documento(cls, documento: Mapping[str, Any]) -> Registro:
        doc = dict(documento)
        entradas = [Entrada(sjis=e["sjis"].upper(), par=e["par"], clave=clave_de(e),
                            campos=tuple(e.get("campos", ())), fuentes=tuple(sorted(e.get("fuentes", {}))))
                    for e in doc.get("bigramas", ())]
        reg = cls(doc, entradas)
        reg.validar()
        return reg

    @classmethod
    def leer(cls, ruta: str | Path) -> Registro:
        return cls.desde_documento(json.loads(Path(ruta).read_text(encoding="utf-8")))

    # -- consultas -----------------------------------------------------

    @property
    def version(self) -> str | None:
        return self.documento.get("version")

    def codigos(self) -> set[str]:
        return {e.sjis for e in self.entradas}

    def por_clave(self) -> dict[str, Entrada]:
        return {e.clave: e for e in self.entradas}

    def por_codigo(self) -> dict[str, Entrada]:
        return {e.sjis: e for e in self.entradas}

    def fuentes_dibujadas(self) -> dict[str, str]:
        return dict(self.documento.get("fuentes_dibujadas", {}))

    # -- invariantes ---------------------------------------------------

    def validar(self) -> None:
        """Códigos únicos, claves únicas y cada código es un doble byte cp932 que vuelve igual."""
        vistos: dict[str, str] = {}
        claves: set[str] = set()
        for e in self.entradas:
            if e.sjis in vistos:
                raise RegistroInvalido(f"código repetido {e.sjis}: {vistos[e.sjis]!r} y {e.clave!r}")
            vistos[e.sjis] = e.clave
            if e.clave in claves:
                raise RegistroInvalido(f"clave repetida {e.clave!r}")
            claves.add(e.clave)
            b = e.codigo
            if len(b) != 2:
                raise RegistroInvalido(f"código de {len(b)} bytes: {e.sjis}")
            try:
                ch = b.decode("cp932")
            except UnicodeDecodeError as exc:
                raise RegistroInvalido(f"código no cp932: {e.sjis}") from exc
            if ch.encode("cp932") != b:
                raise RegistroInvalido(f"código que no vuelve igual en cp932: {e.sjis}")

    def comprobar_sucesor(self, anterior: Registro, liberados: Iterable[str] = ()) -> None:
        """El registro nuevo solo añade: todo código del anterior sigue con su misma clave.

        ``liberados`` son códigos que una capa posterior recuperó a propósito (p. ej. los 13 que la
        v23 de IE2 retiró de la v22): pueden faltar o cambiar de clave. Nada más.
        """
        libres = {c.upper() for c in liberados}
        nuevos = self.por_codigo()
        for e in anterior.entradas:
            if e.sjis in libres:
                continue
            n = nuevos.get(e.sjis)
            if n is None:
                raise RegistroInvalido(f"el sucesor pierde el código {e.sjis} ({e.clave!r})")
            if n.clave != e.clave:
                raise RegistroInvalido(f"el sucesor reasigna {e.sjis}: {e.clave!r} -> {n.clave!r}")

    def anadir(self, clave: str, sjis: str, par: str | None = None, **extra: Any) -> Entrada:
        """Añade una entrada AL FINAL (el registro nunca reasigna un código en uso)."""
        sjis = sjis.upper()
        if sjis in self.codigos():
            raise RegistroInvalido(f"código ya en uso: {sjis}")
        if clave in self.por_clave():
            raise RegistroInvalido(f"clave ya registrada: {clave!r}")
        fila = {"par": par if par is not None else ritmo.texto(clave), "sjis": sjis, **extra}
        if fila["par"] != clave:
            fila["clave"] = clave
        self.documento.setdefault("bigramas", []).append(fila)
        e = Entrada(sjis=sjis, par=fila["par"], clave=clave, campos=tuple(extra.get("campos", ())),
                    fuentes=tuple(sorted(extra.get("fuentes", {}))))
        self.entradas.append(e)
        self.validar()
        return e


def dibujar_trozos(fuente: celdas.FuenteBCFNT, entradas: Iterable[Mapping[str, Any]], mq: ritmo.Maqueta,
                   ) -> list[dict[str, Any]]:
    """Redibuja en ``fuente`` (FONT12) cada entrada con la maqueta de ritmo y le pone sus métricas.

    Es el bucle «dibujo» de la v89: primero se resuelven TODAS las maquetas (las letras nativas no son
    códigos del registro, así que dibujar no las cambia) y después se pinta. Las entradas cuya maqueta
    sea un dibujo fijado (``mq.fijos``, marcado ``medido``) no se tocan. Devuelve, por entrada, lo que
    la capa anota en ``registro.json`` (glifo, cwdh, columna, huella de píxeles).
    """
    p = mq.p
    lista = [dict(e) for e in entradas]
    maquetas = [mq.trozo(clave_de(e)) for e in lista]
    esc = celdas.escritor(fuente)
    salida = []
    for e, m in zip(lista, maquetas):
        clave = clave_de(e)
        if m is None:
            raise ValueError(f"la maqueta no admite la casilla {clave!r}")
        cp = ord(bytes.fromhex(e["sjis"]).decode("cp932"))
        gi = fuente.gi(cp)
        if gi is None:
            raise ValueError(f"el código {e['sjis']} no tiene glifo en la fuente")
        if m.get("medido"):
            salida.append({"sjis": e["sjis"], "glifo": gi, "cwdh": list(fuente.metrics[gi]), "maqueta": "fija"})
            continue
        left, ancho, adv = ritmo.metricas(m, e["par"], p)
        viejo = list(fuente.metrics[gi])
        celdas.pintar(fuente, gi, m["px"], esc)
        fuente.set_metrics(gi, left, ancho, adv)
        if celdas.pixeles(fuente, gi) != m["px"]:
            raise AssertionError(f"el dibujo releído de {clave!r} no coincide")
        if int((p.celda - adv) / 2) + left != m["D"]:
            raise AssertionError(f"colocación de {clave!r} distinta de D")
        salida.append({"sjis": e["sjis"], "glifo": gi, "cwdh_antes": viejo, "cwdh": [left, ancho, adv], "tinta_px": ancho,
                           "columna": m["D"], "solido": [m["S0"], m["S1"]], "hueco_interno": m["g"],
                           "pixeles_sha1": sha1_pixeles(m["px"])})
    return salida
