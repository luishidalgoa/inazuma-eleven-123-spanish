"""Línea v20 · teclado de nombre de IE2 (issue #77): la tabla que el juego LEE de verdad.

POR QUÉ FALLÓ LA v18
--------------------
La v18 puso fcode*.txt sueltos en romfs/inazuma2/data_iz/ (LayeredFS). El juego no los mira nunca.

CARGADOR REAL (ina_main2.cro JP, desensamblado con capstone)
-----------------------------------------------------------
* El array de recursos de CMainMenuScreenEnterName en seg1+0xfabc (fichero 0x221abc) es una lista de pares
  {nombre, ranura}: nedn_*.pac, srd_*.pac, fcode0/1/2.txt, handaku, dakuten, ngword, fcodeck.
* 0x16395c recorre ese array y llama a 0xfacfc(nombre, &ranura, paquete=[this+0xa4]).
* 0xfacfc -> 0x2020c4: comprueba la firma «SFP\\0» del PAQUETE, quita directorios del nombre, lo pasa a
  mayúsculas y lo busca en la tabla de nombres del paquete (entradas de 16 B: nombre, tamaño, bloque;
  datos = paquete + [0x10] + bloque * [0x0c]). No hay ruta de fichero: «fcode0.txt» es una entrada
  INTERNA del paquete.
* El paquete es /data_iz/pic2d/menu/MMName.SPF_ (cadena en 0x221b4c, cargado en 0x164e44) bajo la raíz de
  IE2: inazuma2/data_iz/pic2d/menu/MMName.SPF_ dentro de archive.fa, comprimido LZ10 (0x10). Dentro están
  FCODE0.TXT, FCODE1.TXT, FCODE2.TXT, DAKUTEN, HANDAKU, NGWORD y FCODECK, byte a byte iguales a los fcode
  japoneses de IE1. Por eso el barrido de la v18 (texto plano y L5) no los encontró: van en LZ10.
* La segunda lista (0x226004, pantalla de perfil) usa el mismo mecanismo con
  inazuma2/data_iz/pic2d/menu/MMProfd.SPF_, que lleva otra copia de las mismas tablas.

ARREGLO
-------
Se sustituyen FCODE0/1/2.TXT dentro de los dos paquetes por la tabla latina aprobada de IE1
(ie123kit.ie1.graficos.teclado.patch_map, la misma que generó la v18) y se recomprime en LZ10. Mismo tamaño
de entrada (314 B), misma tabla de nombres; DAKUTEN/HANDAKU/NGWORD/FCODECK intactos. Salida:
extra/inazuma2/data_iz/pic2d/menu/{MMName,MMProfd}.SPF_ (entradas YA existentes de archive.fa: el
constructor las acepta). La carpeta romfs/inazuma2/data_iz/fcode*.txt de la v18 sobra (no se lee).

Base: work/shared/candidatas/probe_ie2_v18/archive.fa. No construye ni instala.
Uso: python -X utf8 work/ie2/shared/capas/v20/teclado/apply.py
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / 'tools/src'))

from ie123kit.nucleo.contenedores.fa import FaArchive   # noqa: E402
from ie123kit.nucleo.compresion import lz10              # noqa: E402
from ie123kit.ie1.graficos.teclado import patch_map, ROWS  # noqa: E402

BASE = ROOT / 'work/shared/candidatas/probe_ie2_v18/archive.fa'
JP = ROOT / 'work/shared/base_3ds/romfs/archive.fa'
PAQUETES = ('inazuma2/data_iz/pic2d/menu/MMName.SPF_', 'inazuma2/data_iz/pic2d/menu/MMProfd.SPF_')
MODOS = {'FCODE0.TXT': 0, 'FCODE1.TXT': 1, 'FCODE2.TXT': 2}
IE1 = {'FCODE0.TXT': 'inazuma1/data_iz/fcode0.txt', 'FCODE1.TXT': 'inazuma1/data_iz/fcode1.txt',
       'FCODE2.TXT': 'inazuma1/data_iz/fcode2.txt'}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sfp_entradas(d):
    """{NOMBRE: (offset, tamaño)} de un paquete SFP descomprimido (ver 0x2020c4)."""
    if d[:4] != b'SFP\0':
        raise ValueError('no es SFP')
    tam_bloque, base = struct.unpack_from('<II', d, 0x0c)
    fin = struct.unpack_from('<I', d, 0x20)[0]      # primera cadena de nombre = fin de la tabla
    out = {}
    for i in range(0x20, fin, 16):
        n_off, tam, bloque, _ = struct.unpack_from('<4I', d, i)
        nombre = d[n_off:d.index(b'\0', n_off)].decode('ascii')
        out[nombre] = (base + bloque * tam_bloque, tam)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    arc, jp = FaArchive(str(BASE)), FaArchive(str(JP))
    informe = {'issue': 77, 'base': str(BASE.relative_to(ROOT)), 'base_sha256_entradas': {},
               'mecanismo': 'entradas FCODEn.TXT dentro de los paquetes SFP (LZ10) que carga el CRO',
               'cargador': {'array_recursos': 'ina_main2.cro 0x221abc (seg1+0xfabc)',
                            'recorrido': '0x16395c', 'busqueda': '0xfacfc -> 0x2020c4 (firma SFP, nombre en mayúsculas)',
                            'paquete': '/data_iz/pic2d/menu/MMName.SPF_ (0x221b4c, carga en 0x164e44)',
                            'segunda_lista': '0x226004 -> MMProfd.SPF_'},
               'paquetes': {}, 'runtime_verified': False}
    for ruta in PAQUETES:
        comp = arc.read(ruta)
        assert comp[0] == 0x10, ruta
        d = bytearray(lz10.decompress(comp))
        ent = sfp_entradas(d)
        d_jp = lz10.decompress(jp.read(ruta))
        ent_jp = sfp_entradas(d_jp)
        cambios = {}
        for nombre, modo in MODOS.items():
            off, tam = ent[nombre]
            viejo = bytes(d[off:off + tam])
            o_jp, t_jp = ent_jp[nombre]
            assert viejo == d_jp[o_jp:o_jp + t_jp], f'{ruta}:{nombre} ya no es la tabla japonesa'
            nuevo = patch_map(viejo, modo)
            assert len(nuevo) == tam
            d[off:off + tam] = nuevo
            cambios[nombre] = dict(offset=hex(off), bytes=tam, modo=modo, sha256_antes=sha(viejo),
                                   sha256_despues=sha(nuevo),
                                   igual_que_ie1_jp=viejo == jp.read(IE1[nombre]),
                                   controles_conservados=sorted({viejo[i:i + 4].decode() for i in range(0, 312, 2)
                                                                 if viejo[i:i + 4] in (b'AAAA', b'DDDD', b'EEEE')}),
                                   primera_fila=nuevo[:52].decode('cp932', 'replace'))
        nuevo_comp = lz10.compress(bytes(d))
        assert lz10.decompress(nuevo_comp) == bytes(d)
        destino = HERE / 'extra' / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(nuevo_comp)
        informe['base_sha256_entradas'][ruta] = sha(comp)
        informe['paquetes'][ruta] = dict(bytes_antes=len(comp), bytes_despues=len(nuevo_comp),
                                         sha256=sha(nuevo_comp), descomprimido=len(d), entradas=cambios,
                                         intactas=sorted(set(ent) - set(MODOS)))
    informe['rejilla'] = {'celda_px': 20, 'filas': ROWS}
    informe['nota'] = ('La carpeta romfs/ suelta de la v18 (inazuma2/data_iz/fcode*.txt) no la lee nadie: '
                       'puede retirarse de la próxima candidata. Texturas latinas del teclado: capa v12 (name_b.arc).')
    (HERE / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(informe, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
