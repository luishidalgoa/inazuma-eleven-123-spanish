# IE3 — ingeniería inversa del manejador de diálogo

> **Actualización 19-09-2026, Fase 2:** la localización mediante
> `301D → @offset,longitud → base evet + offset` ya está demostrada. Las
> hipótesis de esta bitácora que describen `@` como posición visual quedan
> sustituidas por [IE3_FASE2_REFERENCIAS](IE3_FASE2_REFERENCIAS.md).
> Hay una ruta nueva y un piloto de tamaño variable pendiente de prueba manual;
> no se reactivó `--crecer`. Las cifras y bloqueos siguientes son históricos.

Bitácora de la búsqueda de **cómo localiza el motor el texto de un diálogo en
`evet.pkb`**. Es lo que bloquea la reinserción: hoy solo se pueden meter 41 276
de 78 260 líneas porque ningún registro puede cambiar de tamaño.

Se anota TODO, incluidos los caminos que no llevan a nada, con la evidencia. Si
se queda a medias, aquí está el punto exacto.

**Módulo:** `work/shared/base_3ds/romfs/cro/ina_main3ogre.cro` (japonés,
3 481 600 B). Es el motor de **las tres** versiones de IE3 — Rayo Celeste
incluida. En el RomFS no hay ningún `ina_main3.cro`: solo `ina_main1.cro`,
`ina_main2.cro`, `ina_main3ogre.cro` y `ina_menu.cro`. El `activos.toml` de
`ie3.rayo_celeste` declara `cros = ["cro/ina_main3ogre.cro"]`. El nombre es
histórico.

---

## Punto de partida

De `capas/ie1/v82/saltos_dialogo/comun82.py` (IE1, ya resuelto):

- `0x55504` despachador de instrucciones; tabla en `0x55554` indexada por
  `opcode - 0x3002`.
- `0x301c` (abrir ventana) → `0x56d24`; `0x301d` (diálogo) → `0x56eb0`.
- `0x56eb0` llama a `0x36c54`, que expande `%s`/`%d` y convierte `\n`→0x0A en un
  búfer de 0x200 B, y luego a `0x424f4` (el reajuste de línea).

En IE3 ya están localizados, por el mismo patrón y con coincidencia única:

| qué | dirección | instrucción |
|---|---|---|
| ancho por defecto de la ventana | `0x039CEC` | `mov r2,#0xF0` → `strh [r0,#0x1A]` |
| líneas por defecto | `0x039CF8` | `mov r1,#3` → `strh [r0,#0x1C]` |
| ancho que pasa el manejador del diálogo | `0x04F3CC` | `mov r1,#0xF0` |
| líneas que pasa el manejador | `0x04F3D0` | `mov r2,#3` |
| ancho de la rejilla de dibujo | `0x03A928` | `mov r2,#0x120` |

O sea: **el manejador del diálogo de IE3 está alrededor de `0x04F3CC`.** Ése es
el sitio por donde hay que tirar.

---

## Qué se sabe del bytecode

> **Esta sección estaba equivocada y se ha reescrito.** La versión anterior daba
> por hecho que `0x301a` era la instrucción del diálogo y analizaba sus
> argumentos buscando ahí la referencia al texto. No lo es: ver el apartado
> «HALLAZGO PRINCIPAL» más abajo. Se conserva la corrección para que nadie
> repita el camino.

- **`0x301d` es el diálogo** (97,9 % de coincidencia con el número de diálogos
  por evento, sobre 1 852 eventos). Igual que en IE1.
- **`0x301a` abre y configura la caja**: fija el hablante y el ancho. Es donde
  está el `mov r1,#0xF0` que se parchea para ensanchar la ventana. Sus
  argumentos, para referencia:

  | arg | qué es |
  |---|---|
  | arg1 | ID del hablante (u16), resuelto por búsqueda lineal |
  | arg2 | se enmascara a 8 bits y va a `0x1D43B0` — expresión o retrato |
  | arg5 | selector de caso de la tabla de saltos de `0x04F3F0` |

- **No existe ningún argumento que apunte a `evet`.** Los argumentos de `0x301d`
  son todos índices de la tabla de textos del propio SSD, y los del diálogo
  apuntan a huecos vacíos que el motor rellena. Por eso ❌#16 y ❌#17 no
  encontraron nada: no había nada que encontrar.

