# Encargo: extraer los recursos de Inazuma Eleven 3 (3DS europeo)

Documento para el agente de IA de quien colabore. Leer también `docs/SKILL_VOLCADO_ROM_NDS.md` (lecciones de volcado; se puede copiar a `.claude/skills/volcado-rom-nds/SKILL.md` para usarla como skill). **Objetivo: dejar preparados los recursos del juego
europeo en formato legible. No se reinserta nada en el 1·2·3 todavía.**

## ROM de partida

- `roms/ie3/fuego_explosivo/Inazuma Eleven 3 - Bomb Blast (2013).cia`, código `CTR-P-AXBZ`.
- CIA **descifrado** (NCCH con NoCrypto): se puede extraer sin claves.
- Contenido 0 = NCCH en el offset `0x3940`; ExeFS 2.724 unidades, RomFS 3.369.608 unidades
  (unidad = 0x200 B), RomFS con cabecera `IVFC`.

## Normas que no se negocian

1. **Nada extraído va al repositorio** (copyright, Norma 2 de `CLAUDE.md`). Todo en `work/ie3_es/`,
   que `.gitignore` ya excluye. Solo se pueden subir scripts en `tools/` y documentación sin texto del juego.
2. Antes de cualquier commit: `git status` y `git ls-files` para comprobar que no se cuela ningún `.json`,
   `.bin`, `.arc`, texto, textura o audio.
3. No modificar herramientas existentes de `tools/` sin necesidad; si hace falta, añadir opciones
   compatibles y no romper `python -m unittest` en `tools/`.
4. No tocar `work/probe_ie1_*`, `work/v3*`, `work/v4*` ni la carpeta de mods de Azahar.

## Pasos

### 1. Extraer

```text
tools/bin/3dstool.exe -xtf cia "roms/ie3/fuego_explosivo/Inazuma Eleven 3 - Bomb Blast (2013).cia" --contents work/ie3_es/contents
tools/bin/3dstool.exe -xtf cxi work/ie3_es/contents.0000.00000000 --exefs work/ie3_es/exefs.bin --romfs work/ie3_es/romfs.bin --exh work/ie3_es/exheader.bin
tools/bin/3dstool.exe -xtf romfs work/ie3_es/romfs.bin --romfs-dir work/ie3_es/romfs
tools/bin/3dstool.exe -xtf exefs work/ie3_es/exefs.bin --exefs-dir work/ie3_es/exefs
```

(Referencia: `tools/extract_romfs.ps1` hace lo mismo para el `.3ds` del 1·2·3. Si `3dstool` nombra
los contenidos de otra forma, ajustar la ruta del paso 2.)

### 2. Inventario

Generar `work/ie3_es/inventario.json` con cada archivo del RomFS: ruta, tamaño, SHA-256 y los 4 primeros
bytes (magic). Comparar la estructura con el 1·2·3 japonés (`work/shared/base_3ds/romfs`), donde el juego 3 vive en
`inazuma3/` y `inazuma3_ogre/` dentro de `archive.fa`.
Preguntas que el inventario debe responder:
- ¿Hay `archive.fa` o los archivos van sueltos? (`ie123kit._legado.fa_unpack` lee `archive.fa`.)
- ¿Existen `data_iz/script/eve.pkh` y `eve.pkb`? ¿Hay carpetas por idioma (`sp`, `es`, `EU`…)?
- ¿Qué fuentes lleva (`font/*.bcfnt`, `*.NFTR`)?

### 3. Diálogos de NPC e historia → JSON

- Índice y eventos: `ie123kit._legado.pkb_unpack` (`parse_index`) y `ie123kit.nucleo.compresion.lz10` (`decompress`).
- Cada evento es un SSD: `ie123kit.nucleo.eventos.ssd` (`parse`) devuelve instrucciones y registros de texto.
  Formato documentado en `docs/EVENT_SCRIPT_FORMAT.md` y `docs/SSD_REGISTROS_IE1.md`.
- **Codificación: por determinar.** El 1·2·3 japonés usa Shift-JIS, y nuestra traducción mete las
  tildes como letras griegas. La versión europea puede usar otra tabla (Latin-1, UTF-16 o una tabla
  propia). Método: buscar palabras españolas conocidas («Raimon», «Mark», «balón») en los bytes de
  un evento y deducir la tabla. **Documentar la tabla en `docs/`** antes de volcar.
- Separar texto de furigana/lecturas si existen (en el japonés, tipos 2–4 del mismo ID).

Salida: `work/ie3_es/dialogos/<event_id>.json`

```json
{
  "event_id": 92010100,
  "tipo": "historia | npc | sistema",
  "registros": [
    {"indice": 0, "instruccion": 12, "opcode": "0x301d", "argumento": 1,
     "hablante": "Mark", "texto": "…", "bytes_hex": "…"}
  ]
}
```

- `tipo` por rango de ID de evento (en IE1: ≥ 90000000 sistema/historia; comprobar en IE3).
- Guardar `bytes_hex` del original para poder verificar después la decodificación.
- `hablante`: si la instrucción referencia un jugador, resolver con `unitbase.dat`.

### 4. Nombres y textos de datos → JSON

| Recurso | Dónde mirar (IE1 3DS) | Salida |
|---|---|---|
| Jugadores (nombre completo y corto) | `logic/unitbase.dat` (96 B/registro, +0 y +32) | `jugadores.json` |
| Equipos | `logic/team.pkb` (320 B, nombre en +0) | `equipos.json` |
| Supertécnicas y descripciones | `command.dat` / `command.STR` | `tecnicas.json` |
| Objetos y descripciones | `item.dat` / `item.STR` | `objetos.json` |
| Títulos, lugares, menús | `rpgtitle.STR`, `fieldinf.dat`, `games.STR`, `ina_main*.cro` | un JSON por archivo |

Cada entrada con su ID/índice original, el texto y el tamaño del campo en bytes. Las longitudes importan
luego para saber qué cabe en el 1·2·3.

### 5. Resto de recursos (solo inventario, sin convertir)

- Texturas de interfaz (`.arc` con `CTPK`): lista de nombres y tamaños.
- Audio (`.SAD`/`.bcstm`) y vídeos (`.moflex`): lista con duración si es fácil de obtener.

## Comprobaciones antes de dar el trabajo por hecho

- Decodificar y volver a codificar cada texto reproduce los `bytes_hex` exactos (0 diferencias).
- Número de eventos del JSON = número de entradas de `eve.pkh`.
- Informe `work/ie3_es/resumen.json`: eventos, registros, bytes no reconocidos por la tabla (debe ser 0)
  y ejemplos de 5 diálogos para revisión humana.
- Documentar en `docs/IE3_EXTRACCION.md` los formatos encontrados y las diferencias con el 1·2·3.
  **Sin pegar diálogos completos**, solo frases cortas de ejemplo.
- Abrir un issue en GitHub para el trabajo (Norma 1) y comentar en él el resumen.
