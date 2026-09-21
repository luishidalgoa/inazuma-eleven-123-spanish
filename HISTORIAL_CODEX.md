# Historial Codex

## 2026-09-19 — Fase 4: colocación conservando letras, nombres e interfaz

Referencia: ROM fase 3 exacta solicitada, SHA
`34c2e9a3e79d7561ece763e41909f06db97601c98dbcd1d879100b38ddf4bc6e`.
El usuario observa desbordamiento en «Equipos juveniles…» y salto de la i de
Maserati; no dispone de capturas actuales/europeas. La evidencia siguiente es
de datos/código y simulación, no una comparación de ejecuciones inventada.

El espacio ASCII se convierte a U+3000 y avanza 7, no los 3 del medidor anterior.
El límite antiguo 354 tampoco describía la caja IE3. La línea ocupa 12..318
frente al interior conservador 7..312. Se cambia solo el offset del cuerpo
+2→−2, origen total 12→8, y se conecta el wrapping existente al medidor colocado.
«Equipos…» requiere tres filas, sin perder «soñaban» ni sus tres puntos oficiales.
Unos meses/Paolo/È quedan dentro de las cotas. No se cambian separación entre
letras/palabras, interlineado, raster, escala, CWDH, centrado ni encoder. La ruta
texto evita la escala ×1,25 de planos, comprobada por anclas e import/export.

Maserati está completo en 16 bytes con NUL y sin salto: el octavo glifo exige
71 en una rejilla lógica limitada a 64, aunque su tinta mide 44. Se modifica
solo el comparando del llamador de pestaña (134 para 15 glifos), con guardia
de comandos antes del dibujo. Buffer 512 y ancho físico 64 intactos; se descarta
ampliar directamente el argumento que también controla memoria. Intérprete ARM
comprueba llamadores, flags, ASLR, colores y entradas extremas. Auditadas 8.770
filas y 385 nombres 3019 de la candidata; espacios ya modelados.

Interfaz emitida, no solo inventario: 12 etiquetas oficiales comunes, seis
opciones laterales, nivel/título/puntos; por perfil 673 descripciones de objetos,
398 nombres y 382 descripciones de técnicas, 21 descripciones de tácticas,
778/783 fichas, 20 títulos de equipo, 7/8 títulos de cadenas, 38 condiciones
de victoria y 27/25 de apertura. Integradas 64 ayudas y 25 atlas de seis
paquetes (70 recursos), conservando QNA/formatos y píxeles oficiales exactos.
Fuentes Spark/Ogre verificadas por separado; Bomber no se declara localizado.

Pendientes separados: contador superior Jugadores no cabe en 8 bytes; tablas
por capacidad/identidad/encoding; nombres de tácticas sin lector; games.STR
sin fuente española; gráficos incompatibles y 19 ayudas excluidas por diferencias
regionales o PT/PE. Los 221/257 diálogos estáticos no colocables siguen literales
y pueden desbordar. No se reabren controles pendientes. Cobertura 301D heredada:
93,3519 % Spark y 93,2080 % Ogre, no cobertura global de UI.

Validación final: 1.319 tests sin ROM y ocho subtests; 13 tests con originales;
guardias bloqueados/git/shims correctas. SSD/PKB/PKH, centinela y colas cubiertos;
lectura independiente de 79.946 referencias y 210.242 registros, con 835/932
reflujos exactos y restantes literales, sin truncamientos aceptados. Seis
recursos de fuentes y siete componentes protegidos iguales por SHA; cinco
congelados intactos. Lint focal pasa; diez avisos globales anteriores y blanco
final previo en reinsert documentados sin alterar componentes protegidos.

Una única ROM nueva, **Spark + Ogre Fase 4 — pendiente de validación manual del
conjunto**, candidata específica para probar colocación/nombres/UI:
`work/build/inazuma123_spark_ogre_fase4_pendiente_validacion_manual.3ds`.
2.147.483.648 bytes; SHA-256
`c020a022ef6fc8026c4d5040968e3e705ea77737507724b901bead8113c0b645`.
Reextraídos archive/CRO/15.547 entradas y ExeFS original con coincidencia exacta.
Manifiestos en `work/ie3/shared/candidatas/spark_ogre_integrada_fase4/`.
Informe, hashes, pendientes y reproducción en `docs/IE3_FASE4_INTEGRACION.md`.
No se ejecutó el juego; simulaciones no equivalen a validación manual.
Sin push, PR, publicación ni eliminación de originales/guardados. Se detiene
el trabajo estructural a la espera de la prueba del usuario.

