"""Campos .STR IE3 por consumidor, identidad y ranura original, sin crecimiento."""
from __future__ import annotations

import hashlib
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass

from ie123kit.ie3.comun.items import _table, _unicos_por_identidad
from ie123kit.ie3.comun.reinsert import _codificable
from ie123kit.ie3.comun.text import TextTable, load_text_table
from ie123kit.nucleo.registros.tabla_fija import escribir_campo
from ie123kit.nucleo.texto.sjis_portador import avance, es_encode


@dataclass(frozen=True)
class Familia:
    nombre: str
    paso: int
    cantidad: int
    campos: tuple[tuple[str, int, int], ...]
    # offset u16 de referencia; capacidad del lector incluida la terminación.
    escala_es: int = 32


TECNICAS = Familia("command", 36, 512, (("nombre", 24, 32), ("descripcion", 26, 128)))
OBJETOS = Familia("item", 44, 1024, (("descripcion", 42, 128),))
TACTICAS = Familia("tacticscmd", 20, 64, (("nombre", 12, 32), ("descripcion", 14, 128)))
FICHAS = Familia("unitbase", 104, 2582, (("descripcion", 102, 128),), escala_es=256)

ANCLAS_CONSUMIDOR = {
    0x187BD0: "020c51e3d4079035811181300000a023010180301eff2fe1",
    0x10D34C: "b801d0e1800281e0",
    0x113280: "ba01d0e18030a0e3611f84e28022a0e168008fe28f1b01eb",
    0xD24D0: "ba02d0e18030a0e3911f84e28022a0e178008fe2fb1e02eb",
    0x16543C: "400051e30c089035011181300000a023010180301eff2fe1",
    0x126EB8: "be00d0e18030a0e3911f84e28022a0e184008fe281cc00eb",
    0xD2490: "b616d5e1000050e378008f129c008f028122a0e18030a0e3911f84e2091f02eb",
    0x2462DC: "852285e00220d0e7010052e10d00001a2020a0e3",
    0x246300: "851285e0011081e2012080e0bf1f8fe218008de285e8f6eb",
    0x246408: "00c280e000538ce005c0d2e7ff005ce30100000a",
    0x246464: "00c280e000538ce005c0d2e7ff005ce30100000a",
    0x15A6E8: "34109de50cd08de21920a0e3f04fbde88e97faea018088e2140058e3200080e276ffffba",
    0x18F804: "280090e5d43491e5d01491e50320a0e1242bffeb",
}
ANCLAS_CONSUMIDOR_ES = {
    0xD71BC: "b616d5e1000050e378008f129c008f020124a0e1013ca0e3911f84e2424002eb",
    0xD71FC: "ba02d0e1013ca0e3911f84e28022a0e178008fe2344002eb",
    0x11B3E4: "ba01d0e1013ca0e3611f84e28022a0e168008fe2ba2f01eb",
    0x132490: "be00d0e1013ca0e3911f84e28022a0e184008fe28fd300eb",
    0x115454: "b801d0e1800281e0",
}


def verificar_consumidor_europeo(cro: bytes) -> dict:
    """Verifica separadamente escalas EU, incluida unitbase ×256 (JP ×32)."""
    for offset, expected in ANCLAS_CONSUMIDOR_ES.items():
        payload = bytes.fromhex(expected)
        if cro[offset:offset + len(payload)] != payload:
            raise ValueError(f"lector STR europeo inesperado en {offset:#x}")
    return {"sha256": _sha(cro), "anchors": len(ANCLAS_CONSUMIDOR_ES),
            "source_scales": {"unitbase": 256, "item": 32, "command": 32, "tacticscmd": 32},
            "modified": False}


def verificar_consumidor(cro: bytes) -> dict:
    """Anclas de los lectores; no modifica ni normaliza el ejecutable."""
    for offset, expected in ANCLAS_CONSUMIDOR.items():
        payload = bytes.fromhex(expected)
        if cro[offset:offset + len(payload)] != payload:
            raise ValueError(f"lector STR inesperado en {offset:#x}")
    return {"sha256": _sha(cro), "anchors": len(ANCLAS_CONSUMIDOR), "modified": False}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leer_ranura(pool: bytes, pointer: int, escala: int = 32) -> tuple[bytes, int, int]:
    """Referencia con escala del consumidor, nunca deducida del tamaño de lectura."""
    if escala not in (32, 256):
        raise ValueError("escala de referencia STR no auditada")
    start = pointer * escala
    if start >= len(pool):
        raise ValueError("referencia STR fuera del recurso")
    nul = pool.find(b"\0", start)
    if nul < 0:
        raise ValueError("cadena STR sin NUL")
    end = (nul + escala) // escala * escala
    if end > len(pool) or any(pool[nul:end]):
        raise ValueError("padding STR distinto de NUL o ranura incompleta")
    return pool[start:nul], start, end - start


