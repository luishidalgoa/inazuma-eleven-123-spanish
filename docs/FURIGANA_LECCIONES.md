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

## ⚠️ Menú de Fichar de IE1: paso fijo del ITX y rótulos recortados al hueco japonés (2026-10-31, capa `fichar_rotulos_ranuras`)

- **Paso ancho y uniforme en un menú**: no es la fuente ni la caja. `0x16a56c` de `ina_main1.cro` 1.4 carga
  `CMainAdventureScreenScoutSearch_TopMenuCharacterSpace` (ITX+0x5e8 = 11) en G+0xeef6c y `0xe63e0` lo toma como avance fijo.
  Con 0 el avance es el CWDH de la BCFNT (el de los diálogos). Mismo mecanismo en `OtherMenuCharacterSpace` (ITX+0x9d8),
  Headhunt (+0x974) y ReplaceUnit (+0xd74; el desensamblado de `0x13cd18` da `+0xd74`): son **5 sitios** (`0x16a56c`, `0x1658a0`, `0x17b0ec`,
  `0x17f358`, `0x13cd18`), cada uno `ldr rX,[ITX,#off]` → `mov rX,#0` (capa v3). El EU no escribe ese campo. **La línea -3 de la v2 (`0x16a958`) no
  hacía falta**: con G+0xeef6c = 0 `0xe63e0` ya entra en el modo 2 proporcional.
- **Blanqueado de literales del 20/10 «sin efecto»: causa desconocida.** No se sabe si la CRO en blanco llegó a instalarse (el PC conserva `C:\IE_work\aplicar_todo.py`, pero hoy hay
  la `6BBE2F87` con mtime del 19/10, como los respaldos; `copy2` conserva el mtime). Una hipótesis, sin probar, es un estado guardado de Azahar (restaura la RAM con la CRO ya cargada). Tras instalar un
  cambio de CRO/ITX conviene arrancar desde el título; no es una regla demostrada.
- **Panel del jugador de Fichar (ScoutResult `0x167520`, HeadhuntResult `0x17ce24`)**: las filas se construyen en la pila con `STD_CopyLString`/`STD_ConcatenateString` (escuela en 16 B, etiqueta en 32 B, cifra en
  dígitos de ancho completo con relleno y «Ｐ»); el EU usa `sprintf` con GetString 50 (Scout) / 560 (Headhunt, con `\n`), 51 y 352. Un literal más largo que el hueco no cabe en esas copias: se pone la cadena en una cueva y se pasa el puntero
  (`bl cueva` que devuelve `r0` o `r1`), y la fila 2 se hace con `sprintf` desde otra cueva. «.º» es el bigrama `E652` del mod. Detalle y simulación ARM: capa `fichar_rotulos_ranuras`.
- **Palabras cortadas («Fich», «Contac»)**: son literales del proyecto recortados al tamaño del literal japonés, con el
  siguiente pegado sin hueco; no hay recorte de dibujo. Se arregla reapuntando la relocación de SU ranura a un literal nuevo
  (hueco propio o la zona a cero tras el segmento 1), nunca escribiendo encima de un literal compartido («Fin» lo comparten 8).
- **Panel de ranuras de partida**: otra rutina de texto (`0x71b40`); el paso fijo de Fichar no es su causa y la CRO instalada no
  contiene «Niv. Equipo»/«Jugadores».
- **Pool de `CSubAdventureScreenCmdMenu` (`0x144210`, 1.4)**: las palabras a cero entre literales (`0x144820`, `0x14482c`, `0x144838`,
  `0x144848`, `0x1449e4`) son parches de importación de `g_ItxInazuma1` (tercer argumento del dibujo), no espacio libre; y la textura del
  rótulo de título (3×1 baldosas) es lo que dejaba sin sitio a «Título» (v42 lo achacó a un «búfer de 2 caracteres»). Los literales se
  cargan con `add rX,pc,#imm`: solo se reapuntan a otra zona con una cueva `bl` (capa `panel_equipo_rotulos`, sin probar en juego).

## ⚠️ «Estadísticas a 1» no es una regresión: sello de historia (evento 92051000, 2026-10-31)

- **Síntoma:** en el capítulo del partido contra el Otaku todas las estadísticas del equipo (Tiro…Defensa) salen a 1 menos nivel/EXP/PE/PT, y se pierden pachangas.
- **Causa:** mecánica original (JP/EU/NDS): el opcode `0x409b` de `eve.pkb` pone `unit+0xb1 = 1` a 14 jugadores (Mark e id 10 quedan a 0) y los 15 lectores de la CRO devuelven 1;
  lo levanta `92051200` tras el partido. No es del archive.fa, del hook de `usearch` ni de la CRO instalada (== JP 1.4 en esas rutinas).
- **Regla:** antes de diagnosticar «estadísticas a 1» como regresión, comprobar `unit+0xb1`/byte `+0x5d` del registro del guardado y el evento 92051000/92051200
  (`work/ie1/capas/menus_cro/estadisticas_sello_historia/validate.py`). Las 7 estadísticas no se guardan (se calculan al vuelo).

## ⚠️ Menú de Fichar de IE2: espaciado de los nombres, ventana del título y cuevas (2026-10-31, capa `fichar_unido_completo`)

- **Paso fijo ITX**: igual que IE1. `ITX+0x790` (menú) y `ITX+0x804` (lista por nombre) = 11, cada uno con UN lector en toda la CRO 1.4 (`0x1ddd78`, `0x1d92c0`); con `mov rX,#0` no se escribe `G+0xeef6c`.
- **Nombres «Ta lis man», «Zom bie», «Dy er»: dos causas, no una.** (a) Las casillas de bigrama de FONT12 llevan `left` +1/+2 y 1-3 px de avance de más (lista de Headhunt, que dibuja con la BCFNT). (b) `0x121bac` fuerza el
  avance fijo de TODA la cadena si contiene un código con byte inicial ≥ 0x88 (`bl 0x2118b0` en `0x121c78`; ITX123: FONT8 6/7 DS, FONT12 10/11 DS; solo si `G+0xeef6c = 0` y `G+0xeef70 = 1`; FONT12 únicamente en la
  pantalla 0). ❌ La v2 concluyó «no es paso fijo, ningún avance uniforme lo arregla» y lo dejó como decisión del usuario: valía para (a) y no para (b). ✅ Lo arregla expandir las piezas a letras de ancho
  completo sueltas justo antes de dibujar (cadena sin códigos ≥ 0x88 = no hay paso forzado; las letras llevan el avance de la BCFNT de los diálogos). ❌ No tocar FONT12/CWDH: global y bloqueado. Ojo: **en FONT8
  las letras sueltas salen más anchas que las piezas** (modelo: 30 % de huecos ≥ 3 px frente a 2 %).
- **«RoboO» (título de Headhunt)**: literal «Robo» (texto del proyecto) + la escuela, recortado por una ventana de 0x20 unidades (5 glifos a paso fijo). El oficial es «Fichar del %s» (NDS ES id 431): exige ventana ≥ 0x80
  y ampliar el búfer de pila de `0x1f3434` (marco 0x40 → 0x60, lista movida; 22 + 18 + NUL > 32 B). No se halló la llamada a `GetString(431)`: el uso en esta pantalla se infiere.
