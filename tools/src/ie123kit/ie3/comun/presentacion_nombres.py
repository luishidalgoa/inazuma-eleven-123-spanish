"""Identidades oficiales y ajuste acotado del avance FONT8 de IE3.

unitbase es una tabla plana de objetos de 0x68 bytes, incluido el objeto cero.
El consumidor 301A usa el campo corto +0x1C, no el nombre completo +0.
El ajuste del override requiere el CRO v7 exacto; ver IE3_NOMBRES_FASE3.md.
"""
from __future__ import annotations

import hashlib
import re
import struct
from collections import Counter, defaultdict
from functools import cache

from ie123kit.ie3.comun.ancho_ventana import direcciones_de_tablas
from ie123kit.ie3.comun.limite_nombre import LIMITE_LOGICO
from ie123kit.ie3.comun.nombres import _encode_target
from ie123kit.ie3.comun.paquetes import leer_paquete
from ie123kit.ie3.comun.referencias import instrucciones
from ie123kit.ie3.comun.ssd import parse_ssd
from ie123kit.ie3.comun.text import TextTable
from ie123kit.ie3.comun.tipografia import _codepoint_destino
from ie123kit.nucleo.texto.sjis_portador import _acc

TAMANO = 0x68
CORTO = 0x1C
FIN_CORTO = 0x2C
ID = 0x4E
RECURSO_CONFIG = "import/sItxInazuma3ogre.itx"
PARAMETROS_NOMBRE = tuple(
    f"cscenedirection_1728_{s}" for s in ("ofsX", "ofsY", "addW", "addH")
)
CRO_V7_SHA256 = "1c2db0af506077b1e94f1faa83859643cb35ca68ee0665db6872d811580f3061"
SALTO_FONT8 = 0x180918
ANTES_FONT8 = 0x0A000004
DESPUES_FONT8 = 0x0A000014
ANCLAS_FONT8 = {
    0x1808E4: "fc16dce1",  # ldrsh r1,[ip,#6c]: override externo
    0x1808EC: "2300001a",  # si no cero, salta selección de defaults
    0x180914: "010053e3",  # cmp r3,#1: SOLO FONT8
    0x18091C: "000053e3",  # FONT12 sigue su rama original
    0x180970: "98309de5",  # carga configuración propia de llamada
    0x180974: "083093e5",  # addW
    0x180978: "000053e3",  # solo positivo reemplaza el default
    0x18097C: "0310a0c1",
    0x180998: "341085e5",  # str r1,[r5,#34]
    0x180CE8: "340095e5",  # uso posterior de override
    0x180E6C: "000050e3",
    0x180E70: "070000da",  # <=0 conserva el avance NW
}


def parchear_font8_ie3(cro: bytes) -> tuple[bytes, dict]:
    """Opt-in: omite defaults forzados FONT8 en CRO IE3, sin cave ni escalado.

    Afecta otras UI FONT8 del mismo módulo sin override propio. FONT12/cuerpo,
    FONT12T, RUBI y módulos IE1/IE2 no cambian. Requiere CRO v7 exacto; permite
    repetir sobre la propia salida, pero no sobre otro parche no auditado.
    """
    if len(cro) <= max(ANCLAS_FONT8) + 4 or cro[0x80:0x84] != b"CRO0":
        raise ValueError("CRO inválido para la revisión de nombres")
    word = struct.unpack_from("<I", cro, SALTO_FONT8)[0]
    if word not in (ANTES_FONT8, DESPUES_FONT8):
        raise ValueError("rama FONT8 inesperada")
    normalized = bytearray(cro)
    struct.pack_into("<I", normalized, SALTO_FONT8, ANTES_FONT8)
    if hashlib.sha256(normalized).hexdigest() != CRO_V7_SHA256:
        raise ValueError("CRO no coincide con referencia funcional v7 exacta")
    for offset, expected in ANCLAS_FONT8.items():
        if cro[offset:offset + 4].hex() != expected:
            raise ValueError(f"ancla FONT8 distinta en {offset:#x}")
    touched = direcciones_de_tablas(cro)
    if SALTO_FONT8 in touched:
        raise ValueError("rama FONT8 aparece en tabla de relocación")
    output = bytearray(cro)
    struct.pack_into("<I", output, SALTO_FONT8, DESPUES_FONT8)
    result = bytes(output)
    assert len(result) == len(cro)
    assert cro[:SALTO_FONT8] == result[:SALTO_FONT8]
    assert cro[SALTO_FONT8 + 4:] == result[SALTO_FONT8 + 4:]
    return result, {
        "sha256_before": hashlib.sha256(cro).hexdigest(),
        "sha256_after": hashlib.sha256(result).hexdigest(),
        "reference_v7_sha256": CRO_V7_SHA256,
        "offset_file": SALTO_FONT8, "word_before": f"{word:08X}",
        "word_after": f"{DESPUES_FONT8:08X}",
        "branch_destination_before": 0x180930,
        "branch_destination_after": 0x180970,
        "relocation_targets_checked": len(touched),
        "scope": "IE3 FONT8 sin override propio; nombres y otras UI FONT8",
        "font12_body_unchanged": True, "fonts_unchanged": True,
        "no_cave_or_segment_growth": True, "runtime_verified": False,
        "already_applied": word == DESPUES_FONT8,
    }


