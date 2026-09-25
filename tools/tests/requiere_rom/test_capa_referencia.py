"""Gate 3: la capa de referencia (work/ie1/capas/graficos/titulo_logo, antes v67) se regenera byte a byte.

Desde el 2026-09-19 (#49) no se ejecuta el apply.py de la capa (dependía de probe_ie1_v66, borrada, y de
un PNG de Descargas): se reaplica su textura con texturas.apply_plan sobre work/shared/base_3ds en un
temporal y se exige el sha de capa_referencia.sha256. Nunca escribe en la capa.
Requiere work/ local (ROM extraída); en CI se deselecciona con -m "not requiere_rom".
"""
import pytest

pytestmark = pytest.mark.requiere_rom


def test_regenerar_capa_referencia_coincide_con_golden():
    from ie123kit.nucleo.compat import golden
    from ie123kit.nucleo.config.raiz import find_root

    raiz = find_root()
    for rel in (f'{golden.CAPA}/extra/{golden.RUTA_ARC}', f'{golden.BASE_REFERENCIA}/archive.fa'):
        if not (raiz / rel).is_file():
            pytest.skip(f'falta recurso local: {rel}')

    total, malos = golden.regenerar_capa(raiz)
    assert total >= 1
    assert malos == []
