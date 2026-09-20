"""Entradas de fichero de los motores de IE2 que expone ``ie123 motor … --juego ie2``.

Cada función recibe rutas, escribe solo en ``salida`` (nunca en la entrada ni en capas de
``work/``), se niega a sobrescribir y devuelve un dict serializable para el ``Resultado``. La lógica
está en los módulos de ``ie2.comun`` y en ``nucleo``; aquí solo hay lectura y escritura.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

__all__ = ["ayuda", "cro_ancho_dialogo", "paginar", "subtitulos", "teclado", "voces"]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _escribir(ruta: Path, datos: bytes) -> str:
    if ruta.exists():
        raise FileExistsError(f"ya existe: {ruta}")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(datos)
    return str(ruta)


def paginar(texto: str) -> dict:
    """Reparte un texto con el motor de IE2 (37 × 3, 131 B por página)."""
    from ie123kit.ie2.comun.dialogo import MODELO_IE2
    from ie123kit.nucleo.texto import paginado as P

    repartido = P.repartir(texto, MODELO_IE2)
    paginas = [p.split(P.SALTO) for p in repartido.split(P.PAGINA)]
    return {"juego": "ie2", "max_car": MODELO_IE2.max_car, "lineas": MODELO_IE2.lineas,
            "pagina_max": MODELO_IE2.pagina_max, "texto": repartido, "paginas": paginas}


def teclado(archive: str | os.PathLike, salida: str | os.PathLike) -> dict:
    """``MMName.SPF_``/``MMProfd.SPF_`` del ``archive`` con el teclado latino -> ``salida/<ruta>``."""
    from ie123kit.ie2.comun.teclado import PAQUETES, paquete_latino
    from ie123kit.nucleo.contenedores.fa import FaArchive

    arc = FaArchive(str(archive))
    paquetes, artefactos = {}, []
    for ruta in PAQUETES:
        datos, informe = paquete_latino(arc.read(ruta))
        artefactos.append(_escribir(Path(salida) / ruta, datos))
        paquetes[ruta] = informe
    return {"paquetes": paquetes, "artefactos": artefactos}


def cro_ancho_dialogo(cro: str | os.PathLike, salida: str | os.PathLike) -> dict:
    """``ina_main2.cro`` con el ancho de diálogo a 37 caracteres (parches comprobados)."""
    from ie123kit.ie2.comun.cro import parchear_ancho_dialogo

    datos, informe = parchear_ancho_dialogo(Path(cro).read_bytes())
    informe["artefactos"] = [_escribir(Path(salida), datos)]
    return informe


def voces(sonido_3ds: str | os.PathLike, sonido_nds: str | os.PathLike, bancos: list[str],
          salida: str | os.PathLike, base: str | os.PathLike | None = None) -> dict:
    """``sound.pb``/``.ph``/``.ph_`` con los ``bancos`` rehechos con la voz NDS.

    ``sonido_3ds``: carpeta con ``sound.ph``/``sound.pb`` japoneses; ``sonido_nds``: carpeta con
    ``sound.pkh``/``sound.pkb`` de la NDS española; ``base``: carpeta del ``sound.pb`` sobre el que se
    montan los cambios (por defecto, el japonés).
    """
    from ie123kit.ie2.comun.voces import banco_desde_nds
    from ie123kit.nucleo.contenedores import sound_pb as SP

    d3, dn = Path(sonido_3ds), Path(sonido_nds)
    jp = dict(SP.leer_3ds((d3 / "sound.ph").read_bytes(), (d3 / "sound.pb").read_bytes()))
    es = SP.leer_nds((dn / "sound.pkh").read_bytes(), (dn / "sound.pkb").read_bytes())
    db = Path(base) if base else d3
    entradas = SP.leer_3ds((db / "sound.ph").read_bytes(), (db / "sound.pb").read_bytes())
    nuevos, informe = {}, {}
    for n in bancos:
        nuevos[n + ".SED"], nuevos[n + ".SWD"], informe[n] = banco_desde_nds(
            jp[n + ".SWD"], jp[n + ".SED"], es[n + ".SWD"], es[n + ".SED"])
    pb, ph = SP.montar_3ds(entradas, nuevos)
    s = Path(salida)
    artefactos = [_escribir(s / "sound.pb", pb), _escribir(s / "sound.ph", ph), _escribir(s / "sound.ph_", ph)]
    return {"bancos": informe, "sha256": {"sound.pb": _sha(pb), "sound.ph": _sha(ph)}, "artefactos": artefactos}


def subtitulos(dat: str | os.PathLike, fotogramas: int | None = None) -> dict:
    """Pista española de un ``.dat`` NDS ya partida (y, con ``fotogramas``, cuántos llevan texto)."""
    from ie123kit.ie2.comun import subtitulos as IS
    from ie123kit.nucleo.media import subtitulos as S

    pistas = IS.pistas(Path(dat).read_bytes())
    datos = {"subtitulos": pistas}
    if fotogramas is not None:
        idx = S.por_fotograma(pistas, fotogramas, IS.FPS, IS.HZ)
        datos["fotogramas_con_texto"] = int((idx >= 0).sum())
    return datos


def ayuda(archive: str | os.PathLike, capturas_nds: str | os.PathLike, salida: str | os.PathLike,
          rutas: list[str] | None = None) -> dict:
    """Capturas de ayuda de IE2 con las zonas traducidas de la NDS -> ``salida/<ruta>``.

    ``archive``: ``archive.fa`` japonés; ``capturas_nds``: carpeta ``pic3d/script/sp`` de la NDS
    española (``tt*.pac_``, ``syup_bg*.pac_``); ``rutas``: solo esos ``.arc`` (por defecto, todos).
    Las pestañas de ``a_menu/system_b.arc`` no entran aquí: necesitan el motor de rótulos de menús,
    que se le pasa a :func:`ie123kit.ie2.comun.ayuda.pestanas_arc`.
    """
    from ie123kit.ie2.comun import ayuda as AY
    from ie123kit.nucleo.contenedores.fa import FaArchive

    arc = FaArchive(str(archive))
    nds = Path(capturas_nds)
    todas = AY.capturas(p for p, _o, _n in arc.entries if p.startswith(AY.AR))
    pedidas = set(rutas) if rutas else None
    informes, artefactos, pendientes = {}, [], []
    for ruta, nombre in todas:
        if pedidas is not None and ruta not in pedidas:
            continue
        fuente = nds / f"{nombre}.pac_"
        if not fuente.is_file():
            pendientes.append({"tipo": "sin_captura_nds", "arc": ruta})
            continue
        datos, informe = AY.captura_arc(arc.read(ruta), fuente.read_bytes(), nombre)
        informe["sha256"] = _sha(datos)
        informes[ruta] = informe
        artefactos.append(_escribir(Path(salida) / ruta, datos))
    return {"capturas": informes, "pendientes": pendientes, "artefactos": artefactos}
