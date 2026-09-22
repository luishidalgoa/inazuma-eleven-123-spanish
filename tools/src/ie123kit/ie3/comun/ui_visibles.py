"""Atlas UI oficiales: contrato por consumidor, sin trasplantar QNA regionales.

El atlas puede usar UV repetidas fuera de sus dimensiones si son precisamente
las UV oficiales JP/ES y no cambia ni formato ni tamaño. Se conservan índices,
animaciones y todos los bytes no-píxel del paquete actual.
"""
from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Mapping

from ie123kit.ie3.comun.ui_graficos import _sha, _tabla, comprobar_fuentes_compartidas
from ie123kit.nucleo.compresion.sszl import reenvolver_como, unwrap
from ie123kit.nucleo.graficos import ctpk
from ie123kit.nucleo.graficos.qna import QnaLayout

# Selección semántica visual JP/ES, no detección por nombre. No incluye los
# atlas regionales de categorías tutorial ni iconos con significados distintos.
ATLAS_VISIBLES = {
    "status_t": (
        "ie03_menu_status_bg01_t01", "ie03_menu_status_bg03_t01",
        "ie03_menu_status_ranking01_t01",
    ),
    "organization_b": ("ie03o_menu_org_bg_b01", "ie03o_menu_org_btn_b01"),
    "system_b": (
        "ie03_menu_system_window_b02", "ie03_menu_system_window_b03",
        "ie03_menu_system_mes_b02", "ie03_menu_system_button_b02",
        "ie03_menu_system_button_b03",
    ),
    "ranking_b": ("ie03_menu_ranking_bar_b01", "ie03_menu_ranking_button_b01"),
    "item_b": (
        "ie03_menu_item_bg_b01", "ie03_menu_item_window_b02",
        "ie03_menu_item_button_b01", "ie03_menu_item_button_b02",
    ),
    "sp_move_b": (
        "ie03_menu_sp_move_bg_b01", "ie03_menu_sp_move_bg_b02",
        "ie03_menu_sp_move_window_b02", "ie03_menu_sp_move_button_b01",
    ),
    "formation_b": (
        "ie03_menu_form_bg_b01", "ie03_menu_form_window_b01",
        "ie03_menu_form_button_b02",
    ),
}
LECTOR_SSZL_SHA256 = "ae11511902ab4ead12617d5d52099aad2f238037588482651aac5cbae8bea18e"
REGIONES_TUTORIAL = {"ie03o_menu_system_mes_b01.tga": ((0, 0, 96, 144),)}


def _consumidores(raw: bytes, tabla: dict) -> dict[str, Counter]:
    result = {}
    for crc, (offset, size) in tabla.items():
        blob = raw[offset:offset + size]
        if blob[:8] != b" QNA 051":
            continue
        layout = QnaLayout(blob)
        for part in layout.partes:
            if part.nombre_textura is None:
                continue
            name = part.nombre_textura.removesuffix(".tga")
            # Agrupar por CRC impide aceptar consumidores de otro QNA.
            descriptor = bytes(layout.datos[part.offset:part.offset + 128])
            result.setdefault(name, Counter())[(crc, descriptor)] += 1
    return result


