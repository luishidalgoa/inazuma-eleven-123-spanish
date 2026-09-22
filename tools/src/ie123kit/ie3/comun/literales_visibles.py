"""Submenús completos por GetString oficial, compactados en sus rangos originales.

ADR son referencias de datos, no geometría. Ordenación usa Cro.retarget.
No amplía CRO, no usa caves, no modifica fuentes ni el codificador.
"""
import hashlib
import struct

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas
from ie123kit.ie3.comun.nombres import _encode_target
from ie123kit.ie3.comun.text import TextTable
from ie123kit.ie3.comun.ui_literales import _leer_id, extraer_fuente_programa
from ie123kit.nucleo.ejecutable.cro import Cro
from ie123kit.nucleo.registros.rangos import assert_only_changed

RANGOS = {
    (0x16621C, 0x166288): "387c10269b6463d4314606055dc395fd56ee1583b00d5e11359ebe702cc92fe4",
    (0x1662A0, 0x1662FC): "d616392f2d5713a1da6d73a2a5ebf40b39d9eea7432728eef9c9020b5b8c8753",
    (0x16628C, 0x166298): "fffd50e3f831ff31854963be818d429c385dad84a4d50fed2972b2b88784ffa6",
    (0x2A0A4C, 0x2A0AA4): "a34bc2f6ea73f38274a096a793bc01f249d722a87a4c4cfd578c3fbaeb6ee587",
    (0x2A0AA4, 0x2A0AE8): "bd206fda29738d68b10647f0fedb8c03d6ecba81ee187afc5d92daeae9b0eb8a",
    (0x2CD6A6, 0x2CD6D5): "953a58548b696683b8b2e1b1c0f30ba3d15452aba3e0c6c69cef61bdfe3fc5cb",
}
# (old pointer, ADR, GetString IDs/count). Strategy is assembled by EU calls.
GRUPOS = (
    (0x16621C, 0x166288, ((0x16621C, 0x165F38, ((440, 1),)),
                         (0x166228, 0x165F54, ((441, 3),)),
                         (0x166248, 0x165FA4, ((442, 1),)),
                         (0x166254, 0x165FC0, ((794, 1), (105, 1), (385, 1), (386, 1), (387, 1))))),
    (0x1662A0, 0x1662FC, ((0x1662A0, 0x166140, ((449, 1),)),
                         (0x1662AC, 0x16615C, ((450, 3),)),
                         (0x1662C4, 0x1661CC, ((447, 1),)),
                         (0x1662D0, 0x1661E8, ((448, 4),)))),
)
FIJOS = ((0x16628C, 0x166298, 444, 1), (0x2A0A4C, 0x2A0AA4, 445, 8),
         (0x2A0AA4, 0x2A0AE8, 446, 6))
# One unrelated jersey string is moved verbatim alongside the four sort labels.
ORDEN = ((0x2CD6A6, 0x2B2890, 161), (0x2CD6B3, 0x2B2894, 162),
         (0x2CD6BA, 0x2B27BC, None), (0x2CD6C3, 0x2B288C, 160),
         (0x2CD6CA, 0x2B2898, 163))


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def _adr_target(word, pc):
    kind = word & 0x0FEF0000
    if kind not in (0x028F0000, 0x024F0000):
        raise ValueError("instrucción no es ADR")
    return pc + 8 + (1 if kind == 0x028F0000 else -1) * Cro._rotimm(word)


def _adr_retarget(word, pc, target):
    _adr_target(word, pc)
    delta = target - pc - 8
    absolute = abs(delta)
    for rotation in range(16):
        for immediate in range(256):
            operand = rotation * 256 + immediate
            if Cro._rotimm(operand) == absolute:
                # Preserve condition/register, replace ADD/SUB and immediate only.
                return (word & 0xFE1FF000) | (0x02800000 if delta >= 0 else 0x02400000) | operand
    raise ValueError("nueva referencia no representable como ADR ARM")


def _codificar(texts):
    output = b""
    for text in texts:
        encoded = _encode_target(text)
        if not text or "\0" in text or encoded is None:
            raise ValueError("literal oficial vacío/no codificable")
        output += encoded + b"\0"
    return output


def _pack(parts, capacity, alignment=4):
    output, offsets = b"", []
    for payload in parts:
        output += bytes((-len(output)) % alignment)
        offsets.append(len(output))
        output += payload
    if len(output) > capacity:
        raise ValueError("grupo completo no cabe sin ampliar segmento")
    return output.ljust(capacity, b"\0"), offsets


def _referencias_actuales(cro):
    view = Cro(cro)
    segment = view.segments[0]
    found = {}
    for pc in range(segment.offset, segment.offset + segment.size - 3, 4):
        word = _u32(cro, pc)
        if word & 0x0FEF0000 not in (0x028F0000, 0x024F0000):
            continue
        target = _adr_target(word, pc)
        if any(start <= target < end for start, end in RANGOS):
            found[pc] = target
    expected = {adr: old for _, _, fields in GRUPOS for old, adr, _ in fields}
    expected[0x166028] = 0x16628C
    if found != expected:
        raise ValueError("referencias ADR interiores distintas del conjunto auditado")
    incoming = {r.target: r.value for r in view.relocations
                if any(start <= r.value < end for start, end in RANGOS)}
    wanted = {slot: old for old, slot, _ in ORDEN}
    wanted.update({0x166298: 0x2A0A4C, 0x16629C: 0x2A0AA4})
    if incoming != wanted:
        raise ValueError("referencias reubicadas interiores distintas del conjunto auditado")
    touched = direcciones_de_tablas(cro)
    if any(start < pos + 4 and pos < end for start, end in RANGOS for pos in touched):
        raise ValueError("datos literales invaden destinos de relocación")
    return view