- **Un hueco a cero del fichero no es libre si tiene relocaciones**: `0x2114cc..0x2118a4` es una tabla de punteros que rellena el cargador (246 relocaciones). Antes de usar una cueva comprobar `Cro.relocations` (destino y valor).
  La cueva usable de la 1.4 de IE2 es `0x211a90..0x212000`. La CRO es una imagen única (el cargador solo reubica data/BSS): el código llega al hueco del segmento 1 con `add rX,pc,#imm`, sin relocaciones nuevas (deducción, sin probar en juego).
- **Cuevas de código: ejecutarlas, no solo desensamblarlas.** unicorn + keystone en el venv del scratchpad detectaron un desplazamiento mal calculado y la diferencia entre «piezas del registro» y «piezas de la tabla». keystone 0.9.2
  ensambló mal un `blne` a una etiqueta local (4 B de desvío): resolver los saltos a direcciones absolutas y comprobarlos con capstone.
- **«Atrás» no existe en la NDS ES** (á = `0xB2`; se buscó en `arm9` y 98 overlays); もどる = «Salir» (id 174). Tabla `0x29d8d8..0x29d930` = ids NDS 173-193: «Área» era Á + pieza + a, y «Delan», «Sabe», «Veloz», «Fuert», «Hábil», «A/B/F/M» son texto
  del proyecto recortado al hueco japonés. «---» (id 179, JP なし) no se puede codificar: el guion no existe en la tabla latina (shift_jis).
- **IE3 (CRO): una cadena «sin referencia» puede estar viva.** Arrays de cadenas de paso fijo (`base + idx·0x40` en `0x2afd10`, `+0x80` en `0x2af978`) solo tienen referencia el elemento 0; no usar sus colas como cueva ni darlas por muertas. Una zona de ceros del CRO tampoco está libre si contiene palabras con relocación (`0x29b9a0-0x29be49`) ni si es un bloque de datos a cero de uso desconocido (`0x29f09c`).
- **IE3 (CRO): el medidor `0x16f554` con r2 = 0 no es «12 px por letra».** Usa el ancho forzado `[mgr+0x34]` que dejó el último dibujo; el EU (`0x18c2e4`) lo ignora y mide siempre con ancho real. Por eso un modelo de paso fijo no explica las capturas: se replica el EU (nombre a X = 0, sin fila de lectura) en lugar de centrar.


## ⚠️ IE3: nombres fuera de casilla, medidor `0x16f554` y «arreglo global» (ronda 3, 2026-10-31)

- ❌ **Atribuir una captura a una pantalla por la hora o por el nombre de la animación.** La ronda 2 dio las capturas 20/21 por Contactos (`jm_status_t01`); el usuario las vio en Equipo/Jugadores, que es `CSubMenuScreenCharStatus` (`0x12731c`), y esa rutina YA llevaba el clamp en la CRO instalada: el defecto de la 21 es el comportamiento
  sin parche (13 px por letra → X ≈ −49), es decir, una CRO antigua en memoria (estado guardado). ✅ Antes de buscar otra rutina, comparar el X de la captura con el X que daría el código INSTALADO.
- ❌ **«Cambiar el medidor y ya están todos»**: `0x16f554` con r2 = 0 también lee `[mgr+0x34]` (el último ancho forzado), la ventana de diálogo `0x3a754` usa su resultado como ancho de fila (bloqueo v20) y el motor `0x17fb4c` (53 llamadores) no tiene clamp.
  La variante `menus_cro/medidor_ancho_real` (`cmp r8,#0 → #2` + dos anclajes `mov r2,#2`) reproduce el medidor EU y deja idénticos esos dos llamadores, pero sola deja 186/654/1265 nombres con X < 0 (sep 0/1/2): el ancho real de un nombre largo sigue superando la caja de 96 px.
  ✅ Lo que arregla el borde izquierdo es no centrar el nombre (X = 0, como las gemelas EU); el inventario de los 25 llamadores (`nombres_casilla_resto/README.md`) es lo que garantiza que no queda ninguno por cubrir.
- ✅ **Se puede ejecutar el medidor real**: unicorn con ganchos en los cuatro auxiliares (`0x173b8c`, `0x858`, `0x860`, `0x868`; EU `0x18149c`, `0xa70`, `0xa78`) y el `ldr sb,[pc]` apuntado a memoria propia compara el medidor JP, el parcheado y el EU sobre miles de textos (`medidor_ancho_real/validate.py`).
- ✅ **El compositor `0x1440bc` lee el nombre por pares de bytes**: un nombre ASCII con un portador de acento (2 B) queda desalineado y sus pares salen ≥ 0x889f («kanji»): por eso se mostraba el hiragana sobre «Jérome Hervaud». Los 2 `nop` dejan la fila en blanco (los personajes solo-JP con kanji pierden la furigana).
- ❌ **Ensanchar la textura de Contactos (12 → 20 baldosas) sin prueba**: el EU conserva 12 con X = 0; ahora es opción (`--con-ancho-jinmyaku`). 11/143/563 nombres se cortan por la derecha a 96 px con separación 0/1/2 (como el EU).
- La captura 25 («Cambiar jugadores») muestra letras con ~2 px de separación (el modelo de 20/21 es separación 0): el espaciado depende del bloque ITX de cada llamada; no es una posición. La fila pequeña del nombre no se localizó en estático.

## ⚠️ Inablog de IE1: búfer de 128 B, llave de comentario y texto condensado (2026-10-31, capas `blog_bufer_texto`, `comentarios_clave`, `texto_oficial_eu`)

- ❌ **Escribir el campo «entrada» de `blogpost.dat` como 516 B (68..584)**: los bytes 582/583 de cada registro de 584 B son el id del comentario en `blogres.dat` (`0x119bf0`: `ldrb [entrada+0x2de]`). Ponerlos a cero deja el cuadro «Comentarios» vacío aunque la insignia RES esté puesta. El campo de texto es 68..582 (514 B). Mirar siempre qué hay en la cola de un registro en el EU antes de declararla «campo».
- ❌ **Condensar el texto del blog para que quepa en 17 caracteres por línea (v32)**: la causa real eran un búfer de pila de 128 B en `0xbdc2c` (el contador de furigana de `sp+0x6a8` hace de NUL) y un paso fijo; con ≥ 222 B la función pisa `lr` (la 1.0 `0xbda58` lo hacía a 220 B: v16). Hay que ampliar el búfer (`blog_bufer_texto`, 14 palabras) y no recortar el texto (Norma 3).
- ✅ **Se puede ejecutar la función real con unicorn** (`menus_cro/blog_bufer_texto/emulacion.py`: CRO cargada, literales simulados, el motor 2 como gancho que captura el texto recibido): reproduce el corte de la captura y demuestra la equivalencia de la capa. Los literales con relocación se rellenan a mano (`0xbde2c`, `0xbde6c`).
- El preparser `0x375ec` de la 1.4 copia los caracteres de 1 byte; el `0x374cc` de la 1.0 los saltaba (solo ancho completo). El latín de 1 byte del EU llega entero al motor 2 en la 1.4 (comprobado ejecutando la función real); su dibujo proporcional en juego no está probado. Un `%s` se expande en sitio (`0x11a1b4`) antes de llegar al búfer: contar 31 B por nombre.
- Importaciones con nombre de `ina_main1.cro` (`Cro.imports()`): `0x7d8` `get_code_utf16`, `0x7e0` `NWFontGetCharWidth(FONT_TYPE, ushort)`, `0x7c8` `FontGetHeight`, `0x1720` `DrawTextPrimitive(DISPLAY, FONT_TYPE, …)`; tipos de fuente 0 = FONT12, 1 = FONT8, 2 = FONT12T, 3 = RUBI (por la tabla de anchos y las cuevas). `mgr+0x24` (tipo), `+0x28` (ancho forzado) y `+0x2c` (interlineado) son los campos del gestor de texto que lee el motor 2.

