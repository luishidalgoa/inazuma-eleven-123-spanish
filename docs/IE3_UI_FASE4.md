# IE3 Fase 4: interfaz gráfica oficial, investigación y contrato

## Diseño previo a la implementación

El inventario JP/ES encontró recursos ARCV/SSZL con texturas CTPK y maquetados
QNA 051. Las rutas bajo `inazuma3_ogre` también existen en la edición oficial
Spark: el nombre de carpeta por sí solo no identifica una exclusividad Ogre.
La comparación inicial de 140 paquetes encontró 80 con todas las entradas no
gráficas literalmente iguales. Por ejemplo, los 20 CRC de `status_t.arc`
coinciden y el QNA es idéntico; las dimensiones y nombres CTPK coinciden, pero
algunas texturas Spark pasan de ETC1A4 (13) a RGB5A1 (2) en la fuente española.

Problema: copiar un paquete europeo completo puede modificar layouts, entradas
extra y recursos exclusivos; reencodear ciegamente puede introducir pérdida.
Hipótesis comprobable: los atlas con identidad de CRC/nombre, dimensiones y
regiones QNA idénticas pueden recibir sus píxeles oficiales sin cambiar la
geometría ni el resto del paquete japonés.

Se reutilizan `arcv.entries`, `sszl`, `texturas`, `ctpk` y `QnaLayout`; no se
duplica ningún parser ni se emplea el reconstructor 301D. La primera ruta será
conservadora: mantiene la tabla ARCV, tamaños y metadatos CTPK; escribe solo
sus bytes de píxeles. Las entradas no elegidas y los QNA permanecen literales.
Se comprobarán transparencia, ida/vuelta de cada codec, diferencia de color y
fuentes Spark/Ogre compartidas. Los atlas con cambio de geometría quedan
pendientes en vez de importar el layout europeo. Las fuentes tipográficas,
portadores y métricas quedan fuera.

Pruebas previstas: rechazar CRC/nombres/dimensiones/QNA discrepantes; conservar
entradas no textuales y tabla; round-trip/reextracción; conflictos de fuentes
compartidas; atlas y regiones visibles comparados offline a escala nativa.
La inspección offline no demuestra ejecución, el resultado será candidata.

### Evidencia del lector SSZL, antes de ampliar la política comprimida

La primera preparación conservadora bloqueó 26 atlas compatibles por el tamaño
comprimido. El comentario histórico del codec (IE1) no demuestra ese límite IE3.
Se inspeccionó el `.code` JP descomprimido desde ExeFS, SHA-256
`ae11511902ab4ead12617d5d52099aad2f238037588482651aac5cbae8bea18e`:

- `0xA56E0` reconoce `SSZL`/`LZSS`.
- `0x13DD18` devuelve el tamaño de salida del encabezado `+0C`.
- `0x5E9AC` llama ese lector; `5E9B4` pasa su resultado al asignador
  `C28F4`/`C200C`, antes de descomprimir en `13DBB8`.
- La entrada se lee en `B34B4`: `B35A4` obtiene el tamaño actual del archivo
  (`sp+30`); `B35EC` reserva ese tamaño por defecto, y `B363C` lee esos bytes.

Por tanto la política elegida permite cambiar el tamaño SSZL, **no el tamaño
descomprimido del ARCV**, verificando exactamente la huella del lector. El índice
B123 reconstruido suministra el tamaño actual. No se toca ejecutable ni se
amplía un buffer. Sin esa referencia verificada se conserva el rechazo anterior.
La prueba del consumidor es estática, no equivale a cargar las pantallas.

## Resultado y selección semántica final

La identidad de estructura no bastaba: la inspección de las 83 ayudas españolas
diferentes encontró páginas que describen opciones ausentes de la compilación JP.
Se añadió una lista explícita de páginas revisadas (`AYUDAS_REVISADAS`), con
rechazo por defecto para futuras páginas. No se trasplanta un tutorial solo
porque su textura encaje. Las dos fuentes ES deben ser literalmente iguales
para cada ruta compartida; un conflicto detiene la preparación.

Exclusiones documentadas, conservando cada recurso JP íntegro:

- `tt55/59/60/63/64/65/98`: StreetPass, descargas o menús de red diferentes;
  `tt55/98` contradicen explícitamente la advertencia JP sobre la compilación.
- `tt69`: el enlace Ogre europeo exige otra consola/copia, mientras JP describe
  un enlace dentro de la compilación. `tt70/71` tienen cuadros ES vacíos.
- `tt77/78`: extras y enlaces regionales no demostrados equivalentes.
- `tt96/97`: capturas y referencias a tres equipos Duelo no demostradas en JP.
- `tt36/37/48`: PE expandido como «energía», incompatible con el glosario
  confirmado (PE = resistencia, PT = técnica).
- `tt29/68`: siglas de capturas incrustadas no PT/PE; no se repintan inventando
  una equivalencia ni se alteran las fuentes de texto.
- `ie03_menu_equip_parts_b02`: el QNA coincide, pero las celdas oficiales
  intercambian símbolos L/R y flechas. No es un simple rótulo traducible.