def _registros(data: bytes) -> list[bytes]:
    if not data or len(data) % TAMANO:
        raise ValueError("unitbase no es una tabla plana de registros de 0x68")
    return [data[o:o + TAMANO] for o in range(0, len(data), TAMANO)]


def _identidad(record: bytes) -> int:
    return struct.unpack_from("<H", record, ID)[0]


def _corto(record: bytes) -> bytes:
    field = record[CORTO:FIN_CORTO]
    if b"\0" not in field:
        raise ValueError("nombre corto sin NUL interno en sus 16 bytes")
    return field.split(b"\0", 1)[0]


def auditar_cota(datos: bytes) -> dict:
    """Cota ESTÁTICA de este recurso; no prueba productores dinámicos/save."""
    records = _registros(datos)
    lengths = [len(_corto(r)) for r in records]
    return {"registros": len(records), "max_bytes_sin_nul": max(lengths),
            "todos_nul_interno": True, "campo_bytes": FIN_CORTO - CORTO,
            "sha256": hashlib.sha256(datos).hexdigest()}


def localizar_por_identidad(japonesa: bytes, europea: bytes, tabla_europea,
                           actual: bytes | None = None) -> tuple[bytes, dict]:
    """Emite solo nombres cortos oficiales por ID único y metadata contrastada.

    Se admite la estadística +0x5E distinta observada en 11 fichas oficiales y
    el índice local +0x66; ambos se conservan literalmente japoneses. Todo el
    resto de +0x2C..+0x65 debe coincidir: incluye lectura y datos auxiliares.
    `actual` puede ser v7, pero únicamente con campos cortos ya localizados; no
    se autoriza sobrescribir un estado distinto del JP o del ES esperado.
    """
    jp = _registros(japonesa)
    es = _registros(europea)
    current = _registros(actual if actual is not None else japonesa)
    if len(current) != len(jp):
        raise ValueError("estado actual no tiene las mismas fichas JP")
    source_ids = Counter(map(_identidad, jp))
    official = defaultdict(list)
    for index, record in enumerate(es):
        official[_identidad(record)].append((index, record))
    out = bytearray(actual if actual is not None else japonesa)
    entries, pending, counts = [], [], Counter()
    for index, (record, now) in enumerate(zip(jp, current)):
        ident = _identidad(record)
        row = {"record": index, "speaker_id": ident,
               "field_offset": index * TAMANO + CORTO}
        if now[:CORTO] != record[:CORTO] or now[FIN_CORTO:] != record[FIN_CORTO:]:
            raise ValueError(f"campos ajenos al nombre cambiaron en ficha {index}")
        source, inherited = _corto(record), _corto(now)
        candidates = official[ident]
        reason = None
        if ident == 0:
            reason = "id_cero_reservado"
        elif source_ids[ident] != 1 or len(candidates) > 1:
            reason = "identidad_ambigua"
        elif not candidates:
            reason = "sin_equivalente_oficial"
        if reason:
            pending.append(dict(row, causa=reason))
            continue
        es_index, target_record = candidates[0]
        if (record[0x2C:0x5E] != target_record[0x2C:0x5E]
                or record[0x5F:0x66] != target_record[0x5F:0x66]):
            pending.append(dict(row, causa="metadata_identidad_diferente"))
            continue
        official_raw = _corto(target_record)
        if not source or not official_raw:
            pending.append(dict(row, causa="campo_vacio"))
            continue
        text = tabla_europea.decode(official_raw)
        encoded = _encode_target(text)
        if encoded is None:
            pending.append(dict(row, causa="encoding", nombre=text))
            continue
        if len(encoded) >= FIN_CORTO - CORTO:
            pending.append(dict(row, causa="capacidad_16_bytes", nombre=text))
            continue
        if inherited not in (source, encoded):
            pending.append(dict(row, causa="heredado_no_corresponde", nombre=text))
            continue
        if inherited == encoded:
            status = "ya_oficial_original" if source == encoded else "heredado_oficial"
        else:
            status = "insertado_nuevo"
            start = row["field_offset"]
            out[start:start + 16] = encoded.ljust(16, b"\0")
        counts[status] += 1
        entries.append(dict(row, official_record=es_index, nombre=text,
                            estado=status, bytes=len(encoded),
                            diferencia_estadistica_5e=(record[0x5E] != target_record[0x5E])))
    result = bytes(out)
    return result, {
        "registros": len(jp), "oficiales": len(es), "estados": dict(counts),
        "pendientes_por_causa": dict(Counter(x["causa"] for x in pending)),
        "entries": entries, "pendientes": pending,
        "cota_salida": auditar_cota(result),
        "campos_modificados": ["nombre_corto+0x1C:16"],
        "presentacion_visual_corregida": False,
        "bloqueo_visual": "override FONT8 y límite lógico de pestaña; no se parchea CRO",
    }


