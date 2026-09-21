# IE3: geometría del nombre, fase 4

## Referencia y alcance

Auditoría de solo lectura de la candidata fase 3, CRO SHA-256
`763e5246edece475c23ba27eb1fe35db2861618903a80213b8d470c640cb1c77`.
No se cambia ninguna fuente, métrica, encoder, tracking, escala o buffer.
Las direcciones del CRO siguientes son offsets de archivo; las de `.code`
se identifican expresamente como VA (base `0x100000`).

La observación del usuario es «Maserat» y una i fuera de fila. La auditoría
demuestra un salto lógico antes del octavo carácter, no una pérdida de datos
ni un límite de siete bytes. No se dispone de captura nueva a resolución nativa;
la reproducción descrita aquí es del flujo ARM, no una prueba de ejecución.

## Datos hasta consumidor

En ambos perfiles la fila 1850 de `logic/unitbase.dat`, ID 3165, contiene el
campo corto en offset decimal 192428 (`fila*0x68+0x1C`):

```
4d 61 73 65 72 61 74 69 00 00 00 00 00 00 00 00
M  a  s  e  r  a  t  i  NUL
```

Son ocho bytes de nombre, NUL interno y ningún LF. El campo sigue midiendo
16 bytes. El manejador 301A `4F230` obtiene un objeto normal o de caché y copia
0x68 bytes a `sp+E8` (`4F298–2A0`); `4F2F0` selecciona `sp+104`, es decir,
nombre corto +1C. La ruta alternativa carga la misma estructura con `17A1BC`.
`4F4B8` llama `160E88` con ese puntero.

El resto de llamadores directos de `160E88` son `4A2D0`, `50F64` (nombre NULL)
y `54938`. Este último es 3019: tabla de manejadores de ocho bytes por entrada,
relocación en `29ECA0` a `548B8`, seguida de 301A en `29ECA8` a `4F230`.
3019 usa el primer argumento SSD como nombre. En la candidata son todos
operandos tipo 3 constantes: 154 Spark y 231 Ogre, sin productor dinámico.
El mayor cuerpo observado es 12 bytes Spark (`¿Sra. Hob.?`, once glifos) y
diez bytes Ogre. No confundir estos nombres ocultos con el corpus unitbase.

## Dos posiciones diferentes: lógica y dibujo

`160F80`, palabra `E3A02040`, carga el límite **lógico** 64 y `160F88` lo
guarda en el argumento de pila +8. La llamada `160FB4 → 180880` lo carga en
`1808A4` desde `sp+C8` y lo conserva en `sp+28` (`1809C4`). No es la anchura
de las letras ni el tamaño del campo de unitbase.

La llamada de importación `858` es `FontGetCharWidth`. Se resolvió el nombre
en la tabla de importaciones del CRO y su exportación en `static.crs`: `.code`
VA `164660`. La función ignora el carácter y devuelve una entrada por FONT_TYPE
de la tabla VA `25AF98`: `(12, 8, 12, 4)`. FONT8 devuelve ocho siempre.

- `180CB8`: obtiene ancho lógico fijo; resultado en `fp`.
- `180CDC`: obtiene por separado avance NW real; resultado en `sp+48`.
- `180E98–EA0`: acepta carácter si `r8 + fp <= sp+28`; si no, cambia de fila.
- `181150–15C`: después de dibujar, `r8 += fp + gestor[14]`.
- `181154–170`: la posición NW se incrementa por avance real más ese tracking.

El tracking de esta ruta sigue siendo uno. Por tanto el octavo carácter exige
`7*(8+1)+8 = 71`, superior a 64. El séptimo exige 62 y cabe. El parche FONT8
de fase 3 eliminó el override de anchura, pero no cambió este límite lógico.
Eso explica por qué la tinta proporcional cabe y, aun así, la i salta.

No hay compensación tipográfica que deba alterarse para resolver esta causa.

## Capacidad gráfica: condición antes de ampliar el límite