## 2026-09-19 — Fase 3: aprobación del piloto y emisión general Spark/Ogre

El usuario confirmó que la primera intervención de Maserati del piloto se muestra
completa y correctamente. La aprobación corresponde exclusivamente a la ROM
SHA-256 `967107bd55f8f6bb18df896f2564296f0b908163d5fe12a6027cacaad7644e79`,
clave `spark:evet:32500100:00000064`, instrucción 1184. Se registra en
`work/ie3/shared/fase3/aprobacion_piloto.json`; no se reetiqueta como validada
la totalidad del piloto ni los manifiestos históricos. La espera de la entrada
anterior queda superada por esta autorización. El cuerpo tipográfico v7 queda
aceptado y conservado para esta fase.

Se generalizó la reconstrucción desde originales, con transición explícita
original→heredado→salida y comprobación de hashes JP. El núcleo común se trasladó
a `ie3.comun.emision`, manteniendo la CLI de fase 2, y fase 3 lo reutiliza para
ambos perfiles. No se activa `--crecer` ni se cambian instrucciones 301A/301D.
Los secundarios se restauran/conservan literalmente desde los originales de
la estrategia demostrada, sin vaciarlos como hacía la ruta heredada.

Las dos colisiones Ogre se resolvieron por consumidor 1232, encuadrado por las
anclas 1216/1239, y fuente oficial reextraída. Se implementaron cotas de `%d`
(int32, hasta 22 bytes expandidos) y `%s` de objetos (`4099`), calculadas sobre
todos los nombres de la tabla resultante; las rutas dinámicas de personajes
siguen diferenciadas, no se les presta esa cota.

Se integran objetivos/lugares SSD, nombres cortos por identidad real de unitbase
y nombres de objetos dentro de registros ofuscados, conservando IDs/estadísticas.
Para la presentación FONT8 se eligió cambiar una rama existente del CRO IE3,
sin cave, sin escalar fuentes y sin alterar la ruta FONT12 del cuerpo. Su alcance
incluye otras interfaces FONT8 de IE3 sin override propio; requiere prueba manual.
La comparación gráfica offline no se considera ejecución del motor.

Se generó una única ROM nueva integrada, **Spark + Ogre Fase 3 — pendiente de
validación manual del conjunto**:
`work/build/inazuma123_spark_ogre_fase3_pendiente_validacion_manual.3ds`.
Tamaño 2.147.483.648 bytes (2 GiB), SHA-256
`34c2e9a3e79d7561ece763e41909f06db97601c98dbcd1d879100b38ddf4bc6e`.
Manifiestos `manifest.json`, `integration.json` y `qa.json` en
`work/ie3/shared/candidatas/spark_ogre_integrada_fase3/`; informes por perfil
con origen, transición y pendientes en `spark/` y `ogre/`.

Spark: 31.833/34.100 oficiales referenciados admitidos/reextraídos (93,3519 %):
14.566 nuevos, 17.231 heredados oficiales, 23 correcciones y 13 originales ya
idénticos. El decimocuarto original legado está fuera de 301D y sigue literal.
Quedan 2.217 controles, 41 encoding y nueve layout; además 1.605 sin fuente y
3.440 ambiguos. Los 2.217 controles heredados de v7 se preservan, no se cuentan
como nueva emisión certificada. Otros 5.095 mensajes pendientes siguen JP.

Ogre: 34.212/36.705 oficiales referenciados admitidos/reextraídos (93,2080 %):
34.198 nuevos y 14 originales idénticos. Pendientes 2.437 controles, 47 encoding,
nueve layout, 1.758 sin correspondencia y 2.338 ambiguos; 6.589 mensajes JP
preservados. Ambas colisiones de identidad se resolvieron. Se habilitaron
471/499 mensajes con controles, sin cambiar encoder ni tipografía para forzar
los restantes. Denominadores legado: 39.189/40.852 grupos, con 34.101/36.749
oficiales disponibles; no se ocultan los casos fuera de 301D.

Nombres cortos: 11 nuevos Spark y 2.372 Ogre, con 2.345 heredados Spark y cinco
originales ya oficiales por versión. Objetos: 786/789 campos de nombre frente
al JP; objetivos/lugares/nombres ocultos SSD: 95/104 campos distintos del JP,
más 232/355 idénticos. Solo se aceptan identidades estructurales y capacidades
demostradas. Menús generales, ayudas, descripciones, técnicas, cadenas y gráficos
siguen incompletos, documentados por recurso/contrato pendiente: no se copiaron
tablas europeas completas. Bomber sigue sin corpus ni validación propia.

