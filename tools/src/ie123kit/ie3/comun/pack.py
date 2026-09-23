"""
Indice Level-5 PKH + datos PKB.

Cabecera PKH (0x30 bytes), verificada contra eve/evet de IE1.2.3 (JP),
Lightning Bolt (EU) y Team Ogre Attacks (EU):

    0x00  char[16]  "PackNum 20080626"
    0x10  u32       tamano del propio .pkh
    0x14  u16       version (1)
    0x16  u16       numero de entradas
    0x18  u32       alineacion de los bloques (0x10)
    0x1C  u32       tamano del bloque mas grande
    0x20  u8[16]    relleno a cero

Entrada (12 bytes):

    0x00  u32  identificador del evento (ESTABLE entre idiomas)
    0x04  u32  offset dentro del .pkb
    0x08  u32  tamano dentro del .pkb

Algunos .pkh terminan con una entrada centinela FF FF FF FF; se ignora.
El identificador es la clave que permite alinear japones y espanol sin
depender de offsets ni del orden fisico.
"""

import struct
from pathlib import Path

from ie123kit.ie3.comun.lz import maybe_decompress

PKH_MAGIC = b"PackNum "
PKH_HEADER_SIZE = 0x30
PKH_ENTRY_SIZE = 12
SENTINEL = 0xFFFFFFFF


class PackError(RuntimeError):
    pass


class PackEntry:
    __slots__ = ("event_id", "index", "offset", "size")

    def __init__(self, index, event_id, offset, size):
        self.index = index
        self.event_id = event_id
        self.offset = offset
        self.size = size

    @property
    def name(self):
        return f"{self.event_id:08x}"

    def __repr__(self):
        return (
            f"<PackEntry #{self.index} id={self.event_id:08x} "
            f"off={self.offset:#x} size={self.size:#x}>"
        )


class Pack:
    """Par .pkb/.pkh ya cargado en memoria."""

    def __init__(self, pkb_path, pkh_path):
        self.pkb_path = Path(pkb_path)
        self.pkh_path = Path(pkh_path)
        self.pkb = self.pkb_path.read_bytes()

        pkh = self.pkh_path.read_bytes()

        if not pkh.startswith(PKH_MAGIC):
            raise PackError(
                f"{self.pkh_path}: no empieza por {PKH_MAGIC!r} "
                f"(encontrado {pkh[:16]!r})"
            )

        declared_size = struct.unpack_from("<I", pkh, 0x10)[0]
        if declared_size != len(pkh):
            raise PackError(
                f"{self.pkh_path}: la cabecera declara {declared_size} bytes "
                f"y el fichero mide {len(pkh)}"
            )

        self.version = struct.unpack_from("<H", pkh, 0x14)[0]
        count = struct.unpack_from("<H", pkh, 0x16)[0]
        self.alignment = struct.unpack_from("<I", pkh, 0x18)[0]
        self.max_block = struct.unpack_from("<I", pkh, 0x1C)[0]

        available = (len(pkh) - PKH_HEADER_SIZE) // PKH_ENTRY_SIZE
        if count > available:
            raise PackError(
                f"{self.pkh_path}: declara {count} entradas pero solo caben "
                f"{available}"
            )

        self.entries = []
        self.skipped_sentinels = 0

        for i in range(count):
            event_id, offset, size = struct.unpack_from(
                "<III", pkh, PKH_HEADER_SIZE + i * PKH_ENTRY_SIZE
            )

            if event_id == SENTINEL and offset == SENTINEL:
                self.skipped_sentinels += 1
                continue

            if offset + size > len(self.pkb):
                raise PackError(
                    f"{self.pkh_path}: la entrada {i} (id {event_id:08x}) "
                    f"apunta a {offset + size} y el .pkb mide {len(self.pkb)}"
                )

            self.entries.append(PackEntry(i, event_id, offset, size))

        self.duplicate_ids = _duplicates(e.event_id for e in self.entries)

    def __len__(self):
        return len(self.entries)

    def raw(self, entry):
        return self.pkb[entry.offset:entry.offset + entry.size]

    def data(self, entry):
        """Bloque descomprimido. Devuelve (datos, comprimido?)."""
        return maybe_decompress(self.raw(entry))

    def __iter__(self):
        return iter(self.entries)


def _duplicates(values):
    seen = set()
    dupes = set()
    for v in values:
        if v in seen:
            dupes.add(v)
        seen.add(v)
    return dupes


def find_packs(root, names=("eve", "evet")):
    """Busca pares .pkb/.pkh con los nombres indicados bajo `root`."""
    root = Path(root)
    found = {}

    for pkb in root.rglob("*.pkb"):
        if pkb.stem.lower() not in names:
            continue
        pkh = pkb.with_suffix(".pkh")
        if pkh.exists():
            found[str(pkb.resolve()).lower()] = (pkb, pkh)

    return sorted(found.values(), key=lambda pair: str(pair[0]).lower())
