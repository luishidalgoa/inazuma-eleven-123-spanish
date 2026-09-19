"""Tabla de equivalencias: script u orden antigua -> orden ``ie123`` que la sustituye.

La sirve ``ServicioToolkit.equivalencias`` (``ie123 compat equivalencias``). Solo datos, sin importaciones.
"""

from __future__ import annotations

__all__ = ["EQUIVALENCIAS"]

#: Orden antigua -> (orden nueva, nota). Incluye los shims de CLI retirados en la F2.4 (#50) y los
#: scripts archivados en la F1.2/F1.4 (``tools/_archivo/README.md``).
EQUIVALENCIAS: dict[str, tuple[str, str]] = {
    # Scripts PowerShell (siguen existiendo como envoltorios de una orden)
    "tools/build_patch.ps1": ("ie123 parche --rom-base X --rom-parcheada Y --salida patch/...xdelta",
                              "el .ps1 es ahora un envoltorio de esta orden"),
    "tools/extract_romfs.ps1": ("ie123 extraer romfs [--rom X] [--salida work/shared/base_3ds]",
                                "el .ps1 es ahora un envoltorio de esta orden"),
    "tools/extract_nds.ps1": ("ie123 extraer nds --rom X --salida work/<juego>/fuentes/nds_es",
                              "extractor en Python puro: ya no hace falta ndstool"),
    "tools/jugar.ps1": ("tools/jugar.ps1 (lanza Azahar) + ie123 registro --sesion NOMBRE",
                        "la cosecha del log es ahora `ie123 registro`"),
    # Shims de CLI retirados en la F2.4
    "tools/verify_candidate.py": ("ie123 verificar --candidata vNN [--golden]",
                                  "el informe detallado de IE1 sigue en python -m ie123kit._legado.verify_candidate"),
    "tools/nds_unpack.py": ("ie123 extraer nds --rom X --salida DIR", "misma salida (DIR/data_iz/...)"),
    "tools/blz.py": ("python -m ie123kit._legado.blz ENTRADA SALIDA", "solo descompresión (FURIGANA_LECCIONES)"),
    "tools/harvest_log.py": ("ie123 registro [--sesion NOMBRE] [--forzar]", "mismo registro en logs/"),
    "tools/limpiar_work.py": ("ie123 work limpiar [--borrar]", "sin --borrar solo lista"),
    "python -m ie123kit.nucleo.compat.golden comprobar": ("ie123 compat comprobar [--golden]",
                                                          "ejecuta además importaciones y bloqueo"),
    # Archivados en la F1.2/F1.4 (sin shim)
    "tools/build_3ds.py": ("ie123 construir --base ... --salida ...", "archivado (F1.2)"),
    "tools/build_3ds_var.py": ("ie123 construir --base ... --salida ...", "PELIGROSO; archivado (F1.2)"),
    "tools/verify_build.py": ("ie123 verificar --candidata vNN", "archivado (F1.2)"),
    "tools/verify_v21.py": ("ie123 verificar --candidata vNN", "archivado (F1.2)"),
    "tools/build_ie1_movies.py": ("work/ie1/capas/media/cinematicas/build.py", "archivado (F1.2)"),
    "tools/ie1_media.py": ("python -m ie123kit.ie1.media.voces --stage", "archivado (F1.4)"),
    "tools/patch_code.py": ("(ninguna)", "PELIGROSO: NO_CODE_PATCH=1"),
    "tools/patch_cro.py": ("ie123 motor cro-ancho-dialogo (solo inmediatos comprobados)",
                           "PELIGROSO el antiguo: SKIP_CRO=1"),
    # Motores de capas de IE2 portados en la F2.4
    "work/ie2/shared/capas/dialogo/saltos37/apply.py": ("ie123 motor paginar --juego ie2 --texto ...",
                                                        "motor: ie123kit.nucleo.texto.paginado"),
    "work/ie2/shared/capas/teclado/teclado/apply.py": ("ie123 motor teclado --archive A --salida DIR", ""),
    "work/ie2/shared/capas/media/voces/apply.py": ("ie123 motor voces --bancos 2D_020_01,... --salida DIR", ""),
    "work/ie2/shared/capas/media/subtitulos/apply.py": ("ie123 motor subtitulos --dat F [--fotogramas N]",
                                                        "texto y tiempos; la codificación sigue en la capa"),
    "work/ie2/shared/capas/menus_cro/ancho_dialogo/apply.py": ("ie123 motor cro-ancho-dialogo --cro C --salida S",
                                                               ""),
}
