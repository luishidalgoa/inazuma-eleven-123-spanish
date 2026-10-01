"""Prepara una copia de un SMDH con el título del slot español cambiado.

No modifica el icono original. El SMDH conserva 12 slots de idioma de 0x200
bytes; el español ocupa el slot 5.
"""
from pathlib import Path

SMDH_MAGIC = b"SMDH"
TITLE_TABLE_OFFSET = 0x08
TITLE_SLOT_SIZE = 0x200
SPANISH_SLOT = 5


def patch_title(source: Path, output: Path, title: str, slot: int = SPANISH_SLOT) -> None:
    data = bytearray(source.read_bytes())
    if data[:4] != SMDH_MAGIC:
        raise ValueError(f"no es un SMDH: {source}")
    if not 0 <= slot < 12:
        raise ValueError("el slot de idioma debe estar entre 0 y 11")
    encoded = (title + "\0").encode("utf-16le")
    if len(encoded) > TITLE_SLOT_SIZE:
        raise ValueError("el título excede el tamaño del slot SMDH")
    start = TITLE_TABLE_OFFSET + slot * TITLE_SLOT_SIZE
    end = start + TITLE_SLOT_SIZE
    if end > len(data):
        raise ValueError("el SMDH no contiene la tabla completa de títulos")
    data[start:end] = encoded + bytes(TITLE_SLOT_SIZE - len(encoded))
    if output.resolve() == source.resolve():
        raise ValueError("la salida no puede sobrescribir el SMDH original")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)


#: Campos de título de cada slot (offset dentro del slot, tamaño en bytes UTF-16LE).
CAMPOS_TITULO = {"short": (0x000, 0x80), "long": (0x080, 0x100), "publisher": (0x180, 0x80)}
SLOTS = 16


def leer_titulos(data: bytes, slot: int) -> dict[str, str]:
    """Títulos ``short``/``long``/``publisher`` de un slot de idioma."""
    if data[:4] != SMDH_MAGIC:
        raise ValueError("no es un SMDH")
    base = TITLE_TABLE_OFFSET + slot * TITLE_SLOT_SIZE
    out = {}
    for campo, (o, n) in CAMPOS_TITULO.items():
        crudo = data[base + o:base + o + n].decode("utf-16le")
        out[campo] = crudo.split("\0", 1)[0]
    return out


def escribir_titulos(data: bytes, titulos: dict[str, str], slots=range(SLOTS)) -> bytes:
    """Copia del SMDH con ``titulos`` en los slots pedidos (todos por defecto); el icono no cambia.

    Portado de ``build_icon`` de ``work/shared/capas/graficos/banner_home/apply.py`` (F2.5, #51).
    """
    if data[:4] != SMDH_MAGIC:
        raise ValueError("no es un SMDH")
    d = bytearray(data)
    for slot in slots:
        for campo, (o, n) in CAMPOS_TITULO.items():
            if campo not in titulos:
                continue
            enc = titulos[campo].encode("utf-16le")
            if len(enc) + 2 > n:
                raise ValueError(f"{campo}: {len(enc) // 2} unidades > {n // 2 - 1}")
            b = TITLE_TABLE_OFFSET + slot * TITLE_SLOT_SIZE + o
            d[b:b + n] = enc + bytes(n - len(enc))
    return bytes(d)
