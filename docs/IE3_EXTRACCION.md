# IE3: extracción del texto de evento y alineamiento con el español oficial

Resultado del encargo de [`IE3_EXTRACCION_BRIEF.md`](IE3_EXTRACCION_BRIEF.md), ampliado a
las **dos** ROMs europeas disponibles. Todo lo extraído vive en `work/` (Norma 2); aquí
solo hay formatos, cifras y ejemplos cortos.

| Japonés (recopilatorio) | Europeo (juego suelto) | Salida |
|---|---|---|
| `inazuma3/data_iz` (Spark) | IE3: **Rayo Celeste** (Lightning Bolt, `CTR-P-AXSZ`) | `translation/ie3/rayo_celeste/dialogo_oficial.csv` |
| `inazuma3_ogre/data_iz` (Ogre) | IE3: **La amenaza del Ogro** (Team Ogre Attacks, `CTR-P-AXGZ`) | `translation/ie3/amenaza_del_ogro/dialogo_oficial.csv` |

Ambos ficheros están en `.gitignore`: son texto oficial de Nintendo, mismo caso que
`translation/ie1/dialogo_oficial.csv`.

---

## 1. Bomber / Fuego Explosivo no tiene texto propio

`inazuma3/data_iz_bomber/` existe en las tres ROMs examinadas, pero **no contiene
`script/`**: son nueve ficheros de configuración y listas de depuración, y sus
`SCRIPTINFO.TXT`, `EVENTINFO.TXT`, `SCRIPTINFOMAP.TXT`, `MCSFILE.TXT` y
`DEBUG_SCRIPT_LIST.txt` son **idénticos línea a línea** a los de `data_iz`.

Su `MCSFILE.TXT` redirige a `/data_iz/script/`, así que Bomber **carga el `eve.pkb` /
`evet.pkb` de Spark** y el motor ramifica en tiempo de ejecución.

**Consecuencia práctica:** el diálogo de *Fuego Explosivo* es el de
`rayo_celeste/dialogo_oficial.csv`. Cuando aparezca el CIA de *Bomb Blast* servirá para
**verificar** esto y para cubrir sus recursos propios, pero no debería aportar diálogo
nuevo. Queda por auditar el reparto de recursos no textuales.

---

## 2. Formatos

### 2.1 Contenedor

Los tres juegos usan el **mismo contenedor B123** que el 1·2·3, así que
`ie123kit.nucleo.contenedores.fa` los abre sin cambios: `archive.fa` (JP),
`archive_sz.fa` (Rayo) y `archive_oz.fa` (Ogro).

Recuento de ficheros: 15 547 (JP), 19 501 (Rayo), 19 504 (Ogro).

**Diferencia con el 1·2·3:** las ROMs europeas meten el texto en **una carpeta por
idioma** dentro del contenedor — `es/`, `en/`, `it/` — y dejan fuera los recursos
comunes. El diálogo español está en:

```
es/inazuma3/data_iz/script/{eve,evet}.{pkb,pkh}
es/inazuma3_ogre/data_iz/script/{eve,evet}.{pkb,pkh}
```

Las **dos** ROMs europeas llevan las dos mitades, y sus packs españoles son **byte a byte
idénticos** entre Rayo y Ogro (verificado con SHA-256 sobre los 8 ficheros). Eso permite
extraer el español de cualquiera de las dos y sirve de comprobación cruzada del parser.

### 2.2 Índice PKH

Igual que en IE1; lo lee `ie123kit.nucleo.eventos.packnum` sin cambios.

**Corrección importante:** el identificador de evento es **decimal**, no hexadecimal.
El capítulo 1 de IE3 es `31010000`, que es justo como lo llama el propio juego en
`EVENTINFO.TXT` (`eve31010000.ssd`). Una versión anterior de este pipeline lo escribía
en hexadecimal (`01d92cd0`), lo que lo hacía irreconocible y no cuadraba con
`translation/ie1/dialogo.csv`, que ya usaba el decimal.

Las dos mitades **comparten numeración** (las dos empiezan en `31010000`), así que su
diálogo no puede ir en el mismo CSV: de ahí un fichero por versión.

### 2.3 SSD (`eve.pkb`) — incompatibilidad con el parser del núcleo

El bloque SSD de IE3 es el mismo formato que el de IE1, pero
**`ie123kit.nucleo.eventos.ssd.parse` rechaza el 84 % de los bloques de IE3** con
`nonzero text padding`.

