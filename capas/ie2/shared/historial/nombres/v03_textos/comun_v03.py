"""IE2 v03 · utilidades comunes del volcado de texto (issues #70, #71, #72).

- Lectura: `Archivo` de la capa v02 (work/ie2/tormenta_de_fuego/capas/dialogo/dialogo/comun_ie2.py) y
  `abrir` (mmap) de IE1 v88.
- Transporte: `transportar` = dialogue_typography.encode_fullwidth (ancho completo cp932 + portadores).
- Bigramas: SOLO los códigos del registro de IE1 v89 (work/ie1/capas/fuentes/bigramas_ritmo/registro.json).
  Las fuentes BCFNT son compartidas por toda la recopilación y la base probe_ie2_v02 ya lleva los dibujos
  de v89 (se comprueba el sha256). No se añaden pares nuevos.
  Campos y fuentes (mismas reglas que v88/v89 en IE1; límites de ina_main2.cro en
  work/ie2/shared/capas/historial/menus_cro/v01_limites_cro/informe.json):
    nombre       unitbase.dat +0/+16: pares de 2 letras dibujados en FONT12 + FONT8 + FONT12T, sin solape
                 en FONT8 (paso 10) ni FONT12T (paso 15). Máx. 7 casillas (15 B + NUL).
    rotulo       eve 0x4037 arg 3: pares dibujados en FONT8 (y FONT12), sin solape en FONT8. Máx. 10 casillas
                 con los espacios de centrado de v81 (placa 165 px, paso 15).
    objetivo     eve 0x2017/0x2018/0x201c/0x2023 arg 3 y 0x402f arg 2 (FONT12): trozos de v89 (ritmo.py).
    descripcion  unitbase.STR (FONT12): trozos de v89.
Uso como módulo.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
V02 = ROOT / 'work/ie2/tormenta_de_fuego/capas/dialogo/dialogo'
for p in (V02, ROOT / 'work/ie1/capas/historial/fuentes/v88_bigramas_total', ROOT / 'tools/src', ROOT / 'tools'):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import comun_ie2 as M  # noqa: E402
import comun88  # noqa: E402

A89 = comun88.modulo('v89_bigramas_ritmo', ROOT / 'work/ie1/capas/fuentes/bigramas_ritmo/apply.py')
A88 = A89.A88
R = A89.R
F12, F8, F12T = A88.F12, A88.F8, A88.F12T
FUENTES = (F12, F8, F12T)
REGISTRO = ROOT / 'work/ie1/capas/fuentes/bigramas_ritmo/registro.json'
BASE_V02 = ROOT / 'work/shared/candidatas/probe_ie2_v02/archive.fa'
JP = M.JP
LOGIC = 'inazuma2/data_iz/logic'
NDS = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es/data_iz'
NDS_BIN = ROOT / 'work/ie2/tormenta_de_fuego/fuentes/nds_es/bin'
GLOSARIO = ROOT / 'translation/shared/glossary'

ESPACIO = '　'.encode('cp932')
LIMITE = {'nombre': 7, 'rotulo': 10}
PLACA, PASO_ROTULO = 165, 15

abrir = comun88.abrir
transportar = M.transportar
normalizar = M.normalizar


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def dec_nds(b: bytes) -> str:
    """Texto NDS (latín del DS + Shift-JIS incrustado) hasta el primer NUL; None si hay bytes desconocidos."""
    return M.decode_nds(b.split(b'\0')[0])


@lru_cache(maxsize=1)
def base():
    return abrir(BASE_V02)


class Bigramas:
    """Codec de casillas con el registro v89 y las fuentes de probe_ie2_v02 (solo lectura)."""

    def __init__(self):
        reg = json.loads(REGISTRO.read_text(encoding='utf-8'))
        get = base()
        self.tmp = Path(tempfile.mkdtemp(prefix='ie2_v03_'))
        self.F = {}
        for f in FUENTES:
            datos = get(f)
            assert sha(datos) == reg['fuentes_dibujadas'][f], f'{f} no es la de v89'
            (self.tmp / Path(f).name).write_bytes(datos)
            self.F[f] = A88.cargar(self.tmp / Path(f).name)
        self.reg = reg['bigramas']
        self.codec = A89.Codec(self.reg)
        self.mq = A89.Maqueta(self.F[F12], A88.codepoint)
        for e in self.reg:
            self.mq.fijos[A89.clave_de(e)] = A89.medir(self.F[F12], self.F[F12].gi(int(e['unicode'][2:], 16)))
        self.pares = A88.Pares(self.F)
        self.dib = A88.Dibujo(self.F, self.pares, None)
        claves = {A89.clave_de(e): e for e in self.reg}
        self.claves = {
            'nombre': {c for c, e in claves.items() if len(c) == 2 and not R.variante(c)
                       and F8 in e['fuentes'] and F12T in e['fuentes']},
            'rotulo': {c for c, e in claves.items() if F8 in e['fuentes'] and not R.variante(c)},
            'objetivo': set(claves),
            'descripcion': set(claves),
        }

    # ------------------------------------------------------------------ partición
    def _fallos(self, cel, pasos):
        malos = set()
        for f, paso in pasos:
            col = self.dib.colocar(f, cel, paso)
            for i, g in self.dib.huecos(col, A88.SOLIDO[f]):
                if g < A88.HUECO_MIN[f]:
                    malos |= {c for c in (cel[i], cel[i + 1]) if len(c) >= 2}
        return malos

    @lru_cache(None)
    def celdas(self, texto: str, campo: str):
        """Casillas de un texto plano (sin saltos ni %). Lanza ValueError si una letra no tiene glifo."""
        for ch in texto:
            if ch != ' ' and self.mq.nativa(ch) is None:
                raise ValueError(f'sin glifo FONT12: {ch!r} en {texto!r}')
        permit = self.claves[campo]
        if campo in ('nombre', 'rotulo'):
            pasos = [(F8, 10), (F12T, 15)] if campo == 'nombre' else [(F8, 10)]
            prohib = set()
            while True:
                if campo == 'nombre':
                    def ok(c, prohib=frozenset(prohib)):
                        return c in permit and c not in prohib
                    coste, cel = R.particion(texto, self.mq, ok, largo_max=2)
                    cel = list(cel)
                else:
                    cel = A88.particion(texto, self.pares, (F12, F8), permit, frozenset(prohib))
                malos = self._fallos(cel, pasos)
                if not malos:
                    return tuple(cel)
                prohib |= malos
        coste, cel = R.particion(texto, self.mq, lambda c: c in permit)
        if coste == R.INF:
            raise ValueError(f'sin partición: {texto!r}')
        return tuple(cel)

    def codificar_celdas(self, cel) -> bytes:
        return self.codec.codificar(list(cel))

    def texto(self, body: bytes) -> str:
        return self.codec.texto(body)

    # ------------------------------------------------------------------ campos
    def nombre(self, texto: str) -> bytes:
        """Cuerpo de un nombre (sin NUL). ValueError si pasa de 7 casillas / 15 B."""
        cel = self.celdas(texto, 'nombre')
        b = self.codificar_celdas(cel)
        if len(cel) > LIMITE['nombre'] or len(b) > 15:
            raise ValueError(f'nombre de {len(cel)} casillas: {texto!r} {"|".join(cel)}')
        return b

    def rotulo(self, texto: str) -> bytes:
        """Rótulo centrado (v81) en <= 10 casillas. ValueError si no cabe."""
        cel = self.celdas(texto, 'rotulo')
        n = len(cel)
        if n > LIMITE['rotulo']:
            raise ValueError(f'rótulo de {n} casillas: {texto!r} {"|".join(cel)}')
        k = min(max(0, round((PLACA - PASO_ROTULO * n) / 2 / PASO_ROTULO)), LIMITE['rotulo'] - n)
        return ESPACIO * k + self.codificar_celdas(cel)

    def libre(self, texto: str, campo: str = 'descripcion') -> tuple[bytes, int]:
        """Texto de FONT12 (objetivo/descripción) con saltos \\n (0x0A o literal '\\\\n') y %s/%d opacos.
        Devuelve (cuerpo, casillas de la línea más larga)."""
        partes, maxc = [], 0
        for linea_sep in re.split(r'(\n|\\n)', texto):
            if linea_sep in ('\n', '\\n'):
                partes.append(linea_sep.encode('ascii'))
                continue
            n = 0
            for trozo in re.split(r'(%[0-9]*[sd])', linea_sep):
                if not trozo:
                    continue
                if re.fullmatch(r'%[0-9]*[sd]', trozo):
                    partes.append(trozo.encode('ascii'))
                    n += 1
                    continue
                cel = self.celdas(trozo, campo)
                partes.append(self.codificar_celdas(cel))
                n += len(cel)
            maxc = max(maxc, n)
        return b''.join(partes), maxc


@lru_cache(maxsize=1)
def bigramas() -> Bigramas:
    return Bigramas()


def glosario():
    """{(fichero, clave): fila} de translation/shared/glossary/*.csv (lectura)."""
    import csv
    out = {}
    for p in sorted(GLOSARIO.glob('*.csv')):
        with p.open(encoding='utf-8') as f:
            out[p.stem] = list(csv.DictReader(f))
    return out


def sin_glifo_bcfnt(cuerpo: bytes):
    """Caracteres de un cuerpo (sin bigramas) sin glifo en FONT12.bcfnt."""
    return M.sin_glifo(cuerpo)
