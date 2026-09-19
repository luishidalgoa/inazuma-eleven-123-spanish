"""Límites del ajuste automático de la ventana de diálogo de IE1 (ina_main1.cro).

Evidencia (capa ``historial/dialogo/v84_saltos_dialogo_total``, ``comun82.py``): 0x424f4 ajusta con
``[ventana+0x1316] + 0x20`` = 0xF0 + 32 = 272 y avance fijo de 12 px (FontGetCharWidth de FONT12,
code.bin 0x164660) -> 22 caracteres por línea; ``[+0x1318]`` = 3 líneas (0x465cc). No hay tope de
bytes por página (búferes de 0x200 B de entrada y 0x3B0 B de salida). El motor genérico está en
``ie123kit.nucleo.texto.paginado``.
"""

from __future__ import annotations

from ie123kit.nucleo.texto.paginado import ModeloMotor

__all__ = ["MODELO_IE1", "paginar"]

#: Motor del diálogo de IE1: 22 × 3, sin rejilla de dibujo ni tope de página.
MODELO_IE1 = ModeloMotor(ancho_ventana=0xF0)


def paginar(texto: str) -> dict:
    """Reparte un texto con el motor de IE1 (22 × 3, sin tope de página)."""
    from ie123kit.nucleo.texto import paginado as P

    repartido = P.repartir(texto, MODELO_IE1)
    return {"juego": "ie1", "max_car": MODELO_IE1.max_car, "lineas": MODELO_IE1.lineas, "pagina_max": None,
            "texto": repartido, "paginas": [p.split(P.SALTO) for p in repartido.split(P.PAGINA)]}
