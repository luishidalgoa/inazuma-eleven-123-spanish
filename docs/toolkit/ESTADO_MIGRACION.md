# Estado de la migración a ie123kit — REANUDADA (2026-09-19)

Se pausó el 2026-09-16 y el usuario pidió reanudarla el 2026-09-19.

## Hecho y cerrado en `main`

| Subfase | Issue | Commit |
|---|---|---|
| F1.0 línea base | #41 | `e87b084` |
| F1.1 esqueleto del paquete | #42 | `e66f54a` |
| F1.2 archivar retirados | #43 | `4d197ad`, `71c8146` |
| F1.3 motor a `nucleo` | #44 | `5c894f0`…`0af2abd` |
| F1.4 reparto por juego | #45 | `ba0e25f` |
| F1.5 CI y cierre de fase 1 | #46 | `cd5db31`, `a615aff`, `d4618bb` |
| F2.1 servicio y tipos | #47 | `79edbb6` |
| F2.2 primitivas y CLI mínima | #48 | `19805d7`, `c0fd108` |

## F2.3 (#49): en la rama `toolkit-f2.3`, pendiente de revisión

- El trabajo a medias (`bd7aeb2`, guardado en la etiqueta `archivo/toolkit-f2.3-wip`) está rebasado sobre
  `main`. Solo hubo un conflicto, en `docs/ARQUITECTURA.md` (regla 1: cinco ámbitos + capas por tema).
- Adaptado a la **reorganización de capas por juego y tema** (`work/<juego>/capas/<tema>/<linea>` y
  `historial/<tema>/vNN_<linea>`):
  - `nucleo.construir.capas`: `ubicacion()` y `listar_capas()`. `Capa` deduce `tema`, `version` y `linea`
    de las tres disposiciones: vigente, historial y la antigua `vNN/`.
  - Las capas que crean las acciones van a su tema: IE1 `gui`→`graficos`, `eventos`→`dialogo`,
    `tablas`→`nombres`, `cro`→`menus_cro`, `cinematicas`/`voces`→`media`. Las de `juego_principal` van a
    `graficos`. La versión va en `capa.toml`.
  - `aportaciones()` y el índice de `migrar-juego-principal` recorren la disposición nueva. En las
    aportaciones, `historial/` no cuenta.
  - Se han actualizado las rutas `capas/vNN` de `limpieza.py`, los docstrings, `tools/README.md` y
    `tools/_archivo/README.md`, siguiendo `work/shared/reorganizacion_capas.json`.
- **Comprobador de importaciones:** ahora resuelve `import ie123kit…` de las capas contra `tools/src`,
  incluidas las fachadas perezosas con `__getattr__`. Antes daba 86 falsos «no resuelto». Hoy da
  0 nuevos.
- **Golden y gates sin las candidatas borradas** (v66/v67). La nueva referencia solo necesita `work/`:
  - base: `work/shared/base_3ds/romfs` (la extracción de la ROM);
  - capa: `work/ie1/capas/graficos/titulo_logo` (la antigua v67), con `extra/` igual al golden anterior
    (`7de9bcc…`);
  - gate 3: la capa se regenera en un temporal con `texturas.apply_plan` sobre la base, byte a byte.
    El `apply.py` original necesitaba v66 y un PNG de Descargas, que ya no existen;
  - gate 4: base + capa con `build_ui_revision.py` o con `construir` da `archive.fa` `6f23e4d5…d7f1`.
    Solo cambia `title_t.arc`;
  - `candidatas.sha256` vigila `base_3ds` y la candidata vigente `probe_ie2_v34`;
  - `verify_candidate` tiene golden nuevo (`verify_referencia.json`). Informa de 1 entrada
    sustituida y 22 fuentes idénticas, y `dialogue_lock` da PASS.
