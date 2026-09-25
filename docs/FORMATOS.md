# Notas técnicas sobre formatos

## ROM 3DS — Inazuma Eleven 1·2·3 (objetivo)

- Contenedor: **NCSD** (`.3ds`, volcado de cartucho), **descifrado**
  (flag NoCrypto activo en la NCCH → no hacen falta claves de consola).
- Partición 0 (CXI/NCCH): offset `0x4000`, ~1825 MB. Producto `CTR-P-AETJ`.
- Dentro de la NCCH:
  - **ExeFS**: código y banner.
  - **RomFS**: árbol de archivos del juego → **aquí está casi todo el texto y los assets**.
- Formatos internos de Level-5 esperados (a confirmar al extraer):
  - `.cfg.bin` — binarios de configuración/datos (incluyen cadenas). Editor: **CfgBinEditor** / **Nyanko**.
  - Archivos de texto/script propios, fuentes y gráficos empaquetados.

## ROMs NDS de referencia (oficiales en ES)

- Inazuma Eleven 1 (`YEES`) y 2 (`BEES`): formato **NDS** clásico.
- Sistema de archivos extraíble con **ndstool** / Tinke / similar.
- Sirven como **fuente de terminología oficial** (no como texto trasplantable
  directo: el motor y la codificación del 3DS son distintos).

## Estrategia de emparejado (matching) — juego 1

El primer juego del collection 3DS es el remaster del Inazuma Eleven 1 de DS.
Plan: generar un **mapa de cadenas** de ambos (NDS ES y 3DS JP), alinear por
orden/escena/ID y producir una tabla `id_3ds ↔ texto_es` para volcar la
traducción oficial con mínimos retoques.

> Si se consigue la versión **3DS PAL (ES)** del juego 1 (mismo motor que el
> collection), el emparejado pasa a ser casi 1:1 a nivel de archivo.

## Formato del contenedor `archive.fa` (magic `B123`) — DECODIFICADO

Es una **variante del formato ARC0/XFSA de Level-5**, pero con las **tablas SIN
comprimir** y entradas de directorio de **24 bytes** (ARC0 usa 20 y comprimidas).
Por eso las herramientas de la comunidad (Pingouin/StudioElevenLib) **no lo abren**:
solo aceptan los magics `ARC0/XFSA/XFSP/XPCK`. → Parser propio: `ie123kit._legado.fa_unpack`.

**Cabecera (72 bytes):**
| Offset | Tipo | Campo |
|---|---|---|
| 0x00 | char[4] | Magic = `B123` |
| 0x04 | u32 | DirectoryEntriesOffset (= 0x48) |
| 0x08 | u32 | DirectoryHashOffset |
| 0x0C | u32 | FileEntriesOffset |
| 0x10 | u32 | NameTableOffset |
| 0x14 | u32 | DataOffset |
| 0x18 | u16 | DirectoryEntriesCount |
| 0x1A | u16 | DirectoryHashCount |
| 0x1C | u32 | FileEntriesCount |

**DirectoryEntry (24 bytes):** crc32(4), fileCount(u16), subdirCount(u16),
fileNameBaseOffset(u32), firstFileIndex(u32), firstSubdirIndex(u32),
dirNameOffset(u32). **FileEntry (16 bytes):** crc32(4), nameOffset(u32, relativo a
fileNameBase), dataOffset(u32, relativo a DataOffset), size(u32).

Los archivos internos pueden estar **crudos** o con compresión Level-5
(None/LZ10/Huffman4/Huffman8/RLE/ZLib; cabecera de 4 B: 3 bits método + 29 bits
tamaño). `ie123kit._legado.fa_unpack` detecta cuál es por magic/plausibilidad.

## Mapa de contenido (15.547 archivos) y dónde está el TEXTO

- `import/sItx*.itx` → ficheros de **parámetros** (`cImportTxt2Data`: offsets de
  fuente/ventanas), **NO** diálogo. Texto plano con macros `_PARAM_`.
- `message/jp/GameString.bin` (+`.tbl`) → **cadenas de sistema/UI en UTF-8**,
  separadas por NUL (ej.: "ニューゲーム"=Nueva partida). ✅ traducible directo.
