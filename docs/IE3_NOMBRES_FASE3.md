# IE3: nombres de hablante, fase 3

## Decisión previa a la implementación

El usuario autoriza corregir nombres sin alterar el cuerpo de diálogo aprobado.
Se conservan FONT8/FONT12 v7, encoder, portadores, layout, ejecutable y cinco
congelados. No se emitirá una corrección visual basada únicamente en una maqueta.

La auditoría confirma que `unitbase.dat` NO tiene cabecera de 0x60: contiene
2582 registros de 0x68 bytes (268528 bytes), incluido el registro cero «sin
definir». El nombre corto está en +0x1C (16 bytes), el identificador de hablante
en +0x4E (u16), el nombre largo en +0 (28 bytes). La herramienta anterior empieza
8 bytes antes del registro 1 y usa +0x24: alcanza el campo corto correcto, pero
describe incorrectamente los límites de registro y mezcla parte del anterior
en su comparación. No se modifica esa herramienta durante esta subtarea.

**Solución de datos elegida:** módulo independiente que empareja por identificador
único, contrasta los campos auxiliares de identidad, conserva todos los bytes
ajenos al campo corto y reutiliza el encoder existente. No depende del orden
físico, Maserati ni Bianchi. Los IDs cero/duplicados, ausencias, diferencias de
metadatos no explicadas y nombres que no caben quedan pendientes explícitos.
Las discrepancias estadísticas se registran, nunca se copian desde Europa.

**Riesgo:** cambiar nombres no corrige por sí mismo su presentación. El módulo
también aportará diagnóstico del consumidor y métricas; la emisión de cambios
visuales queda bloqueada hasta disponer de una intervención realmente aislada.

## Consumidor confirmado

CRO JP `work/shared/base_3ds/romfs/cro/ina_main3ogre.cro`, SHA-256
`280e423a5957ea5394de359fb37e2945c2e88856b7b45b8b63cb287be6193ff0`.
Direcciones siguientes: offsets de archivo, NO VA; RVA código = offset − 0x180.

- `4F2F0` toma `sp+104`, dentro del objeto copiado en `sp+E8`: nombre corto +1C.
- `17A300` indexa el recurso por índice *0x68; `17A338` lee ese registro.
- `23C8` carga `/data_iz/font/FONT8.NFTR`; `242C` guarda gestor en global+44.
  Global base (reloc `21F8`) = data `34DB20`; gestor de nombres = `34DB64`.
- `1F78`: sb=1; `2520` escribe ese FONT_TYPE=1 en gestor+24.
- `160FA8` carga ese mismo gestor (pool `161130`). `160FB4` llama `180880`.
- `161124` es import `g_ItxInazuma3ogre` con addend `2E48`: parámetros dedicados
  `cscenedirection_1728_{ofsX,ofsY,addW,addH}` en `sItxInazuma3ogre.itx`.
- `180930–948` obtiene defaults FONT8 de `g_ItxInazuma123`: 6 arriba y 7 abajo.
  `180974–97C` solo sustituye el ancho con el addW dedicado si es **positivo**.
  Cero o −1 en ITX no desactiva el ancho forzado.
- `180998` guarda override en gestor+34. `180E6C–E90` sustituye el avance NW
  por override * conversión DS→3DS; `181154–170` añade tracking gestor+14.
  Su constructor `187688` inicia tracking=1. Hay posición DS y posición NW.
- `160F80` pasa ancho lógico 64: no basta con compactar el avance NW para
  asegurar que nombres largos no se parten o agotan su almacenamiento gráfico.

Así queda explicada la separación en esta ruta/configuración; no se afirma que
todas las rutas FONT8 sean de paso fijo. El raster v7 ya está corregido y no se
reescribe ni se sustituye CWDH para intentar contrarrestar un override externo.

## Alternativas visuales y bloqueo acotado

Cambiar los defaults globales de `sItxInazuma123` afectaría IE1/IE2 y otros textos:
descartado. Un addW positivo menor en la entrada dedicada mantendría paso fijo,
con riesgo de solape en letras anchas: no es corrección proporcional general.

Un hook condicionado exclusivamente a la llamada `160FB4` podría neutralizar el
override sin afectar al cuerpo, pero necesita ubicación ejecutable demostrada,
conservación de registros/flags/relocaciones y pruebas del ancho lógico 64.
NO se instala: los ceros finales de .text incluyen destinos de relocación
(`29BF00–29BF44`); el padding externo no se presupone código ejecutable seguro.
No se amplía el segmento ni se reutilizan caves aparentes. La autorización del
usuario cubre una corrección aislada demostrada, no hace segura una ubicación
sin comprobar. La candidata general no debe afirmar «nombres visualmente resueltos».

## Comprobaciones previstas

Pruebas unitarias con filas reordenadas, IDs ambiguos, límite de 16 bytes,
transición desde v7 y preservación de campos. Contraste completo con las fuentes
Spark/Ogre correctas (cada archive europeo contiene tablas de ambas versiones).
Revisión offline de nombres cortos/largos/anchuras distintas, incluyendo Bianchi
y Maserati. Las mediciones no equivalen a una prueba de ejecución.

## Decisión revisada: alternativa sin cave, previa a editar código

Se ha localizado una alternativa de **una instrucción existente**, autorizada
para integrar como ajuste FONT8 de IE3 con alcance explícito. `180918` es
`beq 180930`, después de `cmp FONT_TYPE,#1`. Cambiar su destino a `180970`
evita exclusivamente cargar los defaults FONT8 6/7: conserva r1=0, establecido
antes por `1808E4/EC`. Si hay override de contexto distinto de cero, el flujo
ni siquiera atraviesa esta rama. Se conservan los overrides explícitos positivos
por llamada/gestor. FONT12, FONT12T y RUBI no toman esta rama y son idénticos.