## ⚠️ Slot de guardado de IE1: avance, gestores y cifras (2026-11-09, capa `slot_gemela_eu`)

- ✅ **`[mgr+0x14]` del gestor de texto es el avance extra por letra y `[mgr+0x18]` el interlineado** (el motor 2 suma `+0x14` tras cada glifo; `0xe6db4` en la 1.4, `0xe9740` en el EU, los fija). El EU pone el gestor A a (1,1) en el slot; la 1.4 hereda el valor de la pantalla anterior (≈ +2 según las capturas). Cualquier cambio debe guardar y restaurar el valor para no filtrarlo a otras pantallas (diálogos bloqueados).
- ✅ **«Letras muy separadas» en los rótulos FONT8 no es paso fijo:** es avance proporcional `floor(cw·1,25+0,5)` con la FONT8 instalada (latín 7-8 frente a 5 de la EU, sin glifo ASCII 0x20). El EU no solapa por ~1 px; con la FONT8 instalada «Niv. Equipo» (82 px) pisa las cifras (límite ≈ 56). La FONT12 instalada y la del EU coinciden en ASCII.
- ❌ **Cambiar `0x98` por `0xb8` en la función del slot** (v12): el búfer de textura (`0x98·0x28/2 = 0xbe0`) lo reserva el llamador; solo cambia el ancho de la caja y descoloca todo. No hace falta: todo cabe en 0x98.
- ✅ Las cifras de nivel/jugadores/horas/minutos no son texto: `0x720e8` las pide con `0xba750(columna, …)`; EU usa la columna `0x1a` (en la 1.4 `0x18`) para los jugadores (+2 columnas ≈ +20 px).
- ✅ Una función propia se puede ejecutar entera en unicorn (gestores simulados, vtable → gancho, importaciones en Python) para comprobar textos, x/y, estado de los gestores y pila.

## IE1 Inablog y pantalla de pachanga (2026-11-09): el avance fijo viene de un ancho FORZADO en el código, no del ITX ni de la fuente

- ✅ **«Letras muy separadas» = ancho forzado `obj+0x28` > 0.** El motor 2 (`0x2ee0c`) y el 1 (`0xe63e0`) usan forzado + separación por letra (en px DS, ×1,25 en pantalla) y solo con forzado 0 y bytes iniciales < 0x88 caen a la rama proporcional (ancho BCFNT; cueva `0x1980c4`). Mide la captura: avance_px / 1,25 − separación = el valor forzado. Inablog: 11 y 12 (`0x1179f0`, `0x119d70`, leídos de la tabla ITX compilada en code.bin); pantalla previa de pachanga: 10 (`0x12cef4`, `mov r8,#0xa`). La separación de esa pantalla (`obj+0x14` = `[sp+0x14]` del llamador de `0xbdc2c`, `0xe6db4`) también cuenta: 1 en el objetivo y heredada por los nombres; cuando el texto proporcional tiene que caber en una superficie (14 baldosas = 112 px DS) hay que ponerla a 0 (`0x12cf60`), no solo el forzado.
  Parche: poner el valor a 0 (una palabra), no tocar fuentes ni codificación. Buscar siempre `str rX,[r0,#0x28]` junto a `0xbdc2c`/`vtable+8` en la clase de la pantalla.
- ❌ **Poner a 0 `ArticleCharSpace`/`TitleCharSpace` en el ITX (archive.fa o `.itx` suelto): sin efecto**; los dos valores salen de la tabla compilada en code.bin. El «alternativo» del README de `fichar_rotulos_ranuras` (poner a 0 los 4 parámetros en el `.itx`) tampoco funciona.
- ❌ **Atribuir la pantalla de «Condición para ganar» a `CMainAdventureScreenPracticeGame`**: es la lista táctil. La pantalla es `CSubPlayScreenActionMini` (`SPSActM.SPF_`, `battle_start_t.arc`, `games.STR` a `obj+0xc0`). Pista: buscar la cadena de recurso (`/data_iz/logic/games.STR`, `SPSActM`) y de ahí el cargador, no la clase por el nombre.
- ❌ **Suponer «FontGetCharWidth + 1 = 13» por la medida**: 13,75 px = (10 + 1) × 1,25. Hay que contrastar la medida con valores inmediatos del código cercano.
- ✅ **Separación entre letras de cuerpo y comentario del blog = `[sp+0x14]` del llamador de `0xbdc2c`** (`str r0,[sp,#0x14]` con r0 = 1; el título guarda 0). Con 1 px DS por letra las entradas EU no caben en 5 líneas; con 0 sí. Interlineado = `[sp+0x18]` + 8.
- ✅ **Una llamada `bl` a una cueva debe entrar por su primera instrucción**: `bl 0x1981c4` (en lugar de `0x1981c0`) se saltaba `ldr ip,[pc,#..]` y trabajaba con `ip` basura; comprobar siempre que los gemelos de un parche llaman al mismo punto de entrada.
- ✅ **`games.dat` y `games.STR`**: registros de 48 B, u16 en +0x2e = índice del texto ×32 B; el cargador (`0x12d460`) lee 240 B desde ese hueco. Se puede anexar texto nuevo al final del `.STR` (huecos de 32 B + relleno ≥ 240 B) y reapuntar el u16; no hace falta que el texto quepa en 32 B.

## IE3 ronda 4 · C (2026-11-09): cuevas y cargador de CRO