---

## Cadena localizada (desensamblado con capstone)

Se siguió el mismo hilo que en IE1: buscar el preprocesador de texto, que es el
que convierte la barra invertida + `n` (`0x5C 0x6E`) y expande los `%`, porque
**recibe el puntero al texto** y desde ahí se sube.

### `0x08AC70` — despachador de códigos `%`

Localizado buscando la única pareja de `cmp #0x5C` / `cmp #0x6E` a menos de
0x80 bytes en todo el módulo: `0x08ACBC` y `0x08AD2C`. Coincidencia única.

```
08AC70  push {r4,r5,r6,r7,r8,lr}
08AC74  mov  r4, r1          ; r1 = CURSOR dentro del texto
08AC78  mov  r7, r0          ; r0 = objeto de la ventana
08AC7C  ldrb r0, [r1,#8]     ; campo del cursor
08AC98  ldrb r0, [r4]        ; byte del texto
08AC9C  cmp  r0, #0x6d       ; 'm'
08ACA8  cmp  r0, #0x64       ; 'd'
08ACB4  cmp  r0, #0x5a       ; 'Z'
08ACBC  cmp  r0, #0x5c       ; barra invertida
08ACC4  cmp  r0, #0x62       ; 'b'
```

`r1` es una **entrada de la tabla de manejadores** (se leen `[r1+0]`, `[r1+4]`
y `[r1+8]`), no un puntero al texto. Llamado desde un único sitio, `0x08A7E8`,
dentro de la función de abajo.

### `0x08A610` — NO es lo que parecía: construye las tablas de códigos `%`

**Corrección.** En una primera lectura se tomó por la función que recorre el
texto. Al desensamblar el cuerpo entero resulta que hace dos veces el mismo
patrón:

```
08A61C  ldr  r0, [r5,#0x3c]      ; ¿ya está construida la tabla?
08A620  cmp  r0, #0
08A624  bne  0x8A694             ; sí -> pasa a la segunda
08A628  ldr  r1, [pc,#0x300]     ; plantilla (0x70 B)
08A62C  mov  r2, #0x70
08A634  bl   memcpy
08A640  mov  r0, #0xe0           ; reserva 0xE0 B
08A644  mov  r1, #3
08A648  bl   0x14D450            ; asignador
08A654  ...                      ; convierte entradas de 8 B en entradas de 0x10
08A690  str  r3, [r5,#0x3c]      ; cachea la tabla en el objeto

08A694  ldr  r0, [r5,#0x40]      ; segunda tabla, plantilla de 0x60 B,
...                              ; reserva 0xC0 B, misma conversión
```

O sea: **es el constructor perezoso de las dos tablas de manejadores de `%`**,
que se cachean en el objeto ventana en `+0x3c` y `+0x40`. El `r4` que parecía un
cursor sobre el texto es un cursor sobre la plantilla.

`0x08AC70`, al que llama, es el **despachador de un código `%`**: recibe el
objeto y una entrada de esas tablas, y compara la letra (`'m'`, `'d'`, `'Z'`,
`'b'`, barra invertida).

**Consecuencia: esta rama no lleva al puntero del texto.** Es el subsistema de
códigos de formato. Se deja documentada para que nadie la vuelva a recorrer.

Dato útil aun así: la vtable del objeto ventana está en el segmento 1 y
`0x08A610` ocupa su entrada `0x2BDFF0`. Sus hermanos (`0x08B11C`, `0x08B168`,
`0x08B1D4`, `0x08B354`, `0x08B3B0`, `0x08B42C`, `0x08B54C`) son los demás
métodos de la misma clase, y el typeinfo está en `0x2BA41C`. Si hace falta
volver a esta clase, ahí está entera.

---

## El manejador del diálogo: `0x04F230`

Localizado buscando el prólogo hacia atrás desde el `mov r1,#0xF0` de
`0x04F3CC`, que está a 0x19C bytes.

