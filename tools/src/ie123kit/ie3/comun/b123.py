"""
Contenedor Level-5 "B123" (archive.fa / archive_sz.fa / archive_op.fa).

Estructura verificada empiricamente contra:

  * IE1.2.3!! (JP)        romfs/archive.fa        15547 archivos / 438 dirs
  * IE3 Lightning Bolt    romfs/archive_sz.fa     19501 archivos / 628 dirs
  * IE3 Team Ogre Attacks romfs/archive_op.fa

Cabecera (0x48 bytes):

    0x00  char[4]  "B123"
    0x04  u32      offset de la tabla de directorios (siempre 0x48)
    0x08  u32      final de la tabla de directorios
    0x0C  u32      offset de la tabla de archivos
    0x10  u32      offset de la tabla de nombres
    0x14  u32      offset de los datos
    0x18  u16      numero de directorios
    0x1A  u16      numero de directorios - 1
    0x1C  u32      numero de archivos
    0x20  u32      final util de la tabla de nombres
    0x28  u8[16]   hash / build id
    0x38  u16      numero de directorios (repetido)
    0x3C  u32      numero de archivos (repetido)

Entrada de directorio (24 bytes, ordenadas por crc ascendente):

    0x00  u32  crc32(ruta del directorio en minusculas, con "/" final)
    0x04  u16  numero de archivos del directorio
    0x06  u16  numero de subdirectorios
    0x08  u32  offset del primer nombre de archivo (tabla de nombres)
    0x0C  u32  indice del primer archivo (tabla de archivos)
    0x10  u32  indice del primer subdirectorio
    0x14  u32  offset del nombre del directorio (tabla de nombres)

Entrada de archivo (16 bytes):

    0x00  u32  crc32(nombre del archivo en minusculas)
    0x04  u32  campo auxiliar (no necesario para extraer)
    0x08  u32  offset relativo a data_offset
    0x0C  u32  tamano

Detalle importante: dentro de un directorio los NOMBRES estan ordenados
alfabeticamente pero las ENTRADAS DE ARCHIVO estan ordenadas por CRC32.
Emparejamos ordenando los nombres por CRC32 y validamos entrada a entrada,
asi que una lectura incorrecta se detecta inmediatamente.
"""

import struct
import zlib
from pathlib import Path

MAGIC = b"B123"
HEADER_SIZE = 0x48
DIR_ENTRY_SIZE = 24
FILE_ENTRY_SIZE = 16


def name_crc(name: bytes) -> int:
    return zlib.crc32(name.lower()) & 0xFFFFFFFF


class B123Error(RuntimeError):
    pass


class B123Entry:
    __slots__ = ("aux", "directory", "index", "name", "offset", "path", "size")

    def __init__(self, directory, name, offset, size, index, aux):
        self.directory = directory
        self.name = name
        self.path = directory + name
        self.offset = offset
        self.size = size
        self.index = index
        self.aux = aux

    def __repr__(self):
        return f"<B123Entry {self.path!r} off={self.offset:#x} size={self.size:#x}>"


