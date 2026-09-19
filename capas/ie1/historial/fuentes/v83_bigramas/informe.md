# v83 · Glifos de dos letras («bigramas») para el camino de paso fijo. Informe de viabilidad

Fecha: 2026-09-16. **Este trabajo es solo de investigación.** No se ha construido ninguna candidata ni se ha tocado la fuente instalada, `tools/`, `docs/` ni los eventos.
Base analizada: `work/shared/candidatas/probe_ie1_v81/archive.fa`. La fuente es `font/FONT12.bcfnt`, que es la misma que `work/ie1/capas/fuentes/glifos_eu/extra/font/FONT12.bcfnt` (mismo SHA-1). El código se ha leído de `ina_main1.cro` (original) y de `exefs/code.bin` (descomprimido con BLZ).

Ficheros de esta carpeta:

| Fichero | Qué contiene |
|---|---|
| `inventario.py` → `inventario.json` | Textos españoles por campo y recuento de bigramas |
| `escaneo_sjis.py` → `sjis_usados.json` | Códigos Shift-JIS que aparecen en toda la recopilación |
| `huecos.py` → `huecos.json` | Celdas libres de FONT12 y códigos con glifo que ningún texto usa |
| `previsualizar.py` → `previews/*.png`, `previews/anchos.json` | Simulación a ×3 y anchura de cada par |
| `cro/` | Scripts del análisis de la CRO (rutas fijas, de trabajo) y `cro/llamadas.json` (lugares de llamada) |

## Conclusión

**Es viable, con límites.** En los campos de paso fijo el límite es el número de casillas o de bytes, no los píxeles. Un glifo doble ocupa 2 B y una casilla, así que duplica lo que cabe: el rótulo pasa de 10 a 20 letras y el nombre de 16 B pasa de 7 a 14. Hay sitio de sobra en la fuente sin ampliarla: quedan **2.584 códigos con glifo que no aparecen en ningún texto**, 2.015 de ellos kanji de nivel 2, y la propuesta completa necesita como mucho **995** pares.

Hay tres límites:

1. **La celda de la hoja mide 15 px** (`cell_w` = 15). De los 995 pares, 207 no caben ni con 1 px de separación. Son sobre todo mayúscula + minúscula («Ca», «Ab», «Ra») y pares de cifras («20»). Esos pares se parten: la primera letra va sola. Con esa regla (partición C) salen **812 glifos** y el rótulo más largo de la lista v76 ocupa 9 casillas.
2. **El ritmo no es uniforme.** Cada casilla sigue avanzando 15 px, y un par estrecho («il») deja más aire que uno ancho («mo»). Se lee mucho mejor que ahora (ver `previews/`), pero el resultado no es tipografía proporcional.
3. **Queda una incógnita de código** (§1.3): qué `FONT_TYPE` usan los gestores FONT8/RUBI8/FONT12T. Si alguno no es 0, sus textos se dibujan con otra BCFNT y con otro paso. Hay que comprobarlo en el emulador antes de la fase 1 (fase 0).

**Esfuerzo estimado:** unos 4–6 días de trabajo y 4–5 builds de prueba en Azahar en total (fases 0–3).

---

## 1. Qué textos usan el camino de paso fijo

### 1.1 Qué es el camino de paso fijo en el código

- `0x2ed24` es el **método virtual +8 de `iz_1::CFontManager`**. Su vtable está en `0x1a9404` (typeinfo `N4iz_112CFontManagerE`). La subclase `CFontManager_2` (vtable `0x1a9580`) hereda el mismo +8.
- El juego crea cuatro gestores globales en `iz_main.cpp`, en la función `0x1bb0`, a partir de la base `0x1ff2a0`. Sus NFTR se cargan en este orden:

| Casilla | NFTR | Clase |
|---|---|---|
| `+0x1c` = `0x1ff2bc` | FONT8 | CFontManager |
| `+0x20` = `0x1ff2c0` | RUBI8 | CFontManager |
| `+0x24` = `0x1ff2c4` | FONT12 | CFontManager |
| `+0x28` = `0x1ff2c8` | FONT12T | CFontManager_2 |

  La correspondencia sale de las llamadas a `0xebb14` (carga de NFTR en `0x218c`–`0x21b8`) y de `0xeba44(gestor, NFTR, 0, 0)`.
- Dentro de `0x2ed24`:
  - `n = strlen/2` (`0x2f07c`): **una celda de caché GTSH por carácter**.
  - El lápiz avanza `FontGetCharWidth(tipo)` (`0x2f350`), que es la constante de `code.bin 0x25AF98` = (12, 8, 12, 4); `tipo` = `[gestor+0x24] & 0xff`.
  - Solo con el tipo 3 (RUBI) se usa `NWFontGetCharWidth` (`0x2f370`–`0x2f420`).
  - La longitud de cada carácter la decide `0xd306c`: los bytes `0x20`–`0x7E` y `0xA1`–`0xDF` ocupan 1 B y todo lo demás ocupa 2 B. Cualquier código kanji se lee como un carácter de 2 B.
- El camino proporcional es `0xe6214`, un método no virtual del mismo gestor. Lo usan `CSprDialog.cpp` (diálogo), `CSprMenuCtrl.cpp` y las pantallas `CMain*` de menú.

### 1.2 Quién llama al paso fijo

La lista completa está en `cro/llamadas.json`. Contiene **76 llamadas** a `[vtable+8]`, identificadas por el `__FILE__` que el juego pasa en r1. El tamaño del búfer sale de los argumentos `[sp+0x18]` × `[sp+0x1c]` / 2 / 0x20, que da el número de celdas cuando se ha podido leer.

| Texto | Llamada (fichero:línea) | Gestor | Celdas | Origen del texto |
|---|---|---|---|---|
| **Rótulo de lugar** del minimapa | `0x7a54c` CSubAdventureScreen.cpp:615 | FONT8* | **10** (80×8) | eve.pkb `0x4037` arg 3 |
| Caja grande de la pantalla de aventura (objetivo) | `0x7a090` CSubAdventureScreen.cpp:497 | FONT12 | 128 (64×128) | eve.pkb `0x402f` arg 2/3 (cabecera y objetivo) |
| Texto corto de aventura | `0x7a36c` CSubAdventureScreen.cpp:554 | FONT8* | 4 (32×8) | sin atar |
| **Ficha de jugador** | `0x128418`/`0x128474`/`0x128790`(:870)/`0x12938c`(:927)/`0x129fe8` CSubMenuScreenCharStatus.cpp | FONT8/FONT12 | no leído | unitbase.dat `+0` (nombre) y unitbase.STR (descripción, puntero u16 `+94` ×32) |
| Presentación de jugadores del partido | `0x1317c4` CSubPlayScreenPlayerIntro, `0x13fd00` CMainPlayScreenPlayerIntro | ? | 12 (48×16) | nombre de unitbase |
| Barra y nombres del partido | `0x154788`…`0x154a64` util_play.cpp:266–306 (6 llamadas) | FONT8* | no leído | nombres de unitbase |
| Carpeta (binder, pantalla inferior) | `0x8e95c`, `0x8e9f4`, `0x8eb44`, `0x8ebec`, `0x8f5cc` CSubMenuScreenBinder | FONT8/12 | — | nombres y datos de jugador |
| Menú de comandos, red de contactos, fichaje, cazatalentos | CSubAdventureScreenCmdMenu (8), Jinmyaku (3), ScoutResult (4), HeadhuntResult (4), Inabikari_Menu | varios | — | nombres de unitbase |
| Guardar partida | CMainMenuScreenSave (10) | FONT8/12 | 48 (192×16), 95 (152×40) | lugar, nombre y equipo |
| Escribir nombre | `0xa8010` CMainMenuScreenEnterName | FONT12 | **24** (96×16) | teclado |
| Tienda, técnicas, entrenamiento, formación, bonus, acción, encuentro, WLDL/WfDL/Wc | Shop (3), Waza_den, Tokkun (12 celdas), Formation (16 celdas), ClearBonus(Mini), ActionMini, Encount, Title* | varios | — | objetos, técnicas y nombres |
| FONT12T | `0xb30e0` util_play.cpp | FONT12T | — | sin atar |

