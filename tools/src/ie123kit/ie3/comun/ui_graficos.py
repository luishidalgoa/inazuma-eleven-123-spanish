"""Trasplante sin pérdidas de atlas oficiales con contrato ARCV/QNA idéntico.

No recompone textos, no reescala ni recompresa píxeles. La entrada explícita
son atlas revisados; CTPK y QNA se leen mediante los parsers comunes.
"""
from __future__ import annotations

import hashlib
import struct
from itertools import pairwise
from pathlib import PurePosixPath

from ie123kit.nucleo.compresion.sszl import reenvolver_como, unwrap
from ie123kit.nucleo.contenedores.arcv import entries
from ie123kit.nucleo.graficos import ctpk
from ie123kit.nucleo.graficos.qna import QnaLayout
from ie123kit.nucleo.graficos.texturas import iter_ctpk

FAMILIAS_MENU = frozenset({
    "status_t.arc", "item_b.arc", "bag_b.arc", "organization_b.arc",
    "battle_member_b.arc", "battle_member_t.arc", "equip_b.arc", "equip_t.arc",
    "formation_b.arc", "sp_move_b.arc", "option_b.arc", "phone_b.arc", "phone_t.arc",
    "system_b.arc", "system_b_sb.arc", "field_t.arc", "field_icon_b.arc",
})
ATLAS_ROTULOS = (
    "_mes", "_msg", "_button", "_btn_", "_window", "_ranking", "position_icon",
    "_conf_plt", "_status_bg01", "_status_bg03", "_equip_",
)
# Revisión JP/ES por página, no inferida de CRC ni de carpetas. Desconocidos
# permanecen JP hasta revisar contenido, función y glosario, además del layout.
AYUDAS_REVISADAS = frozenset({
    0, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28,
    30, 31, 32, 33, 34, 35, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
    49, 50, 51, 52, 53, 54, 56, 57, 58, 61, 62, 66, 67, 74, 75, 76,
    80, 81, 82, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95,
})
AYUDAS_EXCLUIDAS = {
    29: "captura_oficial_con_siglas_no_PT_PE",
    36: "glosario_oficial_PE_energia_no_resistencia",
    37: "glosario_oficial_PE_energia_no_resistencia",
    48: "glosario_oficial_PE_energia_no_resistencia",
    55: "StreetPass_descarga_no_disponible_en_compilacion",
    59: "instruccion_StreetPass_ajena_a_compilacion",
    60: "menu_red_con_opciones_ajenas_a_compilacion",
    63: "descargas_Nintendo_Network_no_equivalentes",
    64: "descargas_Nintendo_Network_no_equivalentes",
    65: "descargas_Nintendo_Network_no_equivalentes",
    68: "captura_oficial_con_siglas_no_PT_PE",
    69: "enlace_Ogre_entre_consolas_no_equivalente",
    70: "fuente_oficial_sin_instrucciones",
    71: "fuente_oficial_sin_instrucciones",
    77: "opciones_extras_regionales_no_demostradas",
    78: "opciones_extras_regionales_no_demostradas",
    96: "captura_tres_equipos_duelo_no_equivalente_demostrado",
    97: "captura_tres_equipos_duelo_no_equivalente_demostrado",
    98: "StreetPass_expresamente_deshabilitado_en_compilacion",
}


def motivo_ayuda_pendiente(stem: str) -> str | None:
    """Solo habilita las páginas revisadas; no supone equivalencia regional."""
    if not stem.startswith("ie03o_tt") or not stem[8:].isdigit():
        return "familia_ayuda_sin_revision_semantica"
    number = int(stem[8:])
    if number in AYUDAS_REVISADAS:
        return None
    return AYUDAS_EXCLUIDAS.get(number, "pagina_ayuda_sin_revision_semantica")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tabla(raw: bytes) -> dict:
    table = entries(raw)
    by_crc = {crc: (offset, size) for offset, size, crc in table}
    if len(by_crc) != len(table):
        raise ValueError("CRC ARCV duplicado")
    spans = sorted((o, o + n) for o, n, _ in table)
    if any(a[1] > b[0] for a, b in pairwise(spans)):
        raise ValueError("entradas ARCV solapadas")
    return by_crc