```
04F230  push {r4,r5,r6,r7,lr}
04F234  sub  sp, sp, #0x21c     ; búfer de trabajo grande
04F238  mov  r5, r0             ; r0 = contexto del script
04F23C  mov  r4, r1             ; r1 = LA INSTRUCCIÓN
04F240  mov  r6, r2
04F244  mov  r2, #0x80
04F24C  add  r0, sp, #0x68
04F250  bl   memset             ; limpia 0x80 B en sp+0x68
04F254  ldrsb r0, [r4,#0xb]     ; byte de PASO/flags de la instrucción
04F260  beq  0x4F270            ; 0 = primer paso
04F268  bne  0x4F538            ; otros pasos (la instrucción dura varios frames)

04F270  add  r2, sp, #0x68      ; destino de los argumentos evaluados
04F274  mov  r1, r4
04F278  mov  r0, r5
04F27C  bl   0x161B24           ; EVALÚA LOS ARGUMENTOS
04F280  str  r0, [r4,#4]
04F284  ldr  r0, [sp,#0x6c]     ; arg1 ya evaluado
04F288  bl   0x187CB0           ; lo resuelve a un objeto
04F28C  movs r1, r0
04F294  beq  0x4F2B0            ; si no existe, camino alternativo
04F298  mov  r2, #0x68
04F29C  add  r0, sp, #0xe8
04F2A0  bl   memcpy             ; copia 0x68 B del objeto a sp+0xe8
```

**Los argumentos evaluados quedan en `sp+0x68`**, de 4 en 4: arg0 en `+0x68`,
arg1 en `+0x6c`, arg2 en `+0x70`, etc. Eso da una forma directa de saber qué
hace cada argumento: ver qué offset de `sp` se lee.

### `arg1` es el ID del HABLANTE, no el texto

```
187CB0  uxth r1, r0        ; el ID son 16 bits
187CB4  ldr  r0, [pc,#4]   ; puntero global (a cero en el fichero, reubicado)
187CB8  ldr  r0, [r0]      ; el gestor
187CBC  b    0x188A68      ; salto a la búsqueda
```

```
188A6C  ldrh r3, [r0,#0x18]       ; nº de elementos
188A94  ldr  r4, [ip,#8]          ; array de punteros
188A98  ldr  r0, [r4,r2,lsl#2]    ; array[i]
188AA4  ldrh r4, [r0,#0x8e]       ; flags
188AA8  tst  r4, #1               ; ¿activo?
188AB0  ldrh r4, [r0,#0x4e]       ; ID del elemento (u16)
188AB4  cmp  r4, r1               ; ¿es el buscado?
188AB8  beq  0x188AD0             ; sí -> devuelve el objeto
188ACC  mov  r0, #0               ; no encontrado
```

Búsqueda **lineal** sobre un array de objetos, comparando un `u16` en `+0x4e`.
Devuelve un objeto de 0x68 B, que es justo lo que el llamador copia.

Esto encaja con los valores observados de arg1 (1651, 1671, 1812, 3165, 3170):
son identificadores de actor/personaje, no punteros ni offsets.

**Así que el texto lo referencia OTRO argumento**, y el candidato sigue siendo
arg2 (los 0, 2, 8), que es lo que ❌#17 no consiguió confirmar.

### Después del hablante

De `0x04F2D0` a `0x04F350` se construye el **rótulo del nombre**: dos `memset`
(0x28 y 0xC8 B), copias de cadena (`0x3F8`) y `strlen` (`0x780`) sobre `sp+0x48`,
con comparaciones contra `0x82` y `'0'`. Nada de esto toca el texto del diálogo.

---

## Qué hace cada argumento de `0x301a`

Los argumentos evaluados viven en `sp+0x68 + 4*n`. Recorriendo la función entera
y anotando de qué offset lee cada instrucción:

| arg | dónde se lee | qué se hace |
|---|---|---|
| arg0 | `0x04F3B4` | decide un modo (`0/1/2`), se guarda en `sp+0x24` |
| **arg1** | `0x04F284`, `0x04F2B0` | **ID del hablante**; se resuelve con `0x187CB0` |
| **arg2** | pasa a `0x08A0A4` en r2 | **sin identificar**; ver abajo |
| arg3 | `0x04F448` | se guarda en `sp+0x214` |
| arg4 | `0x04F450` | va en r3 a `0x08A0A4` |
| arg5 | `0x04F3E4` | **selector de caso**: `+1`, `cmp #6`, tabla de saltos en `0x04F3F0` |
| arg6 | `0x04F468` | — |

