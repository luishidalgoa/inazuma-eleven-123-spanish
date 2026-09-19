"""IE2 v07 · media (issue #74): utilidades comunes (voces SAD, subtítulos movie/txt/*.dat, tipografía).

Todo lo que se afirma aquí está comprobado en esta tanda (detalle y pruebas en informe.json):

Subtítulos 3DS (ina_main2.cro)
- 0x8f44 carga `/data_iz/movie/txt/%s.dat` entero (global seg2+0x6e0: +0x18 búfer, +0x1c registro siguiente).
- 0xe84bc, cada fotograma: tick = ms_reproducidos * 30 / 1000 (0x10624dd3 = /1000). Unidad = **ticks de
  30 Hz del tiempo de reproducción**, igual que la NDS. Dibuja cuando tick >= inicio; borra la franja
  (0, 160, 256, 32) y pasa al siguiente cuando tick >= fin.
- Registro: inicio u32, fin u32, tamaño u32 (múltiplo de 4: el lector avanza `tamaño & ~3`), texto con NUL y
  relleno; 0xFFFFFFFF al final. Es el mismo formato que la NDS (32 de 35 ficheros tienen tiempos idénticos
  a los japoneses).
- Dibujo: 0x1208e8 (util.cpp) separa el rubí ([kanji/lectura]) con 0x3cc44 y pinta la base con el gestor
  seg2+0xcc = FONT12 (seg2+0xa0 +0x24..0x30 = FONT8, RUBI8, FONT12, FONT12T; tipo 0) y el rubí con
  seg2+0xc8 = RUBI8. Lienzo DS 256x192, base en y = 0xa4 + 8.
- 0x3cc44 copia '\n' y solo caracteres de 2 bytes: **descarta todo byte suelto 0x20-0x7E** (espacio
  incluido) y usa '[', '/', ']' como marcas de rubí. Texto válido = Shift-JIS de 2 B (ancho completo).
- El gestor (vtable seg1+0x1721c, +8 = 0x33408) pinta carácter a carácter con
  cGameTextSystem::DrawTextHintOnVram(FONT_TYPE 0) -> **FONT12.bcfnt compartida** (la NFTR no pinta).
  Avance en unidades DS: FontGetCharWidth (12) sustituido por g_ItxInazuma123[+8/+0xc/+0x38] = 10/11/11
  (code.bin 0x264094); por defecto 11. Posición 3DS = trunc(x_DS * DSPosXTo3DSPosX_tbl[i]) con
  tbl = {1.5625, 1.25}; por defecto i = 1 -> paso 13,75 px. Ancho 256: si x + avance > 256 salta de línea
  (0x106a5c) y la 2.ª línea queda fuera del lienzo (y 172 + alto > 192).
- Consecuencia: una línea, <= 21 casillas (21 x 12 = 252, peor caso); FONT12.bcfnt es fuente parcheada
  (acentos v20 + bigramas v89/v90) -> mismas reglas de bigramas, comprobando huecos al paso real.

Voces
- 3DS: romfs/inazuma2/data_iz/sound/*.SAD (LayeredFS, fuera de archive.fa); NDS ES: sound/sp/*.SAD.
  Mismo formato SADL (frecuencia en cabecera: ES 32728 Hz, JP 16364 Hz). Se copian enteros.
- Propios de Fuego (data_iz_blizzard trae los suyos o sus cinemáticas a2y difieren): OP00, BG_END, A2Y01-03.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
W = ROOT / 'work'
for p in (W / 'ie2/shared/capas/historial/nombres/v03_textos', ROOT / 'tools/src', ROOT / 'tools'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import comun_v03 as K  # noqa: E402

M = K.M
A88, A89, R = K.A88, K.A89, K.R
F12 = K.F12

# ------------------------------------------------------------------ rutas
BASE_JP = W / 'shared/base_3ds/romfs/archive.fa'
SONIDO_JP = W / 'shared/base_3ds/romfs/inazuma2/data_iz/sound'
NDS = W / 'ie2/tormenta_de_fuego/fuentes/nds_es/data_iz'
SONIDO_ES = NDS / 'sound/sp'
TXT_ES = NDS / 'movie/txt/sp'
MODS = NDS / 'movie'
# Base con las BCFNT actuales (fuentes v90: mismos dibujos que v89 en los códigos de v89).
BASE_ACTUAL = W / 'shared/candidatas/probe_ie2_v05/archive.fa'
# Base con las BCFNT exactas del registro v89 (la que usa también la capa v90 de IE1).
BASE_V89 = W / 'shared/candidatas/probe_ie1_v89/archive.fa'
VGM = W / 'shared/herramientas/media_tools/vgmstream-nightly-win64/vgmstream-cli.exe'

SALIDA = HERE                                             # común a Fuego y Ventisca
SALIDA_FUEGO = W / 'ie2/tormenta_de_fuego/capas/media/media'  # solo Fuego
ROMFS_SONIDO = Path('romfs_mod/inazuma2/data_iz/sound')
EXTRA_TXT = Path('extra/inazuma2/data_iz/movie/txt')
RUTA_TXT = 'inazuma2/data_iz/movie/txt/'
RUTA_MOVIE = 'inazuma2/data_iz/movie/'

SOLO_FUEGO_SAD = {'OP00.SAD', 'BG_END.SAD', 'A2Y01.SAD', 'A2Y02.SAD', 'A2Y03.SAD'}
SOLO_FUEGO_TXT = {'op00.dat'}   # la ventisca usa el mismo txt con su propio vídeo: revisar en su fase

TICKS = 30                      # ticks por segundo de movie/txt/*.dat
MAX_CELDAS = 21                 # 256 px DS / 12 (peor avance)
AVANCE_DS = 11                  # g_ItxInazuma123[+0xc] (modo por defecto)
ESCALA = 1.25                   # DSPosXTo3DSPosX_tbl[1]
PASOS_REVISADOS = ((10, 1.25), (11, 1.25), (12, 1.25), (11, 1.5625))
DURACION_MIN = 12               # ticks (0,4 s) por trozo al partir un subtítulo


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ .dat
@dataclass
class Sub:
    inicio: int
    fin: int
    cuerpo: bytes          # sin NUL


def leer_dat(datos: bytes) -> list[Sub]:
    out, pos = [], 0
    while True:
        if pos + 4 > len(datos):
            raise ValueError('falta el terminador')
        ini = struct.unpack_from('<I', datos, pos)[0]
        if ini == 0xFFFFFFFF:
            if pos + 4 != len(datos):
                raise ValueError('datos tras el terminador')
            return out
        fin, tam = struct.unpack_from('<II', datos, pos + 4)
        if tam == 0 or tam % 4 or pos + 12 + tam > len(datos) or fin < ini:
            raise ValueError(f'registro inválido en 0x{pos:x}')
        carga = datos[pos + 12:pos + 12 + tam]
        if b'\0' not in carga:
            raise ValueError(f'registro sin NUL en 0x{pos:x}')
        out.append(Sub(ini, fin, carga.split(b'\0', 1)[0]))
        pos += 12 + tam


def escribir_dat(subs: list[Sub]) -> bytes:
    out = bytearray()
    for s in subs:
        carga = s.cuerpo + b'\0'
        carga += b'\0' * (-len(carga) % 4)
        out += struct.pack('<III', s.inicio, s.fin, len(carga)) + carga
    out += b'\xff\xff\xff\xff'
    return bytes(out)


def dat_jp(nombre: str) -> bytes:
    return archivo_jp().get(RUTA_TXT + nombre)


@lru_cache(maxsize=1)
def archivo_jp():
    return M.Archivo(BASE_JP)


# ------------------------------------------------------------------ vídeo y audio
def ffprobe_video(ruta: Path) -> dict:
    r = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_frames',
                        '-of', 'json', str(ruta)], capture_output=True, text=True, check=True)
    st = json.loads(r.stdout)['streams'][0]
    num, den = map(int, st['r_frame_rate'].split('/'))
    n = int(st['nb_read_frames'])
    return dict(codec=st['codec_name'], ancho=st['width'], alto=st['height'], fps=num / den,
                fotogramas=n, segundos=round(n * den / num, 3))


class Temporal:
    """Carpeta temporal (fuera de work/) para vídeos extraídos y WAV descodificados."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix='ie2_v07_media_'))

    def moflex(self, nombre: str) -> Path:
        p = self.dir / nombre
        if not p.exists():
            p.write_bytes(archivo_jp().get(RUTA_MOVIE + nombre))
        return p

    def wav(self, sad: Path, etiqueta: str) -> Path:
        p = self.dir / f'{etiqueta}_{sad.stem}.wav'
        if not p.exists():
            subprocess.run([str(VGM), '-o', str(p), str(sad)], capture_output=True, check=True)
        return p

    def cerrar(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def info_sad(ruta: Path) -> dict:
    r = subprocess.run([str(VGM), '-m', str(ruta)], capture_output=True, text=True)
    txt = r.stdout
    if r.returncode != 0 or 'sample rate' not in txt:
        raise RuntimeError(f'vgmstream no reconoce {ruta}: {r.stderr.strip()[:200]}')
    hz = int(re.search(r'sample rate: (\d+)', txt).group(1))
    ch = int(re.search(r'channels: (\d+)', txt).group(1))
    n = int(re.search(r'stream total samples: (\d+)', txt).group(1))
    return dict(hz=hz, canales=ch, muestras=n, segundos=round(n / hz, 3))


def envolvente(wav: Path, hz_obj: int = 16364, ventana_s: float = 1 / TICKS):
    """Señal mono remuestreada a hz_obj (float32) y su RMS por tick."""
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    hz, x = wavfile.read(wav)
    x = x.astype(np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    x /= 32768.0
    if hz != hz_obj:
        from math import gcd
        g = gcd(hz, hz_obj)
        x = resample_poly(x, hz_obj // g, hz // g).astype(np.float32)
    return x


def rms_ticks(x, hz: int = 16364):
    import numpy as np
    paso = hz / TICKS
    n = int(len(x) / paso)
    return np.array([float(np.sqrt(np.mean(x[int(i * paso):int((i + 1) * paso)] ** 2) + 1e-12)) for i in range(n)])


# ------------------------------------------------------------------ tipografía
CP_BCFNT = {'−': 0xFF0D, '〜': 0xFF5E}   # la BCFNT indexa 0x817C y 0x8160 con estos códigos
REG90 = W / 'ie1/capas/historial/menus_cro/v90_cro_restantes/registro.json'
REG_CAPA = HERE / 'registro.json'                      # v90 + códigos de subtítulos (esta capa)
FUENTE_CAPA = HERE / 'extra' / F12                      # FONT12.bcfnt = v90 + dibujos de subtítulos
ESC88 = W / 'ie1/capas/historial/fuentes/v88_bigramas_total/escaneo_base_v87.json'
LIT89 = W / 'ie1/capas/fuentes/bigramas_ritmo/literales.json'
LIT90 = W / 'ie1/capas/historial/menus_cro/v90_cro_restantes/escaneo_literales_v90.json'
GRAFICOS_V90 = re.compile(r'/(pic3d|pic2d|a_field|model|effect3d|face2d|spr|map2d|map3d)/|\.(arc|lzs|pac_)$'
                          r'|(^|/)code\.bin$|\.cr[os]$')
SUB = ''                                          # prefijo de las claves de subtítulo: SUB + D + SUB + texto
PREFIJOS = ('', '', '')               # R.IZQ, R.DER, v90 PROP
G_IN = 2            # px sólidos entre letras dentro de una casilla nueva
ESP = 6             # px sólidos de un espacio dentro de una casilla nueva
CENTRO = 7          # centro de la caja virtual de una casilla nueva (columna respecto al lápiz)
PEN_NUEVO = 0.8     # 1.ª pasada (sondeo de utilidad)
MAX_NUEVOS = 200    # tope de códigos nuevos (el depósito v90 tiene 228; se dejan libres para otras capas)
HOLGURA = 1         # columnas de ajuste alrededor de la centrada
COSTE_CASILLA = 0.35
INF = float('inf')


def coste_hueco(g, palabra):
    """Objetivo a paso real: dentro de palabra 2-3 px; entre palabras 5-7 px."""
    if palabra:
        if g < 4:
            return INF
        return {4: 0.8, 5: 0.2, 6: 0.0, 7: 0.0, 8: 0.3, 9: 1.0}.get(g, 1.0 + 0.8 * (g - 9))
    if g < 1:
        return INF
    return {1: 0.3, 2: 0.0, 3: 0.1, 4: 1.6, 5: 4.0}.get(g, 4.0 + 2.5 * (g - 5))


def coste_par(g_lo, palabra):
    """El paso es 13 o 14 px según la fase: el hueco vale g_lo o g_lo + 1 y ambos cuentan."""
    a, b = coste_hueco(g_lo, palabra), coste_hueco(g_lo + 1, palabra)
    return INF if INF in (a, b) else (a + b) / 2


def clave_sub(t, d):
    return f'{SUB}{d}{SUB}{t}'


def columna(t, ancho_solido):
    """Columna D de la tinta: la caja virtual (espacio de borde = ESP - G_IN px) queda centrada en CENTRO.
    Con cajas de ~11 px el hueco entre casillas vale 13 + 1 - 11 - 1 = 2 (o 3 con paso 14) y un espacio
    de borde lo agranda en ESP - G_IN px."""
    lead = ESP - G_IN if t.startswith(' ') else 0
    trail = ESP - G_IN if t.endswith(' ') else 0
    caja = lead + ancho_solido + trail
    return CENTRO - (caja + 1) // 2 + lead


class Tipo:
    """Maqueta de los subtítulos a su paso real (v07b, sustituye a la de v89 a 15 px).

    Paso: 11 u. DS x 1,25 = 13,75 px -> 13 o 14 px entre casillas según la fase del centrado
    (x = trunc((x_linea + k*11) * 1,25)); cada hueco se mide con los dos. Ritmo v89 (ritmo.py): casillas de
    1-4 caracteres y partición por programación dinámica del coste de huecos, con objetivos retocados para
    este paso (coste_hueco). Casillas: letras nativas, los 876 códigos del registro v90 (medidos en la
    FONT12.bcfnt de la base) y casillas NUEVAS dibujadas para este paso (letras a G_IN px, espacio interior
    ESP px, tinta desde la columna D respecto al lápiz). Los códigos nuevos salen del mismo depósito que v90
    (escaneo v88 + literales v89/v90, sin aparición textual, no usados por el registro) y se añaden al final
    del registro (registro.json de esta capa). Solo se dibujan en FONT12 (los subtítulos solo usan FONT12)."""

    def __init__(self, capa=False):
        get = K.comun88.abrir(BASE_ACTUAL)
        self.base_bytes = get(F12)
        reg = json.loads(REG90.read_text(encoding='utf-8'))
        assert reg['fuentes_dibujadas'][F12] == sha(self.base_bytes), 'la base actual no lleva la FONT12 de v90'
        datos = self.base_bytes
        if capa:
            reg = json.loads(REG_CAPA.read_text(encoding='utf-8'))
            datos = FUENTE_CAPA.read_bytes()
            assert reg['fuentes_dibujadas'][F12] == sha(datos), 'FONT12 de la capa distinta de su registro'
        self.reg = reg
        self.tmp = Path(tempfile.mkdtemp(prefix='ie2_v07_f12_'))
        (self.tmp / 'FONT12.bcfnt').write_bytes(datos)
        self.F = A88.cargar(self.tmp / 'FONT12.bcfnt')
        self.sha_actual = sha(datos)
        self.codigo, self.cp_de, self.por_texto = {}, {}, {}
        for e in reg['bigramas']:
            self._indexar(e)
        from dialogue_typography import ACCENTS
        self.inv_acentos = {v: k for k, v in ACCENTS.items()}
        self.creados = {}            # clave nueva -> uso (aún sin código)
        self.permitidos = None       # 2.ª pasada: solo estas casillas nuevas
        self.nuevos_permitidos = not capa

    def _indexar(self, e):
        clave = A89.clave_de(e)
        self.codigo[clave] = bytes.fromhex(e['sjis'])
        self.cp_de[clave] = int(e['unicode'][2:], 16)
        self.por_texto.setdefault(self.txt(clave), []).append(clave)

    @property
    def inverso(self):
        return {v: self.txt(k) for k, v in self.codigo.items()}

    @staticmethod
    def txt(c):
        if c[:1] == SUB:
            return c.split(SUB, 2)[2]
        return c[1:] if c[:1] in PREFIJOS else c

    def cp(self, c: str):
        if c in self.cp_de:
            return self.cp_de[c]
        return CP_BCFNT.get(c) or A88.codepoint(c)

    # ------------------------------------------------------------------ geometría
    @lru_cache(None)
    def letra(self, ch):
        """(px, s0, s1) del glifo nativo (columnas del mapa de bits) o None."""
        try:
            gi = self.F.gi(self.cp(ch))
        except Exception:
            return None
        if gi is None:
            return None
        px = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
        sol = [x for (x, _), v in px.items() if v >= A88.SOLIDO[F12]]
        return (px, min(sol), max(sol)) if sol else None

    @lru_cache(None)
    def diseno(self, t):
        """Casilla nueva de texto t: (px con la tinta sólida desde x=0, ancho sólido) o None si no cabe."""
        if not t.strip(' ') or '  ' in t or len(t) > 4:
            return None
        px, fin, espacio = {}, None, False
        for ch in t.strip(' '):
            if ch == ' ':
                espacio = True
                continue
            L = self.letra(ch)
            if L is None:
                return None
            p, s0, s1 = L
            off = -s0 if fin is None else fin + 1 + (ESP if espacio else G_IN) - s0
            for (x, y), v in p.items():
                px[(x + off, y)] = max(v, px.get((x + off, y), 0))
            fin = off + s1
            espacio = False
        xs = [x for x, _ in px]
        if max(xs) - min(xs) + 1 > self.F.sx - 1:
            return None
        return px, fin + 1

    @lru_cache(None)
    def tinta(self, c: str):
        """{(x, y): alfa} relativa al lápiz."""
        if not self.txt(c).strip(' '):
            return {}
        if c[:1] == SUB and c not in self.codigo:
            d = int(c.split(SUB)[1])
            px, _ = self.diseno(self.txt(c))
            return {(x + d, y): v for (x, y), v in px.items()}
        gi = self.F.gi(self.cp(c))
        if gi is None:
            raise ValueError(f'sin glifo FONT12: {c!r}')
        left, _, adv = self.F.metrics[gi]
        x0 = int((A88.CELDA[F12] - adv) / 2) + left
        return {(x + x0, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}

    @lru_cache(None)
    def extremos(self, c):
        xs = [x for (x, _), v in self.tinta(c).items() if v >= A88.SOLIDO[F12]]
        return (min(xs), max(xs)) if xs else None

    # ------------------------------------------------------------------ partición
    def opciones(self, texto, i):
        out = []
        ch = texto[i]
        if ch == ' ' or self.letra(ch) is not None:
            out.append((1, ch, 0.0))
        for k in range(1, 5):
            t = texto[i:i + k]
            if len(t) < k:
                break
            for clave in self.por_texto.get(t, ()):
                if clave != ch:
                    out.append((k, clave, 0.0))
            dis = self.diseno(t) if self.nuevos_permitidos else None
            if dis is not None:
                d0 = columna(t, dis[1])
                for d in range(d0 - HOLGURA, d0 + HOLGURA + 1):
                    c = clave_sub(t, d)
                    if c in self.codigo:
                        continue
                    if self.permitidos is not None:
                        if c in self.permitidos:
                            out.append((k, c, 0.0))
                    else:
                        out.append((k, c, 0.0 if c in self.creados else PEN_NUEVO))
        return out

    def celdas(self, texto: str):
        n = len(texto)

        @lru_cache(None)
        def f(i, s1, m, esp):
            if i >= n:
                return 0.0, ()
            mejor = (INF, ())
            for k, c, pen in self.opciones(texto, i):
                t = self.txt(c)
                ext = self.extremos(c) if t.strip(' ') else None
                if ext is None:
                    sub = f(i + k, s1, m + 1, True) if s1 is not None else f(i + k, None, 0, True)
                    total = sub[0] + COSTE_CASILLA + pen
                else:
                    s0, e1 = ext
                    cst = 0.0
                    if s1 is not None:
                        cst = coste_par(int(13.75 * m) + s0 - s1 - 1, esp or t[0] == ' ')
                    if cst == INF:
                        continue
                    sub = f(i + k, e1, 1, t[-1] == ' ')
                    total = cst + sub[0] + COSTE_CASILLA + pen
                if total < mejor[0]:
                    mejor = (total, (c,) + sub[1])
            return mejor

        total, cel = f(0, None, 0, False)
        if total == INF:
            raise ValueError(f'sin partición: {texto!r}')
        return list(cel)

    def usar(self, cel):
        for c in cel:
            if c[:1] == SUB and c not in self.codigo:
                self.creados[c] = self.creados.get(c, 0) + 1

    def reiniciar(self, permitidos):
        self.creados = {}
        self.permitidos = set(permitidos)

    # ------------------------------------------------------------------ códigos y dibujo
    def _pool(self):
        esc = json.loads(ESC88.read_text(encoding='utf-8'))
        lit = json.loads(LIT89.read_text(encoding='utf-8'))
        lit.update(json.loads(LIT90.read_text(encoding='utf-8')))
        usados = {e['sjis'] for e in self.reg['bigramas']}
        inv = {}
        for cp_, gi in self.F.cmap.items():
            inv.setdefault(gi, []).append(cp_)
        limpios, graf = [], []
        for c, v in esc['codigos'].items():
            if c in usados or int(c, 16) < 0x889F or v.get('texto'):
                continue
            if c not in lit or lit[c] or not A89.unico(self.F, inv, c):
                continue
            if c in esc['limpios']:
                limpios.append((c, 'limpio_escaneo_v88'))
                continue
            rutas = [r for r, _ in esc['apariciones_textuales'].get(c, [])]
            if all(GRAFICOS_V90.search(r) for r in rutas):
                graf.append((len(rutas), sum(v.values()), c))
        return limpios + [(c, 'solo_graficos_v90') for _, _, c in sorted(graf)]

    def asignar_y_dibujar(self):
        """Da código a cada casilla nueva usada, la dibuja en FONT12 y la añade al registro."""
        escritor = A88.V75G.Celdas(self.F)
        libres = self._pool()
        if len(self.creados) > len(libres):
            raise RuntimeError(f'{len(self.creados)} casillas nuevas y solo {len(libres)} códigos libres')
        añadidos = []
        for c in sorted(self.creados):
            s, origen = libres.pop(0)
            ch = bytes.fromhex(s).decode('cp932')
            gi = self.F.gi(ord(ch))
            d = int(c.split(SUB)[1])
            t = self.txt(c)
            px, ancho_solido = self.diseno(t)
            f0 = min(x for x, _ in px)
            f1 = max(x for x, _ in px)
            pinta = {(x - f0, y): v for (x, y), v in px.items()}
            width = f1 - f0 + 1
            adv = width
            left = d + f0 - int((A88.CELDA[F12] - adv) / 2)
            assert -128 <= left <= 127 and 0 < adv <= 255
            viejo = list(self.F.metrics[gi])
            for y in range(self.F.sy):
                for x in range(self.F.sx):
                    escritor.escribir(gi, x, y, 0)
            for (x, y), v in pinta.items():
                assert 0 <= x < self.F.sx - 1 and 0 <= y < self.F.sy - 1, (c, x, y)
                escritor.escribir(gi, 1 + x, 1 + y, v)
            self.F.set_metrics(gi, left, width, adv)
            leido = {(x, y): v for y, row in enumerate(self.F.bitmap(gi)) for x, v in enumerate(row) if v}
            assert leido == pinta, c
            px_sha = hashlib.sha1(json.dumps(sorted(pinta.items())).encode()).hexdigest()
            e = dict(par=t, sjis=s, unicode=f'U+{ord(ch):04X}', kanji=ch, origen=origen, clave=c,
                     variante=f'subtitulo paso 13,75 (tinta sólida desde la columna {d})',
                     fuentes={F12: dict(glifo=gi, cwdh_antes=viejo, cwdh=[left, width, adv], tinta_px=width,
                                        columna=d, hueco_interno=G_IN, espacio_interno=ESP,
                                        pixeles_sha1=px_sha, maqueta='v07 subtítulos IE2 (paso 13,75)')},
                     glifo=gi, cwdh=[left, width, adv], tinta_px=width, D=d, pixeles_sha1=px_sha,
                     campos=['subtitulos_ie2'])
            self.reg['bigramas'].append(e)
            self._indexar(e)
            añadidos.append(c)
        self.tinta.cache_clear()
        self.extremos.cache_clear()
        for c in añadidos:        # la tinta leída de la fuente coincide con la del diseño
            d = int(c.split(SUB)[1])
            px, _ = self.diseno(self.txt(c))
            assert self.tinta(c) == {(x + d, y): v for (x, y), v in px.items()}, c
        datos = self.F.data()
        assert len(datos) == len(self.base_bytes)
        self.reg = dict(self.reg)
        self.reg['version'] = 'ie2_v07_media'
        self.reg['descripcion'] = (self.reg['descripcion'] + ' IE2 v07 (work/ie2/shared/capas/media/media): casillas '
                                   'de subtítulos de cinemática dibujadas para el paso 13,75 px, añadidas al final '
                                   '(clave con prefijo U+E003, campo subtitulos_ie2); solo FONT12.')
        self.reg['fuentes_dibujadas'] = dict(self.reg['fuentes_dibujadas'])
        self.reg['fuentes_dibujadas'][F12] = sha(datos)
        self.reg['pares_ie2_v07'] = añadidos
        return datos, añadidos

    # ------------------------------------------------------------------ medida y transporte
    def huecos(self, cel, avance=AVANCE_DS, escala=ESCALA, x_linea=0):
        """[(i, j, hueco sólido)] entre casillas con tinta consecutivas, con la fase dada."""
        out, prev = [], None
        for i, c in enumerate(cel):
            ext = self.extremos(c) if self.txt(c).strip(' ') else None
            if ext is None:
                continue
            base = int((x_linea + i * avance) * escala)
            if prev is not None:
                out.append((prev[0], i, base + ext[0] - prev[1] - 1))
            prev = (i, base + ext[1])
        return out

    def huecos_fases(self, cel, avance=AVANCE_DS, escala=ESCALA):
        return [g for xl in range(4) for _, _, g in self.huecos(cel, avance, escala, xl)]

    def codificar(self, cel) -> bytes:
        return b''.join(self.codigo[c] if c in self.codigo else A88.V79.codificar(c) for c in cel)

    def texto(self, cuerpo: bytes) -> str:
        inv = self.inverso
        out, i = [], 0
        while i < len(cuerpo):
            tok = cuerpo[i:i + 2]
            i += 2
            if tok in inv:
                out.append(inv[tok])
            else:
                ch = tok.decode('cp932')
                out.append(' ' if ch == '　' else self.inv_acentos.get(ch, unicodedata.normalize('NFKC', ch)))
        return ''.join(out)

    def sin_glifo(self, cuerpo: bytes):
        malos, i = [], 0
        while i < len(cuerpo):
            tok = cuerpo[i:i + 2]
            if len(tok) < 2 or tok[0] < 0x81:
                malos.append(tok[:1].hex())
                i += 1
                continue
            try:
                ch = tok.decode('cp932')
                cp = CP_BCFNT.get(ch) or ord(ch)
            except UnicodeDecodeError:
                cp = None
            if cp is None or self.F.gi(cp) is None:
                malos.append(tok.hex())
            i += 2
        return malos


# ------------------------------------------------------------------ texto español
PUNTO = re.compile(r'(?<=[.!?…])\s+')
COMA = re.compile(r'(?<=[,;:])\s+')


def es_nds(cuerpo: bytes) -> str:
    t = M.decode_nds(cuerpo)
    if t is None:
        raise ValueError(f'bytes NDS desconocidos: {cuerpo!r}')
    return t.strip()


def cortes(texto: str):
    """Puntos de corte candidatos (índice de inicio del 2.º trozo) por prioridad."""
    for pat in (PUNTO, COMA, re.compile(r'\s+')):
        idx = [(m.start(), m.end()) for m in pat.finditer(texto)]
        if idx:
            yield idx


def partir(T: Tipo, texto: str):
    """[(texto, casillas)] con <= MAX_CELDAS casillas cada uno, cortando por frases/comas/palabras."""
    cel = T.celdas(texto)
    if len(cel) <= MAX_CELDAS:
        return [(texto, cel)]
    mejor = None
    for grupo in cortes(texto):
        for a, b in grupo:
            izq, der = texto[:a].rstrip(), texto[b:].lstrip()
            if not izq or not der:
                continue
            try:
                ci, cd = T.celdas(izq), T.celdas(der)
            except ValueError:
                continue
            desequilibrio = abs(len(ci) - len(cd))
            cabe = len(ci) <= MAX_CELDAS and len(cd) <= MAX_CELDAS
            clave = (not cabe, desequilibrio)
            if mejor is None or clave < mejor[0]:
                mejor = (clave, izq, der)
        if mejor is not None and not mejor[0][0]:
            break
    if mejor is None:
        # Sin espacios (gritos): corte dentro de la palabra, lo más cerca posible de la mitad.
        for d in range(0, len(texto) // 2):
            for a in (len(texto) // 2 - d, len(texto) // 2 + d):
                if 0 < a < len(texto):
                    try:
                        if len(T.celdas(texto[:a])) <= MAX_CELDAS and len(T.celdas(texto[a:])) <= MAX_CELDAS:
                            mejor = ((False, 0), texto[:a], texto[a:])
                            break
                    except ValueError:
                        continue
            if mejor:
                break
    if mejor is None:
        raise ValueError(f'no se puede partir: {texto!r}')
    _, izq, der = mejor
    return partir(T, izq) + partir(T, der)


def repartir(inicio: int, fin: int, trozos):
    """Intervalos [ini, fin) contiguos proporcionales a la longitud de cada trozo."""
    pesos = [max(1, len(t)) for t, _ in trozos]
    total, acum, out = sum(pesos), 0, []
    ini = inicio
    for k, p in enumerate(pesos):
        acum += p
        f = fin if k == len(pesos) - 1 else inicio + round((fin - inicio) * acum / total)
        out.append((ini, f))
        ini = f
    return out