- ✅ **El destino de una relocación debe caer dentro del tamaño declarado de su segmento** (Azahar `SegmentTagToAddress`: `offset_en_segmento >= size` → `CROFormatError(0x15)`, el módulo no carga); el valor `segmento + addend` no se comprueba. Una cueva fuera del tamaño declarado sirve para código y datos leídos con `add rX,pc,#imm`, pero NO para una palabra de pool que el cargador deba rellenar (habría que ampliar el tamaño del segmento). Reapuntar el addend de una relocación existente es siempre seguro.
- ✅ **Las páginas ejecutables son `[AlignDown(seg0.offset), AlignUp(seg0.offset+seg0.size))`** (`GetExecutablePages`): el relleno hasta el final de página tras el código es ejecutable; el del rodata no. `VerifyHash` es un `TODO` en Azahar (no se comprueban hashes).
- ❌ **`bl STUB` en un sitio tras `pop {…,lr}`** (IE3 `0x68160`: cola `pop; add r1,pc,#imm; b destino`) destruye el retorno de la función: se usa `b STUB` y el stub acaba en `b destino`. Comprobar siempre si `lr` está vivo antes de sustituir una instrucción por `bl`.
- ❌ **«Zona a cero» ≠ libre**: `0x29f09c` está dentro de una racha con 440 destinos de relocación (tabla que rellena el cargador) y `0x2af993` es la cola de un elemento de paso fijo (`0x2af978 + 0x80·k`). Solo son demostrables las colas de página fuera de todo segmento (`0x29bf00-0x29bfff`, `0x2ced34-0x2cefff`).
- ✅ **unicorn ARM: escribir CPSR (modo) ANTES que SP/LR/registros** (SP y LR están banqueados por modo; si no, `lr` se lee como 0).

## ⚠️ Slot de guardado de IE1: gancho de avance por rango de puntero y tabla con la tinta real (2026-11-09, capa `slot_guardado_eu`)

- ✅ **Para cambiar el avance de unos textos concretos del motor 2 sin tocar los demás, engancha el `bl NWFontGetCharWidth` del bucle (`0x2f420`) y decide por el RANGO DEL PUNTERO DE TEXTO (`r4`)**, con los literales juntos en una cueva (un solo `cmp`). No hace falta una línea centinela (`r2` negativo): es más frágil (cualquier llamada con ese valor lo activaría) y obliga a tocar palabras del pool de otra rutina.
  Fuera del rango la cueva devuelve `r0` intacto (probado con 32 casos). Limitación: solo sirve para literales que viven en la CRO.
- ✅ **Tabla de avances = CWDH de la fuente EU ensanchado con la tinta de la fuente INSTALADA.** Con el CWDH EU a secas, las mayúsculas de la FONT8 instalada (N, E, M, ...) tienen la tinta una columna más ancha y se pisan con la letra siguiente; la regla `max(CWDH EU, columna final de tinta − 1)` deja el hueco mínimo en −0,25 px B (el del propio EU). Mide siempre con la tinta real (`ink_bbox` del glifo y `max(left, −1)`), no solo con el CWDH.
- ✅ **El ancho forzado del gestor (`[obj+0x28]`) también se lee en la ruta normal del motor 2 (`0x2f034`, tras el ITX `addW`)**, no solo con `G+0xeef6c ≠ 0`: un valor residual deja los rótulos a paso fijo. Una cueva que ponga `sb = 0` justo tras `NWFontGetCharWidth` lo neutraliza solo para los textos del gancho.
- ✅ **El texto FONT8 se dibuja con un factor 1,25 respecto del FONT12** (avance en pantalla ≈ 1,25·cw frente a cw + t): no mezclar las dos escalas al medir un rótulo FONT8 frente a una cifra; usa el modelo calibrado con la captura 27 (`ocupacion.py`).
- ✅ **Se puede ejecutar el motor 2 real (`0x2ee0c`) entero con unicorn**: cargar la CRO, rellenar las palabras de pool que parchea el cargador (importaciones `&g_ItxInazuma1 + off` → bloque a cero; `0x2f2ac` → puntero a G; `0x2f2bc` guardia ya a 1; `0x2f2c4` tabla `{1,5625; 1,25}`), simular las importaciones (`NWFontGetCharWidth` con el CWDH de las BCFNT, `get_code_utf16`, `DrawTextHintOnVram` que registra pen/sl/x/y) y `sprintf`/`strcat`. Da el avance real por glifo (`sl = round(cw/s1)`, `pen += sl + [gestor+0x14]`).
- ✅ **Una cueva que llama a una función externa debe mantener la pila alineada a 8**: `push {r2,lr}` (8 B), no `str lr,[sp,#-4]!`. Las cuevas que solo llaman a hojas triviales (`0xe6db4`) no lo necesitan.
- ❌ **Fijar el espaciado de un gestor compartido (`+0x14`) sin restaurarlo** (como hace el EU con `0xe9740(A,1,1)`): el valor se filtra a las pantallas siguientes (diálogos bloqueados). Guardar el anterior en un hueco libre del marco y restaurarlo en TODA salida (incluida la de «sin datos» y `r4 = 0`); probar con estados iniciales distintos y con una mutación que omita la restauración.
- ❌ **Mantener las columnas de cifras del EU con un rótulo que mide más** (nivel `0x11`): la decena queda a ~0 px. Las cifras son sprites por columna (`0xba750(columna)`, ~10 px por columna), no partes QNA; se mueven con un inmediato (`0x72364`, `0x723a8`).
- ✅ **Si un texto se arma como «literal» + numeral de una tabla de punteros relocados (3 B por entrada), no hace falta tocar la tabla: redirige la única carga del puntero (`ldr r1,[fp]` de la rama del 10) a un trozo de cueva `add r1,pc,#0 ; bx lr ; « 10\0»`.** Antes mira cómo lo hace el EU (aquí `sprintf("Ep. %d")`, id 172) para saber el texto oficial exacto: lo que parecía «residuo conocido» era un defecto corregible.
- ✅ **Un inmediato que depende de un dato (columna de la cifra del nivel) se vuelve condicional con un trozo `bl` de 4 palabras que lee el registro que ya trae el dato** (`cmp r1,#10 ; movlt r1,#0x11 ; movge r1,#0x12 ; bx lr`), comprobando estáticamente que nada escribe ese registro entre la carga del dato y el punto parcheado. Así el caso de la captura de referencia (nivel de 1 cifra) queda idéntico al original y solo el caso con tinta más ancha (2 cifras) se desplaza.
- ❌ **Premisas descartadas:** «las cifras van en piezas QNA de posición fija» (las partes `number01/02` del grupo 1 no coinciden con la captura 27) y «`font8_ancho_real` está en la CRO instalada» (su cueva `0x197fa0-0x19809f` está a cero). La captura 17 no sale de la CRO instalada (rótulos largos de v11).

## ⚠️ IE3: «sin referencia» no es «muerto» — literales de CRO con carga condicional (2026-11-09, capas `fichar_literales_eu` ronda 4 y `literales_cueva_eu`)

