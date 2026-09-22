# IE3 fase 4: colocación, nombres e interfaz

**Spark + Ogre Fase 4 — pendiente de validación manual del conjunto.**
No se ha ejecutado en emulador ni hardware. Las imágenes son simulaciones.
El usuario no dispone de capturas actuales/europeas nativas: no se inventa una
comparación visual entre ejecuciones. Sin push, publicación, PR ni eliminación
de originales o guardados. Bomber no está certificado.

## Artefacto y referencia

ROM completa: `work/build/inazuma123_spark_ogre_fase4_pendiente_validacion_manual.3ds`.
Tamaño **2.147.483.648 bytes (2 GiB)**; SHA-256:
`c020a022ef6fc8026c4d5040968e3e705ea77737507724b901bead8113c0b645`.

Referencia exacta fase 3, ROM SHA-256
`34c2e9a3e79d7561ece763e41909f06db97601c98dbcd1d879100b38ddf4bc6e`.
No se mezcla con una variante visual posterior. Se construyó una sola ROM nueva.

Manifiestos en `work/ie3/shared/candidatas/spark_ogre_integrada_fase4/`:
`manifest.json` identifica ROM/reextracción; `revision.json`, transición/hashes;
`verification.json`, lectura independiente; `spark.json` y `ogre.json`, cambios
y pendientes por identidad; `graphics.json`, `literals.json`, `names.json` y
dos simulaciones. Un `archive.fa` no es la entrega ejecutable.

Reextracción final: archive SHA
`4aba963e3f2d499cc2fe10c48ed469f0cea7e5251a3c8f44a8f5927f2957e193`,
CRO SHA `29b48d42ddbdf0ac5b06f82b9c61de5804001a8ef7c7e9859ab5605d1df96c06`,
15.547 entradas internas coincidentes y ExeFS original intacto.

## Desbordamiento: causa y cambio acotado

Cadena oficial: `spark:evet:32010100:00000000`, instrucción 1138,
fuente ES m0000 offset 0. Contiene **tres** puntos, no cuatro:

```text
Equipos juveniles de todo el planeta soñaban
con convertirse en campeones mundiales...
```

El medidor anterior contaba espacio ASCII de avance 3, pero el consumidor
convierte `20` a U+3000, cuyo avance aprobado es 7. El límite 354 procedía de
otra geometría; medir desde cero tampoco descontaba el origen 12. Primera
línea: avance 308, tinta relativa 0..306 y colocada 12..318; excede el interior
conservador 7..312. No se demostró tracking duplicado. Se corrige el modelo,
no el espacio, su conversión o su métrica protegida.

La cadena de dibujo nativa suma grupo 10 + posición de glifo + offset ITX 2.
El único cambio del cuerpo es CRO 3ABC8: cargar −2 en vez de +2, origen 8.
La ruta callback de texto evita expresamente la escala ×1,25 de planos
gráficos; prueba en `test_ie3_ruta_coordenadas_oficial.py` y explicación en
[UI fase 4](IE3_UI_FASE4.md). No se suman dos centrados. Caja y textura intactas:
mitades centradas 81/239, ancho 160, tiras x4/5, interior desde 6; cota 7..312
con resguardo. No se presenta como medición de la observación europea de «un píxel».

Desplazar cuatro píxeles no basta para esa primera línea (acabaría en 314).
Se reutiliza `lineas_de`, el algoritmo existente, con el medidor colocado,
sin páginas nuevas ni pérdida de contenido. Resultado de tres filas:

```text
Equipos juveniles de todo el planeta
soñaban
con convertirse en campeones mundiales...
```

| Caso | Tinta colocada fase 3 | Tinta colocada fase 4 |
| --- | --- | --- |
| Equipos juveniles… | 12..318 / 12..296 | 8..253 / 8..60 / 8..292 |
| Unos meses… | 12..313 | 8..309 |
| Paolo | 12..259 / 12..101 | 8..255 / 8..97 |
| È terribile… | 12..258 / 12..187 | 8..254 / 8..183 |

Cada espacio está medido en `colocacion_simulacion.json`: avance 7, tracking 0,
sin eliminar separadores oficiales. Altura raster 16, baseline textura 13,
interlineado adicional 3 y posiciones relativas 0/21/43, conservando 115/100.
La Y inicial de la imagen es ilustrativa: no valida marco vertical en ejecución.
Se reservan conservadoramente 16 px del extremo de la tercera fila para el
indicador; su posición final animada requiere prueba manual.

Comprobados 31.141 estáticos Spark y 33.456 Ogre; 835/932 cambian saltos.
**221/257 casos no caben o no están modelados con estas restricciones y quedan
literales como fase 3**: pueden seguir desbordando. No se cuentan como corregidos.
Los 471/499 admitidos con controles y los pendientes previos no se remodifican.

## Maserati: límite lógico frente a capacidad física

