"""Relocalización por contenido de parches de CRO (nucleo.ejecutable.relocalizar) sobre CRO sintéticas.

La «1.0» y la «1.4» sintéticas tienen el mismo código y datos, pero la 1.4 lleva 8 instrucciones más al
principio del texto y .rodata/.data desplazados. La candidata
cambia una rama a una cueva nueva tras el texto, traduce una cadena en su sitio, añade una cadena al
final de .rodata (el segmento crece), reapunta una relocalización y un literal PIC a esa cadena y
carga una dirección absoluta del code.bin. (El texto se desplaza 0x20 y los datos 0x40.)
"""

from __future__ import annotations

import struct

import pytest

from ie123kit.nucleo.ejecutable.cro import Cro
from ie123kit.nucleo.ejecutable.relocalizar import (
    codificar_referencia,
    es_texto_sjis,
    literales_absolutos,
    mapear_direccion_absoluta,
    normalizar,
    pares_pic,
    referencia,
    relocalizar,
    tramos_cambiados,
    verificar_estructura,
    verificar_relocalizacion,
)

TAM = 0x900
TABLAS, REL = 0x800, 0x840
CADENA1 = "こんにちは世界".encode("cp932")
CADENA2 = "さようなら友達".encode("cp932")
NUEVA = "やあ！".encode("cp932") + b"\0"
ABS_10, ABS_14 = 0x2A16D8, 0x2A06A8


