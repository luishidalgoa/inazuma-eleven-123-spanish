import struct

import pytest

from ie123kit.ie3.comun.ui_paneles import construir_payloads_paneles
from ie123kit.nucleo.compresion.blz import decompress
from ie123kit.nucleo.compresion.sszl import unwrap
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.arcv import entries
from ie123kit.nucleo.contenedores.fa import FaArchive

pytestmark = pytest.mark.requiere_rom


def test_jp_reader_allocates_declared_size_and_accepts_ctpk_enum2():
    path = find_root() / "work/shared/base_3ds/exefs.bin"
    if not path.exists():
        pytest.skip("requiere ExeFS JP")
    exe = path.read_bytes()
    off, size = struct.unpack_from("<II", exe, 8)
    code = decompress(exe[512 + off:512 + off + size])
    anchors = {
        0x80B8: "2c2091e50c2080e5",  # descriptor formato +2C -> +C.
        0xBC470: "24109de5",         # formato desde descriptor en pila.
        0xBC4AC: "48c51b00",         # enum2 -> dirección VA1BC548.
        0xBC548: "bc639fe5285084e51d0000ea",
        0xBC90C: "34800000",         # tipo nativo RGB5A1.
        0xBC5CC: "0f0001e20000c2e5", # conserva enum del archivo.
        0x13DD18: "24209fe5001090e5020051e10c0090050400000a",
        0x5E9AC: ("d97c03eb182194e50010a0e1000055e30800a0e10100000aca8f01eb"
                  "010000ea00f020e38d8d01eb012b8de200109de50040a0e10c2082e2"),
    }
    for offset, expected_hex in anchors.items():
        expected = bytes.fromhex(expected_hex)
        assert code[offset:offset + len(expected)] == expected, hex(offset)


def test_three_official_panels_match_source_ctpk_exactly():
    root = find_root()
    base = root / "work/shared/base_3ds"
    paths = [base / "romfs/archive.fa",
             root / "work/ie3/rayo_celeste/fuentes/3ds_eu/romfs/archive_sz.fa",
             root / "work/ie3/amenaza_del_ogro/fuentes/3ds_eu/romfs/archive_oz.fa"]
    if not all(p.exists() for p in [*paths, base / "exefs.bin"]):
        pytest.skip("requiere originales JP/Spark/Ogre")
    jp, spark, ogre = [FaArchive(str(p)) for p in paths]
    exe = (base / "exefs.bin").read_bytes()
    off, size = struct.unpack_from("<II", exe, 8)
    code = decompress(exe[512 + off:512 + off + size])
    cro = (base / "romfs/cro/ina_main3ogre.cro").read_bytes()
    payloads, report = construir_payloads_paneles(jp, spark, ogre, code, cro)
    assert len(payloads) == 3 and not report["runtime_verified"]
    for path, output in payloads.items():
        raw, source = unwrap(output), unwrap(spark.read("es/" + path))
        o, n, _ = entries(raw)[0]
        eo, en, _ = entries(source)[0]
        assert raw[o:o + n] == source[eo:eo + en]
    assert all(r["ctpk_official_exact"] and r["external_qna_identical"]
               for r in report["resources"])
