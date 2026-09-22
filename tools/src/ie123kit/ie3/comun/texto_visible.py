"""Texto visible IE3 con correspondencia oficial estructural demostrada.

Esta fase se limita deliberadamente a la tabla SSD de ``eve``: rótulos de
objetivo, nombres de lugar y el nombre oculto del interlocutor. Solo se acepta
una correspondencia con misma instrucción/slot y anclas inmediatas de bytecode;
el orden de los campos no es una identidad.

No incluye ``evet`` (diálogo), fuentes, CRO, gráficos, ni las tablas de menú:
sus formatos/campos consumidores no comparten todavía un contrato auditado.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from ie123kit.ie3.comun.b123 import B123Archive
from ie123kit.ie3.comun.paquetes import leer_paquete, reconstruir_paquete
from ie123kit.ie3.comun.referencias import instrucciones
from ie123kit.ie3.comun.reinsert import MAX_CUERPO, _codificable, _emitir
from ie123kit.ie3.comun.sheet import TEXT_OPCODES
from ie123kit.ie3.comun.ssd import SSD_HEADER_SIZE, parse_ssd
from ie123kit.ie3.comun.text import TextTable
from ie123kit.nucleo.texto.sjis_portador import es_encode


@dataclass(frozen=True)
class PerfilTextoVisible:
    """Solo las rutas necesarias para el recurso SSD común de cada versión."""

    nombre: str
    recurso: str


PERFILES = {
    "spark": PerfilTextoVisible("spark", "inazuma3/data_iz/script"),
    "ogre": PerfilTextoVisible("ogre", "inazuma3_ogre/data_iz/script"),
}

# El orden no basta como prueba. Esta es la transición de rol observada en
# ambos pares oficiales completos (Spark↔Rayo y Ogre↔Amenaza): opcode y slot
# físico del texto. Cualquier pareja nueva debe auditarse antes de añadirse.
ROLES_CONFIRMADOS = {
    (0x2019, 3): (0x201A, 3),
    (0x201A, 3): (0x201A, 3),
    (0x201C, 3): (0x201D, 3),
    (0x201D, 3): (0x201D, 3),
    (0x3019, 2): (0x3019, 2),
    (0x4037, 2): (0x4037, 2),
    (0x4037, 3): (0x4037, 3),
}


def _visibles(block, table):
    """Registros SSD que la investigación oficial confirmó visibles."""
    _info, records = parse_ssd(block, table)
    return [record for record in records if record.opcode in TEXT_OPCODES]


def _firma_ancla(instruction):
    """Código invariante: los punteros tipo 3 no son identidad textual."""
    return (
        instruction.ident,
        instruction.opcode,
        instruction.tipos,
        tuple(None if kind == 3 else value for kind, value in zip(instruction.tipos, instruction.valores)),
    )


def _argumentos_no_texto(instruction):
    return instruction.tipos, tuple(
        None if kind == 3 else value for kind, value in zip(instruction.tipos, instruction.valores)
    )


def _alinear_visibles_estructural(jp_rows, es_rows, jp_code, es_code):
    """Correspondencia cerrada por misma instrucción/slot y dos anclas vecinas.

    No usa el ordinal como identidad. Los vecinos inmediatos impiden insertar
    otro campo visible entre anclas; tipo3 se ignora solo en su valor-puntero.
    """
    jp_by_id = {item.ident: (index, item) for index, item in enumerate(jp_code)}
    es_by_id = {item.ident: (index, item) for index, item in enumerate(es_code)}
    mapping, transitions, skipped = {}, [], []
    for ordinal, jp_row in enumerate(jp_rows):
        source_role = (jp_row.opcode, jp_row.argument)
        candidates = [row for row in es_rows if row.instruction == jp_row.instruction and row.argument == jp_row.argument]
        if len(candidates) != 1:
            skipped.append({"ordinal": ordinal, "instruction": jp_row.instruction, "reason": "instruccion_o_slot_visible_no_univoco"})
            continue
        es_row = candidates[0]
        target_role = (es_row.opcode, es_row.argument)
        if ROLES_CONFIRMADOS.get(source_role) != target_role:
            skipped.append({"ordinal": ordinal, "instruction": jp_row.instruction, "reason": "rol_visible_no_confirmado"})
            continue
        jp_pos, jp_instruction = jp_by_id.get(jp_row.instruction, (None, None))
        es_pos, es_instruction = es_by_id.get(es_row.instruction, (None, None))
        if jp_instruction is None or es_instruction is None or jp_pos in (0, len(jp_code) - 1) or es_pos in (0, len(es_code) - 1):
            skipped.append({"ordinal": ordinal, "instruction": jp_row.instruction, "reason": "anclas_de_codigo_ausentes"})
            continue
        if _argumentos_no_texto(jp_instruction) != _argumentos_no_texto(es_instruction):
            skipped.append({"ordinal": ordinal, "instruction": jp_row.instruction, "reason": "argumentos_no_texto_distintos"})
            continue
        # El opcode del objetivo puede tener la transición oficial permitida;
        # las anclas, en cambio, han de ser literales en ambos bytecodes.
        left_ok = _firma_ancla(jp_code[jp_pos - 1]) == _firma_ancla(es_code[es_pos - 1])
        right_ok = _firma_ancla(jp_code[jp_pos + 1]) == _firma_ancla(es_code[es_pos + 1])
        if not left_ok or not right_ok:
            skipped.append({"ordinal": ordinal, "instruction": jp_row.instruction, "reason": "anclas_codigo_distintas"})
            continue
        mapping[jp_row.key] = es_row.text
        transitions.append({
            "ordinal": ordinal,
            "jp": {"instruction": jp_row.instruction, "argument": jp_row.argument, "opcode": f"0x{jp_row.opcode:04X}", "size": jp_row.size},
            "es": {"instruction": es_row.instruction, "argument": es_row.argument, "opcode": f"0x{es_row.opcode:04X}", "size": es_row.size},
            "anchors": {"before": jp_code[jp_pos - 1].ident, "after": jp_code[jp_pos + 1].ident},
        })
    return mapping, transitions, skipped


def reemplazar_ssd_visible(block: bytes, traducciones: dict[tuple[int, int], str]):
    """Reemplaza únicamente registros SSD identificados por ``(id, slot)``.

    La sección de instrucciones se conserva byte a byte.  Las entradas no
    seleccionadas se copian literalmente, incluido el relleno residual que
    IE3 deja tras el NUL.  Las seleccionadas se codifican de forma estricta,
    sin truncamiento, y se vuelven a parsear antes de devolverse.
    """
    info, records = parse_ssd(block, TextTable.identity())
    table_start = SSD_HEADER_SIZE + info["code_len"]
    out = bytearray()
    applied = []

    for record in records:
        original = block[record.offset : record.offset + record.size]
        target = traducciones.get(record.key)
        if target is None:
            out.extend(original)
            continue
        if not _codificable(target):
            raise ValueError(f"texto visible no codificable: {target!r}")
        body = es_encode(target, 1 << 30)
        if body == record.raw:
            # Un oficial idéntico (incluido '?') no debe normalizar padding ni
            # figurar como texto nuevo.
            out.extend(original)
            continue
        if len(body) > len(record.raw):
            raise ValueError("capacidad_consumidor_visible_no_demostrada")
        if len(body) > MAX_CUERPO:
            raise ValueError(f"texto visible supera cuerpo de registro: {target!r}")
        size = record.size
        out.extend(_emitir(record.instruction, record.argument, body, size))
        applied.append({
            "instruction": record.instruction,
            "argument": record.argument,
            "opcode": f"0x{record.opcode:04X}",
            "before": record.size,
            "after": size,
        })

    if not applied:
        return block, applied
    header = bytearray(block[:SSD_HEADER_SIZE])
    if len(out) != info["string_len"]:
        raise ValueError("SSD visible: tabla creció sin cota de consumidor")
    result = bytes(header) + block[SSD_HEADER_SIZE:table_start] + bytes(out)
    verified, after = parse_ssd(result, TextTable.identity())
    if len(after) != len(records) or verified["code_len"] != info["code_len"]:
        raise ValueError("SSD visible: cambió el número de registros o el código")
    if result[SSD_HEADER_SIZE:table_start] != block[SSD_HEADER_SIZE:table_start]:
        raise ValueError("SSD visible: cambió la sección de instrucciones")
    return result, applied


def construir_payloads_texto_visible(jp_archive, official_archive, perfil="spark"):
    """Devuelve ``({ruta: payload}, informe)`` sin escribir ningún archivo.

    ``jp_archive`` contiene el recopilatorio y ``official_archive`` el juego
    europeo. La cardinalidad solo es un diagnóstico: cada texto exige identidad
    estructural independiente, sin correspondencia posicional. El llamador es
    responsable de incorporar los payloads en una candidata ya controlada.
    """
    if isinstance(perfil, str):
        try:
            perfil = PERFILES[perfil]
        except KeyError as exc:
            raise ValueError(f"perfil visible desconocido: {perfil}") from exc
    if not isinstance(jp_archive, B123Archive) or not isinstance(official_archive, B123Archive):
        raise TypeError("se requieren B123Archive abiertos; esta función no escribe archivos")

    resource = perfil.recurso
    jp_h = jp_archive.read(f"{resource}/eve.pkh")
    jp_b = jp_archive.read(f"{resource}/eve.pkb")
    es_h = official_archive.read(f"es/{resource}/eve.pkh")
    es_b = official_archive.read(f"es/{resource}/eve.pkb")
    jp_blocks, _ = leer_paquete(jp_h, jp_b, "eve")
    es_blocks, _ = leer_paquete(es_h, es_b, "eve")
    es_table = TextTable.from_codetable(official_archive.read("font/CodeTable.bin"))

    replacements, pairs, skipped, transitions = {}, Counter(), [], []
    jp_visible_total = sameevent_official = identity_verified = original_already_identical = 0
    applied = 0
    for event, jp_block in jp_blocks.items():
        jp_rows = _visibles(jp_block, TextTable.identity())
        jp_visible_total += len(jp_rows)
        if not jp_rows:
            continue
        if event not in es_blocks:
            skipped.append({"event": event, "jp": len(jp_rows), "es": 0, "reason": "evento_oficial_ausente"})
            continue
        es_rows = _visibles(es_blocks[event], es_table)
        sameevent_official += len(jp_rows)
        if len(jp_rows) != len(es_rows):
            skipped.append({"event": event, "jp": len(jp_rows), "es": len(es_rows),
                            "reason": "cardinalidad_visible_distinta"})
            continue
        mapping, event_transitions, event_skipped = _alinear_visibles_estructural(
            jp_rows, es_rows, instrucciones(jp_block), instrucciones(es_blocks[event])
        )
        identity_verified += len(mapping)
        original_rows = {row.key: row for row in jp_rows}
        too_long = []
        for key, target in mapping.items():
            if _codificable(target) and es_encode(target, 1 << 30) == original_rows[key].raw:
                original_already_identical += 1
            elif not _codificable(target) or len(es_encode(target, 1 << 30)) > len(original_rows[key].raw):
                too_long.append(key)
        for key in too_long:
            mapping.pop(key)
            event_skipped.append({"instruction": key[0], "argument": key[1], "reason": "capacidad_consumidor_visible_no_demostrada"})
        for transition in event_transitions:
            transition["event"] = event
            pairs[(int(transition["jp"]["opcode"], 16), int(transition["es"]["opcode"], 16))] += 1
            transitions.append(transition)
        skipped.extend({"event": event, **entry} for entry in event_skipped)
        new_block, changed = reemplazar_ssd_visible(jp_block, mapping)
        if changed:
            replacements[event] = new_block
            applied += len(changed)

    new_h, new_b, pack_report = reconstruir_paquete(jp_h, jp_b, "eve", replacements)
    reextracted, _metadata = leer_paquete(new_h, new_b, "eve")
    for event, block in replacements.items():
        if reextracted[event] != block:
            raise ValueError(f"reextracción visible difiere en evento {event}")
    paths = {
        f"{resource}/eve.pkh": new_h,
        f"{resource}/eve.pkb": new_b,
    }
    report = {
        "profile": asdict(perfil),
        "category": "objetivos_lugares_nombres_ocultos_ssd",
        "payload_paths": sorted(paths),
        "records_applied": applied,
        "events_changed": len(replacements),
        "opcode_pairs": [
            {"jp": f"0x{jp:04X}", "es": f"0x{es:04X}", "count": count}
            for (jp, es), count in sorted(pairs.items())
        ],
        "transitions": transitions,
        "denominators": {
            "jp_visible_total": jp_visible_total,
            "sameevent_official": sameevent_official,
            "identity_verified": identity_verified,
            "original_already_identical": original_already_identical,
            "new_vs_original": applied,
            "emitible_sin_crecer": applied + original_already_identical,
        },
        "skipped": skipped,
        "pack_report": pack_report,
        "pending": [
            "0x402F etiqueta fija: sin equivalencia ES demostrada; no se toca",
            "menus_descripciones_cadenas_partido: tablas JP/ES de formato o tamaño distinto; falta contrato de campos/consumidor",
            "texto_en_graficos: categoría independiente, sin payload de texto",
            "crecimiento_visible: solo 301D tiene consumidor de tamaño variable demostrado; estos campos conservan el tamaño SSD original",
        ],
    }
    return paths, report
