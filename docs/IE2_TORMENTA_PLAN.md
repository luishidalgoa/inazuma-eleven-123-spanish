# IE2 · Tormenta de Fuego — Fase 0 (inventario, reutilización y plan)

Fecha: 2026-09-16. Alcance: solo análisis; sin build ni instalación. Nada extraído se sube (Norma 2).
Leer antes `CLAUDE.md`, `AGENTS.md`, `docs/ARQUITECTURA.md`, `docs/FURIGANA_LECCIONES.md` y la skill
`volcado-rom-nds` (sección 10).

## 1. Fuentes

| Fuente | Ruta | Estado |
|---|---|---|
| NDS ES Tormenta de Fuego | `Roms/ie2/tormenta_de_fuego/*.nds` (262 MB) | extraída en `work/ie2/tormenta_de_fuego/fuentes/nds_es` (251 MB) con `tools/nds_unpack.py` |
| NDS ES Ventisca Eterna | `Roms/ie2/ventisca_eterna/*.nds` | sin extraer (fase de Ventisca) |
| IE2 3DS europeo | — | **no existe** en `Roms/` (en IE1 fue la mejor fuente de voces y rótulos) |
| Base 3DS japonesa | `work/shared/base_3ds/romfs` (de `Roms/shared/`) | ya extraída; `archive.fa` + CRO + `romfs/inazuma2/**/sound` |

Pendiente en fuentes: `nds_unpack.py` no vuelca `arm9`/`overlay9` ni genera `bin/strings.txt`
(IE1 lo tiene en `work/ie1/fuentes/nds_es/bin`, sin script en `tools/`). Hace falta para los rótulos
de lugar: extraer ARM9/overlays (ndstool vía `tools/extract_nds.ps1`, o ampliar `nds_unpack.py`)
y descomprimir con `tools/blz.py`.

## 2. Datos IE2 dentro de la base 3DS

`archive.fa` tiene 15.547 entradas; 4.885 son `inazuma2/`:

- `inazuma2/data_iz/` = datos comunes **y** de Fuego (versión por defecto).
- `inazuma2/data_iz_blizzard/` = lo que sustituye Ventisca: `script/eve.pkb/pkh`, `movie/op00, a2y01–03`,
  `pic2d/ending/edu00, edu21, edd14, edd15`.
- Fuera del `.fa` (LayeredFS): `romfs/inazuma2/data_iz/sound` (480 SAD + `sound.pb/ph/ph_`) y
  `romfs/inazuma2/data_iz_blizzard/sound` (`BG_END.SAD`, `OP00.SAD`).
- CRO propia: `romfs/cro/ina_main2.cro` (2,7 MB; IE1 usa `ina_main1.cro`).

## 3. Inventario (skill §1 para IE2)

Rutas 3DS relativas a `inazuma2/data_iz/`; rutas NDS relativas a `fuentes/nds_es/data_iz/`.

