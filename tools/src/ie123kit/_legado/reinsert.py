#!/usr/bin/env python3
"""[Etapa 7] Re-encoder real: aplica el espanol (sin acentos) a archive.fa.

Estrategia bulletproof (no depende de la semantica exacta del formato de chunk):
- Cada cadena de dialogo es un chunk delimitado por NUL: [tipo][b2][texto...].
- Se conservan los 2 bytes de prefijo y se sustituye el texto por el ES romanizado
  (ASCII/Shift-JIS), manteniendo el MISMO nº de bytes del chunk (relleno con
  espacios / recorte). => tamano descomprimido del evento INVARIANTE => todo offset
  y longitud interna sigue valido. Se re-LZ10 y se rellena al tamano original de la
  entrada (padding ignorado). archive.fa queda del MISMO tamano -> parche in-place.

Acentos: de momento se romanizan (a/e/i/o/u/n, ! ?). La fuente (etapa 6) los
restaura luego. Solo se aplican lineas con es_final (estado != pendiente).

Uso:
    python -m ie123kit._legado.reinsert           # patчea work/shared/base_3ds/romfs/archive.fa -> work/archive_es.fa
"""
import csv
import os
import struct
import sys

import re as _re
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.compresion.lz10 import compress, decompress
from ie123kit.nucleo.eventos.packnum import parse_index
from ie123kit.nucleo.texto.nds_latin import decode_cadena as _decode_string
from ie123kit.nucleo.fuentes.glifos import patch_font_bytes, PLAN as _PLAN
from ie123kit.nucleo.texto import sjis_portador as _sjis_portador
from ie123kit.nucleo.texto.sjis_portador import _acc, GREEK, FONTS, es_encode, BOX_W, _BASE, _advance


def __getattr__(nombre):
    if nombre == "_ADV":
        return _sjis_portador._ADV
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")


_EN = _re.compile(r"[A-Za-z]{4,}")
_MK = _re.compile(rb"%[1-9]F")          # marcadores furigana en bytes


def looks_like_dialogue(s):
    """True si parece DIALOGO real (no etiqueta/comentario/debug del script).

    Las cadenas estructurales (etiquetas como スカウトキャラ配置, comentarios que
    empiezan por '(', debug en ingles como 'Mobilephone') NO deben traducirse:
    el script las referencia y sustituirlas cuelga el juego.
    """
    s = (s or "").strip()
    if not s or s[0] in "(（/#=":
        return False
    if _EN.search(s):                      # palabra inglesa larga = debug
        return False
    # dialogo real: tiene particulas hiragana (0x3040-0x309F)
    return sum(1 for c in s if 0x3040 <= ord(c) <= 0x309F) >= 2

REPO = str(find_root())


def find_file(arc, suffix):
    for path, off, size in arc.entries:
        if path.endswith(suffix):
            return off, size
    raise SystemExit("no encontrado: " + suffix)


# (carpeta_3ds, carpeta_translation) de cada juego incluido en la build
GAMES = [("inazuma1", "game1"), ("inazuma2", "game2")]


def reflow(text):
    """Re-ajusta el texto ES a BOX_W cortando solo entre palabras (preserva paginas \\f)."""
    if not text or "\\n" not in text and sum(_advance(c) for c in text.split("\\f")[0]) <= BOX_W:
        return text                                      # ya cabe en una linea
    out = []
    for page in text.split("\\f"):
        words = page.replace("\\n", " ").split(" ")
        lines, cur, cw = [], "", 0
        for w in words:
            if not w:
                continue
            ww = sum(_advance(c) for c in w)
            sp = _advance(" ") if cur else 0
            if cur and cw + sp + ww > BOX_W:
                lines.append(cur); cur, cw = w, ww
            else:
                cur = (cur + " " + w) if cur else w; cw += sp + ww
        if cur:
            lines.append(cur)
        out.append("\\n".join(lines))
    return "\\f".join(out)


