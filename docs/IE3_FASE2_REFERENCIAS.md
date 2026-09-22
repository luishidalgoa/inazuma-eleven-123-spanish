# IE3 Fase 2: referencias del consumidor y piloto de tamaño variable

**Actualización fase 3:** el usuario aprobó el caso individual del piloto en
ejecución y autorizó la activación general. La espera descrita abajo es histórica,
no un bloqueo vigente. La nueva candidata no hereda validación de campañas:
ver [integración fase 3](IE3_FASE3_INTEGRACION.md).

## Estado y alcance

19-09-2026. La legibilidad de v7 fue aceptada **solo para los casos probados por
el usuario**. Esta fase no modifica fuentes, glifos, métricas, centrado, encoder,
È, wrapping, dimensiones ni paginación. No reactiva `--crecer`. La nueva ruta
es `python -m ie123kit.ie3.fase2`, compartida por perfiles Spark/Ogre.

El piloto debe probarse antes de activar el corpus entero. Las simulaciones
offline no son QA en juego. No se ejecutan entradas de emulador durante la prueba
manual. Los artefactos y textos oficiales quedan en `work/`, fuera de Git.

## Corrección de las hipótesis históricas

Las cadenas `@offset,longitud` **no representan coordenadas visuales**. Son el
enlace entre `eve` y `evet`. Las descripciones anteriores en la bitácora se
conservan como historia, pero esta evidencia del consumidor las sustituye.
`0x301A` no se modifica ni se trata como un offset.

La reinserción conservadora puede redistribuir tamaños **interiores** de un
grupo ruby. Conservar tamaño total y cantidad no prueba igualdad de cada offset
interior: un nuevo test con kana real lo demuestra. La nueva ruta conserva todos
los secundarios literalmente y mantiene un mapa de **cada** registro.

## Binario y cadena real de carga

Binario original: `work/shared/base_3ds/romfs/cro/ina_main3ogre.cro`.
SHA-256 `280e423a5957ea5394de359fb37e2945c2e88856b7b45b8b63cb287be6193ff0`.
Tamaño 3.481.600 bytes. El nombre no implica que sea exclusivo de Ogre: el
cargador JP selecciona el recurso a través de su contexto, y los paquetes reales
Spark y Ogre se validan separadamente con el mismo consumidor.

Todas las direcciones siguientes son **offsets de archivo CRO**, no VA.
La sección de código empieza en `0x180`: RVA de código = offset − `0x180`.
No se extrapolan direcciones de los ejecutables europeos.

1. `0x408A8` carga un evento. `0x186AF8` busca su ID `u32` en las entradas
   PackNum tipo 0 de 12 bytes. `0x186BF4` devuelve el offset del bloque PKB
   (`entry+4`); `0x40A38` lo guarda en el contexto (`+0x1E0`).
2. `0x40A10/14` fija la ruta del recurso (`context+0x16C`). La tabla
   `0x29EB8C/90` selecciona `evet.pkb` o `mcht.pkb`; esta emisión se limita a
   eventos `eve/evet` comprobados, no altera consumidores de otros recursos.
3. Dispatch `0x4768C–0x476AC`: índice opcode−`0x3001`, tabla `0x29EBE0`,
   stride 8. `0x301D` llega mediante `0x29ECC0` al handler `0x4F05C`.
4. El handler obtiene el operando 0 (`0x4F0B8`), comprueba `@` (`0x4F0C4`),
   lee dos decimales (`0x4F0D0–0x4F110`) y suma el primero a la base del evento
   (`0x4F11C–0x4F120`). **Offset y longitud se miden en bytes**; origen del
   primer campo: inicio del bloque evet, no inicio del archivo ni del SSD.
5. `0x4F134 → 0x267A68`: `FS_SeekFile` SET en `0x267ACC` (thunk 478),
   `FS_ReadFile(buffer,longitud)` en `0x267ADC` (thunk 480).
6. `0x4F150–0x4F19C` recorre argumentos. **Solo tipo 3** consume registros.
   El texto empieza en `record+4` (`0x4F180`); el cursor avanza por el tamaño
   total `u8 record+3` (`0x4F188–0x4F18C`). El primer registro reemplaza el
   argumento `@`; los siguientes son argumentos de texto, no necesariamente ruby.
7. `0x4B424` expande controles/ruby, `0x32EBC` realiza wrapping; el handler espera
   al cierre de la ventana (`0x4F1E4–0x4F208`). **Cada instrucción vuelve a
   resolver su propia referencia**; no depende de un cursor persistente entre
   diálogos. De ahí que crecer evet sin corregir todos los `@` posteriores fallase.

