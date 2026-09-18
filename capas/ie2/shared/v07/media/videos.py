"""IE2 v07 · media: cinemáticas 3DS sin el subtítulo japonés incrustado (issue #74).

Enfoque aprobado por el usuario: se conservan los MOFLEX 3DS (mejor calidad), se borra el subtítulo japonés de la
banda negra inferior (columnas 0-31 del fotograma 240x320 = filas 208-239 en pantalla) y se recodifica con
mobipeg x86 a los mismos fps, fotogramas y layout 0x16. El juego pinta el español desde movie/txt/*.dat.

- Comprobación automática de la banda (banda_ok): fondo plano ~25, columnas 0-5 planas, crominancia neutra y todo
  píxel no plano dentro de la zona de texto (tinta fuerte de fotogramas vecinos
  dilatada 3 px; halo del códec |d| <= 20 a <= 16 px) o borde de 4 px con
  el dibujo (cols 28-31, |d| <= 16); plano = |d| <= 4 (ruido del códec). Si falla, el vídeo se marca y NO se limpia ni se instala.
- a2m14: se usa el vídeo NDS español (otro montaje, 914 fotogramas; A2M14.SAD y su .dat lo siguen).
- op00 (solo Fuego): base 3DS en la línea de tiempo NDS (el SAD y el .dat españoles siguen el montaje NDS, que
  va 2 fotogramas 3DS por detrás antes del logotipo y 8/7 después); el logotipo español (NDS 24,0-28,0 s) se
  compone sobre el fondo 3DS solo donde difiere; 2328 fotogramas (= OP00.SAD 97,0 s).
- a2m06: el marcador («Academia Alius / Kirkwood», también en las piezas que salen volando) y la pizarra final
  se toman del vídeo NDS español (sp/a2m06.mods) con el mismo método (rotulos.py); el resto, planos 3DS exactos.
- a2m20b: el cartel 帝国学園 (al fondo del paneo y en primer plano) se toma del NDS («Royal Academy», movie/a2m20b.mods).
- NDS: YCgCo de rango completo (U = Cg, V = Co), 256x192 x 1,25 = 320x240.
Salida: extra/inazuma2/data_iz/movie/<n>.moflex (op00 en la carpeta de Fuego) y videos.json.
Uso: python -X utf8 videos.py [nombres...]   (sin nombres: los 35)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import comun_media as C

sys.path.insert(0, str(C.ROOT / 'tools/src'))
from ie123kit.nucleo.media.moflex import set_moflex_rotation  # noqa: E402

MOBIPEG = C.W / 'shared/herramientas/media_tools/mobipeg-v2.1-x86/ffmpeg.exe'
W, H = 240, 320
BANDA = 32                      # columnas 0-31
NEGRO = 25
QP = {'op00': 14}
QP_DEFECTO = 12
ROTULOS = {'a2m06', 'a2m20b'}           # rótulos del dibujo sustituidos (rotulos.TRAMOS)
RUTA_VIDEOS = Path('extra/inazuma2/data_iz/movie')
INFORME = C.SALIDA / 'videos.json'


def destino(n: str) -> Path:
    return (C.SALIDA_FUEGO if n == 'op00' else C.SALIDA) / RUTA_VIDEOS / f'{n}.moflex'


# ------------------------------------------------------------------ E/S de vídeo
def leer_yuv(ruta: Path, w=W, h=H):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(ruta), '-map', '0:v:0', '-f', 'rawvideo',
                        '-pix_fmt', 'yuv420p', '-'], capture_output=True, check=True).stdout
    F = np.frombuffer(r, np.uint8).reshape(-1, w * h * 3 // 2)
    Y = F[:, :w * h].reshape(-1, h, w)
    U = F[:, w * h:w * h * 5 // 4].reshape(-1, h // 2, w // 2)
    V = F[:, w * h * 5 // 4:].reshape(-1, h // 2, w // 2)
    return Y.copy(), U.copy(), V.copy()


def nds_a_rgb(Y, U, V):
    """YCgCo rango completo (NDS) -> RGB 320x240."""
    import cv2
    out = np.empty((len(Y), 240, 320, 3), np.uint8)
    for i in range(len(Y)):
        y = Y[i].astype(np.float32)
        cg = cv2.resize(U[i], (256, 192), interpolation=cv2.INTER_LINEAR).astype(np.float32) - 128
        co = cv2.resize(V[i], (256, 192), interpolation=cv2.INTER_LINEAR).astype(np.float32) - 128
        t = y - cg
        rgb = np.clip(np.stack([t + co, y + cg, t - co], -1), 0, 255)
        out[i] = np.clip(cv2.resize(rgb, (320, 240), interpolation=cv2.INTER_LANCZOS4), 0, 255).round()
    return out


def yuv_a_rgb(Y, U, V):
    """BT.601 rango limitado (lo que usa ffmpeg con los MOFLEX 3DS) -> RGB en orientación de pantalla 320x240."""
    y = (Y.astype(np.float32) - 16) * 255 / 219
    u = (U.repeat(2, 1).repeat(2, 2).astype(np.float32) - 128) * 255 / 224
    v = (V.repeat(2, 1).repeat(2, 2).astype(np.float32) - 128) * 255 / 224
    rgb = np.stack([y + 1.402 * v, y - 0.344136 * u - 0.714136 * v, y + 1.772 * u], -1)
    return np.rot90(np.clip(rgb, 0, 255).round().astype(np.uint8), 1, axes=(1, 2))


def rgb_a_yuv(R):
    """RGB de pantalla 320x240 -> planos BT.601 limitados del fotograma 240x320 (giro inverso)."""
    R = np.rot90(R, -1, axes=(1, 2)).astype(np.float32)
    r, g, b = R[..., 0], R[..., 1], R[..., 2]
    Y = 16 + (65.481 * r + 128.553 * g + 24.966 * b) / 255
    Cb = 128 + (-37.797 * r - 74.203 * g + 112.0 * b) / 255
    Cr = 128 + (112.0 * r - 93.786 * g - 18.214 * b) / 255
    sub = lambda c: c.reshape(len(c), H // 2, 2, W // 2, 2).mean((2, 4))
    q = lambda x: np.clip(x.round(), 0, 255).astype(np.uint8)
    return q(Y), q(sub(Cb)), q(sub(Cr))


# ------------------------------------------------------------------ banda
def banda_ok(Y, U, V, negro=NEGRO):
    """(ok, motivos, base). Todo lo no plano de la banda debe ser texto blanco o borde con el dibujo."""
    from scipy.ndimage import binary_dilation, maximum_filter1d
    n = len(Y)
    b = Y[:, :, :BANDA].astype(np.int16)
    base = np.median(b[:, :, :6].reshape(n, -1), axis=1).astype(np.int16)
    d = np.abs(b - base[:, None, None])
    motivos = []
    malos = np.where(np.abs(base - negro) > 3)[0]
    if len(malos):
        motivos.append(f'fondo no negro en {len(malos)} fotogramas (p. ej. {malos[:5].tolist()})')
    malos = np.where((d[:, :, :6] > 4).any(axis=(1, 2)))[0]
    if len(malos):
        motivos.append(f'columnas 0-5 no planas en {len(malos)} fotogramas (p. ej. {malos[:5].tolist()})')
    uv = np.maximum(np.abs(U[:, :, :BANDA // 2].astype(np.int16) - 128), np.abs(V[:, :, :BANDA // 2].astype(np.int16) - 128))
    malos = np.where(uv.max(axis=(1, 2)) > 4)[0]
    if len(malos):
        motivos.append(f'color en la banda en {len(malos)} fotogramas (p. ej. {malos[:5].tolist()})')
    fuerte = d > 60
    # tinta fuerte de los fotogramas vecinos (fundidos del texto), dilatada 3 px
    vecinos = maximum_filter1d(fuerte.view(np.uint8), size=31, axis=0).astype(bool)
    permitido = binary_dilation(vecinos, structure=np.ones((1, 7, 7), bool))
    # halo del códec (bloques de transformada): tenue y a <= 16 px de la tinta
    halo = binary_dilation(vecinos, structure=np.ones((1, 33, 33), bool))
    permitido |= halo & (d <= 20)
    permitido[:, :, 28:] |= d[:, :, 28:] <= 16
    fuera = (d > 4) & ~permitido
    # motas sueltas del códec: tolera hasta 4 píxeles tenues (|d| <= 8) por fotograma
    malos = np.where(((fuera & (d > 8)).sum(axis=(1, 2)) > 0) | (fuera.sum(axis=(1, 2)) > 4))[0]
    if len(malos):
        motivos.append(f'píxeles no planos fuera del texto en {len(malos)} fotogramas (p. ej. {malos[:5].tolist()}, '
                       f'máx {int(d[malos][fuera[malos]].max())})')
    return not motivos, motivos, base


def limpiar(Y, U, V, base=None):
    if base is None:
        base = np.full(len(Y), NEGRO)
    Y[:, :, :BANDA] = np.asarray(base, np.uint8)[:, None, None]
    U[:, :, :BANDA // 2] = 128
    V[:, :, :BANDA // 2] = 128


# ------------------------------------------------------------------ codificación y control
def codificar(Y, U, V, salida: Path, qp: int, fps=24):
    salida.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(suffix='.yuv')
    os.close(fd)
    tmp = salida.with_suffix('.tmp.moflex')
    try:
        with open(raw, 'wb') as f:
            for i in range(len(Y)):
                f.write(Y[i].tobytes()); f.write(U[i].tobytes()); f.write(V[i].tobytes())
        subprocess.run([str(MOBIPEG), '-y', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo',
                        '-pix_fmt', 'yuv420p', '-s:v', f'{W}x{H}', '-r', str(fps), '-i', raw, '-an',
                        '-c:v', 'mobiclip', '-mobiclip', '1', '-moflex', '1', '-qp', str(qp),
                        '-pix_fmt', 'yuv420p', '-threads', '1', '-x264opts', 'mvrange=32', '-f', 'moflex',
                        str(tmp)], check=True)
        set_moflex_rotation(tmp, 1)
        os.replace(tmp, salida)
    finally:
        os.unlink(raw)
        if tmp.exists():
            tmp.unlink()


def layouts(ruta: Path):
    from ie123kit.nucleo.media.moflex import disposicion_rotacion
    return sorted(set(disposicion_rotacion(ruta)))


def psnr(a, b):
    mse = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return round(float(10 * np.log10(255 ** 2 / mse)), 2) if mse else 99.0


def controlar(salida: Path, Y, n_esperados):
    info = C.ffprobe_video(salida)
    Yo, Uo, Vo = leer_yuv(salida)       # descodificación completa
    r = dict(bytes=salida.stat().st_size, fotogramas=len(Yo), fps=info['fps'],
             tam=f"{info['ancho']}x{info['alto']}", layout=[hex(x) for x in layouts(salida)],
             psnr_imagen=psnr(Y[:, :, 36:], Yo[:, :, 36:]), psnr_total=psnr(Y, Yo),
             banda_max_desvio=int(np.abs(Yo[:, :, :BANDA - 4].astype(int) - NEGRO).max()))
    errores = []
    if len(Yo) != n_esperados or info['fotogramas'] != n_esperados:
        errores.append(f'fotogramas {len(Yo)} != {n_esperados}')
    if info['fps'] != 24 or (info['ancho'], info['alto']) != (W, H):
        errores.append('fps o tamaño distintos')
    if r['layout'] != ['0x16']:
        errores.append(f"layout {r['layout']}")
    if r['banda_max_desvio'] > 3:
        errores.append(f"banda recodificada no plana ({r['banda_max_desvio']})")
    return r, errores


# ------------------------------------------------------------------ fuentes especiales
def fuente_a2m14():
    Yn, Un, Vn = leer_yuv(C.MODS / 'a2m14.mods', 256, 192)
    Y, U, V = rgb_a_yuv(nds_a_rgb(Yn, Un, Vn))
    return Y, U, V


def op00_mapa(nt):
    """Fotograma 3DS (float) para el instante NDS t (s); None en el tramo del logotipo."""
    out = []
    for k in range(nt):
        t = k / 24
        if t < 24.0:
            out.append(t * 24 - 2)
        elif t < 28.0:
            out.append(None)
        elif t < 57.7:
            out.append(t * 24 - 8)
        else:
            out.append(t * 24 - 7)
    return out


def fuente_op00(Yj, Uj, Vj):
    """Base 3DS en la línea de tiempo NDS; logotipo español compuesto donde difiere del fondo 3DS."""
    import cv2
    from scipy.ndimage import binary_dilation, gaussian_filter
    J = yuv_a_rgb(Yj, Uj, Vj)
    Yn, Un, Vn = leer_yuv(C.MODS / 'sp/op00.mods', 256, 192)
    N = nds_a_rgb(Yn, Un, Vn)
    total = len(Yj)
    mapa = op00_mapa(total)
    # corrección de color NDS -> 3DS (ajuste lineal por canal en tramos registrados, sin banda)
    pares = [(k, int(round(m))) for k, m in enumerate(mapa) if m is not None and 0 <= round(m) < total][::7]
    a = np.stack([N[min(len(N) - 1, int(k * 20 / 24))][24:200] for k, _ in pares]).reshape(-1, 3).astype(np.float64)
    b = np.stack([J[j][24:200] for _, j in pares]).reshape(-1, 3).astype(np.float64)
    ganancia = [np.polyfit(a[::97, c], b[::97, c], 1) for c in range(3)]
    def color(x):
        return np.clip(np.stack([np.polyval(ganancia[c], x[..., c].astype(np.float32)) for c in range(3)], -1), 0, 255)
    salida = np.empty_like(J)
    inicio, fin = 24 * 24, 28 * 24                   # fotogramas de salida del logotipo
    j0, j1 = inicio - 2, fin - 8                      # fondo 3DS: 574 -> 664
    for k in range(total):
        m = mapa[k]
        if m is not None:
            salida[k] = J[int(np.clip(round(m), 0, total - 1))]
            continue
        nds = color(N[min(len(N) - 1, int(k * 20 / 24))])
        nds = cv2.filter2D(nds.astype(np.float32), -1, np.array([[0, -.25, 0], [-.25, 2, -.25], [0, -.25, 0]], np.float32))
        j = int(round(j0 + (k - inicio) * (j1 - j0) / (fin - inicio)))
        fondo = J[j].astype(np.float32)
        dif = np.abs(gaussian_filter(nds, (1.5, 1.5, 0)) - gaussian_filter(fondo, (1.5, 1.5, 0))).max(-1) > 28
        masc = binary_dilation(dif, iterations=6).astype(np.float32)
        masc = gaussian_filter(masc, 2.5)[..., None]
        salida[k] = np.clip(nds * masc + fondo * (1 - masc), 0, 255).round()
    Y, U, V = rgb_a_yuv(salida)
    # fuera del logotipo se conservan los planos 3DS exactos (sin pasar por RGB)
    for k, m in enumerate(mapa):
        if m is not None:
            j = int(np.clip(round(m), 0, total - 1))
            Y[k], U[k], V[k] = Yj[j], Uj[j], Vj[j]
    return Y, U, V, dict(logotipo_fotogramas=[inicio, fin - 1], fondo_3ds=[j0, j1],
                         desfase_3ds=dict(antes=-2, de_28_a_57_7_s=-8, desde_57_7_s=-7),
                         ganancia_color=[[round(float(x), 4) for x in g] for g in ganancia])


def fuente_rotulos(n, Yj, Uj, Vj):
    """Rótulos del dibujo en español (rotulos.TRAMOS); fuera de los tramos, planos 3DS exactos."""
    import rotulos
    J = yuv_a_rgb(Yj, Uj, Vj)
    ruta = C.MODS / 'sp' / f'{n}.mods'
    if not ruta.exists():
        ruta = C.MODS / f'{n}.mods'
    N = nds_a_rgb(*leer_yuv(ruta, 256, 192))
    S, info = rotulos.componer(n, J, N)
    Y, U, V = Yj.copy(), Uj.copy(), Vj.copy()
    ks = sorted({k for _, kw in rotulos.TRAMOS[n] for k in range(kw['k0'], kw['k1'])})
    Yc, Uc, Vc = rgb_a_yuv(S[ks])
    Y[ks], U[ks], V[ks] = Yc, Uc, Vc
    return Y, U, V, dict(nds=ruta.relative_to(C.NDS).as_posix(), fotogramas_compuestos=len(ks),
                         tramos=info)


# ------------------------------------------------------------------ una cinemática
def procesar(n: str) -> dict:
    tmp = C.Temporal()
    try:
        Yj, Uj, Vj = leer_yuv(tmp.moflex(n + '.moflex'))
    finally:
        tmp.cerrar()
    r = dict(nombre=n, fuego=n == 'op00', qp=QP.get(n, QP_DEFECTO), fotogramas_jp=len(Yj),
             bytes_jp=len(C.archivo_jp().get(C.RUTA_MOVIE + n + '.moflex')))
    ok, motivos, base = banda_ok(Yj, Uj, Vj)
    r['banda_ok'], r['banda_motivos'] = ok, motivos
    if n == 'a2m14':
        Y, U, V = fuente_a2m14()
        okn, mot, _ = banda_ok(Y, U, V, negro=16)
        r['fuente'] = 'NDS ES movie/a2m14.mods (otro montaje)'
        r['banda_nds_ok'], r['banda_nds_motivos'] = okn, mot
        ok = okn
        limpiar(Y, U, V)
    elif n == 'op00':
        if ok:
            limpiar(Yj, Uj, Vj, base)
        Y, U, V, extra = fuente_op00(Yj, Uj, Vj)
        limpiar(Y, U, V)
        r['fuente'] = 'MOFLEX 3DS en la línea de tiempo NDS + logotipo NDS ES'
        r['op00'] = extra
    elif n in ROTULOS:
        if ok:
            limpiar(Yj, Uj, Vj, base)
        Y, U, V, extra = fuente_rotulos(n, Yj, Uj, Vj)
        limpiar(Y, U, V, base if ok else None)
        r['fuente'] = 'MOFLEX 3DS + rótulos del dibujo del NDS ES'
        r['rotulos'] = extra
    else:
        Y, U, V = Yj, Uj, Vj
        r['fuente'] = 'MOFLEX 3DS'
        if ok:
            limpiar(Y, U, V, base)
    sal = destino(n)
    if not ok:
        r['marcado'] = True
        if sal.exists():
            sal.unlink()
        return r
    codificar(Y, U, V, sal, r['qp'])
    ctl, errores = controlar(sal, Y, len(Y))
    r.update(ctl)
    r['errores'] = errores
    r['ruta'] = str(sal.relative_to(C.ROOT)).replace('\\', '/')
    r['sha256'] = C.sha(sal.read_bytes())
    print(n, r['bytes_jp'], '->', r['bytes'], r['psnr_imagen'], errores, flush=True)
    return r


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    tiempos = json.loads((C.SALIDA / 'tiempos.json').read_text(encoding='utf-8'))
    todos = [p['pista'][:-4] for p in tiempos['pistas']]
    nombres = sys.argv[1:] or todos
    previo = {}
    if INFORME.exists():
        previo = {v['nombre']: v for v in json.loads(INFORME.read_text(encoding='utf-8'))['videos']}
    with ProcessPoolExecutor(max_workers=6) as ex:
        for r in ex.map(procesar, nombres):
            previo[r['nombre']] = r
    videos = [previo[n] for n in todos if n in previo]
    hechos = [v for v in videos if not v.get('marcado')]
    resumen = dict(videos=len(videos), instalados=len(hechos),
                   marcados=[v['nombre'] for v in videos if v.get('marcado')],
                   con_errores=[v['nombre'] for v in videos if v.get('errores')],
                   bytes_jp=sum(v['bytes_jp'] for v in hechos), bytes=sum(v['bytes'] for v in hechos),
                   psnr_imagen_min=min((v['psnr_imagen'] for v in hechos), default=None))
    resumen['crecimiento_bytes'] = resumen['bytes'] - resumen['bytes_jp']
    INFORME.write_text(json.dumps(dict(resumen=resumen, videos=videos), ensure_ascii=False, indent=1),
                       encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False))


if __name__ == '__main__':
    main()
