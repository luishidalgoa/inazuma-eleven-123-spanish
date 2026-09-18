"""IE2 v17 · modelo ampliado del motor del diálogo (ina_main2.cro de v15/v16) y reparto en páginas.

Motor (evidencia en ../../v15/ancho_dialogo/informe.json y en este informe.json):
1. reajuste 0x48398: límite [ventana+0x131e] + 0x20 = 0x1A0 + 32 = 448, paso 12 -> 37 caracteres por
   línea; `\\n` en la 3.ª línea -> salto de página (0x0C);
2. dibujo 0x121a78 con el ancho global 0x1C0 (0x4d6a0): corte si x + 12 > 448 -> también 37;
3. copia de página 0x4d5c4-0x4d638: la página (bytes hasta 0x0C, 0x0A cuenta 1 y cada carácter de
   ancho completo 2) va a un búfer de pila de 132 B (sp+0x40..0xc3); 0x122458 pisa sp+0xc4..0xc7 y
   0x4d648 escribe un 0 en el índice longitud+2. Tope seguro: **131 B por página** (el terminador
   queda dentro del búfer; con más se corta o sale «?», y más allá se pisa la pila de la función).
Página en bytes = 2·caracteres + (líneas − 1); %s cuenta 12 caracteres (24 B), %d 5; %NF no ocupa.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'work/ie2/tormenta_de_fuego/capas/v02/dialogo'))
import comun_ie2 as M  # noqa: E402

ANCHO = 0x1A0          # reajuste (0x66a24 / 0x4cabc)
ANCHO_DIBUJO = 0x1C0   # dibujo (0x4d6a0)
MAX_CAR = 37
LINEAS = 3
PAGINA_MAX = 131
SALTO, PAGINA = M.SALTO, M.PAGINA
NF = re.compile(rb'%\d*F')


def simulado(cuerpo: bytes) -> bytes:
    """Cuerpo tal como llega al reajuste: %s/%d a su ancho reservado, %NF fuera."""
    return M.motor_simulado(NF.sub(b'', cuerpo))


def motor(cuerpo: bytes) -> bytes:
    return M.K82.motor(simulado(cuerpo), ancho=ANCHO)


def caracteres(linea: bytes) -> int:
    n, i = 0, 0
    while i < len(linea):
        i += 2 if linea[i] & 0x80 else 1
        n += 1
    return n


def dibujo(linea: bytes) -> list[bytes]:
    """Corte del dibujo 0x12208c: x + 12 > 0x1C0 abre línea."""
    out, x, cur, i = [], 0, bytearray(), 0
    while i < len(linea):
        n = 2 if linea[i] & 0x80 else 1
        if x + 12 > ANCHO_DIBUJO:
            out.append(bytes(cur))
            cur, x = bytearray(), 0
        cur += linea[i:i + n]
        x += 12
        i += n
    out.append(bytes(cur))
    return out


def paginas(cuerpo: bytes) -> list[bytes]:
    return motor(cuerpo).split(b'\x0c')


def problemas(cuerpo: bytes) -> list[str]:
    """Comprobación del modelo completo sobre un registro."""
    p = []
    for k, pg in enumerate(paginas(cuerpo)):
        if len(pg) > PAGINA_MAX:
            p.append(f'página {k}: {len(pg)} B > {PAGINA_MAX}')
        lineas = pg.split(b'\n')
        if len(lineas) > LINEAS:
            p.append(f'página {k}: {len(lineas)} líneas')
        for ln in lineas:
            if caracteres(ln) > MAX_CAR:
                p.append(f'página {k}: línea de {caracteres(ln)} caracteres')
            if len(dibujo(ln)) != 1:
                p.append(f'página {k}: el dibujo parte la línea')
    return p


def reajusta(cuerpo: bytes) -> bool:
    """True si el motor inserta algún salto (convertir un \\n de 3.ª línea en 0x0C no cuenta)."""
    pre = M.K82.preprocesar(simulado(cuerpo))
    return motor(cuerpo).replace(b'\x0c', b'\n') != pre.replace(b'\x0c', b'\n')


# ------------------------------------------------------------------ medida de texto español

def bytes_linea(linea: str) -> int:
    return len(simulado(M.transportar(linea)))


def bytes_pagina(lineas: list[str]) -> int:
    return sum(bytes_linea(x) for x in lineas) + len(lineas) - 1


def cabe_linea(linea: str) -> bool:
    return M.largo(linea) <= MAX_CAR


def envolver(palabras: list[str]):
    """Líneas voraces de <= 37 caracteres; None si una palabra no cabe sola."""
    filas, actual = [], ''
    for w in palabras:
        if not cabe_linea(w):
            return None
        cand = f'{actual} {w}' if actual else w
        if actual and not cabe_linea(cand):
            filas.append(actual)
            actual = w
        else:
            actual = cand
    if actual:
        filas.append(actual)
    return filas


def pagina_valida(filas) -> bool:
    return filas is not None and 0 < len(filas) <= LINEAS and bytes_pagina(filas) <= PAGINA_MAX


def repartir(texto: str) -> str:
    """Texto oficial íntegro -> páginas de <= 3 × 37 y <= 131 B, sin cortar palabras.

    Programación dinámica sobre los cortes de página entre palabras. Coste: cada página 100; cortar
    tras fin de frase 0, tras coma o punto y coma 60, en otro sitio 150; página de menos de 12
    caracteres 200 (evita «río...» sueltos). Los saltos de página del texto se ignoran (se reparte de nuevo)."""
    ws = ' '.join(texto.replace(PAGINA, ' ').replace(SALTO, ' ').split()).split()
    n = len(ws)
    if not n:
        return ''
    INF = float('inf')
    mejor = [INF] * (n + 1)
    previo = [0] * (n + 1)
    mejor[0] = 0

    def coste_corte(j):
        if j == n:
            return 0
        w = ws[j - 1]
        if re.search(r'[.!?…]$', w):
            return 0
        if re.search(r'[,;:]$', w):
            return 60
        return 150

    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            if mejor[i] == INF:
                continue
            filas = envolver(ws[i:j])
            if filas is None or len(filas) > LINEAS:
                break
            if bytes_pagina(filas) > PAGINA_MAX:
                break
            c = mejor[i] + 100 + coste_corte(j)
            if sum(M.largo(x) for x in filas) < 12 and n > 1 and (i > 0 or j < n):
                c += 200
            if c < mejor[j]:
                mejor[j], previo[j] = c, i
    if mejor[n] == INF:
        raise ValueError('no cabe: ' + ' '.join(ws))
    cortes, j = [], n
    while j:
        cortes.append((previo[j], j))
        j = previo[j]
    pags = [envolver(ws[i:j]) for i, j in reversed(cortes)]
    return PAGINA.join(SALTO.join(p) for p in pags)


# ------------------------------------------------------------------ tope en registros existentes

TOK = re.compile(r'(\\n|\\f)')


def partir_paginas(texto: str):
    """Registro existente (disposición actual intacta) -> mismo texto con `\\n` cambiados por `\\f`
    donde una página del motor pasaría de 131 B. Tamaño idéntico (ambos 2 B). Devuelve (texto, cortes)."""
    partes = TOK.split(texto)          # [trozo, sep, trozo, sep, ...]
    trozos, seps = partes[0::2], partes[1::2]

    def b(t):
        return len(simulado(t.encode('cp932')))

    cortes = 0
    # recorre línea a línea como el motor: página = hasta 3 líneas o hasta \f
    inicio, n_lineas, tam = 0, 1, b(trozos[0])
    k = 0
    while k < len(seps):
        sig = b(trozos[k + 1])
        if seps[k] == '\\f':
            inicio, n_lineas, tam = k + 1, 1, sig
        elif n_lineas >= LINEAS:       # el motor convierte este \n en página
            inicio, n_lineas, tam = k + 1, 1, sig
        elif tam + 1 + sig > PAGINA_MAX:
            # cortar: preferir el último \n de la página tras fin de frase; si no, este mismo
            j = k
            for c in range(k, inicio - 1, -1):
                if seps[c] == '\\n' and re.search(r'[.!?…](\s|%)*$', M.K.a_espanol(trozos[c].encode('cp932'))):
                    j = c
                    break
            seps[j] = '\\f'
            cortes += 1
            k = j
            continue
        else:
            n_lineas += 1
            tam += 1 + sig
        k += 1
    out = [trozos[0]]
    for s, t in zip(seps, trozos[1:]):
        out += [s, t]
    return ''.join(out), cortes