def load_translations(game):
    """{event_id: {japones_limpio: es_final}} para lineas con es_final (re-ajustadas)."""
    out = {}
    # Las carpetas se renombraron a ie1/ie2 en la migracion del 2026-09-16
    # (docs/ARQUITECTURA.md) pero la clave interna sigue siendo game1/game2.
    # ds_official.py ya hacia esta misma conversion al escribir; aqui faltaba,
    # asi que load_translations no encontraba nada y el bucle de dialogo se
    # saltaba EN SILENCIO: la build salia con las fuentes parcheadas y el
    # texto en japones.
    carpeta = game.replace("game", "ie")
    path = os.path.join(REPO, "translation", carpeta, "dialogo.csv")
    if not os.path.exists(path):
        return out
    for row in csv.DictReader(open(path, encoding="utf-8")):
        if row["estado"] == "pendiente" or not row["es_final"]:
            continue
        out.setdefault(int(row["event_id"]), {})[row["japones"]] = reflow(row["es_final"])
    # OFICIAL: el diálogo oficial del DS (ie123kit._legado.ds_official -> dialogo_oficial.csv)
    # tiene PRIORIDAD sobre la IA (texto oficial de Nintendo, mismo evento+línea).
    # SOLO en eventos STRIP (historia): meterlo en la apertura PROTEGIDA (furigana)
    # descuadra el crear-partida (pantalla negra). Fichero local gitignored (copyright).
    ofi = os.path.join(REPO, "translation", carpeta, "dialogo_oficial.csv")
    if os.path.exists(ofi):
        from ie123kit._legado.reinsert_var import is_strip_event        # lazy: evita import circular
        for row in csv.DictReader(open(ofi, encoding="utf-8")):
            eid = int(row["event_id"])
            if is_strip_event(eid):
                out.setdefault(eid, {})[row["japones"]] = reflow(row["es_oficial"])
    return out


