"""
Alineamiento japones <-> espanol.

Prioridades (de mas fiable a menos), tal y como pide el proyecto:

  1. IDENTIDAD DEL EVENTO
     El .pkh guarda un identificador de evento que es el MISMO en la version
     japonesa y en la europea. Nunca emparejamos por posicion en el pack.

  2. IDENTIFICADORES INTERNOS DE TEXTO  (solo eve / SSD)
     Cada texto de un SSD cuelga de un par (instruccion, argumento). Ese par
     no depende de la longitud del texto, asi que una traduccion mas larga o
     mas corta no lo mueve. Es un emparejamiento exacto, no una heuristica.

  3. POSICION DENTRO DE LA ESTRUCTURA  (evet)
     evet no tiene claves internas. Si el evento tiene el mismo numero de
     dialogos en los dos idiomas (quitando las lecturas furigana japonesas),
     el orden es fiable y emparejamos por indice.

  4. ALINEAMIENTO POR SECUENCIA        (evet descuadrado)
     Si los numeros no cuadran usamos programacion dinamica con una medida
     de parecido estructural (codigos de control, cifras, signos, longitud).
     Esto SI es una heuristica y se marca como tal.

Estados que se escriben en el CSV:

    exact        misma clave interna y misma estructura de script
    structural   misma clave interna o misma posicion, estructura distinta
    probable     emparejado por alineamiento de secuencia
    unmatched    sin pareja
"""

import math
import re

# Hueco que el motor rellena en tiempo de ejecucion: %s, %d, %02d...
# Sobrevive intacto a la traduccion, asi que es la pista mas fuerte que hay.
PLACEHOLDER = re.compile(r"%\d*[a-z]")

# Marca de furigana. Es SOLO japonesa: en 32 032 parejas fiables de evet
# aparece 51 843 veces en japones y 285 en espanol. Compararlas hundia la
# puntuacion de casi todas las parejas correctas, asi que se quitan antes
# de medir nada.
RUBY = re.compile(r"%\dF")

# El texto se guarda en el CSV con el salto de linea como barra invertida + n.
NEWLINE = chr(92) + "n"

STATUS_EXACT = "exact"
STATUS_STRUCTURAL = "structural"
STATUS_PROBABLE = "probable"
STATUS_UNMATCHED = "unmatched"

# Mediana y dispersion de len(espanol)/len(japones) medidas sobre las 32 032
# parejas fiables de evet: p10 1.40, mediana 2.40, p90 3.88. El espanol ocupa
# del orden del doble que el japones porque el japones usa kanji.
#
# La dispersion es ancha a proposito. El dialogo se alarga al traducir, pero
# los rotulos de eve se ACORTAN, porque tienen el ancho contado:
# "稲妻総合病院 中庭" (9) -> "Hospital" (8). Con una campana estrecha esos
# rotulos, que son texto de verdad, salian peor puntuados que la basura.
RATIO_CENTER = 2.4
RATIO_SPREAD = 0.9


def _features(text, strip_ruby):
    body = RUBY.sub("", text) if strip_ruby else text
    return (
        tuple(sorted(PLACEHOLDER.findall(body))),
        body.count(NEWLINE),
        "?" in body or "\uff1f" in body,
        "!" in body or "\uff01" in body or "\u00a1" in body,
        len(body),
    )


def similarity(a, b):
    """
    0..1. Mide ESTRUCTURA, no significado: son idiomas distintos.

    Los pesos salen de medir cada rasgo sobre 32 032 parejas fiables de evet
    frente a las mismas parejas barajadas al azar:

        rasgo                     parejas buenas   al azar
        huecos %s/%d (si los hay)        100.0%       2.2%
        saltos de linea (exactos)         62.4%      38.0%
        saltos de linea (+-1)             98.3%      84.8%
        signos de exclamacion             77.5%      54.5%
        signos de interrogacion           86.5%      73.6%
        cifras                            98.6%      98.2%  <- inutil, fuera

    Por eso los huecos mandan y las cifras ya no se miran: coincidian
    practicamente siempre, tambien en las parejas falsas.
    """
    if a and a == b:
        # Nombres de recurso y cadenas de depuracion no se traducen.
        return 1.0

    fa = _features(a, strip_ruby=True)
    fb = _features(b, strip_ruby=False)

    # --- huecos de runtime: decisivo ---------------------------------
    if fa[0] or fb[0]:
        if fa[0] != fb[0]:
            # Un %s no desaparece al traducir. Si no cuadran, no son pareja.
            return 0.0
        score = 0.45
    else:
        score = 0.0

    # --- saltos de linea ---------------------------------------------
    diff = abs(fa[1] - fb[1])
    score += 0.15 if diff == 0 else (0.07 if diff == 1 else 0.0)

    # --- signos ------------------------------------------------------
    score += 0.10 if fa[3] == fb[3] else 0.0
    score += 0.07 if fa[2] == fb[2] else 0.0

    # --- proporcion de longitud --------------------------------------
    ratio = fb[4] / max(fa[4], 1)
    z = (math.log(max(ratio, 1e-6)) - math.log(RATIO_CENTER)) / RATIO_SPREAD
    score += 0.23 * math.exp(-z * z)

    return score


