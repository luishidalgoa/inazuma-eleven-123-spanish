# IE3 fase 4 — tablas textuales, independientes del diálogo

## Corrección obligatoria tras prueba visual

Los resultados de fichas/descripciones de la primera fase4 quedan **invalidados**:
el lector europeo de `unitbase.STR` usa referencia×256, no la escala JP×32.
La prueba de roundtrip anterior compartía esta premisa errónea, por lo que no
demostraba identidad de la frase. En Bianchi, fila1855, la referencia europea1855
resuelve `0x73F00`, no `0xE7E0`; texto oficial «¡El delantero estrella conocido\n
como el Meteoro Blanco Italiano!». `D71BC–D71D8` EU hace LSL8 y lee256.
JP `D2490–D24AC` hace LSL5 y lee128. No es caché ni save demostrado.

Se corrige la escala **solo de la fuente unitbase** y se añaden pruebas de
identidad→frase conocida, independientes del roundtrip. Se reconstruyen los
pools desde JP original para quitar traducciones erróneas anteriores antes
de aplicar el conjunto corregido, nunca incrementando sobre el pool defectuoso.
Las otras familias se han reauditado en su consumidor EU: item `D71FC/D7208`,
command `11B3E4/11B3F0`, tactics `132490/13249C` conservan LSL5; nombres command
`115454/115458` también. El tamaño de lectura EU256 no es la escala del puntero.

El título inicial observado no procede de `teamtitle.dat` sino `rpgtitle.STR`;
la descripción y el nombre completo de Bianchi son campos separados del corto.
La misión intro no falló por tamaño: JP ins1817 frente EU1869 no supera la
alineación previa por ID de instrucción aunque conserva ID de misión35080060.
Estos recursos/roles se investigan aparte, sin atribuirles la cobertura anterior.

## Evidencia y diseño antes de implementar

El encargo congela fuentes, métricas y encoder. La fase 3 dejó `.STR` pendiente
porque no se había seguido su lector; eso no demuestra una ofuscación adicional.
El análisis del CRO JP original demuestra ahora:

- `187BD0`: técnica ID `< 0x200`, tabla `manager+7D4`, paso `9*4=36`.
  `command.dat` es **512 × 36 bytes planos**, no 256 × 72 ofuscados.
  Las 512 filas JP/Spark ES coinciden en todos sus bytes excepto los dos u16
  de texto `+18/+1A` (hex). `10D34C–10D350` resuelve el nombre `+18 ×32`;
  `11327C–113294` resuelve descripción `+1A ×32` y lee 128 bytes por `15A0D8`.
- `D24B4–D24E4`: obtiene el objeto por `178284`, lee `u16 +2A`, multiplica32
  y pide128 bytes de `/data_iz/logic/item.STR` a `15A0D8`. El u16 final no es
  un ID regional: es la referencia regional a descripción. Se corrige así la
  hipótesis prudente de fase3; aquel adaptador lo conservaba correctamente.
- `15A0D8 → 184890 → 187764` pasa offset/tamaño a la carga del recurso.
  Los `.STR` son pools SJIS literales con ranuras alineadas32 y relleno NUL;
  no reciben el algoritmo de ofuscación de `item.dat`.
- `16543C`: táctica ID `<64`, tabla `manager+80C`, paso20. `126EB8–126ECC`
  lee descripción `u16 +0E ×32`,128bytes. Se analizará separada de técnicas.
- `games.STR` europeo no tiene entrada española; la entrada común es idéntica
  a JP. No se considera una fuente española por encontrarse en ROM europea.

Se reutilizan TextTable, el encoder aprobado y las primitivas de tablas/objetos.
Nuevo adaptador: `ie3.comun.tablas_ui`; tests `test_ie3_tablas_ui.py`.
No se modifica dat, metadatos, referencias, estadísticas ni IDs: cada sustitución
se limita a una ranura original cuyo NUL y padding se verifican, con cota adicional
del lector conocido. Un texto más largo queda pendiente, sin truncar ni mover
otras cadenas. Identidad: mismo ID físico de técnica/táctica más todos los datos
no textuales iguales; objetos además requieren metadata28:42 única en ambas
tablas y misma fila, igual que el adaptador ya auditado.

Los aliases se resuelven conjuntamente: ningún campo compartido se escribe si
algún propietario no está identificado o exige otra traducción. Se rechazan
controles no demostrados, encoding no soportado y textos sin oficial. Los
campos originalmente idénticos y vacíos no se cuentan como traducción nueva.
Se conservan todos los offsets y bytes fuera de ranuras aprobadas; reextracción
exacta y tests de conflicto, padding, tamaño, identidad y multibyte antes de
integrar. El resultado será candidato offline, no validación de pantallas.