El test `test_ie3_consumidor_fase2.py` fija hash y ocho instrucciones ARM
independientes del lector/escritor, incluyendo seek, read, suma de bases,
tipo de operando y avance. No es una prueba de ejecución en emulador.

### Enlace SSD y tipos

SSD v3 `0x00030001`, cabecera 32 bytes. `+0x10` es longitud de código;
`+0x0C/+0x0E` son contadores consumidos como **signed16**, máximo 32767.
ID de instrucción: patrón `u16`, enlazado con comparación signed16; no se deduce
de ello que los IDs deban ser menores de 32768. Se conserva cada ID.

Instrucción: cabecera 8 bytes, argc `u8 +6`, un nibble por tipo y
`ceil(argc/8)` palabras de tipos, seguidas de argc palabras de operandos.
Tipos 1/2: literal; 3: texto; 4: ID de instrucción; 5: valor de variable;
6: dirección de variable. Para 5/6 hay bits de contexto y un índice low16.
No se reescribe ninguno de estos operandos.

El loader `0x164814–0x1648BC` enlaza los textos por los campos de su cabecera
`(u16 ID de instrucción, u8 slot físico)`. **No por el entero placeholder** del
operando. Slot físico = `ceil(argc/8)+índice_argumento`, no siempre `arg+1`.
Esto se prueba con nueve argumentos y valores placeholder deliberadamente falsos.

El loader enlaza puntero directo (`0x164868/74`), no añade NUL. Hay referencias
oficiales sin NUL cuando sus bytes llenan exactamente el registro. El parser
decimal termina al primer byte no decimal (`0x4F0D4–DC`, `0x4F0F8–100`). Para
aceptarlas se exige que el siguiente byte **exista dentro del SSD y no sea
`0x30..0x39`**; se comprueba también después de reconstruir. Toda referencia nueva
se emite con NUL. Otros textos técnicos originales se conservan literalmente.

### Límites del consumidor: no son el presupuesto japonés

| Elemento | Límite y tratamiento |
|---|---|
| Registro | tamaño total `u8`, alineado 4, máximo 252; cuerpo nuevo ≤247 bytes + NUL |
| Lectura de grupo | buffer de 1024 bytes; no basta con que la suma quepa en evet |
| Argumentos | 32 palabras; tipo 3 consume exactamente un registro |
| Texto expandido | temporal 640, seguido de buffer nominal 512; exigir expansión+NUL ≤512 |
| Ruby | 16 entradas de 42 bytes; texto desde +0xA, ≤31 bytes + NUL |
| Sustitución `%s` | temporal 32 bytes; requiere demostrar cota dinámica ≤31 + NUL |
| Colores `%C` | tabla 16, incluida entrada inicial: ≤15 cambios |
| SSD | contadores signed16; registros de tabla también u8/alineados4 |

No se han ampliado constantes del motor. La ruta de contenido del piloto solo
emite traducciones sin controles `%` pendientes. Ruby JP se conserva como
registros secundarios no utilizados si el ES no lo pide. Se conservan literalmente
los controles de los mensajes no modificados. `\n` y `\f` llegan como 0A/0C al
expansor; **no se ha demostrado que `\f` por sí solo gestione una página real**.
El layout aprobado sigue rechazándolo. Resolver paginación o expansión dinámica
requiere trabajo posterior; no se inventan instrucciones ni se suprimen controles.

## Reconstrucción mínima implementada

- `perfiles`: revisión y hashes compatibles, recursos, fuente oficial, corpus,
  alineación y grupo compartido. Sin rutas personales ni IDs del piloto embebidos.
- `cobertura`: diagnóstico conservador con denominador histórico explícito,
  ambigüedades, contradicciones, encoding/layout y presupuesto heredado separados.
- `fase2.resolver/compilar`: identidad original, reextracción ES real mediante
  CodeTable, memoria unívoca curada, controles y configuración congelada.
- `referencias`: lee los consumidores reales, valida límites/propietarios,
  reconstruye los registros sin encogerlos, conserva secundarios y huérfanos,
  calcula mapa origen→destino y reescribe solo las cadenas `@` afectadas.
  Actualiza longitud de tabla/tamaño SSD, no su bytecode ni conteos/IDs.
- `paquetes`: usa el reconstructor PackNum existente con compresión detectada
  **por entrada**, conserva bytes comprimidos de todos los eventos ajenos y
  reextrae todos los bloques. El round-trip sin cambios retorna bytes originales.
- `piloto`: selecciona explícitamente hasta cinco claves, detecta conflictos con
  la referencia actual y comprueba todas las entradas B123 antes/después.
