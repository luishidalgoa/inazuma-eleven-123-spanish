# v86 · ¿Pueden los DATOS de evento ampliar el límite de 22 caracteres del diálogo?

Investigación de solo lectura. No se ha construido ni instalado nada, ni se han tocado tools/, docs/ o git.
CRO analizado: `work/shared/base_3ds/romfs/cro/ina_main1.cro` (original). El de la candidata v81 difiere
solo en zonas de datos (0x35xxx–0x7cxxx); el código citado aquí es el mismo.

## Veredicto

**Probablemente factible, pero hay que confirmarlo en el emulador.** Por el código, el cuarto
argumento de 0x301c (`arg4`, contando desde 0) escribe directamente el ancho de reajuste
`[ventana+0x1316]`. Cambiarlo no altera el tamaño del evento (es un entero de 4 B que ya existe).
No se ha podido demostrar lo siguiente:

- que el dibujo no recorte ni escale las líneas anchas;
- que el 0x301c #334 se ejecute antes que el diálogo #406;
- durante cuánto tiempo se mantiene el valor.

Solo lo puede resolver una prueba en el emulador.

## Evidencia (direcciones de ina_main1.cro)

### 1. Manejador de 0x301c: 0x56d24 (tabla 0x55554, entrada 0x301c-0x3002, reloc +0x180)

- `0xc3d58` evalúa los argumentos y los guarda de 4 en 4 bytes (`str r0,[r7,r4,lsl#2]` en 0xc3e8c)
  en un búfer de 0x80 B a cero (en `sp+0x28`).
- A continuación llama a `0xc2f28(ventana, r1=0, r2=0, r3=0, pila = arg0, arg1, arg2, arg3, arg4,
  arg5, r5)`. Los `mov r3,#0 / mov r2,r3 / mov r1,r3` de 0x56d80–0x56d90 están fijos, así que la
  rama de 0xc2f68 (`[sp+0x48]` ≠ 0, creación de sprites) no se ejecuta nunca desde 0x301c.
- Lo hace solo en el primer paso de la instrucción (`[inst+0xb]==0`).

### 2. `0xc2f28`, qué hace cada argumento (0xc3054–0xc30ac)

`ldm` en 0xc2f3c: r5..sl = arg0..arg5. Cada campo se escribe **solo si el valor no es 0**:

| arg | destino | tipo |
|---|---|---|
| arg0 | `[+0x3c]` | byte (valores reales: 3, 5, 4, 2, -1) |
| arg1 | `[+0x3d]` | byte (2, 1, 0) |
| arg2 | `[+0x3e]` | byte (siempre 0) |
| arg3 | `[+0x3f]` | byte (siempre 0) |
| **arg4** | **`strhne sb,[+0x1316]`** (0xc3094) | **ancho de reajuste**, int16 con signo (`ldrsh` en 0x4250c) |
| **arg5** | **`strhne sl,[+0x1318]`** (0xc309c) | **líneas por página** |
| r5 del llamador | `[+0x1100]` | 32 bits |

Al entrar, 0xc2f28 también limpia `+0x30`, `+0x3a/3b`, `+0x12a` y `+0x206`, pero **no** toca `+0x1316`.

### 3. Quién lee o escribe `+0x1316` y `+0x1318`

He barrido las 417.607 instrucciones del segmento de código (`todo.py`). `add rX, rY, #0x1300` aparece
solo en 7 sitios:

- escritura en `0x465c8` (valores por defecto 0xF0 y 3), dentro de la función `0x46174`. Esa función
  no tiene llamadas directas; es un constructor o una inicialización llamada por puntero;
- escritura en `0xc3094` y `0xc309c`, que es este mismo camino (0x301c);
- **lectura solo en `0x4250c`/`0x42510`**, dentro del reajuste `0x424f4`, cuyo único llamador es el
  manejador de 0x301d (0x56f20).

Ningún otro código lee el valor: ni el dibujo, ni el rubí, ni la pestaña del nombre.

### 4. El reajuste `0x424f4`

