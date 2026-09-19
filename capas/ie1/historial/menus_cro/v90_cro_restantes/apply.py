"""IE1 v90 + IE2 v04 · literales visibles del CRO que quedaban en japonés (bigramas en las BCFNT compartidas).

Una sola pasada para los dos juegos porque los códigos de bigrama y las fuentes font/*.bcfnt son comunes a la
recopilación (raíz de archive.fa):
  IE1  base work/shared/candidatas/probe_ie1_v89/romfs/cro/ina_main1.cro, tabla literales.json de esta carpeta
       -> romfs/cro/ina_main1.cro
  IE2  base work/ie2/shared/capas/historial/nombres/v03_textos/cro/romfs/cro/ina_main2.cro, tabla
       work/ie2/shared/capas/menus_cro/cro_restantes/literales.json -> romfs/cro/ina_main2.cro de esa carpeta
  Fuentes: extra/font/*.bcfnt (aquí y copia idéntica en la capa IE2), registro.json (v89 + pares nuevos).
  Vistas previas x4 por literal en su fuente real y a su paso real: previews/ de cada capa.
Las NFTR no se tocan (ver comun90.py: no pintan ni miden los literales del CRO).
Reglas del CRO: bytes <= japonés, nunca vacío, sin referencias dentro del hueco, listas empaquetadas con los
mismos bytes, casillas <= caracteres del japonés, relleno NUL.
Uso: python -X utf8 work/ie1/capas/historial/menus_cro/v90_cro_restantes/apply.py   (después validate.py en cada capa)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comun90 as C  # noqa: E402

ROOT = C.ROOT
IE2_DIR = ROOT / 'work/ie2/shared/capas/menus_cro/cro_restantes'
JUEGOS = {
    'ie1': dict(dir=HERE, tabla=HERE / 'literales.json', rel='romfs/cro/ina_main1.cro',
                base=ROOT / 'work/shared/candidatas/probe_ie1_v89/romfs/cro/ina_main1.cro',
                orig=ROOT / 'work/shared/base_3ds/romfs/cro/ina_main1.cro'),
    'ie2': dict(dir=IE2_DIR, tabla=IE2_DIR / 'literales.json', rel='romfs/cro/ina_main2.cro',
                base=ROOT / 'work/ie2/shared/capas/historial/nombres/v03_textos/cro/romfs/cro/ina_main2.cro',
                orig=ROOT / 'work/shared/base_3ds/romfs/cro/ina_main2.cro'),
}
NOMBRE_F = {C.F12: 'FONT12', C.F8: 'FONT8', C.F12T: 'FONT12T'}


def elegir(T, e, uso):
    alternativas = e.get('alternativas') or [[e.get('espanol'), e['campo']]]
    errores = []
    for texto, campo in alternativas:
        e2 = dict(e, espanol=texto, campo=campo)
        try:
            piezas, lineas = C.construir(T, e2, uso)
        except ValueError as ex:
            errores.append(str(ex))
            continue
        faltan = []
        if e.get('extra'):
            for k, v in piezas:
                if k == 'c':
                    faltan += T.extra(v, e['extra'])
        return e2, piezas, lineas, errores, faltan
    raise SystemExit(f'{uso}: ninguna alternativa cabe: {errores}')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    T = C.Tipografia()
    trabajo = {}
    for j, cfg in JUEGOS.items():
        tabla = json.loads(cfg['tabla'].read_text(encoding='utf-8'))
        filas = []
        for e in tabla['literales']:
            if 'igual_a' in e:
                filas.append(dict(e=e))
                continue
            e2, piezas, lineas, errores, faltan = elegir(T, e, f'{j}:{e["offset"]}')
            filas.append(dict(e=e, e2=e2, piezas=piezas, lineas=lineas, descartes=errores, faltan=faltan))
        trabajo[j] = (cfg, tabla, filas)
    añadidos = T.asignar_y_dibujar()

    salida_f = {}
    for destino in (HERE / 'extra', IE2_DIR / 'extra'):
        if destino.exists():
            shutil.rmtree(destino)
        salida_f = T.escribir_fuentes(destino)
    registro = T.registro_json(añadidos, salida_f)
    C.REG90.write_text(json.dumps(registro, ensure_ascii=False, indent=1), encoding='utf-8')

    for j, (cfg, tabla, filas) in trabajo.items():
        base = cfg['base'].read_bytes()
        orig = cfg['orig'].read_bytes()
        refs = C.Refs(orig)
        blanco = refs.targets | refs.reltargets
        out = bytearray(base)
        por_off, informe_lits, huecos = {}, [], set()
        prev_dir = cfg['dir'] / 'previews'
        if prev_dir.exists():
            shutil.rmtree(prev_dir)
        for fila in filas:
            e = fila['e']
            o = int(e['offset'], 16)
            jp = e['japones'].encode('cp932')
            assert orig[o:o + len(jp)] == jp and orig[o + len(jp)] == 0, (j, e['offset'])
            if 'base_v89' in e:
                actual = T.codec.texto(C.cuerpo(base, o))
                assert actual == e['base_v89'], (j, e['offset'], actual)
            else:
                assert base[o:o + len(jp) + 1] == jp + b'\0', (j, e['offset'], 'la base ya no tiene el japonés')
            if 'igual_a' in e:
                enc = por_off[int(e['igual_a'], 16)]
            else:
                enc = C.bytes_de(T, fila['piezas'])
            assert enc and enc.strip(b'\0') == enc, (j, e['offset'], 'vacío o con NUL')
            assert len(enc) <= len(jp), (j, e['offset'], len(enc), len(jp))
            if e.get('exacto'):
                assert len(enc) == len(jp), (j, e['offset'], 'lista empaquetada: longitud distinta')
            fmt_es = C.FMT.findall(enc.decode('latin1'))
            assert [x for x in fmt_es if x != '\n'] == [x for x in C.FMT.findall(e['japones']) if x != '\n'], e
            internas = {int(k, 16): v for k, v in e.get('referencias_internas', {}).items()}
            dentro = [t for t in blanco if o < t < o + len(jp) and t not in internas]
            assert not dentro, (j, e['offset'], [hex(t) for t in dentro])
            for t, txt in internas.items():
                assert (t - o) % 2 == 0 and C.cuerpo(enc + b'\0', t - o) == T.codificar([txt]), (e['offset'], hex(t))
            rango = range(o, o + len(jp) + 1)
            assert not huecos.intersection(rango), (j, e['offset'], 'solapa')
            huecos.update(rango)
            out[o:o + len(jp) + 1] = enc + b'\0' * (len(jp) + 1 - len(enc))
            por_off[o] = enc
            if 'igual_a' in e:
                informe_lits.append(dict(offset=e['offset'], japones=e['japones'], igual_a=e['igual_a'],
                                         bytes=len(enc), hex=enc.hex(), motivo=e['fuente']))
                continue
            e2 = fila['e2']
            fuentes = C.REALES[e2['campo']]
            if e.get('extra'):
                fuentes = tuple(fuentes) + tuple(f for f in e['extra'] if f not in fuentes)
            prop = e2['campo'] == 'dlg'
            solapes, rutas = {}, []
            for f in fuentes:
                ok_f = not any(ff == f for _, ff in fila['faltan'])
                minimo = None
                for ln in fila['lineas']:
                    for grupo in _grupos(ln):
                        g = T.huecos_min(f, grupo, prop and f == C.F12)
                        if g is not None:
                            minimo = g if minimo is None else min(minimo, g)
                solapes[NOMBRE_F[f]] = dict(hueco_min_px=minimo, dibujado=ok_f,
                                            paso='proporcional' if (prop and f == C.F12) else f'{C.PASO[f]} px')
                if ok_f:
                    assert minimo is None or minimo >= C.A88.HUECO_MIN[f], (j, e['offset'], f, minimo)
                    puntos = T.colocar(f, fila['lineas'], prop and f == C.F12)
                    ruta = prev_dir / f'{j}_{e["offset"]}_{NOMBRE_F[f]}_x4.png'
                    C.png(puntos, ruta)
                    rutas.append(str(ruta.relative_to(ROOT)).replace('\\', '/'))
            vista = ' / '.join('|'.join('¤' if c is None else C.texto(c) for c in ln) for ln in fila['lineas'])
            informe_lits.append(dict(
                offset=e['offset'], japones=e['japones'], espanol=e2['espanol'] if 'celdas' not in e else
                ''.join(e['celdas']), campo=e2['campo'], casillas=vista, bytes=len(enc), bytes_japones=len(jp),
                hex=enc.hex(), fuente_texto=e['fuente'], pinta=e['pinta'], nota=e.get('nota'),
                alternativas_descartadas=fila['descartes'], sin_dibujo_extra=[
                    f'{C.texto(c)}:{NOMBRE_F[f]}' for c, f in fila['faltan']],
                huecos=solapes, previews=rutas))
        cambios = [i for i in range(len(base)) if base[i] != out[i]]
        assert all(i in huecos for i in cambios)
        dst = cfg['dir'] / cfg['rel']
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(bytes(out))
        informe = dict(
            archivo=cfg['rel'], base=str(cfg['base'].relative_to(ROOT)).replace('\\', '/'),
            base_sha256=C.sha(base), salida=str(dst.relative_to(ROOT)).replace('\\', '/'),
            salida_sha256=C.sha(bytes(out)), tamano=len(out),
            traducidos=len(informe_lits), invisibles=tabla['invisibles'],
            fuentes_bcfnt={f: dict(sha256=s, ruta=f'{cfg["dir"].relative_to(ROOT).as_posix()}/extra/{f}')
                           for f, s in salida_f.items()},
            registro=str(C.REG90.relative_to(ROOT)).replace('\\', '/'),
            pares_nuevos=len(añadidos),
            nftr='sin cambios: los literales del CRO se pintan con las BCFNT (DrawTextHintOnVram por FONT_TYPE) '
                 'y se miden con FontGetCharWidth/NWFontGetCharWidth; la NFTR solo se carga en el objeto NNS',
            bytes_cambiados=len(cambios), literales=informe_lits,
            nota='Validación offline; pendiente de prueba en emulador según PROTOCOLO_QA.')
        (cfg['dir'] / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
        print(j, 'traducidos', len(informe_lits), 'bytes cambiados', len(cambios), 'sha', informe['salida_sha256'])
    print('pares nuevos', len(añadidos), añadidos)
    print('fuentes', salida_f)


def _grupos(linea):
    """Tramos de casillas contiguas (los formatos %s/%d cortan)."""
    out, cur = [], []
    for c in linea:
        if c is None:
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(c)
    if cur:
        out.append(cur)
    return out


if __name__ == '__main__':
    main()
