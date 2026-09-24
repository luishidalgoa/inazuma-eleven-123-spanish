#!/usr/bin/env python3
"""Extractor del contenedor 'archive.fa' (magic B123) de Inazuma Eleven 1-2-3 (3DS).

B123 es una variante del formato ARC0/XFSA de Level-5, con las TABLAS sin comprimir
y entradas de directorio de 24 bytes (ARC0 usa 20 y comprimidas). Las herramientas
de la comunidad (Pingouin / StudioElevenLib) NO lo abren porque rechazan el magic
y asumen tablas comprimidas -> de ahi este parser propio.

Descompresion Level-5 portada de StudioElevenLib (Tiniifan) / Kuriimu.

Uso:
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa --tree            # listar todo
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa --tree --filter sItx
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa -o work/shared/fa_extract --filter inazuma1
    python -m ie123kit._legado.fa_unpack work/shared/base_3ds/romfs/archive.fa -o work/shared/fa_extract # extraer todo

NOTA: el contenido extraido tiene copyright; va a work/ (ignorado por git).
"""
import difflib
import fnmatch
import struct
import zlib

# ----------------------------- descompresion Level-5 -----------------------------

def _lz10(data):
    p, op, mask, flag = 4, 0, 0, 0
    out = bytearray()
    while p < len(data):
        if mask == 0:
            flag = data[p]; p += 1; mask = 0x80
        if (flag & mask) == 0:
            if p + 1 > len(data): break
            out.append(data[p]); p += 1; op += 1
        else:
            if p + 2 > len(data): break
            dat = (data[p] << 8) | data[p + 1]; p += 2
            pos = (dat & 0x0FFF) + 1
            length = (dat >> 12) + 3
            for _ in range(length):
                if op - pos >= 0:
                    out.append(out[op - pos] if op - pos < len(out) else 0)
                    op += 1
        mask >>= 1
    return bytes(out)


def _rle(data):
    p = 4
    out = bytearray()
    while p < len(data):
        flag = data[p]; p += 1
        if flag & 0x80:
            length = (flag & 0x7F) + 3
            if p >= len(data): break
            out.extend(bytes([data[p]]) * length); p += 1
        else:
            length = (flag & 0x7F) + 1
            out.extend(data[p:p + length]); p += length
    return bytes(out)


