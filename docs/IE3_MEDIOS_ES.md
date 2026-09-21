# IE3: medios oficiales españoles — auditoría y preparación conservadora

## Problema, evidencia y alcance

La candidata de texto no cambia las voces ni películas japonesas. Las dos
extracciones europeas locales sí contienen recursos `es/` y vídeos comunes
por los mismos identificadores. Esto permite una ruta directa de recursos,
sin modificar fuentes, CRO, tablas de sonido ni instrumentos.

Fuentes: RomFS originales de `work/shared/base_3ds`,
`work/ie3/rayo_celeste/fuentes/3ds_eu` y
`work/ie3/amenaza_del_ogro/fuentes/3ds_eu`.
Reutilización revisada: lector B123, inspector SADL del núcleo, conversor
MOFLEX y parser DAT existentes; capas IE2 v07 y documentación IE1 v34/v35.
Los procedimientos DS→3DS no se extrapolan: las fuentes IE3 ya son 3DS.

## Decisión antes de implementar

Preparar recursos individuales con ruta relativa JP existente y fuente ES
explícita. Verificar nombre/identidad interna, cabecera, canales, frecuencia,
codec, bucle y límites de SADL; conservar payload completo sin recodificar.
Comparar fuentes EU duplicadas y rechazar conflictos. No sustituir bancos
`sound_sb`, SWD, SMD o SED sin demostrar sus contratos e identidades internas.

Las películas requieren su pista sonora y subtítulos de la misma edición.
La igualdad de descriptor MOFLEX prueba formato, no montaje ni sincronía.
Los DAT europeos no pueden copiarse como texto crudo: sus acentos usan otra
CodeTable. Se inventarían como pendientes hasta verificar lector/tamaño,
codificación y colocación, o hasta incrustar subtítulos con una ruta validada.
El informe distingue medios preparados, bloqueados y validación en juego;
no promete que una ruta regional implique haber escuchado todas las voces.

Plan de validación: tests sintéticos de cabeceras/rutas/selección/fail-closed,
auditoría completa contra las tres extracciones y hashes de cada payload;
decodificación externa cuando esté disponible y prueba manual de voz, canciones,
película/subtítulos y sincronía. No generar ROM dentro de esta subtarea.

## Resultado reproducible

`ie123kit.ie3.comun.medios_es.planificar_audio(jp_romfs, spark_romfs, ogre_romfs)`
devuelve `(mapa_destino_relativo_a_RomFS_a_Path_fuente, informe)`. No escribe
originales, overlay ni ROM. Cada fila incluye SHA-256/tamaño antes/después y
edición/ruta de origen. El integrador debe copiar el fichero completo y
releerlo comprobando ese SHA; las rutas finales no llevan el prefijo `es/`.

Resultado en las extracciones actuales: **532 SADL, 141.508.656 bytes**:

| Categoría | Archivos preparados |
| --- | ---: |
| Voces de diálogo `inazuma3_ogre/data_iz/sound/V*.SAD` | 472 |
| Audio de escenas `inazuma3_ogre/data_iz/sound/a3m*.SAD` | 56 |
| `op00f.SAD` y `end00f.SAD`, Spark y Ogre | 4 |

Se elige la ruta española oficial exacta. Los duplicados de Spark/Ogre son
byte-idénticos, sin conflictos; opening/ending Spark proceden de Spark y los
de Ogre de Ogre. El ending Spark oficial se llama `end00f.SAD` externamente,
pero su etiqueta interna es `END00B.SAD`; la API admite exclusivamente esa
pareja observada, no cualquier cambio de identidad. No se afirma haber
escuchado el idioma de cada una de las 532 pistas: la procedencia ES está
demostrada y las muestras de voz/opening no son idénticas a las inglesas.

Todos los SADL seleccionados tienen cabecera `sadl`, codec `B4`, 32.728 Hz,
uno/dos canales iguales a JP, sin cambio de bucle, inicio `0x100`, tamaños
declarados iguales al fichero y payload completo alineado a bloques por canal.
No se recodifican ni acortan. La duración de una voz oficial puede cambiar;
la sincronía con la puesta en escena requiere prueba manual.

**No modificados:** 17 SAD idénticos (TITLE y jingles), nueve eyecatches
`a3y*` cambiados que no se han certificado como voces localizables, y todo
banco SED/SWD/SMD/PKB/PKH. Las pistas promocionales `pv_f`, `pv_b`, `pv_o1`,
`pv_o2`, además de opening/ending Bomber, no tienen fuente ES equivalente.
Los recursos `a3y*b` se conservan; no se certifica Bomber por compartir carpetas.

### Vídeos y subtítulos: inventario inicial y activación condicionada

`inventariar_videos(jp_archive, spark_archive, ogre_archive)` resuelve
**65 de 73 IDs MOFLEX** japoneses (4 Spark, 61 en la carpeta Ogre compartida).
Ante ruta común y regional, elige `es/`; los duplicados de las dos ROMs EU
coinciden por SHA. Los 8 sin pareja son promociones/Bomber. Cuatro vídeos
adicionales Ogre (`a3m01f`–`a3m04f`) no tienen ID destino JP: no se insertan
renombrándolos ni sustituyendo escenas por parecido.