def align_sequences(left, right, key=lambda x: x, gap=-0.35,
                    score=None):
    """
    Needleman-Wunsch sobre dos listas. Devuelve [(i, j)] con None en los huecos.
    """
    if score is None:
        score = similarity

    n, m = len(left), len(right)

    if n == 0:
        return [(None, j) for j in range(m)]
    if m == 0:
        return [(i, None) for i in range(n)]

    scores = [[0.0] * (m + 1) for _ in range(n + 1)]
    moves = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        scores[i][0] = scores[i - 1][0] + gap
        moves[i][0] = 1
    for j in range(1, m + 1):
        scores[0][j] = scores[0][j - 1] + gap
        moves[0][j] = 2

    for i in range(1, n + 1):
        ki = key(left[i - 1])
        row, prev = scores[i], scores[i - 1]
        mrow = moves[i]
        for j in range(1, m + 1):
            diag = prev[j - 1] + score(ki, key(right[j - 1]))
            up = prev[j] + gap
            side = row[j - 1] + gap

            best = diag
            move = 0
            if up > best:
                best, move = up, 1
            if side > best:
                best, move = side, 2

            row[j] = best
            mrow[j] = move

    pairs = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and moves[i][j] == 0:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or moves[i][j] == 1):
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1

    pairs.reverse()
    return pairs


MAX_DP = 1200

# eve: umbral de la pasada C. Como esa pasada ya solo compara textos del
# MISMO opcode, el umbral no tiene que hacer de filtro grueso; basta con que
# corte las parejas que no se parecen en nada. Sin huecos %s/%d la
# puntuacion maxima es 0.55, asi que 0.35 es la mitad de la escala util.
MIN_PROBABLE = 0.35

# evet: aqui NO se filtra por puntuacion. El alineamiento de secuencia se
# apoya en el contexto (las frases de alrededor), asi que una pareja suelta
# con poca puntuacion puede ser perfectamente correcta; medido sobre 32 032
# parejas fiables, cortar en 0.55 se cargaba el 76% de las buenas. Solo se
# rechaza lo IMPOSIBLE: que los huecos %s/%d no cuadren, que da 0.0 exacto.
IMPOSSIBLE = 0.0