`sl = [+0x1316] + 0x20`. Cada carácter cuenta 12 (FONT12). Si `x + 12 >= sl`, el motor inserta un
salto. Por tanto, el máximo de caracteres por línea es `max n` tal que `12·n < arg4 + 32`.

| arg4 | límite | caracteres por línea |
|---|---|---|
| 0 (se queda 0xF0) | 272 | 22 |
| 0x190 | 432 | 35 |
| **0x1A0** | **448** | **37** |
| 0x1B0 | 464 | 38 |
| 0x1C0 | 480 | 39 |

He simulado el caso con `simular.py`, que usa `comun82.motor`. Con arg4 = 0, el modelo reproduce
exactamente el fallo visto en v81: «Mark, ¿has hecho algo | que pueda haber | sentado mal al grupo d
|| e gamberros?». Con 0x1A0 o más, la frase objetivo queda intacta, en 2 líneas y 1 página.

### 5. Recorte o escalado en la caja (sin cerrar)

- El dibujo proporcional (0xe6600–0xe6b30, ver `e6600.txt`) avanza con el advance real de la BCFNT.
  Solo multiplica por 1,25 (literal en 0xe67f4) en el modo de paso fijo (`[r5+0x34] > 0`).
- En el tramo revisado no he encontrado un recorte ni un escalado que dependa del ancho. **No puedo
  descartar** un scissor o un recorte en otra parte, y nunca se ha visto en pantalla una línea de más de
  22 caracteres, porque el motor la partía antes.
- Geometría (v77 `comun.py`, medida en capturas):
  - el lápiz empieza en x≈16;
  - el icono de avance ocupa x 370–390 en la 3.ª línea;
  - el panel llega hasta ≈391.
- La tinta medida de la frase objetivo es de **284 px** y **264 px** (v77 `aplicado.json`, #406). La
  línea 1 acabaría en x≈300, con 70 px de margen hasta el icono.
- Con el tope de tinta de 290 px de v77, la caja admite como mucho unos **354 px** antes del icono. En
  la práctica, el límite de caracteres lo pone el valor de arg4 y el límite visual, la tinta (≤ 290 px).

### 6. Encuesta de 0x301c (`encuesta.py`, `encuesta_base.log`, `encuesta_v84.log`)

- Hay 1.293 eventos y 1.287 instrucciones 0x301c. De ellas, 1.285 tienen 6 argumentos y 2 tienen 5.
  Todos los argumentos son de tipo 1 (entero inmediato de 4 B).
- **Ningún evento japonés original usa arg4 ≠ 0 ni arg5 ≠ 0.** El juego nunca ejercita este camino,
  así que tampoco hay precedente de que funcione.
- Cambiar arg4 conserva el tamaño: se sustituyen 4 B por 4 B y ni la instrucción ni el evento crecen.
- En 81000090 (v84) hay un único 0x301c, el ident #334, con args `[4, 2, 0, 0, 0, 0]`:
  - la instrucción empieza en el desplazamiento 0x1b08 del SSD y mide 36 B;
  - **arg4 está en el desplazamiento 0x1b24** (hoy `00 00 00 00`).
- Otras aperturas que llaman a 0xc2f28 son `0x308d` (0x5b66c) y el grupo 0x308f–0x3091, vía 0x5bea0
  (0x5cc70, 0x5d784). La asignación de opcode es aproximada. Esas aperturas pasan otros argumentos a
  las posiciones de ancho, pero en los eventos solo aparecen sin argumentos (8×0x308f, 1×0x308d), así
  que no escriben el ancho.

## Riesgos

1. **Persistencia.** Nada devuelve `+0x1316` a 240 al cerrar la ventana:
   - solo lo restablecen `0x46174` (cuándo se ejecuta: desconocido) u otro 0x301c con arg4 ≠ 0;
   - un 0x301c con arg4 = 0 **no** lo restablece;
   - lo más probable es que el valor ancho se mantenga en los eventos siguientes hasta que se recree la
     ventana.
   - Esto no afecta al texto ya ajustado a ≤ 22 caracteres, porque un límite mayor solo inserta menos
     saltos. **Sí afecta** a los registros que dependen del reajuste automático (líneas largas sin
     `\n`), que se partirían más tarde y podrían salirse de la caja. Esos registros no están
     cuantificados.
   - Para restablecerlo explícitamente, se puede poner arg4 = 0xF0 en los 0x301c de otros eventos.
2. **Orden de ejecución.** En 81000090 hay 0x301d antes del #334 en orden lineal (índices 13, 22,
   31…), así que el flujo real puede saltar. No está comprobado que #334 se ejecute antes de #406.