Todos los equivalentes tienen descriptor de vídeo retail, 240×320, 24/1 fps,
layout `0x16`; audio va en el SAD externo. OpenCV ya instalado permitió
decodificar las 65 fuentes secuencialmente hasta EOF, **54.364 fotogramas**,
sin error comunicado por el backend y sin transcodificación. EOF no constituye
por sí solo una prueba de CRC ni de sincronía. Los PNG de opening Spark/Ogre
y `a3m03a` se inspeccionaron: la orientación rotada para pantalla es correcta
y las bandas negras de esas muestras no llevan subtítulos incrustados.

Hay **98 pistas DAT ES** (47 Spark + 51 Ogre), iguales entre ambas fuentes EU.
Sus registros contienen inicio/fin/tamaño u32, texto NUL y terminador FFFFFFFF.
No se copian: `font/CodeTable.bin` europeo usa portadores distintos de la
fuente JP parcheada. Además IE2 v07 demuestra un consumidor de subtítulos que
descarta ASCII; ese contrato no se debe extrapolar ni al diálogo ni a IE3.
Hace falta cerrar codificación aceptada y geometría del consumidor IE3 antes
de convertir los DAT. El inventario simple devuelve `selected=0`: la activación
posterior exige comprobar independencia y línea temporal, como se describe
abajo. Nunca se vacían los DAT ni se presenta imagen/voz como localización total.

### Actualización: imágenes ES activables sin modificar los DAT

Se demostró directamente en el CRO IE3, no por extrapolación desde IE2:

- `AB3C` carga el DAT: `ABDC` FS_OpenFile, `ABF8` nttcGetLength, `AC08`
  reserva ese tamaño y `AC1C` FS_ReadFile. `AC4C–AC64` y `14D144–14D168`
  avanzan por el tamaño declarado alineado a cuatro.
- `14CF84` actualiza el subtítulo; `14D020–14D044` calcula ticks de30Hz y
  `14D0AC` llama a `17FC4C`. Esa función llama a `23FD0`; `24020–24030`
  **descarta ASCII20–7E** y trata `[ / ]` como rubí. Por tanto los DAT ES
  crudos perderían la mayor parte de su texto. Se conservan los JP intactos.
- La imagen se abre por una ruta independiente: `17F93C/17F954` construyen
  `movie/<ID>.moflex`; `17F9B0` llama a `nnfsFileInputStream::TryInitialize`,
  `17F9CC` a `FsReader::Initialize`, `17F9D8` a `GetMoflexReader`,
  `17F9E8` a `mwmomoflexDemuxerCreate` y `17FA0C` a `Player::Create`.
  Se entrega un stream al middleware, no una longitud binaria JP prefijada.

Se decodificaron también los 65 originales JP y se repitió la QA asociando
cada resultado al SHA-256 del archivo leído. **Cada ID tiene exactamente el
mismo número de fotogramas JP/ES**, 54.364 por lado, a24fps y misma geometría.
Esto valida contador/duración, no reemplaza comprobar doblaje/cues en juego.

La API final `planificar_videos(jp, spark, ogre, cro, qa_jp, qa_es)` comprueba
22 anclas/imports del consumidor, hashes exactos de QA y frames/fps iguales.
Devuelve 65 referencias de origen serializables. `leer_video(entrada, spark,
ogre)` lee el payload y revalida hash/formato antes de emitir. DAT no aparece
en ese plan: `subtitle_localized=False`, `runtime_verified=False`. La candidata
puede mejorar vídeo/voz manteniendo subtítulos japoneses explícitamente pendientes.
No se afirma equivalencia de todas las secuencias visuales solo por contar frames.

El integrador conserva la transición JP/actual/ES: no sobrescribir un vídeo
actual distinto de ambos sin investigarlo. Informes locales:
`decode_videos_jp.json`, `decode_videos.json` y `plan_videos.json`.

### Bancos: pendiente separado, no confundir con voces SAD

`sound_sb.pkh` (Spark, 96 bytes) y `sound.pkh` (Ogre, 10.768 bytes) **no son
PackNum**: comienzan por una tabla binaria, no por esa firma. Sus PKB contienen
SEDL/SWDL y difieren de los europeos; también cambia `3D_901.SED`. No se aplica
el reconstructor de eventos ni se copia el banco entero. Los SMD/SWD sueltos
P36/P37/P39, `2D_011` y `3D_900` sí son iguales y no necesitan modificación.
Pueden seguir existiendo voces japonesas en bancos no auditados; no se declara
que los 532 SAD cubran todas las voces o todas las situaciones de partido.

## Evidencia y pruebas

Diagnósticos locales (ignorados por Git) en `work/ie3/shared/fase5_media/`:
`auditoria.json`, `decode_videos.json`, tres PNG de muestras. La auditoría usa
la API de producción; el decodificador OpenCV es una comprobación independiente.

**18 tests focalizados superados**, incluida prueba con los tres originales;
lint correcto. Pruebas sintéticas cubren rutas, equivalencia entre ediciones,
preservación de instrumentos, rechazo de identidad/cabecera/tamaño/formato,
ausencia de archivos, bancos no modificados, no activación automática sin QA,
rechazo de QA obsoleta/duplicada, frames distintos y lectura final alterada.
No se cambiaron fuentes, encoder, CRO, integrador ni build. Sin ROM generada
por esta subtarea. `runtime_verified=False` y `audio_decoded=False` se mantienen:
no había vgmstream/ffmpeg disponibles en las rutas del proyecto ni en PATH.
