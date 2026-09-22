"""nucleo.eventos.packnum: índice PackNum sintético y equivalencia del LZ10 antiguo."""
import struct

import pytest

from ie123kit.nucleo.compresion import lz10
from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.eventos import packnum


def _lz10_pkb_unpack_original(data):
    # Copia del cuerpo de tools/pkb_unpack.lz10_decompress en 0af2abd, como referencia.
    if not data or data[0] != 0x10:
        return data
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    p = 4
    while len(out) < size and p < len(data):
        flags = data[p]; p += 1
        for bit in range(8):
            if len(out) >= size or p >= len(data):
                break
            if flags & (0x80 >> bit):
                b1, b2 = data[p], data[p + 1]; p += 2
                length = (b1 >> 4) + 3
                disp = ((b1 & 0xF) << 8 | b2) + 1
                for _ in range(length):
                    out.append(out[-disp])
            else:
                out.append(data[p]); p += 1
    return bytes(out)


def _pkh(entradas):
    cab = b"PackNum 20260101" + struct.pack("<I", 0x30 + 12 * len(entradas))
    cab += bytes(0x30 - len(cab))
    return cab + b"".join(struct.pack("<III", *e) for e in entradas)


def test_alias():
    assert packnum.lz10_decompress is lz10.decompress


def test_indice_y_entradas():
    a = b"hola hola hola hola \x00" * 5
    b = bytes(range(40))
    ca, cb = lz10.compress(a), lz10.compress_store(b)
    pkb = ca + b"sin" + cb
    idx = packnum.parse_index(_pkh([(10010001, 0, len(ca)), (10010002, len(ca), 3),
                                    (10010003, len(ca) + 3, len(cb))]))
    assert idx == [(10010001, 0, len(ca)), (10010002, len(ca), 3), (10010003, len(ca) + 3, len(cb))]
    assert [packnum.entry_data(pkb, o, s) for _, o, s in idx] == [a, b"sin", b]


def test_cabecera_invalida():
    with pytest.raises(AssertionError):
        packnum.parse_index(b"NoPack" + bytes(60))


@pytest.mark.parametrize("flujo", [
    lz10.compress(b"abcabcabcabcXYZ" * 20),
    lz10.compress_store(b"literal puro"),
    b"sin comprimir",
    b"",
    lz10.compress(b"abcabcabcabc" * 30)[:-7],
    b"\x10\x40\x00\x00\x00abc",
])
def test_equivalencia_lz10(flujo):
    def resultado(f):
        try:
            return f(flujo)
        except Exception as e:  # noqa: BLE001 - se compara el tipo de fallo de las dos implementaciones
            return type(e)
    assert resultado(packnum.lz10_decompress) == resultado(_lz10_pkb_unpack_original)


def _paquete(payloads, *, align=4):
    """Devuelve (pkh, pkb) con los payloads dados comprimidos y alineados."""
    pkb = bytearray()
    entradas = []
    for eid, datos in payloads:
        bloque = lz10.compress(datos)
        entradas.append((eid, len(pkb), len(bloque)))
        pkb += bloque
        pkb += bytes((-len(pkb)) % align)
    return _pkh(entradas), bytes(pkb)


PAYLOADS = [(10010001, b"hola hola hola " * 4), (10010002, bytes(range(60))), (10010003, b"tercero")]


def _leer(pkh, pkb):
    return {eid: packnum.entry_data(pkb, o, s) for eid, o, s in packnum.parse_index(pkh)}


def test_rebuild_sin_reemplazos_equivalente():
    pkh, pkb = _paquete(PAYLOADS)
    npkh, npkb, informe = packnum.rebuild(pkh, pkb, {})
    assert informe == []
    assert _leer(npkh, npkb) == dict(PAYLOADS)
    assert [e for e, _, _ in packnum.parse_index(npkh)] == [e for e, _ in PAYLOADS]
    assert struct.unpack_from("<I", npkh, 0x10)[0] == len(npkh)


def test_rebuild_mas_largo_y_mas_corto():
    pkh, pkb = _paquete(PAYLOADS)
    largo = b"texto mucho mas largo " * 30
    npkh, npkb, informe = packnum.rebuild(pkh, pkb, {10010001: largo, 10010003: b"x"})
    leido = _leer(npkh, npkb)
    assert leido[10010001] == largo
    assert leido[10010003] == b"x"
    assert leido[10010002] == dict(PAYLOADS)[10010002]
    assert [i["evento"] for i in informe] == [10010001, 10010003]
    assert informe[0]["bytes_despues"] > informe[0]["bytes_antes"]
    assert informe[1]["bytes_despues"] < informe[1]["bytes_antes"]


@pytest.mark.parametrize("align", [4, 8, "auto"])
def test_rebuild_alineado(align):
    pkh, pkb = _paquete(PAYLOADS, align=8)
    npkh, npkb, _ = packnum.rebuild(pkh, pkb, {10010002: b"otro payload"}, align=align)
    paso = 8 if align == "auto" else align
    assert all(o % paso == 0 for _, o, _ in packnum.parse_index(npkh))
    assert len(npkb) % paso == 0
    assert _leer(npkh, npkb)[10010002] == b"otro payload"


def test_rebuild_preserves_sentinel_and_auto_alignment():
    pkh, pkb = _paquete(PAYLOADS, align=16)
    pkh = pkh + struct.pack("<III", 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
    npkh, _npkb, _ = packnum.rebuild(
        pkh, pkb, {10010002: b"otro payload"}, align="auto"
    )
    indice = packnum.parse_index(npkh)
    assert indice[-1] == (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
    assert all(off % 16 == 0 for eid, off, _ in indice if eid != 0xFFFFFFFF)


def test_alineado_observado():
    pkh, _ = _paquete(PAYLOADS, align=16)
    assert packnum.alineado_observado(packnum.parse_index(pkh)) in (16, 32)


def test_rebuild_sin_comprimir():
    pkh, pkb = _paquete(PAYLOADS)
    npkh, npkb, _ = packnum.rebuild(pkh, pkb, {10010001: b"crudo y sin cabecera"}, comprimir=False)
    _eid, off, size = packnum.parse_index(npkh)[0]
    assert npkb[off:off + size] == b"crudo y sin cabecera"
    assert _leer(npkh, npkb)[10010001] == b"crudo y sin cabecera"


def test_rebuild_sin_tocar_cabecera():
    pkh, pkb = _paquete(PAYLOADS)
    npkh, _, _ = packnum.rebuild(pkh, pkb, {}, keep_header_size=False)
    assert npkh[:0x30] == pkh[:0x30]


def test_rebuild_id_desconocido():
    pkh, pkb = _paquete(PAYLOADS)
    with pytest.raises(ValidacionError) as exc:
        packnum.rebuild(pkh, pkb, {99999999: b"x"})
    assert exc.value.codigo == "packnum_id_desconocido"


def test_rebuild_alineado_invalido():
    pkh, pkb = _paquete(PAYLOADS)
    with pytest.raises(ValidacionError):
        packnum.rebuild(pkh, pkb, {}, align="raro")
    with pytest.raises(ValidacionError):
        packnum.rebuild(pkh, pkb, {}, align=0)
