# Explicaciones Codex

## 2026-09-19 — Reinserción IE3 y candidata Spark

**Problema.** La rama de trabajo exponía `--crecer` para ampliar registros de
`evet`, aunque las pruebas de Spark documentadas en `docs/IE3_TRASPASO.md` y
`docs/IE3_RE_DIALOGO.md` muestran que desplazar registros hace que el motor lea
el diálogo con bytes iniciales perdidos.

**Hechos confirmados.** `0x301D` se correlaciona con los diálogos; `0x301A`
configura la caja y su argumento 2 no es un offset a `evet`. Los slots SSD que
se consideraron para recolocación son lecturas furigana. Por tanto, la antigua
correlación de 0x301A con offsets era espuria. La rama
`origin/estado-ie2-cajas` ya es ancestro de `HEAD`; su patrón de validación es
útil, pero sus estructuras no se trasladan sin verificar.

**Decisión.** Solo se permite la reinserción que conserva el tamaño total de
cada grupo diálogo+lecturas, el número de registros y todos los offsets. Se
deshabilita `--crecer` y se elimina la lógica de recolocación desmentida. Los
objetivos y nombres de sitio de los opcodes IE3 ya identificados siguen usando
la tabla SSD, que actualiza tamaños de cabecera y se vuelve a parsear.

**Riesgos y alcance.** Esto no elimina el límite de cobertura: las líneas que
no caben en su grupo continúan en japonés, sin truncarlas. Tampoco prueba aún
el experimento de slots ni modifica Bomber, menús o descripciones. Para una
candidata Spark reproducible, la salida debe pasar el verificador de offsets,
las validaciones del pack y después una prueba de los primeros 2–3 minutos.

**Validación prevista.** Pruebas sintéticas de invariantes, parser SSD/PKH y
guardias del toolkit; la validación visual pendiente comprobará ancho, tres
líneas, acentos y la división de diálogos del prólogo.

**Resultado.** Las pruebas nuevas verifican que la reinserción mantiene tamaño,
número de registros y offsets de inicio. La suite completa y las guardias se
ejecutan al cierre de esta sesión; la validación en emulador/consola sigue
pendiente y no se presenta como resuelta.

## 2026-09-19 — Evidencia oficial y reconstrucción futura

La comparación Spark JP ↔ Rayo ES confirma que la oficial no conserva `evet`:
2.451/2.846 eventos comunes cambian su número de registros; globalmente pasa
de 102.413 a 39.064. `0x301A` se conserva en los casos analizados, mientras
`0x301D` se recompila al retirar ruby. El crecimiento aislado no sirve, pero
esto no prueba que el motor no admita crecimiento: demuestra que requeriría
reconstruir coordinadamente `evet`, `0x301D` y PackNum. El encoding ES oficial
no es directamente reutilizable, pues sus acentos/signos usan bytes distintos
de `sjis_portador`.

La hipótesis queda inconclusa hasta identificar el cargador/índice real. No se
habilita crecimiento. Además se corrigió `packnum.rebuild`: el centinela PKH se
conserva literal y ya no degrada el alineado automático.

## 2026-09-19 — Cadena Unicode → SJIS-portador → fuente en Spark v2

**Observación.** La primera ROM conservadora arrancaba y mostraba el cuerpo
español, pero `¡`, `ú` y otros caracteres aparecían como símbolos griegos. Los
textos rechazados por presupuesto que continúan en japonés son otra categoría:
son esperados y no se confunden con un texto español renderizado mal.

**Evidencia y descarte.** `sjis_portador` transforma `¡` en U+039E y lo guarda
como `83 AC`; `ú` pasa a U+0395 y `83 A3`. Es la salida histórica esperada. Se
descartan como causa el Unicode fuente, el encoder y el wrapping. La candidata
v1 contenía fuentes JP, no el resultado de `font_patch`; por eso el motor
pintaba el glifo griego original al encontrar esos codepoints.

**Solución limitada.** El pipeline aplica el `font_patch` congelado a fuentes
JP verificadas y las reinserta sin cambiar tamaño, métricas, espaciado ni caja.
La cadena correcta es: Unicode `¡` → U+039E → bytes `83 AC` → CMAP U+039E de
BCFNT → glifo `¡` parcheado. La referencia v106 no se copió a ciegas: sus
hashes coinciden con el parche reproducible desde las fuentes originales.

**Validación.** `python -m ie123kit.ie3.comun.charset ARCHIVE` comprueba el
charset mínimo, bytes, CMAP e igualdad byte a byte contra el parche esperado
en FONT12, FONT12T y FONT8. Se ejecutó sobre la candidata y sobre `archive.fa`
extraído del `.3ds` final. La validación visual de la baseline v2 sigue
pendiente antes de retomar cualquier crecimiento estructural.

## 2026-09-19 — Layout de Spark: maquetador y CRO no viajaban juntos

**Evidencia.** El registro final de `32500100` guarda literalmente
`Unos meses antes, en cierto lugar de\\nItalia...`: el salto está antes de
`Italia`, no entre `c` e `ierto`. El caso de `¡Bravo, Paolo!` también está
maquetado con salto explícito antes de `en tus botas`. Por tanto los cortes
visibles a 22 caracteres no los introdujo el encoder ni la candidata.

**Causa demostrada.** `maqueta.py` calcula 42 caracteres por línea usando
`ancho_ventana.ANCHO = 0x1E0`, pero la build v2 solo superpuso `archive.fa`.
No incluyó el `cro/ina_main3ogre.cro` que `ancho_ventana.parchear` verifica y
prepara. La ROM ejecutaba el valor JP de fábrica, 0xF0: `(0xF0 + 0x20) / 12`
deja 22 caracteres y reproduce exactamente los cortes observados.

**Decisión y riesgo.** No se cambia el wrapping, las fuentes ni el encoder.
Se integrará el CRO ya analizado como overlay explícito del candidato, pasando
sus comprobaciones de instrucciones, contexto y tablas de reubicación. La ROM
se construirá mediante `nucleo.construir.rom.build_3ds`, que superpone archive
y CRO sobre una copia temporal del RomFS; así se evita alterar la base. Queda
pendiente la comprobación visual de que el ancho ampliado y la rejilla de dibujo
se aplican juntos en esta build, aunque el diagnóstico previo documenta la misma
sonda en IE3.

## 2026-09-19 — Nombres de hablante y carácter `È` en la baseline v3

**Nombres.** Se sustituyó la excepción aislada de Bianchi por una localización
conservadora de nombres cortos de `unitbase.dat`. Cada registro IE3 se identifica
por su huella estructural entre JP y ES; solo se copia el campo corto de 16 bytes
cuando el nombre oficial es codificable y cabe. El campo largo y el resto del
registro no se tocan. El resultado aplica 2.345 correspondencias oficiales; 11
registros se descartan por estructura no equivalente, 2 por codificación y ninguno
por tamaño. No se afirma cobertura de IDs que no pertenezcan a esta tabla.

