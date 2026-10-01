"""Read texture rectangles from QNA 051 parts without changing layout data."""
import struct


def regions(data):
    if data[:8] != b' QNA 051':
        raise ValueError('unsupported QNA version')
    textures, _, parts = struct.unpack_from('<III', data, 8)
    names_offset, _, parts_offset = struct.unpack_from('<III', data, 36)
    if names_offset + textures * 32 > len(data) or parts_offset + parts * 128 > len(data):
        raise ValueError('QNA table outside file')
    names = [data[names_offset+i*32:names_offset+(i+1)*32].split(b'\0')[0].decode('ascii')
             for i in range(textures)]
    result = set()
    for i in range(parts):
        offset = parts_offset + i * 128
        texture = struct.unpack_from('<I', data, offset+88)[0]
        # Untextured colour parts (for example the emblem-name background).
        if texture == 0xffffffff:
            continue
        if texture >= textures:
            raise ValueError('QNA texture index outside table')
        box = struct.unpack_from('<4f', data, offset)
        if not all(value.is_integer() for value in box):
            raise ValueError('fractional QNA region')
        result.add((names[texture], tuple(map(int, box))))
    return sorted(result)


# --- QnaLayout: lectura y edición del maquetado QNA 051 (patrón qna_region_lookup_and_edit) ---
#
# Cabecera: b' QNA 051', +8 (textures, ?, parts) y +36 (names_offset, ?, parts_offset).
# Cada nombre de textura ocupa 32 B ASCII terminados en NUL.
# Cada parte ocupa 128 B: +0 caja UV (4 float), +32/+36 posición X/Y, +52/+56 la segunda pareja
# de posición (las capas de work/ movían siempre los dos campos a la vez), +88 índice de textura
# (0xffffffff = parte de color sin textura).

_MAGIA = b" QNA 051"
_PARTE = 128
_NOMBRE = 32
_POS = ((32, 36), (52, 56))
_SIN_TEXTURA = 0xFFFFFFFF


class QnaParte:
    """Una parte del maquetado, ligada al búfer de su :class:`QnaLayout`."""

    def __init__(self, layout, indice):
        self._layout = layout
        self.indice = indice
        self.offset = layout._partes_offset + indice * _PARTE

    @property
    def caja(self):
        """Caja UV ``(x0, y0, x1, y1)`` en píxeles de la textura."""
        return tuple(struct.unpack_from('<4f', self._layout.datos, self.offset))

    @property
    def indice_textura(self):
        valor = struct.unpack_from('<I', self._layout.datos, self.offset + 88)[0]
        return None if valor == _SIN_TEXTURA else valor

    @property
    def nombre_textura(self):
        i = self.indice_textura
        return None if i is None else self._layout.texturas[i]

    def _pos(self, campo):
        return struct.unpack_from('<f', self._layout.datos, self.offset + campo)[0]

    @property
    def x(self):
        return self._pos(_POS[0][0])

    @property
    def y(self):
        return self._pos(_POS[0][1])

    def move(self, dx, dy=0.0):
        """Desplaza la parte escribiendo in situ LOS DOS campos de posición (X y Y)."""
        for campo_x, campo_y in _POS:
            for campo, delta in ((campo_x, dx), (campo_y, dy)):
                struct.pack_into('<f', self._layout.datos, self.offset + campo,
                                 self._pos(campo) + delta)