\* «FONT8» indica qué gestor se usa, no qué BCFNT se dibuja (ver §1.3).

**Pestaña del nombre del hablante:** en la CRO **no aparece como paso fijo**. `CSprDialog.cpp` solo llama al camino proporcional (`0xe6214` desde `0x71ec`). La medición de v74 (`nombres_cortos/medir.py`) ya trataba esa pestaña con los dos modelos. Probablemente allí no hacen falta bigramas; si se usan en `unitbase +16`, se verán por el camino proporcional (§4).

### 1.3 Incógnita: el tipo de fuente de cada gestor

`FontGetCharWidth` lee el tipo en `gestor+0x24`, pero ninguna instrucción de la CRO escribe ese campo:
- `NNS_G2dFontInitShiftJIS` (`code.bin 0x14944c`) es un simple `bx lr`.
- El constructor `0xeba9c` no toca `+0x24`.

Si la memoria del gestor sale a cero, los cuatro gestores tienen el tipo 0, es decir, FONT12.bcfnt con paso 12 × 1,25 = **15 px**. Eso cuadra con el modelo que se ha usado desde v74 para el rótulo, que según §1.2 va con el gestor FONT8. No está demostrado: hay que medirlo en la fase 0. Si algún gestor tuviera tipo 1 (FONT8.bcfnt, celda de 11 px y paso de 10 px), sus textos necesitarían bigramas propios en FONT8.bcfnt, y en 10 px apenas caben dos letras finas.

## 2. Inventario de pares

Resultados de `inventario.json`. Todos los textos están en latín y se cuentan una sola vez. Las cabeceras de objetivo (arg 2) y los objetivos (arg 3) se cuentan como textos separados. Las descripciones se cuentan por línea.

Particiones:
- **A:** pares desde el principio del texto.
- **B («relleno»):** pares dentro de cada palabra; la letra impar final se une al espacio siguiente y no se cruzan palabras.
- **C:** como A, pero el par que no cabe en 15 px se parte.

| Campo | Textos | Letras | Casillas A | Pares A | Pares B | Casillas C | Pares C | Máx. casillas C |
|---|---|---|---|---|---|---|---|---|
| Rótulos actuales (v81) | 80 | 672 | 350 | 164 | 150 | 402 | 124 | 7 |
| Rótulos largos v76 (propuesta + sin cambios) | 81 | 951 | 494 | 181 | 159 | 535 | 151 | **9** (≤ 10) |
| Objetivos (0x402f) | 91 | 1.609 | 827 | 230 | 204 | 849 | 200 | 12 |
| Nombre ficha (unitbase +0) | 1.740 | 10.188 | 5.611 | 571 | 565 | 6.237 | 420 | 6 |
| Nombre lista/hablante (+16) | 1.748 | 10.233 | 5.634 | 572 | 566 | 6.264 | 421 | 6 |
| Nombre largo (+32) | 18 | 201 | 103 | 77 | 70 | 117 | 65 | 9 |
| Descripciones (unitbase.STR, por línea) | 2.050 | 37.136 | 19.014 | 763 | 705 | 19.760 | 658 | 14 |

Unión de los campos (pares distintos):

| Alcance | A | B | C |
|---|---|---|---|
| Fase 1: rótulos (actuales + v76) | 222 | 179 | 167 |
| Fase 2: + nombres | 631 | 603 | — |
| Todo | **995** | 928 | **812** |

