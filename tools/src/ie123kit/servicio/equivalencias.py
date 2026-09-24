"""Tabla de equivalencias: script u orden antigua -> orden ``ie123`` que la sustituye.

La sirve ``ServicioToolkit.equivalencias`` (``ie123 compat equivalencias``). Solo datos, sin importaciones.
"""

from __future__ import annotations

__all__ = ["EQUIVALENCIAS"]

#: Orden antigua -> (orden nueva, nota). Incluye los shims retirados en la F2.4 (#50), la F2.6 y la F2.7
#: (#55) y los scripts archivados en la F1.2/F1.4 (``docs/toolkit/SCRIPTS_RETIRADOS.md``).
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
    # Shims planos retirados en la F2.6 (#55): sus módulos siguen en _legado, en cuarentena
    "tools/validate.py": ("python -m ie123kit._legado.validate --legado-lo-se [game1]",
                          "validador del flujo eve_var abandonado; la verificación viva es `ie123 verificar`"),
    "tools/reinsert_var.py": ("python -m ie123kit._legado.reinsert_var --legado-lo-se",
                              "PELIGROSO: el offset-fixup corrompía eventos (FURIGANA_LECCIONES #8/#11/#13)"),
    "tools/ssd_reinsert.py": ("python -m ie123kit._legado.ssd_reinsert --legado-lo-se",
                              "PELIGROSO: ignora el byte de tamaño de registro; el motor vivo es nucleo.eventos.ssd"),
    "tools/ds_roster.py": ("python -m ie123kit._legado.ds_roster --legado-lo-se",
                           "la regla +16/NUL (#16) vive en ie123kit.ie1.texto.tablas"),
    # Motores de capas portados en la F2.6 (#55)
    "work/ie2/shared/capas/graficos/ayuda/apply.py": (
        "ie123 motor ayuda --juego ie2 --archive A --capturas-nds DIR --salida DIR",
        "solo las capturas: las pestañas necesitan el motor de rótulos de menús de la capa"),
    "work/ie1/capas/dialogo/motor_unificado/apply.py": (
        "ie123 motor paginar --juego ie1 --texto ...",
        "los parches de ina_main1.cro están en ie123kit.ie1.texto.cro"),
    "work/shared/capas/media/voz_titulo_recopilatorio/apply.py": (
        "ie123 motor voz-recopilatorio --sonido DIR --fuente AUDIO --salida DIR",
        "la capa es ya un envoltorio del motor (juego_principal.voz_titulo)"),
    # Shims planos retirados en la F2.7: en código se importa el módulo real (misma identidad)
    "tools/lz10.py": ("import ie123kit.nucleo.compresion.lz10 as lz10", "sin CLI propia"),
    "tools/sszl.py": ("import ie123kit.nucleo.compresion.sszl as sszl", "sin CLI propia"),
    "tools/ui_archive.py": ("import ie123kit._legado.ui_archive as ui_archive", "sin CLI propia"),
    "tools/qna_regions.py": ("import ie123kit.nucleo.graficos.qna as qna_regions", "sin CLI propia"),
    "tools/legacy_sprite.py": ("import ie123kit.nucleo.graficos.pac_sprite as legacy_sprite", "sin CLI propia"),
    "tools/nftr_metrics.py": ("python -m ie123kit._legado.nftr_metrics", "en código: import ie123kit._legado.nftr_metrics as nftr_metrics"),
    "tools/bcfnt.py": ("python -m ie123kit._legado.bcfnt", "en código: import ie123kit._legado.bcfnt as bcfnt"),
    "tools/ctpk_ui.py": ("import ie123kit.nucleo.graficos.ctpk as ctpk_ui", "sin CLI propia"),
    "tools/ssd_records.py": ("import ie123kit.nucleo.eventos.ssd as ssd_records", "sin CLI propia"),
    "tools/fa_unpack.py": ("python -m ie123kit._legado.fa_unpack", "en código: import ie123kit._legado.fa_unpack as fa_unpack"),
    "tools/fa_repack.py": ("python -m ie123kit._legado.fa_repack", "en código: import ie123kit._legado.fa_repack as fa_repack"),
    "tools/patch_smdh_title.py": ("python -m ie123kit._legado.patch_smdh_title", "en código: import ie123kit._legado.patch_smdh_title as patch_smdh_title"),
    "tools/ie1_keyboard.py": ("import ie123kit.ie1.graficos.teclado as ie1_keyboard", "sin CLI propia"),
    "tools/ie3_pipeline.py": ("python -m ie123kit.ie3.pipeline", "en código: import ie123kit.ie3.pipeline as ie3_pipeline"),
    "tools/ie3_verificar_offsets.py": ("python -m ie123kit.ie3.comun.verificar_offsets", "en código: import ie123kit.ie3.comun.verificar_offsets as ie3_verificar_offsets"),
    "tools/pkb_unpack.py": ("python -m ie123kit._legado.pkb_unpack", "en código: import ie123kit._legado.pkb_unpack as pkb_unpack"),
    "tools/build_glossary.py": ("python -m ie123kit._legado.build_glossary", "en código: import ie123kit._legado.build_glossary as build_glossary"),
    "tools/ds_official.py": ("python -m ie123kit._legado.ds_official --legado-lo-se", "en código: import ie123kit._legado.ds_official as ds_official"),
    "tools/reinsert.py": ("python -m ie123kit._legado.reinsert", "en código: import ie123kit._legado.reinsert as reinsert"),
    "tools/translate_ui_textures.py": ("python -m ie123kit._legado.translate_ui_textures", "en código: import ie123kit._legado.translate_ui_textures as translate_ui_textures"),
    "tools/mods_to_moflex.py": ("python -m ie123kit._legado.mods_to_moflex", "en código: import ie123kit._legado.mods_to_moflex as mods_to_moflex"),
    "tools/audit_dialogo_ids.py": ("python -m ie123kit._legado.audit_dialogo_ids", "en código: import ie123kit._legado.audit_dialogo_ids as audit_dialogo_ids"),
    # Congelados con CLI (F2.7): ya no se lanzan como `python tools/<nombre>.py`
    "tools/build_ui_revision.py": ("python -m ie123kit.nucleo.compat.congelados build_ui_revision --base ... --ui ... --output ...",
                                   "mismo fichero congelado, con los alias de congelados.preparar"),
    "tools/build_ie1_probe.py": ("python -m ie123kit.nucleo.compat.congelados build_ie1_probe ...",
                                 "mismo fichero congelado, con los alias de congelados.preparar"),
}
