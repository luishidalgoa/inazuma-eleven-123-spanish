"""IE2 v07 · media (issue #74): doblaje español y subtítulos de cinemáticas. No construye ni instala.

1. Voces: cada sound/sp/*.SAD de la NDS ES cuyo nombre existe (sin distinguir mayúsculas) en
   romfs/inazuma2/data_iz/sound de la base 3DS se copia ENTERO, sin recodificar, con el nombre 3DS:
   - comunes a Fuego y Ventisca -> romfs_mod/inazuma2/data_iz/sound/ (esta carpeta);
   - propios de Fuego (comun_media.SOLO_FUEGO_SAD) -> work/ie2/tormenta_de_fuego/capas/v07/media/romfs_mod/...
   sound.pb/ph (bancos SED/SWD/SMD) NO se tocan: ver bancos.py (pruebas de par en par).
2. Subtítulos: los vídeos MOFLEX japoneses se conservan. Cada movie/txt/<n>.dat 3DS se sustituye por la
   pista NDS ES movie/txt/sp/<n>.dat con sus mismos ticks de 30 Hz (misma unidad en ambas plataformas,
   ver comun_media) y el texto en FONT12 de ancho completo con casillas maquetadas al paso real (13,75 px;
   comun_media.Tipo) y, si hacen falta, casillas nuevas dibujadas en extra/font/FONT12.bcfnt (registro.json). Un subtítulo de más de
   21 casillas se parte en trozos consecutivos dentro de su mismo intervalo (reparto proporcional).
   - extra/inazuma2/data_iz/movie/txt/ (comunes) y, para op00.dat, la carpeta de Fuego.
3. informe.json (texto del juego: no publicar).

Uso: python -X utf8 work/ie2/shared/capas/v07/media/apply.py
"""
from __future__ import annotations

import json
import shutil
import sys

import comun_media as C


def limpiar(carpeta, patron):
    if carpeta.exists():
        for p in carpeta.glob(patron):
            p.unlink()


def voces(informe):
    jp = {p.name.upper(): p for p in C.SONIDO_JP.iterdir() if p.suffix.upper() == '.SAD'}
    es = {p.name.upper(): p for p in C.SONIDO_ES.iterdir() if p.suffix.upper() == '.SAD'}
    destinos = {False: C.SALIDA / C.ROMFS_SONIDO, True: C.SALIDA_FUEGO / C.ROMFS_SONIDO}
    for d in destinos.values():
        limpiar(d, '*.SAD')
        d.mkdir(parents=True, exist_ok=True)
    filas = []
    for clave in sorted(jp.keys() & es.keys()):
        nombre = jp[clave].name
        fuego = nombre.upper() in C.SOLO_FUEGO_SAD
        dst = destinos[fuego] / nombre
        shutil.copyfile(es[clave], dst)
        datos = dst.read_bytes()
        assert datos == es[clave].read_bytes()
        filas.append(dict(nombre=nombre, fuego=fuego, bytes=len(datos), sha256=C.sha(datos),
                          bytes_jp=jp[clave].stat().st_size))
    informe['voces'] = dict(
        instaladas=len(filas), comunes=sum(not f['fuego'] for f in filas), solo_fuego=sum(f['fuego'] for f in filas),
        sin_par_3ds=sorted(jp[k].name for k in jp.keys() - es.keys()),
        sin_par_nds=sorted(es[k].name for k in es.keys() - jp.keys()),
        ventisca_propios_sin_tocar=sorted(p.name for p in (C.SONIDO_JP.parent.parent / 'data_iz_blizzard/sound').glob('*.SAD')),
        ficheros=filas)
    print(f"voces: {len(filas)} copiadas ({informe['voces']['comunes']} comunes, "
          f"{informe['voces']['solo_fuego']} Fuego); sin par: {informe['voces']['sin_par_3ds']}")


def maquetar(T, pistas_es):
    """Partición de todos los subtítulos con las casillas nuevas permitidas en T (registra su uso)."""
    T.creados = {}
    out = {}
    for nombre, es in pistas_es.items():
        out[nombre] = []
        for s in es:
            trozos = C.partir(T, C.M.normalizar(C.es_nds(s.cuerpo)))
            for _, cel in trozos:
                T.usar(cel)
            out[nombre].append(trozos)
    return out