- ❌ **Declarar «muerto» un literal japonés del CRO porque ninguna `add rX,pc,#imm` / `ldr rX,[pc,#imm]` lo alcanza.** La ronda 3 lo hizo con `0x1ffb88`, `0x1ffbb0`, `0x2b6034`, `0x20c544`, `0x20c56c`, `0x1c9820` y `0x1c9848`, y era falso: el extractor solo veía las formas INCONDICIONALES. El compilador carga estos literales con `addeq/addne rX,pc,#imm` y `ldrne rX,[pc,#imm]` (palabra de pool con relocación). Buscar siempre `add<cc>`, `sub<cc>`, `ldr<cc>` (mnemónicos de capstone con sufijo de condición) y relocaciones, además de los arrays de paso fijo.
- ❌ **Descartar un literal por caer dentro de un rango Wi-Fi demasiado amplio** (`~95 cadenas en 0x217b8-0x2b96f8`): escondió literales vivos y visibles (Cápsulas/teléfono `0xd0048`, `0xd0068`, contraseñas `0x19a7d8`, reglas `0xb7b44`, `0x1dad40`…). Documentar las cadenas raras por offsets y función, no por un rango.
- ✅ **Identidad JP↔EU cuando el orden de las llamadas no decide:** ejecutar la función JP y su gemela EU con unicorn con el MISMO estado (campos del objeto, retorno de las `bl` y bytes de BSS) y comparar el literal que carga el JP con el id que pide `GetString` en el EU (`fichar_literales_eu/ejecucion.py`). El JP carga 432, 434, 433 (por rama) y la gemela EU llama 434, 432, 433; el orden estático engaña, la ejecución diferencial no. En el EU el id sale de `moveq r0,#id` / `ldrne r0,[pc]` justo antes de UN solo `bl`: `evidencia.py` debe entender `mov<cc>`/`ldr<cc>`.
- ✅ **Un `add r1,pc,#imm` que no alcanza su cueva se puede reencaminar sin relocaciones nuevas:** `bl STUB` con `STUB = add r1,pc,#imm ; bx lr` en el relleno de la página de texto (`0x29bf00`). Solo es seguro si `lr` está muerto en el sitio (el siguiente `bl` lo sobrescribe y no hay lecturas de `lr` ni ramas en medio): se comprueba por código.
- ✅ **El cargador de Azahar (HLE) NO comprueba el valor de una relocación, solo que su DESTINO esté dentro de su segmento (`CROFormatError(0x15)` si no):** reapuntar el addend de una relocación existente a un rótulo muerto es seguro; añadir un registro nuevo o ampliar un segmento no se hace sin la prueba del usuario. Aún sin probar en juego (hardware real y otras versiones de Azahar sin comprobar).
- ❌ **Traducir con el texto de una frase japonesa «idéntica» sin gemela EU de la función** (`0x1c9820`/`0x1c9848` en la función de torneos por StreetPass): no es identidad de función; se deja como pregunta al usuario.
- ❌ **Dejar «sin tratar por su baja visibilidad» cadenas que ya cumplen el criterio de la capa** (corrección 2 de la ronda 4: `0x653d8`, `0x653f8`, `0x9f300`, `0x2b4ec4`, `0x2b88cc`, `0x2b4a10`, `0x2b906c`, `0x2b9028`, `0x86dd0`, `0x87864`; la nota «unas 34 tendrían id EU demostrado» nunca se revisó una a una). Con una autorización de traducir «lo que queda», el motivo de un pendiente tiene que ser concreto por literal. ✅ Repetir el criterio exacto de la capa sobre TODAS las cadenas con referencia (`fichar_literales_eu/barrido_referencias.py`) y guardar una fila con motivo por cadena; las cifras de un documento («355 = 56+180+71+48», «34») salen de ese barrido, no de una suma antigua.
- ✅ **Un `%d` del EU puede ser un `%s` en el JP sin que sea un error:** si el JP convierte el entero a cadena (`0x175bb8`) y pasa el puntero en `r3` (códigos de error `0x86dd0`/`0x87864`, PE/PT `0x155af8`), el literal ES debe llevar `%s` aunque el texto oficial EU lleve `%d` (se declara en `ADAPTADOS`).

## Paquetes IE2/IE3 sobre IE1 v2 (2026-11-09)

- ✅ **Un hash de `archive.fa` exigido «por si acaso» hay que justificarlo con las entradas que el paquete usa realmente.** El paquete de IE2 solo comprobaba el `archive.fa` (no lo escribe) porque su tabla de piezas sale de `unitbase`, `schinfo`, FONT12 y FONT8. Al instalarse el IE1 v2 (`BD1B450F…`) el instalador habría rechazado un archive.fa válido. En vez de pasar a `-IgnorarArchive`, se demostró (tabla de FileEntry, región de datos y lectura byte a byte) que esas 4 entradas son idénticas en v1 y v2, y se amplió la lista de hashes aceptados (v2, v2+IE3, v1), cada uno con su tamaño; cualquier otro se sigue negando sin escribir.
- ✅ **Si la comprobación del archive.fa de un paquete que no lo escribe se queda desfasada, el síntoma es una negativa del instalador, no una corrupción:** es el fallo seguro, pero hay que regenerar los hashes del informe/README/test a la vez; el test de los `.ps1` compara el conjunto de sha256 de los scripts con el de `informe.json` para que no queden hashes antiguos (p. ej. `E4C1697A…`, IE3 sobre v1).
- ✅ **El parser de PowerShell por stdin falla con el BOM si se pasa tal cual:** `[Text.Encoding]::UTF8.GetString` conserva U+FEFF y rompe `<#` (falsos «errores» en un script que sí es válido). Quitar el BOM (`.TrimStart([char]0xFEFF)`) y hacer una prueba de control con un script roto (debe dar errores).
- ✅ **Un paquete que SÍ escribe el `archive.fa` queda ligado a la base exacta sobre la que se construyó, aunque su única entrada no haya cambiado (IE3, 2026-11-09).** El paquete de IE3 solo reemplaza `connection_b.arc`, pero su `archive.fa` final contiene toda la base: al instalar IE1 v2 (`BD1B450F…`) la salida vieja (`E4C1697A…`, hecha sobre el v1) habría **deshecho** las 4 entradas nuevas del v2 y su instalador, con razón, se niega. Se regenera sobre la nueva base (`6878CC93…`) y se comprueba, con las 26 entradas de IE1 v2, offset/tamaño **y sha256 del contenido** en base y salida (no solo la tabla). La capa gráfica comprueba la ENTRADA (sha256+FileEntry), así que solo hizo falta añadir la base nueva a su lista; la CRO no cambió. Un paquete construido sobre el v2 NO sirve sobre el v1: el instalador lo rechaza sin escribir (el hash v1 figura solo para dar un mensaje claro, nunca como base ni salida).
- ✅ **`tests/requiere_rom/test_paquete_final_ie1.py` y `..._ie1_v2.py` no se pueden ejecutar en la misma sesión de pytest** (colisión de `sys.modules['verificar_cro']`: el segundo falla en `test_cro_final_se_reproduce…`); por separado pasan. Preexistente y ajeno a IE2/IE3; ejecutarlos en procesos distintos.
- ✅ **Al regenerar un paquete hay que buscar sus hashes viejos y sus afirmaciones de compatibilidad en TODOS los documentos (también los de otros paquetes) y corregir la línea entera, no solo la primera frase con un corchete.** La primera pasada dejó frases ya falsas («los paquetes son excluyentes», `E4C1697A…` como `archive.fa` vigente de IE3, «recorte a 1 625 457 264 B», «exactamente los 4 sha256», «el parser NO se ha vuelto a pasar») que dos revisores encontraron. Y cuidado con la herramienta: en esta sesión `grep` respeta `.gitignore` y salta `work/` entero si se busca desde la raíz del proyecto, así que un «no hay más menciones» puede ser falso; usar `command grep -rI` o rutas explícitas dentro de `work/`.
- ✅ **Un README que dice «los `.ps1` son los de X con otros hashes» o «llevan exactamente N sha256» envejece en cuanto el script gana lógica propia** (`instalar_ie3.ps1`: rama que rechaza el v1 con un quinto sha256 y bloque `$otras` de avisos, ambos nunca ejecutados). Declarar qué hace el script de más, que no se ha ejecutado y que se niega o avisa ANTES de escribir, y recomendar `-SoloComprobar` primero.
- ✅ **La documentación de un paquete protegido que describe la compatibilidad con otros se queda obsoleta cuando los otros se regeneran** (README de IE1 v2: «excluyentes en la práctica»). No se edita a escondidas: se declara el desfase en los paquetes vigentes y en el BACKLOG, se deja un parche aplicable en el scratchpad y se pregunta al usuario. Con IE3 instalado, el `instalar_ie1.ps1` y el `deshacer_ie1.ps1` del v2 se niegan sin escribir (el `archive.fa` ya es el de IE3): para deshacer el v2 hay que deshacer IE3 antes.