class B123Archive:
    """Lector del contenedor B123."""

    def __init__(self, path):
        self.path = Path(path)
        self._fh = None
        self._parse()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    @property
    def fh(self):
        if self._fh is None:
            self._fh = self.path.open("rb")
        return self._fh

    @staticmethod
    def looks_like(path):
        try:
            with open(path, "rb") as f:
                return f.read(4) == MAGIC
        except OSError:
            return False

    def _parse(self):
        f = self.fh
        header = f.read(HEADER_SIZE)

        if len(header) < HEADER_SIZE or header[:4] != MAGIC:
            raise B123Error(f"{self.path} no tiene cabecera B123")

        (
            dir_table,
            dir_table_end,
            file_table,
            name_table,
            self.data_offset,
        ) = struct.unpack_from("<5I", header, 0x04)

        dir_count = struct.unpack_from("<H", header, 0x18)[0]
        file_count = struct.unpack_from("<I", header, 0x1C)[0]

        self.dir_count = dir_count
        self.file_count = file_count

        expected_dir_bytes = dir_count * DIR_ENTRY_SIZE
        if dir_table_end - dir_table != expected_dir_bytes:
            raise B123Error(
                f"{self.path}: la tabla de directorios mide "
                f"{dir_table_end - dir_table} bytes y esperaba "
                f"{expected_dir_bytes} ({dir_count} x {DIR_ENTRY_SIZE})"
            )

        expected_file_bytes = file_count * FILE_ENTRY_SIZE
        if name_table - file_table != expected_file_bytes:
            raise B123Error(
                f"{self.path}: la tabla de archivos mide "
                f"{name_table - file_table} bytes y esperaba "
                f"{expected_file_bytes} ({file_count} x {FILE_ENTRY_SIZE})"
            )

        if not (
            HEADER_SIZE <= dir_table < dir_table_end
            <= file_table < name_table < self.data_offset
        ):
            raise B123Error(f"{self.path}: offsets de cabecera incoherentes")

        f.seek(dir_table)
        dirs_blob = f.read(expected_dir_bytes)

        f.seek(file_table)
        files_blob = f.read(expected_file_bytes)

        f.seek(name_table)
        names_blob = f.read(self.data_offset - name_table)

        self.entries = []
        self.directories = []
        seen_indices = set()

        for i in range(dir_count):
            (
                dir_crc,
                n_files,
                n_subdirs,
                first_name_off,
                first_file_index,
                _first_subdir,
                dir_name_off,
            ) = struct.unpack_from("<IHHIIII", dirs_blob, i * DIR_ENTRY_SIZE)

            dir_name = _cstring(names_blob, dir_name_off)

            # El directorio raiz tiene nombre vacio y usa 0xFFFFFFFF
            # como centinela en vez del CRC del nombre.
            expected_crc = 0xFFFFFFFF if dir_name == b"" else name_crc(dir_name)

            if expected_crc != dir_crc:
                raise B123Error(
                    f"{self.path}: CRC de directorio {i} no cuadra "
                    f"({dir_name!r}: {expected_crc:08x} != {dir_crc:08x})"
                )

            self.directories.append((dir_name, n_files, n_subdirs))

            if n_files == 0:
                continue

            names = []
            off = first_name_off
            for _ in range(n_files):
                nm = _cstring(names_blob, off)
                names.append(nm)
                off += len(nm) + 1

            for slot, nm in enumerate(sorted(names, key=name_crc)):
                index = first_file_index + slot

                if index >= file_count:
                    raise B123Error(
                        f"{self.path}: indice de archivo {index} fuera de rango"
                    )

                crc, aux, rel_off, size = struct.unpack_from(
                    "<4I", files_blob, index * FILE_ENTRY_SIZE
                )

                if crc != name_crc(nm):
                    raise B123Error(
                        f"{self.path}: CRC de archivo {index} no cuadra en "
                        f"{dir_name!r} ({nm!r}: {name_crc(nm):08x} != {crc:08x})"
                    )

                if index in seen_indices:
                    raise B123Error(
                        f"{self.path}: indice de archivo {index} duplicado"
                    )

                seen_indices.add(index)

                self.entries.append(
                    B123Entry(dir_name, nm, rel_off, size, index, aux)
                )

        if len(seen_indices) != file_count:
            raise B123Error(
                f"{self.path}: reconstrui {len(seen_indices)} de "
                f"{file_count} entradas de archivo"
            )

        self.total_size = self.path.stat().st_size
        self._by_path = {e.path: e for e in self.entries}

    def read(self, entry):
        if isinstance(entry, (str, bytes)):
            key = entry.encode() if isinstance(entry, str) else entry
            entry = self._by_path[key]

        end = self.data_offset + entry.offset + entry.size
        if end > self.total_size:
            raise B123Error(
                f"{entry.path!r} se sale del archivo "
                f"(necesita {end} y el fichero mide {self.total_size})"
            )

        self.fh.seek(self.data_offset + entry.offset)
        data = self.fh.read(entry.size)

        if len(data) != entry.size:
            raise B123Error(f"lectura incompleta de {entry.path!r}")

        return data

    @property
    def index(self):
        """Identidades str compatibles con adaptadores de FaArchive, sin cargar datos."""
        return {e.path.decode(): e for e in self.entries}

    def exists(self, path):
        key = path.encode() if isinstance(path, str) else path
        return key in self._by_path

    def find(self, predicate):
        return [e for e in self.entries if predicate(e.path)]

    def extract(self, entry, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.read(entry))
        return destination


def _cstring(blob, offset):
    end = blob.index(b"\x00", offset)
    return blob[offset:end]