**`È` no se confunde con `¿`.** En `32500100`, el texto oficial comienza con
`È`; su CodeTable ES usa el byte `D8`. El charset portador de la candidata no
tiene una ruta aprobada para U+00C8 y lo guarda como `3F` (`?`). Hay 66 apariciones
de seis caracteres italianos fuera del plan de fuente vigente. No se hace una
sustitución global ni se modifica el parche de fuentes congelado: la incidencia
queda explícita para una decisión posterior, y la baseline no se marca verificada.

**Resultado mecánico v3.** La candidata ejecutable superpone tanto `archive.fa`
como el CRO verificado. Sus PKB/PKH y 6.980 SSD se recorrieron sin error; los
offsets de los 39.189 diálogos Spark y 40.852 Ogre se conservaron. Los casos de
texto largo del prólogo están completos en el bloque y el centinela de Bianchi se
comprobó en la salida. Falta exclusivamente la validación visual del usuario.

## 2026-09-19 — Decisión previa: tipografía europea para Spark v4

**Evidencia.** La comparación CWDH demuestra que el cuello visual no es solo el
wrapper. Con `FONT12` JP parcheada, la narración inicial mide 329 px y el
diálogo de Paolo 371 px; con `FONT12` europea miden 239 y 270 px. `Generani`
pasa de 66 a 49 px. La candidata guarda íntegros los textos y sus controles,
por lo que el espaciado y el desbordamiento del rótulo nacen al dibujar con las
métricas/raster latinos JP, no durante la alineación ni la reinserción.

**Solución elegida.** Se conservará la fuente JP como contenedor y todos sus
glifos japoneses, pero `FONT12` recibirá raster y CWDH latinos de la fuente
oficial europea, trasladados por codepoint/CodeTable y alineados por baseline.
El parche congelado no se modifica: la adaptación IE3 se aplica después mediante
un módulo separado y verificable. `È` usará U+03A0 como portador; el byte `83AE`
no aparece en ningún registro de texto JP de IE1/IE2/IE3/Ogre y el glifo existe
en las fuentes destino.

**Límite lógico.** El wrapping proporcional con las métricas europeas, aplicado
a las 34.691 traducciones Spark elegibles, produce como máximo 51 caracteres en
una línea de hasta 354 px. De ahí se derivan `ANCHO=0x250` y `REJILLA=0x270`;
no son valores afinados para los dos ejemplos. Las tres líneas por caja, el
presupuesto binario, los offsets y el rechazo conservador permanecen intactos.

**Riesgo y prueba prevista.** La fuente europea tiene otra geometría de celda;
solo se trasladarán los glifos compatibles de `FONT12`, ajustando un píxel por
la diferencia de baseline y sin cambiar el tamaño del BCFNT. Se probarán hashes,
métricas, raster, `È`, los cuatro casos del prólogo, offsets, PKB/PKH/SSD y las
guardias antes de generar una única build pendiente de validación visual.

**Resultado.** La adaptación escribió 111 glifos/métricas latinos en `FONT12`
sin cambiar sus 1.031.724 bytes. El caso A queda almacenado en una sola línea;
el caso B conserva el salto oficial antes de `en tus botas`; y el caso C empieza
por `83 AE`, que se decodifica como `È`, no como `?` ni `¿`. Los cinco nombres
muestreados del prólogo pasan de 53–66 px a 26–50 px y coinciden con sus avances
oficiales. Los caracteres todavía no soportados ya no usan fallback: la ruta
conservadora rechaza esas líneas y mantiene el japonés original.

La cobertura final es 19.484/34.101 diálogos Spark (57,14 %), con 14.617
rechazos intactos. `unitbase.dat` examinó 2.581 fichas: aplicó 2.345 nombres,
descartó 11 por estructura, 2 por encoding y 0 por tamaño; 223 ya coincidían.
La ejecución visual sigue pendiente: la evidencia estática demuestra bytes,
métricas y layout generado, no el resultado observado en consola/emulador.

## 2026-09-19 — Decisión previa: recalibración posterior a Spark v4

**Observación visual y alcance.** La prueba de v4 confirma que la dirección era
correcta, pero no el trasplante literal: el cuerpo ya entra, aunque sus letras se
perciben demasiado juntas o recortadas, y el nombre conserva separación excesiva.
La `È` es la letra correcta y participa en el mismo defecto; no se reinterpreta
como `¿`. La idea de buscar un «punto intermedio» se trata solo como hipótesis.

**Evidencia del cuerpo.** FONT12 JP tiene celdas 15×16 y baseline 13; la oficial
europea, 14×17 y baseline 14. V4 sustituyó a la vez raster, left/glyph width y
avance, pese a que pertenecen a geometrías distintas. El extremo JP mide 329/371
px en los casos A/B y el trasplante v4, 239/270 px. La corrección no promediará
ambos extremos: conservará el raster JP ya legible y calculará para cada carácter
el menor avance que respeta tanto el avance oficial como la extensión declarada
del glifo JP (`max(avance_ES, max(0,left_JP)+glyphWidth_JP)`). Así se elimina la
incompatibilidad raster/CWDH sin volver al exceso JP. `È` conservará U+03A0/83AE,
pero su raster se construirá desde la `E` JP con acento grave y recibirá la misma
métrica derivada, en lugar de trasplantar una celda europea.

**Evidencia del nombre.** Los 16 bytes de `Bianchi` son idénticos en la candidata
y la edición europea (`4269616e636869...`), por lo que el problema no está en
`unitbase.dat`. El manejador JP de 0x301A y su homólogo europeo son instrucción por
instrucción equivalentes en esta ruta; desde 0x04F4B8 llegan al configurador y a
la misma familia de dibujado que la ruta FONT8 ya documentada en IE1. FONT12 v4
no podía afectarla. FONT8 dibuja la pestaña a paso fijo de 10 px: cambiar CWDH no
resuelve el rótulo. Se reutilizará la técnica de bigramas ya validada en IE1, pero
de forma general: un plan determinista elige los pares más frecuentes del conjunto
oficial de nombres, los dibuja en portadores griegos/cirílicos libres de FONT8 y recodifica
solo el campo corto. No habrá excepciones por frase ni por personaje; el campo
sigue midiendo 16 bytes y los registros siguen inmutables fuera del nombre.

**Riesgos y validación prevista.** Los bigramas solo son válidos para la ruta
FONT8 confirmada y no deben filtrarse al cuerpo. Se verificará que sus portadores
no colisionen con los 16 ya reservados para español/`È`, que el raster compuesto
quepa en la celda, que los nombres obligatorios reduzcan celdas y que el resto de
`unitbase.dat` no cambie. Para el cuerpo se comprobarán contención métrica, casos
A/B/`È`, hashes y ausencia de truncamiento. Después se ejecutarán toda la suite,
verificadores SSD/PKB/PKH, offsets y guardias antes de crear una única candidata
pendiente de validación visual.