- **Bloqueo v20 desactualizado**: resuelto en la F2.5 (#80, ver abajo).

### Autorrevisión del diff (2026-09-19)

Corregido en la rama:

- las capas nuevas de IE1 ya no se mezclan si se crean dos en el mismo minuto (sufijo `_2`, `_3`…);
- `ie1.aportaciones` entrega todo `romfs/` de la capa, no solo la CRO. Los MOFLEX y SAD importados
  llegan al servicio, que los marca como pendientes en vez de perderlos sin aviso;
- el filtro `subtitles=` de la importación de cinemáticas funciona con rutas de Windows;
- la versión de las capas de `juego_principal` es la de la siguiente candidata, como en IE1;
- se reconoce la ruta de historial de la capa conocida del menú.

Quedaba abierto; todo menos `_codificar` se corrigió en la F2.5 (ver abajo):

- ~~`migrar-juego-principal --simular` escribe `historico.json`~~;
- `juego_principal._codificar` aplica `approved_layout` y codifica en cp932 los literales del menú.
  No se ha podido comprobar contra la ROM si el transporte debe ser el de ancho completo, así que no se
  ha cambiado (sigue abierto);
- ~~con varias capas no se funden varias `extra/`~~;
- ~~una importación que falla deja la carpeta de capa vacía creada~~;
- ~~`_volcar_toml` no entrecomilla las claves~~.

### Resultado del gate de F2.3 (2026-09-19, local)

| Punto | Resultado |
|---|---|
| (1) `pytest -m "not requiere_rom"` | 1221 passed, 1 skipped |
| (2) `nucleo.compat.importaciones --baseline …` | 0 nuevos (208 scripts) |
| (3) `pytest tools/tests -m requiere_rom` | 17 passed, 2 skipped (sin ROM .3ds para el parche; sin el PNG de v67), 2 xfail (bloqueo v20) |
| (4) reconstrucción de referencia | `golden comprobar --capa … --referencia` = 0 |
| (5) `work/juego_principal` y `ie123 work limpiar` | existe; no lista base_3ds, fuentes, congelados ni candidatas `.conservar` |
| CI local (toolkit.yml / guardia.yml) | ruff OK, guardia bloqueados/git/todo OK, shims OK, unittest OK, superficie 0 diferencias |

## F2.4 (#50): en la rama `toolkit-f2.4` (PR apilado sobre `toolkit-f2.3`), pendiente de revisión

- **CLI `ie123` completa** (adaptador 1:1 de `ServicioToolkit`): `extraer romfs|nds`, `verificar`,
  `instalar`, `registro` (antes `harvest_log.py`), `compat comprobar [--golden]`, `compat equivalencias`,
  `motor listar|paginar|teclado|cro-ancho-dialogo|voces|subtitulos`, además de las de F2.2/F2.3. Alias en
  inglés de todos los verbos. Un aviso no cambia el código de salida.
- **Servicio**: `extraer`, `compat`, `registro`, `equivalencias`, `motores`, `motor` (tabla `MOTORES`, import
  dinámico) y un `doctor` completo (Python, dependencias, herramientas externas, ficheros bloqueados, ROM
  configuradas y espacio libre). Código de incidencia nuevo: `GATE_FALLIDO` (esquemas actualizados).
- **Gates** (`nucleo.compat.gates`): bloqueados, congelados e importaciones; con `--golden`, capa de
  referencia, candidatas, reconstrucción de referencia y bloqueo de la candidata vigente. Este último falla
  por la decisión #80 y se informa como aviso («fallo conocido»); `BLOQUEO_PENDIENTE` lo controla.
- **Scripts finos**: `build_patch.ps1`, `extract_romfs.ps1` y `extract_nds.ps1` son envoltorios de una orden;
  `jugar.ps1` cosecha con `ie123 registro` y ya no busca `work\build` ni `roms\*ES*` (rutas obsoletas).
  Las rutas por defecto de la ROM japonesa se corrigieron al nombre real de `Roms/shared/`.
- **Shims de CLI retirados**: `verify_candidate`, `nds_unpack`, `blz`, `harvest_log` y `limpiar_work`
  (`shims.RETIRADOS`). El comprobador AST confirma que ninguna capa los importa; sus módulos siguen en
  `ie123kit._legado`. Quedan 24 shims de importación. La retirada la aprueba el propietario en el PR.
- **Motores portados** (ver [`PLAN_PORTEO_CAPAS.md`](PLAN_PORTEO_CAPAS.md)): paginado 37 × 3 / 131 B, SPF_ y
  teclado, DSP-ADPCM + Procyon + sound.pb, subtítulos incrustados y parches de CRO con comprobación de
  relocalizaciones, parametrizados por juego (IE1/IE2, listos para IE3). Equivalencia byte a byte con las
  salidas vigentes de las capas (`tests/requiere_rom/test_equivalencia_motores_ie2.py`).

### Resultado del gate de F2.4 (2026-09-19, local)

| Punto | Resultado |
|---|---|
| (1) `pytest -m "not requiere_rom"` (incluye la validación de las salidas `--json` contra el esquema) | 1318 passed, 1 skipped |
| `pytest -m requiere_rom` | 26 passed, 2 skipped (sin ROM parcheada; sin el PNG de v67), 2 xfail (bloqueo v20, #80) |
| CI local (toolkit.yml / guardia.yml) | ruff OK, guardia bloqueados/git/todo OK, 24 shims sin lógica, unittest OK |
| (2) `ie123 compat comprobar --golden` | 0 (7 gates; `bloqueo_candidata` como aviso conocido #80) |
| (3) `ie123 doctor` | 0 (aviso: no se localiza `mobipeg`) |
| (4) QA en emulador con `ie123 construir` + `ie123 instalar` | **pendiente** de la prueba del usuario; desde la F2.5 (#80) `construir` ya acepta la base v34 |

## F2.5 (#51): en la rama `toolkit-f2.5` (PR apilado sobre `toolkit-f2.4`), pendiente de revisión

- **Bloqueo tipográfico actualizado (#80, cerrado).** Autorización explícita del usuario (2026-09-19):
  «sí, actualiza las huellas a la actual versión que tiene un motor de textos de calidad».
  `FONT_HASHES` de `tools/dialogue_lock.py` son las fuentes de `probe_ie2_v34`: FONT12 `2e231267…`,
  FONT12T `eb2a12cc…` y FONT8 `bec491a0…`. Las NFTR de IE1 no cambian. `congelados.sha256` se recapturó
  solo para `dialogue_lock.py` y `BLOQUEO_PENDIENTE = False`. Los dos `xfail` pasan y `ie123 construir`
  acepta la base v34. Las NFTR propias de IE2 (`inazuma2/data_iz/font/FONT12|FONT8.NFTR`, que cambió la
  capa ie2 `fuentes`) **no** entran en el bloqueo: lo decide el propietario. **Pendiente del usuario**: la
  nota del bloqueo en `AGENTS.md` y `CLAUDE.md` sigue diciendo «v20». Son instrucciones de agente y no se
  han tocado sin una petición directa del usuario.
- **API de servicio 1.0 para la GUI**: `API_VERSION = "1.0"`, esquemas con `examples`, esquemas
  `datos_*` por método, `servicio.contrato` (`METODOS`, `TypedDict` de `datos`, `compatible`,
  `validar_resultado`) y [`API_SERVICIO.md`](API_SERVICIO.md). `instalar` usa ya `[azahar] mods_dir` /
  `IE123_AZAHAR`: antes caía siempre en la carpeta por defecto por un `TypeError` silenciado.
- **Clientes sin cabeza**: `tests/contrato/test_flujo_gui.py` (sintético, en CI) y
  `tests/requiere_rom/test_flujo_gui_real.py`. El real recorre exportar → editar un píxel → importar
  simulado → capa `gui_*` → construir sobre v34 con el bloqueo real → verificar. Solo difiere
  `title_t.arc` y el test borra todo lo que crea.
- **Motores de fuentes portados** (#3, #4 y #8 del [plan](PLAN_PORTEO_CAPAS.md)), con equivalencia byte a
  byte: bigramas y ritmo DP de IE1 v89, menús del CRO de IE2 v23, y banner/SMDH. Ninguna fuente cambia.
- **Herramienta `nucleo.fuentes.liberar`** (solo informe): sobre v34, 0 códigos sin uso y 22 grupos de
  celdas duplicadas, es decir, 22 códigos recuperables.
- **Restos de la F2.3**: `--simular` ya no escribe; varias `extra/` se funden como entradas sueltas en
  orden; una importación fallida borra su capa; `_volcar_toml` entrecomilla las claves.

### Resultado del gate de F2.5 (2026-09-19, local)

| Punto | Resultado |
|---|---|
| (1) `pytest -m "not requiere_rom"` (incluye `test_flujo_gui` sintético y los ejemplos de los esquemas) | 1395 passed, 1 skipped |
| (2) `nucleo.compat.importaciones --baseline …` | 0 nuevos (208 scripts) |
| (3) `pytest -m requiere_rom` (incluye `test_flujo_gui_real` y la equivalencia de fuentes, menús y banner) | 36 passed, 2 skipped (sin ROM parcheada; sin el PNG de v67), **0 xfail** |
| `ie123 compat comprobar --golden` | 0 (7/7 gates; `bloqueo_candidata` pasa sobre v34) |
| `ie123 doctor` | 0 (aviso: no se localiza `mobipeg`) |
| CI local (toolkit.yml / guardia.yml) | ruff OK, guardia bloqueados/git OK, 24 shims sin lógica, unittest OK |
| QA en emulador | pendiente del usuario |

## F2.6 (#55): limpieza final, en la rama `toolkit-f2.6-limpieza` (PR apilado sobre `toolkit-f2.5`)

### 1. Las capas activas ya no duplican el motor

Cada capa vigente que tenía motor copiado (o que lo cargaba de una capa de `historial/` con `importlib`)
es ahora un **envoltorio fino** de `ie123kit` que conserva intacta su superficie pública, la que usan sus
`apply.py`/`validate.py` hermanos. Las capas de `historial/` **no se han tocado**, y no se ha borrado ni un
dato de capa (candidatas, `extra/`, `romfs*/`, `informe.json`, registros: todo intacto).

| Módulo de capa | Líneas | De dónde viene ahora el motor |
|---|---|---|
| `ie2/…/dialogo/saltos37/comun19.py` | 103 -> 105 | `nucleo.texto.paginado` + `ie2.comun.dialogo`; ya no carga `comun17` de `historial/dialogo/v17_paginas` |
| `ie1/capas/dialogo/motor_unificado/comun94.py` | 138 -> 156 | `nucleo.texto.paginado`, `ie1.texto.dialogo.MODELO_IE1_ANCHO` y `ie1.texto.cro` (antes `PARCHES`/`CONTEXTO` a mano); ya no carga `comun17` de `historial/` |
| `ie2/…/media/subtitulos/comun_sub.py` | 151 -> 116 | `nucleo.media.subtitulos` + `ie2.comun.subtitulos` |
| `ie2/…/media/voz_titulo/dsp_adpcm.py` | 347 -> 18 | `nucleo.media.dsp_adpcm` (codificador completo, 17 funciones privadas incluidas) |
| `ie2/…/media/voz_titulo/sonido.py` | 246 -> 79 | `nucleo.contenedores.sound_pb` + `nucleo.media.procyon` |
| `ie2/…/media/media/bancos.py` | 134 -> 134 | el cuerpo de sus 3 lectores pasa a delegación en `sound_pb`; se queda la política de capa |
| `ie2/…/graficos/ayuda/apply.py` | 267 -> 160 | `ie2.comun.ayuda` + `nucleo.graficos.regiones` |
| `ie2/…/graficos/ayuda/ayuda22.py` | 67 -> 63 | `ie2.comun.ayuda` (`capturas`, `captura_nds`, `ModeloAyuda`) |
| `shared/capas/graficos/banner_home/apply.py` | 141 -> 129 | `juego_principal.banner` (`construir_banner`, `construir_icono`, `textura`, `TITULO`) |
| `ie1/capas/graficos/smdh/apply.py` | 156 -> 159 | importa `nucleo.ejecutable.smdh` directamente (antes el shim plano) y usa sus `CAMPOS_TITULO` |

Los dos módulos de diálogo crecen un poco en líneas porque el envoltorio documenta de dónde sale cada
límite y adapta firmas; lo que desaparece es la **segunda implementación**, que era el problema.

Detalle que costaba un fallo silencioso: los lectores de SWD de DS delegan con `alinear=1` (la lectura sin
alinear de la v13, que es la que produjo la salida vigente). El valor por defecto del paquete es 16 (la
corrección de la v20) y habría cambiado bytes.

### 2. Dos motores más portados (cerraban el plan)

El usuario pidió que dos motores que seguían siendo solo de capa pasaran al paquete, parametrizados por
juego y con golden byte a byte. Detalle en [`PLAN_PORTEO_CAPAS.md`](PLAN_PORTEO_CAPAS.md):

- **Capturas de ayuda de IE2**: `nucleo.graficos.regiones` (diferencia de zonas, igualación de color por
  canal, encaje, pegado escalado, caja de contenido), `nucleo.graficos.pac_sprite.decodificar_pac8` y
  `ie2.comun.ayuda` (`ModeloAyuda`, `captura_arc`, `PESTANAS`, `pestanas_arc`), con la traducción de las
  pestañas. Orden `ie123 motor ayuda`.
- **Grito del título del recopilatorio**: banco `CM_000.SWD`/`.SED` con la muestra 162 y el cambio de
  duración de la nota de la secuencia (`nucleo.media.voz`, `nucleo.media.procyon.nota_con_ticks` /
  `sed_con_ticks`, `juego_principal.voz_titulo`). Orden `ie123 motor voz-recopilatorio`.
- **Tabla de parches de la CRO de IE1**, que se había quedado en `comun94.py`: `ie1.texto.cro` sobre
  `nucleo.ejecutable.parches_cro`, más `ie1.texto.dialogo.MODELO_IE1_ANCHO` (37 × 3, 131 B, 247 B).

Ya estaban cubiertos y solo hacía falta rewirar la capa: el **audio del banner** (BCWAV dentro del CBMD) y
la **textura del logo** en `juego_principal.banner`, y los **títulos del SMDH** en `nucleo.ejecutable.smdh`.

### 3. Limpieza de `tools/`

- **`tools/_archivo/` borrado** (29 scripts + 2 tests): el contenido sigue en el historial de git y el
  motivo de cada retirada, su sustituto y los marcados **PELIGROSO: no reutilizar** pasan a
  [`SCRIPTS_RETIRADOS.md`](SCRIPTS_RETIRADOS.md), que era lo que había que conservar. Un test comprueba que
  ese documento y `nucleo.compat.superficie.SCRIPTS_RETIRADOS` dicen lo mismo.
- **4 shims planos retirados**: `ds_roster`, `reinsert_var`, `ssd_reinsert` y `validate`. La ESPECIFICACION
  los conservaba por ser «transitivos desde `reinsert`», pero las fachadas de `_legado` se importan entre
  sí por `ie123kit._legado.<mod>`, nunca por el nombre plano, así que el shim no participaba. Quedan **20**
  shims (eran 24). Sus módulos siguen en `_legado`, en cuarentena.
- **Los 10 shims que NO se pueden retirar**: `lz10`, `fa_unpack`, `fa_repack`, `pkb_unpack`, `ssd_records`,
  `reinsert`, `bcfnt`, `dialogue_typography`, `dialogue_lock` y `font_patch` los importan **por nombre
  plano los ficheros congelados** del bloqueo tipográfico (`build_ie1_probe`, `build_ui_revision`,
  `font_patch`). Retirarlos exigiría editar ficheros congelados, así que se quedan mientras exista el
  bloqueo. Los demás los importan entre 1 y 50 capas vivas.
- **Gate `superficie comprobar` arreglado**: arrastraba **5 diferencias desde la F2.4** («módulo ausente»
  para `blz`, `nds_unpack`, `harvest_log`, `limpiar_work` y `verify_candidate`), porque los shims retirados
  entonces no estaban en ninguna lista. Ahora `RETIRADOS()` suma los scripts borrados y
  `shims.RETIRADOS`: **0 diferencias**.
- `_archivo` fuera de las exclusiones de ruff/black de `tools/pyproject.toml` y del comentario de la CI.

### 4. Lo que NO se ha tocado, a propósito

- **Bloqueo tipográfico**: ni un hash. `FONT_HASHES`, `congelados.sha256` y los 5 ficheros congelados
  siguen como los dejó la F2.5 (v34, autorizado por el usuario el 2026-09-19).
- **`historial/`**: ninguna capa congelada se ha modificado, y su existencia no ha servido de excusa para
  dejar código duplicado en las capas vivas.
- El marcador `.conservar` de `probe_ie1_v66`/`v67` que menciona el issue #55: esas candidatas **ya no
  existen** (se borraron antes de la F2.3) y el golden dejó de depender de ellas en la F2.3. No queda nada
  que retirar.

### Resultado del gate de F2.6 (2026-09-20, local)

| Punto | Resultado |
|---|---|
| (1) `pytest -m "not requiere_rom"` | PENDIENTE |
| (2) `nucleo.compat.importaciones --baseline …` | PENDIENTE |
| (3) `pytest -m requiere_rom` | PENDIENTE |
| (4) `ie123 compat comprobar --golden` | PENDIENTE |
| (5) `ie123 doctor` | PENDIENTE |
| CI local (toolkit.yml / guardia.yml) | PENDIENTE |
| QA en emulador | pendiente del usuario |


## Pendiente

- **F2.3**: revisión y fusión de la rama `toolkit-f2.3` (la decide el usuario).
- **F2.4 (#50)**: revisión y fusión de la rama `toolkit-f2.4` (después de la F2.3). Queda el punto (4) del
  gate: construir e instalar una candidata completa para la QA en emulador, bloqueado por la decisión #80.
- **F2.5 (#51)**: revisión y fusión de la rama `toolkit-f2.5` (después de la F2.4). Queda del issue la QA
  en emulador de una candidata construida con `ie123`.
- **F2.6 (#55)**: revisión y fusión de la rama `toolkit-f2.6-limpieza` (después de la F2.5).
- Mejoras menores abiertas: #53, #54, #56, #57, #60, #61, #62, #63.
- **Decisiones que siguen siendo del propietario**, no del agente: abrir el issue de la GUI con la
  tecnología que elija; si se liberan los 22 códigos de celdas duplicadas del registro de bigramas (toca
  tipografía); si las NFTR propias de IE2 entran en el bloqueo; y la QA en emulador.

## Cómo se reanuda cada subfase

Con la rama de la subfase sobre `main`:

```
python -X utf8 -m pytest tools/tests -m "not requiere_rom" -q
python -X utf8 -m ie123kit.nucleo.compat.importaciones --work work --baseline tools/tests/compat/baseline_importaciones.json
python -X utf8 -m pytest tools/tests -m requiere_rom -q -rsx
python -X utf8 -m ie123kit.nucleo.compat.golden comprobar --capa work/ie1/capas/graficos/titulo_logo --referencia
```

Si se borra `probe_ie2_v34`, hay que cambiar `golden.CANDIDATA_VIGENTE` y ejecutar
`python -m ie123kit.nucleo.compat.golden capturar`. Esa orden solo reescribe hashes. Hay que revisar
que `congelados.sha256` no cambie.