### La llamada central

```
04F448  ldr r0, [sp,#0x74]    ; arg3
04F450  ldr r3, [sp,#0x78]    ; arg4
04F458  add r0, sp, #0x6c
04F45C  ldm r0, {r1, r2}      ; r1 = arg1 (hablante), r2 = arg2
04F460  add r0, sp, #0x150    ; búfer de salida (0xC8 B, limpiado antes)
04F464  bl  0x08A0A4
```

### `0x08A0A4`

```
08A0B0  mov  sb, r2           ; arg2
08A0B8  mov  r7, r1           ; arg1
08A0C0  bl   0x187CB0         ; resuelve el hablante otra vez
08A0C8  beq  0x8A0EC          ; si no existe -> 0x17A1BC (camino alternativo)
08A0D0  mov  r2, #0x97
08A0D8  bl   memcpy           ; copia 0x97 B del hablante a la pila
08A10C  bl   0x167E8C         ; comprueba algo (cmp #3)
08A128  bl   0x18A83C
...
08A18C  and  r1, sb, #0xff    ; los 8 BITS BAJOS de arg2
08A190  mov  r0, sp           ; la estructura del hablante
08A194  bl   0x1D43B0         ; <<-- AQUÍ SE CONSUME arg2
```

**`arg2` se enmascara a 8 bits.** Eso encaja con los valores vistos (0, 2, 8) y
**descarta que sea un índice de registro de `evet`** en bloques de 87 registros:
no cabrían. Refuerza ❌#17.

Candidatos para `arg2`: expresión o retrato del hablante, o una variante de
línea. `0x1D43B0` lo dirá.

---

## HALLAZGO PRINCIPAL: el opcode del dialogo es `0x301d`, no `0x301a`

Medido sobre 1 852 eventos, contando instrucciones de cada opcode frente al
numero de DIALOGOS del `evet` del mismo evento (cabezas de grupo, sin lecturas):

| opcode | coincide exacto | dentro de ±1 |
|---|---|---|
| **`0x301d`** | **1 814 (97,9 %)** | **1 851 (99,9 %)** |
| `0x301e` | 936 (50,5 %) | 55,9 % |
| `0x301a` | 171 (9,2 %) | 17,5 % |

`0x301d` es el dialogo, igual que en IE1. `0x301a` (donde esta el `mov r1,#0xF0`
del ancho) es la instruccion que **abre y configura la caja**: fija el hablante
(arg1) y el ancho. Son cosas distintas y conviene no confundirlas.

### Los argumentos de `0x301d` son SLOTS de la tabla de textos del propio SSD

Todos son de tipo 3 (indice de cadena del SSD). En el evento 31010000:

```
0x301d argc=2:  [166]='@0,36'     [167]=''
0x301d argc=3:  [172]='@36,68'    [173]=''  [174]=''
0x301d argc=4:  [185]='@104,112'  [186]=''  [187]=''  [188]=''
```

**arg0 es el parametro de posicion `@x,y`; los demas apuntan a huecos VACIOS.**
Eso explica los ~63 000 huecos vacios que se contaron en el `eve` japones y que
hasta ahora no tenian explicacion.

### Qué son exactamente esos huecos: las LECTURAS furigana

Medido sobre 37 425 dialogos, comparando `argc-1` con el numero de marcas `%nF`
del dialogo correspondiente en `evet`:

| | |
|---|---|
| `argc-1` == numero de marcas | **34 654 (92,6 %)** |
| distinto | 2 771, y **todas** por +1 exactamente |

O sea: **hay un hueco por cada lectura furigana**, y en un 7,4 % de los casos
hay uno de mas. Encaja con que la version europea los elimine todos (`argc` 1):
el espanol no lleva furigana.

**Consecuencia importante: el TEXTO del dialogo NO esta en esos huecos** — las
lecturas si. El texto sigue viniendo de `evet`. Eso rebaja bastante la esperanza
de mover la reinsercion al SSD, aunque queda por ver que es el hueco de mas del
7,4 %.