Motivo: el núcleo exige que, tras el NUL que cierra cada texto, el relleno hasta el
alineado de 4 sea todo ceros. En IE3 **no lo es**: quedan de 1 a 3 bytes de residuo de
una cadena anterior más larga que se sobrescribió sin limpiar el búfer. Por ejemplo, un
registro de 12 bytes cuyo cuerpo es `@0,36` guarda `40 30 2c 33 36 00` y luego `25 31`
(`%1`, el principio suelto de un marcador de furigana de otra cadena).

No es un segundo texto: leer hasta el primer NUL es correcto. Por eso IE3 usa su propio
lector en `ie123kit.ie3.comun.ssd`, que valida las tres secciones
(`0x20 + código + textos == tamaño == len(bloque)`, comprobado en los más de 14 000
bloques de los tres juegos) pero tolera ese relleno.

> **Pendiente:** unificar los dos lectores añadiendo a `nucleo` una opción
> `tolerar_relleno` que por defecto mantenga el comportamiento estricto de IE1.

### 2.4 `evet.pkb` — tabla plana de diálogos

IE1 no tiene `evet`. En IE3 es la misma entrada de 4 bytes de la tabla de textos del SSD
(u16 instrucción, u8 argumento, u8 tamaño) repetida hasta el final del bloque, con
instrucción y argumento **siempre a 0**, y sin cabecera ni compresión.

**Aquí está el diálogo de verdad.** En japonés, detrás de cada línea van sus lecturas
furigana: la línea lleva marcas `%1F` / `%2F` (una por kanji anotado) y a continuación
vienen tantas entradas de lectura como marcas. Eso explica que el japonés tenga ~102 000
entradas frente a ~39 000 en español: no falta texto, sobran lecturas. Se agrupan con su
línea y no se cuentan como diálogos sueltos.

### 2.5 Codificación europea

**El motor sigue usando Shift-JIS (cp932) también en las versiones europeas.** Lo que
cambió Level-5 es la *fuente*: reaprovechó los huecos de glifos que en japonés ocupaba el
katakana de medio ancho para dibujar allí las letras acentuadas.

La tabla la publica el propio juego en **`font/CodeTable.bin`** (320 bytes = 160 u16 =
80 pares): la entrada `i` es el codepoint real y la `80 + i` el hueco japonés que lo
transporta. Descodificar es `data.decode("cp932").translate(tabla)`.

| Byte | Hueco japonés | Real |
|---|---|---|
| `0xB2` | U+FF72 | `á` |
| `0xBA` | U+FF7A | `é` |
| `0xC2` | U+FF82 | `ñ` |
| `0xA5` | U+FF65 | `¿` |
| `0xDF` | U+FF9F | `¡` |

Son 74 sustituciones, **idénticas en Rayo Celeste y en La amenaza del Ogro**. No se
asumió CP1252 ni Latin-1: la tabla sale del fichero del juego. `text.py` implementa
también `encode()` para cuando toque reinsertar.

---

## 3. Qué texto se ve en pantalla y qué no

Éste era el problema de fondo: de las 263 000 filas que produce el alineamiento en bruto,
**la mayoría no es texto del juego**. Clasificarlas por la pinta del texto da falsos
positivos; se clasifican por el **opcode** de la instrucción de la que cuelga cada
cadena, que no cambia al traducir.

La tabla se obtuvo midiendo, opcode a opcode, cuántos de sus textos aparecen realmente
traducidos en las versiones europeas (contando solo emparejamientos fiables). No hay zona
gris:

| Opcode | Textos JP | Traducidos | Qué es |
|---|---|---|---|
| `0x4037` | 560 | 100,0 % | nombre de sitio |
| `0x201a` | 14 | 100,0 % | rótulo de objetivo |
| `0x201d` | 127 | 99,2 % | rótulo de objetivo |
| `0x3019` | 51 | 98,0 % | nombre tapado del interlocutor |
| `0x201c` | 272 | 97,4 % | rótulo de objetivo |
| `0x2019` | 22 | 90,9 % | rótulo de objetivo |
| `0x3070` | 21 568 | 0,6 % | `printf` de depuración (`■…`) |
| `0x402f` | 1 324 | 0,0 % | etiqueta fija del motor |
| `0x301d` | 79 969 | 0,0 % | parámetros `@x,y` |
| `0x3008`, `0x3014`, `0x3017`, `0x3011`, `0x4090`… | — | 0,0 % | nombres de recurso |

