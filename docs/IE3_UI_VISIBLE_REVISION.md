# Revisión de gráficos visibles tras la prueba de fase 4

## Evidencia y plan antes de implementar

Las capturas nuevas muestran PE/PT, Niv. y DL en castellano en la ficha, pero
el fondo con Tiro/Físico/etc. permanece japonés. Esto corresponde al paquete
`inazuma3_ogre/data_iz/a_menu/status_t.arc`: fase 4 modificó sus indicadores,
no su fondo. No se puede deducir la versión activa solo del nombre de carpeta;
Spark está usando al menos este recurso compartido Ogre.

La política anterior rechazaba cualquier atlas con alguna región QNA fuera
de sus dimensiones. El original usa regiones negativas o extendidas y la
fuente ES conserva exactamente esas mismas partes. Ese rechazo no demostraba
un límite del motor: bloqueó fondos y botones válidos. La nueva ruta conserva
literalmente el QNA, el formato y todos los metadatos, y trasplanta únicamente
píxeles oficiales cuando todas las partes que consumen esa textura coinciden.
No inventa nuevos UV ni cambia recorte, escala, wrap o animación.

El paquete de ajustes `system_b.arc` tiene 170 partes JP y 169 ES, pero las
diferencias de categorías regionales no afectan a todas las texturas. Por
textura, coinciden literalmente los multiconjuntos de partes: `mes_b02` (25),
`window_b03` (9), `window_b02` (4) y botones. Sus índices JP se conservan;
no se copia el QNA europeo ni se supone que el mismo ordinal tenga la misma
función. Se deja aparte el atlas regional `ie03o_menu_system_mes_b01` hasta
demostrar por separado equivalencias de sus regiones.

Alternativa descartada para estos primeros resultados: reencodear RGB a ETC o
importar paquetes completos. No hace falta porque los recursos compartidos
activos ya tienen formato compatible. El eventual cambio de formato/tamaño
de otros recursos requiere una comprobación aparte del lector; no se mezcla
con esta revisión acotada.

Implementación prevista: `ui_visibles.py`, API de payloads separada, contrato
por textura/consumidor y fuentes Spark/Ogre idénticas, tests de partes reordenadas,
UV originales preservadas, regiones incompatibles y no-texto literal. La
inspección de atlas y los tests no constituyen validación en juego.

### Extensión acotada del atlas de categorías

Antes de implementar la extensión se compararon las 34 partes JP y 33 ES del
atlas `ie03o_menu_system_mes_b01`. La región `(0,0)-(96,144)` corresponde a las
primeras nueve categorías y conserva literalmente todas las partes JP/ES que
la consumen (incluidas dos referencias repetidas a la primera fila). Se pueden
trasplantar Modo historia, Partido I–IV, Habilidades, Fase de furor,
Supertécnicas y Talentos sin copiar las categorías regionales posteriores.
Se hará mediante copia de píxeles nativos RGBA4444 en sus posiciones Morton,
sin reencodear, y comprobando que ningún consumidor quede cortado parcialmente.

## Implementación y cobertura concreta

`ie123kit.ie3.comun.ui_visibles.construir_payloads_visibles(jp, spark, ogre,
codigo_lector, actuales=payloads_previos)` devuelve un mapa de paquetes para
superponer al anterior, junto a un informe. No genera ni escribe la ROM.
Pasar `actuales` es imprescindible al componer con fase 4: se mantienen los
atlas PE/PT, Niv. y demás indicadores ya traducidos. El adaptador rechaza cambios
previos en QNA, tablas, metadatos y bytes exteriores a los píxeles.

Selección: 23 atlas completos y una región de otro atlas, en siete paquetes
de `inazuma3_ogre/data_iz/a_menu`. Todos tienen fuente idéntica en Spark y Ogre
ES; cualquier conflicto aborta, nunca gana la última variante.

| Pantalla/familia | Gráficos cubiertos por esta revisión | No atribuir a estos gráficos |
| --- | --- | --- |
| Ficha `status_t` | Tiro, Físico, Control, Defensa, Rapidez, Aguante, Valor, EXP., Equipación, Supertécnicas, Botas, Accesorios, Clasificación | Nombre completo, descripción, título y colocación de valores dinámicos |
| Organización | Equipo, Miembros, Datos, Niv., Formación, Historia, Duelo 1–3; Volver/Copiar/Salir | Opciones de ordenar por nombre/apodo/nivel/capacidad |
| Ajustes/sistema | Controles/Sistema; desplazamiento con B, Correr/Andar, Sonido, Altavoces/Cascos, Volumen, Música, Efectos; Más/Ver/Salir/Aceptar/Cancelar | Explicación superior y categorías regionales posteriores |
| Tutorial | Primeras nueve categorías oficiales, sin cambiar páginas ni opciones | Títulos/descripciones que vengan de strings; resto de categorías aún JP |
| Récords | Récords, clasificación por goles/partidos, Salir/Volver/Clasificación | Etiquetas y valores centrales de la captura: no forman parte de los fondos raster |
| Objetos | Cabecera Objetos, Opciones, ¿Para quién?, Usar/Aceptar/Salir/Volver/Sí/No | Nombres/descripciones y orden dinámico |
| Supertécnicas | Cabecera, Cuadernos, Aprender supertécnica, pregunta de ranura y botones de acciones | Atlas de afinidad con distinto significado por celda, omitido |
| Formación | Reserva, Estrategia, Datos y confirmaciones | Botones/atlas regionales no equivalentes, omitidos |

