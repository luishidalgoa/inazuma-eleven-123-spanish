"""Maquetación del diálogo de IE3: MAX_CAR caracteres por línea, 3 líneas por caja.

El modelo del motor sale del desensamblado del CRO
(``capas/ie1/v82/saltos_dialogo/comun82.py``, rama `estado-ie2-cajas`):

    limite = [ventana+0x131A] + 0x20
    lineas por pagina [ventana+0x131C] = 3
    FontGetCharWidth(FONT12) = 12 FIJO, no depende del caracter
    cabe un caracter si x + 12 < limite

Lo importante es que **el avance es fijo**: una `i` y una `M` ocupan lo mismo.
Medir el ancho real de cada letra (que es lo que hacia el `reflow` de IE1 a
208 px) da de mas y el motor acaba partiendo la palabra: en la primera prueba en
emulador, «¡Bravo, Paolo! ¡El fútbol» (25 caracteres) salio como
«¡Bravo, Paolo! ¡El fút» + «bol», y la ultima linea se perdia.

Con la ventana de fabrica (0xF0) son 22 caracteres; con la ensanchada de
`ancho_ventana` son 51. El ancho no se repite aqui: se lee de alli, que
es donde se parchea el CRO.

El motor **corta por caracter, no por palabra**, asi que si no se le dan los
saltos hechos parte por donde caiga.

Cuando el texto no cabe en 3 lineas se abre otra caja con ``\f``, que es lo que
manda la Norma 3 de CLAUDE.md: el dialogo no se condensa ni se recorta, se
reparte en mas cajas.
"""

from __future__ import annotations

from ie123kit.ie3.comun.ancho_ventana import ANCHO as ANCHO_VENTANA

EXTRA = 0x20
AVANCE = 12
LIMITE = ANCHO_VENTANA + EXTRA

#: Caracteres por línea. Con la ventana de fábrica (0xF0) son 22, que es lo que
#: se midió en el emulador. Con la ventana ensanchada (0x1A0) son 37.
#: El valor sale de `ancho_ventana`, que es donde se parchea el CRO: si se
#: cambia allí, la maquetación lo sigue sola.
MAX_CAR = max(n for n in range(1, 80) if (n - 1) * AVANCE + AVANCE < LIMITE)

#: 3 líneas por caja.
LINEAS = 3

#: Tope de TINTA por línea, en píxeles.
#:
#: El motor REAJUSTA contando 12 px fijos por carácter, pero DIBUJA con el avance
#: real de la fuente, que es proporcional. Son dos límites distintos y hacen falta
#: los dos: el de caracteres decide dónde parte el motor, y éste decide si la
#: línea se sale de la caja.
#:
#: Geometría medida en `capas/ie1/v86/ancho_ventana/informe.md`: el panel llega a
#: x≈391, el icono de avance ocupa 370-390 en la 3.ª línea, y la caja admite unos
#: 354 px de tinta.
MAX_TINTA = 354


def tinta(texto):
    """Anchura real en píxeles del texto con la fuente del diálogo."""
    from ie123kit.ie3.comun.tipografia import avance_font12
    return sum(avance_font12(c) for c in texto)

SALTO = "\\n"
PAGINA = "\\f"


def _partir_palabra(palabra, ancho):
    """Una palabra más larga que la línea se parte a lo bruto, como haría el motor."""
    return [palabra[i:i + ancho] for i in range(0, len(palabra), ancho)]


def lineas_de(texto, ancho=MAX_CAR, max_tinta=MAX_TINTA, *, medir=None):
    """
    Reparte `texto` en líneas sin cortar palabras.

    Una línea se cierra cuando se pasa de `ancho` caracteres (lo que hace que el
    motor meta un salto suyo) O de `max_tinta` píxeles (lo que la sacaría de la
    caja al dibujarla).
    """
    medida = tinta if medir is None else medir

    def cabe(linea):
        return len(linea) <= ancho and medida(linea) <= max_tinta

    lineas = []
    for trozo in texto.split(SALTO):
        actual = ""
        for palabra in trozo.split(" "):
            if not palabra:
                continue
            if len(palabra) > ancho:
                if actual:
                    lineas.append(actual)
                    actual = ""
                cachos = _partir_palabra(palabra, ancho)
                lineas.extend(cachos[:-1])
                actual = cachos[-1]
                continue
            if not actual:
                actual = palabra
            elif cabe(actual + " " + palabra):
                actual += " " + palabra
            else:
                lineas.append(actual)
                actual = palabra
        if actual:
            lineas.append(actual)
    return lineas


def maquetar_una_caja(texto, ancho=MAX_CAR, lineas=LINEAS):
    """
    Maqueta el texto para UNA sola caja, o devuelve None si no cabe.

    El motor de IE3 dibuja una caja por dialogo y no espera mas: de las 79 715
    lineas japonesas del juego, solo 22 llevan salto de pagina, y ninguna pasa
    de 3 lineas. Cada ``\f`` que se anade es texto que el script nunca pide
    mostrar, asi que **se pierde**. Se comprobo dos veces en emulador: los
    dialogos de una caja salian bien y los de dos perdian el principio.

    Por eso aqui no se pagina. Si el espanol no cabe en las 3 lineas, se
    devuelve None y la linea se queda en japones: mejor sin traducir que
    mostrada a medias (Norma 3 de CLAUDE.md, que prohibe condensarla).
    """
    if PAGINA in texto:
        return None                       # ya venia paginado: no se toca
    sueltas = lineas_de(texto, ancho)
    if len(sueltas) > lineas:
        return None
    if any(len(l) > ancho or tinta(l) > MAX_TINTA for l in sueltas):
        return None                       # una palabra suelta que no cabe
    return SALTO.join(sueltas)


def maquetar(texto, ancho=MAX_CAR, lineas=LINEAS):
    """
    Devuelve el texto con los saltos y los cambios de caja ya puestos.

    Respeta los ``\\f`` que ya trajera el original: cada página se maqueta por
    su cuenta y puede generar más páginas si no cabe.
    """
    paginas = []
    for pagina in texto.split(PAGINA):
        sueltas = lineas_de(pagina, ancho)
        for i in range(0, len(sueltas), lineas) if sueltas else []:
            paginas.append(SALTO.join(sueltas[i:i + lineas]))
        if not sueltas:
            paginas.append("")
    return PAGINA.join(paginas)


def motor(texto, ancho=ANCHO_VENTANA, lineas=LINEAS, avance=AVANCE):
    """
    Simula el ajuste automático del motor (0x424f4) sobre un texto ya maquetado.

    Sirve para comprobar que la maquetación no le deja trabajo: si el motor no
    tiene que insertar ningún salto propio, es que todas las líneas caben.
    Devuelve (lineas_dibujadas, saltos_que_mete_el_motor).
    """
    limite = ancho + EXTRA
    x = ln = insertados = 0
    dibujadas = []
    actual = ""
    i = 0
    while i < len(texto):
        if texto.startswith(SALTO, i):
            dibujadas.append(actual)
            actual = ""
            ln += 1
            x = 0
            if ln >= lineas:
                ln = 0
            i += 2
            continue
        if texto.startswith(PAGINA, i):
            dibujadas.append(actual)
            actual = ""
            x = ln = 0
            i += 2
            continue
        if x + avance >= limite:
            dibujadas.append(actual)
            actual = ""
            insertados += 1
            ln += 1
            if ln >= lineas:
                ln = 0
            x = 0
        actual += texto[i]
        x += avance
        i += 1
    if actual:
        dibujadas.append(actual)
    return dibujadas, insertados
