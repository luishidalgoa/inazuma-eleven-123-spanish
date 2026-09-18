"""v93 (IE1) / v09 (IE2) · mensaje de objeto obtenido («Buscar»: cofres, puertas, fichero completo).

Causa (IE1 ina_main1.cro; IE2 ina_main2.cro es idéntico con otros offsets):
  Función de recompensas 0x6BA30 (IE2 0x7B1A8 aprox.): el texto se monta en r8 (64 B, vacío al empezar,
  0x6B960 strb 0) con STD_ConcatenateString:
      por objeto normal:   nombre (0x6BB54) + «\n» (0x6BD00, 0x6BB78)
      carta tipo 0x0E:     nombre + 0x6BD2C («\nのフォーメーションカード»), sin «\n» de 0x6BD00
      carta tipo 0x11:     nombre + 0x6BD48 («\nのバトルカード»)
      al final (0x6BC74):  + 0x6BD74 «を%1F手に%1F入れた！»
  El nombre va SIEMPRE delante y el salto es de diseño (en japonés la partícula を empieza la 2.ª línea).
  v32/v33 tradujo 0x6BD74 como «　obtenido．» con espacio inicial (pensado para «(formac.) obtenido.»):
  en un objeto normal sale «Barrita\\n obtenido.» (espacio suelto y participio en masculino).
  0x6C358 (fichero de jugadores completo) hace lo mismo: 0x6C510 + nombre del objeto 0x89 + «\n» (0x6C534)
  + 0x6C538 (v33 «¡Obtenido!», mismo problema de género).

Texto oficial (NDS ES arm9 0xb1224/0xb1238 y port 3DS EU code.bin 0x1993c3): «Has conseguido:\\n%s»,
«Has conseguido la carta de\\ntáctica “%s”.», «…carta de\\npachanga “%s”.». El oficial pone el verbo delante
del nombre, cosa imposible aquí sin tocar código del CRO (FURIGANA_LECCIONES: no parchear código del CRO).
Solución: cierre neutro que no concuerda con el nombre, sin espacio inicial: «¡Premio!» en 0x6BD74 y 0x6C538.
Las cartas llevan el espacio al final de su sufijo: 0x6BD2C «\\n(táctica) » (término oficial «carta de
táctica»); 0x6BD48 «\\n(duelo)» se queda como estaba (hueco de 15 B: no cabe ni el espacio ni «pachanga»).

Solo casillas existentes del registro de v90 (camino proporcional «dlg» de FONT12, 0x301d): no se tocan fuentes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
V90 = ROOT / 'work/ie1/capas/v90/cro_restantes'
CANDIDATA = ROOT / 'work/shared/candidatas/probe_ie2_v05/archive.fa'
sys.path.insert(0, str(V90))
import comun90 as C  # noqa: E402

C.BASE_IE1 = CANDIDATA               # fuentes de la candidata (= extra/font de v90, se comprueba)
C.REG89 = V90 / 'registro.json'      # registro vigente (v90) como base de la tipografía
from crorefs2 import Refs  # noqa: E402

LINEA_MAX = 20                        # caracteres por línea de la ventana (approved_layout de v33)
NOMBRE = '＊'                         # marcador del nombre del objeto en las vistas compuestas

JUEGOS = {
    'ie1': dict(
        dir=ROOT / 'work/ie1/capas/v93/cofres', rel='romfs/cro/ina_main1.cro',
        base=V90 / 'romfs/cro/ina_main1.cro',
        orig=ROOT / 'work/shared/base_3ds/romfs/cro/ina_main1.cro',
        off=dict(sep=0x6bd00, tactica=0x6bd2c, duelo=0x6bd48, cierre=0x6bd74, sep_fich=0x6c534,
                 cierre_fich=0x6c538, fich=0x6c510)),
    'ie2': dict(
        dir=ROOT / 'work/ie2/shared/capas/v09/cofres', rel='romfs/cro/ina_main2.cro',
        base=ROOT / 'work/ie2/shared/capas/v04/cro_restantes/romfs/cro/ina_main2.cro',
        orig=ROOT / 'work/shared/base_3ds/romfs/cro/ina_main2.cro',
        off=dict(sep=0x7b47c, tactica=0x7b4a4, duelo=0x7b4c0, cierre=0x7b4ec, sep_fich=0x7bc7c,
                 cierre_fich=0x7bc80, fich=0x7bc58)),
}

# (clave, texto español, salto inicial)
CAMBIOS = [
    ('cierre', '¡Premio!', False),
    ('cierre_fich', '¡Premio!', False),
    ('tactica', '(táctica) ', True),
]
FUENTE_TXT = ('NDS ES arm9 0xb1224 «Has conseguido:\\n%s» y 0xb2928 «carta de táctica» (IE2 NDS 0xb30c8/0xb41f4; '
              '3DS EU code.bin 0x1993c3): verbo oficial imposible delante del nombre sin tocar código; '
              'cierre neutro sin concordancia de género')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tipografia():
    T = C.Tipografia()
    get = C.comun88.abrir(CANDIDATA)
    for f in C.FUENTES:
        assert sha(get(f)) == sha((V90 / 'extra' / f).read_bytes()), f'{f}: la candidata no lleva las BCFNT de v90'
    T.codec = C.A89.Codec(T.reg)
    return T


def celdas(T, texto, nmax):
    """Partición 'dlg' solo con casillas ya registradas y sin solapes."""
    prohib = set()
    while True:
        coste, cel = T.particion(texto, 'dlg', nmax, frozenset(prohib))
        if coste == C.R.INF:
            raise ValueError(f'{texto!r} no cabe en {nmax} casillas con códigos existentes')
        cel = list(cel)
        nuevas = {c for c in cel if (len(c) >= 2 or C.R.variante(c)) and c not in T.por_clave}
        if nuevas:
            prohib |= nuevas
            continue
        malos = T._solapes(cel, C.CAMPOS['dlg'][1])
        if not malos:
            return cel
        prohib |= malos


def cuerpo(d, o):
    return d[o:d.index(b'\0', o)]


def texto_de(T, b):
    """Texto legible de un cuerpo (casillas del registro, letras, saltos)."""
    return '\n'.join(''.join('¤' if c is None else C.texto(c) for c in T.codec.claves(t))
                     for t in b.split(b'\n'))


def usos(refs, o):
    return refs.refs(o)


def componer(tx):
    """Mensajes tal como los monta el juego (NOMBRE = nombre del objeto)."""
    return {
        'objeto': NOMBRE * 8 + tx['sep'] + tx['cierre'],
        'dos_objetos': NOMBRE * 8 + tx['sep'] + NOMBRE * 8 + tx['sep'] + tx['cierre'],
        'carta_tactica': NOMBRE * 8 + tx['tactica'] + tx['cierre'],
        'carta_duelo': NOMBRE * 8 + tx['duelo'] + tx['cierre'],
        'fichero_completo': tx['fich'] + NOMBRE * 8 + tx['sep_fich'] + tx['cierre_fich'],
    }


def comprobar_mensajes(msgs):
    errores = []
    for k, m in msgs.items():
        for ln in m.split('\n'):
            if ln.startswith((' ', '　')):
                errores.append(f'{k}: línea con espacio inicial {ln!r}')
            if len(ln) > LINEA_MAX:
                errores.append(f'{k}: línea de {len(ln)} > {LINEA_MAX} {ln!r}')
        if '\n\n' in m:
            errores.append(f'{k}: línea vacía')
        if any(p in m for p in ('obtenid', 'Obtenid')):
            errores.append(f'{k}: participio con género')
    return errores


def aplicar(j):
    sys.stdout.reconfigure(encoding='utf-8')
    cfg = JUEGOS[j]
    T = tipografia()
    base, orig = cfg['base'].read_bytes(), cfg['orig'].read_bytes()
    refs = Refs(orig)
    blanco = refs.targets | refs.reltargets
    out = bytearray(base)
    lits = []
    for clave, es, salto in CAMBIOS:
        o = cfg['off'][clave]
        jp = cuerpo(orig, o)
        fin_nul, fin_hueco = refs.hueco(o)
        assert o in blanco, (j, hex(o), 'sin referencia al inicio')
        dentro = [hex(t) for t in blanco if o < t < fin_hueco]
        assert not dentro, (j, hex(o), 'referencias dentro', dentro)
        cel = celdas(T, es, len(jp) // 2)
        enc = (b'\n' if salto else b'') + T.codificar(cel)
        assert enc and b'\0' not in enc, (j, hex(o), 'vacío o con NUL')
        assert len(enc) <= len(jp), (j, hex(o), len(enc), len(jp))
        assert len(enc) < fin_hueco - o, (j, hex(o), 'no cabe en el hueco')
        antes = cuerpo(base, o)
        out[o:fin_hueco] = enc + b'\0' * (fin_hueco - o - len(enc))
        lits.append(dict(
            offset=hex(o), clave=clave, japones=jp.decode('cp932'), antes=texto_de(T, antes),
            antes_hex=antes.hex(), espanol=('\n' if salto else '') + es,
            casillas='|'.join(C.texto(c) for c in cel), bytes=len(enc), bytes_japones=len(jp),
            hueco=[hex(o), hex(fin_hueco)], hex=enc.hex(), referencias=usos(refs, o),
            huecos_px_min=T.huecos_min(C.F12, cel, True), fuente_texto=FUENTE_TXT))
    tx = {k: texto_de(T, cuerpo(bytes(out), o)) for k, o in cfg['off'].items()}
    msgs = componer(tx)
    errores = comprobar_mensajes({k: v for k, v in msgs.items() if k != 'carta_duelo'})
    assert not errores, errores
    cambios = [i for i in range(len(base)) if base[i] != out[i]]
    dst = cfg['dir'] / cfg['rel']
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(out))
    informe = dict(
        archivo=cfg['rel'], base=cfg['base'].relative_to(ROOT).as_posix(), base_sha256=sha(base),
        salida=dst.relative_to(ROOT).as_posix(), salida_sha256=sha(bytes(out)), tamano=len(out),
        bytes_cambiados=len(cambios),
        causa=('El nombre del objeto se concatena primero y luego «\\n» (0x6BD00 en IE1) y el cierre; '
               'el cierre de v32/v33 «　obtenido．» empezaba con un espacio de ancho completo (pensado para '
               'las cartas) y concordaba en masculino. Mismo patrón en el mensaje de fichero completo.'),
        oficial='NDS ES / 3DS EU: «Has conseguido:\\n%s»; «Has conseguido la carta de\\ntáctica “%s”.»',
        decision=('El verbo oficial no puede ir delante del nombre sin parchear código del CRO: cierre neutro '
                  '«¡Premio!» sin espacio; el espacio pasa al final del sufijo de carta «(táctica) ».'),
        literales=lits,
        textos_resultantes=tx,
        mensajes_compuestos=msgs,
        pendiente=['Carta de duelo (tipo 0x11): «(duelo)¡Premio!» sin espacio; el hueco de 0x6BD48 (15 B) no '
                   'admite más. Sufijo heredado de v33, sin tocar.',
                   'Búfer del mensaje: 64 B (r8..r8+0x40); los cambios acortan el total respecto a v90 salvo '
                   'la carta de táctica (+2 B, sigue por debajo del japonés: 21+16 < 27+20).'],
        nota='Validación offline; pendiente de prueba en emulador según PROTOCOLO_QA.')
    (cfg['dir'] / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(j, 'bytes cambiados', len(cambios), 'sha', informe['salida_sha256'])
    for k, v in msgs.items():
        print(' ', k, '|', v.replace('\n', ' / '))


def validar(j):
    sys.stdout.reconfigure(encoding='utf-8')
    cfg = JUEGOS[j]
    inf = json.loads((cfg['dir'] / 'informe.json').read_text(encoding='utf-8'))
    base, orig = cfg['base'].read_bytes(), cfg['orig'].read_bytes()
    out = (cfg['dir'] / cfg['rel']).read_bytes()
    ok = []

    def chk(nombre, cond, det=''):
        ok.append(dict(prueba=nombre, ok=bool(cond), detalle=det))
        print('OK ' if cond else 'MAL', nombre, det)

    chk('sha de la salida = informe', sha(out) == inf['salida_sha256'], sha(out))
    chk('sha de la base = informe', sha(base) == inf['base_sha256'])
    chk('mismo tamaño', len(out) == len(base) == len(orig))
    T = tipografia()
    chk('BCFNT de la candidata = v90', True, 'comprobado en tipografia()')
    refs = Refs(orig)
    blanco = refs.targets | refs.reltargets
    permitidos = set()
    for lit in inf['literales']:
        o = int(lit['offset'], 16)
        fin = int(lit['hueco'][1], 16)
        permitidos.update(range(o, fin))
        b = cuerpo(out, o)
        chk(f'{lit["offset"]} bytes', 0 < len(b) <= lit['bytes_japones'] and len(b) < fin - o,
            f'{len(b)} <= {lit["bytes_japones"]}')
        chk(f'{lit["offset"]} relleno NUL', out[o + len(b):fin] == b'\0' * (fin - o - len(b)))
        chk(f'{lit["offset"]} sin referencias dentro', not [t for t in blanco if o < t < fin])
        claves = [c for t in b.split(b'\n') for c in T.codec.claves(t)]
        chk(f'{lit["offset"]} casillas registradas', None not in claves and all(
            len(c) < 2 or c in T.por_clave for c in claves))
        chk(f'{lit["offset"]} texto', texto_de(T, b) == lit['espanol'], repr(texto_de(T, b)))
    cambios = [i for i in range(len(base)) if base[i] != out[i]]
    chk('solo cambian los huecos de la tabla', all(i in permitidos for i in cambios), f'{len(cambios)} bytes')
    tx = {k: texto_de(T, cuerpo(out, o)) for k, o in cfg['off'].items()}
    msgs = componer(tx)
    err = comprobar_mensajes({k: v for k, v in msgs.items() if k != 'carta_duelo'})
    chk('mensajes compuestos: sin espacio inicial, sin género, <= 20 por línea', not err, '; '.join(err))
    chk('marcadores %NF fuera del cierre', b'%' not in cuerpo(out, cfg['off']['cierre']) + cuerpo(out, cfg['off']['cierre_fich']))
    for k in ('cierre', 'sep', 'tactica', 'duelo', 'cierre_fich', 'sep_fich'):
        o = cfg['off'][k]
        chk(f'{k} {hex(o)} referenciado por código', bool(refs.refs(o)), ', '.join(refs.refs(o)))
    res = dict(ok=all(x['ok'] for x in ok), pruebas=ok, mensajes=msgs)
    (cfg['dir'] / 'validacion.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print('RESULTADO', 'OK' if res['ok'] else 'FALLO')
    sys.exit(0 if res['ok'] else 1)