def recursos_nombres(perfil, originales: dict, oficiales: dict, tabla_europea,
                     actuales: dict | None = None) -> tuple[dict, dict]:
    """Adaptador de recursos común Spark/Ogre; no selecciona otra versión EU."""
    path = recurso_unitbase(perfil)
    eu_path = "es/" + path
    output, report = localizar_por_identidad(
        originales[path], oficiales[eu_path], tabla_europea,
        None if actuales is None else actuales[path],
    )
    return {path: output}, dict(report, perfil=perfil.nombre, recurso=path,
                                fuente_oficial=eu_path)


def recurso_unitbase(perfil) -> str:
    """Tabla normal del perfil. NPC/ex_binder requieren su propio adaptador."""
    return perfil.recurso.rsplit("/", 1)[0] + "/logic/unitbase.dat"


def configuracion_nombre(itx: bytes, itx_global: bytes) -> dict:
    """Inspección estricta de parámetros s32, sin cambiar recursos compartidos."""
    pattern = rb"_PARAM_\(\s*([^,]+),\s*s32\s*,\s*([A-Za-z0-9_]+)\s*\)"

    def read(blob):
        result = {}
        for index, match in enumerate(re.finditer(pattern, blob)):
            name = match[2].decode("ascii")
            if name in result:
                raise ValueError(f"parámetro ITX duplicado: {name}")
            raw = match[1].strip().decode("ascii")
            try:
                value = int(raw, 0)
            except ValueError:
                # Otras entradas contienen expresiones C: cuentan como s32,
                # pero este auditor no evalúa código del archivo.
                value = raw
            result[name] = {"valor": value, "offset_s32": index * 4}
        return result

    local, shared = read(itx), read(itx_global)
    selected = {key: local[key] for key in PARAMETROS_NOMBRE}
    if [selected[k]["offset_s32"] for k in PARAMETROS_NOMBRE] != list(range(0x2E48, 0x2E58, 4)):
        raise ValueError("layout ITX no coincide con addend auditado del consumidor")
    keys = [f"DRAW_ON_CHARACTOR_FONT8_DISP_{d}_FORCE_CHAR_WIDTH" for d in ("TOP", "BOTTOM")]
    return {"nombre": selected, "defaults_compartidos": {k: shared[k] for k in keys},
            "cero_local_desactiva_override": False,
            "cambia_recursos": False}


def medir_nombre(texto: str, fuente) -> dict:
    """Lectura de tinta v7 y separación lógica por nombre, nunca ejecución.

    fuente es FuenteBCFNT ya abierta. Conserva las claves métricas históricas;
    el override normal superior da trunc(6*1.5625)+1 = 10 píxeles por carácter.
    La ruta proporcional de fase3/fase4 convierte espacio ASCII a U+3000 antes
    de buscar métricas. No se cambia ni fuente ni texto/encoder almacenado.
    """
    pens = {"override_superior": 0, "proporcional_hipotetico": 0}
    ink = {key: set() for key in pens}
    missing, clipped = [], []
    for ch in texto:
        gi = fuente.cmap.get(0x3000 if ch == " " else _codepoint_destino(ch))
        if gi is None:
            missing.append(ch)
            continue
        off = fuente.cwdh_entry_off(gi)
        if off is None:
            missing.append(ch)
            continue
        left, width, advance = struct.unpack_from("<bBB", fuente.data, off)
        shift = left + int((fuente.b.width - advance) / 2)
        grid = fuente.read_cell(gi)
        if any(v for row in grid for v in row[width:]):
            clipped.append(ch)
        for model, pen in pens.items():
            ink[model].update((pen + shift + x, y) for y, row in enumerate(grid)
                              for x, v in enumerate(row[:width]) if v)
            pens[model] += 10 if model == "override_superior" else advance + 1
    logical_lines = {}
    for limit in (64, LIMITE_LOGICO):
        lines, line, logical_x = [], "", 0
        for ch in texto:
            if logical_x + 8 > limit:
                lines.append(line)
                line, logical_x = "", 0
            line += ch
            logical_x += 9
        if line:
            lines.append(line)
        logical_lines[str(limit)] = lines
    ink_widths = {key: max((x for x, _ in px), default=-1)
                 - min((x for x, _ in px), default=0) + 1 for key, px in ink.items()}
    return {"nombre": texto, "caracteres": len(texto), "avance": pens,
            "tinta_ancho": ink_widths,
            "tinta_supera_region64": ink_widths["proporcional_hipotetico"] > 64,
            "glifos_ausentes": missing, "raster_fuera_glyph_width": clipped,
            "lineas_limite_logico": logical_lines,
            "comandos_con_terminador_bytes": (len(texto) + 1) * 32,
            "capacidad_real_512": len(texto) <= 15,
            "espacios_runtime": [{"indice": i, "codepoint": "U+3000"}
                                  for i, ch in enumerate(texto) if ch == " "],
            "supera_8_caracteres": len(texto) > 8,
            "runtime_verified": False}