- `build_piloto`: reutiliza `build_3ds`, superpone el **CRO exacto de v7**, genera
  una ROM completa y vuelve a extraer archive/CRO/ExeFS y todo el inventario B123.

### Particularidades PackNum demostradas

Se limita la escritura a tabla tipo 0 (`u16 +0x12`). Se conserva la cabecera opaca,
incluido `+0x20` (máscara de conversión nombre→ID) y `u16 +0x24` (longitud),
que **no son padding universal**. No se generaliza `u32 +0x10` como tamaño para
tablas de otro tipo; en estos índices tipo 0 el tamaño cabe en low16.

`u16 +0x16` cuenta entradas reales. Tras ellas hay una cola FF de **0/4/8/12
bytes**, no siempre una tripleta completa. Se conserva exactamente la cola de
entrada, el conteo y los metadatos. Así no se interpreta FFFFFFFF como un bloque
ni se pierden colas parciales. Algunos intermedios conservadores anteriores ya
no tienen la cola parcial original; el piloto preserva su referencia literal.

Offsets de bloques alineados a 16. `u32 +0x1C` se recalcula como
`align16(max tamaño ALMACENADO)`, demostrado en los ocho pares JP/ES:
Spark JP eve 29824 (máximo descomprimido 85124), Ogre JP eve 33632 (98060).
La reserva descomprimida de esta ruta procede de la cabecera LZ10, no de +1C;
no se afirma un overflow de ese buffer por el antiguo máximo desactualizado.

Todos los eve actuales usan LZ10 y todos los evet son crudos, pero se detecta
por entrada y se rechaza una compresión ambigua. Hay entradas evet vacías
oficiales, que se conservan. No se asume que IDs u offsets coincidan entre idiomas.

## Correspondencias, denominadores y recursos compartidos

La clave de diagnóstico es `perfil:evet:evento:offset_original_hex`. La instrucción
consumidora, hash del grupo JP, fuente ES y CSV quedan en cada fila. La clave
antigua `(evento,texto JP)` contiene traducciones distintas para mensajes que se
repiten: no se usa «última fila gana». Los conflictos se resuelven por alineación
de identidad fiable y reextracción oficial; si no es posible, quedan pendientes.

Los informes mantienen **ambos denominadores**: cabezas de `group_ruby` legado y
consumidores reales 301D. También inventarían diálogos inline, entradas sin eve,
registros huérfanos y recursos ausentes. No se ocultan para mejorar porcentajes.
`messages.json` contiene todos los pendientes con clave y causa; `exceptions.json`
y `unreferenced.json` completan el inventario fuera de las referencias ordinarias.

Hay 5 diálogos inline por perfil JP (evento 35010300): preservados, aún sin plan
de correspondencias. En Ogre JP el evento 90000002 tiene tres referencias a
evet ausente: se documenta el evento completo, no se reconstruye. Los secundarios
no son todos ruby: existe, por ejemplo, un argumento ES para sustitución de color
en Ogre 39010000. No se vacían por posición ni por parecido.

MCSFILE de Bomber redirige scripts a `inazuma3/data_iz/script`, compartido con
Spark. Modificar esa entrada puede afectar Bomber; **procesar Spark no declara
Bomber traducido ni probado**. Solo se cambia el mensaje seleccionado. Para
integrarlo después se requiere perfil JSON, revisión/fuente oficial Bomber,
corpus y alineación por identidad, reextracción de origen y resolución explícita
de contradicciones con el manifiesto ya aplicado. No se presupone orden, IDs ni
contenido iguales. La selección piloto rechaza sobrescribir un mensaje ya
modificado en vez de decidir silenciosamente qué traducción prevalece.

## Comandos reproducibles

Desde la raíz, con ie123kit instalado:

```powershell
python -X utf8 -m ie123kit.ie3.fase2 auditar --perfil spark --salida work/ie3/shared/fase2/plan_spark_emision
python -X utf8 -m ie123kit.ie3.fase2 auditar --perfil ogre --salida work/ie3/shared/fase2/plan_ogre_emision
python -X utf8 -m ie123kit.ie3.fase2 piloto --perfil spark --plan work/ie3/shared/fase2/plan_spark_emision --referencia work/ie3/rayo_celeste/candidatas/spark_conservadora_v7_celdas_centrado_pendiente_validacion_visual.fa --clave spark:evet:32500100:00000064 --salida work/ie3/rayo_celeste/candidatas/spark_fase2_piloto_referencias
python -X utf8 -m ie123kit.ie3.comun.build_piloto --candidate work/ie3/rayo_celeste/candidatas/spark_fase2_piloto_referencias --visual-manifest work/ie3/rayo_celeste/candidatas/spark_conservadora_v7_celdas_centrado/manifest.json --rom work/build/inazuma123_spark_fase2_piloto_referencias_pendiente_validacion_visual.3ds
```