**Resultado.** La hipótesis del punto intermedio queda sustituida por una regla
de contención. El caso A pasa de 329 px (JP) / 239 px (v4 y oficial) a 272 px; el
caso B, de 371 / 270 a 311 px. El nuevo valor no es la media: es la suma de los
mínimos seguros por glifo. Ambos siguen dentro de 354 px y conservan los saltos
oficiales. FONT12 mantiene todo su raster JP salvo el nuevo grave construido sobre
`E`; el registro de `32500100` comienza por `83 AE` y se decodifica como el
portador de `È`.

El plan de nombres utiliza los 96 pares ASCII más frecuentes y 96 portadores
griegos/cirílicos que no solapan los 16 de español/`È`. Compacta 2.223 de los
2.345 nombres aplicados mediante 4.160 pares. En la ruta fija de 10 px, `Bianchi`
pasa de 7 a 5 celdas, `Generani` y `Maserati` de 8 a 5, y `Diavolo` de 7 a 6.
Los bytes ocupados por cada par siguen siendo dos, así que el campo corto conserva
sus 16 bytes y no altera ningún otro campo del registro.

La ROM v5 se generó, pero permanece **pendiente de validación visual**. El archive
extraído de la ROM coincide con el intermedio (`16620b49…`) y el CRO con el parche
de ventana (`1c2db0af…`). Pasaron 1.036 tests, 6.980 SSD, 5.824 tablas evet,
dos centinelas PKH, 80.041 offsets sin movimiento, 19.484 inserciones completas,
14.617 rechazos intactos y cero truncamientos. Esto valida estructura y métricas;
la legibilidad real y el aspecto de los bigramas siguen dependiendo de la prueba
en emulador/consola.

## 2026-09-19 — Decisión previa: corrección fina posterior a Spark v5

**Evidencia visual y binaria.** Las cinco capturas de v5 separan dos defectos.
En FONT12, secuencias como `ci/ie/rt/to`, `It/ta/li/ia`, `ol/lo`, `fú/út`,
`rr/ri/ib/bl` y `ll` pierden separación o trazos. El recurso final contiene los
strings completos y exactos; no faltan bytes. Conserva además el raster JP, pero
reduce, por ejemplo, `i` y `l` de avance 4 a 3, `r` de 6 a 5 y muchas vocales de
9 a 8. La regla v5 solo contenía la caja CWDH declarada y dejó cero píxeles de
separación en numerosos glifos. Por tanto H1, H2 y H4 quedan confirmadas: no es
wrapping global ni un par concreto, sino una métrica fina demasiado ajustada a
un raster distinto del usado para derivar el avance.

`È` sí está presente: el registro comienza por el portador U+03A0/`83 AE` y la
captura muestra el grave. Su aspecto comparte el mismo defecto general; no hay
evidencia de un fallo de mapping exclusivo de `È`. En los signos invertidos y
acentos tampoco faltan bytes: usan los portadores previstos.

Los nombres confirman H3 por una causa separada. `Maserati` y `Bianchi` son los
textos oficiales exactos de `unitbase.dat`, pero v5 los recodificó como bigramas.
Cada bigrama fue comprimido dentro de una celda FONT8 de 10 px; la captura muestra
la fusión de sus dos letras. El supuesto de que esa ruta avanzaba siempre 10 px
queda descartado: el resultado observado concuerda con los CWDH de los glifos
normales más los portadores de bigrama. FONT8 y FONT12 son recursos distintos y
necesitan adaptaciones distintas.

**Alternativas descartadas.** No se añadirán excepciones por string o por par.
Tampoco se volverá al raster JP con avances elegidos por promedio, ni se conservarán
los bigramas ajustando su dibujo a ojo. La edición europea ya aporta raster y CWDH
coherentes para cada carácter latino; el parche histórico añade además un píxel
de respiración a letras/portadores, criterio general ya usado por el proyecto.

**Corrección elegida.** FONT12 copiará cada glifo latino oficial y su CWDH como
unidad coherente, ajustará la diferencia de baseline 14→13 sin descartar píxeles
y añadirá un píxel de avance a letras y portadores. Es la fuente oficial con el
tracking general existente, no una interpolación. Los anchos calculados de los
casos A/B son 274/310 px, próximos a v5 (272/311) y por debajo de 354 px.

FONT8 retirará por completo los bigramas y volverá a almacenar una letra por
carácter. Solo los caracteres realmente usados por nombres oficiales compatibles
recibirán raster y CWDH de FONT8 europea, con el mismo ajuste de baseline sin
pérdida. Así `Bianchi` y `Maserati` siguen el comportamiento oficial por glifo,
sin tocar el tamaño de `unitbase.dat` ni ningún campo ajeno al nombre corto.

**Riesgos y validación prevista.** Se verificará que el ajuste geométrico conserva
todos los píxeles no nulos, que ambos BCFNT mantienen tamaño y CMAP, que los cinco
casos conservan texto/saltos, que `È`, `¡`, acentos y nombres tienen métrica/raster
oficial coherente y que no aparecen truncamientos. Después pasarán suite completa,
charset, SSD/PKB/PKH, centinelas, offsets y guardias antes de crear una única
candidata v6 pendiente de validación visual. No se toca crecimiento estructural.

**Resultado y casos.** La candidata v6 conserva exactamente los tres strings de
`32500100`: m0000/offset `0x000`, `Unos meses antes, en cierto lugar de
Italia...`; m0003/`0x104`, `¡Bravo, Paolo! ¡El fútbol es puro arte\nen tus
botas!`; y m0007/`0x1DC`, `È terribile! ¡Parece que aquella chica\ndel
puente... se va a caer!`. Los portadores se leen en bruto como U+039E para `¡`,
U+0395 para `ú` y U+03A0 para `È`; no hay pérdida de bytes ni sustitución por
`?` en estos casos.

En A, los pares `ci/ie/rt/to` e `It/ta/li/ia`; en C, `Pa/ao/ol/lo`,
`fú/út/tb/bo/ol`, `ar/rt/te` y `bo/ot/ta/as`; y en E, `te/er/rr/ri/ib/bl/le`,
`Pa/ar/re/ce`, `aq/qu/ue/el/ll/la`, `pu/ue/en/nt/te` y `ca/ae/er` no tienen
kerning propio. Todos heredaban el mismo problema por carácter: v5 dejaba a
`i/l` en 3 px, `r/t` en 5 px y muchas vocales en 8 px sobre raster JP, a menudo
sin margen visual. V6 usa el raster europeo correspondiente y deja un píxel de
avance tras cada letra: `i/l` 3 px sobre glifo de 2, `r/t` 6 sobre 5 y vocales
como `a/e/o` 8 sobre 7. Los acentos conservan su CWDH oficial individual; se
detectó específicamente que `í` necesita 5 px y no los 3 de `i`.