Los 130 «traducidos» de `0x3070` se revisaron uno a uno: 129 son parejas falsas del
alineamiento heurístico y una es casualidad.

**Excepción comprobada:** un opcode técnico puede llevar texto real. El caso son las
**contraseñas secretas** de IE3, que cuelgan de `0x7011` (el que carga los mapas) y que
Level-5 sí tradujo — `カードであそぼう` → `pokerdeases`. Por eso una fila técnica sube a
texto real cuando hay prueba de que se tradujo: japonés de verdad, español oficial sin un
solo kana y emparejamiento fiable. Son 42 filas por juego.

---

## 4. Alineamiento japonés ↔ español

Nunca por offset: las traducciones cambian de longitud. Por orden de fiabilidad:

1. **Identidad del evento** — el id del PKH es el mismo en japonés y en europeo.
2. **Clave interna `(instrucción, argumento)`** en `eve`. No depende de offsets.
3. **Posición** en `evet` cuando el evento tiene el mismo número de diálogos en los dos
   idiomas (quitando las lecturas furigana). Es un emparejamiento por índice, sin
   heurística: cuadra en 2 497 de 2 846 eventos.
4. **Alineamiento de secuencia** (Needleman-Wunsch) para los 349 eventos restantes, que
   de verdad tienen distinto número de diálogos.

### 4.1 La medida de parecido se recalibró con datos

La original puntuaba códigos de control, cifras, signos, saltos y longitud. Medida contra
32 032 parejas fiables de `evet` frente a las mismas barajadas al azar, **rechazaba el
76,6 % de las parejas correctas**. Los rasgos, uno a uno:

| Rasgo | Parejas buenas | Al azar |
|---|---|---|
| huecos `%s`/`%d` (cuando los hay) | **100,0 %** | **2,2 %** |
| saltos de línea (±1) | 98,3 % | 84,8 % |
| signos de exclamación | 77,5 % | 54,5 % |
| saltos de línea (exactos) | 62,4 % | 38,0 % |
| cifras | 98,6 % | 98,2 % |

Dos conclusiones: las **cifras no discriminan nada** (fuera), y los **huecos `%s`/`%d`
son casi perfectos** — un `%s` no desaparece al traducir, así que si no cuadran no son
pareja. Las marcas de furigana `%nF` se quitan antes de comparar: aparecen 51 843 veces
en japonés y 285 en español, y compararlas hundía casi todas las parejas buenas.

### 4.2 Dos mejoras estructurales

- **En `eve`, la pasada heurística solo compara textos del mismo opcode.** Es una
  restricción estructural, no una heurística, y evita el error típico: casar dos mensajes
  de depuración sin relación porque empiezan por el mismo símbolo.
- **En `evet`, memoria de traducción como ancla.** Primero se resuelven los 2 497 eventos
  que cuadran por índice y con ellos se monta un diccionario japonés → español (solo
  frases con traducción **unánime**). Esas parejas anclan el alineamiento de los 349
  eventos descuadrados: ~12 000 anclas por juego.

---

## 5. Salida

`translation/ie3/<versión>/dialogo_oficial.csv`, mismas columnas que
`translation/ie1/dialogo.csv`:

```
event_id,japones,es_final,estado
```

`es_final` queda **vacío** cuando no hay traducción oficial. Antes se arrastraba el
japonés a la columna española, que es lo que hacía que el resultado pareciese medio sin
traducir sin decir por qué.

| Estado | Significado |
|---|---|
| `oficial` | traducción oficial europea, emparejamiento fiable |
| `memoria` | la misma frase japonesa tiene traducción oficial en otra fila y se reutiliza |
| `revisar` | hay traducción, pero el emparejamiento es heurístico: revisar a mano |
| `sin_traducir` | la propia ROM europea lo dejó en japonés |
| `sin_pareja` | no hay contrapartida europea |

### Cifras

| | Filas | `oficial` | `memoria` | `revisar` | `sin_traducir` | `sin_pareja` |
|---|---|---|---|---|---|---|
| Rayo Celeste (Spark) | 38 901 | 34 432 (88,5 %) | 259 | 3 495 | 113 | 602 |
| Amenaza del Ogro | 40 814 | 37 211 (91,2 %) | 396 | 2 467 | 122 | 618 |