La pestaña crea un recurso en `039A10–1C` con exponentes `(3,1)` mediante
`1818CC`. `181948/950` conserva estos exponentes y el formato es 3. Las
dimensiones son `8<<3 = 64` por `8<<1 = 16`; `184A84` calcula los bytes con
división por dos para ese formato: **512 bytes**, sin ampliación. El recurso
se guarda en ventana+32. `181260` obtiene su memoria y `16F874` su altura 16.

El dibujador avanza el puntero de comandos en 32 bytes por glifo (`181168`).
Al terminar, `1811B4–1CC` usa el mismo límite lógico por altura dividido por dos
para decidir si escribe el terminador. **No es correcto afirmar que cambiar
64 a 80 es exclusivamente una comparación sin otras consecuencias**: ese
cálculo final pasaría de 512 a 640 aunque la asignación siguiese siendo 512.

Para los productores acotados examinados, la capacidad real continúa siendo
suficiente: campo unitbase con NUL en 16 bytes implica como máximo 15 glifos,
es decir, `15*32 + 32 = 512`; los 3019 constantes actuales son menores. Una
integración debe verificar esas cotas sobre su salida final y mantener una
guardia explícita para 3019, no extrapolar seguridad a nombres arbitrarios o
futuros campos de más de 15 glifos. No se autoriza aumentar buffers ni cajas.

Se amplió la comprobación a todos los recursos estáticos de esta cadena, no
solamente a los nombres traducidos: unitbase normal Spark/Ogre (2.582 filas
cada uno), unitbase ex_binder Ogre (2.582) y unitbase_npc Spark/Ogre (512 cada
uno). Los NPC tienen stride 0x50, nombre corto +0x10: `17A45C–468` copia esos
16 bytes al corto +0x1C del objeto normal. Los cinco recursos tienen NUL
interno en todas las filas y máximo diez bytes antes de NUL. Los productores
de caché/guardado conservan la estructura de nombre de 16 bytes, pero esta
auditoría no ha recorrido cada escritor de nombres de usuario: un guardado
que incumpla el contrato NUL16 queda fuera de la prueba, y no se promete
seguridad para cadenas arbitrarias más largas.

## Parámetro candidato y pruebas obligatorias

El cambio mínimo de límite para permitir nueve caracteres de esta ruta es
`160F80: E3A02040 → E3A02050` (`mov r2,#64 → #80`), pues el noveno exige
`8*9+8=80`. La instrucción no aparece entre los 40.030 destinos de relocación.
No se ha aplicado en esta auditoría. Anclas inmediatas:

```
160F7C 210083e8  stm r3,{r0,r5}
160F80 4020a0e3  mov r2,#64
160F84 0c008de2  add r0,sp,#12
160F88 08208de5  str r2,[sp,#8]
160FB4 317e00eb  bl 180880
```

Debe comprobarse capacidad real y tinta colocada, no solo que nueve caracteres
se admitan lógicamente. Con el raster y métricas aprobados, sin escalarlos:

| Caso | Caracteres | Avance NW incluyendo tracking final | Anchura de tinta |
|---|---:|---:|---:|
| Bianchi | 7 | 36 | 35 |
| Maserati | 8 | 45 | 44 |
| Downtown / Tomahawk | 8 | 54 | 53 |
| iiiiiii | 7 | 21 | 20 |
| iiiiiiii | 8 | 24 | 23 |
| iiiiiiiii | 9 | 27 | 26 |
| WWWWWWW | 7 | 70 | 69 |
| WWWWWWWW | 8 | 80 | 79 |
| WWWWWWWWW | 9 | 90 | 89 |

Nueve W no se pueden declarar válidas por tener nueve caracteres: pueden
exceder la placa. El corpus unitbase integrado tiene como máximo ocho
caracteres. Nombres ocultos 3019 de más de nueve siguen requiriendo evaluación
de su presentación, sin truncar sus datos ni introducir abreviaturas.

## Espacios: completar el modelo, no cambiar la fuente

