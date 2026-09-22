# Submenús y ordenación: reempaquetado local de literales

## Diseño previo

Una antigua subranura JP no es automáticamente el límite del consumidor. Los
submenús Inventario/Estrategias y Recursos/Formación tienen grupos de datos
contiguos que pueden reempaquetarse sin crecer CRO. Se conservarán sus rangos
completos `16621C:166288` (108bytes) y `1662A0:1662FC` (92bytes), actualizando
los ocho ADR que apuntan al inicio de cada título/lista. No contienen destinos
de relocación. Barrido de referencias ARM/relocaciones debe confirmar que no
hay otros consumidores ni punteros interiores. No se usa cave ni cambia código
de dibujo; únicamente referencias de datos de instrucciones ADR existentes.

El lector `175534` avanza cadenas NUL con strlen+1; el lector título`175608`
acepta15bytes. Fuentes: Inventario440/441, Estrategias442; lista estrategia
794/105/385/386/387, Recursos449/450, Formación447/448 (primeras4cadenas).
El consumidor EU arma Estrategias por IDs individuales en `173708–173740`;
la rama GetLanguageCode==3 usa104«Partido» donde la otra usa794«Historia».
JP muestraストーリー sin esa rama: se toma la redacción oficial794correspondiente
a esa etiqueta, no se importa el condicional ni se inventa una traducción.

Datos título: ADR166028→16628C, ID444. Las listas de8/6elementos son bloques
rodata `2A0A4C:2A0AA4` y `2A0AA4:2A0AE8`, apuntados por relocaciones de pools
166298/16629C. Se comparan con consumidores EU173844/173868, IDs445/446;
el texto español completo cabe sin mover los pools ni cambiar su cardinalidad.

Ordenar: JP93224 usa objeto+8994 y constructor tipo7, carga cuatro punteros
de2B288C, copia a stack20..2C. EU97254 mismo objeto y tipo7, llena stack20..2C
mediante GetString160/161/162/163: Nombre/Apodo/Nivel/Habilidades. El bloque
rodata2CD6A6:2CD6D5 se reempaqueta y sus cinco referencias internas se reapuntan
con `Cro.retarget` existente. La quinta cadenaゼッケン, de otro consumidor,
se conserva literalmente (sin afirmar traducción no auditada). Se comprueba
que toda referencia interior pertenece a este conjunto y no se pierde ninguna.

Nuevo módulo `ie3.comun.literales_visibles` y tests dedicados. Reutiliza fuente
GetString certificada de `ui_literales`, lector CodeTable, encoder protegido y
parser/relocador CRO. No edita ui_literales ni fuentes, no usa29BF48..29C000,
no cambia geometría ni tamaños de buffers. Entrada puede contener ajustes
externos de fase4/5; sólo se exige identidad de rangos/ADR concretos. Verificación
de salida: reextraer por ADR y relocaciones, todas las cadenas oficiales completas,
tamaño y bytes ajenos intactos. Pendiente encaje visual de cada pantalla.

## Resultado

38 etiquetas oficiales reextraídas completas con fuentes Spark y Ogre, mismas
listas y criterios: Inventario (Objetos/Equipación/Supertécnicas), Estrategias
(Historia/Pachanga/Duelo1–3), Recursos (Récords/Tutoriales/Ajustes), Formación
(Historia/Duelo1–3), Datos (variantes de8/6opciones) y ordenación
(Nombre/Apodo/Nivel/Habilidades). Esto cubre las opciones de esos menús, no
certifica como localizada cada pantalla interior de tutoriales o ajustes.

Los bloques nuevos ocupan sus mismos rangos. Ejemplo Inventario/Estrategias:
los nuevos inicios son16621C/166228/16624C/166258; se actualizan los ADR de las
dos últimas entradas, sin confundir la antigua subranura con un límite del
lector. Recursos/Formación usan1662A0/1662AC/1662C8/1662D4. Ordenación conserva
los5destinos de relocación y sus tipos/segmentos, cambiando sólo addends.
El literal ajenoゼッケン permanece japonés e íntegro, con su referencia actualizada.

9tests pasan (7sintéticos +2confuentes): ARM ADR ida/vuelta, registros/condición
conservados, overflow rechazado sin truncar, fuente oficial, reextracción por
referencia, todas las relocaciones ajenas idénticas, composición con cambios
en el área reservada del principal, y rechazo de datos inesperados en los6rangos.
Ruff correcto. La función requiere grupos originales; no intenta reaplicar
silenciosamente sobre grupos ya transformados. El integrador la ejecuta una vez
sobre la candidata fase4 y registra el resultado. No se generó ROM desde esta
subtarea y no se modifica el mecanismo de dibujo de estos menús.