def trasplantar_atlas(japones: bytes, oficial: bytes,
                     nombres: set[str], *, codigo_lector: bytes | None = None,
                     layout_externo: tuple[bytes, bytes, str] | None = None) -> tuple[bytes, dict]:
    """Copia solo bytes de píxeles, con formato y QNA idénticos; jamás RGB→ETC.

Los nombres son una selección explícita, no una detección automática de texto.
Se exige igualdad de todas las entradas no CTPK; referencias/estados/animación
quedan así preservados. Los bytes exteriores a píxeles permanecen literales.
"""
    jp, es = unwrap(japones), unwrap(oficial)
    tj, te = _tabla(jp), _tabla(es)
    if tj.keys() != te.keys():
        raise ValueError("identidades CRC ARCV diferentes")
    qnas = []
    textures = {}
    for crc, (o, n) in tj.items():
        eo, en = te[crc]
        before, source = jp[o:o + n], es[eo:eo + en]
        if before[:4] != b"CTPK":
            if before != source:
                raise ValueError(f"layout/no-texto distinto en CRC {crc:08x}")
            if before[:8] == b" QNA 051":
                qnas.append(QnaLayout(before))
            continue
        if source[:4] != b"CTPK":
            raise ValueError("tipo CTPK distinto")
        mj, me = ctpk.metadata(before), ctpk.metadata(source)
        if mj[0] in textures:
            raise ValueError("nombre CTPK duplicado")
        textures[mj[0]] = (o, n, before, source, mj, me, crc)
    alias = None
    if not qnas and layout_externo is not None:
        lj, le, alias = layout_externo
        rj, re = unwrap(lj), unwrap(le)
        ij, ie = _tabla(rj), _tabla(re)
        if ij.keys() != ie.keys() or len(textures) != 1 or len(nombres) != 1:
            raise ValueError("reemplazo dinámico no es atlas único con identidad estable")
        ghosts = []
        for crc, (o, n) in ij.items():
            eo, en = ie[crc]
            x, y = rj[o:o + n], re[eo:eo + en]
            if x[:4] == b"CTPK":
                if ctpk.metadata(x)[:4] != ctpk.metadata(y)[:4]:
                    raise ValueError("placeholder CTPK externo incompatible")
                ghosts.append(ctpk.metadata(x))
            else:
                if x != y:
                    raise ValueError("consumidor QNA externo distinto")
                if x[:8] == b" QNA 051":
                    qnas.append(QnaLayout(x))
        target_meta = next(iter(textures.values()))[4]
        if (len(qnas) != 1 or len(qnas[0].partes) != 1 or len(ghosts) != 1
                or ghosts[0][0].removesuffix(".tga") != alias
                or ghosts[0][1:3] != target_meta[1:3]
                or [t.removesuffix(".tga") for t in qnas[0].texturas] != [alias]):
            raise ValueError("contrato del placeholder dinámico no demostrado")
    if not qnas:
        raise ValueError("atlas sin consumidor QNA")
    if not nombres <= textures.keys():
        raise ValueError("textura solicitada ausente")
    out = bytearray(jp)
    applied, pending = [], []
    for name in sorted(nombres):
        o, n, before, source, mj, me, crc = textures[name]
        if mj[:4] != me[:4] or mj[5] != me[5]:
            pending.append({"texture": name, "reason": "formato_dimensiones_no_identicos",
                            "jp": mj, "es": me})
            continue
        regions = sorted({tuple(box) for q in qnas for box in q.regions_for(alias or name)})
        if not regions:
            pending.append({"texture": name, "reason": "sin_referencia_QNA"})
            continue
        _, width, height, fmt, jo, size = mj
        eo = me[4]
        if jo + size > n or eo + size > len(source):
            raise ValueError("píxeles CTPK fuera de rango")
        if any(not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height)
               for x0, y0, x1, y1 in regions):
            pending.append({"texture": name, "reason": "UV_original_fuera_atlas_no_modelado",
                            "regions": regions})
            continue
        target = before[:jo] + source[eo:eo + size] + before[jo + size:]
        if target == before:
            continue
        # Decodificar ambas fuentes permite detectar formatos multi-mip o
        # offsets incoherentes; comparar también alfa, no solo RGB.
        official_rgba, result_rgba = ctpk.decode(source), ctpk.decode(target)
        if result_rgba.tobytes() != official_rgba.tobytes():
            raise ValueError("píxeles RGBA diferentes tras trasplante")
        if ctpk.metadata(target) != mj:
            raise ValueError("metadatos CTPK alterados")
        out[o:o + n] = target
        applied.append({"texture": name, "crc": f"{crc:08x}", "format": fmt,
                        "dimensions": [width, height], "regions": regions,
                        "source_sha256": _sha(source), "before_sha256": _sha(before),
                        "after_sha256": _sha(target), "rgba_sha256": _sha(result_rgba.tobytes()),
                        "rgba_exact": True, "alpha_exact": True, "color_error_max": 0,
                        "pixel_range": [o + jo, o + jo + size]})
    output = reenvolver_como(japones, bytes(out), "keep") if applied else japones
    reader_verified = False
    if len(output) > len(japones) and codigo_lector is not None:
        if _sha(codigo_lector) != "ae11511902ab4ead12617d5d52099aad2f238037588482651aac5cbae8bea18e":
            raise ValueError("lector SSZL no coincide con ejecutable JP auditado")
        if output[:4] != b"SSZL" or japones[:4] != b"SSZL":
            raise ValueError("crecimiento ajeno a envoltura SSZL")
        if len(unwrap(output)) != len(jp):
            raise ValueError("tamaño ARCV descomprimido alterado")
        packed, unpacked = struct.unpack_from("<II", output, 8)
        if packed >= unpacked or packed + 16 != len(output):
            raise ValueError("SSZL no cumple contrato packed < unpacked")
        reader_verified = True
    if len(output) > len(japones) and not reader_verified:
        # Sin la prueba del lector conservamos la política inicial.
        pending.extend({"texture": row["texture"], "reason": "crecimiento_SSZL_no_demostrado"}
                       for row in applied)
        applied = []
        output = japones
    if entries(unwrap(output)) != entries(jp):
        raise ValueError("tabla ARCV alterada")
    return output, {"before_sha256": _sha(japones), "after_sha256": _sha(output),
                    "official_sha256": _sha(oficial), "applied": applied, "pending": pending,
                    "qna_identical": True, "runtime_verified": False,
                    "size_before": len(japones), "size_after": len(output),
                    "unpacked_size": len(jp), "sszl_reader_verified": reader_verified,
                    "dynamic_alias": alias,
                    "external_layout_sha256": _sha(layout_externo[0]) if alias else None}