## Fuente latina occidental: comparar celdas de BCFNT (2026-11-09)

- ✅ **No concluir «las letras de la fuente EU no son las de la JP» comparando celdas de hoja sin alinear, y comparar siempre con el fichero ORIGINAL, no con la copia instalada.** La BCFNT EU (celda 14x17, base 14, hoja 32x128, paso 15x18) y la instalada (15x16, base 13, hoja 256x256, paso 16x17) no son intercambiables celda a celda: `font_patch.Font` lee la hoja EU con paso 16 (el real es 15). Con ese método salía «0 de 52 iguales»; recortando cada glifo a su tinta y con el origen `x = col*(cell_w+1)+1`, la **instalada** es la EU en 52/52 letras (y 199/201 códigos del núcleo latino con la CWDH incluida) **porque la capa `fuentes/glifos_eu` (v75, 2026-09-16) ya trasplantó el dibujo EU**; la FONT12 japonesa original (`work/shared/fa_extract/font/FONT12.bcfnt`) **no** es igual a la EU ni a la instalada (0 de 52 en a-zA-Z; 1 y 3 de 201 códigos). La primera versión de esta lección y de la capa decían «JP original = EU = instalada» por no haber comparado contra el original: era falso. Consecuencia: **pasar IE1 «a la fuente EU» no cambia el diálogo** (ya la lleva); lo que se ve redondeado es el A4 suavizado de las versiones 3DS (JP, EU e instalada) frente al 1 bit de la NDS. Antes de proponer una sustitución de fuente, medir igualdad de tinta alineada contra el original sin parchear y contra la instalada, y buscar qué capa tocó ya esos glifos.
- ✅ **La fuente del juego es única para los tres juegos** (`font/*.bcfnt` en la raíz del `archive.fa`): comprobado en el ejecutable JAPONÉS (update 1.4, `work/shared/update_1_4_azahar_respaldo/000bb800/content/00000000.app`, `.code` sha256 `56b083bb…`): `LoadFont(FONT_TYPE)` en `0x165b10` copia a la pila la tabla de 4 punteros de `0x259fcc` (0 FONT12, 1 FONT8, 2 FONT12T, 3 RUBI8) y carga `tabla[índice]` sin comprobar rango ni juego; `ina_main1/2/3ogre.cro` la importan y la llaman con `r1` = 0..3. No existe «fuente de IE2» distinta de la de IE1. Las NFTR de `inazumaN/data_iz/font/` solo dan posiciones (modo DS). Una candidata de fuente se prueba siempre en los tres juegos. ❌ **No dar por imposible algo «porque no está el fichero» sin buscarlo:** la primera versión de la capa decía «no hay `.code` JP» y estaba en `work/shared/update_1_4_azahar_respaldo/`. Separar la fuente por juego exigiría código nuevo en `LoadFont` o en los CRO (ver las lecciones de `code.bin` y de relocaciones de este documento): no se ha intentado.
- ✅ **El avance de las NFTR de la NDS no incluye el espacio entre letras** (`H`: tinta 6, avance 6): el motor suma +1 px por carácter (mismo modelo que el EU). Un renderizado sin ese +1 sale pegado; con él se parece a lo que describe el usuario de la captura (la captura no está en disco: no se ha comparado píxel a píxel). El espacio U+3000 instalado (avance 7) es mucho más ancho que el de la NDS (3): con letras NDS conviene el avance de espacio nativo (`*_espacio`), que no se aplicó por defecto porque lo fijan las capas `espacio_estrecho`.
- ❌ **Fiarse de los códigos de una NFTR por analogía con otra NFTR de la misma ROM:** `FONT8.NFTR` de la NDS ES tiene intercambiados los dibujos grave/agudo de È/É (`0xD8`/`0xD9`), Ò/Ó (`0xAA`/`0xAB`) y Ù/Ú (`0xA1`/`0xA2`); `FONT12.NFTR` no. La primera candidata aplicó el mapa de FONT12 a FONT8 y sacó «Èxito Òscar Ùrsula»; lo vieron los revisores en las previews, no `validate.py`. ✅ Comprobar la FORMA del acento de cada portador en CADA fuente (`fuente_lib.forma_acento`, con controles negativos sobre las graves) y renderizar una fila con los 15 acentos por fuente y variante.
- ✅ **FONT8 NDS (4x5 la H) es la mitad de alta que la FONT8 instalada (8x10) y que la EU (5x8)**: un cambio de dibujo no es un cambio de tipografía «equivalente»; medir el tamaño de la mayúscula y la última fila de cada fuente antes de ofrecerla (`validate.py`, comprobación «medidas»).

## IE1 Inablog v3 (2026-11-09): el modelo de ancho no es uniforme

- ❌ **Fiarse de `round(CWDH/1,25)` con tope 190 de 192 en el cuerpo del Inablog**: en juego se salen lineas medidas 180, 188 y 189 mientras otra de 183 cabe; ninguna constante ni factor sobre el ancho total las separa. Para el tope no basta restar unos pixeles al modelo: hay que usar una cota que dependa de la composicion de la linea (`ceil` por letra).
- ✅ `NWFontGetCharWidth` (1.4, `0x223bd4`) devuelve el byte «char width» del CWDH sin mas (vtable `+0x3c` de la fuente NW); el nombre exportado se busca en el `static.crs` de la 1.4 (dentro del `00000000.app` de la actualizacion, ultimo `CRO0`), con VA = `0x100000 + (tag >> 4)`. El `.code` se descomprime con `ie123kit.nucleo.compresion.blz` (ExeFS del NCCH).
- ✅ Antes de reducir un tope comprueba cuantas entradas dejan de caber (`datos.opciones_tope` del informe de la capa): con el texto oficial el minimo posible del Inablog es 176 (ceil).
- ✅ (2026-11-09, IE1 pachanga) **`0xbdc2c` (texto -> textura) deja `mgr+0x14 = mgr+0x18 = 1` al acabar** (`bl 0xe63cc` en `0xbdcfc`): lo que se pase en `[sp+0x14]` (separacion por letra) solo vale durante ese dibujo. Lo que se dibuje despues con vtable+8 directo (los nombres de equipo de `0x12ccec`) NO hereda esa separacion. ❌ No razones «el siguiente texto hereda el valor del anterior» sin ejecutar la funcion real (la v2 de la pachanga lo asumio y dejo los nombres a +1 y 15 de 158 fuera de la placa). Comprobado con unicorn (`pachanga_objetivos_equipos_v3/validate.py`).