Esto afecta también a otras interfaces FONT8 de **ina_main3ogre.cro** que usen
los defaults, no solamente al nombre. No cambia ina_main1/2, .code ni fuentes
compartidas. Debe probarse también minimapa/listas FONT8 de IE3. No se promete
que todas las rutas FONT8 queden proporcionales: los overrides propios continúan.

Se elige esta intervención en lugar de caves, ampliar segmentos o tocar
parámetros globales compartidos. Se exige el SHA exacto de CRO v7, anclas ARM,
ausencia de la dirección en las tres tablas de relocación existentes, una sola
palabra modificada y misma longitud. El parche es opt-in y queda pendiente de
validación visual. No se escala el raster: FONT8 conserva el tamaño oficial de
v7; corregir la separación no se presenta como aumento del tamaño de glifos.

El corpus completo localizado por identidad no contiene nombres de más de ocho
caracteres. Esto acota el riesgo antes señalado del ancho lógico 64 para ese
corpus; no autoriza nombres dinámicos arbitrarios ni cambios del límite.

## Resultado implementado y validación local

Implementación opt-in en `ie3/comun/presentacion_nombres.py`. El parche cambia
`0A000004` por `0A000014` en offset de archivo `0x180918`; en realidad solo un
byte difiere. La entrada requerida es el CRO v7 de 3481600 bytes, SHA-256
`1c2db0af506077b1e94f1faa83859643cb35ca68ee0665db6872d811580f3061`.
La salida calculada tiene SHA-256
`763e5246edece475c23ba27eb1fe35db2861618903a80213b8d470c640cb1c77`.
Se comprueban 40030 destinos de relocación: la instrucción no es uno de ellos.
La prueba de decodificación ARM conserva el siguiente PC `18091C` para FONT12
(tipo 0), FONT12T, RUBI y tipos restantes; solo FONT8 toma otro destino. Además
se comprueba igualdad literal de todos los bytes restantes del CRO real.

Resultado de datos respecto al FA v7, sin emitir/copiar fuentes ni CRO al juego:

| Perfil | Ya oficiales originales | Heredados v7 | Nuevos | ID cero reservado | Encoding pendiente |
|---|---:|---:|---:|---:|---:|
| Spark | 5 | 2345 | 11 | 219 | 2 |
| Ogre | 5 | 0 | 2372 | 203 | 2 |

Los dos pendientes de codificación por perfil son `Völz` y `Luceafăr`; se
preservan sin abreviar, cambiar encoder ni inventar equivalencias. Todos los
2582 campos de salida por perfil contienen NUL interno; máximo observado 10
bytes antes de NUL. Todos los bytes exteriores al campo corto +1C:16 permanecen
japoneses. Los datos estáticos no demuestran una cota para productores runtime,
objetos de partida o nombres de usuario. Solo se cubre `logic/unitbase.dat`
normal; NPC y ex_binder no quedan implícitamente localizados por este adaptador.

SHA-256 unitbase calculados:

- Spark: `dbb680d63764fae178a39e958f1604490a4c0b8c681eb9a6db256fb4043d6b9a`.
- Ogre: `c98dffcac2724ab25594b563f0383ef0ad6d99675f497a607cc7c2d715f1f9e6`.

`work/ie3/shared/fase3_nombres/revisar.py` genera informes ignorados y una
comparación etiquetada **SIMULACIÓN OFFLINE, no captura de ejecución**. La
fuente se extrae temporalmente del FA v7 exacto, no de una sonda antigua: FONT8
SHA-256 `53a6a8a8c36c74a205749847ed686659b721fcf35170099923e17f22d97cecbb`.
La imagen incluye Ike, Mark, Willy, Bianchi, Maserati, Downtown y Tomahawk. Se
revisó visualmente: el modelo proporcional conserva raster y línea base, y
elimina la separación artificial. Bianchi pasa de avance 70 a 36 píxeles NW;
Maserati de 80 a 45; Downtown y Tomahawk de 80 a 54. Estos valores son del modelo
de esa configuración, no una medición en emulador. Hay 29 nombres por perfil
con espacios que el modelo no representa (no hay glifo CMAP para espacio);
sus anchos quedan incompletos explícitamente en el informe, no se presentan
como verificados. Ningún otro glifo falta ni hay tinta recortada por glyphWidth
en el conjunto modelado. No hay nombres oficiales insertados de más de ocho
caracteres; el comportamiento dinámico de la pestaña sigue pendiente de juego.

Pruebas ejecutadas: `pytest` sobre `test_ie3_presentacion_nombres.py`,
`test_ie3_presentacion_nombres_oficial.py` y `test_ie3_nombres.py`: **19 passed**.
Incluyen identidad reordenada, IDs ambiguos/cero, NUL obligatorio, conservación
de metadata, selección de la versión europea correcta, anclas de CRO real,
parche idempotente, rechazo de entrada desconocida y guardia FONT12. `ruff check`
de los tres archivos nuevos pasa tras ordenar imports. No se construyó ROM en
esta subtarea ni se modificaron archivos oficiales, fuentes o los cinco congelados.

La integración puede generar una candidata, nunca declarar esta presentación
verificada. Prueba manual mínima: nombres cortos/largos, Bianchi/Maserati,
nombres con espacio, pestaña sobre diálogo JP/ES, minimapa y otras listas FONT8
de IE3; confirmar que cuerpo FONT12 aprobado conserva su apariencia.
