# Revisión por casos visibles: misión, ficha de Bianchi y título inicial

## Evidencia antes de editar

La ROM fase4 conserva el nombre completo japonés porque sólo se tradujo el
campo corto `unitbase+1C`; son dos campos distintos. Bianchi es fila1855,
ID de ficha `0C62`, completo `+0:28`, corto `+1C:16`. La fuente oficial completa
es `Paolo Bianchi`. Se reutiliza la identidad única y metadata de fase3, se
conservan el corto actual y todos los bytes desde+1C. No se modifica un save.

Su descripción real es referencia JP6482×32, EU1855×256. La escala europea
equivocada era un defecto del adaptador, no evidencia de ausencia de traducción.
La corrección y la invalidación del informe anterior están en
`IE3_TABLAS_FASE4.md`. Se requiere regenerar desde originalJP, no parchear
incrementalmente el pool que recibió textos incorrectos.

El título inicial `しろいりゅうせい` se encuentra en `rpgtitle.STR` offset`4C0`,
referencia38 de `rpgtitle.dat`, no en `teamtitle.dat`. JP/EU `rpgtitle.dat`
coinciden byte por byte:48×32, referenciau16+1E. El lector JP `1FB114` carga
esa referencia, `1FB120` multiplica32 y `1FB118` limita la lectura a19bytes;
`1FB124` resuelve `/data_iz/logic/rpgtitle.STR` en`1FB3E4`. El consumidor EU
equivalente `209720–209734` usa la misma referencia/escala con límite32.
La fuente oficial del título38 es `El Meteoro Blanco` (17bytes+NUL), por lo
que cabe sin modificar consumidor. Títulos más largos que18bytes quedan JP.

La misión intro es evento32500100, JP ins1817/201C/slot3 y EU ins1869/201D/slot3.
Ambos usan ID misión35080060 y argumento1. Las instrucciones vecinas equivalen
con IDs desplazados+52 y saltos relativos equivalentes. La fuente oficial es
`¡Ayuda a la chica!`; cabe en el cuerpo original28bytes. El alineador previo
por mismo ID instrucción rechazaba este par. Se añade identidad específica
del consumidor de objetivo y contexto de ramas, no una alineación global por
orden ni una excepción por texto japonés. No se cambia 301D ni crece el SSD.

## Implementación y validación previstas

Nuevo módulo `ie3.comun.casos_visibles`, tests sintéticos y con originales.
Opera sobre bytes/payloads, sin escribir ROM ni CRO. Misión se aplica al paquete
actual después de cualquier recolocación de diálogo, comprobando la instrucción
contra JP y preservando todos los registros ajenos. Nombre completo se compone
con cortos ya localizados; título sólo modifica ranuras STR referenciadas y
mantiene la tabla de condiciones intacta. Validar cada caso por ID→frase oficial
conocida, no sólo un roundtrip que podría repetir el error del extractor.

No se ha demostrado almacenamiento de estos textos en guardados: no se borra
ni se pide reiniciar partida como remedio. La actualización visible se probará
en la ROM nueva tras cerrar completamente el juego; no se declara verificada.

## Resultado comprobado offline

Los cuatro casos tienen salida exacta reextraída:

- Spark: nombre completo `Paolo Bianchi`, fila1855/ID3170 (`0C62`). Corto
  `Bianchi` y toda metadata/punteros permanecen como en candidata actual.
- Descripción: `¡El delantero estrella conocido` + salto real LF +
  `como el Meteoro Blanco Italiano!`, 65bytes codificados. FuenteEUoffset`73F00`,
  destinoJPoffset`32A40`, ranura96bytes. Iguales datos en fuente Ogre.
- Spark título38: `El Meteoro Blanco`, 17bytes+NUL. En Ogre ese mismo índice
  tiene otra identidad textual oficial, `Indomable`; se mantiene la fuente
  correspondiente al perfil, no se trasplanta el texto Spark a Ogre.
- Misión: `¡Ayuda a la chica!`, 19bytes frente28 originales, sin crecimiento.
  Ogre conserva consumidorJP1817 pero la fuenteEU equivalente es ins1984;
  SparkEU es1869. Ambas pruebas pasan por el IDmisión y las ramas locales.

Validación: 9 tests nuevos (7 sintéticos +2 con originales y candidata actual),
18 tests de tablas corregidas y Ruff correctos. Además se ejecutó el repack
PKH/PKB en memoria de ambos perfiles y su reextracción, conservando los bloques
ajenos. No se escribieron ROM/CRO/FA ni se alteraron guardados.

Integración: regenerar `tablas_ui` desde JP original, reemplazando sus pools
defectuosos anteriores. `recursos_ficha_y_titulo` compone el nombre completo sobre
la tabla actual. `paquete_mision_intro` se ejecuta sobre la pareja eve actual
tras cambios de referencias de diálogo, para no pisarlos. Esos payloads deben
reextraerse también desde la ROM final por el integrador.