Validación final: **1.154 tests passed**, 17 ROM deselected, ocho subtests;
**cinco tests oficiales passed**. Guardias bloqueados/git/shims correctas:
641 rastreados, cero prohibidos, 31 shims puros; lint pasa. Round-trip de ocho
pares PKB/PKH y 11.669 eventos, centinelas/colas FF, secundarios, bytecode,
límites, referencias y reextracción exacta. QA post-encoder de 66.045 mensajes
sin truncamiento, con máximos de 151 bytes expandidos incluido NUL, 51 glifos
por línea y 322 px de tinta. Las excepciones oficiales 3070, inline/huérfanos y
tres referencias Ogre a recurso ausente se conservan e inventarían.

Se reextrajo la ROM final: las 15.547 entradas del archive, CRO y ExeFS coinciden;
solo doce entradas cambian frente al piloto, ninguna fuente. La tipografía del
cuerpo y los cinco congelados permanecen intactos. El renderer offline revisado
no equivale a ejecución: nombres con espacios y otras UI FONT8 requieren prueba.
Advertencia cosmética preexistente de `git diff --check` en `reinsert.py:284`,
sin tocar ese componente aprobado para eliminarla.

Cobertura, pendientes accionables, comandos y pruebas manuales en
[IE3_FASE3_INTEGRACION](docs/IE3_FASE3_INTEGRACION.md). Se entrega como candidata,
no verificada en juego, y se espera la prueba manual del usuario. No hubo push,
PR, publicación ni borrado de originales o guardados.

## 2026-09-19 — Fase 2: consumidor demostrado y ROM piloto de referencias

Se recuperó v7 como referencia de legibilidad aceptada **solo en los casos
probados**. Se conservaron los cambios locales, la tipografía, fuentes, encoder,
È, métricas, wrapping y CRO v7; no se reactivó `--crecer`. Dos auditorías
independientes de solo lectura contrastaron consumidor y estructura real.

El avance decisivo fue identificar `301D → @offset,longitud → base evet + offset`.
Los campos son bytes de lectura, no posición visual. El cargador SSD enlaza por
ID/slot físico; el consumidor avanza por tamaño u8 solo para argumentos tipo 3.
Se implementó un núcleo de reconstrucción compartido Spark/Ogre, con perfiles,
trazabilidad JP/ES, límites reales, conservación literal de secundarios y código,
recalculo de referencias, compresión por entrada y paquetes/B123. También se
preservan las colas PKH parciales FF, no solo el centinela completo. Evidencia,
alternativas, matices y límites en [EXPLICACIONES_CODEX](EXPLICACIONES_CODEX.md)
y [IE3_FASE2_REFERENCIAS](docs/IE3_FASE2_REFERENCIAS.md).

Se recalcularon las cifras; no se reciclaron porcentajes históricos. El plan
offline emite/reextrae 31.362 Spark y 33.711 Ogre, pero **no se activó en bloque**.
Quedan controles/argumentos, encoding, páginas y correspondencias pendientes,
incluidos cinco diálogos inline por juego y tres referencias Ogre a evet ausente.
Los informes completos y sus denominadores legado/consumidor están en
`work/ie3/shared/fase2/plan_spark_emision` y `plan_ogre_emision`.

Se generó específicamente como **piloto estructural aislado sobre baseline v7**:
`work/build/inazuma123_spark_fase2_piloto_referencias_pendiente_validacion_visual.3ds`.
Etiqueta: **Spark Fase 2 — piloto de referencias — pendiente de validación visual**.
2.147.483.648 bytes; SHA-256
`967107bd55f8f6bb18df896f2564296f0b908163d5fe12a6027cacaad7644e79`.
Manifiestos `manifest.json`, `pilot.json` y `qa.json` en
`work/ie3/rayo_celeste/candidatas/spark_fase2_piloto_referencias/`.

Solo se insertó la primera intervención de Maserati (`32500100`, offset original
100, instrucción 1184), antes rechazada. Su registro crece 92→120 bytes y su
grupo 116→144; siete referencias se actualizan. Se verifican **102.418 registros
restantes idénticos a v7**, bytecode intacto, cinco componentes de código congelados
para esta fase y seis entradas de fuente sin cambios. Los 14.616 rechazados
permanecen intactos. Reextracción del piloto: 19.471 cuerpos traducidos distintos
del original (57,098 %) y 14 originales ya idénticos a ES: métrica legado
19.485/34.101 (57,1391 %). Se registraron **23 alertas de correspondencia heredadas
de v7**, conservadas para aislar el piloto, sin contarlas como validación nueva.

