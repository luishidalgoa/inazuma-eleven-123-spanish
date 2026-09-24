# Formato de los scripts de evento (eve.pkb / evet.pkb) — notas de RE

Estado: **RESUELTO** (extracción limpia). El contenedor es PackNum y **cada entrada
está comprimida con LZ10 de Nintendo**. Tras descomprimir, el texto son cadenas
Shift-JIS separadas por NUL. (Lo que parecían "códigos de control" eran flags y
back-references de LZ10.) Reinserción: pendiente recomprimir + fixup de offsets.

## Contenedor PackNum (RESUELTO — `ie123kit._legado.pkb_unpack`)

- `.pkh`: `"PackNum YYYYMMDD"` (16 B) · `+0x10 u32` tamaño · `+0x30` tabla de
  entradas de **12 B**: `{event_id u32, offset u32, size u32}`.
- `event_id` = id de mapa/evento (p.ej. `10010001`). Offsets cubren el `.pkb`.
- Juego 1: 3DS `eve.pkb` = **1293 eventos**; NDS `evet.pkb` = **1737**;
  **1289 `event_id` comunes** → alineables (etapa 4).

## Compresión LZ10 (RESUELTO)

Cada entrada del `.pkb` empieza por `10 XX XX 00` = **LZ10 de Nintendo**
(`0x10` + tamaño descomprimido de 24 bits LE). `ie123kit._legado.pkb_unpack:lz10_decompress`.
Hallado vía comunidad ([Kuriimu #249](https://github.com/IcySon55/Kuriimu/issues/249),
GBAtemp). Tras descomprimir → cadenas Shift-JIS separadas por NUL.

## Texto descomprimido

- **Sustitución**: `%s` (nombre), `%d` (número).
- **Furigana/ruby**: `%1F`/`%2F`/`%3F` marcan kanji; la **lectura** va como cadena
  aparte (solo hiragana) → se filtra con `is_furigana()`.
- `\n` literal (backslash+n) = salto de línea.
- Encoding: **Shift-JIS** (3DS) / Latin propia (NDS, ver `ie123kit._legado.build_glossary.NDS_DEC`).

## Estado de extracción y alineado

- `ie123kit._legado.pkb_unpack --text` → diálogo LIMPIO (descomprime + NUL-split + filtro).
  JP ~57k cadenas; ES ~22k.
- `tools/align_events.py` → empareja por `event_id` (1289 comunes), quita furigana,
  dedup. **133 eventos con nº de líneas JP=ES idéntico → emparejado posicional
  perfecto** (reúso directo del ES oficial). El resto necesita matching más fino.

## Reinserción (etapa 7) — ciclo de datos VALIDADO

`ie123kit.nucleo.compresion.lz10` (compresor LZ10 propio, roundtrip OK, salida ≤ original) +
`tools/reinsert_test.py` (PoC). Estrategia **bulletproof sin fixup de offsets**:
1. Descomprimir el evento (LZ10).
2. Sustituir cadenas por el ES **del mismo nº de bytes** (relleno/recorte) → el
   tamaño descomprimido y todos los offsets internos quedan intactos.
3. Recomprimir; si ≤ tamaño original de la entrada, **rellenar con `\x00`** hasta
   ese tamaño exacto (el descompresor ignora el padding).
4. Sobrescribir en `eve.pkb`/`archive.fa` **in-place** (mismo tamaño) → no hay que
   tocar `.pkh`, B123 ni el NCSD.

Validado: re-extraer del `archive.fa` parcheado devuelve el texto nuevo.
Aprovecha que el japonés (Shift-JIS, 2 B/char) suele ocupar MÁS bytes que el
español ASCII → cabe.

## Pendiente sobre la reinserción
- Re-encode real del ES preservando códigos del 3DS (`%s`, `\n`, quitar furigana).
- Meter el `archive.fa` parcheado en un `.3ds` (parche in-place del .3ds, o rebuild
  con 3dstool) — verificar arranque en emulador (hashes IVFC/NCCH: Citra/Lime3DS
  suelen ignorarlos). Alternativa: distribuir como mod LayeredFS.
- Fuente (etapa 6) para ñ/tildes/¿¡.

## Tabla de cadenas e IDs (2026-09-15) — emparejado EXACTO 3DS ↔ NDS

Las frases no se emparejan por orden: cada una tiene un **ID de cadena**.

- **NDS `script/sp/evet.pkb`**: `u32 tamaño` + entradas `{id u16, tipo u16, longitud u32}` + cadena.
- **3DS `eve.pkb` (SSD)**: la cabecera apunta con `u32@+16` a la sección de datos; **32 B después**
  empiezan entradas `{id u16, tipo u8, longitud u8}` + cadena.
- La `longitud` **incluye la cabecera** de la entrada (8 B en NDS, 4 B en 3DS).
- Tipo 1 = frase. En el 3DS las lecturas furigana van con tipo 2..4 **y el mismo id** de su frase.
  En la NDS el tipo 2 son nombres de archivo/recursos.
- Los IDs son **posiciones en el bytecode**. En 621 eventos la NDS tiene instrucciones de más y los
  IDs se desplazan (+1, +2…) a partir de un punto. **El patrón de saltos entre IDs consecutivos se
  conserva**: se alinea esa secuencia y se valida con anclas ASCII (nombres de archivo, variables
  `HikinukiX=%d`) que son idénticas en ambas ROMs. Herramienta: `ie123kit._legado.audit_dialogo_ids`
  (18.343 pares; anclas 12.395 idénticas / 66 distintas).

> ⚠️ `ie123kit._legado.ds_official` alineaba por patrón de repeticiones con difflib, que en eventos sin
> frases repetidas equivale a emparejar **por posición**. Dejó 1.579 filas desalineadas en
> `dialogo_oficial.csv` y 931 frases desplazadas en la build (issue #36). No usarlo para regenerar.
