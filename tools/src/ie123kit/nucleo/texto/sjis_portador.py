"""Codificación SJIS con portadores griegos del diálogo (copia literal desde tools/reinsert.py).

Portadores griegos: cada acento o signo del español (á, é, ñ, ¿, ¡…) se sustituye por
un carácter griego «portador» (``chr(cp)`` de ``font_patch.PLAN``) cuyo glifo está
parcheado en la fuente con el acento. ``es_encode`` emite el portador en Shift-JIS; el
motor lo reconvierte a Unicode y pinta el glifo parcheado. ``es_encode`` TRUNCA al
presupuesto sin partir multibyte (no es ``encode_fullwidth``: no se unifican).

``_advance`` lee los anchos de ``work/fa_extract/font/FONT12.bcfnt`` la primera vez que
se llama (``_ADV`` es perezoso y mutable). Importar este módulo carga ``font_patch``
(bloqueado v20) pero no escribe nada.
"""
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.fuentes.glifos import PLAN as _PLAN

# Acentos/signos del espanol -> caracter PORTADOR griego (su glifo se sustituye en la
# fuente por el acento, ver font_patch.PLAN). DERIVADO de PLAN: el portador es chr(cp), el
# caracter griego del codepoint UNICODE que pinta font_patch. es_encode lo emite en SJIS;
# el motor lo reconvierte a Unicode y busca ese glifo (parcheado) -> sale el acento.
_acc = {ch: chr(cp) for ch, _b, _t, cp in _PLAN}
_acc["È"] = chr(0x03A0)  # libre en registros de texto JP; raster IE3 en tipografia.py
_acc.update({"ª": "a", "º": "o", "“": '"', "”": '"', "—": "-", "…": "..."})
GREEK = str.maketrans(_acc)

FONTS = ["font/FONT12T.bcfnt", "font/FONT12.bcfnt", "font/FONT8.bcfnt"]


def es_encode(s, budget):
    """Codifica el ES (acentos->griego->SJIS) sin partir multibyte ni pasar budget."""
    out = b""
    for ch in s.translate(GREEK):
        b = ch.encode("shift-jis", "replace")
        if len(out) + len(b) > budget:
            break
        out += b
    return out


# --- Reflow (ajuste de linea por PALABRAS) ---------------------------------
# El motor 3DS corta el texto por ancho de pixel SIN respetar palabras (estilo japones,
# sin espacios). Los saltos \n del DS oficial son mas anchos que la caja del 3DS (~140px),
# asi que el motor re-corta a mitad de palabra ("vamo|s"). Solucion: re-ajustar el ES a la
# anchura de caja cortando solo entre palabras. Ancho de caja conservador (caja principal).
# The dialogue window has 208 usable pixels at native resolution.  The former
# 132-pixel limit left Spanish lines in the middle of the box and caused
# unnatural early breaks.
BOX_W = 208
_BASE = {acc: base for acc, base, _t, _cp in _PLAN}     # á->a, ¿->?, ... (anchura del base)
_BASE["È"] = "E"
_ADV = None


def _advance(ch):
    """Ancho de avance (px) del caracter en la fuente del dialogo (FONT12). Los acentos
    usan el ancho de su letra base (copy_width los iguala)."""
    global _ADV
    if _ADV is None:
        from ie123kit.nucleo.fuentes.glifos import Font
        f = Font(str(find_root() / "work" / "fa_extract" / "font" / "FONT12.bcfnt"))
        _ADV = {}
        for cp, gi in f.cmap.items():
            o = f.cwdh_entry_off(gi)
            if o is not None:
                _ADV[cp] = f.data[o + 2]
    base = _BASE.get(ch, ch)
    advance = _ADV.get(ord(base), 8)
    # v16 gives Latin glyphs the same one-pixel breathing room as the patched
    # BCFNT CWDH metrics.  Spaces retain their original advance.
    if base.isascii() and base.isalpha():
        advance += 1
    return advance


avance = _advance