Los literales de carga de paquetes están en `ina_main3ogre.cro`: status_t
`0x2C9B14`, organization `0x2CA6FF`, system `0x2CB8AD`, ranking `0x2CCCAB`, item
`0x2CA077`, sp_move `0x2CB3D7`, formation `0x2C7EBB`, junto a los ANQ `ie03o`.
La captura de ficha confirma empíricamente el namespace compartido por sus
indicadores previamente traducidos. Las otras familias tienen identidad de
recurso/consumidor consistente, pero no se afirma haber observado en ejecución
esta nueva emisión ni que un literal aislado demuestre por sí solo toda ruta.

Los gráficos conservan formato nativo y dimensiones; no se genera tipografía,
se suaviza, reescala ni recompresa ETC. La región tutorial usa copia de palabras
RGBA4444 exactas. La comparación RGBA comprueba color y alfa, y para el atlas
parcial verifica también que el resto sea idéntico a la candidata de entrada.
Solo puede variar el tamaño SSZL comprimido bajo la huella del lector ya auditado;
el tamaño descomprimido permanece idéntico en todos los paquetes.

## Verificación

Los tests unitarios cubren partes reordenadas, UV extendidos originales, cambios
regionales ajenos a la textura seleccionada, composición/idempotencia, formatos
incompatibles, consumidores faltantes/repetidos, QNA/no-texto inmutable y regiones
parciales con alfa exacto. El test oficial compara las siete familias, sus QNA
literales, RGBA exacto y una segunda aplicación sin cambios.

Esto es validación estructural y de recursos, **no validación en juego**. El
resultado se mantiene pendiente de prueba manual. No se ha generado otra ROM
desde esta subtarea ni se ha hecho push.

Resultado ejecutado: **12 tests pasan** (11 unitarios y 1 oficial integral),
46,91 s; Ruff sin incidencias. Emisión sobre `fase4_ui/extra_final`:
`work/ie3/shared/fase4_ui/extra_visibles/`, **7 paquetes / 21 atlas modificados
incrementalmente / 1.016.371 bytes**. Tres atlas de los 24 seleccionados ya
estaban traducidos y no vuelven a contarse. Manifiesto reproducible en
`work/ie3/shared/fase4_ui/emision_visibles.json`. Estos son payloads para el
integrador, no una build ejecutable ni un sustituto de `archive.fa` completo.

## Revisión independiente del recorte del menú principal

Problema detectado antes de implementar: elevar solamente el comparando del
generador a 144 no elimina el segundo filtro del consumidor. El constructor
genérico de listas `10ACC8` fija la parte de texto 4 con ancho 64/128 y altura
12 en `10AFD4..10AFE8`, mediante `182100` (escribe `part+8/+A`). La función
`15488` suma ancho y origen UV; `15984..15994` normaliza ese extremo por el ancho
de textura. `196C8C..196D60` pasa los UV al lector de hints. En ExeFS,
`651A4..651B8` recupera el extremo y `65428..65458` descarta los comandos que
quedan fuera. El buffer de comandos puede seguir siendo 64×128: son magnitudes
distintas y el nuevo límite del generador no modifica el filtro del lector.

No procede sustituir globalmente el ancho de ese constructor: lo comparten
otras listas. El parche propuesto se limita al widget cuyo primer puntero de
texto (`[[widget+108]]`) es el literal de inicio del menú principal `165E8C`.
El widget se reconoce sin direcciones absolutas nuevas, mediante diferencia
PC/puntero, con comprobación de array nulo. El hook en `10AFD8` conserva `r0`
(ancho original), lo cambia a 144 solo para esa identidad y reproduce la
instrucción desplazada `SXTH r3,r0`. Las demás listas conservan su ancho.

Este cambio amplía la selección de comandos de la parte de texto, no las
partes gráficas del botón. Las posiciones finales se calculan en ExeFS
`655F8..65628` a partir de `command+C/E`, el primer comando y el origen; no se
multiplican por el ancho de la parte. Por ello no hay un factor 144/64 aplicado
a las letras. Tampoco se modifica su fuente ni el buffer, ni los parámetros de
escala. Que los nuevos textos quepan visualmente sigue requiriendo prueba real.

Coordinación: `colocacion_visible` termina en `29BFC8` y libera el tramo desde
`29BFCC` (cuatro bytes de separación conservados). El módulo
independiente `rectangulo_menu.py` usará 40 bytes hasta `29BFF4`, sin mover datos
que empiezan en `29C000`, y actualizará el final declarado del segmento código.
No amplía todavía el alcance a los 38 nuevos rótulos de submenús: necesitan
identidades y revisión conjunta de generación/recorte propias.