De las 263 114 filas del alineamiento en bruto quedan **79 715 de texto real**; el resto
(172 933) son nombres de recurso, parámetros y depuración, y se guardan aparte en
`work/ie3/shared/salida/traduccion/descartado/` para que nada desaparezca sin dejar
rastro.

Salidas auxiliares en `work/ie3/shared/salida/traduccion/`:
`<versión>_pendiente.csv` (lo que hay que traducir a mano), `<versión>_revisar.csv`
(emparejamientos heurísticos) y `<versión>_glosario.csv` (frases japonesas distintas con
su traducción, útil como memoria: 14 554 y 15 681 frases únicas).

---

## 6. Cómo regenerarlo

Requiere `tools/bin/3dstool.exe` y `ctrtool.exe`, y las ROMs en su sitio:

```
Roms/shared/IE123_JP_CTR-P-AETJ.3ds
Roms/ie3/rayo_celeste/00040000000F7E00_v00.trim.3ds
Roms/ie3/amenaza_del_ogro/00040000000F8000 IE3 Team Ogre Attacks! ....cia
```

Todo de una vez (~20 min la primera vez por los RomFS, ~40 s después):

```bash
python tools/ie3_pipeline.py run
```

Por partes:

```bash
python tools/ie3_pipeline.py extract Roms/shared/IE123_JP_CTR-P-AETJ.3ds --lang jp --tag jp
python tools/ie3_pipeline.py align      # cruza japonés y español
python tools/ie3_pipeline.py sheet      # hoja de traducción + dialogo_oficial.csv
python tools/ie3_pipeline.py validate   # revalida
python tools/ie3_pipeline.py info <rom> # identifica una ROM sin extraer nada
```

Admite `.3ds`, `.trim.3ds`, `.cci`, `.cxi`, `.app`, `.cia` y carpetas de RomFS ya
extraídas; el tipo se detecta por el contenido (magic `NCSD`/`NCCH`), no por el nombre.
Opciones: `--force`, `--dump-events`, `--3dstool`, `--ctrtool`.

En Windows, si la consola falla al imprimir japonés: `$env:PYTHONIOENCODING="utf-8"`.

---

## 7. Validación

`validate` comprueba y deja el informe en
`work/ie3/shared/salida/validation_report.txt`:

- caracteres que no se pudieron descodificar: **0** en los 8 CSV de extracción;
- claves repetidas: **0**;
- cuántos textos españoles siguen en japonés en la propia ROM europea;
- **que el español de Rayo Celeste y el de La amenaza del Ogro sea idéntico** — la mejor
  comprobación cruzada que hay: el mismo parser saca el mismo texto de dos contenedores
  distintos (`archive_sz.fa` y `archive_oz.fa`).

Durante el parseo se aborta con mensaje claro si: el CRC de un nombre no cuadra, la tabla
de directorios no mide lo que declara la cabecera, un PKH apunta más allá del final de su
PKB, un bloque LZ10 produce un tamaño distinto del declarado, las tres secciones de un
SSD no suman el tamaño del bloque o una entrada de texto se sale del bloque.

Comprobación cruzada de contenedores: `tools/fa_unpack.py` (núcleo) y el lector B123 de
IE3 extraen **los mismos 15 547 ficheros** del `archive.fa` japonés.

---

## 8. Límites pendientes

- **No hay reinserción de IE3.** Esto extrae y alinea; falta el camino de vuelta. Las
  piezas están (`text.py` sabe codificar a la tabla del juego), pero hay que decidir cómo
  encaja con el bloqueo tipográfico v20 y con las lecciones de
  [`FURIGANA_LECCIONES.md`](FURIGANA_LECCIONES.md).
- **~2 500–3 500 filas por juego en `revisar`.** Vienen de los 349 eventos con distinto
  número de diálogos. Conviene mirarlas antes de fiarse.
- **Solo se tocan `eve` y `evet`.** Los menús, nombres de técnicas y descripciones de
  jugadores están en otros contenedores (`menu/`, `message/`, `es/menu/common.arc`,
  `es/localize/`, `*.arc`) y no se extraen todavía. Los apartados 4 y 5 del brief siguen
  sin hacer.
- **Los opcodes no están documentados** más allá de los seis que llevan texto en pantalla.
- **`evet` no puede llegar a `exact`:** sus entradas no llevan clave interna, así que lo
  máximo alcanzable es la posición.

