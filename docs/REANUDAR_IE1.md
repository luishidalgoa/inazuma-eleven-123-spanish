> Retoma 2026-09-11 (v33): `work/shared/candidatas/probe_ie1_v33/archive.fa` está instalada en Azahar
> (hash `b65cd7ea…48285314`, CRO `44d4e206…` con 158 literales nuevos). Base
> reproducible: v32 (se conserva; el `archive.fa` de v31 se borró). Cada línea de trabajo vive en `work/ie1/capas/v33/<línea>/`
> con su `validate.py`; mapa de propiedad en `work/ie1/capas/v33/ownership.json`; pendientes de
> texturas ya cambiadas en `work/ie1/capas/v33/tex_residual/report.json`. Detalle en
> [IE1_V33_TANDA.md](IE1_V33_TANDA.md).

> Retoma 2026-09-11 (v32, histórica): `work/shared/candidatas/probe_ie1_v32/archive.fa` estuvo instalada en Azahar
> (hash `4043c5c9…a8a7498a`, CRO igual que v31). Base reproducible: v31 (se conserva;
> el `archive.fa` de v30 se borró). Cadenas oficiales del ejecutable NDS en
> `work/ie1/fuentes/nds_es/bin/strings.txt`. Detalle y pendientes en
> [IE1_V32_TANDA.md](IE1_V32_TANDA.md).

> Retoma 2026-09-11 (v31, histórica): `work/shared/candidatas/probe_ie1_v31/archive.fa` estuvo instalada en Azahar
> (hash `e19252b1…eb00f746`, CRO igual que v30). Base reproducible: v30 (se conserva;
> el `archive.fa` de v29 se borró). La ROM NDS española está extraída en
> `work/ie1/fuentes/nds_es/` y es la fuente de nombres oficiales. Orden completa, pendientes y
> prueba sugerida en [IE1_V31_TANDA.md](IE1_V31_TANDA.md).