### La version europea lo confirma y da la clave

El MISMO evento en `es/inazuma3/data_iz/script/eve`:

```
EU:  0x301d argc=1:  [166]='@0,28'
     0x301d argc=1:  [171]='@28,28'
     0x301d argc=1:  [182]='@56,72'
```

**`argc` pasa de 2/3/4 a 1: los huecos vacios desaparecen.** Como el espanol no
lleva furigana y el japones si, la lectura natural es que **cada hueco extra
corresponde a una lectura furigana** de esa linea.

Consecuencias:

1. El `evet` alimenta esos huecos **en orden**; no hay ningun offset ni indice
   guardado en el bytecode que apunte a `evet`. Por eso ni ❌#16 ni ❌#17 dieron
   con el: no existe tal argumento.
2. **Level-5 RECOMPILO los scripts al localizar.** Al cambiar `argc` cambia el
   tamano de la instruccion y con el toda la seccion de codigo. Eso confirma, por
   tercera via, que la comparacion JP/EU de ❌#16 no probaba nada.

### Direccion nueva que esto abre

Si el texto acaba en la tabla de textos del SSD, **quiza se pueda escribir el
espanol directamente en esos huecos en vez de pelearse con `evet`**. Serian dos
ventajas grandes:

- la tabla de textos del SSD se referencia **por indice**, que es estable, y
  `ie123kit.nucleo.eventos.ssd.replace` ya sabe hacerla crecer;
- desaparece el problema de los tamanos de `evet` que limita hoy la cobertura a
  41 276 de 78 260 lineas.

**Falta comprobar lo esencial:** si el motor SOBREESCRIBE esos huecos con lo que
haya en `evet` al cargar el evento. Si los sobreescribe, escribir ahi no sirve
de nada. Dos formas de saberlo, por coste:

1. **Prueba en emulador, barata:** escribir una marca reconocible en un hueco
   vacio de un evento del prologo, dejar su `evet` intacto, y ver si sale la
   marca o el japones. Una build y la respuesta es binaria.
2. Desensamblar el cargador del evento y ver si copia `evet` sobre la tabla.

---

## Experimento preparado: `inazuma123_slots.3ds`

Prueba binaria para saber si esos huecos son el almacen real del texto.

**Qué hace:** escribe una marca reconocible (`SLOT01-ESTE-ES-EL-HUECO`,
`SLOT02-...`) en los 215 huecos vacios que `0x301d` referencia en los cinco
eventos del prologo italiano (32010200, 32010300, 32500100, 32500120,
32500130). **`evet` se deja intacto.** Los registros del SSD crecen lo que haga
falta, que es legitimo porque la tabla de textos del SSD se referencia por
indice.

Generado con `scratchpad/prueba_slots.py` (conviene moverlo a `tools/` si el
resultado es positivo).

**Cómo leerlo:**

| Lo que sale en el prologo | Qué significa |
|---|---|
> **Ojo al interpretarlo.** Medido despues de preparar la build: esos huecos son
> las **lecturas furigana**, una por marca `%nF` (92,6 % de coincidencia). O sea
> que la marca, si aparece, saldra como **ruby encima del texto**, no como el
> dialogo. Aun asi la prueba sigue valiendo, y mucho.

| Lo que salga | Qué significa |
|---|---|
| La marca **encima** del texto, como furigana | Los huecos se escriben desde el SSD y **admiten crecer**. Abre la via de vaciarlos ahi mismo en vez de en `evet`, que es justo lo que hoy consume el presupuesto de bytes de cada grupo. |
| Ruby en japones de siempre | El motor los rellena desde `evet` al cargar. Los huecos del SSD son solo destino, no origen. |
| Se cuelga | Crecer la tabla de textos del SSD no es seguro en IE3, pese a serlo en IE1. Anotarlo como ❌ nuevo. |
| Nada raro, el prologo va normal | Los huecos ni se leen. Descartar la via. |

**Qué se gana si la marca aparece:** hoy, para meter el espanol, hay que robarle
bytes a las lecturas furigana DENTRO del grupo de `evet`, y eso es lo que limita
la cobertura. Si las lecturas se pueden vaciar desde el SSD, el registro de
`evet` no necesita moverse ni robar nada.

