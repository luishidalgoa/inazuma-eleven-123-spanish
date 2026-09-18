# Capas de trabajo (solo código y notas)

Copia de los scripts reutilizables de las capas que viven en `work/` (ignorado por git), para que un
colaborador vea el estado de los formatos de caja de texto y de las herramientas. **Aquí no hay datos del
juego**: ni ROMs, ni ficheros extraídos, ni JSON/PNG/SSD/ARC/BCFNT/CRO/MOFLEX/SAD/PB, ni tablas de texto.
Cada colaborador los regenera desde **su propio volcado** (Norma 2, [`LEGAL.md`](../LEGAL.md)).

## Estructura

La misma que en `work/`, sin el nivel `capas/` intermedio:

| Aquí | Origen en `work/` | Contenido |
|---|---|---|
| `capas/ie1/vNN/...` | `work/ie1/capas/vNN/...` | IE1: v82/v84 saltos de diálogo (22 car. × 3 líneas), v83–v89 bigramas (sonda, fuentes, total, ritmo), v86 ancho de ventana, v90 literales CRO, v91 nombres oficiales, v92 redump del port EU 3DS, v93 cofres |
| `capas/ie2/shared/vNN/...` | `work/ie2/shared/capas/vNN/...` | IE2 común: v01 fuentes y límites CRO, v03 gráficos y textos (CRO, nombres, tablas A/B), v04 CRO restantes, v06/v12/v20/v22 gráficos, v07 media, v08 nombres compactos (bigramas), v09 cofres, v11 subtítulos, v13 ranura/títulos/voz, v14–v15 ancho de diálogo, v17 páginas ≤ 131 B, v18/v20 teclado, v19 saltos a 37, v20 textos/voces, v22 ayuda y menús/objetivos |
| `capas/ie2/tormenta_de_fuego/vNN/...` | `work/ie2/tormenta_de_fuego/capas/vNN/...` | IE2 Fuego: v02 emparejado del diálogo, v03 rótulos y candidata, candidatas v05/v10/v16/v21/v22, v13 inicio (solo previews/validación), v21 tutorial |

Convención de cada capa: `apply.py` (o `build.py`) genera los ficheros de la capa en su carpeta de
`work/`; `validate.py`/`validar.py` la comprueba offline; `previews.py`/`previsualizar.py` dibuja vistas
previas; `comun*.py` son utilidades compartidas. Los scripts importan `ie123kit` desde `tools/src`.

## Cómo ejecutarlas con tu volcado

Los scripts calculan la raíz del repo por su posición (`HERE.parents[N]`) **pensando en su sitio en
`work/`**. Para usarlos, cópialos de vuelta a la ruta de la tabla (p. ej.
`cp -r capas/ie2/shared/v22 work/ie2/shared/capas/v22`) y ejecútalos con
`python -X utf8 work/.../apply.py`.