> Retoma 2026-09-11 (v30, histórica): `work/shared/candidatas/probe_ie1_v30/archive.fa` estuvo instalada en Azahar
> (hash `447f2bd8…a430f31af`, CRO igual que v29). Base reproducible: v29 (se conserva;
> el `archive.fa` de v28 se borró). Añade el menú de la bolsa y sus pantallas. Orden
> completa y prueba sugerida en [IE1_V30_TANDA.md](IE1_V30_TANDA.md). Siguiente
> bloqueo: nombres oficiales de supertécnicas y objetos (#22).

> Retoma 2026-09-11 (v29, histórica): `work/shared/candidatas/probe_ie1_v29/archive.fa` y su CRO estuvieron instalados
> en Azahar (hash `cbada7a4…9eaf465`). Base reproducible: v28 (se conserva). Añade
> descripciones de jugadores, pantalla VS, nombres oficiales de equipo, PE/PT de
> objetos y el lote `ui_followup`. Orden completa y prueba sugerida en
> [IE1_V29_TANDA.md](IE1_V29_TANDA.md). Pendiente: prueba jugable; objetos y menú de
> entrenamiento en #22.

> Retoma 2026-09-09 (v27, histórica; su `archive.fa` se borró tras instalar v29):
> La auditoría completa de 982 eventos deja 18.806 diálogos visibles sin japonés,
> 19.039 textos insertados y 0 rechazos. Hash candidato/instalado:
> `91f816060775190e994f585fae5e09c8adab4cc1998b059f250372387ab10369`.

> Retoma 2026-09-09 (v26): `work/shared/candidatas/probe_ie1_v26/archive.fa` está instalada en Azahar.
> Hash candidato/instalado: `394b3ea3f986204a5ed7bb9d8fb2a349333d6b15490736cf16f259ca1dcfa27f`.
> La candidata queda con 0 rechazos de registros y conserva la caja y tipografía
> aprobadas. Continuar con la prueba guiada de capítulo 2 y pachangas desde partida nueva.

## Trabajo en curso: v23 instalada, aspecto aprobado y bloqueado

El usuario confirma que la caja actual está muy bien y prohíbe volver a cambiarla.
Cumplir AGENTS.md y `tools/dialogue_lock.py`. Continuar traduciendo sin tocar la
tipografía; el recorrido completo de QA sigue siendo una comprobación aparte.

Ver [QA_TIPOGRAFIA_V20.md](QA_TIPOGRAFIA_V20.md). V20 recuperó `--fullwidth`
usado en v13, junto a sus cinco fuentes ya recuperadas. V23 conserva esa
apariencia, añade los diálogos de pachangas y cadena de partidos, mantiene los
143 diálogos visibles de la Royal (`mch.pkb`, eventos `9420xxxx` y `94001500`)
y localiza nombres, títulos y categorías de equipo. La candidata instalada
coincide con el SHA-256
`bf1e194564170d86cffcf3acfa70409420584ca048b699253611011e35614393`.
La prueba jugable sigue pendiente; no se debe cargar un estado rápido de otra
build. Las v21 y v22 se eliminaron después de verificar la instalación.
Historial anterior a continuación.

Actualización: se ha construido la candidata general v19; ver
[QA_TIPOGRAFIA_V19.md](QA_TIPOGRAFIA_V19.md). V18 no superó completamente la
prueba. La aparente diferencia entre capítulos procedía de un estado rápido de
otra ROM. No usar esa captura como validación del capítulo 1.

V19 pasa comprobación de 1.293 eventos, instrucciones intactas, cinco fuentes
idénticas a v13 y cero rechazos en 19.036 textos insertados. La prueba visual
sigue pendiente. Historial v18 a continuación.

V17 falló la prueba del aula: cortes dentro de palabras y espaciado irregular.
Ver [QA_ESPACIADO_V18.md](QA_ESPACIADO_V18.md). La candidata de diagnóstico
`work/probe_ie1_spacing_v18/archive.fa` sustituye al mod v17 para repetir un único
diálogo de la profesora (81000090/287). Pendiente de prueba del usuario; no es una
build completa aprobada. El estado v17 de abajo es el antecedente.

Ver [IE1_V14_EN_CURSO.md](IE1_V14_EN_CURSO.md). La candidata local v17 está generada en
`work/shared/candidatas/probe_ie1_v17/archive.fa` y `work/shared/candidatas/probe_ie1_v17/inazuma123_ie1_v17.3ds`,
instalada como mod de Azahar y pendiente de verificación en juego. Incluye 50
correcciones de variantes en 9700, 18 pares de NPC y partidillos en 8100, reflujo
de 208 px, fuente `FONT12T` restaurada y el rótulo «Objetivo» ajustado dentro de
la textura regenerada. Las candidatas anteriores quedan preservadas.

# Guía de continuidad del proyecto IE1

**Retoma actual (2026-09-09): candidata v23 en [IE1_V14_EN_CURSO.md](IE1_V14_EN_CURSO.md).**
Incluye las correcciones de variantes de 9700, los pares de NPC/partidillo de 8100
y el ajuste tipográfico y del rótulo. Mantiene la verificación estática completa.
Sigue pendiente la prueba guiada en Azahar; las
notas v10–v14 de abajo describen el historial.

Estado más reciente: [preparación de v10](IE1_V10_PREPARACION.md). V9 presenta
regresión gráfica confirmada por el usuario. V10 ya está construida e instalada con copia de v9; queda pendiente de QA jugable.

Este documento describe el flujo que ha seguido Astra para que otro modelo pueda
retomar el trabajo sin confundir una candidata local con una build verificada.
La fuente de verdad son los scripts, los manifiestos de `work/` y el protocolo
de QA; las capturas del chat sirven como evidencia visual, pero no sustituyen la
prueba en Azahar.

## Objetivo y límites

El objetivo actual es traducir al español de España **Inazuma Eleven 1** de la
recopilación 3DS japonesa. Se usan los nombres oficiales europeos del glosario
(`Mark Evans`, `Axel Blaze`, `Raimon`, etc.). No se distribuyen ROMs, extracciones,
logs ni recursos oficiales recuperados: todo lo que procede de una ROM permanece
local en `work/`, que está ignorado por Git.

La candidata v9 es experimental. Conserva la interfaz y la historia de v8 y añade
21 diálogos normales de NPC distribuidos por las zonas tempranas del mapa, pero
**no demuestra que todo el capítulo 1 esté terminado**. La validación offline
del archivo no equivale a una prueba jugable. La v9 está instalada como mod
LayeredFS y la v7 se conserva como reversión hasta que complete la prueba.

## Estructura de trabajo local

- `tools/`: scripts de extracción, análisis, edición y construcción.
- `translation/shared/glossary/`: nombres y términos oficiales.
- `docs/`: formatos, decisiones, incidencias y protocolo de pruebas.
- `work/`: ROM extraída, cachés, manifiestos, previews y builds locales; no se
  versiona.
- `work/ie1/legacy/sueltos/archive_entries.json`: índice cacheado del `archive.fa`; permite buscar
  sin cargar repetidamente el archivo completo.
- `work/probe_ie1_v7_inputs/`: entradas de la candidata v7: `reviewed.json`,
  `ui.json`, `items.json`, `keyboard.json`, `extra/` y vistas previas.
- `work/shared/candidatas/probe_ie1_v7/archive.fa`: candidata v7 construida.

Antes de modificar texto hay que leer `CLAUDE.md`,
`docs/PROTOCOLO_QA_IE1.md` y `docs/SSD_REGISTROS_IE1.md`. También hay que revisar
`docs/FURIGANA_LECCIONES.md` para no repetir enfoques ya rechazados.

Las entradas de v9 son work/probe_ie1_v9_inputs/ y la candidata construida es
work/shared/candidatas/probe_ie1_v9/archive.fa. Copiar esas entradas al iniciar una v10; nunca
editar v8, v7 ni la ROM original. V9 conserva las métricas latinas nativas para
FONT12 y FONT8, rótulos de capítulos 1 a 10 y el ajuste aislado del logo Ventisca.

## Flujo que se debe seguir

1. Trabajar siempre sobre una copia o un directorio de candidata, conservando el
   original y anotando sus hashes. No editar directamente la ROM original.
2. Localizar el recurso mediante el índice de `archive.fa` y extraer solo el
   fragmento necesario. Para SSD usar `ie123kit.nucleo.eventos.ssd`; no tratar el texto
   como cadenas separadas por NUL: cada registro lleva un tamaño inline.
3. Preparar traducciones revisadas con hash del texto original. Una sustitución
   debe comprobar que sigue editando exactamente la cadena esperada, conservar
   instrucciones, índices, controles y argumentos, y rechazar el texto si no cabe.
4. Para gráficos CTPK/ARCV/SSZL usar `ie123kit._legado.ui_archive`, `ie123kit.nucleo.graficos.ctpk` y
   `ie123kit._legado.translate_ui_textures`. Mantener dimensiones, formato, metadatos y
   tamaño de entradas. Crear una preview y revisarla antes de empaquetar.
5. Para tablas binarias usar `ie123kit.ie1.texto.tablas` (el original `ie1_tables.py` está retirado; en git, ver `docs/toolkit/SCRIPTS_RETIRADOS.md`): modificar solo
   campos conocidos y comprobar que estadísticas, punteros y bytes no relacionados
   permanecen iguales. Los nombres largos que no caben se dejan pendientes.
6. Ejecutar los fixtures y validaciones, construir una candidata nueva y guardar
   su informe de hashes. No llamar “estable” a una build que solo pasó validadores.
7. Con Azahar cerrado, conservar la candidata instalada anterior y activar la
   nueva como mod LayeredFS. Registrar archivo, hash, emulador y configuración.
8. El usuario juega y controla el emulador; el modelo observa capturas y logs y
   no envía entradas durante la prueba. Seguir exactamente el protocolo hasta la
   primera pachanga: ante el primer fallo, detenerse, corregir y repetir la misma
   reproducción antes de continuar.

## Construcción de la candidata v7

La orden reproducible usada fue:

```text
python -m ie123kit.nucleo.compat.congelados build_ie1_probe --events 92010100 92010200 92010250 92010300 92010340 92010400 92010500 81000040 91010000 92010510 92104100 92104200 83000040 --fullwidth --reviewed-json work/probe_ie1_v7_inputs/reviewed.json --extra-files work/probe_ie1_v7_inputs/extra --output work/shared/candidatas/probe_ie1_v7/archive.fa
```

La v7 instalada tiene SHA-256
`9d1a80d9cada5c39179356042b5a4f84268617591157373629b8d1776f78e26c`. La copia
anterior está en `work/shared/candidatas/probe_ie1_v7/previous-installed.fa`. La build incluye
menús, guardado, teclado latino, botones de partido, logos, pantallas iniciales,
lugares, objetivos, 1.132 nombres cortos, 28 objetos y los eventos indicados en
la orden. Los vídeos no se modifican.

Para comprobar una instalación local:

```text
Get-Process -Name azahar -ErrorAction SilentlyContinue
Get-FileHash work/shared/candidatas/probe_ie1_v7/archive.fa -Algorithm SHA256
```

No sustituir una build instalada mientras Azahar esté abierto. El enlace de mods
actual está en `...\\Azahar\\load\\mods\\00040000000BB800\\romfs\\archive.fa`;
la ruta exacta puede variar según la instalación del usuario.

## Construcción de la candidata v8

La orden reproducible usada fue:

    python -m ie123kit.nucleo.compat.congelados build_ie1_probe --events 92010100 92010200 92010250 92010300 92010340 92010400 92010500 92010520 92010550 92010600 92010620 92010640 81000040 91010000 92010510 92104100 92104200 83000040 --fullwidth --reviewed-json work/probe_ie1_v8_inputs/reviewed.json --extra-files work/probe_ie1_v8_inputs/extra --output work/shared/candidatas/probe_ie1_v8/archive.fa

La candidata tiene SHA-256
246341bad13ca68f36c7dffe221647b81fe7936e427138c8fe00fd59db9650f8. El
informe contiene 184 sustituciones, sin registros rechazados ni ausentes. Aun
así, no se instala ni se llama estable hasta cerrar Azahar y completar el
recorrido de QA.

## Construcción de la candidata v9

La candidata v9 parte de las entradas v8 y añade únicamente 21 registros
revisados de diálogo normal en 81000040. Se eligieron conversaciones de NPC de
instituto, accesos, zona comercial y rutas tempranas; no incluye elecciones,
modales, recuperación ni disparadores de escena. Cada texto nuevo conserva el
mismo número de páginas que su equivalente japonés y está asociado al SHA-256 de
su registro original.

    python -m ie123kit.nucleo.compat.congelados build_ie1_probe --events 92010100 92010200 92010250 92010300 92010340 92010400 92010500 92010520 92010550 92010600 92010620 92010640 81000040 91010000 92010510 92104100 92104200 83000040 --fullwidth --reviewed-json work/probe_ie1_v9_inputs/reviewed.json --extra-files work/probe_ie1_v9_inputs/extra --output work/shared/candidatas/probe_ie1_v9/archive.fa

La candidata tiene SHA-256
6c8f154fce7e37a5d137043ae6783a545eb1f54ce758c43a68a940f1a6b16fff.
El informe contiene 205 sustituciones, sin rechazadas ni ausentes. La
comprobación estática confirmó que, frente a v8, los únicos cambios de
81000040 son esos 21 registros; el bytecode de ese evento permanece idéntico.
La v9 se instaló con Azahar cerrado. El mod activo coincide con este SHA-256 y
la v7 quedó conservada en work/shared/candidatas/probe_ie1_v9/previous-installed.fa como reversión.
La prueba en Azahar sigue pendiente.

El campo corto del NPC Sr. Veteran admite siete caracteres transportados; v8
usa Veteran en la placa para no cambiar el tamaño fijo del registro. No ampliar
el registro ni intentar introducir el nombre completo sin una investigación del
formato y una regresión en juego.

## Qué queda pendiente

- Probar v9 desde partida nueva hasta la primera pachanga y registrar cada NPC,
  empezando por los 21 diálogos recién añadidos.
- Completar eventos y NPC restantes del capítulo 1 después de superar esa prueba.
- En la siguiente tanda, localizar la interfaz de pachangas, el rótulo de límite
  de tiempo, lugares y misiones pendientes, formación/equipamiento y las
  métricas de los puntos suspensivos.
- Localizar y traducir cadenas dinámicas que todavía puedan aparecer en ranuras,
  nombres, equipamiento o pantallas no cubiertas por las texturas sustituidas.
- Revisar nombres largos omitidos, más descripciones de objetos y cualquier crash
  de NPC de evento con modal. Los eventos protegidos por modales no se traducen a
  ciegas: primero se reproduce y se entiende su cierre.
- No cambiar el ejecutable/CRO ni los vídeos sin evidencia y una prueba específica.

## Diagnóstico y documentación

Los fallos nuevos se anotan en `docs/QA_IE1_INCIDENCIAS.md` con build, escena,
evento, acciones, resultado esperado, captura y log. Las limitaciones de formato
van en `docs/SSD_REGISTROS_IE1.md` o `docs/FORMATOS.md`; no se esconden en el chat.
Antes de publicar cualquier parche, verificar que `git ls-files` no incluye ROMs,
`work/`, logs, archivos extraídos ni logos oficiales locales.