def parchear_submenus(cro_actual, codigo_es, crs_es, cro_es, codetable_es):
    """Devuelve CRO+informe; fuente Spark/Ogre verificadas por cadena GetString."""
    _, source_proof = extraer_fuente_programa(codigo_es, crs_es, cro_es, codetable_es)
    table = TextTable.from_codetable(codetable_es)
    view = _referencias_actuales(cro_actual)
    for (start, end), digest in RANGOS.items():
        if hashlib.sha256(cro_actual[start:end]).hexdigest() != digest:
            raise ValueError(f"grupo literal original inesperado {start:#x}")
    # EU consumer identities: fixed source hashes also cover complete callers.
    if Cro(cro_es).imports().get(0x1190) != "_ZN2iz4util15GetLanguageCodeEv":
        raise ValueError("selector regional de Estrategias distinto")
    for offset, ident in {0x173B18: 441, 0x173B1C: 442, 0x173B20: 385,
                          0x173B28: 445, 0x173B2C: 446, 0x173B30: 449,
                          0x173B34: 450, 0x173B38: 447}.items():
        if _u32(cro_es, offset) != ident:
            raise ValueError("identidad de fuente GetString de submenú distinta")
    def source(ids):
        return tuple(text for ident, count in ids for text in _leer_id(codigo_es, table, ident, count))
    allowed = list(RANGOS)
    records, readback = [], []
    for start, end, fields in GRUPOS:
        texts = [source(ids) for _, _, ids in fields]
        parts = [_codificar(group) for group in texts]
        if any(len(parts[i]) > 15 for i in (0, 2)):
            raise ValueError("título excede copia15 del consumidor")
        data, offsets = _pack(parts, end-start)
        view.datos[start:end] = data
        for (old, adr, ids), delta, group, payload in zip(fields, offsets, texts, parts, strict=True):
            target = start + delta
            word = _adr_retarget(_u32(cro_actual, adr), adr, target)
            struct.pack_into("<I", view.datos, adr, word)
            allowed.append((adr, adr+4))
            readback.append((target, payload))
            records.append({"source_ids": ids, "official": group, "old": old, "new": target,
                            "reference": adr, "kind": "adr"})
    for start, end, ident, count in FIJOS:
        texts = source(((ident, count),))
        data = _codificar(texts)
        padded, _ = _pack([data], end-start)
        view.datos[start:end] = padded
        readback.append((start, data))
        records.append({"source_ids": ((ident, count),), "official": texts,
                        "old": start, "new": start, "kind": "fixed"})
    texts, parts = [], []
    for old, _, ident in ORDEN:
        if ident is None:
            end = cro_actual.index(0, old)
            parts.append(cro_actual[old:end+1])
            texts.append(None)
        else:
            words = source(((ident, 1),))
            parts.append(_codificar(words))
            texts.append(words)
    data, offsets = _pack(parts, 0x2CD6D5-0x2CD6A6, alignment=1)
    view.datos[0x2CD6A6:0x2CD6D5] = data
    for (old, slot, ident), offset, words, payload in zip(ORDEN, offsets, texts, parts, strict=True):
        target = 0x2CD6A6 + offset
        relocation = view.retarget(slot, target, expect_old=old)
        allowed.append((relocation.record_offset, relocation.record_offset+12))
        readback.append((target, payload))
        records.append({"source_ids": ((ident, 1),) if ident is not None else (),
                        "official": words, "old": old, "new": target,
                        "reference": slot, "kind": "relocation",
                        "unrelated_japanese_preserved": ident is None})
    result = view.to_bytes()
    for start, payload in readback:
        if result[start:start+len(payload)] != payload:
            raise AssertionError("reextracción de literal no coincide")
    for row in records:
        if row["kind"] == "adr" and _adr_target(_u32(result, row["reference"]), row["reference"]) != row["new"]:
            raise AssertionError("ADR final no resuelve literal")
        if row["kind"] == "relocation":
            actual = [r.value for r in Cro(result).relocations if r.target == row["reference"]]
            if actual != [row["new"]]:
                raise AssertionError("relocación final no resuelve literal")
    changed = assert_only_changed(cro_actual, result, allowed)
    return result, {"source_proof": source_proof, "records": records,
                    "labels": sum(len(r["official"] or ()) for r in records),
                    "changed_ranges": changed, "size_preserved": True,
                    "official_text_readback_exact": True, "runtime_verified": False,
                    "regional_variant": "JPストーリー→EU ID794 Historia; EUlanguage3 alternative104 not imported",
                    "unrelated_jersey_label_preserved": True}