Rutas de `work/` que esperan (ver [`docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md)):

- `work/ie1/fuentes/nds_es/` — sistema de archivos de la NDS española de IE1 (`tools/nds_unpack.py`).
- `work/ie1/fuentes/3ds_eu/` — textos del port europeo 3DS de IE1 (para v92).
- `work/ie2/tormenta_de_fuego/fuentes/nds_es/` — sistema de archivos de la NDS española de IE2 Fuego.
- `work/shared/candidatas/probe_ie1_vNN/`, `probe_ie2_vNN/` — candidatas (`archive.fa` + `romfs/`
  con las CRO). La primera base es tu `archive.fa` y tu RomFS extraídos de la recopilación 3DS.
- Salidas de cada capa: `extra/`, `ie2/eve/`, `romfs/cro/`, informes `.json` en la carpeta de la capa.

Datos retirados de los scripts porque contienen texto del juego (debes generarlos tú, en local):

- `work/ie2/shared/capas/v22/menus_objetivos/resumenes.json` — `{"objetivo íntegro": ["resumen", ...]}`;
  lo lee `resumenes.py`. Si falta, solo se aceptan objetivos que quepan íntegros.
- `work/ie1/capas/v86/ancho_ventana/cambios.json` — `{"id": [línea1, línea2, intacto]}` para la sonda v86.

## Orden de construcción de la candidata actual (IE2 v22)

Cada candidata parte de la anterior instalada (las capas se acumulan):

1. **IE1** hasta `probe_ie1_v89` (base compartida de fuentes y bigramas; `archive.fa` común).
2. `ie2/tormenta_de_fuego/v02/dialogo/build.py` → `probe_ie2_v02` (base IE1 v89 + diálogo IE2 emparejado).
3. `ie2/tormenta_de_fuego/v03/candidata/build.py` → `probe_ie2_v03` (tandas de texto y rótulos).
4. `ie2/tormenta_de_fuego/v05/candidata/build.py` → `probe_ie2_v05` (fuentes/CRO IE1 v90 + CRO IE2 v04 + gráficos v03).
5. `ie2/tormenta_de_fuego/v10/candidata/build.py` → `probe_ie2_v10` (IE1 v91/v92/v93 + IE2 v05…v09).
6. `ie2/shared/v15/ancho_dialogo/build.py` → `probe_ie2_v15` (ventana de diálogo ancha: 3 parches de CRO).
7. `ie2/tormenta_de_fuego/v16/candidata/build.py` → `probe_ie2_v16` (v13 ranura/títulos/voz + v12 gráficos).
8. `ie2/shared/v17/paginas/build.py` → `probe_ie2_v17` (páginas ≤ 131 B + vídeos subtitulados v11).
9. `ie2/shared/v19/saltos37/build.py` → `probe_ie2_v18` (saltos del diálogo rehechos a 37 caracteres).
10. `ie2/tormenta_de_fuego/v21/candidata/build.py` → `probe_ie2_v21` (v20 teclado/textos/gráficos/voces + tutorial).
11. `ie2/tormenta_de_fuego/v22/candidata/build.py` → `probe_ie2_v22` (v22 menús/objetivos + ayuda + gráficos faltantes).

Antes de cada `build.py`, ejecuta el `apply.py` de las capas que integra (lo indica su docstring).
La v14 fue un paso intermedio sustituido por la v15.

## Límites documentados

- [`docs/FURIGANA_LECCIONES.md`](../docs/FURIGANA_LECCIONES.md): enfoques ya probados en emulador que
  fallaron (Norma 4), límites de ancho del diálogo de IE2 y tope de 131 B por página.
- [`docs/SKILL_volcado-rom-nds.md`](../docs/SKILL_volcado-rom-nds.md): checklist y lecciones del volcado
  desde la NDS española (copia de `.claude/skills/volcado-rom-nds/SKILL.md`, que está ignorado).
- [`docs/FORMATOS.md`](../docs/FORMATOS.md): formatos (SSD, ARCV, .STR, .dat, BCFNT, CRO).

## Scripts no incluidos (contienen texto del juego)

- `ie1/v91/nombres_oficiales/nombres.py` (tabla de nombres y lugares con japonés y frases de contexto);
  lo importan `apply.py` y `validate.py` de v91.
- `ie1/v86/ancho_ventana/simular.py`, `ie1/v83/bigramas/previsualizar.py`,
  `ie1/v88/bigramas_total/previsualizar.py`, `ie1/v89/bigramas_ritmo/previsualizar.py`,
  `ie1/v89/bigramas_ritmo/explora2.py` (vistas previas con frases escritas en el código)
- `ie2/shared/v03/textos/tablas_a/manual_base.py` (redacciones de objetivos y recortes)
- `ie2/shared/v03/graficos/planes_menus.py`, `ie2/shared/v06/graficos/planes_v06.py`,
  `ie2/shared/v12/graficos/planes_v12.py` (planes de texturas con los textos de menús y pantallas);
  sin ellos no funcionan `pintado_menus.py`, `apply6.py` ni `v12/graficos/apply.py`.
- `ie2/tormenta_de_fuego/v13/inicio/apply.py` (diálogos escritos en el código)
- `ie2/tormenta_de_fuego/v01/sonda/build.py` (línea de diálogo japonesa de la sonda)

Los términos cortos que quedan en los scripts (nombres de menú, equipos, marcadores como `ダミー`,
rótulos de celdas de la UI) son del tipo que ya está en `translation/shared/glossary/`.