| Qué | 3DS | NDS ES | Clave | Carpeta work |
|---|---|---|---|---|
| Diálogo de eventos | `script/eve.pkb/pkh` (SSD, 12,6 MB, 2.652 entradas) | `script/sp/evet.pkb/pkh` (texto, 2.598) + `script/sp/eve.pkb` | ID de instrucción (`audit_dialogo_ids`) | `tormenta_de_fuego` |
| Diálogo Ventisca | `data_iz_blizzard/script/eve.pkb` (difiere de Fuego) | NDS Ventisca | ídem | `ventisca_eterna` |
| Pachangas | `script/mch.pkb/pkh` (1,4 MB) | `script/sp/mch.pkb` + `mcht.pkb` (texto) | ID de instrucción, op `0x301d` | `ie2/shared` |
| Acciones / ayuda | `script/act.pkb`, `help.pkb` | `script/act.pkb`, `help.pkb` (sin `sp/`) | índice | `ie2/shared` |
| Objetos de mapa | `script/mr*.mbld/.mdjd` sueltos (462) | `script/sp/mr_mbld.pkb`, `mr_mdjd.pkb` (empaquetados) | nombre de fichero | `ie2/shared` |
| Blog | — (por localizar) | `script/sp/blogpost.dat`, `blogres.dat` | — | `ie2/shared` |
| Hablante / nombre | `logic/unitbase.dat` (230.400 B, +16 corto) | `logic/sp/unitbase.dat` (230.400 B, +32 corto) | índice | `ie2/shared` |
| Rótulo de lugar | `eve.pkb` op `0x4037` arg 3 | `strings.txt` del ARM9 (pendiente) | japonés original | por versión |
| Objetivos | `eve.pkb` op `0x402f` | última línea imperativa NDS | evento | por versión |
| Campos | `logic/fieldinf.dat` | `logic/fieldinf.dat`, `logic01/sp/fieldinf.dat` | índice | `ie2/shared` |
| Títulos / Contactos | `logic/rpgtitle.STR`, `JinmyakuData.dat` | `logic/sp/rpgtitle.STR`, `JinmyakuData.dat` | índice | `ie2/shared` |
| Técnicas / objetos / partidos | `logic/command.STR`, `item.STR`, `games.STR` | `logic/sp/command.STR`, `item.STR`, `logic/games.STR` | ID | `ie2/shared` |
| Equipos | `logic/team.pkb`, `teamtitle.dat` | `logic/sp/team.pkb`, `logic01/sp/team.pkb` | ID | `ie2/shared` |
| Literales del ejecutable | `cro/ina_main2.cro` | ARM9/overlays | referencia en código | `ie2/shared` |
| Fuentes | `font/FONT12, FONT12T, FONT8, RUBI8.NFTR` | `font/*.NFTR` (+ `FONT12N`) | — | bloqueo (ver §5) |
| Texturas UI | `a_menu` (52 .arc), `a_game` (20), `a_field` (7), `a_event` (5), `a_title` (3), `a_common` (4), `a_ending`, `tex3ds_game` | sprites `pic2d/**/sp`, `pic3d/sp` | celda / rectángulo QNA | `ie2/shared` |
| Texturas sustituibles | `a_data_replace/*` (2.494: técnicas, escudos, nombres de escuela, minimapa, ayuda, créditos…) | `pic2d`, `pic3d` | nombre | `ie2/shared` |
| Sprites DS heredados | `pic3d/**/*.pac_` (829), `pic3d/script/c2t*.pac_` | `pic3d/sp/*` | nombre de paquete | `ie2/shared` |
| Voces / música | `romfs/inazuma2/data_iz/sound/*.SAD` (480) | `sound/sp/*.SAD` (479) + `sound.pkb` | nombre | `ie2/shared` |
| Cinemáticas | `movie/*.moflex` (40 Fuego + 4 Ventisca) | `movie/*.mods` (37) + `movie/sp/` (a2m06, a2y01–03, op00) | nombre | `a2y*`/`op00` por versión |
| Subtítulos | `movie/txt/*.dat` (existen en 3DS) | `movie/txt/sp/*.dat` | nombre | `ie2/shared` |

## 4. Diferencias frente a IE1

1. **Dos versiones en un mismo juego**: `data_iz` (Fuego y común) + `data_iz_blizzard` (Ventisca).
   Solo `eve.pkb`, 4 cinemáticas, 4 texturas de créditos y 2 SAD cambian. Todo lo demás va en
   `work/ie2/shared` y `translation/ie2/shared`; el diálogo de eventos, `a2y01–03`, `op00` y el rótulo
   de su evento van por versión.
2. **Tamaño**: `eve.pkb` 3× el de IE1 (12,6 MB frente a 4,2 MB); 2.652 eventos frente a 2.598 en la NDS:
   hay eventos solo 3DS (esperar más «protegidos» y sin fuente).
3. **Texto NDS sin furigana en fichero aparte**: la NDS separa guion (`eve.pkb`) y texto (`evet.pkb`),
   igual que en IE1; y además `mcht.pkb` para pachangas.
4. **CRO propia `ina_main2.cro`**: los literales, el ancho de la ventana y las rutinas de la pestaña del
   nombre de IE1 **no están verificados en IE2**. Las reglas (22 caracteres × 3 líneas, pestaña FONT8,
   rótulo de 10 celdas, objetos de 9) se asumen, pero hay que confirmarlas con una sonda en emulador.
5. **Fuentes NFTR distintas** de las de IE1 (hash diferente en FONT12/FONT8/FONT12T; RUBI8 igual).
   El bloqueo v20 (`tools/dialogue_lock.py`) solo cubre `font/*.bcfnt` y `inazuma1/.../FONT12|FONT8.NFTR`.
6. **Sin 3DS europeo** de IE2: voces ES en formato 3DS y rótulos «grandes» no están disponibles;
   las voces se sacan de los SAD de la NDS (SADL DS: comprobar si el 3DS los acepta tal cual).
7. **Subtítulos**: el 3DS sí trae `movie/txt/*.dat` (IE1 no): quizá no haga falta incrustarlos.
8. **Objetos de mapa** sueltos en 3DS, empaquetados en NDS: necesita emparejar por nombre.

## 5. Tipografía (bloqueo v20)