## Auditoría posterior: datos completos no implican encaje visual

La revisión del consumidor identifica límites de dibujo todavía independientes
del reempaquetado anterior. No se deben presentar las38etiquetas como38casos
visualmente resueltos. El constructor `175614` copia el argumento caller
`sp+14` a `widget+CC`; las tres rutas de reserva, generación y recorte calculan
64si ese valor menos20es≤64, o128en caso contrario:

- Reserva `175730..175778`, textura de opciones en`widget+114`.
- Generación `10B2E4..10B2FC`, llamada`180880`en`10B3A8`.
- Recorte `10ACDC..10ACF0`, llamada`182100`en`10AFE8`.

| Lista | Primer literal tras parche | Ancho caller | Generación/recorte original |
| --- | --- | ---: | ---: |
| Inventario |166228|90|128|
| Estrategias |166258|80|64|
| Datos8 |2A0A4C|100|128|
| Datos6 |2A0AA4|100|128|
| Recursos |1662AC|100|128|
| Formación |1662D4|100|128|

Los argumentos se justifican en`165F04`, `165F74`, `165FF0`, `166110`y
`166190`, respectivamente. La fuente común de SL80/R4100está en
`165C80/165C94`. A avance12, Historia/Pachanga requieren96, Supertécnicas156,
y Clasificación FFI204: superan sus rectángulos originales. Es una prueba de
riesgo con ese avance, no una medición visual del resultado ni permiso para
aumentar un stride sin su reserva correspondiente. Se comunicaron las identidades
al propietario de geometría para adaptar generación y recorte conjuntamente.

Los títulos usan otra textura: `widget+110`, reservada SIEMPRE64×8por
`175754/175758→1818CC`. La generación en`269D70` fija64en`269DF4`, lee
`widget+F0`en`269E00`y llama`180880`en`269E18`. El límite de copia15bytes
no demuestra que Inventario/Estrategias/Formación entren visualmente en64píxeles.
Una ampliación de la lista no corrige automáticamente el título.

Ordenación tampoco usa el generador de listas. `9332C→148124`reserva128×16;
si `owner+14`pertenece a4/6/8usa256×32(`148170..14818C`). `14828C`genera
con dimensiones reales y`148310→182100`recorta con las mismas. Habilidades
tiene11caracteres y merece comprobación en la variante128; el modo activo del
owner en la captura no se ha probado. Los otros tres criterios tienen≤6caracteres.

Las explicaciones superiores Tutoriales/Ajustes NO son estas cadenas GetString.
El agente gráfico ha contrastado las capturas con `help_t/syup_bg01`(Sistema,
«Lee información sobre distintos aspectos y funciones del juego») y
`help_t/syup_bg02`(AJUSTES, «Configura distintas opciones del juego»).
Ambas referencias son512×256, pero JP usa ETC1de65536bytes y ES
RGBA5551de262144bytes. La selección de atlas de igual formato/tamaño no las
puede trasladar directamente. Su adaptación pertenece al módulo gráfico; no se
creó una traducción de strings ficticia para esas dos cajas.

## Diseño de corrección acotada de títulos

Nuevo adaptador `geometria_submenus.py` y tests dedicados. La clase completa de
widget comparte constructor175614, copiador175608(`strncpy(...,15)`), generador
269D70y selector269F0C. Se han enumerado9llamadas al constructor,8al copiador,
y una al generador/selector desde1750E0. Se validará este conjunto y cada literal
actual por su ADR, exigiendo NUL antes del byte15; no se afirma que strncpy
por sí solo añada NUL cuando la entrada excede su límite.

Solución: cambiar únicamente175758(exponente de anchura3→4),269DF4(límite
lógico64→128) y269FDC(selecciónUV64→128). La textura de comandos pasa
de64×8a128×8:512bytes. Como hay a lo sumo14glifos y un terminador de32bytes,
la cota conservadora es480bytes. El consumidor sigue usando FONT8 y su avance
actual; no cambian títulos, cajas, escalas, botones, coordenadas ni altura.
Selección comprobada:269FE8→182100(ancho128/alto8),26A004→1821B4(UV0,0),
26A020→182260(posición12,6). El lector de comandos usa esa selección y emite
la tinta por sus coordenadas propias, no estira un bitmap de letras.

Se elige alcance por clase de títulos con contrato probado, no un parche global
de fuentes. No requiere cueva ni crecimiento CRO. Riesgo pendiente: validación
real en juego. Tests previstos: cota14+terminador, rechazo de15sin NUL,
anclas/consumidores, relectura de las tres constantes y bytes ajenos intactos,
composición con literales traducidos y geometría de otros agentes.
