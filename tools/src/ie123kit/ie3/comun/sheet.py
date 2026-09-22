"""
Hoja de traduccion: convierte el CSV alineado en algo que un traductor pueda
usar de verdad.

El CSV alineado (output/aligned/*.csv) tiene 263 000 filas, y la mayoria NO
son texto del juego: son nombres de recurso, parametros de camara y mensajes
de depuracion que nunca salen en pantalla. Eso es lo que hacia que el
resultado pareciese "lleno de japones": no es que falte traduccion, es que
esas filas no se traducen nunca.

Este modulo separa las dos cosas y deja las columnas que pide el proyecto:

    event_id, japones, es_final, estado

------------------------------------------------------------------
Como se decide si una fila es texto de verdad
------------------------------------------------------------------

NO por la pinta del texto. Cada texto de un SSD cuelga de una instruccion, y
esa instruccion tiene un OPCODE. El opcode dice para que sirve el texto, asi
que la clasificacion es estructural, no heuristica.

La tabla de abajo se saco midiendo, opcode por opcode, cuantos de sus textos
aparecen REALMENTE traducidos en las versiones europeas oficiales (contando
solo emparejamientos fiables, nunca los heuristicos). La separacion no tiene
zona gris:

    opcode   textos jp   traducidos en la version europea
    0x4037         560   560   (100.0%)   nombres de sitio: "Hospital"
    0x201d         127   126   ( 99.2%)   rotulo de objetivo
    0x3019          51    50   ( 98.0%)   nombre tapado: ????  -> ???
    0x201c         272   265   ( 97.4%)   rotulo de objetivo
    0x201a          14    14   (100.0%)   rotulo de objetivo
    0x2019          22    20   ( 90.9%)   rotulo de objetivo
    ---------------------------------------------------------------
    0x3070      21 568   130   (  0.6%)   printf de depuracion (■...)
    0x402f       1 324     0   (  0.0%)   etiqueta fija "もくてき"
    0x301d      79 969     0   (  0.0%)   parametros "@x,y"
    0x3008 / 0x3014 / 0x3017 / 0x3011 / 0x4090 / ... : nombres de recurso

Los 130 "traducidos" de 0x3070 se comprobaron uno a uno: 129 son parejas
falsas del alineamiento heuristico (estado `probable`) y una es casualidad.
Por eso la promocion de abajo exige emparejamiento fiable.

------------------------------------------------------------------
Excepcion comprobada: texto real colgando de un opcode tecnico
------------------------------------------------------------------

Un opcode tecnico puede llevar texto de verdad de vez en cuando. El caso
real son las CONTRASENAS secretas de IE3, que cuelgan de 0x7011 (el mismo
opcode que carga los mapas) y que Level-5 si tradujo:

    よっつのぞくせい -> 4elementos
    カードであそぼう -> pokerdeases
    ハロウィンズだ！ -> vuelaescoba

Asi que una fila tecnica sube a texto real cuando hay PRUEBA de que se
tradujo: el japones es japones de verdad, el espanol oficial no lleva ni un
kana, y el emparejamiento es fiable (exact/structural, nunca probable).
Son 42 filas por juego y sin esta regla se perderian.
"""

import re

# --------------------------------------------------------------------------
# Clasificacion
# --------------------------------------------------------------------------

#: Opcodes de eve cuyo texto se ve en pantalla (ver tabla de la cabecera).
TEXT_OPCODES = {
    0x2019: "rotulo de objetivo",
    0x201A: "rotulo de objetivo",
    0x201C: "rotulo de objetivo",
    0x201D: "rotulo de objetivo",
    0x3019: "nombre tapado del interlocutor",
    0x4037: "nombre de sitio",
}

#: Marcas con las que los programadores de Level-5 empiezan sus mensajes de
#: depuracion. No salen en pantalla ni en japones ni en espanol.
DEBUG_MARKS = ("■", "★", "◆")

KANA = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")

#: Clases de fila.
CLASS_DIALOGUE = "dialogo"    # evet: lo que dicen los personajes
CLASS_TEXT = "texto"          # eve: rotulos y nombres que se ven
CLASS_TECHNICAL = "tecnico"   # todo lo demas: recursos, depuracion, parametros