Se rechazan salidas existentes; para repetir usar otra carpeta, sin sobrescribir
originales. El plan fija hashes de fuentes/código; si cambian se debe auditar de
nuevo, no editar el manifiesto para saltarse la protección.

Ogre usa exactamente la misma auditoría y selección por `--perfil ogre`; no se
genera una ROM Ogre antes de probar el piloto Spark. No hay modo de activación
masiva expuesto en esta etapa.

## Prueba manual del piloto

1. Cerrar completamente Azahar. Desactivar cualquier mod/LayeredFS del título;
   **no borrar** mods ni partidas. Abrir la ROM indicada, no otra con nombre parecido.
2. Arranque limpio, sin cargar un savestate creado con otra build. Entrar en Spark
   e iniciar el prólogo italiano por la vía habitual de prueba.
3. Tras la introducción, leer la primera intervención de **Maserati**, dirigida
   a Bianchi/Paolo. Debe aparecer completa en español, desde `¡Madre mía!` hasta
   `mañana!`, en tres líneas con el wrapping actual. Es el único mensaje nuevo.
4. La respuesta inmediata de Bianchi debe seguir como estaba en v7 (japonés).
   No debe mostrar otro mensaje, perder bytes iniciales ni colgarse al avanzar.
5. Continuar por la calle: diálogo de `¡Bravo, Paolo!`, textos cortos, escena del
   puente y siguiente evento. Comprobar inicio/final, saltos, cajas vacías,
   `¡`, `¿`, tildes, `ñ`, `È` cuando aparezcan y que la tipografía no cambie frente a v7.
6. Guardar capturas de la intervención completa, respuesta y siguiente evento;
   indicar cualquier salto, lectura equivocada, corte o cuelgue. El piloto no
   contiene una nueva implementación de páginas: no atribuirle esa validación.

Se espera el resultado del usuario antes de la activación masiva o de abrir otra
investigación amplia. Los defectos visuales residuales de v7 siguen pendientes.

## Resultado generado y cifras recalculadas

ROM completa: `work/build/inazuma123_spark_fase2_piloto_referencias_pendiente_validacion_visual.3ds`.
Etiqueta: **Spark Fase 2 — piloto de referencias — pendiente de validación visual**.
Tamaño: **2.147.483.648 bytes**. SHA-256:
`967107bd55f8f6bb18df896f2564296f0b908163d5fe12a6027cacaad7644e79`.

Manifiestos en `work/ie3/rayo_celeste/candidatas/spark_fase2_piloto_referencias/`:

- `manifest.json`: ROM, referencia visual, CRO, ExeFS y comprobación reextraída.
- `pilot.json`: selección, procedencia ES, mapa de cada registro, inventario/hash
  de las 15.547 entradas B123 antes/después y las cuatro entradas modificadas.
- `qa.json`: conteo real, 14.616 pendientes intactos con clave, 14 originales ya
  idénticos al ES y las 23 alertas de identidad heredadas de v7.

El archive mide 1.342.090.592 bytes, SHA-256
`9a0ce8e332503e6a38d3432bb7abccc55a00cd63d77801056db1b3307e2f3005`.
Dentro de la ROM se verificaron el archive completo, todas sus entradas, el CRO
v7 `1c2db0af506077b1e94f1faa83859643cb35ca68ee0665db6872d811580f3061`
y ExeFS original. **No hay una nueva prueba de ejecución ni validación visual**.

### Inserción real del piloto, distinta de la simulación

Una inserción nueva. Respecto a v7: 1 registro de texto cambiado y **102.418
registros byte-idénticos**; siete referencias actualizadas; bytecode sin cambios.
Cinco archivos de configuración/encoder/tipografía y seis entradas de fuente
coinciden con el manifiesto de referencia. Rechazados intactos: **14.616**.

Se han reextraído 19.471 cuerpos traducidos que difieren del JP (**57,098 %** del
denominador legado de 34.101). Hay otros 14 cuyo original ya es idéntico al ES:
la métrica compatible con el informe conservador anterior es **19.485/34.101 =
57,1391 %**. No se cuentan esos 14 como inserciones nuevas. Esta cifra incluye
23 traducciones heredadas del antiguo cruce que **no coinciden con la identidad
ahora resuelta**, listadas en QA; no equivale a 19.485 correspondencias definitivas
ni a mensajes probados en juego. Se han preservado para aislar este piloto.