Pruebas: **1.098 passed**, 15 ROM deselected, 8 subtests; **3 pruebas oficiales
seleccionadas passed** (consumidor ARM y fuentes). Guardias bloqueados/git/shims
correctas: 641 rastreados, 0 prohibidos, 31 shims puros. Lint nuevo pasa.
Round-trip literal de ocho pares PKB/PKH y 11.669 eventos JP/ES, más simulaciones
de crecimiento de ambos juegos. La ROM final se reextrajo: archive y sus **15.547
entradas**, CRO exacto de v7 y ExeFS original coinciden. No se detectó truncamiento.

**No se ha ejecutado ni verificado visualmente este piloto.** El usuario debe
hacer arranque limpio sin mods/savestates anteriores y revisar Maserati completo,
respuesta de Bianchi, diálogos posteriores y siguiente evento. Se detiene el
trabajo aquí hasta esa prueba, sin activación masiva ni otra investigación amplia.
No hubo push, PR, publicación, cambios en IE1/IE2 ni borrado de originales.

El chequeo de whitespace mantiene un aviso preexistente de línea vacía EOF en
`comun/reinsert.py:284` y los avisos LF/CRLF de Git; no se alteró el archivo
congelado para limpiar ese detalle. Las guardias específicas sí pasaron.

## 2026-09-19 — Continuación IE3: límites seguros y arquitectura

Se partió de un árbol con trabajo local IE3 sin confirmar. Se conservó ese
estado y se revisaron `AGENTS.md`, README, formatos, extracción, traspaso y la
bitácora de diálogo antes de editar.

La comparación de ramas confirmó que `estado-ie2-cajas` ya está integrada:
`f3b48eb` es ancestro de `450fb11`; no se hizo merge ni cherry-pick. La solución
IE2 aportó el patrón SSD/PKB/PKH y de validación, pero no se copió como si IE3
fuera idéntico. IE-repack se revisó como referencia para manifest de archivos,
SHA antes/después y reconstrucción RomFS/IVFC; no resuelve SSD ni wrapping, por
lo que no se duplicó como un repacker paralelo.

La evidencia local rectificó una hipótesis anterior: 0x301D es diálogo y 0x301A
no almacena offsets de `evet`. Se retiró la ruta insegura de crecimiento y
recolocación de offsets, y `--crecer` ahora se rechaza explícitamente. La ruta
segura conserva tamaño total, registros y offsets por grupo. Se añadió una
prueba sintética para estas invariantes y una prueba de rechazo de texto que no
cabe, sin truncar.

También se trasladaron `ie3_pipeline` e `ie3_verificar_offsets` al paquete
`ie123kit`, con shims generados para mantener la CLI, porque los scripts sueltos
en `tools/` hacían fallar la guardia de arquitectura. No se borró ningún
original, extracción, ROM ni build. Spark sigue siendo la prioridad y la
prueba visual de su prólogo queda como siguiente evidencia necesaria.

## 2026-09-19 — Candidata segura y diagnóstico Spark

Se generó `work/ie3/rayo_celeste/candidatas/spark_segura_pendiente_validacion_visual.fa`;
es candidata pendiente de validación visual, no build verificada. La ruta segura
inserta 19.050/34.101 traducciones Spark elegibles (55,86 %) y rechaza 15.051:
13.840 por presupuesto binario y 1.211 por una caja visual de tres líneas. El
reporte reproducible está en `work/informes/spark_rechazos_conservador/`, con
CSV/JSON y 18 casos seleccionados, incluidos 32010100, 32010200 y 32010300.

La comparación oficial muestra que Level-5 elimina ruby y recompila `0x301D`;
no es una prueba para reactivar el crecimiento aislado. También se detectó y
corrigió un bug de centinela PKH que afectaba el alineado automático al
reconstruir paquetes. La siguiente prueba visual debe comprobar los eventos de
prólogo, signos españoles, acentos, ñ, inicios perdidos, cajas vacías, saltos y
líneas que permanecen en japonés.

## 2026-09-19 — Build Spark segura para validación visual

