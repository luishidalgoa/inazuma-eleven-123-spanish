#!/usr/bin/env python3
"""[Longitud VARIABLE] Redimensiona los eventos del eve.pkb para meter el espanol
SIN cortes. Clave (verificada en work/find_refs.py): los chunks de DIALOGO se
consumen SECUENCIALMENTE (no se referencian por offset), asi que se pueden agrandar;
solo las cadenas de debug del inicio se referencian por offset rel_s10 -> esas NO se
tocan (y al ir ANTES del dialogo, no se mueven al agrandar el dialogo).

Salida: work/eve_var/<game>.pkb + .pkh reempaquetados (eventos de tamano variable,
indice pkh con offsets nuevos). Luego fa_repack.py mete el pkb en archive.fa.

Reusa helpers de reinsert.py (glosario, es_encode, furigana INPLACE).
"""
import csv, os, struct, sys
import re as _re
from ie123kit.nucleo.contenedores.fa import FaArchive
# Para longitud variable usamos compresion "store" (todo literales): O(n), instantanea.
# El tamano no importa (el contenedor se reconstruye); la velocidad si (~4000 eventos).
from ie123kit.nucleo.compresion.lz10 import compress_store as compress, decompress
from ie123kit.nucleo.eventos.packnum import parse_index
from ie123kit.nucleo.texto.nds_latin import decode_cadena as _decode_string
from ie123kit._legado import reinsert as R

REPO = R.REPO
GAMES = R.GAMES

# Eventos de ZONA (nombre de area + diálogos de NPC) que, aun siendo de sistema
# (eid>=90000000), se STRIPean: sufren el bug #2 (cuelgue al hablar con NPC, especifico
# del furigana). Son gameplay post-intro, no afectan al crear-partida. Detectados por
# tener nombre-de-zona tipo0x03 + diálogos con marcadores entre los eventos protegidos.
# (vacio) Antes forzaba strip de 92040800/92062100 (正門エリア) pero el strip CRECE el texto
# y DESPLAZA las señales de sonido/animacion que el motor consume por POSICION -> desync ->
# diálogos VACIOS en runtime (datos OK pero render roto). Ahora se tratan como no-strip
# (blank-readings, mismo tamaño): truncado pero estable. Ver FURIGANA_LECCIONES ❌#12.
STRIP_ZONA = set()
# Eventos de gameplay que CRASHEAN con texto-completo (el motor de ruby ❌#9): se tratan como
# SISTEMA (conservar marcadores, furigana en japones, planas en español) = estable sin crash.
# Se amplia segun se cazan jugando. Ver FURIGANA_LECCIONES ❌#9.
DONT_STRIP = {81000040}   # NPC tutorial (回復サイト)
# Eventos HIPER-SENSIBLES: crashean con CUALQUIER cambio (strip Y blank-readings). Se dejan
# 100% ORIGINALES (japones, sin traducir): el original no crashea. Se pierde la traduccion de
# ese NPC pero es ESTABLE. Ej: tutorial 81000040 -> 0x00184AAC al stripear, 0x00ABFCC0 al
# blank-readear. Se amplia segun los cazamos. Mejor japones estable que crash.
DONT_TOUCH = {
    81000040,   # NPC tutorial (回復サイト, "ventana emergente"): cualquier cambio lo tumba
}