class QnaLayout:
    """Maquetado QNA 051 editable sobre una copia del blob original."""

    def __init__(self, blob):
        self.datos = bytearray(blob)
        self._tamano = len(blob)
        if bytes(self.datos[:8]) != _MAGIA:
            raise ValueError('unsupported QNA version')
        n_tex, _, n_partes = struct.unpack_from('<III', self.datos, 8)
        nombres_offset, _, self._partes_offset = struct.unpack_from('<III', self.datos, 36)
        if (nombres_offset + n_tex * _NOMBRE > self._tamano
                or self._partes_offset + n_partes * _PARTE > self._tamano):
            raise ValueError('QNA table outside file')
        self.texturas = [
            bytes(self.datos[nombres_offset + i * _NOMBRE:nombres_offset + (i + 1) * _NOMBRE]).split(b'\0')[0]
            .decode('ascii')
            for i in range(n_tex)
        ]
        self.partes = [QnaParte(self, i) for i in range(n_partes)]

    @classmethod
    def parse(cls, blob):
        return cls(blob)

    def regions_for(self, nombre_textura):
        """Cajas UV (enteras) de las partes que dibujan esa textura, con o sin sufijo ``.tga``."""
        objetivo = {nombre_textura, nombre_textura + '.tga', nombre_textura.removesuffix('.tga')}
        salida = []
        for parte in self.partes:
            nombre = parte.nombre_textura
            if nombre is None or nombre not in objetivo:
                continue
            caja = parte.caja
            if not all(valor.is_integer() for valor in caja):
                raise ValueError('fractional QNA region')
            salida.append(tuple(int(valor) for valor in caja))
        return salida

    def to_bytes(self):
        """Bytes del maquetado; exige el mismo tamaño que el blob original."""
        if len(self.datos) != self._tamano:
            raise ValueError('QNA changed size')
        return bytes(self.datos)


def qna_in_arc(data):
    """Localiza los maquetados QNA de un .arc: ``[(offset_en_el_arc, QnaLayout), ...]``.

    Acepta el .arc envuelto en SSZL; los offsets son los del ARCV ya desenvuelto.
    """
    from ie123kit.nucleo.compresion.sszl import unwrap
    from ie123kit.nucleo.contenedores.arcv import entries

    crudo = unwrap(bytes(data))
    salida = []
    for offset, tamano, _ in entries(crudo):
        blob = crudo[offset:offset + tamano]
        if blob[:8] == _MAGIA:
            salida.append((offset, QnaLayout(blob)))
    return salida


def insertar_copias_nodo(blob, nodo, xs, plantilla=-1, tras=0):
    """QNA con copias de una parte de ``nodo`` insertadas en el propio nodo (crece 128 B por copia).

    Cada copia es la parte ``plantilla`` del nodo (índice relativo; por defecto la última) con la X del
    primer campo de posición (+32) cambiada a cada valor de ``xs``; se insertan detrás de la parte ``tras``
    del nodo, en ese orden. Es lo que hace la EU con la placa del rótulo de lugar (nodo 11 de
    ``a_field/field_t.arc``: 2 partes en la JP, 5 en la EU). Se ajustan el número de partes (+16), los
    cuatro offsets de cola (+48, los que quedan detrás de la tabla de partes) y los índices de los nodos
    posteriores. La segunda pareja de posición (+52) no se toca, como en la EU.
    """
    q = bytes(blob)
    if q[:8] != _MAGIA:
        raise ValueError('unsupported QNA version')
    _, n_nodos, n_partes = struct.unpack_from('<III', q, 8)
    _, nodos_off, partes_off = struct.unpack_from('<III', q, 36)
    fin_partes = partes_off + n_partes * _PARTE
    if nodos_off >= partes_off or not 0 <= nodo < n_nodos:
        raise ValueError('QNA: nodo o tabla de nodos inesperados')
    nodos = [list(struct.unpack_from('<4I', q, nodos_off + 16 * i)) for i in range(n_nodos)]
    cnt, ini, fin, _ = nodos[nodo]
    if cnt != fin - ini or cnt == 0:
        raise ValueError('QNA: nodo sin partes')
    base = q[partes_off + (ini + (plantilla % cnt)) * _PARTE:][:_PARTE]
    nuevas = b''
    for x in xs:
        p = bytearray(base)
        struct.pack_into('<f', p, _POS[0][0], float(x))
        nuevas += bytes(p)
    k = len(xs)
    corte = partes_off + (ini + tras + 1) * _PARTE
    out = bytearray(q[:corte] + nuevas + q[corte:])
    struct.pack_into('<I', out, 16, n_partes + k)
    colas = struct.unpack_from('<4I', q, 48)
    if any(o < fin_partes for o in colas):
        raise ValueError('QNA: offset de cola dentro de la tabla de partes')
    struct.pack_into('<4I', out, 48, *[o + k * _PARTE for o in colas])
    for i, (c, a, f, e) in enumerate(nodos):
        if i == nodo:
            c, f = c + k, f + k
        elif a >= fin:
            a, f = a + k, f + k
        struct.pack_into('<4I', out, nodos_off + 16 * i, c, a, f, e)
    return bytes(out)