- **Cobertura con A (todo):** los 100 pares más frecuentes cubren el 57 % de las apariciones, los 300 primeros el 86 % y los 500 primeros el 95 %. Con un tope de glifos, los pares raros pueden ir partidos en dos letras.
- **Caracteres que se usan:** 83 (letras, cifras, `!(),.:;?¡¿`, las acentuadas y la ñ).
- **Ejemplos con A:**
  - «Instituto Wild» → In|st|it|ut|o␣|Wi|ld (7 casillas).
  - «Caseta del club» → Ca|se|ta|␣d|el|␣c|lu|b (8).
  - «H. de negro» → H.|␣d|e␣|ne|gr|o (6).
- B no ahorra glifos que compensen: entre 5 y 15 % menos pares, pero más casillas (366 frente a 350 en los rótulos).

## 3. Huecos en FONT12.bcfnt

Resultados de `huecos.json`.

- **Estructura:** 7.111 glifos (1:1 con 7.111 codepoints). TGLP en formato A4 (11), celda de 15×16, 30 hojas de 256×256 (32.768 B cada una) y 16×15 = 240 celdas por hoja. Capacidad: 7.200 celdas, de las que **89 están libres**.
- **CMAP:** Unicode, en 20 bloques:
  - 4 bloques directos: ASCII, hiragana, katakana y `FF08`–`FF5E`.
  - 15 bloques de tabla: griego, cirílico, 12 tramos de CJK y `FF61`–`FFE5`.
  - 1 bloque de búsqueda (método 2) con 5.772 entradas.
  - El juego pasa de Shift-JIS a UTF-16 (`iz::util::get_code_utf16`) y busca el glifo por Unicode (ver `tools/font_patch.py`).
- **Códigos cp932 de doble byte con glifo:** 6.953. Por bloque:

| Bloque | Códigos |
|---|---|
| Kanji de nivel 1 | 2.965 |
| Kanji de nivel 2 | 3.390 |
| Símbolos, kana y latín | 524 |
| NEC | 74 |

- **Escaneo de la recopilación** (inazuma1, inazuma2 con blizzard, inazuma3 con bomber, inazuma3_ogre, `menu/`, `import/*.itx`, `message/`, las 4 CRO y `static.crs`, `code.bin`). Se descomprimen LZ10, SSZL y ARCV. Los `.pkb` de `script/` y `logic/` se trocean con su `.pkh`. Se omiten vídeo, modelos, efectos, caras, sprites y mapas.
  - **Fuentes de texto** (toda racha ≥ 2): 3.227 códigos distintos.
  - **Resto** (texturas, CRO, code.bin; solo rachas ≥ 3 con al menos 1/3 de kana): 4.538.
  - **Unión:** 5.991.
  - Primer intento, con rachas ≥ 2 en todo: marcaba los 11.280 códigos posibles. Era ruido y se descartó.
- **Con glifo y usados:** 2.832 según el escaneo fiable y 4.369 contando también el ruidoso.
- **Con glifo y nunca vistos en el escaneo fiable:** 4.121 (3.029 de nivel 2 y 887 de nivel 1).
- **Con glifo y nunca vistos en ningún escaneo:** **2.584** (2.015 de nivel 2, 498 de nivel 1, 50 símbolos y 21 NEC). La lista está en `huecos.json → libre_total_codigos`; por ejemplo: 弌乖亂亅豫舒弍于亞亟亠亢亰亳从仄仆仂…
- **¿Basta con reasignar?** Sí. Hacen falta 812–995 glifos y hay 2.015 kanji de nivel 2 libres incluso con el criterio conservador. Se redibuja la celda del kanji y se cambia su CWDH, como hizo v75 con el latín. El tamaño del fichero no cambia, el CMAP no se toca y los códigos son JIS X 0208 estándar. Es mejor evitar los bloques NEC e IBM.
- **¿Ampliar el CMAP?** No hace falta y `font_patch` no puede hacerlo: solo reescribe celdas y CWDH, e `ie123kit.nucleo.fuentes.bcfnt` solo lee. Solo hay 89 celdas libres; más glifos exigirían hojas nuevas, recolocar los bloques CWDH y CMAP y aumentar la memoria que ocupa la fuente. Además, un código del área de usuario (`F040`…) depende de cómo lo convierta `get_code_utf16`, y eso no se ha verificado. Descartado.
- **La fuente es compartida.** `font/FONT12.bcfnt` está en la raíz de `archive.fa` y la usan los tres juegos, así que los kanji reasignados no se podrán usar en IE2 ni en IE3. Por eso el escaneo incluye todo. Hay que mantener un registro fijo (código → bigrama) y usarlo también en las futuras traducciones de IE2 e IE3.