La investigación paralela del dibujador demuestra que `get_code_utf16`,
`.code` VA `1A0FDC–1A100C`, convierte ASCII 0x20 en U+3000. FONT8 aprobada no
tiene CMAP para U+0020 pero sí U+3000 (glifo 358), con CWDH `(5,0,5)`.
Es un espacio sin tinta y avance cinco; con tracking existente suma seis.
La falta de U+0020 no significa carácter omitido en el juego. El renderer debe
modelar esa conversión y seis unidades de avance; no editar encoder, CWDH o
texto oficial. Esta causa no explica Maserati, que no contiene espacios.

Falta confirmar en ejecución origen y bordes útiles de la pestaña, nombres con
espacio, ambas pantallas y listas FONT8. Los cálculos anteriores son evidencia
de código/datos y simulación; no constituyen validación manual del conjunto.

## Solución revisada: guardia runtime independiente de nombres/guardados

La propuesta de cambiar `160F80` se **descarta**: la comprobación final solo
protege el terminador, no impide que se hayan escrito previamente demasiados
comandos. Tampoco bastaba con conservar `sp+28=64` y ampliar únicamente el
comparando: con dos filas de nueve caracteres podría escribirse fuera del
buffer antes de llegar al terminador. No se fundamenta seguridad en un supuesto
sobre guardados del usuario ni solamente en las longitudes del corpus.

Se implementa `ie3/comun/limite_nombre.py`, función pura
`parchear_limite_nombre(cro)`, sin emitir CRO o ROM en esta subtarea:

1. `180E9C`, antiguo `cmp r1,r2`, salta a `180930`. El `add r1,r8,fp` de
   `180E98` permanece intacto.
2. El bloque `180930–948`, muerto desde el parche FONT8 de fase 3, reconoce
   el retorno guardado `sp+BC == baseCRO+160FB8` por diferencia con PC. La
   base de carga se cancela; no se requieren direcciones absolutas nuevas.
3. Solo ese llamador aumenta **el registro temporal r2** en 70 (límite134,
   revisado desde el primer límite80 para cubrir toda la capacidad válida).
   La memoria
   `sp+28`, el argumento original 64, el buffer de 512 bytes y su geometría
   siguen intactos. Los otros llamadores pasan al CMP original reproducido.
4. Antes del dibujo del nombre, se calcula `r6 - base_comandos(sp+C4)` y se
   termina si es mayor o igual a 480. Así se admiten como máximo 15 comandos
   y se reserva el comando de 32 bytes del terminador. Ni un nombre inesperado
   ni un guardado más largo pueden provocar la escritura del comando 16.
5. El CMP reproducido restaura los flags para el BLE original `180EA0`.
   Solo r0 (muerto hasta las siguientes cargas originales) y r2 temporal se
   alteran. r1, r6, r8, fp, pila y todos los registros restantes se conservan.

El stub necesita reutilizar cinco pares NOP: `180A58/5C`, `180A70/74`,
`180A88/8C`, `180AA0/A4`, `180AB8/BC`. Son colas de casos de selección de
color. Su primer NOP anterior (`180A54`, `180A6C`, `180A84`, `180A9C`,
`180AB4`) pasa a salto directo a **su mismo destino original** `180B08`.
No cambia color, configuración, flags ni registros de ese flujo; las nuevas
instrucciones solo se ejecutan desde el hook. Las otras tres variantes de
color permanecen literales. Se comprobaron ausencia de entradas directas,
exportaciones y referencias reubicables a todos estos sitios y ausencia de
destinos de relocación en las 23 palabras modificadas. Todo permanece dentro
del segmento de código existente; no se usa padding exterior ni se amplía.

Entrada exacta SHA fase 3; salida calculada final con límite134 (solo en memoria):
`d96b6cfb7348a40e62c9466107de02dc79ab174a35a1b50bd2918cfc45350158`.
El SHA preliminar `4116df585107531aa9b84177d0ac37b9a6186d7a256af64e2a3cfb4a7876a4b7`
correspondía al umbral80 y queda sustituido, no se emitió una ROM con él.
El parche es idempotente, rechaza estados parciales/desconocidos y conserva
literalmente todos los bytes ajenos a las 23 instrucciones inventariadas.

