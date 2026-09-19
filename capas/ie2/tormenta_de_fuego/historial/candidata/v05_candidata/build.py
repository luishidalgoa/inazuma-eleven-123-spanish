"""IE2 Fuego v05: candidata probe_ie2_v05 = probe_ie2_v03 + fuentes/CRO IE1 v90 + CRO IE2 v04 + gráficos (snapshot).

Capas (la última gana): ie1/capas/historial/menus_cro/v90_cro_restantes/extra (FONT12/FONT8/FONT12T),
ie2/shared/capas/historial/graficos/v05_graficos_snapshot/extra (copia congelada de v03/graficos/extra, 1535 ficheros).
CRO: ina_main1.cro de v90, ina_main2.cro de ie2 v04. Sin eventos. No se edita tools/.
Uso: python -X utf8 build.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
from ie123kit.nucleo.construir import candidata as C  # noqa: E402

W = ROOT / 'work'
BASE = W / 'shared/candidatas/probe_ie2_v03/archive.fa'
SALIDA = W / 'shared/candidatas/probe_ie2_v05/archive.fa'
V90 = W / 'ie1/capas/historial/menus_cro/v90_cro_restantes'
V04 = W / 'ie2/shared/capas/menus_cro/cro_restantes'
CAPAS = [V90 / 'extra', W / 'ie2/shared/capas/historial/graficos/v05_graficos_snapshot/extra']
CROS = [V90 / 'romfs/cro/ina_main1.cro', V04 / 'romfs/cro/ina_main2.cro']


def main():
    rep = C.construir(BASE, SALIDA, capas=CAPAS, cro=CROS)
    rep['base_ie2'] = 'probe_ie2_v03'
    rep['capas_v05'] = [str(c) for c in CAPAS]
    SALIDA.with_suffix('.build.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    print('archive', rep['archive_sha256'], 'reemplazos', rep['archive_replacements'])


if __name__ == '__main__':
    sys.exit(main())
