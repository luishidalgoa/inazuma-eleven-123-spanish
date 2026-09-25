# Herramientas

## IE3: emisión general tras el piloto aprobado

`python -X utf8 -m ie123kit.ie3.fase3` reconstruye Spark y Ogre con un núcleo
común, transición original/heredado/salida y reportes por categoría. El constructor
`ie123kit.ie3.comun.build_piloto --integrated` produce y reextrae la ROM completa.
Comandos, límites, perfiles Bomber y pruebas manuales en
[IE3_FASE3_INTEGRACION](../docs/IE3_FASE3_INTEGRACION.md). No confundir los planes
offline, la aprobación de un único piloto y la validación de toda una campaña.

## Paquete ie123kit

La fase 1 de la migración (épica #40, subfases F1.0-F1.5) está cerrada. El código vive en
`tools/src/ie123kit`; en `tools/` solo quedan los 5 congelados (ningún shim: los últimos 22 se retiraron
en la F2.7 y todo el código importa `ie123kit.<...>`), los 6 `.ps1` (`build_patch`, `extract_nds` y `extract_romfs` son
envoltorios de una orden `ie123`; `jugar` lanza Azahar y cosecha con `ie123 registro`; `setup_mobipeg`,
`setup_vgmstream`), `bin/` (local, ignorado), `src/`, `tests/`, `pyproject.toml` y este README.

> Norma 2: nunca se suben ROMs ni datos extraídos (`Roms/` y `work/` están ignorados). La CI lo comprueba.

### Inicio rápido

- Instalar: `pip install -e tools[dev]` (Python 3.12; en Windows, `python -X utf8`).
- Sin instalar: añadir `tools/src` a `sys.path` (o `PYTHONPATH`). Ya no existen `python tools/fa_unpack.py`
  ni `import lz10`: se usa `python -m ie123kit._legado.fa_unpack` e `import ie123kit.nucleo.compresion.lz10`
  (tabla de abajo; `ie123 compat equivalencias` o `python -m ie123kit.nucleo.compat.shims listar`).
- Los congelados con CLI se lanzan con `python -m ie123kit.nucleo.compat.congelados build_ui_revision …`
  (o `build_ie1_probe`, `font_patch`); quien los importe llama antes a
  `ie123kit.nucleo.config.congelados.preparar()`.
- Las órdenes nuevas se lanzan como módulo: `python -m ie123kit.<ruta.del.modulo>`.

### La orden `ie123` (CLI)

Con el paquete instalado hay una orden única, `ie123`, equivalente a `python -m ie123kit.cli`. Cada
subcomando es un adaptador argparse 1:1 sobre `ServicioToolkit` (la fachada de `ie123kit.servicio`):
la CLI no tiene lógica propia. Opciones globales: `--proyecto RUTA` (raíz del repositorio) y `--json`
(imprime el `Resultado` serializado en UTF-8).

```
ie123 construir --base probe_ie2_v34 --capas work/ie1/capas/graficos/titulo_logo --salida probe_ie2_v35
ie123 parche --rom-base "Roms/shared/....3ds" --rom-parcheada build/123_es.3ds --salida patch/x.xdelta
ie123 doctor
ie123 proyecto init --rom3ds "Roms/shared/....3ds" --nds-es-ie1 "Roms/ie1/....nds"
ie123 proyecto migrar-juego-principal
ie123 objetivos
ie123 juego_principal activos --json
ie123 work limpiar          # --borrar para borrar de verdad
ie123 extraer romfs         # ROM 3DS -> work/shared/base_3ds (3dstool)
ie123 extraer nds --rom "Roms/ie1/....nds" --salida work/ie1/fuentes/nds_es
ie123 verificar --candidata probe_ie2_v34 [--golden]
ie123 instalar --candidata probe_ie2_v34 [--lanzar]
ie123 registro --sesion v35  # cosecha el log de Azahar (antes harvest_log.py)
ie123 compat comprobar [--golden]
ie123 compat equivalencias  # orden nueva de cada script retirado
ie123 motor listar
ie123 motor paginar --juego ie2 --texto "..."
ie123 motor teclado --archive A --salida DIR
ie123 motor cro-ancho-dialogo --cro ina_main2.cro --salida DIR/ina_main2.cro
ie123 motor voces --sonido-3ds D --sonido-nds D --bancos 2D_020_01,2D_020_02 --salida DIR
ie123 motor subtitulos --dat a2m03.dat [--fotogramas N]
```

Todos los verbos tienen alias en inglés (`build`, `patch`, `extract`, `verify`, `install`, `log`,
`engine`, `check`…; tabla en `ie123kit.cli.main.ALIAS`). Códigos de salida: 0 ok, 1 validación,
2 uso incorrecto, 3 bloqueo v20, 4 falta una herramienta, 5 no soportado; los avisos no cambian el código.

- `extraer romfs|nds`: `romfs` repite los pasos de `extract_romfs.ps1` con 3dstool (la ROM sale de
  `[roms] 3ds_jp` de `ie123.local.toml` si no se pasa `--rom`); `nds` es Python puro (sin ndstool) y deja
  la misma salida que el antiguo `nds_unpack.py`.
- `verificar` ejecuta siempre el bloqueo v20; `--golden` compara además con `candidatas.sha256`. El
  informe detallado de IE1 del antiguo `verify_candidate.py` sigue en
  `python -m ie123kit._legado.verify_candidate`.
- `compat comprobar` ejecuta los gates de la migración (`nucleo.compat.gates`): ficheros bloqueados,
  golden de congelados e importaciones de `work/`; con `--golden`, además la capa de referencia, las
  candidatas, la reconstrucción de referencia y el bloqueo de la candidata vigente. Desde #80
  (2026-09-19) el bloqueo aprueba las fuentes de `probe_ie2_v34` y ese gate tiene que pasar.
- `motor …` expone los motores portados de las capas de IE2 en la F2.4 (paginado 37 × 3 / 131 B, teclado
  en SPF_, bancos DSP-ADPCM, subtítulos incrustados y parche de ancho del diálogo en la CRO). Escriben
  solo en `--salida` y nunca sobrescriben.
- Motores de fuentes portados en la F2.5 (#51), como biblioteca (trabajan sobre copias en memoria y no
  cambian ninguna fuente): `nucleo.fuentes.celdas` (lectura/escritura de celdas BCFNT), `nucleo.fuentes.ritmo`
  (ritmo uniforme y partición DP de IE1 v89), `nucleo.fuentes.bigramas` (registro append-only),
  `nucleo.fuentes.rebanadas` + `ie2.comun.menus` (menús del CRO de IE2 v23), `nucleo.texto.escaneo` y el
  banner HOME (`juego_principal.banner`: SMDH, CBMD, LZ11, CGFX y BCWAV). API de servicio para la GUI:
  [`docs/toolkit/API_SERVICIO.md`](../docs/toolkit/API_SERVICIO.md).

- `construir` construye una candidata de TODA la recopilación (`--objetivos ie1,juego_principal`,
  `--capas` repetible), se niega a sobrescribir y **siempre** ejecuta el bloqueo tipográfico v20.
- `parche` genera el `.xdelta` (único entregable distribuible) con las mismas banderas que
  `tools/build_patch.ps1`.
- `doctor` comprueba el entorno local (sin red y sin exigir ROM).
- `proyecto init` crea `work/<objetivo>/{capas,qa,exportaciones}` y `translation/<objetivo>/` de los
  siete objetivos, `work/juego_principal/` incluido, y anota en `ie123.local.toml` las RUTAS de ROM
  que se le pasen (nunca su contenido). Es idempotente; `--simular` solo informa.
- `proyecto migrar-juego-principal` escribe `work/juego_principal/historico.json` con las capas de
  `work/ie1/capas` que tocan el menú. **No mueve nada** (sus rutas relativas e `importlib` dependen de
  su sitio), así que `--no-simular` responde `5` y deja el histórico escrito igual.
- `objetivos` lista los siete objetivos con su id, prefijos y capacidades.
- `<objetivo> activos [--tipo T] [--filtro P]` es el inventario: las entradas del `archive.fa` MÁS lo
  que vive fuera de él (`cro/*.cro`, `.SAD`, `banner.bnr`/`icon.icn`). Las rutas de `solo_lectura`
  (las fuentes del bloqueo v20) salen listadas con `editable: false`.
- `work limpiar [--borrar]` lista (o borra) lo regenerable de los cinco ámbitos de `work/`.
- `--json` y `--proyecto` valen antes y después del verbo: `ie123 --json ie1 activos` y
  `ie123 ie1 activos --json` son lo mismo.
- Alias en inglés ya disponibles: `build`, `patch`, `targets`, `project`, `assets`, `clean`
  (la tabla completa de equivalencias llega en F2.4).

Códigos de salida: `0` ok · `1` incidencias de validación · `2` uso incorrecto · `3` violación del
bloqueo tipográfico · `4` falta una herramienta externa · `5` operación no soportada.

> Quedan para F2.4 `extraer`, `verificar`, `instalar` y `compat`, y la tabla completa de alias en
> inglés; ver `docs/toolkit/ESPECIFICACION.md`.

### Tests

- Sin ROM (lo que corre la CI): `python -X utf8 -m pytest tools/tests -m "not requiere_rom" -q`.
- Con ROM y `work/` (solo en local): `python -X utf8 -m pytest tools/tests -m requiere_rom -q`.
- Estructura de `tools/tests/`:
  - `unidad/`: tests por área (`texto`, `graficos`, `compresion`, `eventos`…). Aquí están los 6 tests
    heredados de la raíz: `test_dialogue_lock` → `unidad/texto/test_dialogue_lock.py`,
    `test_dialogue_typography` → `unidad/texto/test_ancho_completo.py`, `test_probe_layout` →
    `unidad/texto/test_tipografia_v20.py`, `test_legacy_sprite` → `unidad/graficos/test_pac_sprite.py` +
    `unidad/compresion/test_lz10.py`, `test_ssd_records` → `unidad/eventos/test_ssd.py` y `test_ui_formats`
    → `unidad/graficos/test_formatos_ui.py`. Todos pasan por ruff.
  - `arquitectura/`: reglas de importación del paquete (ver [`docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md)).
  - `compat/`: shims retirados y sus destinos, superficie pública, identidad de módulos y golden de candidatas.
  - `requiere_rom/`: `test_capa_referencia.py` (regenera en un temporal el `.arc` de
    `work/ie1/capas/graficos/titulo_logo` sobre `work/shared/base_3ds`),
    `test_candidata_referencia.py` (`build_ui_revision.py` y `ie123kit.nucleo.construir.candidata`, desde
    `work/shared/base_3ds/romfs`, dan el `archive.fa` de sha256 `golden.ARCHIVE_REFERENCIA`
    `6f23e4d5…d7f1` y solo cambian `title_t.arc`), `test_cli_construir_parche.py` (la CLI reaplica la capa
    sobre la candidata vigente `probe_ie2_v34`; en xfail mientras `FONT_HASHES` no sean las fuentes
    vigentes) y
    `test_clon_limpio.py` (un `git worktree` limpio conserva los hashes de los bloqueados y pasa
    `test_dialogue_lock`).

### CI y guardias

Hay dos workflows de comprobación (`release.yml` no cambia):

- [`.github/workflows/guardia.yml`](../.github/workflows/guardia.yml): **sin filtro de rutas**, corre en
  cada commit y PR toquen lo que toquen, y ejecuta `guardia todo` (bloqueados + git). Es el que hace
  global la Norma 2: una ROM o contenido extraído añadido en `translation/`, `docs/` o una carpeta nueva
  falla ahí. En GitHub Actions `paths` filtra el workflow entero, no un job, así que esta guardia no
  puede vivir dentro de `toolkit.yml`, que sí está filtrado a `tools/**`. No añadir `paths` a
  `guardia.yml`. No instala nada (solo biblioteca estándar, `PYTHONPATH=tools/src`), así que es de
  segundos.
- [`.github/workflows/toolkit.yml`](../.github/workflows/toolkit.yml) corre en `windows-latest` y
  `ubuntu-latest` cuando cambia `tools/**` (o `.gitattributes`, `AGENTS.md`, `CLAUDE.md`):

1. `pip install -e tools[dev]` — el extra `dev` incluye `opencv-python-headless` porque
   `nucleo/graficos/pintado.py` importa `cv2` en cuanto una operación lleva `image` o
   `erase='bright'`; sin él la CI fallaba en los dos SO y solo pasaba en máquinas con OpenCV ya
   instalado (#58).
2. `python -m ie123kit.nucleo.compat.guardia bloqueados`: sha256 de los congelados según
   `congelados.sha256` y `SOURCE_HASHES` de `dialogue_lock`.
3. `python -m ie123kit.nucleo.compat.guardia git`: falla si git rastrea `Roms/`, `work/`, ficheros
   `.3ds/.cia/.nds/.fa/.arc/.lzs/.STR/.dat/.pkb/.pkh/.bcfnt/.NFTR/.moflex/.mods/.SAD` o PNG de más de
   256 KB fuera de `logos/`.
4. `python -m ie123kit.nucleo.compat.shims comprobar`
5. `pytest tools/tests -m "not requiere_rom"`

La CI no se desactiva ni se salta.

Diferencia esperada entre SO (#59): en Linux se saltan los 5 tests de hash de
`tools/tests/unidad/test_pintado.py` (`test_paint_igual_que_original[simple|izq|condensado|rotado]` y
`test_paint_condensed_igual_que_original`), porque sus hashes se capturaron con Arial
(`C:/Windows/Fonts/arial.ttf`), que no se puede redistribuir ni sustituir sin invalidarlos. Las rutas de
código que cubren (condensado, rotación, texto que no cabe, padding negativo) sí se comprueban en los dos
SO con la negrita del sistema (Arial o DejaVu) en el bloque «Cobertura independiente de la fuente» de ese
mismo fichero. Ningún otro test se salta en un SO y no en el otro.

### Congelados (bloqueo v20)

`dialogue_typography.py`, `font_patch.py`, `dialogue_lock.py`, `build_ie1_probe.py` y
`build_ui_revision.py` se quedan en `tools/`, intactos, con `-text` en `.gitattributes` y excluidos de
ruff y black. El paquete los usa mediante re-exports perezosos que no copian código (cargan el fichero con
`ie123kit.nucleo.config.congelados.cargar`).

Como no se pueden editar, siguen importando por su nombre plano 7 módulos que ya no tienen shim
(`fa_unpack`, `fa_repack`, `lz10`, `pkb_unpack`, `reinsert`, `ssd_records` y, desde `font_patch`, `bcfnt`).
`ie123kit.nucleo.config.congelados.preparar()` pone `tools/` en `sys.path` e instala en `sys.meta_path` un
resolutor que devuelve el módulo real de cada uno (`ALIAS_CONGELADOS`), con la misma identidad que daba el
shim. `cargar` ya lo llama; una capa que importe un congelado directamente debe llamarlo antes:

```python
from ie123kit.nucleo.config.congelados import preparar as _preparar_congelados; _preparar_congelados()
from dialogue_typography import encode_fullwidth
```

Para lanzarlos como script: `python -m ie123kit.nucleo.compat.congelados build_ui_revision --base … --ui …
--output …` (también `build_ie1_probe` y `font_patch`), en lugar del antiguo `python tools/build_ui_revision.py`.

### Shims (retirados)

- Hasta la F2.7 cada `tools/<nombre>.py` era un alias que sustituía su entrada de `sys.modules` por el
  módulo real. En la F2.7 se migraron todos sus usos (capas de `work/`, tests, paquete, documentación) a
  `ie123kit.<...>` y se borraron los 22 que quedaban: `tools/` ya no tiene ninguno.
- `ie123kit.nucleo.compat.shims` conserva la tabla (`DESTINOS`, `… shims listar`), la lista de retirados
  (`RETIRADOS`) y el comprobador: `… shims comprobar` falla si reaparece en `tools/` un shim retirado o un
  fichero con lógica disfrazado de shim. `generar` se niega a recrear un retirado.
- **Fachada `_legado`**: `nucleo` no imprime ni termina el proceso, así que los módulos con CLI que escribe
  en pantalla dejan la lógica en `nucleo` y el `main()` original en `ie123kit/_legado/<nombre>.py`, que
  reexporta todos los nombres de antes, privados incluidos.
- **Cuarentena**: `ds_roster`, `reinsert_var`, `ssd_reinsert` y `validate` solo ejecutan su CLI con
  `--legado-lo-se`; `ds_official` exige la misma bandera para `main`/`align` (o `IE123_LEGADO_LO_SE=1`
  si `align` se llama desde código). Se invocan con `python -m ie123kit._legado.<modulo> --legado-lo-se`.

### Equivalencias `tools/<antiguo>.py` → módulo real

| Antiguo (`tools/`, retirado) | Módulo real: `import …` / `python -m …` | Lógica en | Tipo |
|---|---|---|---|
| `audit_dialogo_ids.py` | `ie123kit._legado.audit_dialogo_ids` | `nucleo.eventos.alineado_ids` | fachada; **retirado en F2.7** |
| `bcfnt.py` | `ie123kit._legado.bcfnt` | `nucleo.fuentes.bcfnt` | fachada permanente (`font_patch.py` hace `from bcfnt import BCFNT`); **retirado en F2.7** |
| `blz.py` | `ie123kit._legado.blz` | `nucleo.compresion.blz` | **retirado en F2.4**: `python -m ie123kit._legado.blz in out` |
| `build_glossary.py` | `ie123kit._legado.build_glossary` | `nucleo.texto.nds_latin` | fachada; **retirado en F2.7** |
| `ctpk_ui.py` | `ie123kit.nucleo.graficos.ctpk` | — | alias directo; **retirado en F2.7** |
| `ds_official.py` | `ie123kit._legado.ds_official` | `nucleo.texto.nds_latin` + `nucleo.eventos.alineado_ids` | fachada (`--legado-lo-se`); **retirado en F2.7** |
| `ds_roster.py` | `ie123kit._legado.ds_roster` | — | **retirado en F2.6**, cuarentena: `python -m ie123kit._legado.ds_roster --legado-lo-se` |
| `fa_repack.py` | `ie123kit._legado.fa_repack` | `nucleo.contenedores.fa` (`fe_offset_of`) | fachada; **retirado en F2.7** |
| `fa_unpack.py` | `ie123kit._legado.fa_unpack` | `nucleo.contenedores.fa` | fachada; **retirado en F2.7** |
| `harvest_log.py` | `ie123kit._legado.harvest_log` | `nucleo.construir.registro_azahar` | **retirado en F2.4**: `ie123 registro` |
| `ie1_keyboard.py` | `ie123kit.ie1.graficos.teclado` | — | alias directo; **retirado en F2.7** |
| `legacy_sprite.py` | `ie123kit.nucleo.graficos.pac_sprite` | — | alias directo; **retirado en F2.7** |
| `limpiar_work.py` | `ie123kit._legado.limpiar_work` | `nucleo.construir.limpieza` | **retirado en F2.4**: `ie123 work limpiar [--borrar]` |
| `lz10.py` | `ie123kit.nucleo.compresion.lz10` | — | alias directo sin CLI (autotest: `python -m ie123kit.nucleo.compresion.lz10`); **retirado en F2.7** |
| `mods_to_moflex.py` | `ie123kit._legado.mods_to_moflex` | `nucleo.media.moflex` + `nucleo.media.subtitulos_dat` | fachada; **retirado en F2.7** |
| `nds_unpack.py` | `ie123kit._legado.nds_unpack` | `nucleo.contenedores.nds_rom` | **retirado en F2.4**: `ie123 extraer nds` |
| `nftr_metrics.py` | `ie123kit._legado.nftr_metrics` | `nucleo.fuentes.nftr` | fachada; **retirado en F2.7** |
| `patch_smdh_title.py` | `ie123kit._legado.patch_smdh_title` | `nucleo.ejecutable.smdh` | fachada; **retirado en F2.7** |
| `pkb_unpack.py` | `ie123kit._legado.pkb_unpack` | `nucleo.eventos.packnum` + `nucleo.texto.nds_latin` | fachada; **retirado en F2.7** |
| `qna_regions.py` | `ie123kit.nucleo.graficos.qna` | — | alias directo; **retirado en F2.7** |
| `reinsert.py` | `ie123kit._legado.reinsert` | `nucleo.texto.sjis_portador` + `nucleo.texto.tipografia_v20` | fachada; **retirado en F2.7** |
| `reinsert_var.py` | `ie123kit._legado.reinsert_var` | — | **retirado en F2.6**, cuarentena: `python -m ie123kit._legado.reinsert_var --legado-lo-se` |
| `ssd_records.py` | `ie123kit.nucleo.eventos.ssd` | — | alias directo; **retirado en F2.7** |
| `ssd_reinsert.py` | `ie123kit._legado.ssd_reinsert` | — | **retirado en F2.6**, cuarentena: `python -m ie123kit._legado.ssd_reinsert --legado-lo-se` |
| `sszl.py` | `ie123kit.nucleo.compresion.sszl` | — | alias directo; **retirado en F2.7** |
| `ie3_pipeline.py` | `ie123kit.ie3.pipeline` | — | alias directo; **retirado en F2.7**: `python -m ie123kit.ie3.pipeline` |
| `ie3_verificar_offsets.py` | `ie123kit.ie3.comun.verificar_offsets` | — | alias directo; **retirado en F2.7**: `python -m ie123kit.ie3.comun.verificar_offsets` |
| `translate_ui_textures.py` | `ie123kit._legado.translate_ui_textures` | `nucleo.graficos.pintado` | fachada; **retirado en F2.7** |
| `ui_archive.py` | `ie123kit._legado.ui_archive` | `nucleo.contenedores.arcv` + `nucleo.compresion.sszl` | fachada; **retirado en F2.7** |
| `validate.py` | `ie123kit._legado.validate` | — | **retirado en F2.6**, cuarentena: `python -m ie123kit._legado.validate --legado-lo-se` |
| `verify_candidate.py` | `ie123kit._legado.verify_candidate` | `nucleo.validar.candidata` + `ie1.verificar` | **retirado en F2.4**: `ie123 verificar` o `python -m ie123kit._legado.verify_candidate` |
| `dialogue_typography.py` | se queda en `tools/` | re-export `nucleo.texto.ancho_completo` (+ `decode_fullwidth` nuevo) | congelado |
| `build_ie1_probe.py` | se queda en `tools/` | re-export `nucleo.texto.tipografia_v20` | congelado |
| `font_patch.py` | se queda en `tools/` | re-export `nucleo.fuentes.glifos` | congelado |
| `dialogue_lock.py` | se queda en `tools/` | se carga con `nucleo.config.congelados.cargar` | congelado |
| `build_ui_revision.py` | se queda en `tools/` | traslado en `nucleo.construir.candidata` (el original sigue en uso) | congelado |

Los scripts retirados en F1.2 y F1.4 (entre ellos `ie1_tables`, `ie1_media`, `validate_ie1_media`,
`patch_exefs`, `patch_code` y `patch_cro`) estuvieron en `tools/_archivo/` hasta la F2.6 (#55), que borró
esa carpeta: ahora solo están en el historial de git. El motivo de cada retirada, su sustituto y cuáles
son **PELIGROSO: no reutilizar** están en
[`docs/toolkit/SCRIPTS_RETIRADOS.md`](../docs/toolkit/SCRIPTS_RETIRADOS.md), que
`ie123kit.nucleo.compat.superficie.RETIRADOS` mantiene sincronizado (lo comprueba un test).

### Órdenes útiles

- Las invocaciones antiguas pasan a módulo: `python -m ie123kit._legado.fa_unpack` y
  `python -m ie123kit._legado.patch_smdh_title`. Los shims de CLI `nds_unpack`, `harvest_log`, `limpiar_work`,
  `blz` y `verify_candidate` se retiraron en la F2.4 (#50), `ds_roster`, `reinsert_var`, `ssd_reinsert` y
  `validate` en la F2.6 (#55) y los 22 restantes en la F2.7; `ie123 compat equivalencias` da la orden nueva
  de cada uno.
- `python -m ie123kit.ie1.media.voces [--stage]` (sustituye al retirado `ie1_media.py --stage`).
- `python -m ie123kit.nucleo.construir.candidata --base … --ui … --output …`.
- Puerta del bloqueo v20 sobre una candidata: `python -m ie123kit.nucleo.validar.bloqueo --candidata
  <archive.fa>` (o su carpeta). Extrae las 5 fuentes de `dialogue_lock.FONT_HASHES` a un temporal que
  borra al terminar y llama a `dialogue_lock.validate`; devuelve 0 si cuadra y 1 si no.
- Códigos de bigrama recuperables (solo informe, no cambia nada):
  `python -m ie123kit.nucleo.fuentes.liberar --candidata work/shared/candidatas/probe_ie2_v34
  --registro work/ie2/shared/capas/menus_cro/menus/registro.json --base-cro work/shared/base_3ds/romfs/cro
  [--json informe.json]`. Lista los códigos sin uso en los textos de la candidata (eventos, `.STR`, `.dat`
  de `logic/` y `movie/txt/`, CRO) y los grupos de códigos con el mismo dibujo en todas sus fuentes.
  Liberar uno de verdad toca fuentes y textos: necesita una petición explícita del usuario.
- El código nuevo calcula la raíz del repo con `find_root` (`ie123kit.nucleo.config.raiz`) o con la
  variable `IE123_ROOT`.
- Cada objetivo declara sus activos en `activos.toml` (esquema 1: prefijos de `archive.fa`, CRO y rutas de
  solo lectura) en `juego_principal/`, `ie1/`, `ie2/<versión>/` e `ie3/<versión>/`.

## Audio y cinemáticas europeas de IE1

- `python -m ie123kit.ie1.media.voces --stage` (antes `ie1_media.py --stage`): inventaría los SADL de IE1 DS/3DS y prepara los 70
  reemplazos europeos en el mod local de volumen 1.
- `setup_mobipeg.ps1`: descarga y verifica la versión portátil x86 de mobipeg 2.1.
- `python -m ie123kit._legado.mods_to_moflex` (antes `tools/mods_to_moflex.py`): convierte una película `.mods` de DS, incrusta su pista
  española `.dat` y restaura la orientación MOFLEX `0x16` de la recopilación.
- `work/ie1/capas/media/cinematicas/build.py`: genera las 21 cinemáticas europeas de IE1
  (sustituye a `build_ie1_movies.py`, retirado; ver [`SCRIPTS_RETIRADOS.md`](../docs/toolkit/SCRIPTS_RETIRADOS.md)).
- `work/ie1/capas/graficos/titulo_logo` (sustituye a `fix_ie1_title_logo.py`, retirado): aísla el wordmark europeo y sustituye el rótulo
  rectangular anterior conservando el balón y el rayo animados del juego.
- `setup_vgmstream.ps1` + `validate_ie1_media.py` (archivado en F1.4; sus reglas viven en
  `ie123kit.ie1.verificar`): preparan el decodificador
  portátil y comprueban los 70 SADL instalados y las 21 películas sin generar
  WAV ni vídeos temporales. Véase `docs/IE1_AUDIO_CINEMATICAS_V35.md`.

> Los **binarios de terceros no se suben** a este repositorio (ver `.gitignore`,
> carpeta `tools/bin/`). Aquí solo viven nuestros **scripts** y este índice de
> enlaces. Descarga/compila cada herramienta desde su fuente oficial.

## Cadena 3DS (contenedor)

| Herramienta | Para qué | Fuente |
|---|---|---|
| **3dstool** | Extraer/reconstruir NCSD, NCCH, ExeFS, RomFS | https://github.com/dnasdw/3dstool |
| **ctrtool** | Inspeccionar/extraer CIA/NCCH | https://github.com/3DSGuy/Project_CTR |
| **GodMode9** | Volcar/descifrar en consola real | https://github.com/d0k3/GodMode9 |

## Formatos internos de Level-5

| Herramienta | Para qué | Fuente |
|---|---|---|
| **Pingouin** | **Abrir/extraer/reempaquetar archivos `.fa` (XFSA) de Level-5** — es la clave para `archive.fa` | https://github.com/Tiniifan/Pingouin |
| **Nyanko** | Editor de **texto** Level-5 | https://github.com/Tiniifan/Nyanko |
| **CfgBinEditor** | Editar `.cfg.bin` de Level-5 | https://github.com/Tiniifan/CfgBinEditor |
| **Level5ResourceEditor** | Editar `RES.bin` (recursos) | https://github.com/Tiniifan/Level5ResourceEditor |
| **Strikers2013-Tools** | Extraer/importar texto, gráficos, fuentes (referencia) | https://github.com/obluda3/Strikers2013-Tools |

> **Nota:** *Inazuma-Eleven-Toolbox* (SwareJonge) es un **editor de partidas/estadísticas**,
> NO sirve para extraer `.fa` ni traducir. Las herramientas de traducción son las de Tiniifan
> (Pingouin, Nyanko, CfgBinEditor), las mismas que usan las traducciones de la comunidad.
>
> Las apps de Tiniifan son GUI de .NET Framework (4.6.1+). En `tools/bin/` quedan descargadas
> (ignoradas por git): `Pingouin/`, `Nyanko/`. El `archive.fa` de este juego usa el magic
> `B123H` (variante de XFSA): comprobar que Pingouin lo abre.

## Cadena NDS (referencia ES)

| Herramienta | Para qué | Fuente |
|---|---|---|
| **ndstool** | Extraer/reconstruir sistema de archivos NDS | https://github.com/devkitPro/ndstool |
| **Tinke** | Explorar/editar assets NDS (GUI) | https://github.com/pleonex/tinke |

## Parche y pruebas

| Herramienta | Para qué | Fuente |
|---|---|---|
| **xdelta3** | Generar/aplicar el parche `.xdelta` | https://github.com/jmacd/xdelta |
| **Lime3DS / Azahar** | Emulador 3DS para pruebas | https://azahar-emu.org/ |

## Scripts de este repo

- `extract_romfs.ps1` — envoltorio de `ie123 extraer romfs`: ExeFS/RomFS de la ROM 3DS a `work/shared/base_3ds`.
- `extract_nds.ps1` — envoltorio de `ie123 extraer nds`: sistema de archivos de una ROM NDS a `work/<Name>`.
- `build_patch.ps1` — envoltorio de `ie123 parche`: genera `patch/inazuma123-es.xdelta` a partir de la ROM
  original y la traducida.

### Candidatas IE1 por capas (v28 en adelante)
- `dialogue_lock.py` — bloqueo de la tipografía v20 aprobada por el usuario
  (fuentes, codificación fullwidth, métrica 11 px / 220 px). Todo script que
  toque texto lo valida; no desactivarlo.
- `ie123kit._legado.translate_ui_textures` (antes `tools/translate_ui_textures.py`) — aplica un manifiesto JSON de rectángulos de texto a
  texturas CTPK sin cambiar tamaños ni metadatos. Borrado: relleno plano,
  `row_sample`, `bright` o `none` (cuando operaciones previas ya restauraron el fondo).
- `build_ui_revision.py` (congelado; se lanza con `python -m ie123kit.nucleo.compat.congelados
  build_ui_revision …`) — genera una candidata `archive.fa` sobre la anterior:
  eventos SSD con identidad de registros comprobada (`<ui>/events`), capas de
  archivos repetibles (`--extra`, la última gana) y CRO (`--cro`). Nunca
  sobrescribe una candidata existente.
- `ie123 verificar` (antes `verify_candidate.py`, hoy `python -m ie123kit._legado.verify_candidate` para el
  informe detallado) — verificación estática de una candidata frente a su base: entradas de las capas, resto
  del archivo y fuentes idénticos, eventos SSD y literales del CRO permitidos, bloqueo tipográfico.
- `work/ie1/capas/historial/dialogo/v33_mch_story` y `work/ie1/capas/historial/dialogo/v55_pachangas` (sustituyen a
  `build_match_content_patch.py`, archivado en `_archivo/`) — pachangas, cadena de partidos y nombres de
  `team.pkb`/`teamtitle.dat`/`clubinfo.dat`.
- Detalle de la tanda actual y orden completa: `docs/IE1_V29_TANDA.md`.

### Compilar la build
> **Guía completa (requisitos, regeneración de datos, tabla de flags):**
> [`../docs/DESARROLLO.md`](../docs/DESARROLLO.md).

> **Pipeline HISTÓRICO v27.** `build_3ds_var.py` está archivado en `_archivo/` (ver [`_archivo/README.md`](_archivo/README.md)).
> Cadena vigente: `work/ie1/capas/historial/candidata/v33_final/build_rom.py` (ROM IE1), `build_ui_revision.py`
> (candidatas `work/shared/candidatas/probe_ie1_vNN`) e `ie123 verificar`.

Secuencia histórica (CSV → ROM jugable), con los **flags de la build v27**:
```
python tools/reinsert.py                                  # (hoy: python -m ie123kit._legado.reinsert) fuentes (acentos) + roster + UI -> work/archive_es.fa
python tools/reinsert_var.py game1                        # dialogo (long. variable) -> work/eve_var/
SKIP_CRO=1 NO_CODE_PATCH=1 python tools/_archivo/build_3ds_var.py game1   # (archivado) VALIDA y compila -> work/build/*.3ds
pwsh -File tools/build_patch.ps1 -Translated "work\build\inazuma123_es_var.3ds" -Patch "patch\inazuma123-es-vNN.xdelta"
```
`_archivo/build_3ds_var.py` corría `validate.py` ANTES de compilar y **aborta** si hay una
regresion conocida (operandos corruptos, furigana que crece ❌#9, dialogo vacio,
desbalance marcador↔lectura). `SKIP_VALIDATE=1` lo fuerza (solo builds de prueba).
La build v27 = `SKIP_CRO=1` + `NO_CODE_PATCH=1` (el resto de flags por defecto):
gameplay crece a texto completo, sistema/intro INPLACE, fallback global, CRO sin parchear.

### Detección de errores en runtime (cosecha de logs)
La idea: **cada partida deja su rastro de errores en NUESTRO registro**, para ir
detectando qué mejorar en la siguiente versión sin mirar el log en vivo.

- `ie123 registro` (antes `harvest_log.py`) — lee el log de Azahar, agrupa cada error por su **PC**
  (firma estable del bug; la dirección leída varía y se descarta), separa **crashes** (bugs nuestros) del
  **ruido benigno del emulador**, y lo funde en `logs/runtime_errors.json` (persistente) +
  `logs/INFORME_ERRORES.md`. Los PCs ya diagnosticados se anotan en `KNOWN_PCS`
  (`ie123kit.nucleo.construir.registro_azahar`).
  ```
  ie123 registro                  # cosecha el log actual + .old
  ie123 registro --sesion v35     # solo el log actual, marcado con la build
  ie123 registro --forzar         # reprocesa aunque el log no haya cambiado
  ```
  Sin logs nuevos, la orden solo reimprime el informe.
- `jugar.ps1` — lanza la build en Azahar y, **al cerrar el emulador, cosecha
  automáticamente** la sesión. Así el registro se alimenta solo en cada arranque.
  ```
  pwsh -File tools/jugar.ps1 [ruta\build.3ds]   # sin arg: la build más reciente
  ```

> `logs/` está en `.gitignore` (datos locales de la máquina). A GitHub solo van las
> herramientas, no la cosecha.

> Coloca los ejecutables descargados en `tools/bin/` (ignorado por git).

## IE3 Fase 2: referencias y piloto (sin reactivar `--crecer`)

- `python -m ie123kit.ie3.comun.cobertura --perfil spark --salida <carpeta-nueva>`:
  diagnóstico conservador trazable, disponible también para `ogre`.
- `python -m ie123kit.ie3.fase2 auditar --perfil spark --salida <carpeta-nueva>`:
  round-trip JP/ES, referencias del consumidor, correspondencias y simulación
  offline; el mismo núcleo acepta `--perfil ogre`.
- `python -m ie123kit.ie3.fase2 piloto --perfil spark --plan <auditoría> --referencia <archive-v7> --clave <clave-estable> --salida <candidata-nueva>`:
  selección explícita de 1–5 mensajes, compresión/índices/referencias y B123.
- `python -m ie123kit.ie3.comun.build_piloto --candidate <candidata> --visual-manifest <manifest-v7> --rom <salida.3ds>`:
  build completa reutilizando el CRO exacto de referencia y reextracción de ROM.

Se rechazan conflictos, cambios de hash y salidas existentes. No hay activación
masiva hasta la prueba manual. Bomber requiere perfil/corpus/correspondencias
propios, aunque comparta recursos con Spark. Evidencia, límites, comandos y
protocolo en [IE3_FASE2_REFERENCIAS](../docs/IE3_FASE2_REFERENCIAS.md).

## IE3 Fase 4: colocación e interfaz sobre la referencia fase 3

- `python -m ie123kit.ie3.fase4 --referencia <carpeta-fase3> --salida <carpeta-nueva>`:
  prepara la revisión sin modificar tipografía/encoder ni originales.
- El mismo comando con `--verificar`: reextrae registros/recursos y comprueba
  nombres, fuentes y equivalencia oficial de literales Ogre/Spark.
- `python -m ie123kit.ie3.comun.build_piloto --revision --candidate <carpeta-fase4> --visual-manifest <fase3/manifest.json> --rom <salida-nueva.3ds>`:
  exige verificación vigente, construye una ROM completa y relee sus recursos.

La simulación no equivale a validación visual. Contratos, porcentajes separados,
pendientes y comandos completos en [IE3_FASE4_INTEGRACION](../docs/IE3_FASE4_INTEGRACION.md).
