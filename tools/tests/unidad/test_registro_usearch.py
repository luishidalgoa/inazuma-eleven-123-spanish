"""ie123kit.ie3.comun.registro_usearch: nombres españoles y orden alfabético global."""
import struct
import unittest

from ie123kit.ie3.comun import registro_usearch as RU


def _us(nombre: bytes, uid: int) -> bytes:
    r = bytearray(RU.R_USEARCH)
    r[0:16] = nombre.ljust(16, b"\0")
    r[16:32] = nombre.ljust(16, b"\0")
    struct.pack_into("<H", r, 0x24, uid)
    return bytes(r)


def _ub(corto: bytes, uid: int) -> bytes:
    r = bytearray(RU.R_UNITBASE)
    r[RU.CORTO:RU.CORTO + 16] = corto.ljust(16, b"\0")
    struct.pack_into("<H", r, RU.ID, uid)
    return bytes(r)


ALVARO = b"\x83\xa6lvaro"  # Álvaro con portador


class TestRegistroUsearch(unittest.TestCase):
    def test_fila_kana(self):
        self.assertEqual(RU.fila_kana("あ".encode("cp932")), 0)
        self.assertEqual(RU.fila_kana("カ".encode("cp932")), 1)
        self.assertEqual(RU.fila_kana(b"Ab"), -1)

    def test_nombres_y_orden(self):
        a, i = "あきら".encode("cp932"), "いいのや".encode("cp932")
        us_jp = _us(a, 1) + _us(i, 2)
        u_jp = _ub(a, 1) + _ub(i, 2)
        u_es = _ub(b"Zeta", 1) + _ub(b"Ameen", 2)
        us, inf = RU.nombres(us_jp, u_jp, u_es)
        self.assertEqual(inf["cambiados"], 2)
        self.assertEqual(us[:4], b"Zeta")
        ordenado = RU.ordenar(us_jp, us)
        self.assertEqual(ordenado[:5], b"Ameen")
        self.assertEqual(len(ordenado), len(us))

    def test_orden_global_y_fijos(self):
        # filas kana distintas en el japonés: el orden ya no las respeta; «???» no se mueve
        jp = [_us("さ".encode("cp932"), 1), _us(b"???", 0), _us("あ".encode("cp932"), 2), _us("か".encode("cp932"), 3)]
        es = [_us(b"Butler", 1), _us(b"???", 0), _us(b"Zoolan", 2), _us(ALVARO, 3)]
        out = RU.ordenar(b"".join(jp), b"".join(es))
        nombres = [out[k * 44:k * 44 + 16].split(b"\0")[0] for k in range(4)]
        self.assertEqual(nombres, [ALVARO, b"???", b"Butler", b"Zoolan"])

    def test_letra(self):
        self.assertEqual(RU.letra(b"Ab"), 1)
        self.assertEqual(RU.letra(ALVARO), 1)
        self.assertEqual(RU.letra(b"Sam"), 31)
        self.assertEqual(RU.letra(b"Zed"), 44)
        self.assertEqual(RU.letra("ドン".encode("cp932")), 44)

    def test_clave_portador(self):
        self.assertEqual(RU.clave(b"\x83\xa6lvaro"), "ALVARO")


if __name__ == "__main__":
    unittest.main()