## Slot de guardado de IE2: FONT12 a paso fijo en el motor 2 (analisis estatico + unicorn, 2026-11-09; sin capa, sin probar en juego)

- SI: **la causa de «E p .», «N i v e l», «J u g» y de «Arietes Maniacos» fuera de la caja en IE2 no es la NFTR ni la BCFNT: es el avance por defecto del ITX123 en FONT12.** En el motor 2 de `ina_main2.cro` (`0x334b8`, vtable+8 del gestor FONT12 `[0x29b20c]`) la rama del tipo 0 (`0x3364c`: `beq 0x33688`, palabra `0a00000d`) carga `sb = ITX123[+8/+0xc/+0x38]` = 10/11/11 DS y el bucle de letras hace `movgt sl,sb`: todo texto FONT12 sin ancho forzado ni modo sin escala va a 10-11 DS por letra, tambien el ASCII y las letras de ancho completo. Ejecutado con unicorn sobre el motor real (CRO CE0449BF): «Arietes Maniacos» = 16 x 11 (176 DS; 160 si `G+0xeef48` = 0, que cambia 11 por 10), «Ep. 2» = 55, «Nivel» = 55, «Jug» = 33.
- SI: **IE1 e IE3 llevan una palabra que IE2 no lleva**: `0x2efa0` (IE1) y `0x19fd8` (IE3 paquete final) valen `0a00001f` (`beq` que salta los anchos por defecto; la JP 1.4 trae `0a00000d`); en IE2 `0x3364c` sigue en `0a00000d`. Por eso el slot de IE1 salia con FONT12 proporcional (la capa `slot_guardado_eu` solo tuvo que arreglar FONT8) y el de IE2 no. La cueva `bigramas` de `objetivos_proporcional` (FONT12 a ITX solo para piezas >= 0x88) presupone esa palabra.
- SI: la capa `nftr_proporcional` esta aplicada en el archive instalado (FONT12 de IE2: 72 de 74 letras anchas = regla `round((cw+1)/1,5625)`; FONT8 lleva ademas `font8_proporcional`), pero **esas pantallas no leen la NFTR para el avance**: el motor 2 usa `NWFontGetCharWidth` (CWDH de la BCFNT) o el ITX123 del exe, y la NFTR solo sirve para el largo del caracter. Sus supuestos de escala (1,5625 / 1,25) no entran aqui; en el motor 2 el indice de escala es 0 (1,5625) con `G+0xeef7c` = 1 («modo _2») y 1 (1,25) si no.
- SI: el rotulo «Jugadores» pequeno y comprimido de la pantalla del titulo es textura (`menu_slot.arc`, `ie02_slot_b_font01`, celda de 48 px, capa `cro_ranura` v13): no lo toca ningun cambio de CRO. «Arietes Maniacos» es la cadena 33 de `rpgtitle.STR` (ASCII + portador griego `83 a1`), «ライモン» es dato de la partida (literal `0x216304`, ya traducido en la CRO instalada; una partida nueva sale «Raimon»).
- NO: **no hay arreglo solo de datos** para IE2 (ITX123 vive en el exe; NFTR y BCFNT no entran en el avance). NO: resetear el modo _2 en las dos primeras lineas de la caja (ya fallo: «Ep.» desaparecia).
- Marca de linea para un arreglo acotado: el motor lee la linea de depuracion en `[sp+0xa4]`; `-1/-2` (campos de nombre, rotulos de baldosas) y `-3` (cuatro llamadas FONT8 de goles/recompensas y los dos reinicios de la caja) ya estan en uso; `-4` (`0xfffffffc`) esta libre. Hueco demostrable para una cueva: `0x2119f0-0x211a1f` (48 B a cero en la JP y en CE0449BF, sin relocaciones ni importaciones, sin ramas hacia el, dentro del segmento de codigo que acaba en `0x211a24`).

### IE2 · slot/partida: FONT12 a paso fijo por una palabra que IE1/IE3 si llevan (2026-11-09; construido en estatico, NO probado en juego)
- SI: antes de culpar a la fuente (NFTR/BCFNT) o a una textura, ejecutar el motor de texto REAL en unicorn y comparar con el hermano que ya funciona: la diferencia de IE2 era UNA palabra de CRO (`0x3364c`, `0a00000d` frente a `0a00001f` de IE1 `0x2efa0` / IE3 `0x19fd8`) que decide si FONT12 usa el ancho por defecto del ITX123 (10/11 DS por letra). Un arreglo acotado por la marca de linea de depuracion (-4, argumento que el motor solo lee para -1/-2) deja el resto de las llamadas identicas (rejilla de 2 816 casos). Capa: `work/ie2/shared/capas/menus_cro/slot_guardado_ie2`.
- SI: comparar la salida acotada con la «palabra global» en el mismo emulador (iguales en todos los casos con -4) prueba que el arreglo es el camino de IE1/IE3 sin tocar las demas llamadas.
- NO: suponer que el hueco «dentro del segmento de codigo» acaba en `0x211a24`: el segmento 0 de la CRO de IE2 acaba en `0x2118a4` y las cuevas (`0x2118b0-0x212000`) estan en el relleno de la pagina; vale porque la base ya ejecuta ahi (objetivos_proporcional), no por el tamano del segmento. NO: tratar el modo «_2» como fiable (resta 2 DS por letra; espacio y punto avanzan 0): lo que lo use queda como incierto hasta verlo en juego.

### IE2 Inablog: mismo paso fijo que el guardado, y la linea que llega al motor es una constante del utilitario (2026-11-09; analisis estatico + unicorn, sin capa, sin probar en juego)
- SI: el Inablog de IE2 (cuerpo `0x15ed84`, titulo `0x15eb6c`, comentario `0x15e868`) pasa por `0x120a24` y el motor 2 con paso fijo de 11 DS por letra (`0x3364c`), igual que el guardado; ancho forzado y separacion del Inablog valen 0 en IE2 (ITX2 `0x3090/0x30a0/0x30b0`). Textos y reparto ya son los oficiales NDS: no hay arreglo de datos.
- SI: la marca -4 del guardado no llega por si sola a los utilitarios `0x120a24` y `0x12269c`: la linea que pasan al motor es una constante propia (`0xb17`, `0xb5c`), no la del llamador. Hace falta hacer que `0x120a24` reenvie r1 solo cuando valga -4 (cueva de 5 palabras, comprobado con la `0x120a24` real en unicorn).
- NO: dejar la separacion por letra en 0 con la marca -4 en modo «_2»: `i`, `l`, `.`, `!` avanzan 0 (410 de 3 111 glifos del Inablog).

