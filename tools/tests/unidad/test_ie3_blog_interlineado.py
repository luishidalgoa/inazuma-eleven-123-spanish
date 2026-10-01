"""ie123kit.ie3.comun.blog_interlineado: las palabras nuevas son las instrucciones anotadas y dejan los
mismos argumentos en la pila salvo [sp+0x18] (emulado con unicorn si está)."""
import struct
import unittest

from ie123kit.ie3.comun import blog_interlineado as B

try:
    from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
except ImportError:  # pragma: no cover
    Cs = None
try:
    import unicorn as U
    from unicorn import arm_const as A
except ImportError:  # pragma: no cover
    U = None


def _normal(s: str) -> str:
    return " ".join(s.split(";")[0].replace(",", " ").split())


@unittest.skipIf(Cs is None, "sin capstone")
class TestDesensamblado(unittest.TestCase):
    def test_palabras(self):
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        for a, _antes, nueva, texto in B.ENTRADA + B.COMENTARIO + B.TITULO:
            i = next(md.disasm(struct.pack("<I", nueva), a))
            self.assertEqual(_normal(f"{i.mnemonic} {i.op_str}"), _normal(texto), hex(a))


@unittest.skipIf(U is None, "sin unicorn")
class TestPila(unittest.TestCase):
    def _correr(self, bloque, pos):
        mu = U.Uc(U.UC_ARCH_ARM, U.UC_MODE_ARM)
        mu.mem_map(0x100000, 0x200000)
        codigo = b"".join(struct.pack("<I", w[pos]) for w in bloque)
        base = bloque[0][0]
        mu.mem_write(base, codigo)
        mu.mem_write(0x194DFC, struct.pack("<I", 0xCAFE))
        sp = 0x280000
        for r, v in ((A.UC_ARM_REG_SP, sp), (A.UC_ARM_REG_R1, 0x1111), (A.UC_ARM_REG_R2, 0x2000),
                     (A.UC_ARM_REG_R4, 0x200000), (A.UC_ARM_REG_LR, sp + 0x18)):
            mu.reg_write(r, v)
        mu.mem_write(0x200000, struct.pack("<HHH", 0, 0, 0) + struct.pack("<HH", 5, 7))
        mu.emu_start(base, base + 4 * len(bloque))
        pila = struct.unpack("<10i", mu.mem_read(sp, 40))
        regs = [mu.reg_read(r) for r in (A.UC_ARM_REG_R0, A.UC_ARM_REG_R1, A.UC_ARM_REG_R2, A.UC_ARM_REG_R3)]
        return pila, regs

    def test_entrada(self):
        jp, rj = self._correr(B.ENTRADA, 1)
        es, re_ = self._correr(B.ENTRADA, 2)
        self.assertEqual(es[6], B.ESPACIADO)
        self.assertEqual(jp[6], 1)
        self.assertEqual(jp[:6] + jp[7:], es[:6] + es[7:])
        self.assertEqual(rj[1:], re_[1:])   # r1, r2, r3 iguales al llegar a la llamada

    def test_comentario(self):
        jp, _ = self._correr(B.COMENTARIO, 1)
        es, _ = self._correr(B.COMENTARIO, 2)
        self.assertEqual(es[6], B.ESPACIADO)
        self.assertEqual(jp[6], 3)
        self.assertEqual(jp[7:], es[7:])


if __name__ == "__main__":
    unittest.main()