## Ampliación independiente con lector demostrado

`unitbase.STR`: `D2490–D24AC` toma la referencia `unitbase+66 ×32` y lee128.
Se reutiliza la identidad de fichas ID+4E y metadata del adaptador de nombres;
se conserva la estadística regional+5E y el puntero JP, sin tocar `unitbase.dat`.

`BattleRouteTitle.dat`: las relocaciones internas llevan el pool `246818` a
`2B0B20` (`/data_iz/logic/BattleRouteTitle.dat`), cargado en objeto+D8.
`2462BC–246334` recorre filas de33, compara IDu8 y centinela FF, usa texto+1
en buffer32. La fuente ES usa filas64. Solo se escriben los32bytes de texto
del ID confirmado; el título que no quepa queda japonés.

`ClearCondition.dat`/`OpenCondition.dat`: pools `246810/246814`, destinos
objeto+D0/D4. `246408–24647C` recorre `17*i+64*i=81*i`, compara IDu8 con
el requisito solicitado y FF; texto+1 pasa a `1109EC`. EU128 frenteJP81.
Adaptador por ID único, no orden, conserva los255 IDs, centinela y todo lo
no textual; límite conservador79bytes+NUL de la ranura JP. No se cambian
condiciones jugables, premios ni rutas de las tablas `Practice*`.

`teamtitle.dat`: `190054–19005C` carga recurso por pool `1901D4`, reloc a
`2B4DA8`, en objeto+28. `18F804–18F814` pasa esa tabla a `15A4AC`: evalúa
los tres pares de condiciones26:32, avanza32 y limita20filas (`15A6FC–708`).
El título elegido se copia con máximo25 (`15A6E8–6F8`) y se dibuja mediante
`18F8C0`. Las20identidades de metadata26:32 son unívocas e igualesJP/ES;
se conserva índice y las condiciones. Se exige ES<25bytes y NUL, sin ampliar
el buffer ni la fuente. Este adaptador cubre títulos de equipo del menú.

## Resultado histórico de los adaptadores (fichas invalidadas arriba)

Se producen ocho payloads de recurso por perfil, sin escribir el archivo FA ni
la ROM. Desglose de campos nuevos realmente insertados:

| Familia | Spark | Ogre |
| --- | ---: | ---: |
| Descripciones de objetos | 673 | 673 |
| Nombres / descripciones de técnicas | 398 / 382 | 398 / 382 |
| Descripciones de tácticas | 21 | 21 |
| Descripciones de fichas | 778 | 783 |
| Títulos de equipo | 20 | 20 |
| Títulos de cadenas | 7 | 8 |
| Condiciones de victoria | 38 | 38 |
| Condiciones de apertura | 27 | 25 |

Pendientes: objetos 28/32 por identidad y107 por capacidad; técnicas5 por
capacidad y1 por carácter no codificable; nombres de tácticas21 porque falta
auditar su consumidor; fichas3 por capacidad; cadenas2 por capacidad;
apertura3/5 por capacidad. Ninguno se trunca. Los campos vacíos y ya iguales
se registran por separado y no se suman a traducción nueva. `games.STR` queda
bloqueado: su copia europea común es exactamente japonesa y no hay `es/`.

Pruebas finales de esta subtarea: 17 tests de tablas (15 sintéticos +2 fuentes
oficiales Spark/Ogre) y15 tests de literales (13 sintéticos +2 oficiales):
**32 passed**. Ruff correcto para ambos módulos y sus tests. Los tests locales
verifican roundtrip contra fuente oficial, lectores originales, misma longitud,
IDs/metadata/referencias conservados y rechazo intacto. No equivale a revisión
visual del inventario, fichas, técnicas o cadenas dentro del juego.

## Resultado de la corrección de escala

La nueva extracción europea genera2336 descripciones de fichas Spark y2352 Ogre
con referencia fuente×256; quedan22 por capacidad en ambos perfiles y224/208
vacías. Estos números no validan visualmente las fichas: la regresión comprobada
se protege además con la identidad Bianchi→frase española exacta, offset fuente
`73F00` y destino`32A40`. Ningún ID/estadística/referencia de unitbase.dat cambia.
Los pools se calculan nuevamente desde JP; el integrador debe sustituir el pool
de la candidata defectuosa completo con ese derivado, no conservar sus cambios.

Suite corregida:18tests (incluye prueba explícita de escalas distintas y caso
Bianchi en ambos originales europeos). Verificadas las5anclas EU además de las
anclas JP. El resto de familias conserva sus resultados al confirmar ×32 en
los lectores europeos. No se extrapola esa constatación a otras tablas.
