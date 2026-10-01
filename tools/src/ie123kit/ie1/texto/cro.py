"""Parches de código de ``ina_main1.cro`` (IE1): ancho de la ventana de diálogo.

Porteo de la tabla que vivía en ``work/ie1/capas/dialogo/motor_unificado/comun94.py`` (F2.6, #55).
Es el mismo código del IE2, desplazado, así que el motor genérico y las comprobaciones son los de
``ie123kit.nucleo.ejecutable.parches_cro`` y la tabla del IE2 está en ``ie123kit.ie2.comun.cro``:

===========================================  ===========================================
IE2 (``ina_main2.cro``)                      IE1 (``ina_main1.cro``)
===========================================  ===========================================
0x66a24 ``mov r1,#0xF0`` (manejador 0x301a)  0x5cb8c ``mov r1,#0xF0``
0x4cabc ``mov r2,#0xF0`` (por defecto)       0x465c0 ``mov r2,#0xF0`` (``strh [ventana+0x1316]``)
0x4d6a0 ``mov r2,#0x120`` (dibujo, global)   0x470cc ``mov r2,#0x120`` (``str [base+0xeef60]``)
===========================================  ===========================================

El búfer de página de la pila es igual en los dos (sp+0x40..0xc3 -> 132 B, tope de 131 B), y el
reajuste de IE1 (0x424f4, ``[ventana+0x1316] + 0x20``) es el mismo algoritmo, de modo que con la CRO
parcheada IE1 usa el mismo modelo de 37 × 3 y 131 B: :data:`ie123kit.ie1.texto.dialogo.MODELO_IE1_ANCHO`.

Las líneas por página (``mov r2,#3`` en 0x5cb90 y ``mov r1,#3`` en 0x465cc) no se tocan. Ver
``docs/FURIGANA_LECCIONES.md``.
"""

from __future__ import annotations

from ie123kit.nucleo.ejecutable import parches_cro as PC

__all__ = ["CONTEXTO_ANCHO_DIALOGO", "PARCHES_ANCHO_DIALOGO", "parchear_ancho_dialogo"]

PARCHES_ANCHO_DIALOGO = (
    PC.ParchePalabra(0x5CB8C, 0xE3A010F0, 0xE3A01E1A, "0x301a: mov r1,#0xF0 -> mov r1,#0x1A0"),
    PC.ParchePalabra(0x465C0, 0xE3A020F0, 0xE3A02E1A, "por defecto: mov r2,#0xF0 -> mov r2,#0x1A0"),
    PC.ParchePalabra(0x470CC, 0xE3A02E12, 0xE3A02D07,
                     "dibujo de página: mov r2,#0x120 -> mov r2,#0x1C0 (global +0xeef60)"),
)

CONTEXTO_ANCHO_DIALOGO = (
    PC.Contexto(0x5CB90, 0xE3A02003, "mov r2,#3 (líneas, 0x301a)"),
    PC.Contexto(0x465CC, 0xE3A01003, "mov r1,#3 (líneas por defecto)"),
    PC.Contexto(0x47128, 0xE3A02C01, "mov r2,#0x100 (argumento de ancho, anulado por el global)"),
    PC.Contexto(0x47120, 0xE3A00040, "mov r0,#0x40 (alto de la rejilla)"),
    PC.Contexto(0x4705C, 0xE28D0040, "add r0,sp,#0x40 (búfer de página)"),
    PC.Contexto(0x470AC, 0xE28D30C4, "add r3,sp,#0xc4 (lo siguiente al búfer)"),
)


def parchear_ancho_dialogo(cro: bytes) -> tuple[bytes, dict]:
    """``ina_main1.cro`` -> ``(CRO con el diálogo a 37 × 3, informe)``."""
    return PC.aplicar(cro, PARCHES_ANCHO_DIALOGO, CONTEXTO_ANCHO_DIALOGO)