Se construyó específicamente la baseline conservadora ejecutable
`work/build/inazuma123_spark_segura_pendiente_validacion_visual.3ds` a partir
de la candidata segura. La imagen está marcada por su nombre como **pendiente
de validación visual**; no se ha probado en emulador ni consola y no se
considera verificada.

La reconstrucción rehízo RomFS, CXI y NCSD con 3dstool y las cabeceras/ExeFS
originales. `archive.fa` solo se sustituyó durante ese proceso y fue restaurado:
su SHA-256 de origen sigue siendo
`be78bb7290d87edd2ac8cd012edc6a8473868dbf1f8a41e2d3c081e4db3864d4`.
La build resultante es NCSD, TitleID `00040000000BB800`, producto `CTR-P-AETJ`,
con SHA-256 `820d7f1e6d107aadbacfe503a117d1e05cd5e07a4010e70e6b020b6fd5f27df5`.

Antes de construir pasaron las pruebas de PackNum y reinserción, el verificador
de offsets (cero diálogos desplazados), las guardias de congelados/Git y los
shims. La ruta inserta 19.050/34.101 textos Spark elegibles (55,86 %) y deja
15.051 en japonés de forma intacta. Se detiene el trabajo aquí a la espera de
la prueba visual solicitada.

## 2026-09-19 — Spark conservadora v2: corrección de glifos y baseline visual

La primera baseline arrancaba y mostraba los diálogos españoles, pero `¡`,
acentos y otros caracteres se veían como glifos incorrectos. No era un error
de wrapping ni de bytes: `sjis_portador` emitía los portadores griegos
correctos, mientras que `archive.fa` contenía los BCFNT japoneses sin parchear.
La referencia funcional v106 confirmó los hashes esperados de `font_patch`.

El pipeline aplica ahora el parche reproducible y de igual tamaño de
`FONT12.bcfnt`, `FONT12T.bcfnt` y `FONT8.bcfnt`, tras comprobar que la fuente
de trabajo coincide byte a byte con la JP. Se añadió `ie123kit.ie3.comun.charset`
y su prueba: verifica `¡ ! ¿ ? á é í ó ú Á É Í Ó Ú ñ Ñ ü Ü`, sus bytes SJIS,
portador, CMAP y hash de las tres fuentes finales. El `archive.fa` extraído de
la ROM reconstruida coincide byte a byte con la candidata.

El rótulo `フィディオ` se localizó fuera de `evet`, en
`inazuma3/data_iz/logic/unitbase.dat`: `0x301A` usa el ID de hablante. Solo se
actualizó el campo corto observado, de 16 bytes, a `Bianchi`, equivalente
oficial ES en el mismo registro; no se abrió una auditoría de menús o nombres.

Se generó `work/build/inazuma123_spark_conservadora_v2_pendiente_validacion_visual.3ds`.
Sigue **pendiente de validación visual**, no verificada. Spark insertó
19.059/34.101 (55,89 %) y rechazó 15.042 diálogos sin modificarlos. Cero
diálogos quedaron desplazados; el parser recorrió 12.804 eventos (6.980 SSD,
5.824 planos) y preservó dos centinelas PKH. Pasaron 1.024 tests (12 deselected,
8 subtests), las guardias y los shims. `archive.fa` base fue restaurado y
conserva SHA-256 `be78bb7290d87edd2ac8cd012edc6a8473868dbf1f8a41e2d3c081e4db3864d4`.

## 2026-09-19 — Spark conservadora v3: layout y nombres, baseline visual

Se construyó `work/build/inazuma123_spark_conservadora_v3_pendiente_validacion_visual.3ds`
como baseline conservadora para prueba visual. Lleva la candidata Spark y el CRO
de ancho ya verificado; la build v2 omitía ese CRO y por ello el motor mantenía
22 caracteres por línea pese a que el maquetador preparaba 42. Esta v3 no cambia
crecimiento, menús, Bomber u Ogre, y no se considera verificada.

La imagen mide 2.147.483.648 bytes y su SHA-256 es
`899ebce0e93e406e78918e6da92dd96339480fd40c99e4cc02243b80baac31b9`.
Inserta 19.059/34.101 diálogos Spark elegibles (55,89 %) y mantiene 15.042 en
japonés cuando la inserción conservadora no cabe. Además localiza 2.345 nombres
cortos oficiales de hablante, sin modificar campos largos ni registros no
equivalentes.