def is_grow_safe(dec, string_slots):
    """True si el evento se puede CRECER (strip a texto completo) sin romper referencias.
    False si tiene refs a byte-id/lectura/control NO reubicables: su opcode MEZCLA refs con
    operandos numericos (p.ej. op 0x01026001 = 76% numeros) -> reubicarlas corromperia los
    numeros = crash Read32 ❌#11. Por eso no estan en string_slots. Al crecer el texto, esos
    byte-id se desplazan y la ref apunta mal -> DIALOGO VACIO. Esos eventos -> blank-readings
    (mismo tamaño = no se desplaza nada = sin vacio). Es la clasificacion automatica que
    sustituye al whack-a-mole de zonas. Ver FURIGANA_LECCIONES ❌#12/#13."""
    if dec[:4] != b"SSD\x00":
        return True
    s10 = struct.unpack_from("<I", dec, 0x10)[0]
    starts = {}; r = 0
    for p in dec[s10:].split(b"\x00"):
        starts[r] = p; r += len(p) + 1
    for opos, op, slot in _instr_operands(dec[:s10], s10):
        v = struct.unpack_from("<I", dec, opos)[0]
        if v and v in starts and (op, slot) not in string_slots:
            ch = starts[v]
            # ref a byte-id (1 byte >=0x80) o a chunk TIPADO (lectura/control 0x02-0x1f):
            # son referencias reales que se rompen al desplazarse. (Dialogo 0x01 / mid-chunk
            # numerico no se referencian -> no cuentan.)
            if (len(ch) == 1 and ch[0] >= 0x80) or (len(ch) >= 2 and 2 <= ch[0] <= 0x1f):
                return False
    return True


def is_strip_event(eid):
    """True si el evento se STRIPea (historia/gameplay): quita furigana, texto completo.
    False = evento PROTEGIDO (apertura/sistema/menu): furigana a mismo tamano (=v25), NO
    se le aplica la traduccion oficial (descuadra el crear-partida). Debe coincidir con
    la decision 'strip' de main()."""
    if eid in DONT_STRIP:
        return False                          # crashea al stripear -> blank-readings
    # EXPERIMENTAL (STRIP_ALL=1): stripear TODO, incluido intro/sistema -> quita el furigana
    # japones de TODOS los dialogos. El cuelgue ❌#1 (crear-partida) lo causaba el DESBALANCE
    # marcador<->lectura, ya corregido con drop_readings; validate.py caza el desbalance
    # offline antes de compilar. Riesgo residual: la apertura (92010200) podria exigir
    # marcadores aun balanceada -> probar con PARTIDA NUEVA.
    if os.environ.get("STRIP_ALL"):
        return True
    return eid < 90000000 or eid in STRIP_ZONA or 92010510 <= eid < 92011000
# Ademas se STRIPea el bloque de gameplay del cap.1 [92010510, 92011000): zona
# サークル棟エリア (92010510) y los eventos interactivos siguientes (92010520 "Axel se
# fue", 92010600 torre, 92010640 entreno, 92010730 casa, 92010820, 92010900...). Son
# POST-control (el crear-partida es la apertura 92010100..92010509) -> STRIP seguro,
# arregla el bug #2 (cuelgue al hablar, furigana-especifico) y da texto completo.


def _instr_operands(code, s10):
    """Recorre el stream de instrucciones SSD (desde 0x20) y produce (pos_operando,
    opcode_u32, slot). Formato de instruccion VERIFICADO en el ROM:
        <u16 indice><u16 longitud><u32 opcode><operandos u32...>
    'longitud' (en +2) es el tamano TOTAL de la instruccion en bytes (incluye los 8 de
    cabecera+opcode). Asi se distinguen con PRECISION los operandos de los opcodes/
    cabeceras: clave para no corromper contadores numericos (causa del crash Read32)."""
    i = 0x20
    while i + 8 <= s10:
        ln = struct.unpack_from("<H", code, i + 2)[0]
        if ln < 8 or i + ln > s10:
            return
        op = struct.unpack_from("<I", code, i + 4)[0]
        for slot, opos in enumerate(range(i + 8, i + ln, 4)):
            yield opos, op, slot
        i += ln