En B/D, la referencia oficial confirma `Maserati` (registro 1849) y `Bianchi`
(1854). V5 almacenaba respectivamente `83D1845083C48472` y
`426983B1844E69`, con portadores de bigrama. V6 almacena los ASCII oficiales
`4D61736572617469` y `4269616E636869` y adapta 65 glifos FONT8 individuales.
Ambos casos comparten exactamente la misma causa y corrección; el diálogo
japonés de sus capturas no forma parte del defecto.

La adaptación final reproduce raster+CWDH oficial y fusiona en el borde la fila
que no cabe al pasar baseline 14→13, sin descartar píxeles no nulos. FONT12 mide
274 px en A y 310 px en C, por debajo de 354 px y prácticamente igual que v5.
La previsualización estática `work/informes/spark_v6_metricas_finas.png` confirma
que los trazos individuales existen; la ruta runtime sigue pendiente de prueba.

**Validación mecánica.** La reconstrucción segura se reprodujo byte a byte para
2.849 eventos Spark: 19.484 aplicados completos y 14.617 rechazados intactos.
Se analizaron 12.804 entradas (6.980 SSD y 5.824 planas), dos centinelas PKH y
80.041 offsets sin incidencia. Pasaron 1.037 tests (12 deseleccionados), charset,
CMAP/hashes y las guardias de congelados, Git y shims. La extracción independiente
de la ROM devolvió el archive `6a5962de…10e1de` y el CRO `1c2db0af…f3061`.
La build no está verificada en ejecución.

## 2026-09-19 — V7: regresión visual de v6, celdas y posición real de tinta

**Corrección del diagnóstico anterior.** El usuario rechaza visualmente v6:
nombres torcidos y separados, y cuerpo menos legible que v5. Las afirmaciones
anteriores de H1/H2/H4 «confirmadas» y de raster oficial sin pérdida eran
excesivas: se comprobó la salida con el mismo lector erróneo que la generaba.
Fusionar píxeles en un borde tampoco preserva su geometría. Esas conclusiones
quedan sustituidas por esta investigación; los resultados estructurales no
demostraban legibilidad.

**Evidencia.** La dirección de una celda BCFNT usa
`col*(cellWidth+1)+1`, `fila*(cellHeight+1)+1`; véase `fontCalcGlyphPos`
en https://github.com/devkitPro/libctru/blob/master/libctru/source/font.c.
El lector congelado divide la hoja por el número de celdas y omite el margen
inicial. En FONT8 europea esto da paso vertical 16 en vez de 13; en FONT12,
horizontal 16 en vez de 15. La sonda `work/ie3/sonda_celdas_v7.py` reproduce
el nombre torcido al leer con la fórmula antigua y lo alinea con la correcta.
El análisis independiente de `code.bin` confirma además centrado horizontal
en BuildTextCommand (VA 0x1A147C–0x1A14A0); falta incorporar ese término a la
validación de CWDH, que antes solo sumaba avances. La cadena IE3 mantiene dos
posiciones (DS/NW), por lo que «siempre fijo10» no se deduce de las capturas.

**Decisión previa.** Mantener los originales y los cinco congelados intactos.
Especializar el lector existente fuera del congelado, con stride y origen
correctos. Reemplazar la fusión de bordes por una comprobación estricta que
rechace cualquier píxel no nulo que no quepa. Tras confirmar las unidades del
centrado, compensarlo en CWDH sin cambiar los textos ni el crecimiento SSD.
Reutilizar raster oficial sin reescalado ni bigramas y comparar antes/después
con un modelo que incluya el desplazamiento del motor.

**Riesgos y validación.** Los recursos de fuente son compartidos; limitar los
cambios a los glifos latinos previstos y conservar geometría, CMAP y tamaño.
Probar direccionamiento con hojas no divisibles, márgenes, baseline y CWDH
negativo. Comprobar por lectura independiente el raster, los japoneses intactos,
los casos de las capturas y los textos rechazados, además de suite y guardias.
La siguiente candidata seguirá pendiente de validación visual; no hacer push.

**Centrado confirmado antes de adaptar CWDH.** La auditoría del binario JP
local resuelve vtable+8 a VA 0x223FD4 (FINF.width: 15 FONT12 y 11 FONT8,
no 10). CalcStringRect 0x180BBC–0x180C6C mide el avance CWDH y no incorpora
left ni glyphWidth. El constructor 0x2067A8 inicia escala 1; la ruta habitual
no la sustituye. Se aplica `left_ES - trunc((FINF.width - charWidth)/2)`,
manteniendo glyphWidth y charWidth separados. No hay cambio de CRO adicional.
El propio código JP 0x223F50–0x223F7C confirma pitch y origen +1 de la textura.
FONT12/FONT8 parten del original, evitando residuos del escritor histórico en
los márgenes; FONT12T mantiene exactamente el tratamiento anterior.

**Resultado implementado.** V7 adapta 111 glifos FONT12 y 73 FONT8 (nombres
y portadores de español/È). Cero fusiones de borde: la traslación de baseline
14→13 y 10→9 solo elimina filas vacías; una muestra no nula fuera de celda
detendría el proceso. Tests con direccionamiento independiente verifican cada
muestra, CWDH, cabeceras, CMAP, márgenes y todas las zonas ajenas a los glifos
objetivo. Las fuentes japonesas originales permanecen intactas.

La sonda `work/informes/sonda_celdas_v7.png` incorpora el centrado del motor y
reproduce en FONT12 los síntomas de v5/v6; la fila v7 muestra `Italia`, `Paolo`,
`fútbol`, `È`, `¡`, `¿`, acentos y `ñ` sin la deformación previa. Es una
previsualización, no una captura de ejecución. La fila FONT8 v5 de la sonda
no decodifica sus bigramas y no debe usarse como reproducción del nombre v5.

Comparación exhaustiva de las entradas archive v6/v7: **solo FONT12 y FONT8
son distintas**. `unitbase.dat`, textos, paquetes, FONT12T y demás entradas
son byte-idénticos. El CRO conserva el parche de ventana previo, sin cambios
nuevos. La comprobación independiente de texto encuentra 19.484 inserciones
completas (14 ya coinciden con el texto original), 14.617 rechazos cuyos
grupos completos, incluido relleno, son byte-idénticos, y cero truncamientos.
También comprueba que las 571 sustituciones SSD no quedaron recortadas.