Implementación ejecutada: `parchear_rectangulo_menu(cro)` se compone después de
`colocacion_visible.parchear`, con anclas exactas, padding cero y comprobación
de relocaciones/saltos previos. Pruebas del ARM cubren identidad, ASLR, array
nulo, otras listas, anchos 64/128 e instrucción SXTH desplazada. Las pruebas
con los binarios locales comprueban composición real, cambios restringidos y
anclas del productor/lector que separan coordenadas lógicas y nativas.

Resultado focal ejecutado: **28 tests pasan en 1,27 s**, Ruff correcto. Sin
ejecutar el juego ni modificar ninguna ROM desde esta subtarea.

### Paneles superiores de tutorial y ajustes: recurso identificado

La comparación visual directa de originales confirma que
`a_data_replace/help_t/data/ie03o_syup_bg00.arc`, `bg01` y `bg02` contienen,
respectivamente, los títulos y explicaciones completos de Controles, Sistema
y AJUSTES. Los dos últimos son los paneles japoneses de las capturas nuevas;
no son strings que la revisión de tablas vaya a traducir.

La fuente ES existe y tiene geometría 512×256 idéntica, pero **JP usa ETC1,
formato CTPK 12, 65.536 bytes; ES usa RGBA5551, formato 2, 262.144 bytes**.
No se ha transplantado bajo el contrato actual de tamaño/formato invariable.
Integrarlos sin pérdida exigiría validar el lector y la asignación para el
formato 2 y nuevo tamaño descomprimido; convertirlos a ETC1 sería otra ruta con
pérdida que requeriría QA específico. No se da ninguna de esas rutas por
demostrada. Comparativas de inspección (no capturas de ejecución):
`work/ie3/shared/fase4_ui/syup_00.png`, `syup_01.png`, `syup_02.png`.

### Ampliación demostrada para los tres paneles oficiales

La restricción anterior era de la herramienta, no un límite probado del motor.
Antes de implementar se verificó la ruta JP: ExeFS `8078` copia el descriptor
CTPK, incluido formato `+2C` (`80B8`); `BC470` lo lee y la tabla `BC4AC` para
enum 2 salta a `BC548`, seleccionando tipo `8034` de `BC90C` y enviándolo por
`BC650..BC674` al cargador. No es una ruta ajena al ejecutable japonés.

Además, el placeholder de `help_t/parts.arc` sigue en ETC1 **también en ES**, con
512×256 y QNA idénticos al JP, aunque esos tres payloads oficiales ES son
RGBA5551. La textura dinámica aporta su formato real; no hay que cambiar ni
suavizar el placeholder ni alterar el QNA. El consumidor mantiene la región
400×240. Cada paquete de datos contiene exactamente una entrada CTPK con el
mismo CRC y nombre JP/ES; no hay otros archivos regionales que importar.

La asignación SSZL ya auditada (`.code` SHA256
`ae11511902ab4ead12617d5d52099aad2f238037588482651aac5cbae8bea18e`) permite
validar también esta ampliación: `13DD18` devuelve encabezado `+0C`, `5E9B4`
lo pasa como tamaño al asignador `5E9C4/5E9D0`, antes de descomprimir en `5E9E4`.
No usa el tamaño descomprimido histórico del archivo JP.

Plan: `ui_paneles.py` se limita a los tres paquetes `help_t/data/syup`, copia
el CTPK oficial completo sin pérdida y reconstruye el ARCV de entrada única,
actualizando su tamaño total y el de esa entrada, conservando CRC, offset,
padding y todos los datos externos. Reutiliza parsers/compresor y el contrato
de placeholder de `ui_graficos`; no existe un escritor ARCV genérico en el
toolkit para esta operación (los adaptadores anteriores exigen tamaño igual).
Pruebas: identidad, formato enum2, dimensiones, QNA externo, tamaños/offsets,
reextracción binaria del CTPK oficial exacto, RGBA y transparencia, conflictos
Spark/Ogre y anclas del lector real. Seguirá pendiente de validación en juego.

Implementación terminada: `ui_paneles.construir_payloads_paneles(jp, spark,
ogre, codigo_lector, cro_jp)` devuelve los tres payloads y sus pruebas de
identidad/huella. **5 tests pasan en 11,83 s** (3 unitarios y 2 oficiales),
Ruff correcto. La reextracción devuelve los CTPK europeos literales: no se ha
convertido ni un píxel, y su alfa es el original. El consumidor externo conserva
todos sus bytes; los ARCV pasan de 65.792 a 262.400 bytes descomprimidos mediante
la cabecera que utiliza el asignador auditado.

Payloads en `work/ie3/shared/fase4_ui/extra_paneles/` y manifiesto en
`work/ie3/shared/fase4_ui/emision_paneles.json`; destinados al integrador,
no son una ROM ni una validación en ejecución. Esta ampliación sustituye el
bloqueo de formato documentado arriba exclusivamente para estos tres paneles.