`Maserati` está completo, con NUL y sin salto en su campo de 16 bytes. La ruta
lógica usa 8 por carácter y tracking 1: el octavo exige 71, mayor que 64.
La tinta proporcional aprobada ocupa 44 px y cabe en el recurso físico 64.
Cambiar directamente 64 por 80 alteraría además el cálculo de terminación del
buffer: esa propuesta se descartó.

Solo el comparando temporal del llamador de pestaña pasa a 134 (15 glifos),
sin cambiar argumento 64 ni buffer 512. Guardia previa al dibujo reserva
32 bytes para terminador y evita comando 16 incluso ante entrada inválida.
Otros llamadores y selecciones de color conservan comportamiento: intérprete
ARM, ASLR y entradas extremas. No se abrevia ni amplían campos. Detalle en
[geometría de nombres](IE3_NOMBRE_GEOMETRIA_FASE4.md).

Auditoría final: 8.770 filas de cinco tablas y 385 nombres SSD 3019; todos NUL,
≤15 comandos y ≤64 px de tinta. Se modelan los 29 nombres con espacios por
perfil (U+3000, avance 5 + tracking 1). Ejemplos de 7/8/9 W que exceden 64 son
negativos visuales, no se declaran válidos. Origen/pestaña, listas y otras
interfaces FONT8 requieren ejecución manual.

## Emisión real: categorías separadas

| Categoría | Spark | Ogre |
| --- | ---: | ---: |
| Diálogos oficiales referenciados admitidos, conservados | 31.833/34.100 (93,3519 %) | 34.212/36.705 (93,2080 %) |
| Traducciones 301D nuevas en esta fase | 0 | 0 |
| Nombres cortos nuevos en fase 3, conservados | 11 | 2.372 |
| Nombres de objetos distintos de JP, conservados | 786 | 789 |
| Campos SSD visibles distintos de JP, conservados | 95 | 104 |
| Descripciones de objetos nuevas | 673 | 673 |
| Nombres / descripciones de técnicas nuevos | 398 / 382 | 398 / 382 |
| Descripciones de tácticas nuevas | 21 | 21 |
| Descripciones de jugadores nuevas | 778 | 783 |
| Títulos de equipo nuevos | 20 | 20 |
| Títulos de cadenas nuevos | 7 | 8 |
| Condiciones de victoria / apertura nuevas | 38 / 27 | 38 / 25 |

No hay porcentaje global de interfaz: no existe denominador completo demostrado.
Vacíos y ya idénticos se separan de inserciones en los JSON.

Menú común: 12 etiquetas oficiales en 7 bloques: **Menú, Jugadores, Inventario,
Estrategias, Datos, Recursos, Guardar, Maestro, Niv. equipo, Título, Pasión,
Amistad**. Fuente GetString/ID de ExeFS europeo, comprobada independientemente
para Spark y Ogre. No son traducciones inventadas.

Gráficos: 64 ayudas modificadas y 25 atlas de 6 paquetes, 70 recursos/89 atlas.
Píxeles oficiales exactos, QNA/formato/dimensiones iguales, sin redibujar ni
compresión con pérdida. SSZL cambia tamaño comprimido tras demostrar su lector;
tamaño descomprimido y tablas intactos. Paquetes: Spark `sp_move_b`,
`organization_b`, `formation_b`; carpeta Ogre `item_b`, `organization_b`,
`status_t`. Compartir ruta no certifica Bomber ni un menú totalmente localizado.
Detalle: [tablas](IE3_TABLAS_FASE4.md), [literales](IE3_LITERALES_FASE4.md),
[gráficos](IE3_UI_FASE4.md).

## Pendientes concretos

- Diálogos: 5.095/6.589 japoneses, además 2.217 Spark heredados pendientes de
  cota dinámica. Entre oficiales referenciados, 2.267/2.493 no admitidos.
  No confundir esos universos con los 221/257 pendientes de colocación nuevos.
- SSD objetivos/rótulos: 506/680 pendientes de fase 3 (identidad 332/378,
  capacidad 174/302); cuerpo ≤JP, sin extrapolar 301D.
- Nombres: 219/203 IDs reservados y dos nombres no codificables por perfil;
  NPC/ex_binder auditados, no declarados traducidos.
- `item.STR`: 28/32 identidades y 107 descripciones por capacidad;
  `command.STR`: 5 por capacidad, 1 por encoding; `tacticscmd.STR`: 21 nombres
  sin lector demostrado; `unitbase.STR`: 3 descripciones por capacidad.
- Contador superior `Jugadores`, CRO 1F9E70: necesita 10 bytes, dispone 8;
  se preservan JP/sufijo/relocaciones. No abreviatura inventada.
- `BattleRouteTitle.dat`: 2 títulos por capacidad; `OpenCondition.dat`: 3/5
  campos por capacidad. Premios/condiciones jugables Practice* no modificados.
- `games.STR`: común EU idéntico a JP, sin fuente española.
- 19 ayudas excluidas por funciones regionales/red/Ogrelink, cuadros vacíos,
  semántica no demostrada o PT/PE incompatibles. `equip_parts_b02` invierte
  L/R/flechas y queda intacto. Véanse IDs y motivos en el documento gráfico.
