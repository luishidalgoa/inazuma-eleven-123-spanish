"""Codificación Latin propia del NDS europeo en castellano (Inazuma Eleven DS).

Hay DOS tablas distintas y NO se unifican (cada una conserva la semántica exacta de
la herramienta de la que procede):

- ``NDS_DEC`` (glosario, antes ``build_glossary.NDS_DEC``): incluye ``0xB5 = 'ä'``.
  La usan ``dec_es`` (nombres de .dat/.STR) y ``decode_cadena`` en modo ``'nds'``.
- ``DS_TABLE`` (diálogo oficial DS, antes ``ds_official.DS_TABLE``): NO tiene 0xB5,
  así que ese byte sale como ``'?'``. En el resto coincide con ``NDS_DEC``
  (``0xD9 = 'É'``, ``0xA6 = 'Í'``).

Sin E/S: solo tablas y funciones puras.
"""

# Codificacion Latin propia del NDS ES (inferida por contexto; ampliable)
# Same table as the old tools/ds_official.py (now ie123kit._legado.ds_official) (verified on official sentences):
# 0xD9 is É ("Épsilon"), not Í.
NDS_DEC = {0xB2: "á", 0xBA: "é", 0xBE: "í", 0xC4: "ó", 0xCA: "ú",
           0xC2: "ñ", 0xCC: "ü", 0xB5: "ä", 0xA5: "¿", 0xDF: "¡",
           0xD1: "Á", 0xD9: "É", 0xA6: "Í", 0xAB: "Ó", 0xA2: "Ú", 0xA9: "Ñ"}
# Shift-JIS pairs embedded in the Spanish text (typographic quotes).
NDS_SJIS = {b"\x81\x67": '"', b"\x81\x68": '"'}


def dec_es(b):
    out = []
    i = 0
    while i < len(b):
        c = b[i]
        if c == 0:
            break
        if b[i:i + 2] in NDS_SJIS:
            out.append(NDS_SJIS[b[i:i + 2]])
            i += 2
            continue
        if c in (0x0A, 0x0D):      # salto de linea -> espacio
            out.append(" ")
        elif c == 0x7E:            # '~' se usa como ordinal: n.~2 -> n.º2
            out.append("º")
        elif 0x20 <= c < 0x7F:
            out.append(chr(c))
        elif c in NDS_DEC:
            out.append(NDS_DEC[c])
        else:
            out.append("?")
        i += 1
    return " ".join("".join(out).split()).strip()


def dec_jp(b):
    return b.split(b"\x00")[0].decode("shift-jis", "replace").strip()


def decode_cadena(part, enc):
    """Decodifica una cadena (entre NUL) ya descomprimida, limpiando controles."""
    if enc == "sjis":
        s = part.decode("shift-jis", "replace")
        # quitar controles sueltos (<0x20) salvo nada; conservar texto, %codes, \n literal
        s = "".join(c for c in s if ord(c) >= 0x20 or c == "\n")
        return s.strip()
    out = []
    for c in part:
        if c == 0x0A:
            out.append(" ")
        elif 0x20 <= c < 0x7F:
            out.append(chr(c))
        elif c in NDS_DEC:
            out.append(NDS_DEC[c])
    return " ".join("".join(out).split()).strip()


# Tabla de codificacion del DS espanol -> Unicode (bytes >=0x80). Inferida del contexto
# (cada byte verificado en frases reales del DS, minus/mayus distintas).
DS_TABLE = {
    # minusculas acentuadas
    0xB2: "á", 0xBA: "é", 0xBE: "í", 0xC4: "ó", 0xCA: "ú", 0xC2: "ñ", 0xCC: "ü",
    # mayusculas acentuadas
    0xD1: "Á", 0xD9: "É", 0xA6: "Í", 0xAB: "Ó", 0xA2: "Ú", 0xA9: "Ñ",
    # signos de apertura
    0xDF: "¡", 0xA5: "¿",
}


def decode_ds(b, unmapped=None):
    out = []
    for c in b:
        if c < 0x80:
            out.append(chr(c))
        elif c in DS_TABLE:
            out.append(DS_TABLE[c])
        else:
            if unmapped is not None:
                unmapped[c] = unmapped.get(c, 0) + 1
            out.append("?")
    return "".join(out)