def build_string_slots(events):
    """Clasifica que (opcode, slot) son OFFSETS DE STRING (referencias a texto) frente a
    operandos numericos/indice. Criterio data-driven verificado en el ROM: un slot de
    offset apunta SIEMPRE al INICIO de un chunk o vale 0 (nulo); casi NUNCA cae a media
    cadena. Un slot numerico (contador, coordenada, ID, delay) cae a media cadena ~40-80%
    de las veces (valores aleatorios). Devuelve el set de (opcode_u32, slot) de string.

    Solo estos se reubican al crecer el dialogo (offset-fixup). Los demas operandos se
    dejan INTACTOS -> nunca se corrompe un contador (eso convertia un 6 en un offset
    grande y el motor leia un array hasta salirse de la RAM = crash 'unmapped Read32')."""
    from collections import Counter
    tot = Counter(); hit = Counter(); zero = Counter(); mid = Counter()
    for dec in events:
        if dec[:4] != b"SSD\x00":
            continue
        s10 = struct.unpack_from("<I", dec, 0x10)[0]
        code = dec[:s10]; text = dec[s10:]; tlen = len(text)
        starts = set(); r = 0
        for p in text.split(b"\x00"):
            starts.add(r); r += len(p) + 1
        for opos, op, slot in _instr_operands(code, s10):
            v = struct.unpack_from("<I", code, opos)[0]
            key = (op, slot); tot[key] += 1
            if v == 0:
                zero[key] += 1
            elif 16 <= v < tlen:
                if v in starts:
                    hit[key] += 1
                else:
                    mid[key] += 1
    return {k for k in tot
            if tot[k] >= 10 and hit[k] >= 5
            and (hit[k] + zero[k]) / tot[k] >= 0.90 and mid[k] / tot[k] <= 0.03}


def _furigana_var(orig_body, es):
    """Cuerpo furigana de longitud VARIABLE (sin relleno): marcadores por pagina
    (ancho completo) + texto ES completo. Devuelve bytes o None si las paginas no
    casan. NO asigna relleno (a diferencia de _furigana_body_bytes con budget enorme)."""
    orig_pages = orig_body.split(b"\\f")
    es_pages = es.split("\\f")
    if len(es_pages) != len(orig_pages):
        return None
    out = []
    for i, esp in enumerate(es_pages):
        mk = [m.group().decode() for m in R._MK.finditer(orig_pages[i])]
        prefix = "".join(m + "　" * int(m[1]) for m in mk)   # marcador + N espacios ancho completo
        out.append(R.es_encode(prefix + esp, 1 << 20))           # 1MB tope = sin cortar, sin alloc enorme
    return b"\\f".join(out)