- `inazumaN/data_iz/a_field/field_message*.arc` → **mensajes/diálogos**, dentro de
  contenedores **ARCV** (formato clásico de Level-5 de la era DS).
- Miles de `.arc` (XPCK/ARCV) con datos de menús, técnicas, jugadores, etc.

> **Encoding clave:** el 3DS usa **UTF-8** (las NDS usaban Shift-JIS). El uso de
> contenedores **ARCV** sugiere que el remaster reutiliza estructuras de los juegos
> de DS → posible emparejado favorable con el texto español oficial.
>
> **Pendiente (siguiente fase):** parsear ARCV y el formato interno de los
> message-bin para volcar los diálogos a formato editable.

## Emparejado JP (3DS) ↔ ES (NDS) — vía `data_iz/logic/`

**Hallazgo clave:** el 3DS conserva en `inazuma1/data_iz/logic/` **los mismos
ficheros que el NDS** (`item.STR`, `command.dat`, `games.STR`, `unitbase.dat`…).
`unitbase.dat` mide **230400 bytes en ambos** → misma estructura de registros,
solo cambia el idioma. Esto permite **alinear por índice/registro** el japonés del
3DS con el castellano oficial del NDS.

**Formato `.STR`:** 32 bytes de cabecera (ceros) + pool de cadenas separadas por
`NUL`. Encodings distintos:
- **3DS**: Shift-JIS, con **furigana** `[kanji/lectura]` (p.ej. `[水/みず]`).
- **NDS (ES)**: codificación **Latin propia** con bytes especiales para acentos/ñ
  y códigos de control. Tabla parcial inferida (ampliar):
  `0xC2→ñ, 0xDF→¡, 0xBA→é, 0xC4→ó, 0xB2→á`.

**Estado del emparejado (item.STR, juego 1):** las primeras ~10 cadenas alinean
perfectamente (descripciones de objetos), pero los recuentos difieren
(3DS=300, NDS=603 ≈ el NDS intercala nombre+descripción). → El alineado por
posición es solo un punto de partida; el exacto necesita el **índice del `.dat`**
asociado (`item.dat` → offsets dentro del `.STR`). Herramienta histórica: `str_align.py` (retirada, ver [`SCRIPTS_RETIRADOS.md`](toolkit/SCRIPTS_RETIRADOS.md)): emparejaba por índice de forma ingenua (300 frente a 603); su tabla `NDS_FIX` queda superada por el futuro `nucleo/texto/nds_latin` de ie123kit.

### Formatos de registro resueltos (juego 1)

- **`unitbase.dat`** (jugadores): registros de **96 bytes**, nombre (kanji) en
  `+0` (16 B) y lectura kana en `+16`. Mismo tamaño/orden en 3DS y NDS →
  emparejado por índice (verificado: 円堂守→Mark Evans). 2400 registros.
- **`unitbase.STR`** (descripciones de perfil, 161.440 B): 1.040 textos Shift-JIS
  con furigana, alineados a **32 bytes** y rellenos con NUL (huecos de 32/64/96/128 B).
  Cada registro de `unitbase.dat` apunta a su descripción con un **u16 en `+94`
  en unidades de 32 bytes** (`offset = u16 × 32`; verificado en Mark, Nathan, Jack…).
  Los 1.034 textos con salto usan exactamente **dos líneas**. Se traducen en su
  propio hueco, sin mover offsets (`work/ie1/legacy/desc_revision/apply.py`).
- **`team.pkb`** (nombres de equipo): registros de **320 bytes**, nombre en un campo
  fijo de 32 bytes en `+0`. Nombres oficiales ES confirmados en el diálogo NDS:
  Occult, Brain, Farm, Inazuma Kids FC.
- **Pantalla VS**: los nombres no salen de `team.pkb`, sino de texturas CTPK en
  `a_data_replace/vs_school_name` (placas 128×32 con furigana), `pk_school_name`
  (placas 64×16, 48 px útiles; `t001p1/p2` son variantes resaltadas con fondo negro)
  y `vs_stage_select` (rótulos 512×128 de campo sobre panel naranja y banda oscura).
  `vs_stage_select_cg` y `formation_name_plt` no contienen texto.
