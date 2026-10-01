"""Gate (3) de la F2.5 (#51): el ciclo de la GUI sobre la base real, con el bloqueo tipográfico real.

exportar ``inazuma1/data_iz/a_title/title_t.arc`` (ie1) → cambiar un píxel dentro de un rectángulo QNA
→ importar(simular) sin escribir → importar (capa ``gui_*`` nueva en work/ie1/capas/graficos) →
construir sobre la candidata vigente (``probe_ie2_v34``, cuyas fuentes aprueba el bloqueo desde #80)
→ verificar. La única entrada distinta de la base es ``title_t.arc``. Todo lo que crea (capa, PNG,
candidata) se borra al terminar; nada se instala en el emulador.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from ie123kit.nucleo.compat import golden
from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom

RUTA = "inazuma1/data_iz/a_title/title_t.arc"


@pytest.fixture(scope="module")
def raiz() -> Path:
    r = find_root()
    for rel in ("work/shared/base_3ds/romfs/archive.fa", f"work/shared/candidatas/{golden.CANDIDATA_VIGENTE}/archive.fa"):
        if not (r / rel).is_file():
            pytest.skip(f"falta recurso local: {rel}")
    return r


def _capas_gui(raiz: Path) -> set[Path]:
    return set((raiz / "work/ie1/capas/graficos").glob("gui_*"))


def test_flujo_gui_real_title_t(raiz) -> None:
    from PIL import Image

    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.servicio import contrato
    from ie123kit.servicio.api import ServicioToolkit, SolicitudConstruccion

    servicio = ServicioToolkit.abrir(raiz)
    assert contrato.compatible("1.0", servicio.API_VERSION)
    tmp = Path(tempfile.mkdtemp(prefix="ie123_gui_real_"))
    previas = _capas_gui(raiz)
    nuevas: set[Path] = set()
    try:
        activo = next(a for a in servicio.activos("ie1", tipo="grafico").datos["activos"]
                      if a["ruta_romfs"] == RUTA)
        exp = servicio.exportar("ie1", [activo["id"]], tmp / "png")
        assert exp.ok, exp.incidencias
        assert contrato.validar_resultado("exportar", exp) == []

        # «editar»: un píxel dentro de un rectángulo QNA si la textura lo declara; si no, en el centro
        metas = [json.loads(Path(m).read_text(encoding="utf-8")) for m in exp.artefactos if m.endswith(".qna.json")]
        meta = next((m for m in metas if m["rects"]), metas[0])
        png = tmp / "png" / f"{Path(meta['textura']).stem}.png"
        x0, y0 = (meta["rects"][0][:2] if meta["rects"] else (meta["ancho"] // 2, meta["alto"] // 2))
        edicion = tmp / "edicion"
        edicion.mkdir()
        img = Image.open(png).convert("RGBA")
        r, g, b, a = img.getpixel((x0, y0))
        img.putpixel((x0, y0), ((r + 128) % 256, g, b, 255))
        img.save(edicion / png.name)

        sim = servicio.importar("ie1", activo["id"], edicion, simular=True)
        assert sim.ok and sim.datos["simulado"] is True, sim.incidencias
        assert _capas_gui(raiz) == previas, "simular no puede crear capas"

        imp = servicio.importar("ie1", activo["id"], edicion, simular=False)
        nuevas = _capas_gui(raiz) - previas          # antes de cualquier assert: se borran en finally
        assert imp.ok, imp.incidencias
        assert contrato.validar_resultado("importar", imp) == []
        capa = Path(imp.datos["capa"])
        assert nuevas == {capa} and capa.name.startswith("gui_") and (capa / "capa.toml").is_file()

        salida = tmp / "candidata"
        base = raiz / "work/shared/candidatas" / golden.CANDIDATA_VIGENTE
        res = servicio.construir(SolicitudConstruccion(base=str(base), objetivos=(), capas=(str(capa),),
                                                       salida=str(salida)))
        assert res.ok, res.incidencias                       # incluye el bloqueo tipográfico real
        assert contrato.validar_resultado("construir", res) == []
        a, b = FaArchive(str(base / "archive.fa")), FaArchive(str(salida / "archive.fa"))
        assert [p for p, _, _ in a.entries] == [p for p, _, _ in b.entries]
        en_b = {p: (o, s) for p, o, s in b.entries}
        distintas = [p for p, o, s in a.entries if s != en_b[p][1] or a.file_bytes(o, s) != b.file_bytes(*en_b[p])]
        assert distintas == [RUTA]

        ver = servicio.verificar(str(salida))
        assert ver.ok and ver.datos["bloqueo_v20"] == "ok", ver.incidencias
        assert contrato.validar_resultado("verificar", ver) == []
    finally:
        for c in nuevas:
            shutil.rmtree(c, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
    assert _capas_gui(raiz) == previas
