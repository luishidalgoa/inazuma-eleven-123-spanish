"""IE2 v13 · titulos: títulos de equipo (rpgtitle.STR) con la forma oficial NDS más completa que quepa.

Límite: el juego copia el título a búferes de 19 B (menú de mando, 0x1a3e5c -> 0xf1e08 con r3 = 0x13) y de
24 B (resúmenes de ranura/listas: 0x82578, 0x18355c, 0x183a30, 0x1af984, 0x1c3a4c -> 0xec214 con r3 = 0x18 o
0x19; 0xec214 exige >= 0x13 y copia 0x20). El japonés más largo mide 18 B (IE1 v46): máximo 9 casillas de
2 B + NUL.

Fuentes que lo pintan: el menú de mando (0x1a2600) pinta sus rótulos con el gestor seg2+0xcc (FONT12) y la
celda 称号 con seg2+0xc4 (FONT8); los demás caminos solo copian el título a registros de resumen y no se
resolvió su gestor. Todo texto del juego pasa por un gestor FONT8, FONT12 o FONT12T (v90 comun90; RUBI8 solo
para rubí), así que se usan SOLO casillas del registro dibujadas en las tres fuentes y letras nativas
(campo «nombre» de v08: FONT8 a paso 10, FONT12 y FONT12T a paso 15, sin solapes). No se crean códigos ni se
tocan fuentes: el registro y las BCFNT son los de v08 (= probe_ie2_v10).

Por título: candidatos = texto oficial NDS completo; sin «Equipo »/artículo inicial; la forma actual (v03).
Se elige el primero que v08 Diseno.partir('nombre', ..., 9) compone sin casillas nuevas y sin solapes; solo se
cambia si queda más completo que el actual.
Salida: extra/inazuma2/data_iz/logic/rpgtitle.STR, informe.json. Uso: python -X utf8 apply.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
W = ROOT / 'work'
V08 = W / 'ie2/shared/capas/v08/nombres_compactos'
sys.path.insert(0, str(V08))
import comun08 as K  # noqa: E402

K.REG07 = V08 / 'registro.json'
K.FUENTE_ORIGEN = {f: V08 / 'extra' / f for f in K.FUENTES}
import diseno08 as D  # noqa: E402
import modelo8 as M8  # noqa: E402

sys.path.insert(0, str(W / 'ie2/tormenta_de_fuego/capas/v02/dialogo'))
import comun_ie2 as M  # noqa: E402

A89, A88 = K.A89, K.A88
V79 = A88.V79
RUTA = 'inazuma2/data_iz/logic/rpgtitle.STR'
NDS_STR = W / 'ie2/tormenta_de_fuego/fuentes/nds_es/data_iz/logic/sp/rpgtitle.STR'
CAND = M.CAND / 'probe_ie2_v10/archive.fa'
SALIDA = HERE / 'extra' / RUTA
CASILLAS = 9
REG = 32
ESPACIO = '　'.encode('cp932')
TRES = set(K.FUENTES)
ARTICULOS = ('Equipo ', 'Los ', 'Las ', 'La ', 'El ')


def candidatos(oficial, actual):
    out = [oficial]
    for a in ARTICULOS:
        if oficial.startswith(a):
            out.append(oficial[len(a):])
    out.append(actual)
    vistos = set()
    return [t for t in out if t and not (t in vistos or vistos.add(t))]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    reg, Fs, antes, tmp = K.cargar_fuentes()
    shutil.rmtree(tmp, ignore_errors=True)
    Dz = D.Diseno(reg, Fs)
    Dz.coste_def = M8.INF                      # sin casillas nuevas
    codec = A89.Codec(reg['bigramas'])
    base = bytearray(M.Archivo(CAND).get(RUTA))
    nds = (NDS_STR).read_bytes()
    assert len(nds) == len(base)

    def partir(t):
        while True:
            cst, sel = Dz.partir('nombre', t, CASILLAS)
            if cst == M8.INF:
                return None
            malos = Dz.fallos(sel, 'nombre')
            for c, _, _ in sel:
                if c in Dz.por_clave and not TRES <= set(Dz.por_clave[c]['fuentes']):
                    malos.add(c)
                if c.startswith(D.PREF) and c not in Dz.por_clave:
                    malos.add(c)                 # casilla nueva: no permitida
            if not malos:
                return sel
            Dz.prohibidos[('nombre', t)] |= malos

    def cod(c):
        if c == ' ':
            return ESPACIO
        if c in Dz.por_clave:
            return bytes.fromhex(Dz.por_clave[c]['sjis'])
        assert len(c) == 1, c
        return V79.codificar(c)

    filas = []
    for i in range(len(base) // REG):
        cuerpo = bytes(base[i * REG:(i + 1) * REG]).split(b'\0')[0]
        of = nds[i * REG:(i + 1) * REG].split(b'\0')[0]
        if not cuerpo or not of:
            continue
        oficial = M.normalizar(M.decode_nds(of))
        actual = codec.texto(cuerpo)
        fila = dict(indice=i, jp=M.Archivo(M.JP).get(RUTA)[i * REG:(i + 1) * REG].split(b'\0')[0].decode('cp932'),
                    oficial=oficial, actual=actual)
        for t in candidatos(oficial, actual):
            sel = partir(t)
            if sel is None:
                continue
            nuevo = b''.join(cod(c) for c, _, _ in sel)
            assert codec.texto(nuevo) == t and len(nuevo) <= 2 * CASILLAS, (i, t)
            fila.update(elegido=t, casillas=len(sel), bytes=len(nuevo),
                        claves=[c if len(c) == 1 else Dz.por_clave[c]['sjis'] for c, _, _ in sel])
            if t != actual and len(t.replace('.', '')) > len(actual.replace('.', '')):
                base[i * REG:(i + 1) * REG] = nuevo.ljust(REG, b'\0')
                fila['cambia'] = True
            break
        filas.append(fila)
    if (HERE / 'extra').exists():
        shutil.rmtree(HERE / 'extra')
    SALIDA.parent.mkdir(parents=True)
    SALIDA.write_bytes(bytes(base))
    informe = dict(archivo=RUTA, casillas_max=CASILLAS, fuentes=sorted(TRES), registro=str(K.REG07.relative_to(ROOT)),
                   cambiados=sum(1 for f in filas if f.get('cambia')), titulos=filas, runtime_verified=False)
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    for f in filas:
        print(f['indice'], f['actual'], '->', f.get('elegido'), '(cambia)' if f.get('cambia') else '', '| NDS:', f['oficial'])


if __name__ == '__main__':
    main()