### Plan offline, no activado en la ROM

| Métrica | Spark | Ogre |
|---|---:|---:|
| Grupos originales legado | 39.189 | 40.852 |
| Traducciones disponibles legado | 34.101 | 36.749 |
| Consumidores `@` JP válidos | 39.145 | 40.801 |
| Disponibles sobre consumidores reales | 34.100 | 36.705 |
| Correspondencias oficiales reextraídas | 34.100 | 36.703 |
| Emitibles y reextraídos en simulación | 31.362 | 33.711 |
| De ellos requieren crecer su registro principal | 18.795 | 19.888 |
| Pendientes por controles/argumentos | 2.688 | 2.936 |
| Pendientes por encoding | 41 | 47 |
| Pendientes por layout/páginas | 9 | 9 |
| Emparejamientos elegibles sin confirmar | 0 | 2 |
| Correspondencias ausentes / ambiguas | 1.605 / 3.440 | 1.758 / 2.338 |
| Diálogos JP inline inventariados aparte | 5 | 5 |
| Registros huérfanos preservados | 7 | 6 |

El plan representa 91,9707 % / 91,8431 % del denominador de consumidores con
traducción disponible. Sobre el denominador legado, sin alterarlo silenciosamente:
**91,9680 % / 91,7331 %**. No son porcentajes insertados en la ROM piloto.

Informes definitivos: `work/ie3/shared/fase2/plan_{spark,ogre}_emision/`:
`manifest.json`, `messages.json`, `summary.json`, `exceptions.json`, `unreferenced.json`.
Los `diagnostico_{spark,ogre}` fijan el diagnóstico conservador previo; los planes
anteriores `plan_spark`, `plan_*_final` son resultados intermedios, no el plan
utilizado para construir. No se deben confundir sus hashes de código.

Claves destacadas de cobertura y pruebas:

- Rechazo binario pequeño: `spark:evet:31200000:000002AC`.
- Rechazo binario grande: `spark:evet:36171508:00000000`.
- Ruby múltiple y prólogo real: `spark:evet:32500100:00000064` (piloto).
- Páginas no emitidas: `spark:evet:35090501:00000000`. Hay nueve casos explícitos;
  no se borran páginas ni se transforman en una sola caja.
- Ogre sin confirmar: `ogre:evet:36134726:000004B0` y
  `ogre:evet:36134727:000004B0`.
- Recurso evet ausente en Ogre: `ogre:eve:90000002:319` (`@0,144`),
  `ogre:eve:90000002:320` (`@144,40`),
  `ogre:eve:90000002:332` (`@184,76`). No se emite ese evento.

### Pruebas y guardias ejecutadas

```powershell
python -X utf8 -m pytest tools/tests -m "not requiere_rom" -q
python -X utf8 -m pytest tools/tests/requiere_rom/test_ie3_consumidor_fase2.py tools/tests/requiere_rom/test_ie3_tipografia_oficial.py -q
python -m ie123kit.nucleo.compat.guardia bloqueados
python -m ie123kit.nucleo.compat.guardia git
python -m ie123kit.nucleo.compat.shims comprobar
python -X utf8 work/ie3/shared/fase2/verificar_piloto.py
```

Resultados: **1.098 passed**, 15 pruebas ROM excluidas de esa ejecución, 8 subtests;
las **3 pruebas locales seleccionadas passed**. Las 20 pruebas de referencias
están incluidas en la batería general. Cubren principio/medio/final, posteriores,
multibyte, controles sin transformación, ruby real, 9 argumentos, placeholders
falsos, referencias compartidas, solapes inválidos, NUL/terminador decimal,
límites, colas PKH y entradas vacías. El test de ruta antigua deshabilitada se
mantiene. Lint de todos los módulos/pruebas nuevos: pasa.

Guardias: cinco congelados y SOURCE_HASHES correctos; 641 ficheros rastreados,
0 prohibidos; 31 shims sin lógica. Round-trip literal: ocho pares PKB/PKH y
11.669 eventos de los cuatro perfiles JP/ES. No se hizo push, publicación, PR,
ni se borraron originales. Solo se limpiaron los temporales internos del builder
y de la reextracción, regenerables automáticamente; v7 sigue disponible.

Aviso de higiene preexistente: `git diff --check` sigue señalando una línea vacía
al final de `comun/reinsert.py:284`, además de avisos LF/CRLF de Git. No se tocó
ese archivo para conservar su hash de referencia. No es un fallo de las guardias
ni de la ROM; tampoco se presenta el diff global como limpio.
