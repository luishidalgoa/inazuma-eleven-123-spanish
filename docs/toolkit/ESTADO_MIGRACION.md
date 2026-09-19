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

Ver la sección siguiente; se rellena al cerrar la subfase.

## Pendiente

- **F2.3**: revisión y fusión de la rama `toolkit-f2.3` (la decide el usuario).
- **F2.4 (#50)**: revisión y fusión de la rama `toolkit-f2.4` (después de la F2.3). Queda el punto (4) del
  gate: construir e instalar una candidata completa para la QA en emulador, bloqueado por la decisión #80.
- **F2.5 (#51)**: revisión y fusión de la rama `toolkit-f2.5` (después de la F2.4). Quedan del issue:
  cerrar la épica #40 y abrir el issue de la GUI con la tecnología que elija el propietario, y la QA en
  emulador de una candidata construida con `ie123`.
- Mejoras menores abiertas: #53, #54, #56, #57, #60, #61, #62, #63.
- Limpieza final (#55) después de F2.5.

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
