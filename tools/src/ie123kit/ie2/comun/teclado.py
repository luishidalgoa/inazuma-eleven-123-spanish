"""Teclado de nombre de IE2: tablas FCODE dentro de los paquetes ``SPF_`` del menú.

Porteo de ``work/ie2/shared/capas/teclado/teclado/apply.py`` (issue #77). El juego no lee
``fcode*.txt`` sueltos: ``CMainMenuScreenEnterName`` (ina_main2.cro, array de recursos en
0x221abc, recorrido 0x16395c, búsqueda 0xfacfc -> 0x2020c4) los busca como entradas internas de
``/data_iz/pic2d/menu/MMName.SPF_``; la pantalla de perfil (0x226004) usa ``MMProfd.SPF_``.

Se sustituyen FCODE0/1/2.TXT por la tabla latina (``nucleo.texto.teclado``) y se recomprime en LZ10.
DAKUTEN, HANDAKU, NGWORD y FCODECK quedan intactos; la tabla de nombres no cambia.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

from ie123kit.nucleo.contenedores import spf
from ie123kit.nucleo.texto.teclado import FILAS_LATINAS, parchear_fcode

__all__ = ["MODOS", "PAQUETES", "paquete_latino"]

#: Paquetes del menú de IE2 (rutas de archive.fa) que llevan las tablas del teclado.
PAQUETES = ("inazuma2/data_iz/pic2d/menu/MMName.SPF_", "inazuma2/data_iz/pic2d/menu/MMProfd.SPF_")

#: Entrada FCODE -> modo del teclado (0 mayúsculas, 1 minúsculas, 2 símbolos).
MODOS = {"FCODE0.TXT": 0, "FCODE1.TXT": 1, "FCODE2.TXT": 2}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def paquete_latino(comprimido: bytes, filas: Sequence[str] = FILAS_LATINAS,
                   original: Callable[[str], bytes] | None = None) -> tuple[bytes, dict]:
    """``.SPF_`` japonés (LZ10) -> ``(.SPF_ con el teclado latino en LZ10, informe)``.

    ``original(nombre)`` devuelve la tabla japonesa de referencia de cada FCODE; si se da, se
    exige que la entrada del paquete siga siéndolo (evita parchear dos veces).
    """
    plano = spf.descomprimir(comprimido)
    tabla = spf.entradas(plano)
    cambios, informe = {}, {}
    for nombre, modo in MODOS.items():
        viejo = spf.leer(plano, nombre)
        if original is not None and viejo != original(nombre):
            raise ValueError(f"{nombre} ya no es la tabla japonesa")
        nuevo = parchear_fcode(viejo, modo, filas)
        cambios[nombre] = nuevo
        informe[nombre] = {"offset": hex(tabla[nombre].offset), "bytes": len(nuevo), "modo": modo,
                           "sha256_antes": _sha(viejo), "sha256_despues": _sha(nuevo)}
    nuevo_plano = spf.sustituir(plano, cambios)
    salida = spf.empaquetar(nuevo_plano)
    return salida, {"bytes_antes": len(comprimido), "bytes_despues": len(salida), "sha256": _sha(salida),
                    "descomprimido": len(nuevo_plano), "entradas": informe,
                    "intactas": sorted(set(tabla) - set(MODOS))}
