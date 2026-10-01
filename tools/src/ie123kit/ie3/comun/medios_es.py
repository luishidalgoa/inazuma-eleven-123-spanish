"""Selección conservadora de medios oficiales IE3; nunca modifica originales.

El plan de sonido devuelve rutas, no cientos de MB duplicados en memoria.
Las películas se inventarían aparte: formato compatible no demuestra montaje,
subtítulos ni sincronía. No se copian bancos ni se modifica música idéntica.
"""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import asdict
from pathlib import Path

from ie123kit.nucleo.ejecutable.cro import Cro
from ie123kit.nucleo.media.audio import inspect_sad

PERFILES = ("inazuma3", "inazuma3_ogre")
VOZ = re.compile(r"V[0-9]{4}[aA][0-9]{2}[a-c]?\.SAD\Z")
ESCENA = re.compile(r"a3m[0-9]{2}[a-f]\.SAD\Z")
CANCION = re.compile(r"(?:op|end)00f\.SAD\Z")

ANCLAS_CONSUMIDORES = {
    0xABD0: 0xE28F1F51, 0xABF8: 0xEBFFD69A, 0xAC08: 0xEB05EA04,
    0xAC1C: 0xEBFFD617, 0xAC4C: 0xE5920000, 0xAC5C: 0xE3C00003,
    0xAC60: 0xE0800001, 0x14D0AC: 0xEB00CAE6, 0x14D150: 0xE5900000,
    0x14D160: 0xE3C00003, 0x14D164: 0xE0800002, 0x17FCA0: 0xEBFA90CA,
    0x24020: 0xE2459020, 0x24024: 0xE359005E, 0x24030: 0x9A000020,
    0x17F93C: 0xE28F1FAE, 0x17F954: 0xE28F1FAA, 0x17F9B0: 0xEBFA0730,
    0x17F9CC: 0xEBFA072D, 0x17F9D8: 0xEBFA072C, 0x17F9E8: 0xEBFA072A,
    0x17FA0C: 0xEBFA0723,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _categoria(name: str) -> str | None:
    for pattern, category in ((VOZ, "voz_dialogo"), (ESCENA, "audio_cinematica"),
                              (CANCION, "cancion")):
        if pattern.fullmatch(name):
            return category
    return None


def _sad(path: Path) -> tuple[bytes, dict]:
    info = inspect_sad(path)
    data = path.read_bytes()
    if _sha(data) != info.sha256:
        raise ValueError(f"SADL cambió durante la inspección: {path.name}")
    if (len(data) < 0x100 or info.start_offset != 0x100
            or info.data_size != len(data) or struct.unpack_from("<I", data, 8)[0] != len(data)
            or info.channels not in (1, 2) or info.codec_flag != "0xb4"
            or (len(data) - 0x100) % (16 * info.channels)):
        raise ValueError(f"SADL fuera del contrato IE3: {path.name}")
    return data, asdict(info)


def planificar_audio(jp_romfs: Path, spark_romfs: Path, ogre_romfs: Path):
    """Retorna (destino RomFS relativo -> Path ES, informe JSON serializable).

    Solo nombres existentes exactos, categorías auditadas y SADL compatibles.
    Rechaza contradicciones entre fuentes, cambios de codec/bucle/canales y
    fuentes ausentes. Ficheros idénticos e instrumentales permanecen intactos.
    No emite nada ni valida reproducción/sincronía en el juego.
    """
    roots = {"spark": Path(spark_romfs), "ogre": Path(ogre_romfs)}
    selected, rows, pending = {}, [], []
    for profile in PERFILES:
        rel = f"{profile}/data_iz/sound"
        jpdir = Path(jp_romfs) / rel
        if not jpdir.is_dir() or any(not (r / "es" / rel).is_dir() for r in roots.values()):
            raise ValueError(f"falta directorio de audio oficial: {rel}")
        for original in sorted(jpdir.glob("*.SAD")):
            target = f"{rel}/{original.name}"
            sources = [(tag, root / "es" / target) for tag, root in roots.items()
                       if (root / "es" / target).is_file()]
            if not sources:
                pending.append({"target": target, "reason": "sin_equivalente_ES"})
                continue
            before, jpinfo = _sad(original)
            options = [(tag, p, *_sad(p)) for tag, p in sources]
            if any(raw != options[0][2] for _, _, raw, _ in options[1:]):
                raise ValueError(f"fuentes ES contradictorias: {target}")
            tag, source, after, esinfo = options[0]
            row = {"target": target, "source": str(source), "edition": tag,
                   "source_editions": [x[0] for x in options], "before": jpinfo, "after": esinfo}
            if before == after:
                row["state"] = "identico_preservado"
            elif (category := _categoria(original.name)) is None:
                row["state"] = "pendiente_categoria_no_auditada"
                pending.append({"target": target, "reason": row["state"]})
            else:
                for key in ("channels", "sample_rate", "codec_flag", "loop", "start_offset"):
                    if jpinfo[key] != esinfo[key]:
                        raise ValueError(f"{target}: cambia {key}, no sustituir a ciegas")
                # Nombres internos admiten alias oficiales; se compara JP/ES,
                # no se asume que el título instrumental coincida con el fichero.
                names = (before[0x20:0x30].split(b"\0", 1)[0], after[0x20:0x30].split(b"\0", 1)[0])
                ending_alias = (target == "inazuma3/data_iz/sound/end00f.SAD"
                                and names == (b"END00F.SAD", b"END00B.SAD"))
                if names[0] != names[1] and not ending_alias:
                    raise ValueError(f"{target}: cambia identidad interna SADL")
                row["official_internal_name_alias"] = ending_alias
                row.update(state="preparado", category=category)
                selected[target] = source
            rows.append(row)
        for suffix in ("*.pkb", "*.pkh", "*.SWD", "*.SED", "*.SMD"):
            for p in sorted(jpdir.glob(suffix)):
                pending.append({"target": f"{rel}/{p.name}", "reason": "banco_no_modificado"})
    return selected, {
        "schema": 1, "runtime_verified": False, "audio_decoded": False,
        "selected": len(selected), "rows": rows, "pending": pending,
        "note": "Voces regionales oficiales; sincronía y escucha pendientes de prueba manual.",
    }


def descriptor_moflex(data: bytes) -> dict:
    """Valida el descriptor de apertura retail observado, sin fingir decodificar."""
    if len(data) < 0x1000 or data[:4] != bytes.fromhex("4c32aaab"):
        raise ValueError("MOFLEX: cabecera/sincronía desconocida")
    if data[14:16] != b"\x03\x0d" or data[16:18] != b"\0\0":
        raise ValueError("MOFLEX: descriptor distinto del vídeo retail sin audio")
    # Descriptor type3: ID, codec, fps num/den, width/height, aspecto y layout.
    numerator, denominator, width, height = struct.unpack_from(">HHHH", data, 18)
    if (numerator, denominator, width, height, data[26:29]) != (24, 1, 240, 320, b"\1\1\x16"):
        raise ValueError("MOFLEX: geometría/fps/layout no auditados")
    return {"width": width, "height": height, "fps": [numerator, denominator],
            "layout": 0x16, "sha256": _sha(data), "bytes": len(data)}


def inventariar_videos(jp, spark, ogre) -> dict:
    """Resuelve IDs y precedencia regional ES; NO activa vídeos sin QA adicional.

    Los adaptadores de archivo exponen index/read/exists. El informe indica
    fuente exacta para lectura posterior, sin retener todos los MOFLEX.
    DAT se enumera como pendiente, nunca se copia crudo con otra CodeTable.
    """
    rows, subtitles, pending, extra = [], [], [], []
    for profile in PERFILES:
        prefix = f"{profile}/data_iz/movie/"
        targets = sorted(p for p in jp.index if p.startswith(prefix) and p.endswith(".moflex"))
        for target in targets:
            original = descriptor_moflex(jp.read(target))
            options = []
            for tag, archive in (("spark", spark), ("ogre", ogre)):
                source = "es/" + target if archive.exists("es/" + target) else target
                if archive.exists(source):
                    options.append((tag, source, descriptor_moflex(archive.read(source))))
            if not options:
                pending.append({"target": target, "reason": "sin_equivalente_ES"})
                continue
            if any(x[2]["sha256"] != options[0][2]["sha256"] for x in options[1:]):
                raise ValueError(f"película ES ambigua entre ediciones: {target}")
            tag, source, info = options[0]
            rows.append({"target": target, "edition": tag, "source": source,
                         "source_editions": [x[0] for x in options], "before": original,
                         "after": info, "state": "compatible_pendiente_subtitulos_y_QA"})
        for target in sorted(p for p in jp.index if p.startswith(prefix + "txt/") and p.endswith(".dat")):
            sources = [(tag, "es/" + target, _sha(archive.read("es/" + target)))
                       for tag, archive in (("spark", spark), ("ogre", ogre)) if archive.exists("es/" + target)]
            if not sources or any(x[2] != sources[0][2] for x in sources[1:]):
                raise ValueError(f"pista ES ausente/ambigua: {target}")
            subtitles.append({"target": target, "edition": sources[0][0], "source": sources[0][1],
                              "sha256": sources[0][2], "state": "requiere_conversion_portadores_y_consumidor"})
        for tag, archive in (("spark", spark), ("ogre", ogre)):
            extra.extend({"edition": tag, "source": p, "reason": "sin_ID_destino_JP"}
                         for p in sorted(archive.index) if p.startswith("es/" + prefix)
                         and p.endswith(".moflex") and not jp.exists(p[3:]))
    return {"schema": 1, "runtime_verified": False, "videos_decoded": False,
            "selected": 0, "compatible": len(rows), "rows": rows,
            "subtitles": subtitles, "pending": pending, "extra": extra}


def comprobar_consumidores(cro: bytes) -> dict:
    """Solo lectura: vídeo por stream y DAT cargado/interpretado por otra ruta."""
    if len(cro) < 0x17FD00 or cro[0x80:0x84] != b"CRO0":
        raise ValueError("CRO IE3 insuficiente")
    for address, word in ANCLAS_CONSUMIDORES.items():
        if struct.unpack_from("<I", cro, address)[0] != word:
            raise ValueError(f"consumidor de medios cambiado en {address:X}")
    if not cro.startswith(b"/data_iz/movie/txt/%s.dat\0", 0xAD1C):
        raise ValueError("ruta de subtítulos no coincide")
    imports = Cro(cro).imports()
    expected = {
        0x668: "nttcGetLength", 0x480: "FS_ReadFile",
        0x1678: "_ZN19nnfsFileInputStream13TryInitializeEPKw",
        0x1688: "_ZN2mw2mo6helper8FsReader10InitializeEPN2nn2fs15FileInputStreamEPNS3_3fnd10IAllocatorE",
        0x1690: "_ZN2mw2mo6helper8FsReader15GetMoflexReaderEv",
        0x1698: "mwmomoflexDemuxerCreate",
    }
    if any(imports.get(address) != name for address, name in expected.items()):
        raise ValueError("imports de medios no coinciden")
    return {"movie_stream": True, "subtitle_independent": True,
            "subtitle_ascii_discarded": True, "cro_changed": False,
            "anchors_checked": len(ANCLAS_CONSUMIDORES)}


def planificar_videos(jp, spark, ogre, cro: bytes, qa_jp: dict, qa_es: dict):
    """Plan de imágenes oficiales con línea temporal conservada, DAT JP literal.

    Exige QA de decodificación de ambos archivos ligados a sus SHA-256 y al
    mismo número de frames/fps. Retorna referencias serializables, no películas
    duplicadas en memoria. Nunca declara traducidos los subtítulos conservados.
    """
    consumer = comprobar_consumidores(cro)
    report = inventariar_videos(jp, spark, ogre)
    maps = []
    for qa in (qa_jp, qa_es):
        rows = qa["results"]
        mapping = {row["target"]: row for row in rows}
        if len(mapping) != len(rows):
            raise ValueError("QA de películas duplicada")
        maps.append(mapping)
    plan = {}
    for row in report["rows"]:
        target = row["target"]
        if any(target not in mapping for mapping in maps):
            raise ValueError(f"falta QA: {target}")
        old, new = [mapping[target] for mapping in maps]
        for result, info in ((old, row["before"]), (new, row["after"])):
            if (result["sha256"] != info["sha256"] or result["fps"] != 24
                    or result["frames"] <= 0 or result["decode"] != "sequential_eof"):
                raise ValueError(f"QA obsoleta/incompatible: {target}")
        if old["frames"] != new["frames"]:
            raise ValueError(f"cambia línea temporal: {target}")
        row.update(state="preparado_video_DAT_JP_preservado", frames=new["frames"])
        plan[target] = {key: row[key] for key in ("edition", "source", "after")}
    report.update(selected=len(plan), videos_decoded=True, consumer=consumer,
                  subtitle_localized=False, audio_sync_runtime_verified=False)
    return plan, report


def leer_video(plan_entry: dict, spark, ogre) -> bytes:
    """Obtiene una película del plan y vuelve a verificar el hash antes de emitir."""
    archive = {"spark": spark, "ogre": ogre}[plan_entry["edition"]]
    data = archive.read(plan_entry["source"])
    if descriptor_moflex(data) != plan_entry["after"]:
        raise ValueError("vídeo cambió después de planificar")
    return data


def elegir_fuente_video(ruta_jp: str, ediciones) -> dict | None:
    """Fuente europea de un MOFLEX japonés entre varias CIA europeas (Fuego, Rayo, Ogro).

    ``ediciones``: secuencia ``(etiqueta, rutas)`` en orden de preferencia, con ``rutas`` el conjunto
    de rutas del archive europeo. Por niveles, y en cada nivel la primera edición que lo tenga:

    1. ``es/<ruta>`` exacta (vídeo con rótulos en español: openings, eyecatches ``a3y``);
    2. ``<ruta>`` de la raíz (vídeo sin texto, común a los idiomas);
    3. el mismo nombre bajo otra carpeta ``es/…/movie/`` (último recurso).

    Así el opening del Ogro (``inazuma3_ogre/…/op00f``) sale de la CIA del Ogro y los ``a3y0Nf`` de
    ``inazuma3`` salen de la de Rayo en vez de caer en los del Ogro por nombre. El subtítulo es
    ``es/<carpeta>/movie/txt/<nombre>.dat``, preferentemente de la misma edición que el vídeo.
    Devuelve ``{edicion, video, edicion_dat, dat}`` (``dat`` None si no hay) o None sin fuente.
    """
    ediciones = [(tag, set(rutas)) for tag, rutas in ediciones]
    nombre = ruta_jp.rsplit("/", 1)[-1]
    niveles = (
        lambda rutas: ["es/" + ruta_jp] if "es/" + ruta_jp in rutas else [],
        lambda rutas: [ruta_jp] if ruta_jp in rutas else [],
        lambda rutas: sorted(p for p in rutas if p.startswith("es/") and "/movie/" in p
                             and p.rsplit("/", 1)[-1] == nombre),
    )
    for nivel in niveles:
        for tag, rutas in ediciones:
            encontradas = nivel(rutas)
            if encontradas:
                return {"edicion": tag, "video": encontradas[0],
                        **_elegir_dat(ruta_jp, tag, ediciones)}
    return None


def _elegir_dat(ruta_jp: str, edicion: str, ediciones) -> dict:
    carpeta, _, fichero = ruta_jp.partition("/movie/")
    tallo = fichero.rsplit(".", 1)[0]
    mismo = f"es/{carpeta}/movie/txt/{tallo}.dat"
    orden = sorted(ediciones, key=lambda e: e[0] != edicion)
    for tag, rutas in orden:
        if mismo in rutas:
            return {"edicion_dat": tag, "dat": mismo}
    for tag, rutas in orden:
        otros = sorted(p for p in rutas if p.startswith("es/") and p.endswith(f"/movie/txt/{tallo}.dat"))
        if otros:
            return {"edicion_dat": tag, "dat": otros[0]}
    return {"edicion_dat": None, "dat": None}
