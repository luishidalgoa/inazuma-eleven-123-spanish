"""Parches de código de ``ina_main2.cro`` (IE2), autorizados por el usuario (capa ``menus_cro/ancho_dialogo``).

Ancho del diálogo 0xF0 -> 0x1A0 (22 -> 37 caracteres por línea), solo inmediatos:

- 0x66a24 ``mov r1,#0xF0 -> #0x1A0``: manejador 0x301a (0x66884), ancho que pasa a 0xf59dc en cada
  diálogo; 0xf5a5c ``strhne`` -> ``[ventana+0x131e]``;
- 0x4cabc ``mov r2,#0xF0 -> #0x1A0``: valores por defecto de la ventana (0x4cac4 ``strh``);
- 0x4d6a0 ``mov r2,#0x120 -> #0x1C0``: ancho de la rejilla de dibujo de la página (global
  ``[base+0xeef60]`` que 0x121a78 usa en vez de su argumento 0x100; corte si ``x + 12 > ancho``).

Las líneas por página (``mov r2,#3`` en 0x66a28 y ``mov r1,#3`` en 0x4cac8) no se tocan. Ver
``docs/FURIGANA_LECCIONES.md`` (límites del ancho de diálogo del IE2 y tope de 131 B por página).
"""

from __future__ import annotations

from ie123kit.nucleo.ejecutable import parches_cro as PC

__all__ = ["CONTEXTO_ANCHO_DIALOGO", "PARCHES_ANCHO_DIALOGO", "parchear_ancho_dialogo"]

PARCHES_ANCHO_DIALOGO = (
    PC.ParchePalabra(0x66A24, 0xE3A010F0, 0xE3A01E1A, "0x301a: mov r1,#0xF0 -> mov r1,#0x1A0"),
    PC.ParchePalabra(0x4CABC, 0xE3A020F0, 0xE3A02E1A, "por defecto: mov r2,#0xF0 -> mov r2,#0x1A0"),
    PC.ParchePalabra(0x4D6A0, 0xE3A02E12, 0xE3A02D07,
                     "dibujo de página: mov r2,#0x120 -> mov r2,#0x1C0 (global +0xeef60)"),
)

CONTEXTO_ANCHO_DIALOGO = (
    PC.Contexto(0x66A28, 0xE3A02003, "mov r2,#3 (líneas)"),
    PC.Contexto(0x66A34, None, "stm ip,{r1,r2}"),
    PC.Contexto(0x4CAC4, None, "strh r2,[r0,#0x1e]"),
    PC.Contexto(0x4CAC8, 0xE3A01003, "mov r1,#3 (líneas)"),
    PC.Contexto(0x4D6FC, 0xE3A02C01, "mov r2,#0x100 (argumento de ancho, anulado por el global)"),
    PC.Contexto(0x4D6F4, 0xE3A00040, "mov r0,#0x40 (alto de la rejilla)"),
)


def parchear_ancho_dialogo(cro: bytes) -> tuple[bytes, dict]:
    """``ina_main2.cro`` -> ``(CRO con el diálogo a 37 × 3, informe)``."""
    return PC.aplicar(cro, PARCHES_ANCHO_DIALOGO, CONTEXTO_ANCHO_DIALOGO)
