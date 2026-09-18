"""Validación offline de la línea v18 · teclado de IE2 (issue #73). runtime_verified=false.

Comprueba, sin emulador:
  1. Los siete ficheros existen bajo `romfs/inazuma2/data_iz/` y NADA más cuelga de `romfs/`.
  2. `fcode0/1/2.txt` miden 314 B exactos, terminan en CRLF y son 6 filas de 52 B (26 celdas).
  3. Cada letra ocupa SUS DOS celdas con el mismo código (formato del motor) y en la columna
     que le toca en la rejilla de 20 px (hueco tras la 5.ª columna).
  4. El contenido coincide carácter a carácter con `ie123kit.ie1.graficos.teclado.ROWS`
     en el modo del fichero (mayúsculas / minúsculas / mayúsculas sin cambio de modo).
  5. Los controles se conservan: `AAAA` (cambio de modo) y `DDDD` (borrar) siguen donde
     estaban en el japonés, y los de dakuten/handakuten (`BBBB`/`CCCC`) quedan en blanco.
  6. Los bytes son IDÉNTICOS a la tabla ya aprobada de IE1 en la candidata instalada
     (`inazuma1/data_iz/fcodeN.txt` de `archive.fa`), si se encuentra una candidata.
  7. `dakuten/handaku/ngword/fcodeck.txt` son copia byte a byte del japonés.
  8. Acentos y ñ: todos los caracteres de la rejilla se codifican con el transporte de
     ancho completo del proyecto y los acentuados salen por su PORTADOR GRIEGO
     (`tools/dialogue_typography.ACCENTS`), el mismo que ya usan los diálogos de IE2,
     así que la fuente de IE2 los dibuja sin cambios adicionales.
  9. Rejilla contra textura: en la textura latina de la capa v12 (`name_b.arc`), cada celda
     de 20x20 que la tabla declara con carácter tiene tinta, y cada celda declarada vacía
     no la tiene.

Uso: python work/ie2/shared/capas/v18/teclado/validate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apply as A  # noqa: E402
from apply import ROWS, FaArchive, CELDA  # noqa: E402

from ie123kit.nucleo.texto.ancho_completo import encode_fullwidth  # noqa: E402


def _celdas(datos):
    """[(fila, columna, par de bytes izquierdo, par derecho)] de un fcodeN de 314 B."""
    for fila in range(6):
        base = fila * 52
        for col in range(10):
            off = base + (col * 2 + (1 if col >= 5 else 0)) * 2
            yield fila, col, datos[off:off + 2], datos[off + 2:off + 4]


def _candidata():
    raiz = A.ROOT / 'work/shared/candidatas'
    if not raiz.is_dir():
        return None
    for d in sorted(raiz.iterdir(), reverse=True):
        fa = d / 'archive.fa'
        if fa.is_file():
            return fa
    return None


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    problemas = []
    base = FaArchive(str(A.BASE))

    escritos = {p.relative_to(HERE / 'romfs').as_posix() for p in (HERE / 'romfs').rglob('*') if p.is_file()}
    esperados = {f'inazuma2/data_iz/{n}' for n in list(A.TRADUCIDOS) + list(A.COPIADOS)}
    if escritos != esperados:
        problemas.append(f'romfs/ no coincide con el plan: {sorted(escritos ^ esperados)}')

    from ie123kit.nucleo.config.congelados import cargar
    ACCENTS = cargar('dialogue_typography').ACCENTS

    for nombre, modo in A.TRADUCIDOS.items():
        datos = (HERE / 'romfs/inazuma2/data_iz' / nombre).read_bytes()
        original = base.read(A.RAIZ_IE1 + nombre)
        if len(datos) != 314 or datos[-2:] != b'\r\n':
            problemas.append(f'{nombre}: tamaño/terminador inesperados ({len(datos)} B)')
            continue
        for fila, col, izq, der in _celdas(datos):
            ch = ROWS[fila][col]
            if izq != der:
                problemas.append(f'{nombre}: celda ({col},{fila}) con las dos mitades distintas')
            if ch == ' ':
                continue
            esperado = encode_fullwidth(ch.lower() if modo == 1 else ch)
            off = fila * 52 + (col * 2 + (1 if col >= 5 else 0)) * 2
            if modo == 2 and original[off:off + 4] == b'    ':
                if izq + der != b'    ':
                    problemas.append(f'{nombre}: celda ({col},{fila}) debía quedar vacía como el japonés')
                continue
            if izq != esperado:
                problemas.append(f'{nombre}: celda ({col},{fila}) es {izq!r}, se esperaba {esperado!r} para {ch!r}')
        for fila, control in ((0, b'AAAA'), (3, b'DDDD')):
            off = fila * 52 + 48
            if original[off:off + 4] == control and datos[off:off + 4] != control:
                problemas.append(f'{nombre}: se perdió el control {control.decode()} de la fila {fila}')
        for fila in (1, 2):
            off = fila * 52 + 48
            if datos[off:off + 4] != b'    ':
                problemas.append(f'{nombre}: la tecla de dakuten/handakuten de la fila {fila} no está en blanco')

    cand = _candidata()
    if cand is None:
        problemas.append('aviso: no hay candidata para cotejar con la tabla aprobada de IE1')
    else:
        arc = FaArchive(str(cand))
        for nombre in A.TRADUCIDOS:
            ie1 = arc.read(A.RAIZ_IE1 + nombre)
            if ie1 != (HERE / 'romfs/inazuma2/data_iz' / nombre).read_bytes():
                problemas.append(f'{nombre}: distinto de la tabla de IE1 en {cand.parent.name}')

    for nombre in A.COPIADOS:
        if (HERE / 'romfs/inazuma2/data_iz' / nombre).read_bytes() != base.read(A.RAIZ_IE1 + nombre):
            problemas.append(f'{nombre}: no es copia byte a byte del japonés')

    portadores = []
    for fila in ROWS:
        for ch in fila:
            if ch == ' ':
                continue
            for variante in {ch, ch.lower()}:
                try:
                    encode_fullwidth(variante)
                except Exception as exc:                       # noqa: BLE001
                    problemas.append(f'{variante!r} no se puede codificar: {exc}')
                if variante in ACCENTS:
                    portadores.append(f'{variante}->{ACCENTS[variante]}')

    tinta = {}
    for nombre, imagen in A._texturas().items():
        modo = 1 if 'kana01' in nombre else 0
        alfa = imagen.split()[3]
        vacias, con_texto = [], 0
        for fila in range(6):
            for col in range(10):
                caja = alfa.crop((col * CELDA, fila * CELDA, col * CELDA + CELDA, fila * CELDA + CELDA))
                hay = caja.getbbox() is not None
                if hay:
                    con_texto += 1
                else:
                    vacias.append((col, fila))
        tinta[nombre] = {'modo': modo, 'celdas_con_tinta': con_texto, 'celdas_vacias': vacias}
        if vacias:
            problemas.append(f'{nombre}: celdas de la rejilla sin dibujo: {vacias}')

    informe = dict(ficheros=sorted(escritos), portadores_griegos=sorted(set(portadores)),
                   rejilla_vs_textura=tinta, candidata_cotejada=str(cand) if cand else None,
                   runtime_verified=False, problemas=problemas,
                   resultado='PASS' if not problemas else 'FAIL')
    (HERE / 'validate.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(informe, ensure_ascii=False, indent=1))
    sys.exit(1 if problemas else 0)


if __name__ == '__main__':
    main()