---

## Bug cazado al intentar montar una v107

Al regenerar el contenedor con el codigo actual salia distinto de la v106, y el
log decia «6 offsets recolocados». Era la recolocacion basada en ❌#17, que se
disparaba incluso en modo mismo-tamano: al repartir bytes dentro de un grupo se
mueven las lecturas, el mapa deja de ser identidad y 6 valores de `0x301a` arg2
coincidian por azar con esas posiciones. **Se estaban corrompiendo 6 operandos
por una hipotesis ya desmentida.**

Desactivada. Tras desactivarla el contenedor vuelve a ser **byte a byte
identico** al de la v106 (`a45c6993…`), que es lo que debia ser.

Leccion de proceso: cuando se desmiente una hipotesis, hay que quitar tambien el
codigo que la implementaba, no solo anotarlo en el documento.

---

## Dónde continuar exactamente

**Descartado:** la rama `0x08A610` / `0x08AC70` es el subsistema de códigos
`%`, no el que localiza el texto.

**Por donde seguir, en orden de coste:**

1. **`0x1D43B0`** — es quien consume `arg2` (enmascarado a 8 bits) junto con la
   estructura del hablante. Desensamblarla dice qué es arg2 de una vez.
2. **`0x04F538`** — la rama de los pasos siguientes de la instrucción
   (`[instrucción+0xB] != 0`). El texto puede fetcharse ahí y no en el primer
   paso, porque la instrucción dura varios frames. **Es el candidato más
   probable y no se ha mirado.**
3. **La tabla de saltos de `0x04F3F0`**, seleccionada por `arg5+1` con 6 casos.
   Sus entradas están en `0x04F3F8`, a cero en el fichero: resolver con las
   tablas de reubicación, no desensamblando.
4. **Duda de fondo que conviene despejar antes de seguir:** puede que `0x301a`
   NO sea la instrucción que muestra el texto, sino la que abre la caja y fija
   hablante y ancho. Comprobación barata: contar, en un evento, cuántas
   instrucciones de cada opcode hay frente a cuántos diálogos tiene su `evet`, y
   mirar si algún otro opcode cuadra mejor uno a uno.
2. **Desde la carga del pack.** El bloque de `evet` de un evento se localiza por
   su id en el `.pkh`. Buscar el código que lee la cabecera `"PackNum "` o que
   recorre entradas de 12 bytes da la función de búsqueda, y su valor de retorno
   es el puntero al bloque. Desde ahí se ve cómo se indexa dentro.
3. **Experimento en emulador, que es lo más barato.** Con la build de
   diagnóstico (`ie123kit.ie3.pipeline diagnostico`) se puede montar un caso
   controlado: encoger a propósito un registro anterior una cantidad conocida y
   ver si la regla empieza desplazada esa misma cantidad. Eso confirma o descarta
   ❌#16 sin desensamblar nada.

**Herramientas ya escritas** (en el scratchpad de la sesión, conviene moverlas a
`tools/`): desensamblador con capstone, buscador de llamadas `bl` a una
dirección, y decodificador de las tablas de reubicación del CRO. El formato de
una entrada de 12 B es:

```
a: (desplazamiento << 4) | segmento_origen    donde se escribe el puntero
b: byte0 = tipo de parche, byte1 = segmento destino
c: desplazamiento dentro del segmento destino
```

Segmentos del CRO: [0] código en `0x000180` (0x29BDC8 B), [1] datos en
`0x29C000`, [2] en `0x34DA80`, [3] bss. Con eso se resuelve cualquier puntero
que el fichero tenga a cero.

---

## Estado

- [x] Localizado el manejador del diálogo (alrededor de `0x04F3CC`).
- [x] `0x301a` identificada como la instrucción de diálogo (una por diálogo).
- [x] Localizado el despachador de `%` (`0x08AC70`) y su único llamador.
- [x] Localizada la función que recorre el texto (`0x08A610`).
- [x] Descartada la rama `0x08A610` / `0x08AC70` (subsistema de `%`).
- [x] Identificado `0x301d` como el opcode del diálogo (97,9 %).
- [x] Descubierto que sus argumentos son huecos VACÍOS de la tabla de textos del
      propio SSD, y que la versión europea los elimina (argc 2/3/4 → 1).