Selección final: 64 ayudas cambiadas y tres ya idénticas (`tt13/14/15`), más
25 atlas de seis paquetes de menús. Las ayudas cubren movimiento, pases, tiros,
comandos, técnicas y talentos, recuperación/objetos compatibles, fichajes,
entrenamiento, formaciones, afinidades y funciones de partido. No se afirma
que todas las ayudas ni todos los menús estén traducidos.

Los seis paquetes son `inazuma3/.../sp_move_b`, `organization_b`, `formation_b`
y `inazuma3_ogre/.../item_b`, `organization_b`, `status_t` bajo `data_iz/a_menu`.
Sus fuentes ES son comunes Spark/Ogre, pero la carpeta no prueba qué ruta usa
cada versión en todas sus pantallas. Los menús pendientes incluyen layouts
distintos, formatos de textura distintos y referencias UV originales todavía
no modeladas. Las tres ayudas superiores `syup_bg00/01/02` tampoco se activan:
además de no cerrar su revisión semántica, JP usa formato 12 y ES formato 2.
No se convierte RGB a ETC con pérdida para sortear este límite.

## API reproducible y validación

`ie3.comun.ui_graficos.construir_payloads_graficos(jp, spark, ogre,
codigo_lector, cro_jp, cro_es)` recibe archivos que ofrecen `index`, `exists` y
`read`, y devuelve `{ruta: bytes}` más un informe. No escribe el archivo B123,
el CRO ni la ROM. Las ayudas exigen el literal `.ctpk` en ambos CRO, un único
atlas y el mismo placeholder/QNA externo de `parts.arc`. Se registran offsets
de consumidor, huellas, intervalos de píxeles, regiones, tamaños y motivos de
rechazo. Los literales del menú principal quedan a cargo de otro adaptador;
este módulo no toca código ejecutable, fuentes, métricas ni encoder.

Validación ejecutada: nueve tests unitarios y un test con fuentes oficiales
(`tt40`), todos pasan; Ruff sin incidencias. Se comprueban transparencia y RGBA
exactos, error de color cero, invariancia de metadatos/QNA/tabla ARCV, conflictos
de fuentes, cambios de formato rechazados, identidad del consumidor dinámico,
límites UV y exclusiones semánticas. Se inspeccionaron comparativas JP/ES/salida
de los atlas y las 83 páginas candidatas a escala nativa. **No se ejecutaron
estas pantallas en el juego**: `runtime_verified` permanece `false`.

Los resultados locales definitivos se generan en
`work/ie3/shared/fase4_ui/extra_final/` y `emision_final.json`. Los anteriores
`extra/` y `emision_familias.json` son diagnósticos obsoletos que incluyen ayudas
descartadas: no deben integrarse por un glob de carpeta. El integrador debe usar
el diccionario devuelto por la API o exclusivamente el manifiesto final.

## Apéndice: unidades del origen del cuerpo (auditoría estática)

Se comprobó una posible confusión entre las coordenadas heredadas DS y las
nativas. El consumidor gráfico `SetPosition` sí convierte posiciones mediante
factores 1,25/1,5625 según pantalla. **Ese hecho no determina las coordenadas
del texto del cuerpo**, que emplea un callback independiente:

1. `3A764/3A76C/3A770` establecen `sl = escena + EE4`, el mismo grupo utilizado
   en `3AB9C`. `3ABB0` pone cero y `3ABB8 → 17064 → 170D0` escribe ese cero
   en el campo `part+80` de cada glifo del cuerpo.
2. `17534 → 15F1C` prepara el estado del dibujo. En `16420–16458` suma las
   coordenadas fijas del grupo (`+8/+C`) y plano (`+1C/+20`) y multiplica
   por `1/4096`, constante de `16330`, guardando X/Y en `222C8+4/+8`.
3. `17588–1758C` pasa esa parte a `196BDC`. El callback convierte las X/Y
   anteriores a enteros y añade `part+84/+88` (`196D14–196D54`).
4. `196D60` llama al import `1818`,
   `cGameTextSystem::FindHintOnPlaneVramAndDrawText`. La exportación del CRS
   JP en `1114` lo resuelve a `.code+650F0`.
5. El prólogo desplaza SP `F0` bytes: el indicador se lee en `sp+FC`, X en
   `sp+C8` e Y en `sp+F0`. Con el indicador cero, `655A8–655B8` carga las
   coordenadas sin convertir y salta a `655F8`, evitando por completo las
   multiplicaciones de `655BC–655F4`.

En esta ruta, para posiciones enteras, el paso fijo `<<12`, redondeo y `/4096`
conserva exactamente las posiciones. El origen lógico es
`baseX + 10 + glifoX + desplazamientoX`: con `baseX=0`, el desplazamiento
original `+2` da `12+glifoX`, y un desplazamiento `−2` da `8+glifoX`.
La tinta visible puede tener el bearing propio del glifo; no se cambia ni se
deduce una métrica nueva de esta comprobación. Tampoco se aplica el factor 1,25
a los avances de texto de este recorrido.

El test local `test_ie3_ruta_coordenadas_oficial.py` fija las instrucciones
relevantes, el import/export y la rama que evita el escalado, leyendo los
CRO/CRS/ExeFS originales. Esta prueba es de estructura y consumidor estáticos:
**no demuestra una comparación visual ni ejecución de la candidata**.