---

## 9. Reinserción del diálogo de IE3

`ie123kit.ie3.comun.reinsert` mete el español en `evet.pkb`, que es donde está
el diálogo de IE3 (`eve` lleva rótulos y nombres de sitio: unas 850 líneas
frente a 34 000). Un bloque de `evet` va **sin comprimir**.

### 9.1 Las entradas se referencian por ÍNDICE, no por offset

Ésta era la pregunta que decidía cuánto texto podía entrar, y la contesta la
propia versión europea:

> Hay **39 eventos** cuyo bloque de `evet` tiene 3 o más registros, cuyos
> offsets se mueven entre el japonés y el español (p. ej. `0/96/192/288` pasa a
> `0/120/240/360`) y cuya sección de código del `eve` es **byte a byte
> idéntica**.

Si el motor leyera offsets, Level-5 habría tenido que reescribir ese código al
traducir. No lo hizo. Los registros tampoco llevan clave propia: los 102 419
del pack tienen instrucción y argumento a cero. Luego la referencia es la
posición en el recorrido, o sea el índice.

**Consecuencia:** un registro puede crecer o encoger libremente mientras no
cambie el NÚMERO de registros del bloque. Eso es lo único que se comprueba, y
se comprueba siempre.

### 9.2 Dos modos

| | Cobertura Rayo | Cobertura Ogro | Qué toca |
|---|---|---|---|
| mismo tamaño (`reinsert`) | 19 458 (57 %) | 21 254 (58 %) | solo bytes dentro del grupo |
| **crecer** (`reinsert --crecer`) | **34 101 (100 %)** | **36 749 (100 %)** | `.pkb` y `.pkh` reconstruidos |

En el modo de mismo tamaño se aprovecha que las lecturas furigana hay que
vaciarlas de todas formas (el español no lleva furigana) para darle sus bytes a
la línea; eso sube del 41,5 % al 53,7 %, pero el resto se queda en japonés.

En el modo de crecer entra **todo**, y el pack apenas cambia: +1,1 % en Rayo y
−0,2 % en Ogro, porque vaciar las lecturas libera casi tanto como ocupa el
español. Se reconstruye con `packnum.rebuild(comprimir=False)` y se recalcula
**el campo 0x1C del `.pkh`**, que declara el tamaño del bloque mayor: si el
motor reserva el búfer con ese número y un bloque crece por encima, se sale.

El contenedor se actualiza con `fa.reemplazar_entrada`, que anexa al final y
reapunta la entrada, así que `archive.fa` crece unos 5,8 MB sobre 1,3 GB.

### 9.3 Los saltos de línea hay que rehacerlos

El texto oficial trae saltos calculados para la pantalla del IE3 europeo, que no
es la caja del recopilatorio. Medidos con la fuente del juego, **4 435 de 6 000
diálogos (74 %) se pasan de los 208 px**. Y el motor corta por ancho de píxel
sin respetar palabras, así que se quedarían partidos a mitad («Balón Ba|zar»).
Se reajustan con el mismo `reflow` que usan IE1 e IE2, que corta solo entre
palabras.

### 9.4 Lo que no se hace

No se trunca nunca. Con `--crecer` solo se quedan fuera **2 líneas** de 70 850,
las que pasan de 247 bytes, que es lo que cabe en el u8 del tamaño del registro.
Meterlas exigiría partirlas en varios registros, y eso cambiaría el número de
registros del bloque.

---

## 10. Lo que aporta la rama `estado-ie2-cajas`

Añade 233 ficheros en `capas/`: los scripts de las capas de IE1 (v82–v93) e IE2
(v01–v22) que hasta ahora vivían en `work/` y no llegaban al clon. No toca
`CLAUDE.md`, `AGENTS.md`, `FURIGANA_LECCIONES.md`, `tools/` ni `ie123.toml`.

De ahí sale una palanca que **todavía no se ha aplicado a IE3**: IE2 v22
ensancha la ventana de diálogo con tres parches de `ina_main2.cro`, limita las
páginas a 131 B y rehace los saltos a 37 caracteres por línea. El equivalente
para IE3 sería `cro/ina_main3ogre.cro`, y habría que localizar los parches; con
la ventana ancha, el `reflow` de IE3 podría subir de 22 a 37 caracteres y se
verían menos cajas por diálogo.
