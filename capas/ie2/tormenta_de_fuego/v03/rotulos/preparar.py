"""IE2 Fuego v03 · rótulos de lugar (0x4037 a3) y objetivos (0x2017/0x2018/0x201c/0x2023 a3).

Entrada: tabla.json (a mano) + inventario de eve.pkb japonés (inventario.py, se recalcula aquí).
- Rótulo: primer candidato que cabe en B.rotulo (<= 10 casillas con centrado, bigramas FONT8).
- Rótulo: texto completo si cabe; si no, se quitan palabras (nunca se parafrasea). Origen en tabla['rotulos_origen'].
- Objetivo con par NDS: texto oficial literal (solo M.normalizar para glifos), <= 128 casillas (búfer 64x128
  FONT12, work/ie2/shared/capas/v01/limites_cro/informe.json caja_objetivo_0x402f). Sin par: tabla 'JP:'.
- Cabecera 0x402f a2: もくてき -> Objetivo.
Salida: textos.json e informe.json. Falla (exit 1) si algo queda sin texto válido.
Uso: python -X utf8 preparar.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'work/ie2/shared/capas/v03/textos'))

import inventario as I  # noqa: E402
import comun_v03  # noqa: E402

OBJ_MAX = 128
PROHIBIDO = set('\'"’‘“”«»')


def main():
    tabla = json.loads((HERE / 'tabla.json').read_text(encoding='utf-8'))
    I.main()
    inv = json.loads((HERE / 'inventario.json').read_text(encoding='utf-8'))
    B = comun_v03.bigramas()
    errores = []

    # ---- rótulos
    rotulos, abreviados, detalle = {}, [], {}
    for jp in sorted({r['jp'] for r in inv['rotulos']}):
        cands = tabla['rotulos'].get(jp)
        if cands is None:
            errores.append(f'rótulo sin entrada: {jp!r}')
            continue
        if jp == '':
            rotulos[jp] = ''
            continue
        elegido = None
        for c in cands:
            try:
                cuerpo = B.rotulo(c)
            except ValueError as e:
                detalle.setdefault(jp, []).append(str(e))
                continue
            elegido = c
            cel = B.celdas(c, 'rotulo')
            break
        if elegido is None:
            errores.append(f'rótulo sin candidato que quepa: {jp!r} {cands}')
            continue
        rotulos[jp] = elegido
        if elegido != cands[0]:
            abreviados.append({'jp': jp, 'largo': cands[0], 'rotulo': elegido,
                               'motivo': f'{len(B.celdas(cands[0], "rotulo"))} casillas > 10; ' + (
                                   'se quitan palabras' if set(elegido.lower().split()) <= set(cands[0].lower().split())
                                   else 'abreviatura IE1 para distinguir lugares del mismo mapa')})
        detalle[jp] = {'es': elegido, 'casillas': '|'.join(cel), 'n': len(cel), 'bytes': len(cuerpo)}

    # ---- objetivos
    objetivos, condensados = [], {}
    sin_fuente = []
    mismo_jp = {}
    for o in inv['objetivos']:
        if o['es_nds']:
            mismo_jp.setdefault(o['jp'], o['es_nds'])
    for o in inv['objetivos']:
        lim = OBJ_MAX
        if o['es_nds']:
            cands, clave = [comun_v03.normalizar(o['es_nds'])], None
        elif o['jp'] in mismo_jp:
            cands, clave = [comun_v03.normalizar(mismo_jp[o['jp']])], 'mismo_jp'
        else:
            clave = 'JP:' + o['jp']
            cands = tabla['objetivos'].get(clave)
            if cands is None:
                errores.append(f'objetivo sin entrada: {clave!r} ({o["evento"]}#{o["indice"]})')
                continue
        elegido, info = None, None
        for c in cands:
            if PROHIBIDO & set(c):
                continue
            try:
                cuerpo, n = B.libre(c, 'objetivo')
            except ValueError as e:
                errores.append(str(e))
                continue
            if n <= lim:
                elegido, info = c, (n, len(cuerpo))
                break
        if elegido is None:
            errores.append(f'objetivo sin candidato válido: {o["evento"]}#{o["indice"]} {cands}')
            continue
        objetivos.append({'evento': o['evento'], 'indice': o['indice'], 'op': o['op'], 'jp': o['jp'],
                          'es_nds': o['es_nds'], 'es': elegido})
        if not o['es_nds']:
            sin_fuente.append({'evento': o['evento'], 'indice': o['indice'], 'jp': o['jp'], 'es': elegido,
                               'motivo': ('evento ausente en la NDS' if not o['nds'] else
                                          'la instrucción no tiene par en el evento NDS')
                               + ('; texto NDS de otro evento con el mismo japonés' if clave == 'mismo_jp'
                                  else '; traducido del japonés')})
        elif elegido != o['es_nds']:
            condensados[f"{o['evento']}#{o['indice']}"] = {'nds': o['es_nds'], 'es': elegido,
                                                          'motivo': 'normalización de glifos'}

    # cabecera
    for jp, es in tabla['cabecera'].items():
        B.libre(es, 'objetivo')

    textos = {'cabecera': tabla['cabecera'], 'rotulos': rotulos, 'objetivos': objetivos,
              'rotulos_registros': [{'evento': r['evento'], 'indice': r['indice'], 'jp': r['jp']}
                                    for r in inv['rotulos']]}
    (HERE / 'textos.json').write_text(json.dumps(textos, ensure_ascii=False, indent=1), encoding='utf-8')
    informe = {
        'rotulos_registros': len(inv['rotulos']),
        'rotulos_unicos': len({r['jp'] for r in inv['rotulos']}),
        'rotulos_vacios': sum(1 for r in inv['rotulos'] if r['jp'] == ''),
        'cabeceras_402f': inv['cabeceras'],
        'objetivos_registros': len(inv['objetivos']),
        'objetivos_con_nds': sum(1 for o in inv['objetivos'] if o['es_nds']),
        'objetivos_sin_nds': sin_fuente,
        'rotulos_sin_nds': [{'jp': jp, 'es': es, 'motivo': ('inventado (sin nombre oficial NDS ni IE1)'
                             if jp in tabla['rotulos_origen']['inventado'] else tabla['rotulos_origen']['_defecto'])}
                            for jp, es in rotulos.items() if jp],
        'rotulos_abreviados': abreviados,
        'rotulos_detalle': detalle,
        'objetivos_modificados': condensados,
        'errores': errores,
    }
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"rótulos {informe['rotulos_registros']} ({informe['rotulos_unicos']} únicos, "
          f"{len(abreviados)} abreviados) · objetivos {len(objetivos)}/{len(inv['objetivos'])} "
          f"({len(condensados)} modificados, {len(sin_fuente)} sin NDS) · cabeceras {inv['cabeceras']} · errores {len(errores)}")
    for e in errores:
        print(' ', e)
    return 1 if errores else 0


if __name__ == '__main__':
    sys.exit(main())