def trasplantar_atlas_por_partes(japones: bytes, oficial: bytes, nombres: set[str],
                                *, actual: bytes | None = None,
                                codigo_lector: bytes | None = None,
                                regiones: Mapping[str, tuple] | None = None) -> tuple[bytes, dict]:
    """Copia RGBA oficial exacto con equivalencia de TODOS los consumidores.

``actual`` permite componer traducciones previas. Solo acepta cambios previos
en píxeles CTPK, nunca geometría, metadatos, identidad ni tamaño descomprimido.
"""
    current = japones if actual is None else actual
    jp, es, base = unwrap(japones), unwrap(oficial), unwrap(current)
    tj, te, tb = _tabla(jp), _tabla(es), _tabla(base)
    if tj.keys() != te.keys() or tj != tb or len(jp) != len(base):
        raise ValueError("identidades CRC o tabla ARCV actual incompatibles")
    refs_j, refs_e = _consumidores(jp, tj), _consumidores(es, te)
    textures = {}
    allowed_current = bytearray(jp)
    for crc, (offset, size) in tj.items():
        eo, en = te[crc]
        original = jp[offset:offset + size]
        before, source = base[offset:offset + size], es[eo:eo + en]
        if original[:4] != b"CTPK":
            if before != original:
                raise ValueError("actual altera QNA/no-texto")
            if original[:8] != b" QNA 051" and original != source:
                raise ValueError("fuente altera recurso no-texto desconocido")
            continue
        mj, mb, me = ctpk.metadata(original), ctpk.metadata(before), ctpk.metadata(source)
        if mj != mb:
            raise ValueError("actual altera metadatos CTPK")
        name, _, _, _, pixel_offset, pixel_size = mj
        if pixel_offset + pixel_size > size:
            raise ValueError("píxeles CTPK fuera de rango")
        allowed_current[offset + pixel_offset:offset + pixel_offset + pixel_size] = (
            before[pixel_offset:pixel_offset + pixel_size])
        if name in textures:
            raise ValueError("nombre CTPK duplicado")
        textures[name] = offset, before, source, mj, me, crc
    if bytes(allowed_current) != base:
        raise ValueError("actual altera bytes fuera de píxeles")
    if not nombres <= textures.keys():
        raise ValueError("textura solicitada ausente")
    if regiones and not regiones.keys() <= nombres:
        raise ValueError("regiones sin textura seleccionada")
    out, applied = bytearray(base), []
    for name in sorted(nombres):
        offset, before, source, mj, me, crc = textures[name]
        key = name.removesuffix(".tga")
        if mj[:4] != me[:4] or mj[5] != me[5]:
            raise ValueError(f"formato/dimensiones no equivalentes: {name}")
        _, width, height, fmt, po, size = mj
        boxes = (regiones or {}).get(name)
        consumers_j, consumers_e = refs_j.get(key, Counter()), refs_e.get(key, Counter())
        if boxes:
            if fmt not in (2, 3, 4):
                raise ValueError("regiones requieren formato nativo de 16 bits sin pérdidas")
            if any(not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height)
                   for x0, y0, x1, y1 in boxes):
                raise ValueError("región seleccionada fuera de textura")
            def intersecting(refs, selected_boxes=boxes):
                filtered = Counter()
                for identity, count in refs.items():
                    a, b, c, d = struct.unpack_from("<4f", identity[1])
                    for x0, y0, x1, y1 in selected_boxes:
                        if a < x1 and c > x0 and b < y1 and d > y0:
                            if not (x0 <= a < c <= x1 and y0 <= b < d <= y1):
                                raise ValueError("región corta un consumidor QNA")
                            filtered[identity] = count
                return filtered
            consumers_j, consumers_e = intersecting(consumers_j), intersecting(consumers_e)
        if not consumers_j or consumers_j != consumers_e:
            raise ValueError(f"consumidores QNA no equivalentes: {name}")
        so = me[4]
        if so + size > len(source):
            raise ValueError("píxeles oficiales fuera de rango")
        if boxes:
            result = bytearray(before)
            for x0, y0, x1, y1 in boxes:
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        p = 2 * ctpk.pixel_index(x, y, width)
                        result[po + p:po + p + 2] = source[so + p:so + p + 2]
            result = bytes(result)
        else:
            result = before[:po] + source[so:so + size] + before[po + size:]
        if result == before:
            continue
        image, reference = ctpk.decode(result), ctpk.decode(source)
        if boxes:
            expected = ctpk.decode(before)
            for box in boxes:
                expected.paste(reference.crop(box), box[:2])
        else:
            expected = reference
        rgba = image.tobytes()
        if rgba != expected.tobytes():
            raise ValueError("píxeles RGBA no idénticos")
        out[offset:offset + len(result)] = result
        applied.append({"texture": name, "crc": f"{crc:08x}",
                        "consumer_parts": sum(consumers_j.values()),
                        "regions": boxes, "rgba_scope": "selected_regions" if boxes else "atlas",
                        "format": fmt, "dimensions": [width, height],
                        "pixel_range": [offset + po, offset + po + size],
                        "source_sha256": _sha(source), "rgba_sha256": _sha(rgba),
                        "rgba_exact": True, "alpha_exact": True, "color_error_max": 0})
    output = reenvolver_como(current, bytes(out), "keep") if applied else current
    reader_verified = False
    if len(output) > len(current):
        if codigo_lector is None or _sha(codigo_lector) != LECTOR_SSZL_SHA256:
            raise ValueError("crecimiento SSZL sin lector auditado")
        if output[:4] != b"SSZL" or current[:4] != b"SSZL":
            raise ValueError("crecimiento fuera de envoltura SSZL")
        packed, unpacked = struct.unpack_from("<II", output, 8)
        if packed >= unpacked or packed + 16 != len(output) or unpacked != len(base):
            raise ValueError("tamaños SSZL incompatibles")
        reader_verified = True
    if unwrap(output) != bytes(out):
        raise ValueError("roundtrip SSZL distinto")
    return output, {"applied": applied, "pending": [], "runtime_verified": False,
                    "qna_preserved": True, "nonpixel_preserved": True,
                    "consumer_contract": "all_128_byte_parts_identical_per_QNA_CRC",
                    "sszl_reader_verified": reader_verified, "unpacked_size": len(base),
                    "size_before": len(current), "size_after": len(output),
                    "original_sha256": _sha(japones), "before_sha256": _sha(current),
                    "after_sha256": _sha(output), "official_sha256": _sha(oficial)}


def construir_payloads_visibles(jp, spark, ogre, codigo_lector: bytes, *,
                                actuales: Mapping[str, bytes] | None = None
                                ) -> tuple[dict[str, bytes], dict]:
    """Siete familias compartidas JP/Ogre usadas por IE3; no escribe archivos.

Pasar en ``actuales`` los payloads de fase4 evita deshacer atlas previamente
traducidos. Se devuelven solamente paquetes cambiados para sobreponer al mapa.
"""
    payloads, rows = {}, []
    for family, names in ATLAS_VISIBLES.items():
        path = f"inazuma3_ogre/data_iz/a_menu/{family}.arc"
        source = spark.read("es/" + path)
        comprobar_fuentes_compartidas(source, ogre.read("es/" + path))
        regions = REGIONES_TUTORIAL if family == "system_b" else None
        selected = {name + ".tga" for name in names} | set(regions or {})
        output, detail = trasplantar_atlas_por_partes(
            jp.read(path), source, selected, regiones=regions,
            actual=(actuales or {}).get(path), codigo_lector=codigo_lector)
        rows.append({"path": path, "selected": sorted(selected),
                     "shared_source_identical": True, **detail})
        if detail["applied"]:
            payloads[path] = output
    return payloads, {"resources": rows, "payload_count": len(payloads),
                      "atlas_count": sum(len(row["applied"]) for row in rows),
                      "runtime_verified": False}