Pasaron 1.060 tests sin ROM (14 deseleccionados), 2 pruebas adicionales contra
las fuentes oficiales, charset, 6.980 SSD, 5.824 tablas planas, dos centinelas
PKH y 80.041 offsets. Guardias: cinco congelados intactos, cero prohibidos
entre 641 ficheros rastreados y 31 shims correctos. `git diff --check` señala
una línea vacía al final de `reinsert.py` que ya existía al empezar esta tarea;
no se modificó ese archivo para una corrección exclusivamente tipográfica.

**Pendiente real.** Validación en juego de esta fuente en la ruta de diálogo y
nombres, y posibles rutas con override/escala diferente. No se declara resuelta
la legibilidad basándose solo en tests ni se generaliza a menús u otros juegos.
El charset histórico tampoco soporta Ü mayúscula (no aparece en el corpus
insertado); no se ha ampliado esa cobertura en esta revisión.

La ROM completa v7 ya generada fue extraída de nuevo: archive y CRO coinciden
con la candidata, ExeFS no cambió y la base conserva su hash. Tamaño, SHA-256
y ruta exacta constan en HISTORIAL_CODEX.md. No hay warnings del empaquetador.
El siguiente paso es exclusivamente la prueba visual; `runtime_verified` sigue
en false.

## 2026-09-19 — Fase 2: referencia aceptada y reconstrucción coordinada

El usuario acepta la legibilidad de v7 en los casos probados, sin declarar QA
global. Se congela como referencia funcional la tipografía, encoder, portadores,
È, dimensiones, wrapping y tratamiento actual de páginas. La nueva autorización
permite investigar e implementar tamaños variables con referencias demostradas;
no permite reactivar el antiguo `--crecer` ni tocar los cinco congelados.

**Diagnóstico previo y primera evidencia.** Se reutiliza el informe histórico de
rechazos, pero se ampliará a perfiles Spark/Ogre, con todos los grupos originales
en el denominador, ambigüedades explícitas, encoding estricto y claves de origen.
Un manifiesto fijará entradas, corpus, configuración/código y hashes de v7 sin
copiar ROMs. Las cifras anteriores no se reciclan como diagnóstico actual.

El consumidor de diálogo encontrado en CRO offset 0x4F05C interpreta el prefijo
`@`: en 0x4F0C4–0x4F120 obtiene dos números decimales, suma el primero a la base
del recurso y pasa el segundo como longitud a 0x267A68. Los datos JP/ES confirman
que son (offset, longitud de grupo), **no posición visual** como afirmaban las
notas históricas. Quedan por fijar límites del lector, cobertura de referencias
y diferencias de versión antes de emitir recursos. No se extrapola de un caso.

**Alternativa mínima a comprobar.** Crecer los registros necesarios manteniendo
el número/orden, conservar los slots ruby (vacíos cuando proceda) y actualizar
solo las cadenas `@offset,longitud` que realmente consume cada instrucción. Así
podría mantenerse byte-idéntica la sección de código, sin reenumerar instrucciones,
ramas, voces o hablantes. Esta es una hipótesis de implementación, condicionada a
la auditoría del consumidor y de todas las referencias del evento.

**Validación prevista.** Round-trip exacto sin traducción, pruebas de crecimiento
al principio/medio/final, controles, multibyte, ruby, límites y referencias
compartidas. Después un piloto mínimo del prólogo sobre archive v7, con
reextracción del artefacto final. No activar todo el corpus hasta que el piloto
tenga prueba dinámica; los rechazos por layout/encoding/límites reales seguirán
visibles, no se resolverán alterando la tipografía ni truncando.

### Resultado de la investigación y elección de emisión

La cadena de carga quedó demostrada en el CRO JP y contrastada con Spark y Ogre,
no inferida de un entero o de un script europeo. La descripción completa,
offsets de archivo, hash, tipos, límites y comandos está en
[IE3_FASE2_REFERENCIAS](docs/IE3_FASE2_REFERENCIAS.md). El primer argumento de
301D resuelve bytes relativos a evet; solo los argumentos tipo 3 consumen sus
registros. El cargador SSD enlaza por ID de instrucción/slot físico, no por el
placeholder. No hay que modificar 301A ni el bytecode para este crecimiento.

Se eligió **conservar literalmente todos los registros secundarios**, no vaciarlos
ni retirarlos: no todos son ruby, algunos son parámetros de controles. La nueva
emisión de contenido es deliberadamente parcial para controles con sustituciones:
no puede declararse el 100 % mientras no se demuestren sus cotas dinámicas. Se
mantienen las limitaciones reales del consumidor (registro 252, grupo 1024,
texto expandido 512), sin ampliar constantes ni alterar el layout aprobado.

La validación estricta detectó dos particularidades oficiales antes de construir:
las colas PKH son 0/4/8/12 bytes FF según el conteo real; algunas referencias SSD
llenan el registro sin NUL. En este último caso se comprobó el parser decimal real
y se exige un byte posterior no decimal, también en la salida. Las cadenas nuevas
sí terminan dentro de su registro. Las 74 cadenas de depuración 3070 sin NUL de
Spark son una peculiaridad original ajena al consumidor auditado y se preservan.
Estas reglas están probadas; no se retiró una guardia para aceptar un error.

Los perfiles fijan base, consumidor, fuente ES, corpus y correspondencias. Se
resolverán las colisiones del antiguo `(evento,texto JP)` por identidad y fuente
reextraída, no con «última fila gana». Bomber sigue sin corpus: comparte recursos
con Spark, pero eso no demuestra igualdad semántica y no se declara localizado.
El piloto rechaza sobrescribir un mensaje ya cambiado si no coincide su hash JP.

**Validación offline conseguida:** round-trip literal de ocho pares PKB/PKH y
11.669 eventos JP/ES; 79.946 referencias JP y 79.684 ES verificadas. Simulación
de 31.362 mensajes Spark y 33.711 Ogre, con reextracción exacta, sin activarlos
masivamente. El 100 % no está resuelto: Spark conserva 2.688 pendientes por
controles, 41 de encoding y 9 de layout entre los mensajes oficiales referenciados;
Ogre conserva 2.936, 47 y 9 respectivamente, además de dos correspondencias sin
confirmar. Inline, huérfanos y tres referencias Ogre a recurso ausente se inventarían
aparte, sin desaparecer del diagnóstico ni del denominador legado.

**Piloto elegido:** clave `spark:evet:32500100:00000064`, instrucción 1184, primera
intervención de Maserati. Procedencia ES evento 32500100, offset 52, `m0001`.
Registro 92→120 bytes, grupo 116→144; secundarios 12+12 intactos. Cambian siete
referencias SSD; el bytecode, la respuesta siguiente y todos los demás registros
permanecen como v7. La build reutiliza su CRO exacto, no lo vuelve a parchear.

La comparación real detectó 14 originales ya idénticos al ES (no son inserciones
nuevas) y 23 traducciones heredadas de v7 que difieren de la identidad resuelta.
Se documentan en `qa.json` y se mantienen para no mezclar una corrección de corpus
con la prueba estructural de un único mensaje. Quedan pendientes para la futura
activación, sin maquillarlas como nuevas traducciones verificadas.