Pasaron el verificador de charset/fuentes, el de offsets (0 desplazados), el
recorrido de 6.980 SSD con PKB/PKH, el centinela Bianchi y las guardias de
congelados, Git y shims. Queda un warning conocido: `È` y otros seis caracteres
italianos no están incluidos en el plan de fuente congelado; se preserva el `?`
actual como bloqueo visible y no se lo sustituye por `¿`. Se detiene aquí hasta
recibir la prueba visual solicitada.

La extracción independiente de la ROM final confirmó dentro de su RomFS el
`archive.fa` con SHA-256 `fee9914509896acd1ade410a086d7b3521e62b38d3f86319da05e16f68783550`
y `cro/ina_main3ogre.cro` con SHA-256
`c17a5175cedb441f490d087229bc241d989bc56f54cd2451c8bc4a3d5da0ed43`.

## 2026-09-19 — Spark conservadora v4: tipografía europea y `È`

La comparación directa de CWDH descartó que el problema fuese solo de wrapping:
`FONT12` JP hacía que los dos textos del prólogo midieran 329/371 px, frente a
239/270 px en la fuente oficial europea. Se añadió
`ie123kit.ie3.comun.tipografia`, que conserva el BCFNT JP y sus glifos japoneses,
pero traslada 111 glifos y métricas latinos oficiales a `FONT12`, alineados por
baseline y sin cambiar el tamaño del recurso. El parche congelado permanece
intacto.

El wrapping IE3 usa ahora esas métricas. El barrido completo de las 34.691
traducciones elegibles dio un máximo general de 51 caracteres dentro de 354 px;
por ello el CRO usa 0x250 para el límite y 0x270 para la rejilla. Las líneas por
caja siguen siendo tres y no se reactivó crecimiento. `È` usa el portador libre
U+03A0 (`83 AE`), ausente de todos los registros de texto JP comprobados. El
reinsertor rechaza de forma conservadora cualquier otro carácter no codificable,
en vez de degradarlo silenciosamente a `?`.

Se generó la ROM pendiente de validación visual
`work/build/inazuma123_spark_conservadora_v4_pendiente_validacion_visual.3ds`,
de 2.147.483.648 bytes y SHA-256
`3771f9f19c0e601023505be8d07760979ba0e86d961b869d845b8553ecf295f4`.
Inserta 19.484/34.101 diálogos Spark (57,14 %) y deja 14.617 rechazados intactos;
los 571 rótulos `eve` elevan el total insertado a 20.055. Los 2.581 registros de
nombres produjeron 2.345 cambios verificados, 11 descartes estructurales, 2 de
encoding, 0 de tamaño y 223 coincidencias que no requerían cambio.

Pasaron 1.035 tests, 12 deseleccionados y 8 subtests; las guardias de congelados,
Git y 31 shims; el verificador de 80.041 offsets; 6.980 SSD y dos centinelas PKH.
La extracción de la ROM final confirmó dentro del RomFS `archive.fa` con SHA-256
`a56720451b461314664f0395293235a200ec5c6cdc892776ab5296b93eb69b82` y
el CRO con `1c2db0af506077b1e94f1faa83859643cb35ca68ee0665db6872d811580f3061`.
No se hizo push y se detiene el trabajo hasta la siguiente prueba visual.

## 2026-09-19 — Spark conservadora v5: recalibración legible y nombres FONT8

La prueba visual de v4 confirmó que el trasplante de la tipografía europea fue
demasiado agresivo: el texto entraba, pero las letras aparecían juntas/recortadas;
los nombres no mejoraban porque 0x301A los dibuja por una ruta FONT8 separada.
La `È` observada era correcta y sufría el mismo problema, no una confusión con
`¿`. La hipótesis inicial de tomar un punto medio se descartó como criterio.

FONT12 conserva ahora el raster japonés legible y solo recalibra CWDH con una
regla derivada de ambas fuentes: el mayor entre el avance oficial y la extensión
declarada del glifo JP. La narración de control queda en 272 px (329 JP, 239
v4/oficial) y el diálogo de Paolo en 311 px (371 JP, 270 v4/oficial); siguen
entrando dentro de los 354 px. `È` mantiene U+03A0/`83 AE`, pero su raster se
construye desde la `E` JP con grave y usa el mismo avance seguro.

Para los nombres se confirmó que `Bianchi` tiene exactamente los mismos bytes en
la candidata y la oficial; la diferencia era el renderer FONT8 a paso fijo de
10 px. Se aplicó la técnica de bigramas ya validada en IE1 mediante un plan general
de los 96 pares más frecuentes de todos los nombres oficiales, sin excepciones por
personaje. Se compactaron 2.223/2.345 nombres (4.160 pares): `Bianchi` pasa de 7 a
5 celdas, `Generani`/`Maserati` de 8 a 5 y `Diavolo` de 7 a 6. El tamaño de
`unitbase.dat`, sus registros y sus campos permanecen invariantes.