3. **Furigana, pestaña de nombre y otros tipos de ventana.** No leen `+0x1316`. El rubí usa el camino
   de paso fijo (0x2F2F0), que no lo consulta. `+0x1318` (arg5) no se toca en la prueba.
4. **Signo.** El campo es int16 con signo (`ldrsh`). Hay que usar valores < 0x8000.
5. **Dibujo.** Queda sin demostrar que no haya recorte ni escalado (punto 5).
6. Esto es un **parche de datos**, no de código. Respeta la prohibición de CRO y code.bin, y el
   bloqueo tipográfico v20: no cambia fuente, caja, codificación ni espaciado.

## Plan de prueba (no ejecutado)

**Base:** la última candidata estable (v84) y la capa v82 aplicada.

**Cambios, solo en el evento 81000090:**

1. **0x301c #334, arg4:** escribir `A0 01 00 00` (0x1A0) en el desplazamiento 0x1b24 del SSD. Antes
   de escribir, comprobar que los 36 B de la instrucción son
   `4e 01 24 00 1c 30 06 01 11 11 11 00 04 00 00 00 02 00 …00`. No tocar nada más: arg5 sigue en 0.
2. **0x301d #406:** volver a la disposición v77, que tiene la misma longitud de registro:
   `Mark, ¿has hecho algo que pueda haber\nsentado mal al grupo de gamberros?`
   - 37 y 34 caracteres;
   - tinta de 284 y 264 px;
   - 1 página.
   - Validar que `len(registro)` es igual y que `comun82.motor(cuerpo, ancho=0x1A0) ==
     preprocesar(cuerpo)`.
3. Tamaño del evento y bytecode idénticos, salvo esos 4 B y el texto del registro.

**Opcional, para calibrar el límite:** añadir en otro registro del mismo evento que se vea después
una línea de exactamente 38 caracteres. El modelo predice que se partirá en el carácter 38.

**Qué comprobar en Azahar (según `PROTOCOLO_QA_IE1`):**

- #406 se ve en 2 líneas exactas y 1 página, sin saltos añadidos;
- la línea 1 no aparece recortada, escalada ni encima del icono;
- los diálogos anteriores y posteriores del evento se ven igual que en v84;
- el siguiente evento con diálogo también se ve igual (así se comprueba la persistencia).

**Cómo leer el resultado:**

| Lo que se ve | Qué significa |
|---|---|
| #406 sigue partido a los 22 | #334 no se ejecuta antes o no es la ventana que usa #406. Buscar otra apertura |
| Aparece en 2 líneas pero recortado | No factible sin tocar el código: queda descartado |
| Correcto | Factible. Siguiente paso: decidir el valor global (¿0x1A0 en todos los 0x301c?), estudiar el efecto sobre los registros que dependen del reajuste automático y medir en `ajustar` con el límite (arg4+32)/12 y la tinta ≤ 290 px |

Cualquier resultado, incluido el ❌, debe anotarse en `docs/FURIGANA_LECCIONES.md`.

## Archivos

- `desens.py`: desensamblador sobre el CRO base.
- `todo.py`: vuelca el segmento de código completo; su salida (12 MB) se borró.
- `h301c.txt`, `c2f28.txt`, `sub.txt`, `sub2.txt`, `e6600.txt`: desensamblados.
- `encuesta.py`, `encuesta_base.log`, `encuesta_v84.log`: encuesta de 0x301c.
- `simular.py`: simulación del reajuste con distintos valores de arg4.