def render_comparacion(nombres: list[str], fuente):
    """Simulación offline fase3/fase4, misma fuente proporcional en ambas.

    No cambia raster ni lo escala dentro de la maqueta; la salida final se
    amplía por píxel entero para inspección. Filas separadas para inspección:
    el panel no representa los bordes/origen reales de la pestaña del juego.
    """
    from PIL import Image, ImageDraw

    from ie123kit.ie3.comun.geometria_dialogo import Medidor

    medidor = Medidor(fuente, tracking=1)
    reports = [medir_nombre(text, fuente) for text in nombres]
    row_heights = [22 + 3 * ((fuente.t["cell_h"] + 4) * max(
        1, *(len(lines) for lines in report["lineas_limite_logico"].values())))
        for report in reports]
    output = Image.new("RGB", (780, 80 + sum(row_heights)), (24, 28, 34))
    draw = ImageDraw.Draw(output)
    draw.text((12, 6), "SIMULACION OFFLINE - no captura de ejecucion", fill="white")
    draw.text((12, 24), "Filas para inspeccion; origen y marco de pestana pendientes de juego", fill="white")
    draw.text((12, 46), "Fase 3: limite logico 64", fill="white")
    draw.text((390, 46), f"Fase 4: limite logico {LIMITE_LOGICO} + guardia512", fill="white")
    y = 70
    for text, report, row_height in zip(nombres, reports, row_heights):
        if report["glifos_ausentes"] or report["raster_fuera_glyph_width"]:
            raise ValueError(f"maqueta requiere glifos conocidos: {text}")
        if not report["capacidad_real_512"]:
            raise ValueError("nombre excede capacidad real; no ocultar corte defensivo")
        for limit, column in (("64", 12), (str(LIMITE_LOGICO), 390)):
            lines = report["lineas_limite_logico"][limit]
            sample = Image.new("RGBA", (112, (fuente.t["cell_h"] + 4) * max(1, len(lines))),
                               (12, 48, 105, 255))
            for line_no, line in enumerate(lines):
                pen = 3
                for ch in line:
                    advance, pixels = medidor.glifo(ch)
                    for x, gy, value in pixels:
                        tx, ty = pen + x, gy + 2 + line_no * (fuente.t["cell_h"] + 4)
                        if not (0 <= tx < sample.width and 0 <= ty < sample.height):
                            raise ValueError("simulación recortaría tinta; ampliar lienzo, no glifos")
                        sample.putpixel((tx, ty), tuple(int(b + (255 - b) * value / 15)
                                                       for b in (12, 48, 105)) + (255,))
                    pen += advance
            label = text + (" [NEGATIVO: tinta >64]" if report["tinta_supera_region64"] else "")
            draw.text((column, y), label, fill="white")
            output.paste(sample.resize((sample.width * 3, sample.height * 3), Image.Resampling.NEAREST),
                         (column, y + 16))
        y += row_height
    return output


