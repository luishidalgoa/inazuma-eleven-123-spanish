"""Tres paneles superiores oficiales: CTPK completo y ARCV con tamaño real.

No recodifica píxeles. La ruta JP admite enum2 y reserva el tamaño SSZL del
encabezado; el placeholder QNA se conserva idéntico al original.
"""
from __future__ import annotations

import struct

from ie123kit.ie3.comun.ui_graficos import (
    _sha,
    comprobar_fuentes_compartidas,
    trasplantar_atlas,
)
from ie123kit.ie3.comun.ui_visibles import LECTOR_SSZL_SHA256
from ie123kit.nucleo.compresion.sszl import reenvolver_como, unwrap
from ie123kit.nucleo.contenedores.arcv import entries
from ie123kit.nucleo.graficos import ctpk

PANELES = ("ie03o_syup_bg00", "ie03o_syup_bg01", "ie03o_syup_bg02")
PREFIJO = "inazuma3_ogre/data_iz/a_data_replace/help_t/"


def reconstruir_panel(japones: bytes, oficial: bytes, partes_jp: bytes,
                       partes_es: bytes, nombre: str, codigo_lector: bytes
                       ) -> tuple[bytes, dict]:
    """Reconstrucción acotada al ARCV de una textura, sin copiar paquete ES."""
    if _sha(codigo_lector) != LECTOR_SSZL_SHA256:
        raise ValueError("lector CTPK/SSZL no coincide con JP auditado")
    if nombre not in PANELES:
        raise ValueError("panel sin revisión semántica")
    jp, es = unwrap(japones), unwrap(oficial)
    tj, te = entries(jp), entries(es)
    if len(tj) != 1 or len(te) != 1 or tj[0][2] != te[0][2]:
        raise ValueError("panel requiere ARCV de una entrada con CRC idéntico")
    offset, size, crc = tj[0]
    source_offset, source_size, _ = te[0]
    original, source = jp[offset:offset + size], es[source_offset:source_offset + source_size]
    mj, me = ctpk.metadata(original), ctpk.metadata(source)
    if (mj[0] != nombre + ".tga" or mj[:3] != me[:3]
            or mj[1:4] != (512, 256, 12) or me[3] != 2
            or mj[5] != 65536 or me[5] != 262144):
        raise ValueError("panel no cumple transición oficial ETC1→RGBA5551 512×256")
    if any(jp[offset + size:]) or offset % 128:
        raise ValueError("padding o alineación ARCV del panel no demostrados")
    # Reutilizar la validación externa: CRC/layout y placeholder único idénticos,
    # salvo sus píxeles, con dimensiones y alias adecuados. El adapter de tamaño
    # fijo debe rechazar únicamente el cambio de formato que esta ruta admite.
    checked, contract = trasplantar_atlas(
        japones, oficial, {nombre + ".tga"}, codigo_lector=codigo_lector,
        layout_externo=(partes_jp, partes_es, "ie03_help_bg_t_ghost01"))
    if (checked != japones or contract["applied"]
            or [p["reason"] for p in contract["pending"]]
            != ["formato_dimensiones_no_identicos"]):
        raise ValueError("contrato del consumidor externo inesperado")
    raw = bytearray(jp[:offset] + source + jp[offset + size:])
    struct.pack_into("<I", raw, 8, len(raw))
    struct.pack_into("<I", raw, 16, len(source))
    if entries(raw) != [(offset, source_size, crc)]:
        raise ValueError("reconstrucción ARCV no conserva identidad/offset")
    result = reenvolver_como(japones, bytes(raw), "keep")
    if result[:4] != b"SSZL" or unwrap(result) != bytes(raw):
        raise ValueError("panel exige SSZL con roundtrip exacto")
    packed, unpacked = struct.unpack_from("<II", result, 8)
    if packed + 16 != len(result) or packed >= unpacked or unpacked != len(raw):
        raise ValueError("tamaños SSZL no cumplen contrato del asignador")
    extracted = unwrap(result)[offset:offset + source_size]
    if extracted != source:
        raise ValueError("CTPK oficial no reextraído literalmente")
    rgba = ctpk.decode(extracted).tobytes()
    return result, {"texture": nombre + ".tga", "crc": f"{crc:08x}",
                    "format_before": mj[3], "format_after": me[3],
                    "dimensions": list(me[1:3]), "entry_offset_unchanged": offset,
                    "entry_size_before": size, "entry_size_after": source_size,
                    "unpacked_size_before": len(jp), "unpacked_size_after": len(raw),
                    "packed_size_before": len(japones), "packed_size_after": len(result),
                    "before_sha256": _sha(japones), "after_sha256": _sha(result),
                    "source_ctpk_sha256": _sha(source), "rgba_sha256": _sha(rgba),
                    "ctpk_official_exact": True, "rgba_exact": True, "alpha_exact": True,
                    "external_qna_identical": True, "placeholder_unchanged": True,
                    "reader_sha256": LECTOR_SSZL_SHA256, "runtime_verified": False}


def construir_payloads_paneles(jp, spark, ogre, codigo_lector: bytes,
                               cro_jp: bytes) -> tuple[dict[str, bytes], dict]:
    """Payloads superiores Controles/Sistema/Ajustes; no escribe archivos."""
    parts = PREFIJO + "parts.arc"
    pj, pe = jp.read(parts), spark.read("es/" + parts)
    comprobar_fuentes_compartidas(pe, ogre.read("es/" + parts))
    payloads, rows = {}, []
    for name in PANELES:
        literal = (name + ".ctpk").encode("ascii") + b"\0"
        if literal not in cro_jp:
            raise ValueError("panel sin identidad de consumidor CRO")
        path = PREFIJO + "data/" + name + ".arc"
        source = spark.read("es/" + path)
        comprobar_fuentes_compartidas(source, ogre.read("es/" + path))
        output, report = reconstruir_panel(jp.read(path), source, pj, pe, name, codigo_lector)
        payloads[path] = output
        rows.append({"path": path, "consumer_literal": cro_jp.index(literal),
                     "shared_source_identical": True, **report})
    return payloads, {"resources": rows, "payload_count": len(payloads),
                      "runtime_verified": False}
