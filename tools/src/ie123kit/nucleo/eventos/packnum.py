"""Índice del paquete de scripts de evento Level-5 "PackNum" (eve.pkb + eve.pkh).

FORMATO RESUELTO del indice (.pkh):
  - 16 bytes: cabecera ASCII "PackNum YYYYMMDD"
  - +0x10 u32: tamaño total del .pkh
  - +0x30 en adelante: tabla de entradas de 12 bytes c/u:
        u32 event_id   (p.ej. 10010001 = mapa/capitulo 1001, evento 0001)
        u32 offset      (en el .pkb)
        u32 size
  Los offsets cubren el .pkb completo (verificado).

Cada entrada del .pkb es un SCRIPT DE EVENTO COMPILADO (bytecode) con el texto del
dialogo EMBEBIDO como operandos, comprimido en LZ10 de Nintendo.

``lz10_decompress`` es un alias de ``nucleo.compresion.lz10.decompress`` (cuerpo
idéntico al de la antigua ``pkb_unpack.lz10_decompress``).

``rebuild`` reconstruye el par (.pkh, .pkb) a partir de los bytes de entrada. El
módulo NO conoce ninguna ruta del contenedor ('inazuma1/data_iz/script/eve.*' o
'mch.*'): quien llama pasa los bytes ya leídos. Sustituye a las cuatro copias del
patrón ``pack_rebuild`` del catálogo de auditoría (entre ellas el ``exec`` sobre el
texto del bloqueado tools/build_ui_revision.py que hace la capa v55).
"""
import struct

from ie123kit.nucleo.compresion import lz10
from ie123kit.nucleo.compresion.lz10 import decompress as lz10_decompress
from ie123kit.nucleo.errores import ValidacionError

ALINEADOS = (32, 16, 8, 4, 2, 1)


def parse_index(pkh):
    assert pkh[:7] == b"PackNum", "no es un .pkh PackNum"
    n = (len(pkh) - 0x30) // 12
    out = []
    for i in range(n):
        eid, off, size = struct.unpack_from("<III", pkh, 0x30 + i * 12)
        out.append((eid, off, size))
    return out


def entry_data(pkb, off, size):
    """Devuelve el contenido descomprimido de una entrada del .pkb."""
    return lz10_decompress(pkb[off:off + size])


def alineado_observado(indice) -> int:
    """Mayor alineado de ``ALINEADOS`` que divide todos los offsets del índice."""
    # El centinela ``FF FF FF FF`` no es un bloque: sus dos campos restantes
    # también son FFFFFFFF y no participa en el alineado del PKB.
    offsets = [off for eid, off, _ in indice if eid != 0xFFFFFFFF]
    for paso in ALINEADOS:
        if all(off % paso == 0 for off in offsets):
            return paso
    return 1


def _paso(align, indice) -> int:
    if isinstance(align, str):
        if align != "auto":
            raise ValidacionError("packnum_alineado_invalido", detalle=align)
        return alineado_observado(indice)
    paso = int(align)
    if paso < 1:
        raise ValidacionError("packnum_alineado_invalido", detalle=str(align))
    return paso


def rebuild(
    pkh: bytes,
    pkb: bytes,
    reemplazos: dict[int, bytes],
    *,
    comprimir: bool = True,
    align: int | str = 4,
    keep_header_size: bool = True,
) -> tuple[bytes, bytes, list[dict]]:
    """Reconstruye (.pkh, .pkb) sustituyendo el payload de los ids de ``reemplazos``.

    - Se recorre el índice en su ORDEN ORIGINAL; las entradas sin reemplazo se copian
      tal cual desde ``pkb`` (misma secuencia de bytes comprimidos).
    - ``comprimir`` afecta solo a los payloads nuevos: con ``True`` se comprimen en LZ10
      comprobando la ida y vuelta (``decompress(compress(x)) == x``); con ``False`` se
      almacenan en crudo (``entry_data`` los devuelve intactos: no llevan cabecera 0x10).
    - ``align`` rellena con ceros detrás de cada entrada; ``'auto'`` deduce el alineado
      observado en los offsets del ``pkh`` original.
    - ``keep_header_size`` reescribe el tamaño de cabecera en 0x10, igual que hace
      tools/build_ui_revision.py; con ``False`` se conservan los 0x30 bytes originales.

    Devuelve además un informe por id sustituido con
    ``{"evento", "bytes_antes", "bytes_despues"}`` (tamaños ALMACENADOS en el .pkb).
    """
    indice = parse_index(pkh)
    reales = [registro for registro in indice if registro[0] != 0xFFFFFFFF]
    centinelas = [registro for registro in indice if registro[0] == 0xFFFFFFFF]
    conocidos = {eid for eid, _, _ in reales}
    desconocidos = sorted(set(reemplazos) - conocidos)
    if desconocidos:
        raise ValidacionError("packnum_id_desconocido", detalle=", ".join(str(e) for e in desconocidos))
    paso = _paso(align, indice)

    salida = bytearray()
    nuevo_indice: list[tuple[int, int, int]] = []
    informe: list[dict] = []
    for eid, off, size in reales:
        original = bytes(pkb[off:off + size])
        if eid in reemplazos:
            payload = bytes(reemplazos[eid])
            if comprimir:
                bloque = lz10.compress(payload)
                if lz10.decompress(bloque) != payload:
                    raise ValidacionError("packnum_lz10_ida_y_vuelta", detalle=str(eid))
            else:
                bloque = payload
            informe.append({"evento": eid, "bytes_antes": len(original), "bytes_despues": len(bloque)})
        else:
            bloque = original
        nuevo_indice.append((eid, len(salida), len(bloque)))
        salida.extend(bloque)
        salida.extend(bytes((-len(salida)) % paso))

    nuevo_pkh = bytearray(pkh[:0x30])
    for registro in nuevo_indice:
        nuevo_pkh.extend(struct.pack("<III", *registro))
    # Conserva exactamente el centinela original. Convertirlo en una entrada
    # con offset final inventado altera la semántica del índice y, además,
    # falsea el alineado detectado por ``auto``.
    for registro in centinelas:
        nuevo_pkh.extend(struct.pack("<III", *registro))
    if keep_header_size:
        struct.pack_into("<I", nuevo_pkh, 0x10, len(nuevo_pkh))
    return bytes(nuevo_pkh), bytes(salida), informe