def _mov(i: int) -> int:
    """Instrucción distinta para cada i (mov rX, #imm): código sin repeticiones."""
    return 0xE3A00000 | ((i % 13) << 12) | ((i * 7) & 0xFF) | ((i // 64) << 8)


def _rama(pc: int, destino: int, bl: bool = True) -> int:
    return (0xEB000000 if bl else 0xEA000000) | (((destino - pc - 8) >> 2) & 0xFFFFFF)


def construir(desp: int, prefijo: int = 0) -> tuple[bytearray, dict]:
    """CRO sintética; ``desp`` desplaza .rodata/.data y ``prefijo`` mete instrucciones al principio del texto."""
    d = bytearray(TAM)
    texto, rodata, datos = 0x180, 0x400 + desp, 0x600 + desp
    tam_texto = 0x140 + 4 * prefijo
    struct.pack_into("<I", d, 0x84, TABLAS)
    struct.pack_into("<II", d, 0xC8, TABLAS, 3)
    struct.pack_into("<III", d, TABLAS, texto, tam_texto, 0)
    struct.pack_into("<III", d, TABLAS + 12, rodata, 0x40, 1)
    struct.pack_into("<III", d, TABLAS + 24, datos, 0x40, 2)
    struct.pack_into("<II", d, 0x128, REL, 1)
    # relocalización: el puntero de .data+0 apunta a CADENA2
    struct.pack_into("<IBBBBI", d, REL, (0 << 4) | 2, 2, 1, 0, 0, 0x10)
    for tabla in (0xF0, 0xF8, 0x100, 0x130):
        struct.pack_into("<II", d, tabla, 0x880, 0)
    p = {"texto": texto, "rodata": rodata, "datos": datos}
    pc = texto
    for i in range(prefijo):
        struct.pack_into("<I", d, pc, _mov(500 + i))
        pc += 4
    base = pc  # a partir de aquí el código es el mismo en las dos versiones
    for i in range(16):
        struct.pack_into("<I", d, base + 4 * i, _mov(i))
    a, b = base + 0x40, base + 0xA0
    p.update(a=a, b=b, bl=a + 0x10, ldr=a + 0x20, add=a + 0x24, lit=a + 0x40, lit_abs=a + 0x44)
    for i in range(0x60 // 4):
        struct.pack_into("<I", d, a + 4 * i, _mov(100 + i))
    struct.pack_into("<I", d, p["bl"], _rama(p["bl"], b))
    struct.pack_into("<I", d, p["ldr"], 0xE59F1000 | (p["lit"] - p["ldr"] - 8))   # ldr r1, [pc, #n]
    struct.pack_into("<I", d, p["add"], 0xE08F1001)                                # add r1, pc, r1
    struct.pack_into("<I", d, a + 0x28, 0xE59F2000 | (p["lit_abs"] - a - 0x28 - 8))  # ldr r2, [pc, #n]
    struct.pack_into("<i", d, p["lit"], rodata - (p["add"] + 8))                  # PIC -> CADENA1
    struct.pack_into("<I", d, p["lit_abs"], 0x12345678)
    for i in range(0x18):
        struct.pack_into("<I", d, b + 4 * i, _mov(300 + i))
    struct.pack_into("<I", d, b + 0x5C, 0xE12FFF1E)  # bx lr
    # cadenas dentro del segmento de código (como en las CRO del juego), junto a un entero 0x7fff
    p["texto_cod"] = b + 0x60
    d[b + 0x60:b + 0x80] = "吾輩は猫である。名前はまだ無い。".encode("cp932")
    struct.pack_into("<I", d, b + 0x80, 0x7FFF)
    d[b + 0x84:b + 0xA0] = "どこで生れたかとんと見当がつか".encode("cp932")[:0x1C]
    d[rodata:rodata + len(CADENA1)] = CADENA1
    d[rodata + 0x10:rodata + 0x10 + len(CADENA2)] = CADENA2
    d[rodata + 0x20:rodata + 0x40] = "寿限無寿限無五劫の擦り切れ海砂利".encode("cp932")[:0x20]
    d[datos + 4:datos + 0x40] = bytes((i * 37 + 11) & 0xFF for i in range(0x3C))
    return d, p


@pytest.fixture
def versiones():
    base, pb = construir(0)
    dest, pd = construir(0x40, prefijo=8)
    cand = bytearray(base)
    fin_texto = pb["texto"] + 0x140
    # (1) bl B -> bl cueva; la cueva hace mov r0,#7 y vuelve con b (bl+4)
    struct.pack_into("<I", cand, pb["bl"], _rama(pb["bl"], fin_texto))
    struct.pack_into("<I", cand, fin_texto, 0xE3A00007)
    struct.pack_into("<I", cand, fin_texto + 4, _rama(fin_texto + 4, pb["bl"] + 4, bl=False))
    # (2) cadena traducida en su sitio
    cand[pb["rodata"] + 0x10:pb["rodata"] + 0x10 + len(CADENA2)] = "おはよう皆さん".encode("cp932")
    # (3) cadena nueva al final de .rodata; el segmento crece 8 bytes
    nueva = pb["rodata"] + 0x40
    cand[nueva:nueva + len(NUEVA)] = NUEVA
    struct.pack_into("<I", cand, TABLAS + 16, 0x48)
    # (4) la relocalización y el literal PIC apuntan a la cadena nueva
    struct.pack_into("<IBBBBI", cand, REL, 2, 2, 1, 0, 0, 0x40)
    struct.pack_into("<i", cand, pb["lit"], nueva - (pb["add"] + 8))
    # (6) cadena del segmento de código traducida con códigos propios: «82 93 00 ea» parece una rama
    cand[pb["texto_cod"] + 4:pb["texto_cod"] + 12] = bytes.fromhex("e8d7e95f829300ea")
    # (5) literal absoluto del code.bin
    struct.pack_into("<I", cand, pb["lit_abs"], ABS_10)
    return bytes(base), bytes(cand), bytes(dest), pb, pd


def test_referencias_arm_ida_y_vuelta():
    casos = [
        (0x1000, _rama(0x1000, 0x2000), "rama", 0x2000),
        (0x1000, 0xE59F1010, "ldr", 0x1018),
        (0x1000, 0xE51F1010, "ldr", 0x0FF8),
        (0x1000, 0xE1DF20B4, "ldrh", 0x100C),
        (0x1000, 0xED9F0A02, "vldr", 0x1010),
        (0x1000, 0xE28F1F8D, "adr", 0x1000 + 8 + 0x234),
        (0x1000, 0xE24F1F8D, "adr", 0x1000 + 8 - 0x234),
    ]
    for pc, w, clase, destino in casos:
        assert referencia(pc, w) == (clase, destino)
        # misma distancia desde otro sitio -> misma instrucción
        assert codificar_referencia(pc + 0x40, w, destino + 0x40) == w
    assert referencia(0x1000, 0xE3A00001) is None
    # adr que cambia de signo: add <-> sub
    nueva = codificar_referencia(0x1000, 0xE28F1010, 0x0F00)
    assert referencia(0x1000, nueva) == ("adr", 0x0F00)
    assert codificar_referencia(0x1000, 0xE59F1010, 0x9000) is None  # no cabe en 12 bits


def test_texto_sjis_y_tramos():
    assert es_texto_sjis(CADENA1 + b"\0\0" + CADENA2)
    assert not es_texto_sjis(struct.pack("<4I", 0xE3A01000, 0xE59F1010, 0xE12FFF1E, 0xEB000010))
    assert tramos_cambiados(b"abcdefgh", b"abXdeYgh") == [(2, 6)]
    assert tramos_cambiados(b"abcdefgh", b"abXdeYgh", separacion=1) == [(2, 3), (5, 6)]


def test_pares_pic_y_normalizacion(versiones):
    base, _cand, dest, pb, pd = versiones
    assert pares_pic(base, 0x180, 0x400) == {pb["lit"]: pb["add"]}
    nb, nd = normalizar(Cro(base)), normalizar(Cro(dest))
    # el código de A, con la rama y el literal PIC anulados, es idéntico en las dos versiones
    assert nb[pb["a"]:pb["a"] + 0x60] == nd[pd["a"]:pd["a"] + 0x60]
    assert base[pb["a"]:pb["a"] + 0x60] != dest[pd["a"]:pd["a"] + 0x60]


def test_relocaliza_todos_los_parches(versiones):
    base, cand, dest, _pb, pd = versiones
    r = relocalizar(base, cand, dest, absolutas={ABS_10: ABS_14})
    assert r.ok, [p.a_dict() for p in r.fallidos]
    tipos = sorted(p.tipo for p in r.parches)
    assert set(tipos) == {"cadena", "codigo", "crecimiento", "cueva", "relocacion"}
    out = r.datos
    cueva_d = pd["texto"] + 0x160
    assert referencia(pd["bl"], struct.unpack_from("<I", out, pd["bl"])[0]) == ("rama", cueva_d)
    assert referencia(cueva_d + 4, struct.unpack_from("<I", out, cueva_d + 4)[0]) == ("rama", pd["bl"] + 4)
    assert out[pd["rodata"] + 0x10:pd["rodata"] + 0x10 + len(CADENA2)] == "おはよう皆さん".encode("cp932")
    nueva_d = pd["rodata"] + 0x40
    assert out[nueva_d:nueva_d + len(NUEVA)] == NUEVA
    cro = Cro(out)
    assert cro.segments[1].size == 0x48
    assert cro.relocations[0].value == nueva_d
    assert struct.unpack_from("<i", out, pd["lit"])[0] == nueva_d - (pd["add"] + 8)
    assert struct.unpack_from("<I", out, pd["lit_abs"])[0] == ABS_14
    # el texto se copia tal cual: la «rama» aparente no se recalcula
    assert out[pd["texto_cod"] + 4:pd["texto_cod"] + 12] == bytes.fromhex("e8d7e95f829300ea")
    assert verificar_estructura(dest, out, r.rangos) == []
    assert verificar_relocalizacion(base, cand, dest, r) == []
    assert r.resumen()["fallidos"] == 0


def test_literal_absoluto_sin_traducir_falla(versiones):
    base, cand, dest, pb, _pd = versiones
    assert literales_absolutos(base, cand) == {pb["lit_abs"]: ABS_10}
    r = relocalizar(base, cand, dest)
    fallidos = [p for p in r.fallidos if "code.bin" in p.motivo]
    assert fallidos and fallidos[0].tipo == "codigo"


def test_contexto_distinto_no_se_parchea(versiones):
    base, cand, dest, _pb, pd = versiones
    otra = bytearray(dest)
    # la 1.4 «cambió» la función A: el parche de la rama ya no se puede localizar con seguridad
    for i in range(0x60 // 4):
        if pd["a"] + 4 * i not in (pd["bl"], pd["ldr"], pd["add"], pd["a"] + 0x28):
            struct.pack_into("<I", otra, pd["a"] + 4 * i, _mov(700 + i))
    r = relocalizar(base, cand, bytes(otra), absolutas={ABS_10: ABS_14})
    fallido = [p for p in r.fallidos if p.tipo == "codigo"]
    assert fallido and "contexto" in fallido[0].motivo
    # lo no relocalizado no se escribe
    assert r.datos[pd["a"]:pd["a"] + 0x60] == bytes(otra[pd["a"]:pd["a"] + 0x60])


def test_mapear_direccion_absoluta():
    def code(desp: int, direccion: int) -> bytes:
        d = bytearray(0x400 + desp)
        for rep in range(3):
            o = desp + 0x100 * rep
            for i in range(16):
                struct.pack_into("<I", d, o + 4 * i, _mov(40 * rep + i))
            struct.pack_into("<I", d, o + 0x40, direccion)
        return bytes(d)

    res = mapear_direccion_absoluta(code(0, ABS_10), code(0x20, ABS_14), ABS_10)
    assert res["destino"] == ABS_14 and res["votos"] == 3
    assert mapear_direccion_absoluta(code(0, ABS_10), code(0x20, ABS_14), 0x2B0000)["destino"] is None


def test_construir_actualizacion_de_punta_a_punta(versiones, tmp_path):
    """Orquestador: CRO relocalizada + textura de data_iz2 tomada de la candidata + informe."""
    import sys
    from pathlib import Path

    contrato = Path(__file__).resolve().parent.parent / "contrato"
    if str(contrato) not in sys.path:
        sys.path.insert(0, str(contrato))
    from fa_sintetico import escribir_fa

    from ie123kit.nucleo.construir.actualizacion import construir_actualizacion, equivalente_1_0

    base, cand, dest, _pb, _pd = versiones
    ruta_tex = "inazuma3_ogre/data_iz/a_data_replace/collection_b/data/tarjeta.arc"
    ruta_otra = "inazuma3_ogre/data_iz/a_data_replace/collection_b/data/otra.arc"
    assert equivalente_1_0(ruta_tex.replace("/data_iz/", "/data_iz2/")) == ruta_tex
    for d, contenido in (("base", base), ("cand", cand)):
        (tmp_path / d).mkdir()
        (tmp_path / d / "ina_main9.cro").write_bytes(contenido)
    upd = tmp_path / "update"
    (upd / "cro").mkdir(parents=True)
    (upd / "cro" / "ina_main9.cro").write_bytes(dest)
    (upd / ".crr").mkdir()
    (upd / ".crr" / "static.crr").write_bytes(b"CRR0")
    for r in (ruta_tex, ruta_otra):
        f = upd / equivalente_1_0(r).replace("/data_iz/", "/data_iz2/")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"SSZL-1.4")
    fb = escribir_fa(tmp_path / "base.fa", {ruta_tex: b"SSZL-jp", ruta_otra: b"SSZL-igual"})
    fc = escribir_fa(tmp_path / "cand.fa", {ruta_tex: b"SSZL-es", ruta_otra: b"SSZL-igual"})
    code_b = b"".join(struct.pack("<16I", *(_mov(40 * r + i) for i in range(16))) + struct.pack("<I", ABS_10)
                      for r in range(3))
    code_u = b"\0" * 8 + code_b.replace(struct.pack("<I", ABS_10), struct.pack("<I", ABS_14))
    salida = tmp_path / "salida"
    inf = construir_actualizacion(cro_base=tmp_path / "base", cro_candidata=tmp_path / "cand",
                                  romfs_actualizacion=upd, code_base=code_b, code_actualizacion=code_u,
                                  archive_base=fb, archive_candidata=fc, destino=salida)
    assert inf["completo"], inf
    assert inf["absolutas"][hex(ABS_10)]["destino"] == hex(ABS_14)
    datos = (salida / "romfs/cro/ina_main9.cro").read_bytes()
    assert verificar_estructura(dest, datos) == []
    tex = salida / "romfs" / ruta_tex.replace("/data_iz/", "/data_iz2/")
    assert tex.read_bytes() == b"SSZL-es"
    assert not (salida / "romfs" / ruta_otra.replace("/data_iz/", "/data_iz2/")).exists()
    assert ".crr/static.crr" in inf["sin_tocar"]
    assert (salida / "informe_actualizacion.json").is_file()