Se generó `work/build/inazuma123_spark_conservadora_v5_calibrada_pendiente_validacion_visual.3ds`
como nueva candidata, todavía **pendiente de validación visual**. Mide
2.147.483.648 bytes y su SHA-256 es
`d01cbbeba83e4117a86bb77a565efeee31e86a17e6a37675797e3c85ef2fee1c`.
El `archive.fa` intermedio mide 1.327.809.120 bytes y tiene SHA-256
`16620b497b1238b4b58af7153a04e1f846858829a00d5e4fddbfcf4a6d5510ca`;
el CRO final conserva `1c2db0af506077b1e94f1faa83859643cb35ca68ee0665db6872d811580f3061`.

Pasaron 1.036 tests (12 deseleccionados), las guardias de congelados/Git/31 shims,
6.980 SSD, 5.824 tablas evet, dos centinelas PKH y el verificador de 80.041
offsets. Spark inserta 19.484/34.101 diálogos (57,14 %), mantiene 14.617 rechazos
intactos y presenta cero truncamientos. Los 571 rótulos `eve` mantienen el total
en 20.055 inserciones. La extracción independiente de la ROM confirmó que su
archive y CRO coinciden con la candidata. No se hizo push; el trabajo se detiene
para esperar la prueba visual.

## 2026-09-19 — Spark conservadora v6: métricas finas y nombres legibles

Las capturas de v5 confirmaron dos defectos independientes. En el cuerpo, el
raster JP se había combinado con CWDH reducidos hasta dejar sin respiración a
`i`, `l`, `r`, `t` y vocales; por eso los pares de `cierto`, `Italia`, `Paolo`,
`fútbol`, `arte`, `botas` y `terribile` se solapaban aunque los strings estuvieran
completos. `È` sí usaba U+03A0/`83 AE` y mostraba el grave: no era un fallo de
mapping distinto. En la pestaña, los bigramas FONT8 comprimían dos letras en un
solo glifo y fusionaban `Maserati` y `Bianchi`.

Se sustituyó la mezcla v5 por una corrección general. FONT12 traslada juntos el
raster y CWDH oficiales europeos y añade el píxel de respiración ya establecido
por el proyecto; la diferencia de baseline se absorbe fusionando el borde sin
perder píxeles. Los acentos usan su métrica oficial propia (`í`, por ejemplo,
mide 5 px y no 3). FONT8 eliminó todos los bigramas, conserva una letra por
carácter y adapta únicamente los 65 glifos latinos presentes en nombres oficiales
compatibles. `Maserati` y `Bianchi` vuelven a almacenar exactamente sus ASCII
oficiales. No se tocó crecimiento, PackNum fuera de la ruta conservadora, menús,
Bomber, Ogre ni audio.

Se generó la candidata
`work/ie3/rayo_celeste/candidatas/spark_conservadora_v6_metricas_finas_pendiente_validacion_visual.fa`,
de 1.327.809.120 bytes y SHA-256
`6a5962de9d946864bb04950843c81ef14ee6551085246ccf8afd99b73110e1de`.
La ROM completa pendiente de validación visual es
`work/build/inazuma123_spark_conservadora_v6_metricas_finas_pendiente_validacion_visual.3ds`,
de 2.147.483.648 bytes y SHA-256
`c006fad335d1729e01806ce5d6d9b669196e6765edded4eedcddbd7f443be7f7`.
No se considera verificada en juego.

La cobertura permanece en 19.484/34.101 diálogos Spark (57,14 %), con 14.617
rechazos byte-idénticos al original y 571 rótulos `eve` (20.055 inserciones en
total). La reinserción se reprodujo exactamente para 2.849 eventos; se recorrieron
6.980 SSD, 5.824 tablas planas, dos centinelas PKH y 80.041 offsets sin fallos.
Pasaron 1.037 tests (12 deseleccionados), charset/fuentes y las guardias de los
cinco congelados, 641 ficheros Git y 31 shims. La extracción independiente de la
ROM confirmó el archive anterior y el CRO
`1c2db0af506077b1e94f1faa83859643cb35ca68ee0665db6872d811580f3061`.
El archive base conserva SHA-256
`be78bb7290d87edd2ac8cd012edc6a8473868dbf1f8a41e2d3c081e4db3864d4`.
No se hizo push; se detiene el trabajo a la espera de la prueba visual v6.

