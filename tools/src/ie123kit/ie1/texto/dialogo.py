"""Límites del ajuste automático de la ventana de diálogo de IE1 (ina_main1.cro).

Evidencia (capa ``historial/dialogo/v84_saltos_dialogo_total``, ``comun82.py``): 0x424f4 ajusta con
``[ventana+0x1316] + 0x20`` = 0xF0 + 32 = 272 y avance fijo de 12 px (FontGetCharWidth de FONT12,
code.bin 0x164660) -> 22 caracteres por línea; ``[+0x1318]`` = 3 líneas (0x465cc). No hay tope de
bytes por página (búferes de 0x200 B de entrada y 0x3B0 B de salida). El motor genérico está en
``ie123kit.nucleo.texto.paginado``.
"""

from __future__ import annotations

from ie123kit.nucleo.texto.paginado import ModeloMotor

__all__ = ["MODELO_IE1", "MODELO_IE1_ANCHO", "paginar"]

#: Motor del diálogo de IE1 sin parchear: 22 × 3, sin rejilla de dibujo ni tope de página.
MODELO_IE1 = ModeloMotor(ancho_ventana=0xF0)

#: Motor del diálogo de IE1 con la CRO parcheada por ``ie123kit.ie1.texto.cro``: 37 × 3 y 131 B por
#: página, como el IE2. El código de IE1 es el del IE2 desplazado (mismo reajuste en 0x424f4 y mismo
#: búfer de página sp+0x40..0xc3 -> 132 B, tope 131 B), así que el modelo medido para el IE2 vale tal
#: cual. Lo usa la capa ``ie1/capas/dialogo/motor_unificado`` (v94).
MODELO_IE1_ANCHO = ModeloMotor(ancho_ventana=0x1A0, ancho_dibujo=0x1C0, pagina_max=131, registro_max=247)


def paginar(texto: str) -> dict:
    """Reparte un texto con el motor de IE1 (22 × 3, sin tope de página)."""
    from ie123kit.nucleo.texto import paginado as P

    repartido = P.repartir(texto, MODELO_IE1)
    return {"juego": "ie1", "max_car": MODELO_IE1.max_car, "lineas": MODELO_IE1.lineas, "pagina_max": None,
            "texto": repartido, "paginas": [p.split(P.SALTO) for p in repartido.split(P.PAGINA)]}