## 4. Riesgos

- **Kinsoku, mayúsculas y furigana.** No se ha localizado la tabla de kinsoku. Estas tablas contienen puntuación y kana pequeños, nunca kanji de nivel 2. La furigana va entre marcadores ASCII `%NF` y solo se inserta en el diálogo; los bigramas solo irían en campos de datos concretos, no en el texto del diálogo. En el camino de paso fijo, la única rama especial por tipo es la de RUBI (tipo 3). No se ha visto ninguna conversión de mayúsculas.
- **El mismo texto por los dos caminos.** Pasa con seguridad con los nombres de unitbase:
  - Paso fijo: ficha, carpeta inferior, partido y fichajes.
  - Proporcional: `CSprMenuCtrl`, `CMainMenuScreenBinder`, `Formation`, `CharaSelect`, `ReplaceUnit`, `ScoutResult` y probablemente la pestaña del hablante.

  No es grave. Los dos caminos colocan la tinta con la misma fórmula, `lápiz + trunc((15 − advance)/2) + left`, y en el proporcional el lápiz avanza `advance`. Basta con dar al bigrama `advance` = ancho + 1 y `left` = 1 − trunc((15 − advance)/2), el mismo criterio que v75: se prioriza el diálogo y, en el paso fijo, la tinta queda a 1 px del borde izquierdo de la casilla. Un par con tinta de 15 px no deja hueco con el carácter siguiente en ninguno de los dos caminos, así que conviene limitar la tinta a 14 px.

  Riesgo aparte: los rótulos y objetivos de eve.pkb podrían reutilizarse en el diálogo mediante `%s`. No se ha visto, pero hay que comprobarlo con el mapa de referencias `C.text_refs` antes de la fase 1.
- **NFTR.** Los kanji reasignados siguen en FONT12.NFTR y FONT8.NFTR de IE1 con su avance de kanji. Ninguno de los dos caminos usa la NFTR para colocar glifos (motor.py). El corte de menú a los 10 caracteres (lección v47) cuenta caracteres, así que un bigrama cuenta como uno, que es justo lo que se busca. Las NFTR están bloqueadas y no se tocan.
- **Búsqueda y ordenación.** No se ha localizado cómo ordena la carpeta. Si ordena por los bytes del nombre, los nombres con bigramas (`0x98`–`0xEA`) quedarían detrás de los que empiezan en latín (`0x82xx`) y el orden alfabético se rompería. Hay que probarlo en la fase 2. Mitigación: empezar el nombre siempre con una letra suelta, o no usar bigramas en `+16`.
- **Teclado y entrada de texto.** `EnterName` dibuja por paso fijo (24 celdas), pero su teclado no genera kanji, así que no hay conflicto. `ngword.txt`, `dakuten.txt` y `handaku.txt` son kana. Riesgo menor: nombres recibidos por comunicación local o intercambio (`CMainTitleScreenTrade`, WLDL) desde una copia japonesa que contengan justo esos kanji de nivel 2 se verían como pares de letras.
- **Límite de celdas del búfer.** Un bigrama ocupa una celda GTSH, como cualquier carácter. La regla de 10 celdas del rótulo (lección del 2026-09-16) se mantiene, pero ahora son 10 casillas de hasta 2 letras. Los espacios de centrado también cuentan como casillas.
- **Bloqueo v20.** `dialogue_lock.py` comprueba el hash de la FONT12 base de `--extra-files`. Los bigramas irían en una capa posterior, igual que v75 (`extra/font/FONT12.bcfnt`), sin tocar los 5 ficheros congelados. La autorización del 2026-09-16 cubre el dibujo latino. Redibujar celdas de kanji con letras es una extensión que el usuario debe confirmar expresamente.