def auditar_presentacion(archive, fuente_FONT8) -> dict:
    """Audita productores de nombres actuales con la fuente del mismo archivo.

    API de solo lectura compatible con FaArchive/B123Archive. Comprueba todas
    las tablas normales/NPC/ex_binder y el primer argumento de cada SSD3019;
    exige NUL, <=15 glifos, tinta <=64 y raster modelado completo. No escribe
    JSON/PNG/CRO ni valida en ejecución el origen de la pestaña. Los negativos
    sintéticos (por ejemplo nueve W) NO son nombres aceptados por esta auditoría.
    """
    font_bytes = archive.read("font/FONT8.bcfnt")
    if bytes(fuente_FONT8.data) != font_bytes:
        raise ValueError("FONT8 del medidor no coincide con el archivo auditado")
    reverse = str.maketrans({v: k for k, v in _acc.items() if len(v) == 1 and ord(v) > 127})

    @cache
    def measure(raw):
        text = raw.decode("shift-jis").translate(reverse)
        measured = dict(medir_nombre(text, fuente_FONT8), bytes_sin_nul=len(raw), raw_hex=raw.hex())
        if any(ch in text for ch in ("\n", "\r", "\f", "\0")):
            raise ValueError("nombre contiene salto/control no modelado")
        if measured["glifos_ausentes"] or measured["raster_fuera_glyph_width"]:
            raise ValueError(f"nombre con glifo/tinta no modelados: {text!r}")
        if not measured["capacidad_real_512"]:
            raise ValueError(f"nombre supera quince comandos/capacidad512: {text!r}")
        if measured["tinta_supera_region64"]:
            raise ValueError(f"nombre excede región de tinta64: {text!r}")
        return measured

    def summary(rows):
        return {
            "max_bytes": max((r["bytes_sin_nul"] for r in rows), default=0),
            "max_glyphs": max((r["caracteres"] for r in rows), default=0),
            "max_ink_width": max((r["tinta_ancho"]["proporcional_hipotetico"] for r in rows), default=0),
            "all_capacity512": True, "all_ink_within64": True,
            "spaces": sum(bool(r["espacios_runtime"]) for r in rows),
            "unmodeled": [], "rows": rows,
        }

    report = {"runtime_verified": False, "font8_sha256": hashlib.sha256(font_bytes).hexdigest(),
              "font_bytes_unchanged": True, "unitbase": {}, "ssd3019": {},
              "logical_limit": LIMITE_LOGICO, "physical_width_unchanged": 64,
              "native_origin_and_tab_frame_verified": False}
    paths = [(prefix + "/data_iz/logic/unitbase.dat", 104, 28)
             for prefix in ("inazuma3", "inazuma3_ogre")]
    paths += [(prefix + "/data_iz/logic/unitbase_npc.dat", 80, 16)
              for prefix in ("inazuma3", "inazuma3_ogre")]
    paths.append(("inazuma3_ogre/data_iz/logic/ex_binder/unitbase.dat", 104, 28))
    for path, stride, field in paths:
        data = archive.read(path)
        if not data or len(data) % stride:
            raise ValueError(f"tabla de nombres incompleta/no alineada: {path}")
        rows = []
        for offset in range(0, len(data), stride):
            short = data[offset + field:offset + field + 16]
            if b"\0" not in short:
                raise ValueError(f"nombre sin NUL16 en {path}:{offset}")
            rows.append(dict(measure(short.split(b"\0", 1)[0]), record=offset // stride))
        report["unitbase"][path] = dict(summary(rows), records=len(rows), all_nul16=True)
    for prefix in ("inazuma3", "inazuma3_ogre"):
        resource = prefix + "/data_iz/script/eve"
        blocks, _ = leer_paquete(archive.read(resource + ".pkh"), archive.read(resource + ".pkb"), "eve")
        rows = []
        for event, block in blocks.items():
            owners = {r.key: r for r in parse_ssd(block, TextTable.identity())[1]}
            for instruction in instrucciones(block):
                if instruction.opcode != 0x3019:
                    continue
                if not instruction.tipos or instruction.tipos[0] != 3:
                    raise ValueError(f"nombre3019 no constante en {resource}:{event}:{instruction.ident}")
                key = (instruction.ident, instruction.slots[0])
                if key not in owners:
                    raise ValueError(f"nombre3019 sin propietario en {resource}:{event}:{key}")
                row = owners[key]
                if b"\0" not in block[row.offset + 4:row.offset + row.size]:
                    raise ValueError(f"nombre3019 sin NUL en {resource}:{event}:{key}")
                rows.append(dict(measure(row.raw), event=event, instruction=instruction.ident))
        report["ssd3019"][prefix] = dict(summary(rows), count=len(rows), all_type3_constant=True, all_nul=True)
    report["totals"] = {
        "unitbase_rows": sum(v["records"] for v in report["unitbase"].values()),
        "ssd3019_names": sum(v["count"] for v in report["ssd3019"].values()),
    }
    if bytes(fuente_FONT8.data) != font_bytes:
        raise ValueError("el lector modificó FONT8 durante la auditoría")
    return report
