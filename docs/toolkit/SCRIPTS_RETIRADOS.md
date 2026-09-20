# Scripts retirados de `tools/`

Registro de los scripts **retirados** de `tools/` durante la migración al paquete `ie123kit`. Se
archivaron primero en `tools/_archivo/` (subfases F1.2, [issue #43](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/43), y F1.4, [issue #45](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/45)) y en la
limpieza final F2.6 ([issue #55](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/55)) se **borraron del árbol**: su
contenido sigue completo en el historial de git y este documento conserva el motivo de cada
retirada, que es lo que había que preservar.

- Para recuperar uno: `git log --follow -- tools/_archivo/<script>.py` y
  `git show <commit>:tools/_archivo/<script>.py`.
- Ninguno era importable (la carpeta no tenía `__init__.py` ni estaba en `sys.path`) y lo más
  probable es que no se ejecuten tal cual: usaban rutas `parents[N]` y estructuras antiguas de
  `work/` que ya no existen.
- `ie123kit.nucleo.compat.superficie` los cuenta como retirados a partir de la lista `RETIRADOS`
  del propio módulo, que debe coincidir con la tabla de abajo.

Antes de rescatar cualquier idea de aquí, lee [`FURIGANA_LECCIONES.md`](../FURIGANA_LECCIONES.md).
En particular, los marcados **PELIGROSO: no reutilizar** están ahí por un fallo reproducido en
emulador (Norma 4).

## Scripts archivados

| Script | Motivo | Sustituto o dónde vive ahora |
|---|---|---|
| `pkb_scan.py` | Diagnóstico sin importadores. Su premisa (texto en bytecode sin LZ10) es errónea según EVENT_SCRIPT_FORMAT.md. | `ie123kit.nucleo.eventos.packnum` |
| `reinsert_test.py` | Prueba de concepto de la etapa 7. Nadie la referencia. | `ie123kit.nucleo.texto.sjis_portador` / `_legado/reinsert.py` |
| `recompress_test.py` | Diagnóstico v9 con efectos al importar y rutas inexistentes (`work/fa_extract`). | Ninguno |
| `build_translation.py` | **PELIGROSO: no reutilizar.** Sobrescribe `translation/ie*/dialogo.csv` con emparejamiento por orden. | Emparejamiento por ID (`tools/audit_dialogo_ids.py`); ver [#36](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/36) |
| `str_align.py` | Emparejamiento por índice ingenuo (item.STR 300 frente a 603). NDS_FIX superada. | `ie123kit.nucleo.texto.nds_latin` |
| `nds_str_dump.py` | Volcado ASCII trivial de la fase 2 inicial. Sin importadores. | `nds_latin` + `tools/build_glossary.py` |
| `tr_prepare.py` | Flujo de lotes IA de 2026-06-14 ya terminado, con rutas rotas. | Validaciones de `ie123 textos importar` (fase 2): %NF fuera y conteo de `\f` |
| `tr_merge.py` | Mitad de fusión del mismo flujo. | Validación «solo rellenar pendiente o vacío» del importador de textos (fase 2) |
| `align_events.py` | Alineador por orden (Needleman-Wunsch), fallido. | Emparejamiento por ID; ver [#36](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/36). `dialogue_runs`/`is_furigana` siguen en la fachada `_legado` de pkb_unpack |
| `audit_ie1_voiced_text.py` | Sustituido por la auditoría por ID. Sin importadores. | `work/ie1/capas/media/voces/auditoria.py`; regla documentada en `ie1/media/voces.py` |
| `verify_build.py` | Comprobaciones SAME_SIZE de la era v27. Sin llamadores. | `ie123 verificar` (el shim `tools/verify_candidate.py` se retiró en la F2.4) |
| `verify_v21.py` | Aserciones puntuales contra v21, que ya no existe. | `ie123 verificar` (el shim `tools/verify_candidate.py` se retiró en la F2.4) |
| `fix_ie1_title_logo.py` | Rehecho por capas posteriores; tenía una ruta fija a Downloads. | Capas v60/v62/v63 y `work/ie1/capas/graficos/titulo_logo` |
| `compact_typography.py` | Experimentos v4/v8 superados por el bloqueo v20. | Bloqueo tipográfico v20 (`tools/dialogue_lock.py`, `AGENTS.md`) |
| `build_match_content_patch.py` | Produjo mch v23-v27. | `work/ie1/capas/historial/dialogo/v33_mch_story` y `work/ie1/capas/historial/dialogo/v55_pachangas`; invariantes a `ie1/texto/mch.py` (fase 2) |
| `build_mch_patch.py` | Variante solo Royal (v21), contenida en la anterior. | `work/ie1/capas/historial/dialogo/v33_mch_story` y `work/ie1/capas/historial/dialogo/v55_pachangas` |
| `build_3ds.py` | Constructor in situ de la etapa 8 (parches v1-v9). | `work/ie1/capas/historial/candidata/v33_final/build_rom.py` + `tools/build_ui_revision.py` + `tools/verify_candidate.py` |
| `build_3ds_var.py` | **PELIGROSO: no reutilizar.** Sin SKIP_CRO/NO_CODE_PATCH aplica parches fallidos. | `work/ie1/capas/historial/candidata/v33_final/build_rom.py` + `tools/build_ui_revision.py` + `tools/verify_candidate.py` |
| `build_fontui.py` | **PELIGROSO: no reutilizar.** Diagnóstico v7 con efectos al importar; pasa FONT12T por el editor 4bpp incompatible. | Bloqueo tipográfico v20 (`tools/font_patch.py`, `tools/dialogue_lock.py`) |
| `ui_insert.py` | **PELIGROSO: no reutilizar.** Escribía unitbase +0 en ASCII sin NUL. | Regla +16/NUL: [#16](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/16), `work/ie1/capas/historial/nombres/v36_nombres` |
| `probe_ie1_spacing.py` | Experimento v18 retirado; sus fuentes chocan con el bloqueo v20. | Bloqueo tipográfico v20 (`tools/dialogue_lock.py`, `AGENTS.md`) |
| `build_ie1_movies.py` | Sustituido: las 21 películas de v66/v67 son idénticas a su `extra/`. | `work/ie1/capas/media/cinematicas/build.py` |
| `reorganizar_proyecto.py` | Migración del 2026-09-16 ya aplicada. | Ninguno (la migración a juego_principal será una acción aparte que copia) |
| `tests/test_compact_typography.py` | Prueba un módulo archivado; ya se saltaba por faltar `work/fa_extract`. | Ninguno |
| `tests/test_validate_inputs.py` | Prueba `validate.py`, que queda en cuarentena. | `ie123kit/_legado/validate.py` (F1.4) |
| `ie1_tables.py` | F1.4: sin importadores; lógica dividida. | `ie123kit.nucleo.registros.tabla_fija` + `ie123kit.ie1.texto.tablas` |
| `ie1_media.py` | F1.4: sin importadores. El stage legacy (v34) ya no es válido. | `ie123kit.nucleo.media.audio` + `ie123kit.ie1.media.voces` (`python -m ie123kit.ie1.media.voces --stage`) |
| `validate_ie1_media.py` | F1.4: sin importadores; sus reglas pasan a la verificación de IE1. | `ie123kit.ie1.verificar` + `ie123kit.nucleo.media.moflex.disposicion_rotacion` |
| `patch_exefs.py` | F1.4: su ruta code.bin/exheader dependía de `patch_code`. | La primitiva ExeFS vive en `ie123kit.nucleo.contenedores.exefs` (experimental) |
| `patch_code.py` | **PELIGROSO: no reutilizar.** Saltos a cuevas de la CRO imposibles (crash en 0xAD9E38). Regla vigente: `NO_CODE_PATCH=1`. | Ninguno |
| `patch_cro.py` | **PELIGROSO: no reutilizar.** La cueva 0x50E14 es zona de reubicación (crash en 0xAD9E1C). Regla vigente: `SKIP_CRO=1`. | Ninguno |

Issues relacionados: [#9](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/9),
[#16](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/16),
[#36](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/36).

## Retirados en F1.4

`patch_code.py` y `patch_cro.py`, que en F1.2 seguían en `tools/` porque `patch_exefs.py` los importaba,
se archivaron en F1.4 ([#45](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/45)) junto
con `patch_exefs.py`, `ie1_tables.py`, `ie1_media.py` y `validate_ie1_media.py`. Ambos parches son
**obsolete_dangerous** según [`FURIGANA_LECCIONES.md`](../FURIGANA_LECCIONES.md).

## Retirados en F2.6 (#55)

Shims planos de `tools/` borrados en la limpieza final: el comprobador AST no encontró **ningún**
importador (ni en `tools/`, ni en `tools/src`, ni en `tools/tests`, ni en `work/`, historial
incluido). Los cuatro siguen en cuarentena dentro de `ie123kit._legado`, con su bandera
`--legado-lo-se`, y se lanzan con `python -m ie123kit._legado.<modulo>`.

| Script | Motivo | Sustituto o dónde vive ahora |
|---|---|---|
| `ds_roster.py` | Sin importadores. La ESPECIFICACION lo conservaba por ser «transitivo desde `reinsert`», pero `_legado` se importa entre sí por `ie123kit._legado.<mod>`, no por el nombre plano. | `ie123kit._legado.ds_roster` (cuarentena); regla +16/NUL en `ie123kit.ie1.texto.tablas` |
| `reinsert_var.py` | Ídem. **PELIGROSO: no reutilizar** (el offset-fixup corrompía eventos, [`FURIGANA_LECCIONES`](../FURIGANA_LECCIONES.md) ❌#8/#11/#13). | `ie123kit._legado.reinsert_var` (cuarentena) |
| `ssd_reinsert.py` | Ídem. **PELIGROSO: no reutilizar** (ignora el byte de tamaño de registro). | `ie123kit.nucleo.eventos.ssd` (`ssd.replace`) |
| `validate.py` | Sin importadores, y su nombre colisionaba en `sys.path` con los `validate.py` de las capas; al retirarlo cada capa resuelve el suyo. | `ie123 verificar`; el validador del flujo abandonado sigue en `ie123kit._legado.validate` |

## Nota

No hay stubs ni shims en `tools/` para estos nombres. `ie123 compat equivalencias` (F2.4) indica la orden
sustituta de cada script retirado, incluidos los shims de CLI retirados en la F2.4.