La v20 se aprobó sobre las fuentes de IE1. Traducir IE2 con ancho completo y el ajuste bloqueado exige
aplicar el mismo parche a las NFTR de `inazuma2/` y añadirlas al bloqueo. **Eso es un cambio de
tipografía y requiere una petición explícita del usuario** (CLAUDE.md). Hasta entonces:
medir con las NFTR originales de IE2 y no tocar fuentes. La autorización del 2026-09-16 (solo espaciado
de glifos latinos, issue #66) es de IE1.

## 6. Reutilización de herramientas

| Herramienta | Veredicto | Qué falta |
|---|---|---|
| `nds_unpack.py` | tal cual | volcar ARM9/overlays (`extract_nds.ps1` o parámetro) |
| `fa_unpack.py` / `FaArchive` | tal cual | `--filter inazuma2/` |
| `pkb_unpack.py`, `ssd_records.py`, `blz.py`, `lz10.py`, `sszl.py` | tal cual | — |
| `audit_dialogo_ids.py` | **parámetro** | rutas de entrada/salida fijas a `work/ie1/legacy/audit_dialogo`; añadir `--juego/--nds/--eve/--out` |
| `ssd_reinsert.py` / `reinsert*.py` | parámetro | rangos protegidos (`92010100..92010509`, `81000040`) son de IE1: localizar los de IE2 |
| `build_ui_revision.py` | **congelado** (bloqueo v20) | rutas `inazuma1/...eve.pk*` e `ina_main1.cro` fijas; usar `ie123kit.nucleo.construir.candidata` con `RUTA_EVE`/`RUTA_MCH` parametrizados, sin tocar el congelado |
| `nucleo/construir/candidata.py` | parámetro | `RUTA_EVE`, `RUTA_MCH` y `cro_principal` fijos a IE1 (la CRO ya admite las cuatro). Toda construcción con `candidata.construir` (también `python -m ie123kit.nucleo.construir.candidata`) sincroniza `usearch.dat` con `unitbase.dat` como paso final por defecto (opt-out nombrado `sincronia_usearch=False` / `--sin-sincronia-usearch`); ver `docs/HARNESS.md` §4 |
| `verify_candidate.py` | casi tal cual | comprueba el CRO por nombre; pasar `ina_main2.cro` |
| `dialogue_lock.py` | **congelado** | solo cubre fuentes IE1 (ver §5) |
| `qna_regions.py`, `translate_ui_textures.py`, `ctpk_ui.py`, `ui_archive.py`, `legacy_sprite.py` | tal cual | formatos ARCV/CTPK/QNA comunes |
| `nftr_metrics.py` | tal cual | pasar `inazuma2/.../FONT12.NFTR` |
| `ds_roster.py`, `build_glossary.py`, `ds_official.py` | parámetro | rutas IE1; `ds_official` no se usa (❌ orden de líneas) |
| `mods_to_moflex.py` | tal cual | — |
| `ie1_media` (`ie123kit.ie1.media.voces`), `ie1_keyboard` | código nuevo pequeño | copiar a `ie2/comun` con listas de IE2 (480 SAD, 44 moflex, `fcode` de IE2) |
| capas IE1 (`medir_rotulos.py`, `crorefs.py`, `piezas_nds.py`, `celdas.py`, `voces/auditoria.py`, `pachangas`) | parámetro | constantes de ruta; mover lo común a `ie2/comun` o parametrizar |
| `limpiar_work.py` | tal cual | — |

Toolkit en pausa: no migrar; solo parametrizar lo que haga falta, en el mismo estilo.

## 7. Plan por fases

| Fase | Contenido | Salida | Dependencias |
|---|---|---|---|
| 0 (#68) | Fuentes, inventario, reutilización (este documento) | este doc | — |
| 1 (#69) | **Diálogo Fuego**: ARM9/strings, `audit_dialogo_ids` parametrizado, pares por ID, protegidos de IE2, reparto 22×3 | `translation/ie2/tormenta_de_fuego` (solo términos), `work/ie2/tormenta_de_fuego/capas/v1/dialogo` | decisión tipográfica (§5) |
| 2 (#70) | **Nombres**: `unitbase` +16/+0, NPC genéricos | capa `nombres` | 1 |
| 3 (#71) | **Rótulos y objetivos** (`0x4037` ≤10 celdas, `0x402f`) | capa `rotulos` | 1 |
| 4 (#72) | **Menús y CRO** (`ina_main2.cro`, `command/item/games/rpgtitle.STR`, `team.pkb`, pachangas `mch`) | capa `cro`, `tablas`, `pachangas` | sonda de límites |
| 5 (#73) | **Texturas** (`a_*`, `a_data_replace`, sprites DS, `.lzs`) | capa `graficos` | — |
| 6 (#74) | **Media** (SAD, 44 moflex, subtítulos) | capa `media` | — |
| 7 (#75) | **Build y QA** (candidata `probe_ie1_vNN` que incluye IE2; protocolo QA como IE1) | candidata + informe QA | 1–6 |

Ventisca Eterna reutiliza las fases 2, 4, 5 y 6 (`ie2/shared`) y repite solo 1, 3 y sus cinemáticas.

**Primera fase recomendada:** antes de la 1, pedir al usuario la decisión de tipografía para IE2 (§5)
y hacer una sonda mínima en emulador que confirme en `ina_main2.cro` los límites de caja, pestaña
y rótulo. Luego, fase 1.