## 5. Prototipo visual

Carpeta `previews/`, escala ×3. Las líneas grises separan las casillas de 15 px y la línea roja marca el límite del campo (10 casillas en el rótulo, 7 en el nombre de 16 B). En cada imagen hay cuatro filas:
1. Actual (v75).
2. Pares con el espaciado natural del diálogo, centrados en la casilla.
3. Pares con el hueco repartido.
4. Partición C: el par demasiado ancho se parte y su primera letra se pega a la derecha.

| Imagen | Actual | Pares A | C |
|---|---|---|---|
| `1_Instituto_Wild_x3.png` | 14 casillas: no cabe | 7 | 8 (se parte «Wi») |
| `2_Caseta_del_club_x3.png` | 15 | 8 | 8 |
| `3_Aurelia_x3.png` | 7 | 4 | 4 |
| `4_H_de_negro_x3.png` | 11: no cabe en 7 | 6 | 6 |
| `5_Goleador_del_Raimo_x3.png` (primera línea de la descripción de Axel) | 33 | 17 | 19 |
| `6_pero_se_esfuerza_e_x3.png` (segunda línea de la descripción de Axel) | 28 | 14 | 14 |

En las filas 2 y 3, los pares anchos («Ca», «mo») invaden la casilla vecina. En el juego no podrían hacerlo, porque la celda mide 15 px. Por eso la fila 4 es la única realista.

`previews/anchos.json` recoge la anchura de tinta de los 995 pares:
- Natural: 261 pasan de 15 px.
- Hueco repartido con 1 px mínimo: **207** pasan de 15 px. El máximo es 21 px.

## 6. Plan por fases

| Fase | Contenido | Glifos | Builds | Esfuerzo |
|---|---|---|---|---|
| **0. Sonda** | 3 bigramas («In», «st», «Wi») en 3 kanji libres de nivel 2 y un rótulo de prueba («Instituto Wild»). Se comprueba en Azahar el paso de 15 px, que el rótulo se dibuja con FONT12 (§1.3) y que el mismo código se ve bien en una pantalla proporcional. | 3 | 1 | 0,5 días |
| **1. Rótulos** | Registro fijo `bigramas.json` (par → código cp932, orden estable, solo `libre_total` de nivel 2). Compositor de glifos a partir de v75, con `advance`/`left` como en §4 y tinta ≤ 14 px. Partición C. Reinserción desde v79/v80 con el límite de 10 casillas, espacios de centrado incluidos. Pasar la lista larga de v76 sin abreviaturas. | ~170 | 1–2 | 1,5 días |
| **2. Nombres** | unitbase `+0` y, si la ordenación lo permite, `+16` (14 letras en 16 B). Probar la carpeta, la ordenación, la formación, el partido y la pestaña del hablante. | +~420 (≈ 600) | 1 | 1–1,5 días |
| **3. Ficha y objetivos** | unitbase.STR (2 líneas que ahora admiten ~28–40 letras; hay que medir el búfer de CharStatus, que no se ha leído) y 0x402f. | +~210 (≈ 812) | 1 | 1–1,5 días |

Reglas que valen para todas las fases:
- Cada glifo nuevo sale del registro, y ningún código del registro puede aparecer en `sjis_usados.json`. Hay que volver a pasar `escaneo_sjis.py` sobre cada candidata.
- Seguir el protocolo QA de IE1: probar en el emulador, parar ante el primer fallo y anotar en `docs/FURIGANA_LECCIONES.md` cualquier fallo nuevo.
- El trabajo se apunta en un issue nuevo, que aún no está creado (este análisis no toca git).