def subtitulos(informe):
    T = C.Tipo()
    destinos = {False: C.SALIDA / C.EXTRA_TXT, True: C.SALIDA_FUEGO / C.EXTRA_TXT}
    for d in destinos.values():
        limpiar(d, '*.dat')
        d.mkdir(parents=True, exist_ok=True)
    jp_nombres = sorted(p.split('/')[-1] for p in C.archivo_jp().por if p.startswith(C.RUTA_TXT))
    es_nombres = sorted(p.name for p in C.TXT_ES.glob('*.dat'))
    assert jp_nombres == es_nombres, (set(jp_nombres) ^ set(es_nombres))
    pistas_es = {}
    for nombre in es_nombres:
        es_raw = (C.TXT_ES / nombre).read_bytes()
        pistas_es[nombre] = C.leer_dat(es_raw)
        assert C.escribir_dat(pistas_es[nombre]) == es_raw, f'{nombre}: la pista NDS no se reescribe igual'

    # 1.ª pasada sin tope (PEN_NUEVO) y poda por uso hasta MAX_NUEVOS casillas nuevas.
    maqueta = maquetar(T, pistas_es)
    rondas = [len(T.creados)]
    while len(T.creados) > C.MAX_NUEVOS:
        permit = dict(T.creados)
        exceso = len(permit) - C.MAX_NUEVOS
        quitar = sorted(permit, key=lambda c: (permit[c], c))[:max(1, min(exceso, len(permit) // 8))]
        T.reiniciar(set(permit) - set(quitar))
        maqueta = maquetar(T, pistas_es)
        rondas.append(len(T.creados))
    fuente, añadidos = T.asignar_y_dibujar()
    C.FUENTE_CAPA.parent.mkdir(parents=True, exist_ok=True)
    C.FUENTE_CAPA.write_bytes(fuente)
    C.REG_CAPA.write_text(json.dumps(T.reg, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'casillas nuevas: {len(añadidos)} (poda {rondas})')

    pistas, partidos, total_es, total_out = [], 0, 0, 0
    for nombre in es_nombres:
        jp = C.leer_dat(C.dat_jp(nombre))
        es = pistas_es[nombre]
        salida, filas = [], []
        for k, (s, trozos) in enumerate(zip(es, maqueta[nombre])):
            tramos = C.repartir(s.inicio, s.fin, trozos)
            for (t, cel), (a, b) in zip(trozos, tramos):
                cuerpo = T.codificar(cel)
                salida.append(C.Sub(a, b, cuerpo))
                filas.append(dict(registro_nds=k, inicio=a, fin=b, texto=t, casillas='|'.join(cel),
                                  n_casillas=len(cel), hex=cuerpo.hex(),
                                  hueco_min_px=min(T.huecos_fases(cel), default=None),
                                  hueco_max_px=max(T.huecos_fases(cel), default=None)))
            partidos += len(trozos) > 1
        total_es += len(es)
        total_out += len(salida)
        datos = C.escribir_dat(salida)
        fuego = nombre in C.SOLO_FUEGO_TXT
        (destinos[fuego] / nombre).write_bytes(datos)
        pistas.append(dict(
            nombre=nombre, fuego=fuego, registros_jp=len(jp), registros_nds=len(es), registros_salida=len(salida),
            tiempos_iguales_a_jp=[(s.inicio, s.fin) for s in jp] == [(s.inicio, s.fin) for s in es],
            ultimo_fin_tick=max(s.fin for s in es), bytes=len(datos), sha256=C.sha(datos), subtitulos=filas))
    informe['subtitulos'] = dict(
        pistas=len(pistas), registros_nds=total_es, registros_salida=total_out, subtitulos_partidos=partidos,
        tiempos_distintos_de_jp=[p['nombre'] for p in pistas if not p['tiempos_iguales_a_jp']],
        fuente=f'extra/font/FONT12.bcfnt = FONT12 v90 (base {C.sha(T.base_bytes)}) + {len(añadidos)} casillas '
               f'de subtítulo; registro.json (v90 + pares_ie2_v07). Aplicar DESPUÉS de la capa de fuentes v90.',
        maqueta='v07b: ritmo v89 medido a paso 13/14 px (comun_media.Tipo)',
        casillas_nuevas=len(añadidos), poda=rondas,
        paso_modelo_px=C.AVANCE_DS * C.ESCALA, max_casillas=C.MAX_CELDAS, detalle=pistas)
    print(f'subtítulos: {len(pistas)} pistas, {total_es} registros NDS -> {total_out} ({partidos} partidos)')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    informe = dict(capa='work/ie2/shared/capas/v07/media', issue=74,
                   fuego='work/ie2/tormenta_de_fuego/capas/v07/media',
                   nota='Contiene texto y sumas de ficheros del juego: no publicar.',
                   hallazgos=[
                       'Los MOFLEX japoneses llevan el subtítulo japonés INCRUSTADO en la banda inferior '
                       '(incrustados.json: 704/773 bordes de subtítulo coinciden +-1 fotograma con un cambio en '
                       'la banda; control NDS 199/771). Si el juego pinta además movie/txt, el español saldrá '
                       'encima del japonés: comprobar en emulador antes de seguir.',
                       'Unidad de movie/txt: ticks de 30 Hz del tiempo de reproducción (CRO 0xe84bc; tiempos.json '
                       'y la alineación del texto incrustado lo confirman). Los ticks NDS se copian sin convertir.',
                       'a2m14: la NDS española es otro montaje (914 fotogramas, 38,08 s) frente al 3DS (1020, 42,5 s); '
                       'A2M14.SAD y sus 4 subtítulos siguen ese montaje: con el vídeo japonés se desincronizan '
                       '(el último subtítulo llega ~4,6 s antes).',
                       'Vídeos con variante visual española en la NDS (movie/sp): a2m06, a2y01-03, op00; se conserva '
                       'la imagen japonesa (logos/créditos en japonés).',
                       'J07.SAD solo existe en 3DS (se queda en japonés/original).',
                   ])
    voces(informe)
    subtitulos(informe)
    (C.SALIDA / 'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