#: Estados que se escriben en la columna `estado`.
OFFICIAL = "oficial"          # traduccion oficial europea, emparejada en firme
MEMORY = "memoria"            # la MISMA frase japonesa tiene traduccion oficial
                              # en otra fila, y aqui se ha reutilizado
REVIEW = "revisar"            # hay traduccion pero el emparejamiento es heuristico
UNTRANSLATED = "sin_traducir"  # la propia version europea lo dejo en japones
NO_MATCH = "sin_pareja"       # no hay contrapartida europea

#: Estados que llevan texto espanol utilizable.
TRANSLATED_STATES = (OFFICIAL, MEMORY, REVIEW)

RELIABLE = ("exact", "structural")


def is_japanese(text):
    return bool(KANA.search(text))


def is_debug(text):
    return text.startswith(DEBUG_MARKS)


def parse_opcode(value):
    """La columna `opcode` viene como '0x4037', o vacia en evet."""
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def classify(pack, opcode, jp_text, es_text, status):
    """
    Devuelve (clase, estado, es_final) para una fila del CSV alineado.

    `es_final` se deja VACIO cuando no hay traduccion oficial. Antes se
    arrastraba el japones a la columna espanola, y eso es justo lo que hacia
    que el resultado pareciese medio sin traducir sin decir por que.
    """
    reliable = status in RELIABLE
    translated = bool(es_text) and not is_japanese(es_text) and es_text != jp_text

    # --- clase -------------------------------------------------------
    if pack != "eve":
        cls = CLASS_DIALOGUE
    elif opcode in TEXT_OPCODES and not is_debug(jp_text):
        cls = CLASS_TEXT
    elif (is_japanese(jp_text) and not is_debug(jp_text)
            and translated and reliable):
        # Prueba de que se traduce: las contrasenas secretas y poco mas.
        cls = CLASS_TEXT
    else:
        cls = CLASS_TECHNICAL

    # --- estado ------------------------------------------------------
    if status == "unmatched" or not es_text:
        estado = NO_MATCH
    elif is_japanese(es_text):
        # La version europea trae el texto, pero sin traducir.
        estado = UNTRANSLATED
    elif es_text == jp_text:
        # Identico y sin kana: es un identificador, no una traduccion.
        estado = NO_MATCH if is_japanese(jp_text) else OFFICIAL
    else:
        estado = OFFICIAL if reliable else REVIEW

    es_final = es_text if estado in (OFFICIAL, REVIEW) else ""

    return cls, estado, es_final


# --------------------------------------------------------------------------
# Memoria de traduccion
# --------------------------------------------------------------------------

def build_memory(entries):
    """
    {japones: espanol} con las frases cuya traduccion oficial es UNANIME.

    La misma frase japonesa sale muchas veces repartida por los eventos. Basta
    con que UNA de esas apariciones caiga en un emparejamiento fiable para
    saber como la tradujo Level-5, y entonces se puede rellenar el resto: las
    que quedaron sin pareja, las que la version europea dejo en japones y las
    que solo se emparejaron por heuristica.

    Solo se acepta cuando todas las apariciones oficiales coinciden. Si una
    misma frase japonesa tiene dos traducciones oficiales distintas (pasa con
    las que llevan %s), depende del contexto y no se puede reutilizar.
    """
    candidates = {}
    for jp_text, es_text in entries:
        seen = candidates.setdefault(jp_text, set())
        if len(seen) < 2:
            seen.add(es_text)

    return {jp: next(iter(v)) for jp, v in candidates.items() if len(v) == 1}


# --------------------------------------------------------------------------
# Construccion de la hoja
# --------------------------------------------------------------------------

#: Columnas de la hoja de traduccion. Las cuatro primeras son las que pide el
#: proyecto; `pack` y `string_id` van detras porque sin ellas no se puede
#: volver a meter la traduccion en la ROM (un mismo event_id tiene muchas
#: cadenas).
SHEET_HEADER = ["event_id", "japones", "es_final", "estado", "pack", "string_id"]