def comprobar_fuentes_compartidas(spark: bytes, ogre: bytes) -> None:
    """Las mismas rutas deben tener la misma fuente, no gana el último perfil."""
    if spark != ogre:
        raise ValueError("conflicto entre fuentes oficiales de recurso compartido")


def construir_payloads_graficos(jp, spark, ogre, codigo_lector: bytes,
                                cro_jp: bytes, cro_es: bytes) -> tuple[dict[str, bytes], dict]:
    """Familias de menús y ayudas verificables, sin escribir contenedores/ROMs.

Las fuentes ES se comparan también en rutas aparentemente Ogre: Spark contiene
esos recursos y no se presupone exclusividad por el nombre de directorio.
"""
    payloads, rows = {}, []
    for path in jp.index:
        if not path.startswith(("inazuma3/", "inazuma3_ogre/")):
            continue
        help_family = next((s for s in ("help_b", "help_t")
                            if f"/a_data_replace/{s}/data/" in path), None)
        if not help_family and PurePosixPath(path).name not in FAMILIAS_MENU:
            continue
        official_path = "es/" + path
        row = {"path": path, "category": "ayudas_graficas" if help_family else "rotulos_menu"}
        if not spark.exists(official_path) or not ogre.exists(official_path):
            rows.append({**row, "blocked": "fuente_oficial_no_disponible_en_ambos"})
            continue
        source = spark.read(official_path)
        comprobar_fuentes_compartidas(source, ogre.read(official_path))
        textures = list(iter_ctpk(jp.read(path)))
        names = {t.nombre for t in textures if help_family or any(k in t.nombre for k in ATLAS_ROTULOS)}
        if not names:
            continue
        external = None
        if help_family:
            stem = PurePosixPath(path).stem
            semantic_reason = motivo_ayuda_pendiente(stem)
            if semantic_reason is not None:
                rows.append({**row, "blocked": semantic_reason,
                             "semantic_review": "pending_or_incompatible"})
                continue
            row["semantic_review"] = "official_page_reviewed_JP_ES"
            literal = stem.encode("ascii") + b".ctpk\0"
            if literal not in cro_jp or literal not in cro_es:
                rows.append({**row, "blocked": "sin_identidad_consumidor_ctpk_JP_ES"})
                continue
            if names != {stem + ".tga"}:
                raise ValueError("atlas de ayuda no coincide con identidad del recurso")
            parts = path.split("/data/")[0] + "/parts.arc"
            alias = "ie03_help_bg_ghost01" if help_family == "help_b" else "ie03_help_bg_t_ghost01"
            comprobar_fuentes_compartidas(spark.read("es/" + parts), ogre.read("es/" + parts))
            external = (jp.read(parts), spark.read("es/" + parts), alias)
            row["consumer_literal_jp"] = cro_jp.index(literal)
            row["consumer_literal_es"] = cro_es.index(literal)
            row["consumer_layout"] = parts
        else:
            # Este atlas tiene idéntico QNA pero los símbolos L/R y flechas
            # cambian de celda: no es una traducción semánticamente demostrada.
            names.discard("ie03_menu_equip_parts_b02.tga")
            if not names:
                rows.append({**row, "blocked": "iconos_equipacion_celdas_no_equivalentes"})
                continue
        try:
            payload, detail = trasplantar_atlas(jp.read(path), source, names,
                                              codigo_lector=codigo_lector,
                                              layout_externo=external)
        except ValueError as exc:
            rows.append({**row, "blocked": str(exc), "selected": sorted(names)})
            continue
        rows.append({**row, **detail, "selected": sorted(names),
                     "shared_source_identical": True})
        if detail["applied"]:
            payloads[path] = payload
    return payloads, {"resources": rows, "runtime_verified": False,
                      "payload_count": len(payloads),
                      "atlas_count": sum(len(r.get("applied", [])) for r in rows)}