- [ ] **Saber si esos huecos son el almacén real del texto** → build
      `inazuma123_slots.3ds`, pendiente de probar en emulador.
- [ ] Si lo son: mover la reinserción del `evet` a la tabla del SSD.
- [ ] Si no lo son: averiguar por qué un cambio de tamaño en `evet` descuadra la
      lectura (el modelo de ❌#16 describe el síntoma pero no el mecanismo).

## Registro cronológico

### 2026-09-18 · sesión 1

- Confirmado que `ina_main3ogre.cro` es el módulo de las tres versiones de IE3.
- Localizados los cinco sitios de la ventana (tabla de arriba) por el patrón de
  IE1 e IE2, con coincidencia única.
- Parche del ancho aplicado y verificado contra las tablas de reubicación del
  CRO (40 030 entradas, ninguna de las tres direcciones aparece).
- Descartado que `0x301a` arg2 sea un offset (❌#17): correlación del 95 % que
  resultó ser ruido de valores pequeños.
- Detectada la contradicción entre el modelo de offset y el de índice.
- `pip install capstone` (lo documenta `DESARROLLO.md` para esto).
- Desensamblada la cadena hasta `0x08A610`. El hilo se corta ahí porque la
  función se llama por puntero y las tablas del CRO están a cero en el fichero.
- Herramienta nueva: `ie123kit.ie3.comun.verificar_offsets`, comprobación obligatoria
  antes de construir. Dice si algún diálogo se ha movido de su offset.

### 2026-09-19 · revisión tipográfica v7 (sin crecimiento de eventos)

La prueba del usuario rechaza v6. No reabrir las hipótesis estructurales de las
secciones históricas anteriores: el trabajo actual corrige fuentes y espera una
nueva prueba visual. Evidencia de solo lectura en `.code` JP descomprimido desde
`work/shared/base_3ds/exefs.bin` (VA; restar 0x100000 para offset):

- 0x223F50–0x223F7C: muestreo de textura con pitch `cellWidth+1` /
  `cellHeight+1` y origen +1. El lector histórico calculaba divisiones de la
  hoja y omitía el origen; produce los nombres torcidos de FONT8 europea.
- 0x1A1428–0x1A14A0: BuildTextCommand centra cada carácter salvo tipo 3.
  Vtable 0x293868, método +8 → 0x223FD4 devuelve FINF.width.
  Ese ancho es **15 FONT12 y 11 FONT8**, no el paso lógico de 10.
- 0x25705C → 0x256FA8 → 0x180CC8 → 0x1808D4: CalcStringRect.
  0x180BBC–0x180C6C mide avance, no left/glyphWidth; GetCharWidth
  0x223D58 extrae CWDH.charWidth. Escala inicial 1 en 0x2067B4/B8.
- Posición de tinta de una letra en esta ruta:
  `pen + trunc((FINF.width-charWidth)/2) + left`.
  La fuente v7 compensa left con el negativo de ese centrado. No requiere
  parche nuevo en el ejecutable ni cambio de avance.
- Pestaña hablante en `ina_main3ogre.cro`:
  0x4F4B8 → 0x160E88 → 0x160FB4 → 0x180880. 0x180CB8 mide posición
  lógica DS; 0x180CDC, posición NW. 0x18114C pasa ambas al dibujado y
  0x181154–0x181170 incrementa NW proporcionalmente. No confundir ambas.

Límite de la evidencia: hay un override de ancho en gestor+0x34 y variantes
con tamaños explícitos que no se han auditado exhaustivamente. La fórmula
está comprobada para la ruta habitual; no se afirma que toda la interfaz sea
proporcional ni que una previsualización equivalga a prueba en juego.

La implementación vive en `ie3/comun/tipografia.py`, sin tocar el congelado.
Pruebas independientes en `test_ie3_tipografia.py` y
`requiere_rom/test_ie3_tipografia_oficial.py`: geometría, compensación, raster,
márgenes y glifos japoneses intactos. Véase EXPLICACIONES_CODEX.md para la
rectificación del diagnóstico v6 y HISTORIAL_CODEX.md para la candidata exacta.