## 2026-09-19 — Fase 3: piloto aprobado y activación por perfiles

El usuario confirma en ejecución la primera intervención de Maserati del piloto
con ROM SHA-256 `967107bd55f8f6bb18df896f2564296f0b908163d5fe12a6027cacaad7644e79`.
La aprobación se limita a `spark:evet:32500100:00000064` (1184, grupo 116→144),
no a todos los controles/campañas. Autoriza emisión general de los casos
equivalentes, corrección de nombres y localización de texto visible adicional.
El cuerpo de diálogo, portadores, encoder, È, dimensiones y wrapping quedan
congelados; los cinco archivos protegidos siguen intactos.

**Diseño antes de editar.** Reutilizar lector/reconstructor fase2 y sus perfiles.
Separar la planificación de contenido de la emisión para todos los mensajes,
sin IDs de ejemplo. Reconstruir desde entradas declaradas y comparar la
transición JP→heredado aprobado→salida; jamás retirar la comprobación de hash JP
ni crecer repetidamente tomando offsets nuevos como originales. Conservar los
secundarios originales de la estrategia demostrada y todos los metadatos/código.
Registrar inserción nueva, ya idéntico, heredado y corrección por separado.

Controles: agrupar por consumidor/argumentos, demostrar cotas de expansión y
compatibilidad de orden antes de emitir. No sustituir cotas por longitudes
«típicas». Encoding no cubierto por los portadores congelados seguirá pendiente
si exige modificarlos. Las páginas solo podrán emitirse con semántica probada.
Dos líneas independientes revisan nombres e integración de otros textos con
propiedad de archivos separada; el agente principal integra y verifica.

Validación prevista: pruebas de referencias/controles y regresión, diagnóstico
actualizado Spark/Ogre, reextracción de paquetes y campos no textuales, renderer
offline, guardias y una única build integrada reextraída. No ampliar la aceptación
del piloto a esta nueva candidata ni pedir repetirlo para los casos equivalentes.

### Fase 3: decisiones de implementación y límites de la ampliación

La guardia arquitectónica detectó inicialmente que `comun.controles` importaba
la CLI de fase 2. Se corrigió trasladando el algoritmo, sin duplicarlo, a
`comun.emision`; la fachada fase2 conserva su API. No se relajó la guardia.

**Controles.** `4B424` usa un cursor de argumentos compartido para `%s`, `%d`,
`%C` y ruby. Solo se emite una sustitución inicial seguida exclusivamente de
ruby JP; no se descartan argumentos anteriores. `%d` formatea int32 y convierte
hasta 11 caracteres a 22 bytes SJIS. Para `%s`, `4099→47F24→178284→17DA4C`
obtiene el nombre del pool item: el campo NUL ocupa 28 bytes y cada una de sus
1024 entradas se verifica después de localizar. La cota incluye bytes, máximo
de caracteres y máximo de tinta. Un marcador de reserva con ambas cotas pasa
por el mismo wrapping aprobado, luego se recupera el control original. Se
comprueba el mensaje expandido completo, incluyendo NUL, frente a 512 bytes;
registro 252 y grupo 1024 siguen intactos. El productor `4002→48010→17A1BC`
de personajes puede venir de instancias vivas/cachés: la cota estática de
unitbase no demuestra por sí sola todas esas rutas y no se generaliza a ellas.

**Objetos.** La aparente ausencia de texto en item.dat era ofuscación, no otra
codificación: el lector copia 44 bytes, XOR AD, rota dos bits y permuta grupos.
Se invierte esa transformación reutilizando RecordTable para escribir únicamente
el campo de nombre. La correspondencia requiere la misma fila y metadatos
28:42 unívocos en ambas ediciones; 42:44 se conserva del JP, sin presumir que
su numeración regional sea intercambiable. Todos los campos no textuales y las
filas no modificadas se comparan literalmente con el original. No se extiende
esa geometría a item.STR, técnicas, menús o gráficos sin su contrato propio.

**Nombres.** unitbase no tiene cabecera 0x60: son objetos planos de 0x68, corto
en +1C e identidad en +4E. El adaptador anterior acertaba el campo físico por
un desfase compensado, pero sus comprobaciones quedaban desplazadas. El nuevo
adaptador enlaza IDs únicos y preserva los campos ajenos. La rama `180918`
solo se toma para FONT8; cambiar `beq 180930` a `beq 180970` evita defaults
forzados sin modificar FONT12/FONT12T/RUBI ni las fuentes. Se exige el hash v7
exacto, anclas ARM, ausencia en relocaciones y una sola palabra cambiada. Los
overrides explícitos siguen funcionando. Riesgo nuevo: otras interfaces FONT8
del mismo CRO; debe revisarse también su espaciado. No afecta los CRO IE1/IE2.

Más evidencia y pendientes en `docs/IE3_NOMBRES_FASE3.md`,
`docs/IE3_ITEMS_FASE3.md`, `docs/IE3_IDENTIDADES_FASE3.md` y
`docs/IE3_TEXTO_VISIBLE_FASE3.md`.

**Revisión final de textos visibles:** la propuesta inicial por orden y rol se
rechazó antes de generar una ROM. Se exigen misma instrucción/slot, argumentos
no textuales iguales y dos anclas inmediatas de bytecode. Tampoco se extrapola
el buffer 301D a objetivos/lugares: sin cota del destino IE3, el ES debe ocupar
como máximo los bytes del cuerpo JP original, conservando tamaño del registro,
tabla y cabecera. Los demás campos quedan pendientes explícitos. Se mantuvieron
los diagnósticos preliminares, sin archive/ROM, para explicar la reducción de
cobertura; no se presentan sus cifras de candidatos como inserciones finales.

### Resultado final de validación de fase 3

La candidata emitió y reextrajo 31.833 mensajes Spark y 34.212 Ogre. Son
93,3519 % y 93,2080 % de los oficiales referenciados, no del juego entero ni
traducciones nuevas. Se comprobaron separadamente las 23 correcciones heredadas,
los 14 originales Spark idénticos (13 dentro de 301D) y las dos identidades
Ogre resueltas. Los 2.217 controles Spark heredados se conservan como pendientes,
sin convertir una aceptación antigua en prueba de sus cotas dinámicas.

El control adicional post-encoder valida los 66.045 mensajes admitidos contra
las métricas aprobadas y las cotas del pool completo: máximo 151 bytes
expandidos incluido NUL, 51 glifos por línea y 322 px de tinta. Los 471/499
mensajes habilitados con controles pasan esa comprobación; no se eliminaron
argumentos, signos ni caracteres para aumentar cobertura. El renderer offline
permite inspeccionar raster/layout, pero no se afirma haber cargado los eventos.