La validación usa un intérprete independiente del subconjunto ARM real del
stub (Unicorn no está instalado), con ASLR, llamadores ajenos, comparación
de flags/registros, todos los caminos de color reutilizados y nombres desde
cero hasta 1.000 caracteres. El comando 15 se admite; el 16 se rechaza antes
de dibujar. Ese corte defensivo no se presenta como localización completa de
entradas inválidas: el emisor debe seguir rechazando un nombre nuevo que
exceda la capacidad, sin abreviarlo. Los nombres actuales no activan el corte.
Se añade prueba con el CRO oficial de referencia y todos sus 40.030 destinos
de relocación. Ninguna prueba supone validación en juego.

## Renderer completado y auditoría de nombres actuales

`medir_nombre` y `render_comparacion` completan la conversión del espacio sin
cambiar recursos tipográficos. La comparación muestra **la misma FONT8 y el
mismo avance proporcional** a ambos lados; solo cambia la separación lógica
64 frente a 134. Las filas se separan para inspección, no se presenta ese
espaciado del lienzo como baseline real del emulador. Un píxel que quedase
fuera del lienzo o un nombre que superase 15 comandos provoca error, no un
recorte silencioso. Se mantienen las claves históricas del informe métrico.

Ejecución `python -X utf8 work/fase4_nombre/auditar.py` sobre la candidata fase3:
`work/fase4_nombre/auditoria.json` y `nombres_simulacion.png`, revisada visualmente.
Se comprobaron 8.770 filas unitbase/NPC/ex_binder: cero glifos sin modelar,
cero raster fuera de glyphWidth, todas NUL16 y dentro de 512 bytes. Los 29
nombres con espacios por perfil ya tienen medidas completas. Máxima tinta
unitbase normal: 53 (Downtown/Tomahawk); NPC: 50; ex_binder JP: 52. Máximo de
caracteres: ocho en unitbase localizado y cinco en NPC/ex_binder.

Los 385 nombres SSD3019 también son constantes terminadas y caben en memoria.
Se detectó un caso de presentación específico: Spark `¿Sra. Hob.?`, once
glifos y 59 píxeles de tinta, que conservaba dos filas bajo el primer umbral80.
No se abrevia ni elimina el signo. La solución final usa el umbral134,
`14*(8+1)+8`, que cubre los quince glifos admisibles por la capacidad real,
manteniendo la guardia previa al dibujo independiente y el ancho físico64.
Así no se introduce otro tope arbitrario de nueve caracteres y el caso real
se muestra en una sola fila en el modelo. Todas las entradas actuales tienen
como máximo quince glifos y 64 píxeles de tinta; esto no sustituye comprobar
el origen colocado en ejecución. Los ejemplos W de siete a nueve letras
superan la región64 y se marcan explícitamente como **negativos visuales**, sin
recortar su raster ni declarar que caben porque los admita el contador lógico.

Pruebas focalizadas finales después del cambio del renderer, límite134 y API:
**121 passed**, incluido CRO local; lint correcto. Se incluyen los límites
lógicos134/135, ¿Sra. Hob.? y nueve W como negativo visual.
FONT8 leída sin escrituras, SHA-256
`53a6a8a8c36c74a205749847ed686659b721fcf35170099923e17f22d97cecbb`.

La auditoría está integrada en la API reutilizable
`presentacion_nombres.auditar_presentacion(archive, fuente_FONT8)`; no importa
un CLI ni escribe archivos. El script de trabajo solo invoca esa API y emite
los diagnósticos. La función exige que la FONT8 suministrada coincida byte a
byte con la del archivo, comprueba los cinco recursos completos y todos los
3019 de ambos perfiles, y rechaza entradas no constantes, campos sin NUL,
glifos sin modelar, más de quince comandos o tinta mayor que 64 píxeles.
La repetición sobre los datos reales mediante esta API obtuvo exactamente
8.770 filas y 385 nombres SSD3019. Su informe mantiene explícitamente
`runtime_verified=False`: el origen nativo y la pestaña requieren prueba visual.
