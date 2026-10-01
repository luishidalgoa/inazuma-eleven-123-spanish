# Glosario JP (3DS) ↔ ES (NDS oficial) — Juego 1

Generado automáticamente con [`ie123kit._legado.build_glossary`](../../tools/src/ie123kit/_legado/build_glossary.py)
emparejando **por índice de registro** los datos del 3DS (japonés) con los del
NDS europeo oficial en castellano, que comparten el mismo orden de entidades.

Cada CSV tiene columnas: `idx, japones, espanol_oficial`. El `espanol_oficial` usa
los **nombres europeos oficiales** (decisión del proyecto).

## Ficheros

| Archivo | Entradas | Fuente | Estado |
|---|---|---|---|
| `jugadores.csv` | ~1174 | `unitbase.dat` (reg. 96 B, nombre@+0) | ✅ verificado |
| `titulos_equipo.csv` | 20 | `teamtitle.dat` (reg. 16 B) | ✅ verificado |
| `menus.csv` | ~133 | `games.STR` (índice 1:1) | ✅ verificado |
| `equipos.csv` | 158 | `team.pkb` (reg. 320 B; NDS desplazada +1 desde el 32) | ✅ verificado |
| `tecnicas.csv` | 131 | `command.dat`/`command.STR` (por ID de técnica) | ✅ verificado; `nombre_3ds` abreviado a 15 caracteres |
| `objetos.csv` | 302 | `item.dat` (índice; NDS 48 B, 3DS 32 B) | ✅ verificado; `nombre_3ds` abreviado a 9 caracteres |

Ejemplos verificados: 円堂守→**Mark Evans**, 豪炎寺修也→**Axel Blaze**,
鬼道有人→**Jude Sharp**, 音無春奈→**Celia Hills**.

## Codificación

- 3DS: **Shift-JIS** (con furigana `[kanji/lectura]` en los textos largos).
- NDS (ES): **codificación Latin propia**, decodificada con la tabla `NDS_DEC` de
  `ie123kit._legado.build_glossary`: `0xB2→á, 0xBA→é, 0xBE→í, 0xC4→ó, 0xCA→ú, 0xC2→ñ, 0xCC→ü,
  0xA5→¿, 0xDF→¡, 0xD9→Í` (ampliable).

## Pendiente

- **Objetos** y **técnicas**: el `item.dat`/`command.STR` no alinean 1:1 entre
  plataformas (estructura/recuento distintos); hay que parsear su índice real.
- Completar la tabla `NDS_DEC` (mayúsculas acentuadas, signos restantes).

> Estos CSV son **tablas de terminología** (etiquetas cortas) para coherencia de la
> traducción. No contienen diálogos ni descripciones. No se suben ROMs ni texto
> extraído al repo (ver [`LEGAL.md`](../../LEGAL.md)).