GLOSSARY_HEADER = ["japones", "es_final", "estado", "veces"]

TECHNICAL_HEADER = ["event_id", "japones", "es_oficial", "opcode", "motivo",
                    "pack", "string_id"]


def _reason(opcode, jp_text):
    if is_debug(jp_text):
        return "mensaje de depuracion"
    if opcode == 0x301D:
        return "parametro de posicion"
    if opcode == 0x402F:
        return "etiqueta fija del motor"
    if opcode is None:
        return "sin opcode"
    return "nombre de recurso"


def build(rows, version):
    """
    rows: dicts del CSV alineado (una version).

    Devuelve (filas_hoja, filas_tecnicas, filas_glosario, estadisticas).

    Dos pasadas: la primera clasifica cada fila por su cuenta, la segunda
    reutiliza las traducciones oficiales que ya se conocen para rellenar las
    filas que se quedaron sin espanol.
    """
    sheet = []
    technical = []
    stats = {
        "version": version,
        "filas_alineadas": len(rows),
        "texto_real": 0,
        "tecnico": 0,
        "descartadas_sin_japones": 0,
        "por_clase": {},
        "por_estado": {},
        "dialogo": {},
        "texto": {},
    }

    # --- pasada 1: clasificar -----------------------------------------
    draft = []
    for r in rows:
        jp = r["jp_text"]

        # La hoja se ordena por el japones: si no hay original japones no hay
        # nada que traducir (son lineas que la version europea anadio).
        if not jp:
            stats["descartadas_sin_japones"] += 1
            continue

        opcode = parse_opcode(r.get("opcode", ""))
        cls, estado, es_final = classify(
            r["pack"], opcode, jp, r["es_text"], r["status"]
        )

        stats["por_clase"][cls] = stats["por_clase"].get(cls, 0) + 1

        if cls == CLASS_TECHNICAL:
            stats["tecnico"] += 1
            technical.append([
                r["event_id"], jp, r["es_text"], r.get("opcode", ""),
                _reason(opcode, jp), r["pack"], r["string_id"],
            ])
            continue

        draft.append((r["event_id"], jp, es_final, estado, r["pack"],
                      r["string_id"], cls))

    # --- pasada 2: memoria de traduccion ------------------------------
    memory = build_memory(
        (jp, es) for _e, jp, es, estado, _p, _s, _c in draft
        if estado == OFFICIAL
    )
    stats["memoria_frases"] = len(memory)

    recovered = 0
    confirmed = 0

    for event_id, jp, es_final, estado, pack, string_id, cls in draft:
        known = memory.get(jp)

        if estado == REVIEW and known is not None and es_final == known:
            # El emparejamiento era heuristico, pero coincide con lo que dice
            # un emparejamiento fiable de la misma frase en otro sitio.
            estado = OFFICIAL
            confirmed += 1
        elif estado in (UNTRANSLATED, NO_MATCH) and known:
            es_final, estado = known, MEMORY
            recovered += 1

        stats["texto_real"] += 1
        stats["por_estado"][estado] = stats["por_estado"].get(estado, 0) + 1
        bucket = stats["dialogo"] if cls == CLASS_DIALOGUE else stats["texto"]
        bucket[estado] = bucket.get(estado, 0) + 1

        sheet.append([event_id, jp, es_final, estado, pack, string_id])

    stats["memoria_rellenadas"] = recovered
    stats["heuristicas_confirmadas"] = confirmed

    # --- glosario ------------------------------------------------------
    glossary = {}
    for event_id, jp, es_final, estado, pack, string_id in sheet:
        entry = glossary.get(jp)
        if entry is None:
            glossary[jp] = [jp, es_final, estado, 1]
        else:
            entry[3] += 1
            if not entry[1] and es_final:
                entry[1], entry[2] = es_final, estado

    glossary_rows = sorted(glossary.values(), key=lambda e: (-e[3], e[0]))

    stats["glosario_unicos"] = len(glossary_rows)
    stats["glosario_con_oficial"] = sum(1 for e in glossary_rows if e[1])

    return sheet, technical, glossary_rows, stats
