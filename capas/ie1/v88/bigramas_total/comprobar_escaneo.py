"""v88 · comprueba escaneo_v88.json (escaneo estricto de los códigos del registro sobre probe_ie1_v88):
cada aparición en texto debe estar en unitbase.dat, unitbase.STR o eve.pkb de IE1, y ninguna en contexto
textual de otros ficheros. Añade el resultado a validacion.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERMITIDOS = {'inazuma1/data_iz/logic/unitbase.dat', 'inazuma1/data_iz/logic/unitbase.STR',
              'inazuma1/data_iz/script/eve.pkb'}
esc = json.loads((HERE / 'escaneo_v88.json').read_text(encoding='utf-8'))
reg = json.loads((HERE / 'registro.json').read_text(encoding='utf-8'))
errores = []
for c in (e['sjis'] for e in reg['bigramas']):
    for ruta, cnt in esc['apariciones_textuales'].get(c, []):
        if ruta not in PERMITIDOS or cnt.get('binario_textual'):
            errores.append(f'{c} {ruta} {cnt}')
val = json.loads((HERE / 'validacion.json').read_text(encoding='utf-8'))
val['escaneo_kanji_v88'] = dict(codigos=len(reg['bigramas']), ficheros_con_codigos=sorted(
    {r for v in esc['apariciones_textuales'].values() for r, _ in v}), errores=errores,
    resultado='PASS' if not errores else 'FAIL')
if errores:
    val['resultado'] = 'FAIL'
(HERE / 'validacion.json').write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding='utf-8')
print(val['escaneo_kanji_v88']['resultado'], len(errores), errores[:10], val['escaneo_kanji_v88']['ficheros_con_codigos'])