def _repaginate(es, n):
    """Reparte el texto ES en EXACTAMENTE n paginas NO vacias (en limites de linea \\n/\\f).
    El motor consume marcadores por pagina, asi que el nº de paginas DEBE coincidir con el JP;
    cuando el traductor uso \\n donde el JP usa \\f (paginas != ), re-paginamos en vez de
    rechazar la linea (que la dejaba en japones). Devuelve lista de n paginas, o None si no hay
    lineas suficientes para n paginas no vacias (entonces se rechaza -> japones, seguro: nunca
    una pagina vacia, que CUELGA el motor ❌#4)."""
    lines = [l for l in es.replace("\\f", "\\n").split("\\n") if l.strip()]
    if len(lines) < n:
        return None                                  # no hay lineas para n paginas no vacias
    pages = [[] for _ in range(n)]
    for i, l in enumerate(lines):
        pages[i * n // len(lines)].append(l)          # repartir lineas equilibrado entre n paginas
    res = ["\\n".join(p) for p in pages]
    if any(not p.strip() for p in res):
        return None                                  # alguna pagina quedaria vacia -> rechazar
    return res


def _furigana_body_bytes(orig_body, es, budget, allow_repaginate=True):
    """v20+: construye el CUERPO (bytes) del chunk furigana traducido, a prueba de
    truncado. Reparte los marcadores %NF POR PAGINA igual que el original (el motor
    consume 1 lectura por marcador y pagina) y cada marcador lleva detras N espacios
    de ANCHO COMPLETO (U+3000, 2 bytes, como los kanji) para que el ruby no se salga.
    Los marcadores NUNCA se truncan: si no caben enteros en 'budget', devuelve None
    (-> dejar la linea en japones). Devuelve bytes rellenos a 'budget', o None."""
    orig_pages = orig_body.split(b"\\f")
    es_pages = es.split("\\f")
    # El nº de paginas DEBE coincidir (marcadores por pagina). Si el ES difiere, RE-PAGINAR
    # (repartir las lineas del ES en len(orig_pages) paginas) en vez de rechazar -> recupera
    # las lineas traducidas que el traductor dejo con \\n donde el JP usa \\f. Si no se puede
    # re-paginar sin paginas vacias, devolver None (japones, seguro).
    if len(es_pages) != len(orig_pages):
        es_pages = _repaginate(es, len(orig_pages)) if allow_repaginate else None
        if es_pages is None:
            return None
    marks_pp = [[m.group().decode() for m in _MK.finditer(p)] for p in orig_pages]
    npages = len(es_pages)
    prefixes = [es_encode("".join(m + "　" * int(m[1]) for m in (marks_pp[i] if i < len(marks_pp) else [])),
                          1 << 30) for i in range(npages)]   # marcadores enteros, sin recorte
    sep = 2 * (npages - 1)                            # los "\\f" entre paginas (2 bytes c/u)
    fixed = sum(len(p) for p in prefixes) + sep
    if fixed > budget:
        return None                                  # ni los marcadores caben -> revertir linea
    rem = budget - fixed
    out = []
    for i in range(npages):
        share = rem // (npages - i)                  # reparto del presupuesto de texto restante
        body = es_encode(es_pages[i], share)
        rem -= len(body)
        out.append(prefixes[i] + body)
    full = b"\\f".join(out)
    return full + b" " * (budget - len(full))


def _is_reading(part):
    """True si el chunk es una LECTURA de furigana. Las lecturas se numeran
    SECUENCIALMENTE por evento: [indice][estilo][kana...], p.ej \\x02\\x0cひとり,
    \\x03\\x10れんしゅう, \\x04\\x0cはじ... (indice 0x02..0x1f, estilo 0x08/0x0c/0x10).
    El cuerpo tras los 2 bytes de prefijo es kana puro."""
    if len(part) < 4 or not (2 <= part[0] <= 0x1f) or part[1] not in (0x08, 0x0c, 0x10, 0x14, 0x18):
        return False
    try:
        s = part[2:].split(b"\x00")[0].decode("shift-jis")
    except Exception:
        return False
    s = s.strip()
    return bool(s) and all(0x3040 <= ord(c) <= 0x30FF or c == "ー" for c in s)


def reencode_event(dec, trans, esize):
    """Sustituye las cadenas traducidas (tamano de chunk invariante). Si el evento
    recomprimido no cabe, revierte lineas (las que mas ocupan) hasta que quepa, en
    vez de saltar el evento entero. Devuelve (comp_bytes_o_None, n_aplicadas).

    Modos de furigana (env):
    - (ninguno) = v10: SALTAR los chunks con marcadores (seguro, ~30% dialogo).
    - FURIGANA_KEEP_MARKERS = v13: traducir y re-colgar marcadores al final
      (DEFECTUOSO: el marcador sin texto base detras cuelga el motor).
    - FURIGANA_STRIP = v14: traducir el dialogo SIN marcadores y VACIAR los chunks
      de lectura (kana) -> espanol limpio, sin ruby ni basura, mismo tamano."""
    orig = dec.split(b"\x00")
    parts = list(orig)
    changed = []                                    # (idx, peso_es)
    KEEP = os.environ.get("FURIGANA_KEEP_MARKERS")
    STRIP = os.environ.get("FURIGANA_STRIP")
    INPLACE = os.environ.get("FURIGANA_INPLACE")
    stripped = 0
    pending = 0                                    # nº de lecturas a vaciar tras un dialogo traducido
    for i, part in enumerate(orig):
        # SOLO vaciar las lecturas que pertenecen a un dialogo que ACABAMOS de
        # traducir (1 lectura por marcador). Asi no tocamos kana estructural
        # (menus, nombres) que no es furigana -> evita romper el juego.
        if STRIP and pending > 0 and _is_reading(part):
            parts[i] = bytes(part[:2]) + b" " * (len(part) - 2)
            pending -= 1
            stripped += 1
            continue
        if len(part) < 3 or part[0] not in (1, 2, 4):
            continue
        marks = _MK.findall(part)                  # marcadores en orden, p.ej [b'%1F',b'%2F']
        if marks and not (KEEP or STRIP or INPLACE or os.environ.get("TRANSLATE_FURIGANA")):
            continue                               # comportamiento v10 (seguro): saltar furigana
        clean = _decode_string(part, "sjis")
        if not looks_like_dialogue(clean):       # excluir etiquetas/comentarios/debug
            continue
        es = trans.get(clean)
        if not es:
            continue
        es = _re.sub(r"%[1-9]F", "", es)           # quitar cualquier %NF huerfano del ES
        # (un marcador suelto en el texto, sin N chars de ancho completo detras,
        #  descuadra el motor y cuelga; los marcadores correctos los pone el INPLACE)
        budget = len(part) - 2
        if marks and INPLACE:
            body = _furigana_body_bytes(part[2:], es, budget)  # marcadores enteros, por pagina
            if body is None:
                continue                             # no caben los marcadores -> dejar japones
            weight = len(body)
        elif marks and STRIP:
            # v24: QUITAR los marcadores del todo (espanol limpio, sin rellenos ->
            # TODO el presupuesto de bytes para el texto, sin cortes) y VACIAR las N
            # lecturas siguientes (para que no salgan kana sueltos ni se descuadre).
            body = es_encode(es, budget)
            weight = len(body)
            body = body + b" " * (budget - len(body))
            pending += len(marks)                  # vaciar las N lecturas siguientes
        elif marks and KEEP:
            tail = b" " + b"".join(marks)          # v13 (DEFECTUOSO): marcadores al final
            body = es_encode(es, budget - len(tail))
            weight = len(body) + len(tail)
            body = body + tail
            body = body + b" " * (budget - len(body))
        else:
            body = es_encode(es, budget)           # v10/sin-furigana: ES limpio
            weight = len(body)
            body = body + b" " * (budget - len(body))
        parts[i] = bytes(part[:2]) + body
        changed.append((i, weight))
    if not changed and not stripped:
        return None, 0
    comp = compress(b"\x00".join(parts))
    n = len(changed)
    if len(comp) > esize:
        for idx, _w in sorted(changed, key=lambda x: -x[1]):
            parts[idx] = orig[idx]                   # revertir a japones (el peor primero)
            n -= 1
            comp = compress(b"\x00".join(parts))
            if len(comp) <= esize:
                break                                # reverter todo -> original siempre cabe
    if len(comp) > esize:
        return None, 0
    return comp + b"\x00" * (esize - len(comp)), n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    src = os.path.join(REPO, "work", "shared", "base_3ds", "romfs", "archive.fa")
    dst = os.path.join(REPO, "work", "archive_es.fa")
    data = bytearray(open(src, "rb").read())
    arc = FaArchive(src)

    games = [g for g in GAMES if g[1] in sys.argv] or GAMES
    if os.environ.get("SKIP_DIALOGUE"):
        games = []                                 # diagnostico: solo parchear fuentes
    for folder, game in games:
        trans = load_translations(game)
        if not trans:
            continue
        pkb_off, pkb_size = find_file(arc, f"{folder}/data_iz/script/eve.pkb")
        pkh_off, pkh_size = find_file(arc, f"{folder}/data_iz/script/eve.pkh")
        pkb = bytearray(data[pkb_off:pkb_off + pkb_size])
        ents = parse_index(bytes(data[pkh_off:pkh_off + pkh_size]))
        ev_ok = lines = 0
        skip_sys = os.environ.get("SKIP_SYSTEM")
        skip_pref = os.environ.get("SKIP_EID_PREFIX")   # p.ej "9201" salta la apertura
        for eid, eoff, esize in ents:
            if eid not in trans:
                continue
            if skip_sys and eid >= 90000000:        # diagnostico: no tocar eventos de sistema/intro/menu
                continue
            if skip_pref and str(eid).startswith(skip_pref):
                continue
            dec = decompress(bytes(pkb[eoff:eoff + esize]))
            comp, n = reencode_event(dec, trans[eid], esize)
            if comp is None:                         # nada aplicado o no cabe
                continue
            pkb[eoff:eoff + esize] = comp
            ev_ok += 1; lines += n
        data[pkb_off:pkb_off + pkb_size] = pkb
        print(f"{game}: {ev_ok} eventos, {lines} lineas ES")

    # parchear fuentes (anadir glifos ES) - mismo tamano, in-place
    for fp in FONTS:
        foff, fsize = find_file(arc, fp)
        ext = os.path.join(REPO, "work", "shared", "fa_extract", *fp.split("/"))
        patched = patch_font_bytes(ext)
        assert len(patched) == fsize, f"{fp}: tamano cambio {len(patched)}!={fsize}"
        data[foff:foff + fsize] = patched

    # ROSTER: nombre europeo en el RECUADRO AZUL del hablante (campo +16 de unitbase.dat,
    # mismo tamano, in-place). Muestra Mark/Nathan/Jack... en vez de えんどう/かぜまる/かべやま.
    # SEGURO (ds_roster.patch_unitbase): solo toca +16 (token unico). NO toca +0/+32
    # (llevan separador 0x8140 que el motor parsea por offset; escribir ASCII ahi causaba
    # el crash "unmapped Read8"). Desactivable con NO_ROSTER=1. Ver issue #16.
    from ie123kit._legado import ds_roster as DR                                # lazy: evita import circular
    for game, (dsdir, suf) in ([] if os.environ.get("NO_ROSTER") else DR.GAMES.items()):
        try:
            doff, dsize = find_file(arc, suf)
        except Exception:
            continue
        ds_path = os.path.join(REPO, "work", dsdir, "data_iz", "logic", "sp", "unitbase.dat")
        if not os.path.exists(ds_path):
            continue
        patched, nrec = DR.patch_unitbase(bytes(data[doff:doff + dsize]), open(ds_path, "rb").read())
        assert len(patched) == dsize
        data[doff:doff + dsize] = patched
        print(f"roster {game}: {nrec} nombres europeos en unitbase.dat")

    open(dst, "wb").write(data)
    print(f"fuentes parcheadas: {len(FONTS)}")
    print(f"-> {dst} (mismo tamano = {len(data)})")


if __name__ == "__main__":
    main()