- **`command.dat`/`command.STR`** (técnicas): 3DS 24 B por registro con punteros
  u16 (×32) a nombre y descripción en `+16`; NDS 28 B con el mismo par en `+20`.
  El índice de registro es el ID de técnica en ambas versiones y coincide con el
  número de los rótulos `command_technique/ie01_command_tec_bcNNN/bgNNN`.
  Nombres en huecos de 32 B (15 caracteres en ancho completo).
- **`item.dat`/`item.STR`** (objetos): 3DS 32 B (nombre 19 B = 9 caracteres en ancho
  completo, descripción u16×32 en `+30`); NDS 48 B (nombre 32 B, descripción en `+46`).
  Mismo índice en ambas versiones.
- **`teamtitle.dat`** (títulos de equipo): registros de **16 bytes**, nombre@+0.
- **`games.STR`** (menús): mismo nº de cadenas en 3DS y NDS → índice 1:1.
- **`item.dat`** / **`command.STR`**: el orden NO casa 1:1 entre plataformas
  (3DS item.dat=16384 B vs NDS=49152; recuentos de `.STR` distintos). Pendiente
  parsear su índice real.

### Tabla de codificación NDS (ES) — `NDS_DEC` (parcial, ampliable)
`0xB2→á, 0xBA→é, 0xBE→í, 0xC4→ó, 0xCA→ú, 0xC2→ñ, 0xCC→ü, 0xB5→ä, 0xA5→¿,
0xDF→¡, 0xD9→Í`. El 3DS usa Shift-JIS con furigana `[kanji/lectura]`.

Glosario generado: ver [`translation/shared/glossary/`](../translation/shared/glossary/) y
`ie123kit._legado.build_glossary`. Resultado: ~1327 parejas exactas (jugadores, títulos
de equipo, menús).

**Pendiente:** (1) parsear los índices `.dat` de objetos/técnicas para alinear con
exactitud; (2) completar la tabla `NDS_DEC` (mayúsculas acentuadas, signos).

## Diálogo narrativo / scripts de evento (issue #3)

**Ubicación (juego 1):** `inazuma1/data_iz/script/`
- **`eve.pkb`** (4,2 MB) = eventos/historia · **`mch.pkb`** (1,1 MB) = combates/partidos
- **`eve.pkh`** (índice) — paquete Level-5 **"PackNum"** (cabecera `PackNum YYYYMMDD`).
- Equivalen al `evet.pkb`/`mcht.pkb` del NDS.

**Formato:** el texto va **EMBEBIDO en scripts de evento COMPILADOS (bytecode)**,
entrelazado con operandos binarios. NO se extrae limpio separando por NUL (las
frases salen partidas). Encoding: **Shift-JIS** en el 3DS; codificación Latin
propia en el NDS ES. Se ven fragmentos reales ("仲間になった！"=¡se unió al equipo!,
NDS "te ha unido!").

**Estrategia recomendada:** el **NDS `evet.pkb` contiene el español oficial en la
MISMA estructura** → una vez parseado el formato de script, **alinear** los mensajes
JP(3DS)↔ES(NDS) y reutilizar la traducción oficial en lugar de traducir desde cero.

**Índice `.pkh` RESUELTO** (`ie123kit._legado.pkb_unpack`):
- 16 B: `"PackNum YYYYMMDD"` · `+0x10 u32`: tamaño del pkh
- `+0x30`: tabla de entradas de **12 B**: `{event_id u32, offset u32, size u32}`.
  Los `event_id` son IDs de mapa/evento (`10010001`…). Offsets cubren el pkb exacto.
- 3DS `eve.pkb`: **1293 eventos**. El NDS `evet.pkb` es también PackNum →
  **alineable por `event_id`** (reutilizar el ES oficial).

