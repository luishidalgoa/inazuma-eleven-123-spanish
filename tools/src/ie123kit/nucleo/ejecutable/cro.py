"""Módulos CRO de 3DS: tablas de segmentos/relocaciones y parcheo de literales.

Recoge los patrones ``cro_relocation_patch`` y ``cro_literal_patch`` de las capas de ``work/``.
Vale para las cuatro CRO de la recopilación (``ina_menu``, ``ina_main1``, ``ina_main2``,
``ina_main3ogre``): ningún nombre de fichero está fijado en el código.

Cabecera usada: 0xC8/0xCC tabla de segmentos (``<III`` = offset, tamaño, id), 0x128/0x12C tabla de
relocaciones (``<IBBBBI``), 0xF0/0xF4 módulos importados y 0x100/0x104 importaciones con nombre.

La codificación del texto NUNCA se implementa aquí: el codificador por defecto es
``ie123kit.nucleo.texto.ancho_completo.encode_fullwidth`` (bloqueo tipográfico v20), importado de
forma perezosa, y se puede sustituir por parámetro.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

from ie123kit.nucleo.errores import ValidacionError
from ie123kit.nucleo.registros.rangos import assert_only_changed, fusionar

__all__ = ["Cro", "CroPatcher", "Reloc", "Segment"]

_SEG_OFF, _SEG_NUM = 0xC8, 0xCC
_REL_OFF, _REL_NUM = 0x128, 0x12C
_MOD_OFF, _MOD_NUM = 0xF0, 0xF4
_IMP_OFF, _IMP_NUM = 0x100, 0x104


@dataclass(frozen=True)
class Segment:
    offset: int
    size: int
    id: int


@dataclass(frozen=True)
class Reloc:
    record_offset: int
    target: int
    type: int
    seg_index: int
    addend: int
    value: int


def _codificador_por_defecto():
    """Transporte latino de ancho completo v20 (importación perezosa; nunca se copia aquí)."""
    from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth

    return encode_fullwidth


class Cro:
    """Vista sobre una CRO: segmentos, relocaciones, referencias e importaciones."""

    def __init__(self, data) -> None:
        self.datos = bytearray(data)
        if len(self.datos) < 0x140:
            raise ValidacionError("cro_corta", detalle=f"{len(self.datos)} B")

    def _u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self.datos, offset)[0]

    @property
    def segments(self) -> list[Segment]:
        base, numero = self._u32(_SEG_OFF), self._u32(_SEG_NUM)
        if base + 12 * numero > len(self.datos):
            raise ValidacionError("tabla_segmentos_fuera", detalle=f"0x{base:x} x{numero}")
        return [Segment(*struct.unpack_from("<III", self.datos, base + 12 * i)) for i in range(numero)]

    def _reloc(self, segs: list[Segment], indice: int, base: int) -> Reloc:
        p = base + 12 * indice
        so, typ, sidx, _u1, _u2, add = struct.unpack_from("<IBBBBI", self.datos, p)
        return Reloc(
            record_offset=p,
            target=segs[so & 0xF].offset + (so >> 4),
            type=typ,
            seg_index=sidx,
            addend=add,
            value=segs[sidx].offset + add if sidx < len(segs) else add,
        )

    @property
    def relocations(self) -> list[Reloc]:
        segs = self.segments
        base, numero = self._u32(_REL_OFF), self._u32(_REL_NUM)
        if base + 12 * numero > len(self.datos):
            raise ValidacionError("tabla_relocaciones_fuera", detalle=f"0x{base:x} x{numero}")
        return [self._reloc(segs, i, base) for i in range(numero)]

    def retarget(self, target_offset: int, new_value: int, expect_old: int | None = None) -> Reloc:
        """Reapunta la relocación cuyo destino es ``target_offset`` al offset ``new_value``.

        Exige exactamente una coincidencia y, si se indica ``expect_old``, que el valor actual sea
        ese. Devuelve la relocación ya modificada.
        """
        segs = self.segments
        candidatas = [r for r in self.relocations if r.target == target_offset]
        if len(candidatas) != 1:
            raise ValidacionError(
                "relocacion_ambigua", detalle=f"0x{target_offset:x}: {len(candidatas)} coincidencias"
            )
        reloc = candidatas[0]
        if expect_old is not None and reloc.value != expect_old:
            raise ValidacionError(
                "relocacion_inesperada", detalle=f"0x{target_offset:x}: 0x{reloc.value:x} != 0x{expect_old:x}"
            )
        destino = [i for i, s in enumerate(segs) if s.offset <= new_value < s.offset + s.size]
        if not destino:
            raise ValidacionError("valor_fuera_de_segmento", detalle=f"0x{new_value:x}")
        indice = destino[0]
        so, typ, _sidx, u1, u2, _add = struct.unpack_from("<IBBBBI", self.datos, reloc.record_offset)
        struct.pack_into(
            "<IBBBBI", self.datos, reloc.record_offset, so, typ, indice, u1, u2, new_value - segs[indice].offset
        )
        return self._reloc(segs, (reloc.record_offset - self._u32(_REL_OFF)) // 12, self._u32(_REL_OFF))

    @staticmethod
    def _rotimm(palabra: int) -> int:
        rot = ((palabra >> 8) & 0xF) * 2
        imm = palabra & 0xFF
        return ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF if rot else imm

    def references(self, offset: int) -> list[tuple[str, int]]:
        """Referencias ARM al offset: ``('adr', pc)`` y ``('pool@X', pc)`` de un LDR de pool literal.

        Este barrido es aritmética pura sobre el segmento de código y NO necesita capstone; solo
        :meth:`desensamblar` lo usa.
        """
        segs = self.segments
        if not segs:
            return []
        inicio, fin = segs[0].offset, min(segs[0].offset + segs[0].size, len(self.datos))
        adr: dict[int, list[int]] = {}
        ldrs: dict[int, list[int]] = {}
        for pc in range(inicio, fin - 3, 4):
            w = self._u32(pc)
            if (w & 0x0FEF0000) == 0x028F0000:
                adr.setdefault(pc + 8 + self._rotimm(w), []).append(pc)
            elif (w & 0x0FEF0000) == 0x024F0000:
                adr.setdefault(pc + 8 - self._rotimm(w), []).append(pc)
            if (w & 0x0F7F0000) == 0x051F0000:
                imm = w & 0xFFF
                arriba = (w >> 23) & 1
                ldrs.setdefault(pc + 8 + (imm if arriba else -imm), []).append(pc)
        por_valor: dict[int, list[int]] = {}
        for r in self.relocations:
            por_valor.setdefault(r.value, []).append(r.target)
        salida = [("adr", pc) for pc in adr.get(offset, [])]
        for pool in por_valor.get(offset, []):
            salida += [(f"pool@{pool:x}", pc) for pc in ldrs.get(pool, [])]
        return salida

    def desensamblar(self, inicio: int, fin: int) -> list[tuple[int, str, str]]:
        """``[(dirección, mnemónico, operandos)]`` usando capstone.

        capstone es dependencia declarada del paquete, pero se importa de forma perezosa: si no
        está instalado se devuelve una lista vacía en lugar de fallar.
        """
        try:
            from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
        except ImportError:
            return []
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        return [(i.address, i.mnemonic, i.op_str) for i in md.disasm(bytes(self.datos[inicio:fin]), inicio)]

    def _cadena(self, offset: int) -> str:
        fin = self.datos.index(b"\0", offset)
        return bytes(self.datos[offset:fin]).decode("latin1")

    def _parches(self, offset: int) -> list[int]:
        segs = self.segments
        salida = []
        while True:
            so, _typ, ultimo, _u0, _u, _add = struct.unpack_from("<IBBBBI", self.datos, offset)
            salida.append(segs[so & 0xF].offset + (so >> 4))
            if ultimo:
                return salida
            offset += 12

    def imports(self) -> dict[int, str]:
        """``{offset_del_thunk: nombre}`` de las importaciones con nombre y de módulo."""
        nombres: dict[int, str] = {}
        base, numero = self._u32(_IMP_OFF), self._u32(_IMP_NUM)
        for i in range(numero):
            nombre_off, parche_off = struct.unpack_from("<II", self.datos, base + 8 * i)
            for p in self._parches(parche_off):
                nombres[p - 4] = self._cadena(nombre_off)
        base, numero = self._u32(_MOD_OFF), self._u32(_MOD_NUM)
        for i in range(numero):
            nombre_off, idx_off, idx_num, anon_off, anon_num = struct.unpack_from(
                "<IIIII", self.datos, base + 20 * i
            )
            modulo = self._cadena(nombre_off)
            for j in range(idx_num):
                idx, parche_off = struct.unpack_from("<II", self.datos, idx_off + 8 * j)
                for p in self._parches(parche_off):
                    nombres.setdefault(p - 4, f"{modulo}#{idx}")
            for j in range(anon_num):
                seg_ofs, parche_off = struct.unpack_from("<II", self.datos, anon_off + 8 * j)
                for p in self._parches(parche_off):
                    nombres.setdefault(p - 4, f"{modulo}@{seg_ofs:x}")
        return nombres

    def import_patches(self, nombre: str) -> list[tuple[int, int, int]]:
        """``[(destino, sumando, offset_del_registro)]`` de la importación con nombre ``nombre``."""
        base, numero = self._u32(_IMP_OFF), self._u32(_IMP_NUM)
        segs = self.segments
        salida = []
        for i in range(numero):
            nombre_off, parche_off = struct.unpack_from("<II", self.datos, base + 8 * i)
            if self._cadena(nombre_off) != nombre:
                continue
            p = parche_off
            while True:
                so, _typ, ultimo, _u0, _u, add = struct.unpack_from("<IBBBBI", self.datos, p)
                salida.append((segs[so & 0xF].offset + (so >> 4), add, p))
                if ultimo:
                    break
                p += 12
        return salida

    def retarget_import(self, nombre: str, destino: int, nuevo: int, esperado: int | None = None) -> int:
        """Cambia el sumando de la entrada de importación ``nombre`` que parchea ``destino``.

        Sirve para apuntar una llamada a otro campo del mismo símbolo importado (p. ej. otro bloque
        de un ``g_Itx*``). Exige una sola coincidencia y, si se da, el sumando ``esperado``
        (o ``nuevo``: idempotente). Devuelve el sumando anterior.
        """
        hits = [(add, p) for t, add, p in self.import_patches(nombre) if t == destino]
        if len(hits) != 1:
            raise ValidacionError("importacion_ambigua", detalle=f"{nombre} 0x{destino:x}: {len(hits)}")
        add, p = hits[0]
        if esperado is not None and add not in (esperado, nuevo):
            raise ValidacionError("importacion_inesperada", detalle=f"0x{destino:x}: 0x{add:x} != 0x{esperado:x}")
        struct.pack_into("<I", self.datos, p + 8, nuevo)
        return add

    def to_bytes(self) -> bytes:
        return bytes(self.datos)


class CroPatcher:
    """Parcheo de literales de una CRO con la comprobación enmascarada de rangos declarados."""

    def __init__(self, base_cro) -> None:
        self.base_cro = Path(base_cro)
        self.base = self.base_cro.read_bytes()
        self.datos = bytearray(self.base)
        self.rangos: list[tuple[int, int]] = []
        self.literales: list[dict] = []

    @staticmethod
    def _bytes(valor) -> bytes:
        return valor if isinstance(valor, (bytes, bytearray)) else valor.encode("cp932")

    def find_literal(self, esperado) -> list[int]:
        """Offsets donde ``esperado`` aparece como literal completo (delimitado por NUL)."""
        aguja = self._bytes(esperado)
        salida, pos = [], 0
        while True:
            pos = self.base.find(aguja, pos)
            if pos < 0:
                return salida
            fin = pos + len(aguja)
            if (pos == 0 or self.base[pos - 1] == 0) and fin < len(self.base) and self.base[fin] == 0:
                salida.append(pos)
            pos += 1

    def _hueco(self, offset: int, largo: int) -> int:
        """Bytes NUL de relleno tras el terminador del literal."""
        extra, pos = 0, offset + largo + 1
        while pos < len(self.base) and self.base[pos] == 0:
            extra += 1
            pos += 1
        return extra

    def literal(self, offset, esperado, nuevo, capacidad=None, encoder=None, blank="　",
                allow_growth_into_padding=False) -> tuple[int, int]:
        """Sustituye el literal japonés de ``offset`` por ``nuevo`` (rellenando con NUL).

        Exige que en ``offset`` esté ``esperado`` seguido de NUL, que el literal empiece justo
        detrás de un NUL y que ``0 < len(codificado) <= len(esperado)`` (o ``capacidad``). Un texto
        vacío se sustituye por ``blank`` (el juego nunca debe copiar una cadena vacía).
        Devuelve el rango semiabierto escrito.
        """
        original = self._bytes(esperado)
        fin = offset + len(original)
        if bytes(self.datos[offset:fin + 1]) != original + b"\0":
            raise ValidacionError("literal_inesperado", self.base_cro, f"0x{offset:x}")
        if offset and self.datos[offset - 1] != 0:
            raise ValidacionError("literal_sin_nul_previo", self.base_cro, f"0x{offset:x}")
        texto = nuevo if nuevo else blank
        codificado = (encoder or _codificador_por_defecto())(texto)
        tope = capacidad if capacidad is not None else len(original)
        if allow_growth_into_padding:
            tope += self._hueco(offset, len(original))
        if not 0 < len(codificado) <= tope:
            raise ValidacionError(
                "literal_no_cabe", self.base_cro, f"0x{offset:x}: {texto!r} ocupa {len(codificado)} B > {tope} B"
            )
        self.datos[offset:offset + tope + 1] = codificado + bytes(tope + 1 - len(codificado))
        self.rangos.append((offset, offset + tope + 1))
        self.literales.append({"offset": offset, "jp": original.decode("cp932", "replace"), "es": texto,
                               "bytes": len(codificado), "capacidad": tope})
        return (offset, offset + tope + 1)

    def raw(self, offset, bytes_esperados, bytes_nuevos) -> tuple[int, int]:
        """Sustituye bytes crudos del mismo tamaño, comprobando antes el contenido actual."""
        esperados, nuevos = bytes(bytes_esperados), bytes(bytes_nuevos)
        if len(esperados) != len(nuevos):
            raise ValidacionError("raw_tamano_distinto", self.base_cro, f"0x{offset:x}")
        if bytes(self.datos[offset:offset + len(esperados)]) != esperados:
            raise ValidacionError("raw_inesperado", self.base_cro, f"0x{offset:x}")
        self.datos[offset:offset + len(nuevos)] = nuevos
        self.rangos.append((offset, offset + len(nuevos)))
        return (offset, offset + len(nuevos))

    def declarar(self, inicio: int, fin: int) -> None:
        """Declara un rango cambiado por fuera de esta clase (por ejemplo por :class:`Cro`)."""
        self.rangos.append((inicio, fin))

    def save(self, dir_capa) -> Path:
        """Escribe ``<dir_capa>/romfs/cro/<nombre>.cro`` y ``cro_literales.json``.

        Antes comprueba que SOLO los rangos declarados difieren de la CRO base.
        """
        resultado = bytes(self.datos)
        assert_only_changed(self.base, resultado, self.rangos)
        destino = Path(dir_capa) / "romfs" / "cro" / self.base_cro.name
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(resultado)
        informe = {
            "cro": self.base_cro.name,
            "rangos": [[a, b] for a, b in fusionar(self.rangos)],
            "literales": self.literales,
        }
        (Path(dir_capa) / "cro_literales.json").write_text(
            json.dumps(informe, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return destino