## ❌ Rótulos de lugar en rebanadas de FONT8 con espacio de 2 px, «º» como «°», guion de 9 px y letras pegadas (lugares_oficiales, 2026-11-09)

- **Qué se probó (primera versión de `lugares_oficiales`)**: tira continua con las letras nativas de FONT8 y 4/3/2 px entre palabras («2» para que el nombre quepa en 100 px), «º» -> `°` nativo, «-» -> el guion de ancho completo (9 px), y centrado fijo sin holgura.
- **Resultado (previews vistas por revisores independientes, no por el usuario)**: «RestauranteRaiRai», «Cámara Piedra Alius» y «Calle Nevada oeste» sin espacio visible; «1.º» con un punto cuadrado; «–» largo donde el oficial lleva «-»; y para colocar 4 nombres de 101-106 px se dejó el nombre antiguo.
- **Causa**: FONT8 no tiene glifo de espacio de imprenta (solo `8140`, la baldosa vacía de delante), así que el espacio es un hueco de columnas dentro de la tira y 2 px no se leen como espacio (el hueco entre letras ya es 1 px); FONT8 tampoco tiene «º»/«ª» (solo el «°» de 4x4 px) ni guion corto; **y el rótulo es una rebanada dibujada por la propia capa, así que sí puede llevar glifos propios** (`lugares.PROPIOS`: 5x5 px subrayados y guion de 5 px) sin tocar letras nativas. Los huecos de palabra legibles (5/4 px, mínimo 3) hacen más anchos los nombres y multiplican la demanda de códigos de rebanada (415 baldosas distintas frente a 278 libres) hasta que se permite una **holgura de posición de 4 px y elegir 5 o 4 px de hueco** para compartir baldosas entre nombres (193).
- **No reintentar**: (1) hueco de palabra < 3 px; (2) estrechar el hueco entre letras a 0 para que quepa un nombre: las letras se funden («planta» -> «pianta»; ver `lugares_oficiales/previews/pendientes_no_caben.png`); (3) medir contra un recuadro fijo de 100 px: la caja real de IE1 es una placa de 165 px con búfer de 10 celdas (`ina_main1.cro` 0x1500) y la de IE2 una placa de 239 px con búfer ampliado de 15 baldosas; (4) dar por cierto que el búfer de 15 baldosas existe en IE1 (solo está en IE2/IE3).
- **Segunda causa (ronda de corrección, documentación)**: el generador llevaba la cifra de la excepción de tipografía como CONSTANTE de texto («264 glifos») y, al bajar la demanda a 193, el `informe.json` siguió diciendo 264 aunque el README y el FONT8 decían 193; `validate.py` solo buscaba la frase de la aprobación y no lo detectó. Las cifras de un informe deben calcularse del dato (`len(asignacion)`), y la validación debe exigir que coincidan (`excepcion_tipografia_cifra_exacta`); la cifra aprobada por el usuario se cita como tal («aprobó 264; se reescriben 193, menos de lo aprobado»). Lo mismo con «n comprobaciones»: las `validacion.json` de las tres capas deben pasarse con las mismas opciones (`--reproducir`), si no una dice 26 y las otras 25.
- **Tercera causa (eventos que no pueden crecer)**: para que el nombre oficial quepa en un evento con `%nF` o id ≥ 90 000 000 se quitan baldosas VACÍAS de delante, y el rótulo queda descentrado (11 en IE1). No es un desborde, pero hay que declararlo y medirlo (`rotulos_descentrados_por_recorte`); y un rótulo recortado hasta quedar byte a byte como estaba («Azotea», 91990000#32) cuenta como «sin cambio de dibujo» (el cuadre de registros debe sumar el total: 170 en IE1).

## IE2 · menus de campo y opcion A: lo que NO es (analisis 3, 2026-11-09; estatico + unicorn, sin probar en juego)
- SI: el menu de campo de IE2 (Datos: Blog, Album, Movil, Uniformes, Records) lo dibuja el MOTOR 1 (`0x121bac`, `bl` directo desde el widget de lista `0xbd280` en `0xbd390`), no el motor 2 `0x334b8`. El motor 1 pone paso fijo ITX (10 DS) solo si la cadena trae un byte >= 0x88 (los bigramas son kanji) y proporcional si no; por eso «Móv il» y «Un iformes» son la tinta de cada bigrama centrada en su celda, no un problema de NFTR ni de la palabra `0x3364c`.
- NO: contar las 98 relocaciones al puntero `0x29b20c` como «98 llamadas FONT12 al motor 2». Hay 84 sitios de dibujo (45 virtuales directos + 39 llamadores de `0x120a24`); el resto de relocaciones son medir/limpiar/reservar.
- NO: suponer que la marca -4 llega a las filas de la lista del Inablog (`0x12269c`): llama al motor 1, no a `vtable+8`; ademas sus letras 82xx ya salen proporcionales en el motor 1.
- NO reintentar: aplicar la opcion A (`0x3364c = 0a00001f`) a todo el motor 2 sin medir antes los bigramas (metrizados para paso fijo: con +0x14 = 0 el 22 % de los pares de tinta se solapan) ni los 39-40 sitios en modo «_2» (`i`, `l`, `.` avanzan 0).

## IE2 · Inablog y pantalla previa a la pachanga: lo que NO es (capas inablog_ie2_proporcional / pachanga_ie2_proporcional, 2026-11-09; estatico + unicorn, sin probar en juego)
- SI: en el Inablog la separacion por letra del cuerpo y del comentario NO la fija el motor sino el llamador: `[sp,#0x14]` (= `ITX2[0xa18]`/`[0xa28]`, valen 0) llega por `0x122580` a `mgr+0x14` y `0x121b98` lo reinicia a 1 al terminar. Con la marca -4 en modo «_2» (`G+0xeef7c = 1`, 410 de 3 139 glifos con `sl = 0`: `i`, `l`, `.`, `!`, `¡`, coma) hay que dar separacion 1 en el llamador o salen pegadas.
- SI: ejecutar las funciones REALES de pantalla (aqui `0x15ed84`/`0x15e868`/`0x15eb6c` y `0x17b6d4` con entradas reales y los stubs minimos del juego) cubre mas que ejecutar solo el utilitario o el motor: sale la cadena completa linea -> utilitario -> motor y la separacion de `mgr+0x14`.
- NO: asumir que el flag «sin escala» (`G+0xeef78`, pachanga) solo cambia el avance. En `0x33d0c` el motor tambien pasa `x`/`y` al dibujo sin convertir de DS a 3DS; en la ejecucion de CPU la `y` del objetivo pasa de 0 a 8 y la de los nombres de 7 a 6. Hay que mirar la altura del texto en la primera prueba antes de generalizar el modo.
- NO: dar por buena una placa de 112 texels = 140 px. Con 108 utiles (el texto empieza en x = 4) pasan 13 de 34 rivales con `sl = CWDH`; con 140 px, 1 de 34. La unidad solo la resuelve el juego.
- NO reintentar: meter la marca -4 en la pachanga de IE2 sin una cueva de separacion (modo «_2»: -2 por letra) ni sumar una cueva de 14 palabras a la del Inablog (los dos necesitan `0x211a00`).
