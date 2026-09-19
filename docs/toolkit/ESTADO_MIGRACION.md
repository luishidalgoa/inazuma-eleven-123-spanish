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
- **Bloqueo v20 desactualizado (decisión del usuario).** `FONT_HASHES` de `tools/dialogue_lock.py` no
  coincide con las fuentes de ninguna base actual: la extraída es la original y la v34 lleva espaciado y
  bigramas. Por eso `ie123 construir` rechaza hoy cualquier base con `BLOQUEO_V20`. Los dos tests que lo
  miden están en `xfail` explícito y no se ha tocado ningún fichero bloqueado. `congelados.sha256` no
  cambia.

### Autorrevisión del diff (2026-09-19)

Corregido en la rama:

- las capas nuevas de IE1 ya no se mezclan si se crean dos en el mismo minuto (sufijo `_2`, `_3`…);
- `ie1.aportaciones` entrega todo `romfs/` de la capa, no solo la CRO. Los MOFLEX y SAD importados
  llegan al servicio, que los marca como pendientes en vez de perderlos sin aviso;
- el filtro `subtitles=` de la importación de cinemáticas funciona con rutas de Windows;
- la versión de las capas de `juego_principal` es la de la siguiente candidata, como en IE1;
- se reconoce la ruta de historial de la capa conocida del menú.

Queda abierto para la F2.4 o para decisión del usuario:

- `migrar-juego-principal --simular` escribe `historico.json`. Lo pide el gate de #49, pero choca con
  la regla de que simular no escribe nada;
- `juego_principal._codificar` aplica `approved_layout` y codifica en cp932 los literales del menú.
  No se ha podido comprobar contra la ROM si el transporte debe ser el de ancho completo, así que no se
  ha cambiado;
- con varias capas, las `entradas_fa` no comparten raíz y el servicio las marca como pendientes: aún
  no se funden varias `extra/`;
- una importación que falla deja la carpeta de capa vacía creada;
- `_volcar_toml` no entrecomilla las claves.

### Resultado del gate de F2.3 (2026-09-19, local)

| Punto | Resultado |
|---|---|
| (1) `pytest -m "not requiere_rom"` | 1221 passed, 1 skipped |
| (2) `nucleo.compat.importaciones --baseline …` | 0 nuevos (208 scripts) |
| (3) `pytest tools/tests -m requiere_rom` | 17 passed, 2 skipped (sin ROM .3ds para el parche; sin el PNG de v67), 2 xfail (bloqueo v20) |
| (4) reconstrucción de referencia | `golden comprobar --capa … --referencia` = 0 |
| (5) `work/juego_principal` y `ie123 work limpiar` | existe; no lista base_3ds, fuentes, congelados ni candidatas `.conservar` |
| CI local (toolkit.yml / guardia.yml) | ruff OK, guardia bloqueados/git/todo OK, shims OK, unittest OK, superficie 0 diferencias |

## Pendiente

- **F2.3**: revisión y fusión de la rama `toolkit-f2.3` (la decide el usuario).
- **F2.4 (#50)**: orden `ie123`, scripts finos, retirada de shims de CLI y los motores sin impacto
  tipográfico de [`PLAN_PORTEO_CAPAS.md`](PLAN_PORTEO_CAPAS.md) (paginado 37/131, SPF_, DSP-ADPCM,
  subtítulos, parches de CRO).
- **F2.5 (#51)**: preparación para la GUI, más bigramas, rebanadas y escritura de SMDH/banner, una vez
  decidido el bloqueo v20.
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
