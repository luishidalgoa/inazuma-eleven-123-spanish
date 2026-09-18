"""v82 · saltos de diálogo: modelo REAL del ajuste automático del motor (ina_main1.cro) y ajuste nuevo.

Evidencia (diagnostico/, desensamblado de work/shared/candidatas/probe_ie1_v81/romfs/cro/ina_main1.cro):
- 0x55504: despachador de instrucciones; tabla en 0x55554 indexada por opcode-0x3002.
  0x301c (abrir ventana) -> 0x56d24; 0x301d (diálogo) -> 0x56eb0.
- 0x56eb0 (0x301d): 0x36c54 expande %s/%d/%C/%F y convierte `\\n`->0x0A y `\\f`->0x0C (1 byte; la
  barra se descarta, 0x36f4c..0x36f68) en un búfer de 0x200 B; luego llama a 0x424f4.
- 0x424f4 (ajuste automático de la ventana), por carácter:
      sl = [ventana+0x1316] + 0x20 ; sb = [ventana+0x1318]
      0x0A: línea+=1, x=0; si línea >= sb el 0x0A se convierte en 0x0C y línea=0
      0x0C: x=0, línea=0
      otro: w = 0xd004c(car) = FontGetCharWidth(tipo, car)   (code.bin 0x164660: tabla fija
            [12, 8, 12, 4] por tipo de fuente, NO depende del carácter; FONT12 -> 12)
            si x + w >= sl: línea+=1; se INSERTA 0x0A (o 0x0C y línea=0 si línea >= sb); x=0
            x += w ; se copia el carácter (el que desborda abre la línea siguiente, aunque sea espacio)
  Corte por carácter, no por palabra.
- 0x465c0: valores por defecto de la ventana [0x1316]=0xF0 (240) y [0x1318]=3.
  0xc2f28 (desde 0x301c, 0x56d94) solo los cambia si arg4/arg5 != 0; en los 1.287 0x301c del juego
  (diagnostico/ventanas.py) arg4 = arg5 = 0.
=> límite 240 + 32 = 272; cabe un carácter si x + 12 < 272: **22 caracteres por línea** (cada letra y
   cada espacio de ancho completo cuentan 1) y **3 líneas por página**. No hay tope de bytes por
   página (búferes de 0x200 B de entrada y 0x3B0 B de salida en ventana+0x1104).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V77 = HERE.parents[1] / 'v77/saltos_dialogo'
if str(V77) not in sys.path:
    sys.path.insert(0, str(V77))

import comun as K  # noqa: E402  (v77: lectura de eventos, fuentes, medidor de tinta)
from comun import SALTO, PAGINA, sin_marcas, transportar  # noqa: E402,F401

ANCHO_VENTANA = 0xF0       # ina_main1.cro 0x465c0
EXTRA = 0x20               # 0x424f4: addne sl, sl, #0x20
AVANCE = 12                # FontGetCharWidth(FONT12), code.bin 0x25af98
LINEAS = 3                 # 0x465cc
LIMITE = ANCHO_VENTANA + EXTRA
MAX_CAR = max(n for n in range(1, 64) if (n - 1) * AVANCE + AVANCE < LIMITE)   # = 22
ANCHO_TINTA = K.ANCHO_UTIL  # 290 px: tope visual ya usado en v77 (nunca se alcanza con 22 caracteres)


def preprocesar(cuerpo: bytes) -> bytes:
    """0x36c54 para un registro español (sin % de formato): `\\n`/`\\f` -> 0x0A/0x0C."""
    out, i = bytearray(), 0
    while i < len(cuerpo):
        b = cuerpo[i]
        if b == 0x25:
            raise ValueError('código % no modelado')
        if b == 0x5C:
            i += 1
            c = cuerpo[i]
            out.append({0x6E: 0x0A, 0x66: 0x0C}.get(c, c))
            i += 1
            continue
        if b & 0x80:
            out += cuerpo[i:i + 2]
            i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


def motor(cuerpo: bytes, ancho=ANCHO_VENTANA, lineas=LINEAS, avance=AVANCE) -> bytes:
    """0x424f4: ajuste automático del motor. Devuelve el texto tal como lo dibuja la ventana."""
    s = bytearray(preprocesar(cuerpo))
    sl, out, x, ln, i = ancho + EXTRA, bytearray(), 0, 0, 0
    while i < len(s):
        c = s[i]
        if c == 0x0A:
            ln += 1
            x = 0
            if ln >= lineas:
                s[i] = 0x0C
                ln = 0
        elif c == 0x0C:
            x = ln = 0
        else:
            w = avance
            if x + w >= sl:
                ln += 1
                if ln < lineas:
                    out.append(0x0A)
                else:
                    out.append(0x0C)
                    ln = 0
                x = 0
            x += w
        if s[i] & 0x80:
            out.append(s[i])
            i += 1
        out.append(s[i])
        i += 1
    return bytes(out)


def paginas_motor(cuerpo: bytes):
    """[[línea española, ...], ...] tal como se ven en el juego."""
    t = motor(cuerpo).decode('cp932')
    es = K.a_espanol(t.encode('cp932'))
    return [pg.split('\n') for pg in es.split('\x0c')]


def ajustar(texto: str, ancho_linea=None, max_car: int = MAX_CAR, lineas: int = LINEAS,
            ancho: int = ANCHO_TINTA) -> str:
    """Ajuste nuevo: voraz por palabras con el límite REAL del motor (22 caracteres transportados por
    línea, 3 por página). Si se da `ancho_linea`, además exige tinta <= `ancho` px.
    Conserva los `\\f` del fuente, quita %NF, colapsa espacios y `\\n` (como v20 y v77)."""
    texto = sin_marcas(texto)

    def cabe(linea):
        if len(transportar(linea)) > max_car:
            return False
        return ancho_linea is None or ancho_linea(linea) <= ancho

    paginas = []
    for bloque in texto.split(PAGINA):
        filas, actual = [], ''
        for p in ' '.join(bloque.replace(SALTO, ' ').split()).split():
            if not cabe(p):
                raise ValueError(f'palabra más larga que la línea: {p}')
            cand = f'{actual} {p}' if actual else p
            if actual and not cabe(cand):
                filas.append(actual)
                actual = p
            else:
                actual = cand
        if actual:
            filas.append(actual)
        paginas.extend(SALTO.join(filas[i:i + lineas]) for i in range(0, len(filas), lineas))
    return PAGINA.join(paginas)


def respeta_motor(cuerpo: bytes) -> bool:
    """True si el motor no inserta ni convierte ningún salto: lo que dibuja es lo que escribimos."""
    pre = preprocesar(cuerpo)
    return motor(cuerpo) == pre