## 2026-09-19 — Spark segura v7: corregir la regresión visual de v6

El usuario probó v6 y la consideró un paso atrás respecto de v5: nombres
torcidos y muy separados, y diálogo menos legible. Se rectifica el diagnóstico
anterior: los tests verificaban con el mismo lector defectuoso que escribía las
fuentes y no modelaban el centrado adicional del motor. No bastaba ajustar anchos.

Se comprobaron dos causas en el ejecutable JP y las fuentes originales:
direccionamiento erróneo de celdas europeas (pitch y origen +1) y centrado
individual `trunc((FINF.width-charWidth)/2)`, con FINF.width 15/11 para
FONT12/FONT8. El segundo término se compensa mediante left CWDH, sin nuevos
parches del ejecutable. La adaptación ahora parte del original, conserva todas
las muestras por traslación estricta, no fusiona bordes y no crea bigramas.
Se reutilizó el lector congelado mediante una especialización fuera de él;
los cinco congelados siguen intactos. La auditoría independiente se realizó
con un subagente de solo lectura conforme a AGENTS.md.

111 glifos FONT12 y 73 FONT8 adaptados. Comparada con v6, la candidata solo
cambia esas dos entradas de archive.fa; los textos, nombres cortos, paquetes,
FONT12T y demás recursos son idénticos. No se reactivó crecimiento ni se
abrieron líneas sobre menús, Bomber u Ogre. El usuario confirmó que prueba ROM
completa, por lo que se generó una nueva ROM y no un mod de Azahar.

Candidata conservadora para la nueva prueba visual:
`work/ie3/rayo_celeste/candidatas/spark_conservadora_v7_celdas_centrado_pendiente_validacion_visual.fa`,
1.327.809.120 bytes, SHA-256
`5ae93aee9af3dc5bd947078a629ec5c6407c1df1e3bde4c66c33d865ad5a4fbd`.

ROM completa **Spark segura v7 — pendiente de validación visual**:
`work/build/inazuma123_spark_conservadora_v7_celdas_centrado_pendiente_validacion_visual.3ds`,
2.147.483.648 bytes (2 GiB), SHA-256
`fb846ce1a733bb3aa347cc45af817bf1722194b23e13776f38c2ef9d82df9ab1`.
Manifiesto en
`work/ie3/rayo_celeste/candidatas/spark_conservadora_v7_celdas_centrado/manifest.json`,
con `runtime_verified: false`. Es una baseline conservadora para prueba visual,
no una versión verificada en juego.

Validación: 1.060 tests sin ROM; 2 pruebas contra fuentes oficiales (27 tests
tipográficos al contar también las pruebas unitarias). 6.980 SSD, 5.824 tablas
planas, dos centinelas PKH y 80.041 offsets correctos. Guardias de congelados,
Git y 31 shims correctas. Charset y hashes FONT12/FONT8:
`7908857da6b8055c7847635c8449f1b916a00bca12997a4d2af4b67eb3be4466` /
`53a6a8a8c36c74a205749847ed686659b721fcf35170099923e17f22d97cecbb`.

Cobertura inalterada: 19.484/34.101 diálogos (57,14 %), 14.617 rechazados
intactos y 571 rótulos, total 20.055 inserciones. Una lectura independiente
compara el texto completo, no solo la salida del reinsertor: cero truncamientos;
los rechazos conservan también el relleno original. 14 traducciones coinciden
ya con el original y no deben confundirse con rechazos por comparar solo bytes.

Warnings: la mejora visual sigue pendiente de prueba; fuentes compartidas y
rutas con otros tamaños no validadas en ejecución. Ü mayúscula sigue sin soporte
en el encoder histórico y no aparece en el corpus insertado. `git diff --check`
avisa del blanco final preexistente en `reinsert.py`; no se cambió dicho archivo.
No se hizo push ni se eliminó ninguna referencia original o v5.

La extracción independiente de la ROM terminada confirma archive.fa
`5ae93aee…ad5a4fbd` y CRO `1c2db0af…f3061`. ExeFS es byte-idéntico a la
base; el archive original conserva `be78bb72…64d4`. Los tres pasos de
3dstool terminaron con código 0 y sin warnings. Sus temporales y los de la
comprobación se retiraron automáticamente; no se borraron datos del proyecto.
Trabajo detenido aquí a la espera de la prueba visual v7 del usuario.