def _plain(dat: bytes, family: Familia) -> bytes:
    if len(dat) != family.paso * family.cantidad:
        raise ValueError(f"{family.nombre}.dat: geometría distinta")
    return _table(dat).to_bytes() if family == OBJETOS else dat


def _metadata(record: bytes, family: Familia) -> bytes:
    mutable = bytearray(record)
    for _, off, _ in family.campos:
        mutable[off:off + 2] = b"\0\0"
    return bytes(mutable)


def construir_tabla_str(jp_dat: bytes, es_dat: bytes, jp_pool: bytes, es_pool: bytes,
                        table: TextTable, family: Familia) -> tuple[bytes, dict]:
    """No emite .dat: los punteros y todos los datos de juego quedan literales.

    Reúne todos los propietarios antes de escribir para evitar que un alias
    traduzca un ID sin correspondencia, aunque otro ID sí la tenga.
    """
    jp, es = _plain(jp_dat, family), _plain(es_dat, family)
    unique_jp = _unicos_por_identidad(_table(jp_dat)) if family == OBJETOS else {}
    unique_es = _unicos_por_identidad(_table(es_dat)) if family == OBJETOS else {}
    jp_ids = Counter(struct.unpack_from("<H", jp, row * 104 + 78)[0] for row in range(family.cantidad)) if family == FICHAS else {}
    es_ids = defaultdict(list)
    if family == FICHAS:
        for row in range(family.cantidad):
            es_ids[struct.unpack_from("<H", es, row * 104 + 78)[0]].append(row)
    owners = defaultdict(list)
    pending = []
    already = []
    empty = []
    for row in range(family.cantidad):
        j = jp[row * family.paso:(row + 1) * family.paso]
        es_row = row
        if family == FICHAS:
            ident = struct.unpack_from("<H", j, 78)[0]
            matches = es_ids[ident]
            es_row = matches[0] if len(matches) == 1 else row
        e = es[es_row * family.paso:(es_row + 1) * family.paso]
        if family == OBJETOS:
            identity = j[28:42]
            identified = unique_jp.get(identity) == row == unique_es.get(identity)
        elif family == FICHAS:
            # Mismo contrato de identidad ya auditado para nombre corto.
            identified = bool(ident and jp_ids[ident] == 1 and len(matches) == 1
                              and j[44:94] == e[44:94] and j[95:102] == e[95:102])
        else:
            # El acceso del consumidor es por ID físico. La evidencia adicional
            # exige igualdad de TODOS los campos ajenos a referencias de texto.
            identified = _metadata(j, family) == _metadata(e, family) and any(_metadata(j, family))
        for field, off, limit in family.campos:
            ptr_j, ptr_e = struct.unpack_from("<H", j, off)[0], struct.unpack_from("<H", e, off)[0]
            raw_j, start, capacity = leer_ranura(jp_pool, ptr_j)
            raw_e, _, _ = leer_ranura(es_pool, ptr_e, family.escala_es)
            target = table.decode(raw_e, errors="strict")
            entry = {"record": row, "source_record": es_row, "field": field, "pointer_jp": ptr_j,
                     "pointer_es": ptr_e, "offset": start, "capacity": min(limit, capacity),
                     "original_sha256": _sha(raw_j), "official": target,
                     "source_offset": ptr_e * family.escala_es, "source_pointer_scale": family.escala_es}
            reason = None
            encoded = None
            if not raw_j or not raw_e:
                reason = "empty"
            elif TextTable.identity().decode(raw_j, errors="strict") == target:
                reason = "already"
            elif not identified or row == 0:
                reason = "identity"
            elif family == TACTICAS and field == "nombre":
                reason = "name_consumer_not_audited"
            elif any(c in target for c in ("%", "[", "]", "\r", "\\")):
                reason = "control_not_audited"
            elif not _codificable(target.replace("\n", "")):
                reason = "encoding"
                entry["unsupported"] = sorted({c for c in target if c != "\n" and not _codificable(c)})
            else:
                encoded = es_encode(target, 1 << 30)
                if len(encoded) >= min(limit, capacity):
                    reason = "capacity"
                    entry["encoded_bytes"] = len(encoded)
                elif encoded == raw_j:
                    reason = "already"
            entry["reason"] = reason
            owners[start].append((entry, encoded))

    out = bytearray(jp_pool)
    applied = []
    spans = []
    for start, group in sorted(owners.items()):
        reasons = {entry["reason"] for entry, _ in group}
        payloads = {encoded for _, encoded in group}
        if reasons == {None} and len(payloads) == 1:
            encoded = next(iter(payloads))
            capacity = min(entry["capacity"] for entry, _ in group)
            end = start + capacity
            if any(start < other < end for other in owners):
                raise ValueError("ranura STR invade otra referencia, incluso no traducida")
            if spans and start < spans[-1][1]:
                raise ValueError("ranuras STR solapadas")
            escribir_campo(out, start, capacity, encoded, group[0][0]["official"])
            spans.append((start, end))
            for entry, _ in group:
                entry.pop("reason")
                entry["encoded_bytes"] = len(encoded)
                entry["line_advance_offline"] = [sum(avance(c) for c in line) for line in entry["official"].split("\n")]
                applied.append(entry)
            if bytes(out[start:end]).split(b"\0", 1)[0] != encoded:
                raise ValueError("reextracción STR distinta")
        else:
            for entry, _ in group:
                if entry["reason"] == "empty":
                    empty.append(entry)
                elif entry["reason"] == "already":
                    already.append(entry)
                else:
                    if entry["reason"] is None:
                        entry["reason"] = "alias_conflict_or_unverified_owner"
                    pending.append(entry)
    cursor = 0
    for start, end in spans:
        if jp_pool[cursor:start] != out[cursor:start]:
            raise ValueError("STR: bytes fuera de campos modificados")
        cursor = end
    if jp_pool[cursor:] != out[cursor:] or len(out) != len(jp_pool):
        raise ValueError("STR: cola/tamaño modificado")
    for row in applied:
        source, _, _ = leer_ranura(es_pool, row["pointer_es"], family.escala_es)
        checked, _, _ = leer_ranura(bytes(out), row["pointer_jp"])
        if checked != es_encode(table.decode(source, errors="strict"), 1 << 30):
            raise ValueError("STR: reextracción final no coincide con oficial")
    changed_starts = {start for start, _ in spans}
    for start in owners.keys() - changed_starts:
        if leer_ranura(jp_pool, start // 32)[0] != leer_ranura(bytes(out), start // 32)[0]:
            raise ValueError("STR: cadena pendiente o vacía modificada")
    return bytes(out), {
        "family": family.nombre, "physical_records": family.cantidad,
        "field_count": family.cantidad * len(family.campos),
        "applied_fields": len(applied), "applied_slots": len(spans),
        "by_field": dict(Counter(row["field"] for row in applied)),
        "pending_by_reason": dict(Counter(row["reason"] for row in pending)),
        "empty_fields": len(empty), "already_fields": len(already), "empty": empty,
        "applied": applied, "pending": pending,
        "sha256_before": _sha(jp_pool), "sha256_after": _sha(bytes(out)),
        "dat_sha256_preserved": _sha(jp_dat), "original_size": len(jp_pool),
        "size_preserved": True, "nontext_and_references_unchanged": True,
        "roundtrip_official_exact": True, "runtime_verified": False,
    }


def recursos_tablas_ui(profile, japanese, european) -> tuple[dict[str, bytes], dict]:
    """Mismo adaptador Spark/Ogre; sin rutas ni correspondencias Bomber implícitas."""
    prefix = profile.recurso.rsplit("/", 1)[0] + "/logic/"
    table = load_text_table(european)
    payloads, reports = {}, {}
    for family in (OBJETOS, TECNICAS, TACTICAS, FICHAS):
        path_dat, path_str = prefix + family.nombre + ".dat", prefix + family.nombre + ".STR"
        output, report = construir_tabla_str(japanese.read(path_dat), european.read("es/" + path_dat),
                                             japanese.read(path_str), european.read("es/" + path_str), table, family)
        if output != japanese.read(path_str):
            payloads[path_str] = output
        reports[family.nombre] = report
    for name in ("teamtitle", "BattleRouteTitle", "ClearCondition", "OpenCondition"):
        path = prefix + name + ".dat"
        output, report = construir_rotulos(japanese.read(path), european.read("es/" + path), table, name)
        if output != japanese.read(path):
            payloads[path] = output
        reports[name] = report
    reports["games"] = {"applied_fields": 0, "reason": "no_spanish_resource_common_resource_not_official_translation",
                        "jp_es_common_identical": japanese.read(prefix + "games.STR") == european.read(prefix + "games.STR")}
    return payloads, reports


def _registros_id(data: bytes, stride: int) -> dict[int, tuple[int, bytes]]:
    if not data or len(data) % stride:
        raise ValueError("tabla de rótulos: tamaño distinto del paso auditado")
    result = {}
    for offset in range(0, len(data), stride):
        record = data[offset:offset + stride]
        ident = record[0]
        if ident == 255:
            return result
        if ident in result:
            raise ValueError("tabla de rótulos: ID duplicado")
        result[ident] = (offset, record)
    raise ValueError("tabla de rótulos: falta centinela FF")


def construir_rotulos(japanese: bytes, european: bytes, table: TextTable, name: str) -> tuple[bytes, dict]:
    """Títulos/condiciones por ID o metadata, conservando geometría JP y centinela."""
    if name == "teamtitle":
        if len(japanese) != 640 or len(european) != 640:
            raise ValueError("teamtitle: esperaba20registros32")
        jp = {i: (i * 32, japanese[i * 32:(i + 1) * 32]) for i in range(20)}
        es = {i: (i * 32, european[i * 32:(i + 1) * 32]) for i in range(20)}
        jp_keys, es_keys = Counter(r[26:32] for _, r in jp.values()), Counter(r[26:32] for _, r in es.values())
        text_start, text_end, capacity = 0, 26, 25
    else:
        if name not in ("BattleRouteTitle", "ClearCondition", "OpenCondition"):
            raise ValueError("familia de rótulos sin consumidor auditado")
        stride_jp = 33 if name == "BattleRouteTitle" else 81
        stride_es = 64 if name == "BattleRouteTitle" else 128
        jp, es = _registros_id(japanese, stride_jp), _registros_id(european, stride_es)
        text_start, text_end, capacity = 1, stride_jp, stride_jp - 1
    output = bytearray(japanese)
    applied, pending, empty, already = [], [], [], []
    for ident, (offset, original) in jp.items():
        row = {"id": ident, "record": offset // len(original), "offset": offset + text_start}
        if ident not in es:
            pending.append(dict(row, reason="identity_missing"))
            continue
        source_offset, official = es[ident]
        if name == "teamtitle":
            key = original[26:32]
            if key != official[26:32] or jp_keys[key] != 1 or es_keys[key] != 1:
                pending.append(dict(row, reason="metadata_identity"))
                continue
        field_jp = original[text_start:text_end]
        field_es = official[text_start:26] if name == "teamtitle" else official[1:]
        if b"\0" not in field_jp or b"\0" not in field_es:
            raise ValueError(f"{name}: campo sin NUL, ID{ident}")
        raw_jp, raw_es = field_jp.split(b"\0", 1)[0], field_es.split(b"\0", 1)[0]
        if any(field_jp[len(raw_jp):]):
            raise ValueError(f"{name}: bytes no nulos tras terminador, ID{ident}")
        text = table.decode(raw_es, errors="strict")
        row.update(official=text, source_record=source_offset // len(official), capacity=capacity,
                   original_sha256=_sha(raw_jp))
        if not raw_jp or not raw_es:
            empty.append(row)
            continue
        if TextTable.identity().decode(raw_jp, errors="strict") == text:
            already.append(row)
            continue
        if any(c in text for c in ("%", "[", "]", "\r", "\\")):
            pending.append(dict(row, reason="control_not_audited"))
            continue
        if not _codificable(text.replace("\n", "")):
            pending.append(dict(row, reason="encoding"))
            continue
        encoded = es_encode(text, 1 << 30)
        if len(encoded) >= capacity:
            pending.append(dict(row, reason="capacity", encoded_bytes=len(encoded)))
            continue
        escribir_campo(output, offset + text_start, capacity, encoded, text)
        row["encoded_bytes"] = len(encoded)
        applied.append(row)
    changed = {row["record"] for row in applied}
    for ident, (offset, original) in jp.items():
        after = bytes(output[offset:offset + len(original)])
        if offset // len(original) not in changed:
            if after != original:
                raise ValueError("rótulo pendiente modificado")
        elif after[:text_start] != original[:text_start] or after[text_start + capacity:] != original[text_start + capacity:]:
            raise ValueError("rótulo: ID o metadatos modificados")
    for row in applied:
        if bytes(output[row["offset"]:row["offset"] + capacity]).split(b"\0", 1)[0] != es_encode(row["official"], 1 << 30):
            raise ValueError("rótulo: reextracción diferente del oficial")
    tail = max(offset + len(record) for offset, record in jp.values())
    if bytes(output[tail:]) != japanese[tail:]:
        raise ValueError("centinela o cola modificados")
    return bytes(output), {"family": name, "field_count": len(jp), "applied_fields": len(applied),
                           "empty_fields": len(empty), "already_fields": len(already),
                           "applied": applied, "pending": pending, "empty": empty,
                           "pending_by_reason": dict(Counter(row["reason"] for row in pending)),
                           "sha256_before": _sha(japanese), "sha256_after": _sha(bytes(output)),
                           "size_preserved": True, "ids_metadata_sentinel_unchanged": True,
                           "roundtrip_official_exact": True, "runtime_verified": False}