La intervención FONT8 conserva literalmente todas las fuentes y todas las
rutas restantes del CRO. Su efecto en otras interfaces de IE3 y en nombres con
espacios sigue pendiente de ejecución. Se emitieron 11/2.372 nombres cortos
nuevos, 786/789 nombres de objetos frente al JP y 95/104 campos SSD visibles
distintos del JP. Los originales idénticos y heredados figuran aparte. Los
campos ajenos a texto, IDs y estadísticas se conservaron. No se dedujo seguridad
para menús/descripciones/cadenas/gráficos a partir del éxito de esos adaptadores.

Pruebas: 1.154 tests sin ROM y ocho subtests, cinco tests seleccionados sobre
oficiales, ocho round-trips PKB/PKH y 11.669 eventos; guardias completas y lint
correctos. Las excepciones oficiales de terminación/colas y recurso Ogre
90000002 ausente se verificaron contra originales. Ningún truncamiento aceptado.

La ROM completa de 2.147.483.648 bytes tiene SHA-256
`34c2e9a3e79d7561ece763e41909f06db97601c98dbcd1d879100b38ddf4bc6e`.
Su reextracción confirma archive/CRO, todas las 15.547 entradas internas y
ExeFS original. Los hashes del código congelado y seis recursos de fuente se
mantienen. Artefacto y manifiestos en `docs/IE3_FASE3_INTEGRACION.md`.
Este resultado demuestra integridad/reproducibilidad local, no corrección visual
de todas las campañas. La etiqueta permanece **pendiente de validación manual
del conjunto** y la aprobación previa no se amplía.

## 2026-09-19 — Fase 4: colocación, límite de nombre e interfaz

Encargo nuevo: conservar estrictamente fuentes/raster/escala/métricas/bearings,
centrado, encoder/portadores y cinco congelados. Se autorizan únicamente origen,
separación adicional entre palabras o filas y límites de presentación de nombres
con evidencia. La ROM de partida fue comprobada en disco: SHA-256
`34c2e9a3e79d7561ece763e41909f06db97601c98dbcd1d879100b38ddf4bc6e`.
Se preserva el árbol local sin commit/push y no se reabre la reconstrucción 301D.

**Observación, no causa aún:** el usuario ve desbordamiento en «Equipos
juveniles…» y la última i de Maserati fuera de su fila. No dispone de capturas
actuales/europeas; la comparación visual de ejecución no puede inventarse.
Se usará evidencia de los originales y simulación a escala nativa, explicitando
los límites. El mensaje localizado es Spark evet 32010100:0, instrucción1138,
fuente ES m0000 offset0. La fuente tiene dos líneas y tres puntos finales,
no los cuatro de la transcripción aproximada. La candidata conserva ese texto.

**Plan previo a cambios:** seguir origen/rectángulo y espacios desde el llamador
de diálogo hasta el dibujado, medir tinta colocada y no solo suma de avances.
Reutilizar el wrapping existente si hace falta un salto; no compensar con letras
más pequeñas ni tracking global. Para nombres, comprobar el límite lógico64,
el ancho FONT8 lógico8 y tracking1 frente al ancho proporcional de dibujo,
incluido el uso del mismo límite en el terminador del buffer antes de ampliarlo.
Las familias gráficas de menú y tablas de descripciones se investigan en paralelo
con propietarios de archivos separados; solo se integrarán equivalencias y
campos/regiones seguros. No se copia un paquete EU entero por parecido.

**Validación prevista:** snapshots de hashes protegidos, tests por contrato,
renderer con las mismas transformaciones del consumidor, simulación de casos
largos/nombres7–9/con espacios, preservación literal no textual, suite/guardias
y una sola ROM integrada reextraída. Los bloqueos de UI se mantienen separados
de los porcentajes de diálogo. No se declara validación en juego de una maqueta.

### Evidencia de colocación antes de implementar

El espacio emitido sigue siendo ASCII `20`. El consumidor JP lo transforma en
U+3000 (.code VA 1A0FDC–1A100C, llamado desde CRO 180CC0). En la fuente aprobada
ese glifo invisible avanza **7**, no los **3** que contaba la maqueta anterior.
No existe aquí tracking extra entre todas las letras: el llamador 3A8D4–3A8F0
establece tracking 0 e interlineado adicional 3. No se cambia ni el convertidor
ni CWDH. El antiguo tope354 provenía de una geometría IE1, no de la caja IE3
inferior de320. Por ello una medida anterior desde cero no demostraba encaje.

La cadena de posición relativa al origen de ventana es 38D5C (+10 al grupo),
3AB98/182260 (posición NW de cada glifo), 3ABC8/167DC0 (+2 desde ITX).
La compensación FINF/CWDH se aplica una sola vez al raster. La textura oficial
de marco tiene tiras en columnas4/5 y región interior desde6; las mitades QNA
centradas81/239, ancho160, cubren1..319. Se usa interior conservador7..312.
La colocación candidata será +8 (grupo+10, offset del cuerpo−2), dejando un
píxel respecto a la tira. Se cambia exclusivamente el literal del llamador
3ABC8, no el ITX compartido ni los offsets de ruby/nombre. Es una decisión de
colocación sustentada por recursos, **no una medición de captura de ejecución**.
El ITX europeo también dice +2: no se afirma un padding duplicado demostrado.

Se conecta el wrapping existente a un medidor de tinta/raster real que modela
U+3000 y el origen. No se cambia su algoritmo ni se inventan páginas. Un caso
que requiera más de tres filas o controles no resueltos permanece literal y
se declara pendiente, nunca truncado ni ocultado en un porcentaje global.
Vertical: se conserva la transformación existente 115/100 de las posiciones,
no se escala el glifo y no se cambia el interlineado sin comparación visual.

### Comprobación de las dos rutas de coordenadas

Se auditó expresamente el riesgo de confundir el plano gráfico con el texto.
SetPosition (.code 9B7C8) sí tiene conversión ×1,25 para la pantalla inferior,
pero no se aplica al cuerpo: CRO 3ABB8→17064 fija part+80=0 en el mismo grupo
del cuerpo; 16420–16458 suma grupo y glifo fijos y divide por4096; 196D44–54
añade part+84. FindHintOnPlaneVramAndDrawText (.code650F0) recibe el indicador
cero, y 655B0–655B8 salta la conversión 655BC–655F4. Por tanto la posición es
baseX+10+glifoX+2 (antes) y baseX+10+glifoX−2 (candidata), sin escalar avances
ni raster. El modelo relativo 12→8 se mantiene tras esta comprobación.
La animación de la ventana no equivale a alterar esos márgenes relativos.

### Resultado de la fase 4 y límites de la evidencia