def _huffman(data, bitdepth):
    size = (data[0] >> 3) | (data[1] << 5) | (data[2] << 13) | (data[3] << 21)
    p = 4
    tree_size = data[p]; p += 1
    p += 1  # tree_root byte
    tree_root = data[4 + 1]
    tree_buffer = data[p:p + tree_size * 2]; p += tree_size * 2
    result = bytearray(size * 8 // bitdepth)
    code = 0; nxt = 0; pos = tree_root; rp = 0; i = 0
    while rp < len(result):
        if i % 32 == 0:
            code = struct.unpack_from("<i", data, p)[0]; p += 4
        nxt += ((pos & 0x3F) << 1) + 2
        bit = (code >> ((31 - i) & 31)) & 1
        direction = 2 if bit == 0 else 1
        leaf = ((pos >> 5 >> direction) & 1) != 0
        pos = tree_buffer[nxt - direction]
        if leaf:
            result[rp] = pos; rp += 1
            pos = tree_root; nxt = 0
        i += 1
    if bitdepth == 8:
        return bytes(result)
    return bytes((result[2 * j] | (result[2 * j + 1] << 4)) for j in range(size))


# Magics de contenedores/archivos Level-5 que se guardan SIN comprimir en el .fa.
# Si un archivo empieza por uno de estos, NO hay que descomprimirlo.
RAW_MAGICS = (b"ARCV", b"XPCK", b"ARC0", b"XFSA", b"XFSP", b"CHRC",
              b"CHNC", b"XMPR", b"XPVB", b"XPVI", b"XCMA", b"XRES",
              b"XTX2", b"SARC", b"CGFX", b"CTPK", b"BCH\x00")


def l5_method(data):
    if len(data) < 4:
        return None, 0
    hdr = struct.unpack_from("<I", data, 0)[0]
    return hdr & 7, hdr >> 3


def is_compressed(data):
    """Heuristica: ¿este bloque es una compresion Level-5 real (no datos crudos)?"""
    if len(data) < 4 or data[:4] in RAW_MAGICS:
        return False
    method, size = l5_method(data)
    stored = len(data)
    if method == 0:
        return size == stored - 4              # None real: tamano cuadra
    # Comprimido real: el tamano declarado debe ser plausible
    return stored <= size <= stored * 400 and size <= 96 * 1024 * 1024


def l5_decompress(data):
    if not is_compressed(data):
        return data
    method, size = l5_method(data)
    if method == 0:      # None
        return data[4:4 + size]
    if method == 1:      # LZ10
        return _lz10(data)[:size]
    if method in (2, 3): # Huffman 4/8
        return _huffman(data, 4 if method == 2 else 8)[:size]
    if method == 4:      # RLE
        return _rle(data)[:size]
    if method == 5:      # ZLib
        return zlib.decompress(data[4:])[:size]
    return data


METHOD_NAME = {0: "None", 1: "LZ10", 2: "Huff4", 3: "Huff8", 4: "RLE", 5: "ZLib"}


def describe(data):
    """Etiqueta para el listado: magic crudo o metodo de compresion."""
    if len(data) >= 4 and data[:4] in RAW_MAGICS:
        return data[:4].decode("ascii", "replace").strip("\x00")
    if is_compressed(data):
        m, _ = l5_method(data)
        return METHOD_NAME.get(m, f"?{m}")
    return "raw"


# ----------------------------- parser del contenedor B123 -----------------------------

class FaArchive:
    def __init__(self, path):
        #: Ruta de origen tal cual se recibió (la usan los informes con sha256).
        self.ruta = str(path)
        self._indice = None
        with open(path, "rb") as fh:
            self.d = fh.read()
        d = self.d
        magic = d[0:4]
        if magic not in (b"B123", b"ARC0", b"XFSA"):
            raise ValueError(f"Magic no soportado: {magic!r}")
        self.de_off, self.dh_off, self.fe_off, self.name_off, self.data_off = struct.unpack_from("<5i", d, 4)
        self.de_cnt = struct.unpack_from("<H", d, 24)[0]
        self.fe_cnt = struct.unpack_from("<I", d, 28)[0]
        self.entries = self._walk()

    def _name(self, base):
        o = self.name_off + base
        e = self.d.index(b"\x00", o)
        return self.d[o:e].decode("shift-jis", "replace")

    def _walk(self):
        d = self.d
        out = []  # (fullpath, data_offset_abs, size)
        for i in range(self.de_cnt):
            o = self.de_off + i * 24
            file_count = struct.unpack_from("<H", d, o + 4)[0]
            name_base = struct.unpack_from("<I", d, o + 8)[0]
            first_file = struct.unpack_from("<I", d, o + 12)[0]
            dir_name_off = struct.unpack_from("<I", d, o + 20)[0]
            dir_path = self._name(dir_name_off)
            for j in range(file_count):
                fo = self.fe_off + (first_file + j) * 16
                name_rel = struct.unpack_from("<I", d, fo + 4)[0]
                file_off = struct.unpack_from("<I", d, fo + 8)[0]
                size = struct.unpack_from("<I", d, fo + 12)[0]
                fname = self._name(name_base + name_rel)
                out.append((dir_path + fname, self.data_off + file_off, size))
        return out

    def file_bytes(self, abs_off, size):
        return self.d[abs_off:abs_off + size]

    # ---- API añadida en F2.2 (#48): lectura por ruta -------------------------------
    # `.d`, `.entries`, `._name`, `._walk` y `file_bytes` NO cambian: las capas de work/
    # dependen de ellos byte a byte. Todo lo de abajo es aditivo.

    @property
    def index(self):
        """Índice perezoso y cacheado: ruta -> (offset absoluto, tamaño)."""
        if self._indice is None:
            self._indice = {p: (o, s) for p, o, s in self.entries}
        return self._indice

    def _parecidas(self, ruta):
        candidatas = difflib.get_close_matches(ruta, self.index, n=5, cutoff=0.4)
        if not candidatas:
            cola = ruta.rsplit("/", 1)[-1]
            candidatas = [p for p in self.index if p.endswith(cola)][:5]
        return candidatas

    def exists(self, ruta):
        """¿Existe una entrada con esa ruta exacta?"""
        return ruta in self.index

    def read(self, ruta):
        """Bytes de la entrada `ruta`; KeyError con hasta 5 rutas parecidas si no está."""
        par = self.index.get(ruta)
        if par is None:
            parecidas = self._parecidas(ruta)
            pista = "; parecidas: " + ", ".join(parecidas) if parecidas else ""
            raise KeyError(f"entrada ausente en el contenedor: {ruta}{pista}")
        off, size = par
        return bytes(self.d[off:off + size])

    def glob(self, patron):
        """Entradas que casan con `patron` (prefijo literal o comodines fnmatch), por ruta."""
        comodin = any(c in patron for c in "*?[")
        rutas = [p for p in self.index if (fnmatch.fnmatchcase(p, patron) if comodin else p.startswith(patron))]
        return {p: self.read(p) for p in sorted(rutas)}


def fe_offset_of(arc, suffix):
    """offset BYTE del FileEntry (16B) cuyo path acaba en `suffix`, y (data_off, size)."""
    d = arc.d
    for i in range(arc.de_cnt):
        o = arc.de_off + i * 24
        file_count = struct.unpack_from("<H", d, o + 4)[0]
        name_base = struct.unpack_from("<I", d, o + 8)[0]
        first_file = struct.unpack_from("<I", d, o + 12)[0]
        dir_name_off = struct.unpack_from("<I", d, o + 20)[0]
        dir_path = arc._name(dir_name_off)
        for j in range(file_count):
            fo = arc.fe_off + (first_file + j) * 16
            name_rel = struct.unpack_from("<I", d, fo + 4)[0]
            fname = arc._name(name_base + name_rel)
            if (dir_path + fname).endswith(suffix):
                return fo
    return None


def reemplazar_entrada(handle, arc, ruta, payload):
    """Anexa `payload` alineado a 16 al final de `handle` y reapunta su FileEntry.

    Copia funcional de ``ie123kit.nucleo.construir.candidata.replace_entry``. NO se importa de
    allí a propósito: ese cuerpo es copia literal de tools/build_ui_revision.py (fichero
    congelado por el bloqueo v20) y está vigilado por un test de igualdad por AST, así que no
    puede convertirse en una llamada a esta función. Se duplica aquí para que las capas y el
    constructor generalizado tengan la primitiva en nucleo sin tocar lo congelado.
    """
    field = fe_offset_of(arc, ruta)
    if field is None:
        raise ValueError(f"missing archive entry: {ruta}")
    handle.seek(0, 2)
    handle.write(bytes((-handle.tell()) % 16))
    offset = handle.tell()
    handle.write(payload)
    handle.seek(field + 8)
    handle.write(struct.pack("<II", offset - arc.data_off, len(payload)))
