"""Casos visibles que no cubrían los adaptadores anteriores: ficha/título/misión.

Sólo payloads; ningún cambio de CRO, fuente, encoder, instrucciones ni save.
"""
import struct
from collections import Counter, defaultdict

from ie123kit.ie3.comun.nombres import _encode_target
from ie123kit.ie3.comun.paquetes import leer_paquete, reconstruir_paquete
from ie123kit.ie3.comun.presentacion_nombres import _identidad, _registros
from ie123kit.ie3.comun.referencias import instrucciones
from ie123kit.ie3.comun.ssd import parse_ssd
from ie123kit.ie3.comun.tablas_ui import leer_ranura
from ie123kit.ie3.comun.text import TextTable, load_text_table
from ie123kit.ie3.comun.texto_visible import reemplazar_ssd_visible

EVENTO_INTRO = 32500100
ID_MISION_INTRO = 35080060


def nombres_completos(japonesa: bytes, europea: bytes, actual: bytes,
                      tabla: TextTable) -> tuple[bytes, dict]:
    """Campo completo +0:28, ID único+metadata; conserva corto y referencias JP."""
    jp, es, current = map(_registros, (japonesa, europea, actual))
    if len(jp) != len(current):
        raise ValueError("nombres completos: cardinalidad actual distinta")
    counts = Counter(map(_identidad, jp))
    sources = defaultdict(list)
    for index, record in enumerate(es):
        sources[_identidad(record)].append((index, record))
    output = bytearray(actual)
    applied, pending = [], []
    for index, (original, now) in enumerate(zip(jp, current, strict=True)):
        ident = _identidad(original)
        # Existing short-name translations are allowed; all other fields are JP.
        if now[44:] != original[44:]:
            raise ValueError("nombres completos: metadata/referencias actuales distintas")
        candidates = sources[ident]
        if not ident or counts[ident] != 1 or len(candidates) != 1:
            pending.append({"record": index, "reason": "identity"})
            continue
        source_index, source = candidates[0]
        if original[44:94] != source[44:94] or original[95:102] != source[95:102]:
            pending.append({"record": index, "reason": "metadata"})
            continue
        fields = [record[:28] for record in (original, source, now)]
        if any(b"\0" not in field for field in fields):
            raise ValueError("nombre completo sin NUL en28bytes")
        raw, source_raw, inherited = [field.split(b"\0", 1)[0] for field in fields]
        text = tabla.decode(source_raw, errors="strict")
        encoded = _encode_target(text)
        if not raw or not source_raw or encoded is None or len(encoded) >= 28:
            pending.append({"record": index, "official": text, "reason": "empty_encoding_or_capacity"})
            continue
        if inherited not in (raw, encoded):
            raise ValueError(f"nombre completo heredado distinto: {index}")
        if inherited == encoded:
            continue
        start = index * 104
        output[start:start + 28] = encoded.ljust(28, b"\0")
        applied.append({"record": index, "id": ident, "source_record": source_index,
                        "official": text, "offset": start, "encoded_bytes": len(encoded)})
    for i, before in enumerate(current):
        if output[i * 104 + 28:(i + 1) * 104] != before[28:]:
            raise AssertionError("campo corto/metadata/referencia modificado")
    return bytes(output), {"applied": applied, "pending": pending, "field": "unitbase+0:28",
                           "size_preserved": len(output) == len(actual), "runtime_verified": False}


def titulos_rpg(jp_dat: bytes, es_dat: bytes, jp_pool: bytes,
                es_pool: bytes, tabla: TextTable) -> tuple[bytes, dict]:
    """Título seleccionado por condiciones de rpgtitle.dat, referenciau16+1E×32."""
    if len(jp_dat) != 48 * 32 or len(es_dat) != len(jp_dat):
        raise ValueError("rpgtitle: geometría de tabla distinta")
    if jp_dat != es_dat:
        raise ValueError("rpgtitle: condiciones/identidades distintas, no asumir correspondencia")
    output = bytearray(jp_pool)
    applied, pending, owners = [], [], defaultdict(list)
    for index in range(48):
        pointer = struct.unpack_from("<H", jp_dat, index * 32 + 30)[0]
        owners[pointer].append(index)
    for pointer, records in owners.items():
        raw, offset, capacity = leer_ranura(jp_pool, pointer)
        official, _, _ = leer_ranura(es_pool, pointer)
        text = tabla.decode(official, errors="strict")
        encoded = _encode_target(text)
        # Consumer JP reads19 bytes; EU reads32. Never import that larger capacity.
        if not raw or not official or encoded is None or len(encoded) >= min(19, capacity):
            pending.append({"records": records, "pointer": pointer, "official": text,
                            "reason": "empty_encoding_or_consumer_capacity19"})
            continue
        if encoded == raw:
            continue
        output[offset:offset + capacity] = encoded.ljust(capacity, b"\0")
        applied.append({"records": records, "pointer": pointer, "offset": offset,
                        "official": text, "encoded_bytes": len(encoded)})
    return bytes(output), {"applied": applied, "pending": pending, "conditions_unchanged": True,
                           "consumer_capacity": 19, "runtime_verified": False}


