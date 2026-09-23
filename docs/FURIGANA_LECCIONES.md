# Furigana / reinserción de diálogo — LO QUE NO FUNCIONA (y por qué)

> **LÉEME ANTES de tocar `tools/reinsert.py` o cambiar el manejo de furigana.**
> Cada enfoque de esta lista ya se probó **en emulador** y FALLÓ. No repetir.
> Cada línea está pagada con una build de ~15 min + una prueba del usuario.

## ✅✅✅ SOLUCIÓN POR INGENIERÍA INVERSA del EJECUTABLE (2026-06) — pendiente confirmar in-game

**El muro del furigana (❌#1/#9/#12, el crash `0x00ABFCC0`) es del CÓDIGO, no de los datos** → se
parchea el ejecutable. Hallazgo (desensamblando `work/shared/base_3ds/romfs/cro/ina_main1.cro` con **capstone**):

- El crash `unmapped Read8 … PC 0x00ABFCC0` está en **`ina_main1.cro`** (cargado en 0x00A89000;
  offset de fichero 0x36CC0). La instrucción es **`ldrb r0, [r4]`** — un **bucle que lee una cadena
  byte a byte** (`cmp r0,#0; beq` = busca el NUL). `r4` sale de `ldr r4,[r0]` (campo de estructura).
  Con la línea traducida, **`r4` vale BASURA** (0x5F,0x67,0x69,0x6F,0x72,0x77 = `_giorw`, los mismos
  bytes de los logs) → lee memoria no mapeada → crash.

- **PARCHE (`tools/patch_cro.py`, bounds-check):** los punteros válidos en 3DS son grandes
  (≥0x100000), los corruptos diminutos (<0x100). Hook en 0xABFCC0 → code cave (hueco de 0x00 en
  `.text`, 0xAD9E14): `cmp r4,#0x10000; movlo r0,#0` (basura→cadena vacía) `ldrbhs r0,[r4]` (válido→
  lee normal) `b 0xABFCC4`. La línea corrupta se trata como vacía (el motor salta al final, sin crash);
  las cadenas válidas se leen igual. Idempotente, integrado en `build_3ds_var.py`.

- **Esto ABRE el texto completo en TODO:** `FULLTEXT=1 python tools/reinsert_var.py` traduce los 911
  eventos a texto completo (sistema incluido). **Invalida la conclusión de ❌#13** ("texto-completo-en-
  TODO es IMPOSIBLE"): lo era desde los datos, NO con el parche del código.

**El muro NO era 1 función, eran 4** (cosecha de logs): el texto traducido pasa un puntero corrupto a
varias funciones de cadena, que petan con `unmapped Read`. Todas son el MISMO patrón (puntero válido
≥0x100000, corrupto <0x100) → mismo bounds-check:

| # | Función | Módulo | PC | Parche |
|---|---|---|---|---|
| 1 | ruby/furigana | `ina_main1.cro` | `0xABFCC0` | `tools/patch_cro.py` |
| 2 | `strcpy` (`ldrb [r1]; strb [r0]++`) | `code.bin` | `0x14AC5C` | `tools/patch_code.py` |
| 3 | `getc` (`r1=[r0+0x10]; r0=[r1]`) | `code.bin` | `0x1B3788` | `tools/patch_code.py` |
| 4 | `strcmp` (`and r3,r0,#3 …`) | `code.bin` | `0x184AAC` | `tools/patch_code.py` |

`code.bin` va **comprimido (BLZ)** → `tools/blz.py` lo descomprime; se parchea; `tools/patch_exefs.py`
reconstruye el exefs con el `.code` PLANO y pone el flag compress-code (exheader @0xD bit0) a 0 (el
loader lo carga sin descomprimir, sin recomprimir BLZ). Todo integrado en `build_3ds_var.py`. Caves =
huecos de 0x00 en `.text`. Con esto, **`FULLTEXT=1` traduce los 911 eventos a texto completo**.

**DÓNDE meter el parche de code.bin (saga cara):** code.bin NO tiene hueco seguro — ❌ in-place = solo
4 bytes; ❌ los runs de ceros del `.text` son DATOS que el juego lee por índice → machacarlos = **NO
ARRANCA** (pantalla negra); ❌ extender el `.code` (slack de página / subir `code_size`) → **Azahar
CIERRA al cargar**; ❌ cave en el CRO (cross-module) → falla por DOS motivos: (a) el salto code.bin→CRO
peta el arranque temprano (el CRO se carga ~30 s tarde, las funciones se usan antes), y (b) la zona
@0x50E24+ del CRO **NO es libre** (la rellena la relocación/runtime; escribir ahí PETA `@0xAD9E38`,
confirmado por el log). **CONCLUSIÓN: los 3 parches de code.bin son IMPOSIBLES de colocar** en este setup.

### ❌❌❌ ACTUALIZACIÓN DEFINITIVA (2026-06): NINGÚN parche en el CRO es fiable — ni el del ruby
Lo de "solo `@0x50E14` (cave del ruby) es seguro" / "el parche del ruby FUNCIONA" era **FALSO**, una
conclusión por suerte. Con el log volcando se cazó un crash **DENTRO de mi propio cave del ruby**:
`ExceptionRaised(exception=1, pc=00AD9E1C, code=00ADB0F8)`. `0xAD9E1C` es la 3ª instrucción del cave
(`ldrbhs r0,[r4]`); el valor cargado ahí (`0x00ADB0F8`) **NO es mi instrucción — es un puntero**.
`exception=1` (instrucción indefinida/impredecible, NO un *unmapped Read*) ⇒ **el loader del CRO
SOBREESCRIBIÓ mi cave al cargar**. Toda la run `@0x50E14` es **zona de RELOCALIZACIÓN**, no espacio
libre. Por qué "funcionaba" antes: las builds con el cave de getc roto **crasheaban en `@0xAD9E38`
ANTES de llegar nunca a la ruby (`@0xAD9E1C`)**, así que el cave del ruby **jamás se ejecutó** — el
"0xABFCC0 desaparecido" solo significaba "crashea antes". **No reintentar parches en `ina_main1.cro`.**

**Consecuencia para el furigana:** sin parche de código fiable, las líneas de diálogo CON furigana
solo se pueden dejar en **japonés** (mismo tamaño). Vaciar la lectura dispara la ruby `@0xABFCC0` →
crash (no hay cave que lo salve). El techo ESTABLE = `SAME_SIZE` + `NO_BLANK` (lectura original) +
no traducir líneas con marcador: todo lo demás (menús, avisos, ítems, líneas planas) → español.
Flags nuevos: `NO_BLANK=1` (`reencode_ssd` deja la lectura intacta), `SKIP_CRO=1` (`build_3ds_var`
no parchea el CRO; restaura el `.orig`).

**LOG de Azahar (CLAVE para diagnosticar, antes imposible):** Azahar bufferea y `azahar_log.txt` queda
en **0 bytes**. Causa: **`instant_debug_log=false`** en `%APPDATA%\Azahar\config\qt-config.ini`. Ponerlo
a **`true`** → vuelca al instante → el harvest captura el PC exacto. (Además rota `.txt`→`.old.txt` al
reabrir: el crash de una sesión aparece en `.old.txt` tras la siguiente.) Con esto se CONFIRMÓ el crash
de gameplay: strcpy/getc/strcmp leyendo punteros `<0x10000` (`0x192..0x20C`). (OJO: que `0xABFCC0` no
apareciera NO probaba que su parche funcionase — solo que se crasheaba antes; ver la actualización ❌❌❌
de arriba: el cave del ruby también está roto por la relocalización.)

## ✅✅ SOLUCIÓN DEFINITIVA (2026-06, via Tiniifan/SceneScriptData) — pendiente confirmar in-game

El formato SSD se descifró del TODO gracias a **github.com/Tiniifan/SceneScriptData** (decompilador
de nuestro formato). Lo que invalida casi toda la lista de abajo:
- **El bytecode referencia el texto por ÍNDICE de entrada (0..textCount-1), ESTABLE — NO por offset.**
  Cada instrucción lleva el TIPO de cada arg en **4 bits** (String=0x3). Layout: `id i16, size i16,
  opcode u16, argsCount u8, unk u8, [4·ceil(argsCount/8) bytes de nibbles de tipo], [argsCount×u32]`.
- Por eso TODO el **offset-fixup** (❌#8/#11/#12/#13, `build_string_slots`, `is_grow_safe`) estaba
  MAL: trataba índices estables como offsets y los CORROMPÍA → vacío/crash/Read32/truncado.

**Motor correcto = `tools/ssd_reinsert.py` `reencode_ssd()`:** traduce los diálogos (CRECEN libres,
sin truncar), VACÍA las lecturas furigana **a MISMO TAMAÑO** (espacios ancho completo 0x8140, NO
encoger a 2 bytes ni eliminar → el índice no se desplaza Y el motor las consume sin desbordar), y
**NO toca el bytecode**. Validado offline: **bytecode INTACTO en los 4825 eventos**, estructura válida.

> ⚠️ **RE-APRENDIDO (❌#12 otra vez):** vaciar la lectura ENCOGIÉNDOLA (a 2 bytes) cambia el `textSize`
> del evento. Con marcadores conservados (modo SAME_SIZE), el motor consume 1 lectura por marcador y
> al ser de otro tamaño se DESBORDA → `Assertion Failed!` + `resource exceeds limit` → **pantalla
> negra**. **`tools/validate.py` LO CAZA** (operando corrupto @0x14 = `textSize`). **No saltarse el
> validador con `SKIP_VALIDATE` en builds SAME_SIZE.** El vaciado correcto es mismo-tamaño.
Sustituye a `reencode_var` + offset-fixup. Ver [[ssd-format-spec-scenescriptdata]].

PENDIENTE in-game: ¿la apertura sigue colgando al quitar marcadores (❌#1)? ¿hay que traducir el
texto-display (nombres de zona/objetivos, entradas que no son diálogo ni lectura)?

## Resumen en una frase

El diálogo va en `eve.pkb` como **bytecode con texto inline**. Las palabras con
kanji llevan **furigana**: un marcador `%NF` en el texto + una **lectura** (kana) en
un chunk aparte (numerado `0x02..0x1f`). El motor consume **1 lectura por marcador y
por página (`\f`)**. La reinserción es **mismo-tamaño-en-bytes** (no se puede crecer
sin un desensamblador que recalcule offsets). Todo lo que rompa esa mecánica → cuelga.

## IE3 (2026-09-18) — probado en emulador

Primeras pruebas en juego de la reinsercion de IE3 (`ie123kit.ie3.comun`). El
dialogo de IE3 vive en `evet.pkb`, que es una tabla PLANA sin comprimir, no un
SSD: las entradas no llevan clave (los 102 419 registros tienen instruccion y
argumento a cero) y el script las referencia por INDICE.

### ❌ #16 — `evet` se lee por OFFSET DE BYTES, no por indice

**El hallazgo mas importante de IE3, y corrige lo que se escribio antes en este
mismo documento.** Si un registro de `evet` cambia de tamano, todos los que van
detras se desplazan y el motor sigue leyendo desde el offset viejo: el dialogo
sale con los primeros bytes comidos.

Medido en tres capturas del usuario, y cuadra al byte en las tres:

| build | registros anteriores (base -> build) | delta | bytes perdidos al dibujar |
|---|---|---|---|
| v102 | 260 -> 260 | 0 | ninguno, salio bien |
| v103 | 100 -> 80 | **-20** | **20** (`¡Madre mía! ¡Hoy `) |
| v105 | 260 -> 256 | **-4** | **4** (`¡Br`) |

El delta acumulado de los registros ANTERIORES es exactamente lo que se pierde.

**La prueba que me llevo a la conclusion contraria estaba mal.** Se buscaron
eventos cuyo bloque de `evet` cambia de tamano entre el japones y el europeo y
cuya seccion de codigo del `eve` es identica, y se dedujo que las referencias no
eran offsets. Pero Level-5 reconstruyo LAS DOS cosas al localizar (el europeo
tiene 8 registros donde el japones tiene 22, porque elimino las lecturas
furigana): que el codigo de un evento concreto coincida no prueba nada sobre el
resto, y desde luego no sobre nuestro caso, que es cambiar solo el `evet`.

**Regla: el tamano de cada registro de `evet` es intocable.** Lo unico que se
puede hacer es repartir bytes DENTRO de un grupo (un dialogo y sus lecturas
furigana), porque el dialogo va primero y su offset no se mueve, y el total del
grupo se conserva, asi que los registros posteriores tampoco se mueven. Las
lecturas del grupo si se desplazan, pero al haber quitado los marcadores no se
consumen.

### ❌ #17 — Buscar el offset de evet por correlacion estadistica: FALSO POSITIVO

Intento de recuperar las lineas que no caben a mismo tamano: si el motor lee
`evet` por offset (❌#16), ese offset estara en algun operando del `eve`, se
recalcula al crecer y se acabo el problema.

Se midio, para cada (opcode, posicion de argumento), que fraccion de sus valores
cae exactamente en el inicio de un registro del `evet` del mismo evento. Gano
**0x301a argumento 2 con un 95,0 % sobre 54 380 usos**, muy por encima del
resto. Parecia concluyente.

**Es un artefacto.** Al mirar un evento concreto (31200000), los valores de ese
argumento son 0, 2, 8... y los registros de su `evet` empiezan en 204, 216, 228.
Son numeros pequenos, y en cualquier bloque el offset 0 siempre es inicio de
registro y los primeros registros caen en valores bajos: la correlacion se la
comen los ceros y los dos.

Comprobacion que lo delata en un minuto y que habria que hacer SIEMPRE antes de
fiarse de una correlacion asi: coger un evento suelto y mirar si los valores
tienen el ORDEN DE MAGNITUD de los offsets del bloque. Ademas, de 2 181 eventos
con registros movidos, la recolocacion solo cambiaba algo en **2**: si el hueco
fuera de verdad el del offset, cambiaria en casi todos.

Es el mismo error que ❌#11, con otra ropa. **Sigue sin saberse donde guarda el
`eve` los offsets de `evet`**, asi que el unico modo seguro es el de mismo
tamano: cada registro conserva sus bytes y solo se reparten dentro del grupo.

### ❌ #14 — Anadir paginas `` a un dialogo de IE3: SE PIERDE TEXTO

Sintoma: el dialogo salia con las primeras lineas comidas. Confirmado dos veces
(v102 y v103), con capturas del usuario.

Causa: **de las 79 715 lineas japonesas de IE3 solo 22 llevan ``**, y ningun
dialogo pasa de 3 lineas (34 284 de 1 linea, 31 219 de 2, 14 192 de 3). El motor
dibuja UNA caja por dialogo. El manejador de `` (0x0C) solo hace `x=0, linea=0`:
no borra la caja ni espera al boton. Todo lo que se ponga detras de un ``
anadido se dibuja encima o no se pide nunca.

Es el mismo principio que ❌#5 en IE1 (el numero de paginas del ES debe ser igual
que el del JP), pero aqui la regla es mas dura porque el japones no pagina casi
nunca: **no se anade ninguna pagina**. Si el espanol no cabe en 3 lineas, la linea
se queda en japones.

### ❌ #15 — Maquetar midiendo el ancho REAL de cada letra

El `reflow` de IE1 (`sjis_portador`, 208 px) mide el avance real de cada glifo. El
motor NO: cuenta **12 px fijos por caracter** (`FontGetCharWidth`), da igual que
sea una `i` o una `M`. Medir la tinta da de mas, el motor parte la palabra y la
ultima linea se cae de la caja.

Visto en emulador: «¡Bravo, Paolo! ¡El fútbol» (25 caracteres) salio como
«¡Bravo, Paolo! ¡El fút» + «bol», y se perdio la tercera linea. Los 22 caracteres
que se vieron son exactamente el limite de fabrica.

**Las dos restricciones son distintas y hay que aplicar las dos:**

- **caracteres por linea** = `(ancho + 0x20) / 12` — decide donde parte el motor;
- **tinta de la linea** — decide si se sale de la caja al dibujar, porque el
  dibujo SI es proporcional. Geometria medida en `capas/ie1/v86/ancho_ventana`:
  el panel llega a x≈391, el icono de avance ocupa 370–390 en la 3.ª linea, y la
  caja admite unos **354 px** de tinta.

### Ventana de dialogo de IE3: valores de fabrica

Mismo patron que IE1 e IE2, con el offset de la estructura desplazado:

| juego | modulo | escritura por defecto | ancho | lineas |
|---|---|---|---|---|
| IE1 | `ina_main1.cro` | 0x0465B4 | `[+0x1316]` = 0xF0 | `[+0x1318]` = 3 |
| **IE3** | **`ina_main3ogre.cro`** | **0x039CE0** | **`[+0x131A]` = 0xF0** | **`[+0x131C]` = 3** |
| IE2 | `ina_main2.cro` | 0x04CAB0 | `[+0x131E]` = 0xF0 | `[+0x1320]` = 3 |

0xF0 + 0x20 = 272, a 12 px por caracter → **22 caracteres**, que es lo medido en
emulador.

Los tres sitios que la capa IE2 v15 parchea existen igual en IE3, con
coincidencia unica:

    0x04F3CC  mov r1,#0xF0   ancho que el manejador del dialogo pasa en cada caja
    0x039CEC  mov r2,#0xF0   valor por defecto de la ventana
    0x03A928  mov r2,#0x120  ancho de la rejilla de DIBUJO (sin este, el texto se
                             reajusta pero se sigue dibujando cortado)

> **Alternativa sin tocar el CRO, preferible:** el arg4 de `0x301c` escribe el
> ancho directamente (`strhne`), y el arg5 las lineas. Es un parche de DATOS de
> 4 bytes dentro del evento, no cambia su tamano y respeta la prohibicion de
> tocar CRO y code.bin. Lo documenta `capas/ie1/v86/ancho_ventana/informe.md`
> para IE1; en IE3 los 2 289 `0x301c` tienen arg4 y arg5 a cero, asi que el
> camino esta libre. Su riesgo conocido es la PERSISTENCIA: nada devuelve el
> ancho a 240 al cerrar la ventana, asi que el valor ancho se arrastra a los
> eventos siguientes. Parchear el CRO no tiene ese problema porque deja el ancho
> uniforme, pero es un parche de codigo.

### Pendiente de comprobar: lecturas furigana huerfanas en `evet`

La reinsersion de IE3 quita los marcadores `%NF` del espanol y **vacia** las
lecturas. Eso deja el mismo patron que causo el bug de la zona del club en IE1
(0 marcadores y N lecturas sueltas → el dialogo no cierra y se bloquean los
controles). Alli la solucion fue **eliminarlas**, no vaciarlas; en `evet` no se
pueden eliminar sin cambiar el numero de registros, y las referencias van por
indice. Sin sintoma observado todavia, pero queda anotado.

Lo que si se corrige ya, por ❌#12: las lecturas se vacian **a su tamano
original**, sin encogerlas.

## ❌ Enfoques que CUELGAN (no reintentar)

| # | Enfoque | Resultado | Por qué |
|---|---|---|---|
| 1 | **Quitar los marcadores `%NF`** del diálogo (texto español limpio) | **CUELGA al crear partida** (v12, v24/STRIP) | El motor EXIGE los marcadores. Sin ellos, la apertura (ev 92010200) descuadra el consumo de lecturas y cuelga. **Los marcadores son obligatorios.** |
| 2 | Marcadores al **final** de la línea (trailing) | CUELGA (v13) | `%NF` intenta dibujar ruby sobre el carácter *siguiente*, que no existe → fuera de límites. |
| 3 | Marcador seguido de **espacios de 1 byte** (half-width) | CUELGA (v14/v15/v16) | `%NF` espera **N caracteres de ANCHO COMPLETO** (2 bytes, como los kanji). Con 1 byte el motor se desalinea. |
| 4 | Rellenar páginas ES vacías para casar el conteo (`%NF` sin texto detrás en una página) | CUELGA al crear partida (v20) | Una página solo-marcadores/vacía descuadra el motor. |
| 5 | Traducir chunks donde el **nº de páginas `\f` ES ≠ JP** | CUELGA (v16/v19/v20) | El reparto de marcadores por página deja de casar 1:1. **Solución v16: solo traducir si `es.count(\f)==jp.count(\f)`; si no, dejar en japonés.** **MEJORA (2026-06): RE-PAGINAR** — en vez de rechazar la línea, repartir las líneas del ES en EXACTAMENTE `len(orig_pages)` páginas no vacías (`_repaginate` en `reinsert.py`), conservando los marcadores por página original → el conteo casa y se RECUPERA la traducción. Muchas líneas del principio (Willy 92010250…) estaban traducidas pero el traductor usó `\n` donde el JP usa `\f` (p.ej. jp=2 págs, es=1) → se rechazaban. La re-paginación las recupera. **NO se re-pagina la APERTURA (eid 90000000..92010249)**: ahí se mantiene byte-idéntico a la build que crea partida (gate `allow_repaginate` en `reencode_ssd`; cualquier cambio de más en la apertura la congela, ❌#1). Sigue limitado por el presupuesto mismo-tamaño (si los marcadores+texto no caben, se rechaza igual → el intro trunca/queda parcial; es el techo duro del sistema, que NO puede crecer ❌#9). |
| 6 | Dejar un **`%NF` huérfano** dentro del texto español (venía de algunas líneas `auto-ia`/`revisar`) | CUELGA en zonas concretas (v18/v21/v23) | El marcador suelto, sin N chars de ancho completo detrás, descuadra. **Solución: `reinsert` quita cualquier `%NF` del ES antes de codificar.** |
| 7 | Cargar un **save state del emulador** hecho con OTRA build | "Cuelga" siempre | NO es bug nuestro: los save states guardan memoria de una build concreta. **Probar siempre con partida NUEVA.** |
| 8 | **[Longitud variable]** offset-fixup que actualiza **cualquier u32** que coincida con un inicio de chunk | **Error Fatal al avanzar el 1er diálogo** (build var inicial) | Muchos **operandos numéricos** del bytecode (p.ej. `1000`, coordenadas, IDs) coinciden por casualidad con una posición de inicio de chunk → el fixup los "recoloca" (`1000→972`) y **corrompe el evento**. Esos valores apuntan a **chunks vacíos** (NUL consecutivos) o a **diálogo** (que se consume secuencialmente, nunca por offset). **Solución: solo actualizar offsets cuyo destino sea un chunk TIPADO (`part[0]` 0x01–0x1f: lectura furigana / debug / control) o un BYTE-ID (1 byte ≥0x80).** Ver `_is_ref_target()` en `reinsert_var.py`. Pasó de corromper decenas de u32/evento a ~7 referencias reales/evento. |
| 9 | **Hacer CRECER una línea con furigana** (reinyectar marcadores + texto ES más largo) | **Error Fatal al AVANZAR** (no al mostrar: la línea se ve completa) | El evento queda perfecto a nivel de datos (1 sola ref de texto, recolocada; sin campos de longitud) pero el **runtime del motor de ruby se descuadra** con el diálogo más largo. NO editable desde el evento. **RE-CONFIRMADO (2026-06) con el offset-fixup PRECISO nuevo** (`GROW_INTRO`/`grow_fg`): el dato valida 100% pero **sigue crasheando al avanzar** → es del runtime, no de los datos. **Solución: NO hacer crecer líneas con furigana.** En español el furigana no aporta → en HISTORIA se hace **STRIP** (quitar marcador + vaciar lectura + texto completo); en SISTEMA/INTRO se deja a **mismo tamaño** (=v25). **`tools/validate.py` ahora lo CAZA** (chunks con %NF que crecen) y el build aborta → no se compila una ROM con este crash. |
| 10 | **REUBICAR** una línea de furigana (aunque NO crezca) por hacer crecer **otra** línea del mismo evento | **Texto vacío + no cierra el diálogo + se congela** (NPC de サークル棟エリア / 92010510) | Si un evento de sistema/intro conserva furigana pero crece una línea PLANA suya, todo lo que va detrás (incluidas las líneas de furigana) **se desplaza**. Reubicar una línea de furigana rompe el ruby igual que hacerla crecer (mismo runtime de ❌#9), aunque su contenido no cambie. **Solución: los eventos que conservan furigana (sistema/intro, eid≥90000000) deben quedar a MISMO TAMAÑO en TODAS sus líneas** (planas incluidas) → byte-idénticos, no se reubica nada. Ver rama `not strip` en `reencode_var`. |
| 11 | **[Longitud variable]** offset-fixup que reubica un u32 según el **TIPO del chunk** al que apunta (`_is_ref_target`: tipo 0x01–0x1f o byte-id) | **Error Fatal `unmapped Read32 @ … PC 0x001C8D68`** a los ~20 min (al hablar con cierto NPC) | El tipo del chunk NO distingue una referencia de un operando numérico: el diálogo (tipo 0x01) **nunca se referencia** y muchísimos **contadores/índices** del bytecode coinciden por azar con una posición de diálogo (839/901 eventos game1). El fixup los convertía en offsets grandes → un handler los usa como **contador** y lee un array de u32 hasta salirse de la RAM (`Read32` secuencial). **Solución (la que funciona): identificar los slots de string por ESTADÍSTICA, no por tipo.** El bytecode es un stream `<u16 idx><u16 len><u32 opcode><operandos>` (ver FORMATOS.md); un `(opcode,slot)` es offset-de-string si sus valores caen SIEMPRE en inicio de chunk o 0 y **casi nunca a media cadena**. Reubicar SOLO esos. Validado offline: **0 operandos numéricos alterados**. Ver `build_string_slots()`/`_instr_operands()` en `reinsert_var.py` (sustituye a `_is_ref_target`). |
| 12 | **[Longitud variable] STRIP_ALL**: stripear TODOS los eventos incl. intro/sistema (quitar furigana de TODO) | **PANTALLA NEGRA al crear partida NUEVA** (crash `unmapped Read8 ... PC 0x00ABFCC0`, lee bytes de cadena como puntero: `0x5F,0x67,0x69,0x6F,0x72,0x77` = `_giorw`) | **Re-confirma ❌#1**: la **apertura (92010200) EXIGE sus marcadores** aunque el strip esté BALANCEADO (`drop_readings` no basta). Es del **runtime de consumición de lecturas**, NO detectable offline: `validate` pasa TODOS los checks estructurales (0 operandos, 0 refs rotas, 0 vacíos, 0 ❌#9); el único indicio fue el aviso de desbalance (72/690 ev) pero es **mayormente preexistente del gameplay**. Verificado: **0 eventos referencian lecturas/byte-id por offset** → no hay señal offline limpia. **El MISMO crash `0x00ABFCC0` afecta al tutorial `81000040`** (eid<90000000, stripeado en el build por defecto) → hay eventos de gameplay puntuales que tampoco toleran strip (issue #18). **Solución: NO stripear intro/sistema (eid≥90000000 salvo zonas seguras 92010510+); para quitar el japonés visible del intro sin crashear → conservar marcadores y VACIAR la lectura (espacios ancho completo, mismo tamaño, balanceado) — no quita el truncado pero oculta el japonés (`_blank_reading` en `reinsert_var.py`).** ⚠️ **PERO** hay eventos HIPER-SENSIBLES (mucha densidad de furigana, p.ej. tutorial `81000040` con 473 marcadores) que crashean con CUALQUIER cambio: **strip → `0x00184AAC`, blank-readings → `0x00ABFCC0`** (la traducción INPLACE mismo-tamaño trunca/descuadra algún marcador). **Para esos: `DONT_TOUCH` = dejar 100% ORIGINAL (japonés, sin traducir) → estable, sin crash.** Mejor japonés estable que crash. Se amplía el set según se cazan con la cosecha de logs. |
| 13 | **[Longitud variable] CRECER (strip a texto completo)** eventos con **refs a byte-id de furigana** | **DIÁLOGO VACÍO** al crecer (**727/900 eventos game1, ~80-90%**) | **LÍMITE DURO confirmado.** Las refs a los byte-id (las etiquetas de 1 byte ≥0x80 que preceden cada lectura) **COMPARTEN opcode con operandos numéricos** (`op 0x01026001` = 76% números, `0x0102700e` = 34%…) → **no se pueden reubicar sin corromper los números = crash Read32 ❌#11.** Por eso `build_string_slots` (correctamente) NO las clasifica. Al CRECER el texto, esos byte-id se desplazan y la ref (sin reubicar) apunta a basura → **vacío**. En versiones viejas SAME-SIZE no pasaba (nada se desplazaba). **Solución: `is_grow_safe(dec, string_slots)` clasifica cada evento — solo CRECE (texto completo) los ~10-22% SIN refs no-reubicables; el resto → blank-readings (mismo tamaño, español truncado pero VISIBLE, sin vacío). Elimina vacío+crash SISTEMÁTICAMENTE (adiós whack-a-mole).** Conclusión: **texto-completo-en-TODO es IMPOSIBLE** con furigana + fixup preciso; lo máximo estable = truncado-visible en la mayoría + completo donde se pueda. |

## ✅ Enfoque ACTUAL (build var STRIP-historia): texto completo + furigana solo en intro

Tras confirmar que **hacer crecer una línea con furigana CUELGA al avanzar** (❌#8,
límite del runtime de ruby — el evento queda perfecto pero el motor se descuadra con
el diálogo más largo) y que **quitar furigana CUELGA al crear partida** (❌#1, solo en
los eventos de apertura), la estrategia que combina ambas restricciones:

- **HISTORIA** (`eid < 90000000`): **STRIP** — quitar marcadores `%NF`, **crecer el
  texto a longitud COMPLETA** (sin cortes) y **vaciar las N lecturas siguientes**
  (espacios, mismo tamaño; conservan su byte de tipo 0x02+ → el motor las ignora).
  En español el furigana no aporta nada. → **texto ES completo y limpio.**
- **SISTEMA/INTRO** (`eid >= 90000000`, incl. club 92010100): **FURIGANA_INPLACE a
  MISMO tamaño** (= v25): marcadores por página + N espacios ancho completo, solo
  páginas `\f` que casan, sin `%NF` huérfano, sin truncar marcadores. NO crecer (❌#8).
  Conservar el furigana aquí evita el cuelgue del crear-partida (❌#1).

`reinsert_var.py` `reencode_var(strip=eid<90000000)`. Reparto game1: **706 ev /
10613 líneas completas** (88%) + 315 ev / 1419 líneas furigana (intro/sistema).

**Estado:** PENDIENTE confirmar en emulador (build var STRIP-historia). Lo anterior
(`FURIGANA_INPLACE` mismo-tamaño en TODO, v23/v25) arranca, crea partida y muestra
diálogo en español, pero **trunca** (este es justo el problema que STRIP-historia
resuelve para el grueso del juego).

### ❌❌ (2026-06) INPLACE del INTRO en el path `ssd_reinsert` → CONGELA el crear-partida
Porté `_furigana_body_bytes` (INPLACE v25) a `reencode_ssd` para traducir el intro y quité
`SYS_ORIG`. Offline TODO perfecto (92010100/92010200 mismo tamaño, marcadores 6→6, lecturas
7→7, balance 0, `validate` verde). **En emulador: CONGELA en la pantalla de título al CREAR
PARTIDA** (no pasa de ahí). Re-confirma ❌#1/❌#12: el crear-partida (rango **92010100..92010509**)
EXIGE sus eventos INTACTOS — ni INPLACE mismo-tamaño con marcadores+lecturas balanceados lo
tolera (al menos en este path, y/o el fallback global mete una traducción de otro evento con
estructura de página distinta). **No verificado si fue el INPLACE o el global; da igual: regla
dura = dejar el intro/sistema en JAPONÉS (`SYS_ORIG=1`), el crear-partida no se traduce.** El
gameplay (`<90000000`) SÍ crece/traduce bien. Build jugable = `SYS_ORIG=1` + fallback global.

### Hechos confirmados del bytecode (offline, evento 92010100)
- La sección de texto tiene **una sola** referencia a la zona que se mueve (`code+2960`
  = byte-id `0xbc` antes de la lectura れんしゅう); el offset-fixup ya la recoloca bien.
- **No hay campos de longitud/offset-de-final** del diálogo en el bytecode (no existe
  `len`/`end` que actualizar al crecer). Los u32 que caen en `[first_change,tlen)` y
  coinciden con un inicio de chunk son **constantes de opcode** (273/819/305/529…),
  NO punteros: reubicarlos corrompe el evento. Por eso `_is_ref_target` solo toca
  cadenas tipadas/byte-id. ⇒ a nivel de DATOS el evento queda correcto al crecer; el
  cuelgue de ❌#8 es del **runtime** del motor, no editable desde el evento.

## ⚠️ Problemas ABIERTOS del enfoque que funciona (v23/v25)

### 1. Texto cortado (truncado)
El presupuesto **mismo-tamaño** + el coste de los rellenos de ancho completo dejan
poco espacio → frases recortadas ("Vaya, entr" en vez de "Vaya, a entrenar"). 
**Solución real: longitud variable** (`tools/reinsert_var.py` + `fa_repack.py` +
`build_3ds_var.py`) → reconstruye el contenedor con eventos más grandes.

**Modelo de referencias del evento SSD (clave para el redimensionado).** La sección
de texto (`d[s10:]`) es una secuencia de records separados por NUL:
`<byte-id><NUL><cadena tipada><NUL>...`. Hay tres clases:
- **Diálogo** (`part[0]`=0x01, estilo): se **consume SECUENCIALMENTE** (el motor lo
  recorre NUL→NUL). **Nunca se referencia por offset** → se puede agrandar libremente.
- **Lecturas furigana / strings de debug / control** (`part[0]` 0x02–0x1f, p.ej.
  `01_3.SAD`, `れんしゅう`) y sus **byte-id** (1 byte ≥0x80 que las precede): **SÍ se
  referencian por offset** (u32 rel a `s10`) desde el bytecode `d[:s10]`.
- **Chunks vacíos** (NUL consecutivos): nunca son destino de referencia.

Al agrandar el diálogo, todo lo que va detrás se desplaza; hay que **sumar el delta a
cada offset del bytecode que apunte a una lectura/debug/byte-id movido** (offset-fixup).
**Solo a esos** (ver ❌ #8): tocar operandos numéricos coincidentes cuelga el juego.

### 2. BUG (CAUSA REAL HALLADA): controles bloqueados al hablar con NPC en `サークル棟エリア`
- **Síntoma:** al hablar con un NPC de la zona, el diálogo **no muestra texto y no se
  cierra**; el juego NO crashea (sonido + sprites siguen vivos) pero **los controles se
  bloquean**. Afecta a TODA la zona, no a un NPC suelto.
- **Causa REAL (verificada offline):** **desincronización marcador `%NF` ↔ lectura
  furigana**. El motor consume **1 lectura por cada marcador**. El STRIP quitaba los
  marcadores de las líneas traducidas pero **VACIABA las lecturas dejándolas como chunks**
  (tipo 0x02 + espacios). Resultado en ev **92010510**: **0 marcadores pero 29 chunks de
  lectura** huérfanos en el stream → el motor los lee como líneas vacías / se descuadra
  y nunca cierra el diálogo. (El STRIP "vaciar" NO arreglaba el bug, solo lo disfrazaba.)
- **SOLUCIÓN (la que funciona):** **ELIMINAR** (no vaciar) las lecturas de cada línea
  traducida, hasta la siguiente línea de diálogo (flag `drop_readings` en `reencode_var`).
  Así marcadores y lecturas quedan **balanceados** como en el original (zona club: de 28
  chunks huérfanos → 0). Es viable gracias al **offset-fixup preciso por slot** (ver ❌#11):
  al borrar chunks, las referencias string se reubican; si alguna apunta a un chunk
  borrado, el evento revierte a japonés (seguro). Validado offline: 0 operandos numéricos
  alterados, 0 referencias nuevas rotas. **PENDIENTE confirmar en emulador.**
- Nota: `STRIP_ZONA` y el rango `92010510..92011000` siguen marcando qué zonas se STRIPean
  (post-intro, seguras); el fix de arriba corrige CÓMO se hace el strip de las lecturas.
- **(2026-06) RE-CONFIRMADO y PORTADO al path actual `reencode_ssd`** (motor SSD por índice):
  el path que CRECE el gameplay vaciaba **TODAS** las lecturas del evento, pero solo quita
  marcadores de las líneas TRADUCIDAS → las líneas NO traducidas se quedaban con marcador y SIN
  lectura (huérfanos). Síntoma en datos: eid 10020022 ORIG 30 marcadores/29 lecturas → 5
  marcadores/**0** lecturas (desbalance). **Fix:** contador `pending` en `reencode_ssd` — solo se
  vacían las N lecturas de cada línea TRADUCIDA (1 por marcador); las de líneas no traducidas se
  CONSERVAN (marcador+lectura japoneses, balanceado). `validate.py` lo mide: **48 → 0 eventos
  desbalanceados**. La regla unificada del vaciado va ligada a `system`: mismo-tamaño (marcadores
  conservados) → NO vaciar (la ruby se invoca, necesita lectura válida); crecer/STRIP (marcadores
  quitados) → vaciar solo las de líneas traducidas. **PENDIENTE confirmar en emulador.**
- **(2026-06) `validate.py` ahora es consciente del crecimiento:** en modo que crece (sin
  `SAME_SIZE`) tolera el cambio de `textSize@0x14` pero **verifica que sea coherente**
  (`textSize == len(nd) − _text_start(nd)`); en `SAME_SIZE` sigue estricto. Antes el validador
  de mismo-tamaño marcaba los 627 `textSize` que crecen como "operando corrupto" (falso positivo)
  → forzaba `SKIP_VALIDATE` (que apaga TODAS las redes). Ahora el build que crece pasa el
  validador completo sin saltárselo.

### 3. BUG ya resuelto (NO reintentar la causa): cuelgue al CREAR PARTIDA
- **Síntoma (v24/STRIP, v12):** al crear partida nueva se congela en el título/carga,
  no llega a crear la partida.
- **Causa:** se **quitaron los marcadores `%NF`** del diálogo (modo STRIP) → el evento
  de apertura (92010200) descuadra el consumo de lecturas y cuelga.
- **Cómo evitarlo:** **NUNCA quitar los marcadores.** Usar `FURIGANA_INPLACE`
  (conservarlos, ancho completo, por página). Los marcadores son OBLIGATORIOS.

## Herramientas de comunidad (qué cubren y qué no)

- **Tiniifan/CfgBinEditor**, **Tiniifan/Nyanko**, **StudioElevenLib/Pingouin**:
  manejan `.cfg.bin` (menús, objetos, técnicas, stats) — **útiles para los MENÚS**.
- **NINGUNA** maneja el script de evento `.pkb` (formato SSD) con furigana del 3DS →
  ese pipeline es custom (nuestro). No buscar ahí una solución al diálogo.

## Método para depurar un cuelgue nuevo (rápido)

1. Build **sin furigana** (sin flags) = estable → confirma si el cuelgue es del furigana.
2. `work/validate_furigana.py` → busca anomalías (marcador sin ancho completo, etc.).
3. Localizar el evento del NPC/zona (`work/dump_intro2.py`, buscar texto en `eve.pkb`).
4. Comparar el chunk original vs el transformado byte a byte.
5. Probar con **partida NUEVA** (nunca save states entre builds).

## ❌ Emparejar el diálogo NDS↔3DS por orden de líneas (2026-09-15, issue #36)
`tools/ds_official.py` alineaba por patrón de repeticiones (difflib). Sin frases repetidas eso es
emparejar por posición, y en 621 eventos la NDS tiene instrucciones de más que desplazan los IDs:
**931 frases de la build mostraban otra frase del mismo evento** (p. ej. «¡Tú!» → «Ya puedes
entrar.»). **Emparejar siempre por ID de cadena alineando el patrón de saltos**
(`tools/audit_dialogo_ids.py`, formato en `docs/EVENT_SCRIPT_FORMAT.md`).

## ❌ Nombres de objeto en latín de 1 byte para que quepan como en la NDS (v47, 2026-09-15)

- **Idea:** la NDS guarda los nombres de objeto en 1 byte por letra (32 B, fuente proporcional) y cabe
  «Pulsera popular». En el 3DS el campo es 18 B + NUL en ancho completo (9 letras). Se probó escribir
  4 nombres en ASCII de 1 byte en `item.dat` sin tocar fuentes.
- **Resultado en juego:** el menú acepta los bytes y la BCFNT los dibuja proporcionales, pero la NFTR
  solo tiene métricas del espacio y **la fila del menú se parte tras 10 caracteres** sea cual sea el
  ancho de las letras («Agua miner|al», «Bola de ar|roz», «Pulsera ju|venil»); el sobrante se monta
  en la fila siguiente.
- **Conclusión:** el límite es de caracteres, no de píxeles. Arreglar métricas NFTR/BCFNT no haría caber
  los nombres oficiales y obligaría a tocar las fuentes bloqueadas. **No reintentar.** Abreviar dentro
  de 9 caracteres (`work/ie1/capas/v47/objetos/propuesta.md`). Issue #39.

## ❌ Rótulo de lugar del minimapa de más de 10 caracteres (v76–v78, 2026-09-16)

- **Qué se probó:** centrar el rótulo (eve.pkb, 0x4037 argumento 3) anteponiendo espacios de ancho
  completo y, después, poner nombres largos de hasta 15 caracteres en la placa ensanchada de 239 px.
- **Resultado en Azahar:** la placa sale **vacía**.
- **Causa (ina_main1.cro):** el manejador de 0x4037 copia el texto a un búfer de 32 B
  (`STD_CopyLString(estado+0x44, arg3, 0x20)` en 0x5d3f4), pero quien lo dibuja (0x7a3bc) llama al
  camino de paso fijo (0x2ed24) con un búfer de celdas de 0x50×8/2 = 0x140 B, es decir **10 celdas,
  una por carácter**. La búsqueda de celdas libres (0x2f098) no respeta el final del búfer; si hacen
  falta más de 10, el inicio cae fuera y 0x2f0bc–0x2f0d4 sale sin dibujar nada. Aunque no se vacíe,
  el bucle corta en la celda 11.
- **Regla:** el rótulo, **espacios de centrado incluidos**, no puede pasar de **10 caracteres
  (20 B)**. La placa ancha de la capa v73 no amplía ese límite. Capa corregida: `work/ie1/capas/v79/rotulos`.

## ❌ Saltos de diálogo por píxeles más allá de 22 caracteres (piloto v77, visto en v81, 2026-09-16)

- **Qué se probó:** reajustar los saltos de diálogo midiendo la tinta real (FONT12, hasta 290 px por
  línea, hasta 37 caracteres).
- **Resultado en Azahar** (81000090 #406): el motor volvía a partir la línea tras «Mark, ¿has hecho
  algo» y cortaba la página a mitad de palabra («…grupo d» | «e gamberros?»).
- **Causa** (`ina_main1.cro` 0x424f4, llamada desde el manejador de 0x301d en 0x56eb0): la ventana
  reajusta el texto **por carácter** con `FontGetCharWidth`, que vale 12 fijo para FONT12 (code.bin
  0x164660) sin mirar el carácter. Límite `[ventana+0x1316] + 0x20` = 240 + 32 = 272 (por defecto en
  0x465c0; 0x301c no lo cambia porque arg4 = 0) y 3 líneas por página (`[+0x1318]`). Si
  `x + 12 >= 272` inserta un salto de línea (o de página en la 3.ª línea) antes del carácter, aunque
  esté a mitad de palabra; un `\n` que llega a la 3.ª línea pasa a salto de página.
- **Regla:** como máximo **22 caracteres por línea** (letras y espacios de ancho completo) y 3 líneas
  por página; el ancho en píxeles no amplía ese límite; `%s` se expande antes del ajuste, así que su
  línea necesita margen. Capa corregida: `work/ie1/capas/v82/saltos_dialogo` (su simulador
  `comun82.motor` predice exactamente la captura).

## ❌ Bigramas en la pestaña del nombre dibujados solo en FONT12 (sonda v85/v86, 2026-09-16)

- **Qué se probó:** redibujar kanji sin uso de FONT12 como pares de letras («ur», «el», «ia») y escribir
  «Aurelia» como A|ur|el|ia (registro en `work/ie1/capas/v85/bigramas_sonda/registro.json`).
- **Resultado en Azahar:** la pestaña del nombre muestra los **kanji originales** («A亠仭伉»).
- **Causa:** la pestaña (0x301a → 0xc2f28 → 0xe6214) y el rótulo de lugar (0x7a484/0x7a54c) dibujan
  con el gestor de **FONT8** (tipo 1, fijado en 0x24d8–0x24f8), a paso de 10 px en la pantalla superior.
- **Regla:** un bigrama debe dibujarse en **todas** las fuentes que puedan mostrar ese texto, o
  comprobar antes en emulador qué fuente usa cada sitio.

## ❌ Ampliar el ancho del diálogo con arg4 del 0x301c existente (sonda v86, 2026-09-16)

- **Qué se probó:** en 81000090, poner arg4 = 0x1A0 en el único 0x301c (#334, desplazamiento 0x1b24),
  que según el código escribe `[ventana+0x1316]`, y reescribir el #406 en líneas de 37 caracteres.
- **Resultado en Azahar:** el #406 sigue partiéndose a los 22 caracteres («…al grupo d»).
- **Causa:** cada 0x301a (0x5ca84) pasa `0xF0` y 3 líneas fijos a 0xc2f28 (0x5cb8c–0x5cb9c), así que
  reescribe el ancho antes de cada diálogo. Sus 4 argumentos no llegan al ancho. 0x3019 sí lo pasa
  (arg 7), pero tiene otro formato y tamaño.
- **Regla:** ampliar el ancho del diálogo **no es posible** con datos del mismo tamaño. Un texto a más de 22 caracteres con la ventana por defecto se corta a mitad de palabra.

## ✅ Bigramas en FONT12 + FONT8 (v87, 2026-09-16, validado por el usuario en Azahar)

- «Aurelia» como A|ur|el|ia se ve bien en la pestaña del nombre dibujando cada par en **FONT12 y
  FONT8** con los mismos códigos (`work/ie1/capas/v87/bigramas_fuentes/registro.json`). Para nombres de
  partido falta FONT12T.

## ⚠️ Literales del CRO: punteros que apuntan dentro de otro literal (v89/v90, 2026-09-17)

- La opción de afinidad «montaña» (山) de IE1 apunta a los últimos bytes del nombre de escuela 千羽山;
  al traducir la escuela («Far…») la opción mostraba «r». Antes de traducir un literal, comprobar con
  crorefs si hay referencias **dentro** de él, no solo a su inicio. Corregido en v90.
- Los menús estilo DS leen listas con strlen+1: todas las entradas hermanas deben traducirse con la
  misma longitud en bytes.
- Algunos literales que parecían lecturas de furigana sí se dibujan (ねっけつ, ゆうじょう, すてる…):
  confirmar la llamada de dibujo antes de descartarlos.
- Estos literales se dibujan con las BCFNT compartidas (`DrawTextHintOnVram`), según el análisis de
  v90; los bigramas se añaden ahí. Contrasta con la nota de la skill sobre FONT12.NFTR (números
  romanos en blanco): confirmar en emulador pantalla por pantalla.

## ❌ Nombres japoneses romanizados en el diálogo (visto en Azahar, corregido en v91, 2026-09-17)

- **Síntoma:** Axel dice «Mikage fue subcampeón regional, pero perdió contra el Imperial». 御影専農 es
  **Brain** y 帝国 es **Royal Academy** (`translation/shared/glossary/equipos.csv`).
- **Causa:** las tandas manuales/IA antiguas (v14) romanizaron nombres (Mikage, Senbayama, Igajima,
  Ikari, Biruda, Daisuke Endo, Fuyukai…) o los tradujeron («Imperial», «Granja Mikage»). Esas frases
  condensadas siguieron en la build porque la línea oficial NDS no cabe en 247 B. Además, `dialogo.csv`
  tiene filas `auto-ia` de lecturas kana con nombres inventados («lavado de cerebro de Mikage»).
- **Emparejado:** la frase 3DS es la **primera entrada de su ID**, y su argumento puede ser 1 o 2. Le
  corresponde la entrada de **tipo 1** del ID NDS emparejado (`tools/audit_dialogo_ids.py`). Si se busca
  el mismo número de argumento, no se encuentra el par.
- **Regla:** antes de dar por buena una tanda, pasar el detector de
  `work/ie1/capas/v91/nombres_oficiales/nombres.py` sobre todo el diálogo. Los nombres salen de los
  glosarios o de la NDS, nunca de la lectura japonesa. Si la línea NDS cabe, se usa; si no, se cambia
  solo el nombre, con su artículo («el Brain», «la Royal»). Ojo con los nombres que sí son oficiales:
  «Igajima» (la persona 伊賀島仙一), «Raijin» (tienda 雷神模型) y «Sallys» (equipo).
- **Límites técnicos al usar la NDS:** las comillas (`?h`) y el apóstrofo no tienen glifo; el guion no
  se codifica en shift_jis («9-0» → «9 a 0»). Los menús de depuración (90000000, opciones «Sí :»)
  tienen su propio maquetado: se cambia el nombre sin reajustar.

## ⚠️ Ancho de diálogo en el IE2: dos límites parcheables y un tope por página que no lo es (v14–v15, 2026-09-17)

- **Límite 1: reajuste de líneas.** `ina_main2.cro` fija el ancho en 0xF0 en 0x66a24 (0x301a) y en 0x4cabc
  (valor por defecto). Cambiarlo en su sitio a 0x1A0 funciona: el reajuste pasa a 37 caracteres.
- **Límite 2: dibujo de la página.** 0x4d6a0 carga `mov r2,#0x120` (288 px, 24 caracteres). Cambiarlo a
  0x1C0 funciona. El carácter que no cabe se dibuja al principio de la línea siguiente (de ahí el espacio
  inicial que se veía en la v14).
- **Tope 3: búfer de página de 132 B en la pila** (0x4d638, `sp+0x40`). No se puede ampliar en su sitio:
  el marco de pila no tiene hueco. Si una página pasa de 131 B, el texto se corta; si se corta a mitad de
  un carácter de 2 bytes, sale «?». Las páginas muy largas **sobrescriben registros guardados y la
  dirección de retorno**, con riesgo de cuelgue.
- **Regla:** cada página debe cumplir `2 × caracteres + (líneas − 1) ≤ 131`, con líneas de hasta 37
  caracteres. Esto también afecta al reparto de 22 × 3: en la v10 hay 122 páginas de 132–134 B.
- **Cómo cumplirla sin tocar el texto:** repartir el texto en más páginas, nunca recortarlo.

## ⚠️ IE2: tres cosas que parecían texto y no lo eran (v20–v23, 2026-09-19)

- **Los menús de opciones de los eventos** (Mapa/Caravana/Volver, Comprar/Vender/Salir…) son **sprites**:
  la instrucción 0x308e solo cambia el fotograma. Están en `a_data_replace/field_board/data/`.
- **Los argumentos del diálogo se usan en orden.** En japonés, el marcador de furigana consume antes su
  lectura. Si se quita la furigana, el `%s` se queda con la lectura («fichar a いま»).
  ❌ **NO reordenar los argumentos de la instrucción** (se probó en la v20–v23 y se instaló): el juego
  **se cuelga** al abrir las máquinas de Hillman (Ojear y Fichar) y el videoteléfono. La caja de diálogo
  se abre vacía, con la pestaña del nombre puesta, y no responde. Son 12 instrucciones con `%s` en
  7 eventos de cada edición (23000021, 23000031, 23000081, 23000162, 25120100, 25130472, 25130473).
  El orden de los argumentos **tiene que ser el del japonés**; se restaura con
  `work/ie2/shared/capas/orden_argumentos/restaurar.py` (2026-09-20). Si el `%s` sale con la lectura
  furigana, hay que arreglarlo por el lado del TEXTO, nunca moviendo argumentos.
- **El menú de campo dibuja las letras según su anchura real, no con un paso fijo de 15 px** (al revés que
  los rótulos). Tres rondas fallaron por usar el modelo de paso fijo. **Regla:** antes de dar por bueno un
  cambio de texto, comprobar que la simulación reproduce la captura del usuario con el fallo tal cual.
- El nombre de técnica del recuadro de partido es un gráfico (el cartel de la técnica), no `command.STR`:
  solo se ven 86 px.

## ✅ Búfer de página del diálogo ampliado a 256 B (IE3, probado en juego el 2026-09-22)

- El tope «132 B por página» (`2 × caracteres + (líneas − 1) ≤ 131`) **sí se puede ampliar en su sitio**:
  no hace falta hueco en el marco, se agranda el marco. En la función que dibuja la página
  (IE3 `ina_main3ogre.cro` 0x3a75c, IE2 `ina_main2.cro` 0x4d4d8, IE1 `ina_main1.cro` 0x46f00) se cambian
  13 inmediatos: `sub/add sp,sp,#F` → `F+0x100`, las 3 referencias al búfer → `sp+F` (zona nueva) y
  los accesos a registros guardados `[sp,#k≥F]` → `k+0x100`. Sin código nuevo ni huecos.
  Motor: `ie123kit.nucleo.ejecutable.bufer_pagina` (localiza la función y audita todos los accesos a sp).
- Resultado en el IE3: cajas de 3 líneas × 37 caracteres en ancho completo (2 B por letra), sin cambiar
  la codificación. Antes el reparto dejaba una sola línea por caja.
- En el IE3 el salto de página `\f` **funciona** (la conclusión contraria de la bitácora de IE3 era un
  efecto del fallo de offsets que comía bytes, ya resuelto con las referencias `@offset,longitud`).

## ❌ Pantalla de guardado del IE1 con los rótulos europeos (candidata IE3 v11/v12, probado el 2026-09-23)

- **Qué se probó:** en `ina_main1.cro` (función 0x719e4, caja de partida):
  - quitar el avance fijo por defecto de FONT8 (0xe62ac `beq 0xe6304`);
  - pasar el argumento 0x98 de las llamadas de dibujo a 0xb8, como el CRO europeo (0x71a1c);
  - rótulos completos en latín de 1 byte («Niv. Equipo», «Jugadores», «Elige un espacio de guardado.»).
- **Resultado en Azahar:** pantalla rota.
  - Las letras siguen a paso fijo (~10,5 px): el paso de esta caja **no sale del avance por defecto de FONT8**.
  - Con 0xb8 los rótulos se descolocan y bajan de fila: **0x98 no es un ancho**. El motor de texto del
    IE1 europeo es otro, así que sus argumentos no valen para el japonés.
  - «Elige un espacio de guardado.» parte en dos líneas y la segunda no se ve.
- **Regla:** con paso fijo, cada rótulo tiene el número de caracteres del japonés (5 antes del nivel, 3 antes
  de los jugadores, una línea de ~16 en la barra inferior). Los latín de 1 byte se dibujan con el mismo paso
  que el ancho completo. No copiar argumentos de llamadas del CRO europeo.

## ❌ Objetivos del IE2 en «casillas» (bigramas a paso fijo) (probado el 2026-09-23)

- En la caja de objetivos del IE2 las casillas de la v22 se montan («r», «m», «i») y se comen espacios
  («alcampo»). En el IE3, la misma caja muestra bien el latín de 1 byte con portadores (`es_encode`).
  Desde la v12 (candidata del IE3) los objetivos del IE2 van como en el IE3: texto oficial íntegro de ≤ 63 B
  (`work/ie2/shared/capas/rotulos_objetivos/objetivos_1byte`).

## ✅ Diálogo del IE2 dentro de la caja: el motor suma 1 px por carácter (aprobado el 2026-09-23)

- La caja del IE2 con espacios estrechos se salía por la derecha con topes de 296, 290 y 284 px medidos solo
  con la CWDH. El motor suma **1 px por carácter** (`BUG_FIX_MODE_X_ADD = 1` en `import/sItxInazuma123.itx`):
  con ese píxel, las tres capturas dan un borde real de ~320 px. Con 314/314/300 px (tercera línea con el
  icono) el usuario la dio por buena (candidata IE3 v13). Capa `work/ie2/shared/capas/dialogo/espacio_estrecho`.
- Al reejecutar un reparto sobre texto ya repartido, devolver antes el espacio 0x20 a 0x8140: si no, el
  repartidor no rehace nada (117 153 registros «no rehechos» en silencio).

## ⚠️ Rótulo de lugar: 10 baldosas de 8×8 en la VRAM emulada (IE1, IE2 e IE3)

- El rótulo (0x4037 argumento 3) se dibuja en un mapa de bits de 80×8 en VRAM+0x1500 (0x140 B = 10
  baldosas de 32 B): IE1 0x7a3bc, IE2 0x8a548, IE3 0x83bf8. Cada carácter ocupa una baldosa, ocupe 1 o 2
  bytes, así que el máximo son **10 caracteres**. En el IE3, VRAM+0x1e40 es otro rótulo de 32×8, y no se
  sabe qué hay entre los dos: no ampliar el búfer sin comprobar en el emulador qué hay en VRAM+0x1640.
- Los nombres europeos del IE3 que pasan de 10 caracteres (365 de 576 rótulos) se escribieron hasta 20 B:
  según la lección de la v76, esa placa sale vacía. Pendiente de verlo en juego.