def align_script_strings(jp_strings, es_strings, same_structure):
    """
    eve / SSD, en tres pasadas de fiabilidad decreciente:

      A. clave interna (instruccion, argumento) -> exact / structural
      B. texto identico dentro del evento       -> structural
         (los nombres de recurso y las cadenas de depuracion no se traducen;
          la version europea renumera algunas instrucciones, asi que la clave
          se mueve aunque el texto sea el mismo)
      C. alineamiento de secuencia sobre lo que sobra -> probable

    Devuelve [(jp_string|None, es_string|None, estado)] en orden japones.
    """
    es_by_key = {}
    for s in es_strings:
        es_by_key.setdefault(s.key, []).append(s)

    matched = {}          # id(jp) -> (es, estado)
    used = set()

    # --- A: clave interna ---------------------------------------------
    for js in jp_strings:
        for candidate in es_by_key.get(js.key, ()):
            if id(candidate) not in used:
                used.add(id(candidate))
                matched[id(js)] = (
                    candidate,
                    STATUS_EXACT if same_structure else STATUS_STRUCTURAL,
                )
                break

    jp_left = [s for s in jp_strings if id(s) not in matched]
    es_left = [s for s in es_strings if id(s) not in used]

    # --- B: texto identico --------------------------------------------
    by_text = {}
    for s in es_left:
        if s.text:
            by_text.setdefault(s.text, []).append(s)

    for js in jp_left:
        if not js.text:
            continue
        bucket = by_text.get(js.text)
        if not bucket:
            continue
        for candidate in bucket:
            if id(candidate) not in used:
                used.add(id(candidate))
                matched[id(js)] = (candidate, STATUS_STRUCTURAL)
                break

    jp_left = [s for s in jp_left if id(s) not in matched]
    es_left = [s for s in es_left if id(s) not in used]

    # --- C: alineamiento de secuencia, OPCODE A OPCODE -----------------
    # Cada texto de un SSD cuelga de una instruccion, y esa instruccion tiene
    # un opcode que dice para que sirve el texto: rotulo de sitio, nombre de
    # recurso, printf de depuracion... El opcode NO cambia al traducir, asi
    # que emparejar solo dentro del mismo opcode es una restriccion
    # estructural, no una heuristica, y evita el error tipico de esta pasada:
    # casar un mensaje de depuracion con otro que no tiene nada que ver solo
    # porque los dos empiezan por el mismo simbolo.
    jp_by_op = {}
    for s in jp_left:
        if s.text:
            jp_by_op.setdefault(s.opcode, []).append(s)

    es_by_op = {}
    for s in es_left:
        if s.text:
            es_by_op.setdefault(s.opcode, []).append(s)

    for opcode, jp_dp in jp_by_op.items():
        es_dp = es_by_op.get(opcode)
        if not es_dp:
            continue
        if len(jp_dp) > MAX_DP or len(es_dp) > MAX_DP:
            continue

        for i, j in align_sequences(jp_dp, es_dp, key=lambda s: s.text):
            if i is None or j is None:
                continue
            js, es = jp_dp[i], es_dp[j]
            if similarity(js.text, es.text) < MIN_PROBABLE:
                continue
            used.add(id(es))
            matched[id(js)] = (es, STATUS_PROBABLE)

    # --- salida ---------------------------------------------------------
    rows = []
    for js in jp_strings:
        pair = matched.get(id(js))
        if pair is None:
            rows.append((js, None, STATUS_UNMATCHED))
        else:
            rows.append((js, pair[0], pair[1]))

    for es in es_strings:
        if id(es) not in used:
            rows.append((None, es, STATUS_UNMATCHED))

    return rows


def align_flat_strings(jp_mains, es_mains, memory=None):
    """
    evet: por indice si los conteos coinciden, si no por alineamiento.

    jp_mains / es_mains son listas de ScriptString (ya sin furigana).

    `memory` es {japones: espanol} sacado de los eventos que SI cuadraban.
    La misma frase japonesa se repite por todo el juego, asi que cuando un
    evento descuadra casi siempre hay frases suyas que ya se resolvieron en
    otro evento bien alineado. Esas parejas valen como ancla: fijan el resto
    del alineamiento en su sitio en vez de dejarlo a merced de una medida
    estructural que, sin huecos %s/%d, distingue poco.
    """
    if len(jp_mains) == len(es_mains):
        return [
            (a, b, STATUS_STRUCTURAL)
            for a, b in zip(jp_mains, es_mains)
        ]

    if memory:
        def score(a, b):
            known = memory.get(a)
            if known is not None and known == b:
                return 1.0
            return similarity(a, b)
    else:
        score = similarity

    rows = []
    for i, j in align_sequences(
        jp_mains, es_mains, key=lambda s: s.text, score=score
    ):
        jp = jp_mains[i] if i is not None else None
        es = es_mains[j] if j is not None else None

        # Solo se descarta lo imposible: un %s no desaparece al traducir,
        # asi que si los huecos no cuadran no son pareja por mucho que el
        # alineamiento las haya puesto juntas.
        if jp and es and score(jp.text, es.text) <= IMPOSSIBLE:
            rows.append((jp, None, STATUS_UNMATCHED))
            rows.append((None, es, STATUS_UNMATCHED))
            continue

        status = STATUS_PROBABLE if (jp and es) else STATUS_UNMATCHED
        rows.append((jp, es, status))

    return rows


def flat_memory(pairs):
    """
    {japones: espanol} con las frases cuya traduccion es UNANIME.

    Se construye solo con los eventos en los que el numero de dialogos
    coincide en los dos idiomas, que es un emparejamiento por posicion sin
    nada de heuristica. Si una frase japonesa sale con dos traducciones
    distintas se descarta: depende del contexto y no sirve de ancla.
    """
    seen = {}
    for jp_text, es_text in pairs:
        if not jp_text or not es_text:
            continue
        bucket = seen.setdefault(jp_text, set())
        if len(bucket) < 2:
            bucket.add(es_text)

    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}