def recursos_ficha_y_titulo(perfil, japonesa, europea, actual):
    """Nombres completos compuestos sobre actual; rpgtitle generado desde originalJP."""
    prefix = perfil.recurso.rsplit("/", 1)[0] + "/logic/"
    table = load_text_table(europea)
    name = prefix + "unitbase.dat"
    full, names_report = nombres_completos(japonesa.read(name), europea.read("es/" + name),
                                           actual.read(name), table)
    titles, titles_report = titulos_rpg(japonesa.read(prefix + "rpgtitle.dat"),
                                       europea.read("es/" + prefix + "rpgtitle.dat"),
                                       japonesa.read(prefix + "rpgtitle.STR"),
                                       europea.read("es/" + prefix + "rpgtitle.STR"), table)
    return {name: full, prefix + "rpgtitle.STR": titles}, {"full_names": names_report,
                                                          "rpgtitle": titles_report}


def _mision(block, table, opcode):
    code = instrucciones(block)
    found = [(i, ins) for i, ins in enumerate(code)
             if ins.opcode == opcode and ins.tipos == (1, 1, 3)
             and ins.valores[:2] == (ID_MISION_INTRO, 1)]
    if len(found) != 1:
        raise ValueError("misión intro: consumidor no unívoco")
    index, ins = found[0]
    if index < 2 or index + 2 >= len(code):
        raise ValueError("misión intro: faltan anclas")
    before2, before, after, after2 = code[index-2], code[index-1], code[index+1], code[index+2]
    expected = [
        (before2, -2, 0x6014, (1,), (0,)),
        (before, -1, 0x6001, (1, 1), (2, ins.ident + 2)),
        (after, 1, 0x3075, (1, 1, 1), (0, 0, 500)),
        (after2, 2, 0x6002, (1, 1), (2, ins.ident - 1)),
    ]
    for neighbour, relative, op, types, values in expected:
        if (neighbour.ident, neighbour.opcode, neighbour.tipos, neighbour.valores) != (
                ins.ident + relative, op, types, values):
            raise ValueError("misión intro: contexto de ramas distinto")
    _, texts = parse_ssd(block, table)
    owners = [row for row in texts if row.key == (ins.ident, 3)]
    if len(owners) != 1:
        raise ValueError("misión intro: texto no unívoco")
    return ins, owners[0]


def mision_intro_actual(jp_block: bytes, es_block: bytes, current_block: bytes,
                        tabla: TextTable) -> tuple[bytes, dict]:
    """Mismo IDmisión+ramas, sin exigir mismos IDs de instrucción entre idiomas."""
    ji, jr = _mision(jp_block, TextTable.identity(), 0x201C)
    ei, er = _mision(es_block, tabla, 0x201D)
    ci, cr = _mision(current_block, TextTable.identity(), 0x201C)
    if ji != ci:
        raise ValueError("misión intro: consumidor actual difiere del original")
    encoded = _encode_target(er.text)
    if encoded is None or len(encoded) > len(jr.raw):
        raise ValueError("misión intro: no cabe sin crecimiento")
    if cr.raw not in (jr.raw, encoded):
        raise ValueError("misión intro: texto actual no esperado")
    # Existing helper preserves code and every unrelated record exactly.
    result, changed = reemplazar_ssd_visible(current_block, {cr.key: er.text})
    _, checked = parse_ssd(result, TextTable.identity())
    if next(r.raw for r in checked if r.key == cr.key) != encoded:
        raise AssertionError("misión intro: reextracción incorrecta")
    return result, {"mission_id": ID_MISION_INTRO, "event": EVENTO_INTRO,
                    "instruction_jp": ji.ident, "instruction_es": ei.ident,
                    "official": er.text, "encoded_bytes": len(encoded),
                    "original_bytes": len(jr.raw), "changed": bool(changed),
                    "no_growth": len(result) == len(current_block), "runtime_verified": False}


def paquete_mision_intro(jp_h, jp_b, es_h, es_b, actual_h, actual_b, tabla):
    """Devuelve pareja PKH/PKB sobre la versión actual, sin pisar 301D recolocados."""
    jp, _ = leer_paquete(jp_h, jp_b, "eve")
    es, _ = leer_paquete(es_h, es_b, "eve")
    current, _ = leer_paquete(actual_h, actual_b, "eve")
    result, report = mision_intro_actual(jp[EVENTO_INTRO], es[EVENTO_INTRO],
                                        current[EVENTO_INTRO], tabla)
    h, b, pack = reconstruir_paquete(actual_h, actual_b, "eve", {EVENTO_INTRO: result})
    return h, b, {"mission": report, "pack": pack}