def _blank_reading(part):
    """Oculta el japones de una LECTURA furigana SIN romper nada: conserva el prefijo
    [indice][estilo] (2 bytes) y sustituye el kana por espacios ANCHO COMPLETO del MISMO
    tamano en bytes. Asi el chunk sigue en su sitio (el motor lo consume = 1 por marcador,
    balanceado), no se reubica nada (mismo tamano -> sin ❌#9/#10), pero el ruby se dibuja
    en blanco -> el えんどう deja de verse. Solo para eventos NO-strip (intro/sistema), que
    no se pueden stripear (❌#1/#12)."""
    body = part[2:]
    n = len(body)
    fill = b"\x81\x40" * (n // 2) + (b"\x20" * (n % 2))   # 0x8140 = espacio ancho completo SJIS
    return bytes(part[:2]) + fill


def reencode_var(dec, trans, strip=False, string_slots=frozenset(), dbg_eid=None,
                 grow_fg=False):
    """Redimensiona el dialogo a longitud COMPLETA y reubica SOLO las referencias de
    string del bytecode (offset-fixup PRECISO via 'string_slots'), dejando INTACTOS los
    operandos numericos/indice. Devuelve (nuevo_dec, n_lineas).

    'string_slots' = set de (opcode, slot) que son offsets de string (build_string_slots,
    criterio: el operando apunta SIEMPRE a inicio de chunk o vale 0, casi nunca a media
    cadena). Solo esos operandos se reubican al crecer el texto; cualquier otro u32 que
    por azar coincida con una posicion de chunk se IGNORA. Asi NUNCA se corrompe un
    contador/indice (eso convertia p.ej. un 6 en un offset grande y un handler leia un
    array hasta salirse de la RAM = crash 'unmapped Read32 ... PC 0x001C8D68').

    strip=True (HISTORIA): QUITA el furigana (marcadores %NF) y crece el texto a longitud
    completa, vaciando las N lecturas siguientes (mismo tamano). strip=False (sistema/
    intro): furigana a MISMO TAMANO (=v25 INPLACE) para no romper el crear-partida
    (FURIGANA_LECCIONES ❌#1) ni el runtime de ruby al crecer (❌#8)."""
    if dec[:4] != b"SSD\x00":
        return dec, 0
    s10 = struct.unpack_from("<I", dec, 0x10)[0]
    head = bytearray(dec[:s10])               # cabecera + codigo (mutable para el fixup)
    text = dec[s10:]
    tlen = len(text)
    parts = text.split(b"\x00")
    old_starts = set(); _r = 0                 # inicios de chunk en el texto ORIGINAL
    for _p in parts:
        old_starts.add(_r); _r += len(_p) + 1

    # 1) Decidir el contenido nuevo de cada chunk (bytes) o ELIMINARLO (None).
    #    CLAVE del bug del bloqueo (controles bloqueados al hablar con NPC): el motor
    #    consume 1 LECTURA furigana por cada MARCADOR %NF. Al traducir (STRIP) quitamos
    #    los marcadores -> 0 marcadores; si dejamos las lecturas como chunks, quedan
    #    lecturas HUERFANAS (sin marcador que las consuma) que el motor lee como lineas
    #    vacias / se descuadra -> no cierra el dialogo. Solucion: ELIMINAR las lecturas
    #    de las lineas traducidas (no vaciarlas) -> marcadores y lecturas balanceados.
    new_content = []                          # contenido nuevo por chunk (None = eliminar)
    n = 0
    drop_readings = False                      # ¿eliminar las lecturas que siguen? (linea STRIP)
    for part in parts:
        content = part
        if strip and drop_readings and R._is_reading(part):
            # La linea traducida quedo SIN marcadores -> consume 0 lecturas -> eliminar
            # TODAS sus lecturas (hasta la siguiente linea de dialogo). Asi marcadores y
            # lecturas quedan balanceados como en el original (clave del bloqueo de NPCs).
            content = None
        elif (not strip) and R._is_reading(part):
            # INTRO/SISTEMA (no se puede stripear, ❌#1/#12): la lectura NO se elimina
            # (rompe el balance/crear-partida) pero se VACIA -> el japones del furigana
            # deja de verse. Mismo tamano, sin reubicar. Arregla el "japones que empuja
            # el texto" del intro sin tocar nada de lo que crashea.
            content = _blank_reading(part)
        elif len(part) >= 3 and part[0] in (1, 2, 4):
            marks = R._MK.findall(part)
            clean = _decode_string(part, "sjis")
            if R.looks_like_dialogue(clean):
                drop_readings = False         # reset: nueva linea de dialogo
                es = trans.get(clean)
                if strip and dbg_eid is not None:
                    # MODO DEBUG: anteponer el [event_id] a CADA linea de dialogo (con su
                    # traduccion ES si existe, o solo el ID si no). Asi al hablar con un NPC
                    # se ve "[92010640] texto..." -> identifica el evento interno de cada
                    # personaje. Strip (sin furigana) = seguro. Solo eventos strip (gameplay).
                    body = _re.sub(r"%[1-9]F", "", es) if es else ""
                    content = bytes(part[:2]) + R.es_encode("[%d]%s" % (dbg_eid, body), 1 << 20)
                    n += 1
                    drop_readings = True
                elif es:
                    es = _re.sub(r"%[1-9]F", "", es)
                    if not strip and grow_fg:
                        # PRUEBA (intro variable-length): CRECER conservando el furigana
                        # (marcadores + ancho completo via _furigana_var) -> texto completo
                        # SIN truncar y SIN quitar marcadores (no rompe el crear-partida #1).
                        # Riesgo: runtime de ruby (❌#9). Las lecturas se mueven y el
                        # offset-fixup preciso las reubica. Si las paginas no casan, fallback
                        # a mismo-tamano.
                        if marks:
                            body = _furigana_var(part[2:], es)
                            if body is None:
                                body = R._furigana_body_bytes(part[2:], es, len(part) - 2)
                            if body is not None:
                                content = bytes(part[:2]) + body; n += 1
                        else:
                            content = bytes(part[:2]) + R.es_encode(es, 1 << 20); n += 1
                    elif not strip:
                        # SISTEMA/INTRO: MISMO TAMANO (= v25 INPLACE): crecer una linea con
                        # furigana cuelga (ruby ❌#8); plana mas larga desplaza el furigana.
                        budget = len(part) - 2
                        if marks:
                            body = R._furigana_body_bytes(part[2:], es, budget)
                            if body is not None:
                                content = bytes(part[:2]) + body; n += 1   # mismo tamano
                        else:
                            b = R.es_encode(es, budget)
                            content = bytes(part[:2]) + b + b" " * (budget - len(b)); n += 1
                    else:
                        # HISTORIA (strip): crece a texto COMPLETO, sin furigana, y se
                        # ELIMINAN sus lecturas (no tiene marcadores -> 0 lecturas).
                        content = bytes(part[:2]) + R.es_encode(es, 1 << 20); n += 1
                        drop_readings = True
        new_content.append(content)

    # 2) Construir el texto nuevo y el mapa old_start -> new_start (None si se elimino).
    out = bytearray()
    pos_map = {}
    rel = 0
    first = True
    for part, content in zip(parts, new_content):
        if content is None:
            pos_map[rel] = None               # chunk eliminado
        else:
            if not first:
                out += b"\x00"                # separador antes de cada chunk salvo el 1º
            pos_map[rel] = len(out)
            out += content
            first = False
        rel += len(part) + 1
    new_text = bytes(out)

    # 3) FIXUP PRECISO: reubicar SOLO operandos de slots-string que apuntan a un inicio de
    #    chunk movido. Si alguno apunta a un chunk ELIMINADO, no es honrable -> revertir el
    #    evento a japones (seguro). Los operandos numericos/indice NO se tocan.
    relocated = []
    for opos, op, slot in _instr_operands(head, s10):
        if (op, slot) not in string_slots:
            continue
        v = struct.unpack_from("<I", head, opos)[0]
        if v in old_starts:                   # es una referencia a un inicio de chunk
            np = pos_map[v]
            if np is None:
                return dec, 0                 # apunta a chunk eliminado -> revertir
            if np != v:
                struct.pack_into("<I", head, opos, np)
                relocated.append(opos)
    # VALIDACION: cada operando reubicado debe caer EXACTO en un inicio de chunk nuevo.
    if relocated:
        new_starts = set(); _r = 0
        for _p in new_text.split(b"\x00"):
            new_starts.add(_r); _r += len(_p) + 1
        for opos in relocated:
            if struct.unpack_from("<I", head, opos)[0] not in new_starts:
                return dec, 0                 # shift descuadrado -> revertir (seguro)

    if n == 0:
        return dec, 0                         # nada traducido -> dejar original
    new_dec = bytearray(bytes(head) + new_text)
    struct.pack_into("<I", new_dec, 0x08, len(new_dec))       # tamano total
    return bytes(new_dec), n


def main():
    if "--legado-lo-se" not in sys.argv:
        sys.stderr.write("ERROR: reinsert_var está en cuarentena (obsolete_dangerous; ver docs/FURIGANA_LECCIONES.md). Sustituto: ninguno (el offset-fixup corrompía eventos, ❌#8/#11/#13). Para ejecutarlo igualmente añade --legado-lo-se.\n")
        return 2
    sys.argv.remove("--legado-lo-se")
    sys.stdout.reconfigure(encoding="utf-8")
    src = os.path.join(REPO, "work", "shared", "base_3ds", "romfs", "archive.fa")
    data = open(src, "rb").read()
    arc = FaArchive(src)
    outdir = os.path.join(REPO, "work", "eve_var")
    os.makedirs(outdir, exist_ok=True)

    games = [g for g in GAMES if g[1] in sys.argv] or GAMES
    for folder, game in games:
        trans = R.load_translations(game)
        if not trans:
            continue
        # MAPA GLOBAL {japones: es}: union de TODAS las traducciones (cualquier evento). El
        # fallback en reencode_ssd lo usa cuando la busqueda por-evento falla -> recupera las
        # lineas cuyo mismo texto japones esta traducido en OTRO evento (~5575, 48%->~70%
        # cobertura). NO_GLOBAL=1 lo desactiva (diagnostico). Conflicto jp->es distinto: gana
        # la ultima vista (suficiente; el grueso son frases NPC/sistema contexto-independientes).
        gtrans = None
        if not os.environ.get("NO_GLOBAL"):
            gtrans = {}
            for _ev in trans.values():
                gtrans.update(_ev)
        pkb_off, pkb_size = R.find_file(arc, f"{folder}/data_iz/script/eve.pkb")
        pkh_off, pkh_size = R.find_file(arc, f"{folder}/data_iz/script/eve.pkh")
        pkh = bytes(data[pkh_off:pkh_off + pkh_size])
        pkb = data[pkb_off:pkb_off + pkb_size]
        ents = parse_index(pkh)
        # Pre-descomprimir TODOS los eventos para clasificar los slots-string (que
        # (opcode,slot) del bytecode son offsets de texto) -> fixup preciso, sin corromper
        # operandos numericos. Es la diferencia entre arreglar las referencias y crashear.
        decs = {eid: decompress(bytes(pkb[eoff:eoff + esize])) for eid, eoff, esize in ents}
        string_slots = build_string_slots(decs.values())
        print(f"{game}: {len(string_slots)} slots-string detectados (offset-fixup preciso)")
        # MODO DEBUG (DEBUG_IDS=1): antepone el [event_id] a cada linea de dialogo de los
        # eventos de gameplay (strip), incluso sin traduccion -> al hablar con un NPC se ve
        # su ID interno. Para identificar que evento es cada personaje (vacio/crash) entre
        # tests. NO afecta a la build limpia (sin la variable).
        dbg_on = bool(os.environ.get("DEBUG_IDS"))
        new_pkb = bytearray()
        new_index = []                                       # (eid, new_off, new_size)
        ev_ok = lines = grew = reverted = 0
        for eid, eoff, esize in ents:
            comp_orig = bytes(pkb[eoff:eoff + esize])
            # STRIP (quitar furigana, texto completo) en HISTORIA; INPLACE mismo-tamano en
            # sistema/intro (eid>=90000000) para no romper el crear-partida (LECCIONES ❌#1).
            # DEBUG: strip TODO para poner [id] en CADA evento (incluidos los protegidos).
            # Por eso la build DEBUG puede romper el CREAR-PARTIDA -> hay que CARGAR PARTIDA.
            # strip (texto completo) SOLO si es gameplay Y se puede crecer sin romper refs
            # (is_grow_safe). Si no -> blank-readings (mismo tamaño, español truncado, sin
            # vacio). Clasificacion automatica = adios al whack-a-mole de zonas vacias.
            strip = True if dbg_on else (is_strip_event(eid) and is_grow_safe(decs[eid], string_slots))
            # PRUEBA intro variable-length (GROW_INTRO=1): los eventos protegidos del rango
            # del crear-partida/club (92010100..92010509) CRECEN conservando furigana, para
            # quitar el truncado. Hay que probar que no rompe el crear-partida (❌#1/#9).
            grow_fg = bool(os.environ.get("GROW_INTRO")) and 92010100 <= eid <= 92010509
            # BISECCION (EID_LO/EID_HI): traducir SOLO gameplay en ese rango de eid; el resto
            # original. Para cazar por eliminacion el evento que produce el puntero corrupto.
            _inrange = (not os.environ.get("EID_LO")) or (int(os.environ["EID_LO"]) <= eid < int(os.environ.get("EID_HI", "99999999")))
            if eid in DONT_TOUCH:
                comp = comp_orig                          # HIPER-SENSIBLE -> 100% original SIEMPRE
                #   (byte-identico al ROM, fisicamente no puede crashear). Doc ❌#12. Independiente
                #   de SYS_ORIG: estos crashean con CUALQUIER cambio (strip Y blank Y inplace).
            elif os.environ.get("SYS_ORIG") and (eid >= 90000000 or not _inrange):
                comp = comp_orig                          # SYS_ORIG (build ultra-estable): sistema/
                #   intro 100% ORIGINAL. Sin SYS_ORIG el intro se traduce INPLACE (v25, truncado).
            elif eid in trans or gtrans or dbg_on:
                #   eid in trans = tiene traduccion por-evento; gtrans = hay fallback global (procesa
                #   TODOS los eventos para aplicar el global a lineas cuyo jp esta traducido en otro).
                dec = decs[eid]
                # MOTOR NUEVO (formato SSD correcto via SceneScriptData): el texto se
                # referencia por INDICE (estable) -> NO se reubica nada (sin offset-fixup),
                # los diálogos crecen libres (sin truncar), las lecturas se vacían (sin
                # japonés) y el bytecode queda INTACTO. Adios al vacío/crash/truncado.
                from ie123kit._legado import ssd_reinsert
                # sistema/menu/intro (eid>=90000000): conservar marcadores (❌#1 runtime);
                # gameplay (<90000000): texto completo (crece libre).
                # FULLTEXT=1: con el PARCHE del CRO (bounds-check ruby en 0xABFCC0) se puede
                # traducir TODO a texto completo, sistema incluido -> historia entera en español.
                # SAME_SIZE=1: TODO a mismo tamaño (sin crecer) -> no dispara las funciones de
                # code.bin que petan al crecer -> ESTABLE jugable de principio a fin (menos
                # español: truncado + furigana en japones). Sin flags = conservador (sistema jp).
                if os.environ.get("SAME_SIZE"):
                    sysflag = True
                else:
                    sysflag = (eid >= 90000000 or eid in DONT_STRIP) and not os.environ.get("FULLTEXT")
                # REGLA UNIFICADA del vaciado de lecturas (ligado a system, no global):
                #  - system=True (mismo tamaño): se CONSERVAN los marcadores -> la ruby SE invoca
                #    -> dejar la lectura ORIGINAL (vaciarla peta 0xABFCC0; y no hay cave fiable:
                #    la zona del CRO es de relocalizacion -> crash 0xAD9E1C).
                #  - system=False (gameplay STRIP/crecer): se QUITAN los marcadores -> la ruby NO
                #    se invoca -> se VACIAN las lecturas huerfanas (full-width, no las detecta
                #    _is_reading -> balance 0 marcadores : 0 lecturas, sin desync ❌bug#2).
                # NO_BLANK=1 fuerza conservar siempre (solo diagnostico).
                _blank = (not sysflag) and not os.environ.get("NO_BLANK")
                new_dec, n = ssd_reinsert.reencode_ssd(dec, trans.get(eid, {}),
                                                       system=sysflag,
                                                       blank_readings=_blank,
                                                       dbg_eid=(eid if dbg_on else None),
                                                       gtrans=gtrans, eid=eid)
                if n:
                    comp = compress(new_dec)
                    ev_ok += 1; lines += n
                    if len(comp) > esize:
                        grew += 1
                else:
                    comp = comp_orig
                    if eid in trans:
                        reverted += 1
            else:
                comp = comp_orig
            off = len(new_pkb)
            new_pkb += comp
            new_index.append((eid, off, len(comp)))
            while len(new_pkb) % 4:                            # alineacion 4 (como el original)
                new_pkb += b"\x00"
        # reconstruir pkh: cabecera 0x30 igual, tabla de 12B con offsets nuevos
        new_pkh = bytearray(pkh[:0x30])
        for eid, off, size in new_index:
            new_pkh += struct.pack("<III", eid, off, size)
        struct.pack_into("<I", new_pkh, 0x10, len(new_pkh))   # +0x10 = tamano del pkh
        open(os.path.join(outdir, f"{game}.pkb"), "wb").write(new_pkb)
        open(os.path.join(outdir, f"{game}.pkh"), "wb").write(new_pkh)
        print(f"{game}: {ev_ok} eventos, {lines} lineas ES | pkb {pkb_size} -> {len(new_pkb)} "
              f"(+{len(new_pkb)-pkb_size}); {grew} crecieron; {reverted} revertidos (validacion)")


if __name__ == "__main__":
    raise SystemExit(main())
