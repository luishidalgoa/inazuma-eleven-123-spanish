"""IE2 v15 · SONDA de código: ancho del diálogo 0xF0 -> 0x1A0 (22 -> 37 caracteres por línea).

Autorizada explícitamente por el usuario (parche de código en ina_main2.cro, solo inmediatos).

CRO (base: ie2/shared/capas/v09/cofres = la de probe_ie2_v10):
  0x66a24  mov r1,#0xF0  -> mov r1,#0x1A0   (manejador 0x301a, 0x66884: ancho que pasa a 0xf59dc
                                              en cada diálogo; 0xf5a5c strhne -> [ventana+0x131e])
  0x4cabc  mov r2,#0xF0  -> mov r2,#0x1A0   (valores por defecto de la ventana, 0x4cac4 strh)
  0x4d6a0  mov r2,#0x120 -> mov r2,#0x1C0   (v15) ancho de la rejilla de dibujo de la página de diálogo:
                                              se guarda en el global [base+0xeef60] y 0x121a78 lo usa
                                              en vez de su argumento 0x100 (0x121bb8-0x121bcc); corte
                                              de dibujo si x + 12 > ancho (0x12208c-0x122098), así que
                                              0x120 = 288 -> 24 caracteres (lo visto en v14). 0x1C0 = 448
                                              -> 37 caracteres, igual que el reajuste.
  Las líneas por página (mov r2,#3 en 0x66a28 y mov r1,#3 en 0x4cac8) no se tocan.
  Único lector de [+0x131e]: el reajuste 0x48398 (límite = ancho + 0x20 = 448 -> 37 caracteres a 12).
  Se comprueba que ninguna entrada de las tablas de parches (importación 0xF8, relocalización interna
  0x128 y la tabla 0x130) cae sobre los bytes parcheados.

Eventos (base: probe_ie2_v10): 22500101 (escena de Nelly delante de casa de Mark) y 22500102 (la
siguiente), todos sus 0x301d arg 1 en español a 37 × 3 con la disposición de líneas del NDS
(pares.json de Fuego v02); si una línea NDS pasa de 37, reparto por frases
(comun_ie2.ajustar a 37) del texto NDS; si las palabras no coinciden con v10, el mismo reparto del
texto v10 sin sus saltos. Registros <= 247 B; el evento no crece respecto a v10 si tenía %NF.

Salida: romfs/cro/ina_main2.cro, ie2/events/*.ssd, informe.json.
Uso: python -X utf8 work/ie2/shared/capas/v15/ancho_dialogo/apply.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'work/ie2/tormenta_de_fuego/capas/v02/dialogo'))
import comun_ie2 as M  # noqa: E402

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs  # noqa: E402

W = ROOT / 'work'
CRO_BASE = W / 'ie2/shared/capas/v09/cofres/romfs/cro/ina_main2.cro'
BASE = W / 'shared/candidatas/probe_ie2_v10/archive.fa'
PARES = W / 'ie2/tormenta_de_fuego/capas/v02/dialogo/pares.json'
CRO_OUT = HERE / 'romfs/cro/ina_main2.cro'
EV_OUT = HERE / 'ie2/events'

ANCHO = 0x1A0
MAX_CAR = 37           # 12·n < 0x1A0 + 0x20 = 448
LINEAS = 3
PARCHES = [  # (dirección, antes, después, texto)
    (0x66a24, 0xE3A010F0, 0xE3A01E1A, '0x301a: mov r1,#0xF0 -> mov r1,#0x1A0'),
    (0x4cabc, 0xE3A020F0, 0xE3A02E1A, 'por defecto: mov r2,#0xF0 -> mov r2,#0x1A0'),
    (0x4d6a0, 0xE3A02E12, 0xE3A02D07, 'dibujo de página: mov r2,#0x120 -> mov r2,#0x1C0 (global +0xeef60)'),
]
CONTEXTO = [  # palabras que deben seguir intactas alrededor
    (0x66a28, 0xE3A02003, 'mov r2,#3 (líneas)'),
    (0x66a34, None, 'stm ip,{r1,r2}'),
    (0x4cac4, None, 'strh r2,[r0,#0x1e]'),
    (0x4cac8, 0xE3A01003, 'mov r1,#3 (líneas)'),
    (0x4d6fc, 0xE3A02C01, 'mov r2,#0x100 (argumento de ancho, anulado por el global)'),
    (0x4d6f4, 0xE3A00040, 'mov r0,#0x40 (alto de la rejilla)'),
]
EVENTOS = [22500101, 22500102]
TABLAS = {'importacion_0xF8': 0xF8, 'relocacion_interna_0x128': 0x128, 'tabla_0x130': 0x130}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def u32(d, o):
    return struct.unpack_from('<I', d, o)[0]


def parches_cro(d: bytes):
    """{tabla: [dirección de fichero parcheada, ...]} de las tablas de parches de 12 B."""
    segs = [struct.unpack_from('<III', d, u32(d, 0xC8) + 12 * i) for i in range(u32(d, 0xCC))]
    out = {}
    for nombre, h in TABLAS.items():
        off, n = u32(d, h), u32(d, h + 4)
        dirs = []
        for i in range(n):
            so = u32(d, off + 12 * i)
            seg = so & 0xF
            if seg >= len(segs):
                continue
            dirs.append(segs[seg][0] + (so >> 4))
        out[nombre] = dict(offset=hex(off), entradas=n, direcciones=dirs)
    return out, segs


def comprobar_reloc(d: bytes):
    tablas, segs = parches_cro(d)
    res = {}
    for a, *_ in PARCHES:
        choques = {}
        for nombre, t in tablas.items():
            # una entrada escribe 4 B en su dirección: choca si se solapa con [a, a+4)
            c = [hex(x) for x in t['direcciones'] if x - 3 <= a <= x + 3]
            if c:
                choques[nombre] = c
        cerca = sorted({x for t in tablas.values() for x in t['direcciones'] if abs(x - a) <= 0x80})
        res[hex(a)] = dict(choques=choques, entradas_a_0x80=[hex(x) for x in cerca])
    resumen = {k: dict(offset=v['offset'], entradas=v['entradas']) for k, v in tablas.items()}
    return res, resumen, [(hex(a), hex(b), c) for a, b, c in segs]


def parchear_cro():
    d = bytearray(CRO_BASE.read_bytes())
    antes = bytes(d)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    for a, w in [(a, w) for a, w, _ in CONTEXTO if w is not None]:
        assert u32(d, a) == w, hex(a)
    reg = []
    for a, w0, w1, txt in PARCHES:
        assert u32(d, a) == w0, (hex(a), hex(u32(d, a)))
        struct.pack_into('<I', d, a, w1)
        dis = [f'{i.mnemonic} {i.op_str}' for i in md.disasm(bytes(d[a:a + 4]), a)]
        reg.append(dict(direccion=hex(a), texto=txt, antes=struct.pack('<I', w0).hex(),
                        despues=struct.pack('<I', w1).hex(), desensamblado_despues=dis))
    difs = [i for i in range(len(d)) if d[i] != antes[i]]
    assert len(difs) <= 12 and all(any(a <= i < a + 4 for a, *_ in PARCHES) for i in difs), difs
    reloc, tablas, segs = comprobar_reloc(antes)
    assert all(not v['choques'] for v in reloc.values()), reloc
    CRO_OUT.parent.mkdir(parents=True, exist_ok=True)
    CRO_OUT.write_bytes(bytes(d))
    return dict(base=str(CRO_BASE), base_sha256=sha(antes), salida_sha256=sha(bytes(d)),
                bytes_distintos=[hex(i) for i in difs], parches=reg, segmentos=segs,
                tablas_parches=tablas, comprobacion_relocacion=reloc)


# ------------------------------------------------------------------ eventos

def largo(linea: str) -> int:
    return M.largo(linea)


def espanol(b: bytes) -> str:
    return M.normalizar(M.K.a_espanol(b).replace('－', '−').replace('～', '〜'))


def palabras(t: str):
    return t.replace(M.SALTO, ' ').replace(M.PAGINA, ' ').split()


def envolver37(texto: str) -> str:
    M.MAX_CAR = MAX_CAR
    try:
        return M.ajustar(texto)
    finally:
        M.MAX_CAR = 22


def disposicion_nds(es: str):
    """Líneas del NDS agrupadas en cajas de 3; None si alguna línea pasa de 37."""
    cajas = []
    for bloque in es.split(M.PAGINA):
        filas = [' '.join(x.split()) for x in bloque.split(M.SALTO)]
        filas = [x for x in filas if x]
        if any(largo(x) > MAX_CAR for x in filas):
            return None
        cajas += [filas[i:i + LINEAS] for i in range(0, len(filas), LINEAS)]
    return M.PAGINA.join(M.SALTO.join(c) for c in cajas)


def motor37(cuerpo: bytes) -> bytes:
    return M.K82.motor(M.motor_simulado(cuerpo), ancho=ANCHO)


def paginas37(cuerpo: bytes):
    es = M.K.a_espanol(motor37(cuerpo))
    return [pg.split('\n') for pg in es.split('\x0c')]


def comprobar_cuerpo(cuerpo: bytes, actual: bytes):
    t = cuerpo.decode('cp932')
    assert len(cuerpo) <= M.MAX_BYTES, len(cuerpo)
    assert not M.sin_glifo(cuerpo), M.sin_glifo(cuerpo)
    assert M.pct(t) == M.pct(actual.decode('cp932'))
    assert not M.FURI.search(t)
    pre = M.K82.preprocesar(M.motor_simulado(cuerpo))
    assert motor37(cuerpo) == pre, 'el motor a 0x1A0 reajusta'
    pags = paginas37(cuerpo)
    assert all(0 < len(p) <= LINEAS and all(0 < len(x) <= MAX_CAR for x in p) for p in pags), pags
    return pags


def eventos():
    base = M.Archivo(BASE)
    pares = json.loads(PARES.read_text(encoding='utf-8'))
    if EV_OUT.exists():
        shutil.rmtree(EV_OUT)
    EV_OUT.mkdir(parents=True)
    inf = {}
    for eid in EVENTOS:
        data = base.evento('eve', eid)
        end, ins, recs, dl = M.dialogos(data)
        por_i = {f['indice']: f for f in pares.get(f'eve:{eid}', [])}
        cambios, reg = {}, []
        for i in dl:
            actual = recs[i].body
            texto_v10 = espanol(actual)
            if not re.search(r'[A-Za-zÁÉÍÓÚáéíóúñÑ]', texto_v10) or re.search(r'[぀-ヿ一-鿿]', texto_v10):
                reg.append(dict(indice=i, estado='sin_cambio_no_espanol', texto=texto_v10))
                continue
            f = por_i.get(i)
            nds = M.normalizar(f['es']) if f else None
            texto, via = None, None
            if nds is not None and palabras(M.FURI.sub('', nds)) == palabras(texto_v10):
                texto, via = disposicion_nds(nds), 'nds'
                if texto is None:   # alguna línea NDS pasa de 37: reparto por frases del texto NDS
                    texto, via = envolver37(nds), 'nds_voraz37'
            if texto is None:       # palabras distintas del NDS: texto v10 sin sus saltos de 22
                plano = ' '.join(texto_v10.replace(M.PAGINA, ' ').replace(M.SALTO, ' ').split())
                texto, via = envolver37(plano), 'v10_voraz37'
            cuerpo = M.transportar(texto)
            assert palabras(espanol(cuerpo)) == palabras(texto_v10), (eid, i)
            pags = comprobar_cuerpo(cuerpo, actual)
            a22 = M.K82.motor(M.motor_simulado(cuerpo)) != M.K82.preprocesar(M.motor_simulado(cuerpo))
            if cuerpo != actual:
                cambios[i] = cuerpo
            reg.append(dict(indice=i, id=recs[i].instruction, via=via, antes=texto_v10, despues=texto,
                            bytes_antes=len(actual), bytes_despues=len(cuerpo), cajas=pags,
                            max_car=max(len(x) for p in pags for x in p),
                            partiria_a_22=a22))
        nuevo = M.S.replace(data, cambios)
        end2, ins2, recs2 = M.S.parse(nuevo)
        assert nuevo[32:end] == data[32:end] and ins2 == ins and len(recs2) == len(recs)
        for j, (a, b) in enumerate(zip(recs, recs2)):
            assert (a.instruction, a.argument) == (b.instruction, b.argument)
            assert j in cambios or a.raw == b.raw
        if re.search(rb'%\d+F', data):
            assert len(nuevo) <= len(data), (eid, len(nuevo), len(data))
        (EV_OUT / f'{eid}.ssd').write_bytes(nuevo)
        inf[str(eid)] = dict(bytes_v10=len(data), bytes_v14=len(nuevo), sha256_v10=sha(data),
                             sha256_v14=sha(nuevo), registros_cambiados=len(cambios),
                             registros=reg)
    return inf


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    assert HERE.parent.name == 'v15'
    cro = parchear_cro()
    evs = eventos()
    inf = dict(
        sonda='IE2 v15 ancho del diálogo: reajuste 0x1A0 + rejilla de dibujo 0x1C0 (37 × 3), parche de código autorizado por el usuario',
        motor=dict(reajuste='0x48398: sl=[+0x131e]+0x20, sb=[+0x1320]; corte si x+12 >= sl',
                   escritores_131e=['0x4cac4 (defecto)', '0xf5a5c strhne (0xf59dc)'],
                   lectores_131e=['0x483b0 (reajuste)'],
                   llamadores_0xf59dc={'0x5ffb0': 'argumentos del evento', '0x64c70': 'argumentos del evento',
                                       '0x66b10': '0x301a: [sp+0x3c]=ancho, [sp+0x40]=líneas (0x66a34)',
                                       '0x67ae4': 'argumentos del evento'},
                   limite=f'{ANCHO}+32={ANCHO + 32} -> {MAX_CAR} caracteres',
                   segundo_limite=dict(
                       visto_v14='«Nelly, da igual. Hay que» | « irse.» y «A estas alturas ya debe » | «de...»: 24 caracteres',
                       dibujo='0x4d5xx copia la página (hasta 0x0C) y llama a 0x121a78 (0x4d71c) con FONT12 '
                              '(data+0xcc), ancho 0x100, alto 0x40, hasta 0x180 glifos; antes guarda 0x120 en '
                              '[base+0xeef60] (0x4d6a0-0x4d6b4), que 0x121bb8 usa como ancho si > 0; '
                              '0x4d784 lo vuelve a 0 después',
                       corte='0x12208c: si x + FontGetCharWidth(12) > ancho -> nueva línea (x de rejilla y x '
                             'de pantalla a 0, y += alto); el carácter que desborda (el espacio) abre la línea '
                             'siguiente: de ahí el espacio inicial de « irse.»',
                       modelo='12·24 = 288 <= 288 cabe; 12·25 = 300 > 288 corta -> 24; con 0x1C0: 12·37 = 444 '
                              '<= 448, 38 -> 456 > 448',
                       textura='rejilla creada en 0x4ca68 con 0x122bdc(5, 3): 0x40<<3<<5 = 16384 píxeles '
                               '(256×64 o 512×32; sin demostrar). El juego original ya dibuja hasta 288 con '
                               'el argumento 256, así que el tamaño real no se ha podido cerrar')),
        cro=cro, eventos=evs)
    (HERE / 'informe.json').write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding='utf-8')
    print('cro', cro['salida_sha256'], cro['bytes_distintos'])
    for k, v in evs.items():
        print(k, v['bytes_v10'], '->', v['bytes_v14'], 'cambiados', v['registros_cambiados'], v['sha256_v14'])
        for r in v['registros']:
            if 'despues' in r:
                print('  ', r['indice'], r['via'], r['max_car'], repr(r['despues']))


if __name__ == '__main__':
    main()