**Formato de MENSAJE (pendiente, issue #3):** dentro de cada evento el texto va como
operandos de un **script compilado (bytecode)**: plantillas printf (`%s`, `\n`,
`%2F`, `$`) + **códigos de control de 1 byte entrelazados con el Shift-JIS** (e
incluso NUL dentro de una palabra). Hay que **catalogar los códigos de control** y
parsear el bytecode para extraer/​reinsertar el diálogo limpio. Diagnóstico:
`ie123kit._legado.pkb_unpack --text` (volcado best-effort, fragmentado).

### Estructura interna del evento "SSD" — DECODIFICADA (2026-06)

Cada entrada del `.pkb`, una vez descomprimida (LZ10), es un evento con magic
**`SSD\0`** y esta cabecera (analizado con `work/re_ssd*.py`):

| Offset | Valor (ev. ejemplo) | Significado |
|---|---|---|
| 0x00 | `"SSD\0"` | magic |
| 0x04 | `0x00030001` | versión (constante) |
| 0x08 | tamaño total | bytes del evento descomprimido |
| 0x0C | u16+u16 | low=`0xCC` const, high=contador variable |
| 0x10 | offset (p.ej. 4028) | `s10` = inicio de la **sección de texto** (chunks NUL) |
| 0x14 | offset (p.ej. 1500) | puntero a una instrucción (NO es el inicio del bytecode) |
| 0x20 | — | **inicio real del stream de instrucciones** |

**Bytecode = stream de instrucciones de longitud prefijada — DECODIFICADO (2026-06).**
Desde `0x20` hasta `s10` hay instrucciones consecutivas con este formato (verificado:
las longitudes encadenan exactas hasta ~8 B antes de `s10`, un pie especial):

```
<u16 indice><u16 longitud><u32 opcode><operandos u32...>
```

- `longitud` (en +2) = tamaño TOTAL de la instrucción en bytes (incluye los 8 de
  cabecera+opcode). `indice` (en +0) es un contador secuencial 1,2,3,… por evento.
- **OJO al orden de bytes:** `0x002c0001` LE = `01 00 2c 00` → indice=1, longitud=0x2c.
- La **sección de texto** (`dec[s10:]`) son chunks delimitados por NUL: diálogo
  (consumido SECUENCIALMENTE), lecturas furigana, cadenas debug, nombres de archivo.

**Qué operandos son OFFSETS de string (referencias) vs números.** Algunos operandos
guardan un offset (rel a `s10`) que apunta al inicio de un chunk; otros son números
(contador, coordenada, ID, delay). **NO se distinguen por el valor** (un número
redondo como 500/1000 cae por azar en un inicio de chunk). Discriminador que SÍ
funciona (`ie123kit._legado.reinsert_var.build_string_slots`): clasificar cada `(opcode, slot)`
por estadística sobre TODO el ROM — un **slot de offset** apunta SIEMPRE a inicio de
chunk o vale 0; **casi nunca a media cadena** (mid<3%). Un slot numérico cae a media
cadena 40-80% (valores aleatorios). game1: ~6 slots-string; game2: ~45.

**→ La reinserción de LONGITUD VARIABLE sí es viable** (`ie123kit._legado.reinsert_var`):
agranda el diálogo a texto completo y **reubica SOLO los operandos de slots-string**
que apuntan a un chunk movido (offset-fixup preciso), dejando intactos contadores/
índices. Validado offline: 0 operandos no-string alterados, 0 referencias rotas.
La reinserción in-place de MISMO tamaño (`ie123kit._legado.reinsert`) queda como alternativa.

**Furigana (clave del bloqueo de pantalla negra):** un chunk de diálogo (tipo
`0x01`) lleva N marcadores `%NF` (N = nº de caracteres base que reciben ruby;
`%1F`,`%2F`,…). Tras él vienen **N chunks de lectura** (hiragana, tipo `0x02`/`0x03`,
con 2º byte de estilo `0x0c`/`0x10`), consumidos secuencialmente: **un marcador ⇒
una lectura**. Ejemplo: `%1F彼 %2F駅前 %1F呼` → lecturas `かれ`,`えきまえ`,`よ`.

- **Si se traducen y se QUITAN los marcadores** (el español no tiene ruby) pero se
  dejan los chunks de lectura → el motor no los consume y los interpreta como
  mensajes sueltos → **se descuadra y cuelga** (causa de la build v12).
- **Si se quitan marcadores Y lecturas** → cambia el conteo de chunks/offsets →
  cuelga (v11).
- **Regla segura:** preservar el **conteo de marcadores** (modo v13,
  `FURIGANA_KEEP_MARKERS`) para que las N lecturas se sigan consumiendo, traduciendo
  el resto del texto y manteniendo el tamaño en bytes.

**Proporción con furigana:** ~**70%** del diálogo traducido lleva furigana (game1:
13867 de 19849; game2: 46141 de 66598). Por eso la build v10 (que salta el furigana)
solo muestra ~30% en español → el resto sigue en japonés.

## Fuentes y ACENTOS — DECODIFICADO (2026-06)

El español no cabe en Shift-JIS (no tiene á/é/ñ/¡/¿). Estrategia: **codificar cada acento
como un carácter GRIEGO/CIRÍLICO** (que SJIS sí tiene) y **repintar ese glifo en la fuente**
con la letra acentuada (`tools/font_patch.py` sobre las `font/*.bcfnt`, mismo tamaño).

**Fuentes del juego:** las reales son `font/FONT12T.bcfnt` / `FONT12.bcfnt` / `FONT8.bcfnt`
(bcfnt 3DS, con ASCII media anchura + kana + kanji + griego/cirílico). Las
`inazumaN/data_iz/font/*.NFTR` (formato DS) **NO** son las del diálogo (no tienen ASCII
media anchura, que el diálogo sí usa).

**⚠️ Clave (bug de acentos resuelto, verificado renderizando los glifos):** la bcfnt guarda
cada griega en **DOS** glifos distintos: el rango **Unicode** (`0x0391..`) y el **SJIS**
(`0x839F..`). `es_encode` emite bytes **SJIS** (`é`→`0x83A0`), PERO el motor los **reconvierte
a Unicode** y busca el glifo por el **codepoint UNICODE** (comprobado: el glifo que pinta
para el byte `0x83A0` es el del Unicode `0x0392`, no el del SJIS). → hay que repintar el
glifo del **codepoint UNICODE**, no el del SJIS (patchear el SJIS no tiene efecto: el juego
no lo usa). Los **15 griegos mayúsculos Unicode (`0x0391-0x039F`)** están TODOS en el cmap de
las 3 fuentes → cubren los 15 acentos 1:1. `font_patch.PLAN` (codepoints Unicode) es la única
fuente de verdad; `ie123kit._legado.reinsert.GREEK` deriva el portador = `chr(cp)` → siempre coinciden.

## Contexto de herramientas de la comunidad (research 2026-06)

Este juego es un **PORT de los 3 juegos de DS** al 3DS → usa formatos **heredados del DS**
(fuentes NFTR, `.dat`/`.str`, eventos SSD). Por eso:
- Las herramientas de **Inazuma Eleven GO** (nativo 3DS: StudioElevenLib, CfgBinEditor,
  scripts Squirrel, mapenv de Tiniifan) **NO aplican** a nuestros formatos.
- Sí aplican herramientas de **DS**: crystaltile2 (NFTR/`.dat`), `InazumaDSEditor`
  (unitbase.dat), `Inazuma-Eleven-Toolbox` (save/stats de los 3 primeros).
- **El diálogo de eventos SSD con furigana NO lo ha resuelto la comunidad** (en el hilo de
  GBAtemp de este juego se atascaron buscando el texto): nuestro pipeline custom va por
  delante ahí. No reinventar la rueda en lo fácil (fuentes/roster), sí mantener lo difícil.

## Herramientas (resumen, detalle en tools/README.md)

| Tarea | Herramienta |
|---|---|
| Extraer/reconstruir NCSD/NCCH/RomFS/ExeFS | 3dstool, ctrtool, GodMode9 |
| Editar `.cfg.bin` / texto Level-5 | CfgBinEditor, Nyanko |
| Toolbox específico de la saga | Inazuma-Eleven-Toolbox, Strikers2013-Tools |
| Extraer NDS | ndstool, Tinke |
| Parche final | xdelta3 |
| Pruebas | Lime3DS / Azahar |