- Otros gráficos: QNA/layout/formato distinto o UV sin modelar. Ayudas
  superiores `syup_bg00/01/02`: JP formato 12, ES 2; no transcodificar con pérdida.
  No quedan completas todas las pantallas de sistema/guardado.
- Encaje en widgets/páginas de UI nueva pendiente: no se valida por el medidor
  del diálogo, aunque el texto y campos binarios se conserven completos.

## Protección y validación

Seis recursos `font/` idénticos antes/después, hashes en revision y QA.
SHA-256 principales, iguales a fase 3:

- FONT12: `7908857da6b8055c7847635c8449f1b916a00bca12997a4d2af4b67eb3be4466`.
- FONT8: `53a6a8a8c36c74a205749847ed686659b721fcf35170099923e17f22d97cecbb`.
- Encoder: `f369684028834a5fc75fb190cff890e0cb95bcbb79c2c0ad6d9b72aa7be86aee`.

Tipografia, ancho_ventana, reinsert, referencias, paquetes y controles idénticos
al plan fase 3; cinco congelados intactos. Sin cambio de raster, CWDH, escala,
bearing ni compensación de centrado.

- Suite sin ROM: **1.319 passed, 24 deselected, 8 subtests**.
- Tests IE3 con originales: **13 passed** (coordenadas, consumidor, tipografía,
  límite ARM de nombres, tablas, literales y gráficos).
- Guardias bloqueados/git/shims correctas: 641 rastreados, 0 prohibidos, 31 shims.
  En Windows se usa `-X utf8`: una repetición sin ese indicador falló al imprimir
  «lógica» por la consola cp949; se repitió correctamente con UTF-8, sin alterar
  ni omitir ninguna comprobación.
- SSD/PKB/PKH: roundtrip literal previo, reconstrucción y reextracción;
  centinela PKH y colas incluidos en regresiones de la suite.
- Lectura independiente: 79.946 referencias, 210.242 registros, 1.767 reflujos
  exactos; secundarios/pendientes restantes literales. Excepción original Ogre
  de evet ausente intacta. Ningún truncamiento aceptado.
- 94 recursos de archive cambian frente a fase 3; los demás idénticos por hash.
- Lint de módulos/tests fase 4 pasa. Lint global conserva 10 avisos anteriores
  (imports, orden de slots, subprocess/check y noqa); no se modifican fuentes
  protegidas para limpieza cosmética. `git diff --check` conserva blanco final
  previo en `reinsert.py:284` y avisos CRLF; no son fallos binarios ocultados.
- Construcción exige QA independiente vigente y reextrae ROM final completa:
  archive, 15.547 entradas, CRO y ExeFS coinciden.

## Reproducir

Desde raíz, ie123kit instalado y originales locales. Las salidas deben ser
nuevas: no sobrescribir la referencia ni esta candidata.

```powershell
python -X utf8 -m pytest tools/tests -m "not requiere_rom"
$testsIE3 = Get-ChildItem tools/tests/requiere_rom -Filter 'test_ie3_*.py'
python -X utf8 -m pytest $testsIE3.FullName -q
python -X utf8 -m ie123kit.nucleo.compat.guardia bloqueados
python -X utf8 -m ie123kit.nucleo.compat.guardia git
python -X utf8 -m ie123kit.nucleo.compat.shims comprobar
python -X utf8 -m ie123kit.ie3.fase4 --referencia work/ie3/shared/candidatas/spark_ogre_integrada_fase3 --salida work/ie3/shared/candidatas/spark_ogre_integrada_fase4
python -X utf8 -m ie123kit.ie3.fase4 --referencia work/ie3/shared/candidatas/spark_ogre_integrada_fase3 --salida work/ie3/shared/candidatas/spark_ogre_integrada_fase4 --verificar
python -X utf8 -m ie123kit.ie3.comun.build_piloto --revision --candidate work/ie3/shared/candidatas/spark_ogre_integrada_fase4 --visual-manifest work/ie3/shared/candidatas/spark_ogre_integrada_fase3/manifest.json --rom work/build/inazuma123_spark_ogre_fase4_pendiente_validacion_manual.3ds
```

## Prueba manual pendiente

1. Spark: Equipos juveniles, Unos meses, Paolo, È, ¡/¿, acentos/ñ, tres filas,
   indicador, sin cajas vacías ni bytes iniciales perdidos; avanzar al siguiente.
2. Maserati/Bianchi, nombres largos/con espacios; pestaña y listas FONT8.
3. Menú lateral/superior, puntos, título/nivel/contador; entrar/salir de las
   seis opciones, incluido sistema/guardado.
4. Técnicas/descripciones, objetos/fichas y requisitos de cadenas; estadísticas,
   efectos y controles intactos. Ayudas/gráficos y PT/PE.
5. Arranque y varios eventos Ogre. El prólogo no valida toda la campaña.

Detener cambios estructurales y esperar esta prueba; no ampliar la aprobación
previa a esta candidata ni a todas las campañas.