Los cuatro casos se midieron y dibujaron con las mismas fuentes/transformaciones:
Equipos pasa de 12..318 a tres filas 8..253/8..60/8..292; Unos meses acaba en309,
Paolo en255/97 y È en254/183. Espacio avance7 y filas relativas0/21/43 intactos.
Se comprobaron31.141/33.456 estáticos y recolocaron835/932; los221/257 no
admitidos quedan literales, no ocultos ni truncados.

Maserati: ocho letras exigen71 frente al64 lógico anterior, tinta44. La
ampliación directa del argumento habría alterado el cálculo del terminador
y se descartó. Se ajusta solo el comparando de pestaña, límite134 y guardia
previa que reserva terminador; buffer512/ancho64 y otras rutas intactos.
Auditadas8.770 filas y385 nombres SSD finales, incluidos espacios y longitudes.

Integradas tablas,12etiquetas de menú y70recursos gráficos con fuentes oficiales
y consumidores independientes del diálogo. Capacidad binaria o QNA idéntico no
certifican encaje de todos los widgets: falta prueba manual, también de origen
de pestaña e indicador animado. Ayudas regionales incompatibles, PT/PE incorrectos
y campos sin contrato quedan JP. Detalles en `docs/IE3_FASE4_INTEGRACION.md`.

ROM única SHA `c020a022ef6fc8026c4d5040968e3e705ea77737507724b901bead8113c0b645`,
2.147.483.648bytes; reextracción correcta archive/CRO/15.547entradas/ExeFS.
1.319tests sinROM+8subtests,13conoriginales y guardias correctas; lint focal
correcto,10avisos globales anteriores documentados. Tipografía/encoder y cinco
congelados intactos, sin actualizar hashes para sortear guardias. No se ejecutó
el artefacto: sigue pendiente de validación manual del conjunto.

## 2026-09-19 — Revisión tras rechazo visual de fase 4

Las siete capturas nuevas del usuario invalidan la utilidad visual de la entrega:
menú lateral español partido/solapado, etiquetas superiores mal colocadas y
misión, ficha, opciones, registro y tutorial mayoritariamente japoneses. Los
tests binarios no validaban esos consumidores gráficos. Los porcentajes301D
no describen esas pantallas. La fase4 queda rechazada visualmente, no aprobada.

El usuario pide reducir realmente espacio entre palabras e interlineado, y
extiende explícitamente el alcance a canciones, intros/vídeos y voces. La fase4
no redujo separaciones: solo margen y saltos; no se presenta ahora como si lo
hubiera hecho. La nueva intervención conservará las letras/raster/encoder y
buscará parámetros de colocación específicos, sincronizando medida y dibujo.

Plan: principal corrige límites del menú y colocación del cuerpo; tres líneas
independientes comprueban gráficos activos, textos de misión/ficha reales y
medios españoles locales. No basta insertar un recurso que esa pantalla no usa.
Se retirarán restricciones de formato que sean políticas sin base técnica,
sin ignorar buffers, referencias ni semántica regional. No se inventará doblaje
español inexistente ni se prometerá TODO traducido con un inventario incompleto.
Primero cambios y pruebas focalizadas, una sola candidata ejecutable al cerrar
el conjunto; no reconstrucción2GiB por cada ajuste ni repetición de la auditoría
completa anterior. Originales/guardados intactos, sin push.

### Ajustes de colocación propuestos antes de emitir

El menú lateral usa el generador común desde10B3A8 con límite lógico64 para
la textura de comandos, pero cada letra lógica FONT12 cuenta12: «Jugadores»
se parte tras cinco letras, exactamente como la captura. Su ancho proporcional
no es ese contador. Se ajustará solo la comparación de ese llamador y de las
seis cadenas del menú principal, conservando capacidad/argumentos y añadiendo
guardia contra exceso de comandos. No ampliar cajas ni cambiar glifos.

Para el cuerpo, avance de colocación del separador ASCII20:7→3 solo desde el
llamador3A9A4; no CWDH/encoder ni espacios de otras interfaces. Interlineado
adicional3→1 y factor de posición115/100→100/100, de21/22 a17píxeles por fila,
con raster16 intacto. Debe probarse que el hueco vertical siga sin colisión.
El medidor offline recibirá exactamente estos parámetros y restaurará saltos
de fase3 cuando el texto ya quepa, en vez de conservar el reflujo innecesario.

El espacio para trampolines se limitará al padding cero29BF48..29C000, antes
del segmento de datos, sin desplazar archivo ni referencias. Antes de escribir
se comprobarán ausencia de entradas/reubicaciones/exportaciones, segmentación,
hash exacto de fase4 y destinos; se ampliará solo la longitud declarada del
segmento de código dentro de ese padding. Si cualquiera no se demuestra se
rechaza. Tests independientes de instrucciones/ASLR y fuentes intactas antes
de integrar, sin presentar la simulación como ejecución.

### Correcciones al diseño tras revisión independiente

El padding29BF48 tiene una referencia como extremo de un rango semiabierto de
metadatos CRO. Se conserva esa referencia y los ocho ceros29BF48..29BF50. Los
trampolines comienzan en29BF50, sin modificar ese endpoint. El ajuste del espacio
se aplica en180E94, después de los posibles overrides del gestor; solo ASCII20
del cuerpo3A9A8 recibe avance de colocación3. Las letras y CWDH no cambian.

El comparando de menú por sí solo NO resolvía el problema. La revisión del lector
FindHintOnPlane demuestra un segundo filtro por UV/ancho de parte: había que
ampliar también la selección de comandos del menú principal. El nuevo ajuste
10AFD8 discrimina por el primer literal del widget, preserva anchos de las demás
listas, y cambia solo selección64→144. No cambia tamaño de botón, escala de
glifo ni buffer. La cadena probada está en IE3_UI_VISIBLE_REVISION.md.

Para liberar espacio sin mover datos, el comparando se discrimina por el rango
único de las seis cadenas, no también por el llamador redundante. Stub menú
29BF80..29BFC8; selección29BFCC..29BFF4. Cada módulo comprueba anclas,
segmentación y destinos, y la composición se prueba contra la candidata exacta.

La auditoría de datos encontró además un error real en fase4: unitbase europeo
referencia strings con escala256, no32. Un roundtrip del mismo adaptador erróneo
no lo detectaba. La nueva validación usa el lector europeo y casos conocidos
(Paolo Bianchi/descripción exacta), regenerando los pools desde JP; los
porcentajes de descripciones de fase4 no se consideran válidos. Los otros tres
lectores europeos sí usan32 y se verifican por separado.

Los medios externos requieren otra comprobación del artefacto: se extenderá el
readback final a cada SADL, no solo archive/CRO. Vídeos y subtítulos son rutas
distintas; se admiten65 vídeos oficiales con igual timeline decodificado, pero
se conservan explícitamente los DAT japoneses porque su lector descarta ASCII.
Esto mejora medios pero NO equivale a localización completa del juego.
