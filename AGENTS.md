# Retoma del proyecto

## Terminología confirmada por el usuario

- PT = puntos de técnica; PE = puntos de resistencia (versión castellana).
  Usar estas siglas también en indicadores gráficos y textos de ayuda.

## BLOQUEO DE CAJA Y TIPOGRAFÍA — orden explícita del usuario

- Referencia aprobada: **v34** (2026-09-19). El usuario autorizó actualizar el bloqueo a su motor de
  textos: glifos europeos y espaciado corregido, letras dobles, caja ancha de 37 caracteres por
  3 líneas y páginas de 131 B como máximo. **Ampliado el 2026-09-22** (el usuario probó la candidata
  IE3 v04 y la dio por «perfecta», y pidió aplicarlo a IE1 e IE2): búfer de página de 256 B en los tres
  CRO (`ie123kit.nucleo.ejecutable.bufer_pagina`), páginas de hasta 250 B, es decir 3 líneas llenas de
  37 caracteres en ancho completo. La codificación sigue siendo la misma (2 B por letra): el usuario
  rechazó expresamente pasar a 1 byte. No modificar caja, dimensiones, posición, tamaño de letra,
  glifos, espaciado, fuentes, codificación ni algoritmo de saltos sin una nueva petición expresa.
- Las cinco fuentes exactas se verifican con `tools/dialogue_lock.py`.
- Las nuevas traducciones deben adaptarse a esta configuración. Un texto largo
  no autoriza a cambiar la caja, las fuentes o el motor para hacerlo caber.
- No eliminar, desactivar, actualizar hashes ni sortear el bloqueo para compilar.
  Solo una nueva petición explícita del usuario sobre la tipografía permite
  revisar esta protección. Una petición general de continuar o traducir no basta.
- Esta aprobación se refiere al aspecto observado; no significa que toda la ROM
  o todos los capítulos hayan superado el recorrido QA.

- Objetivo actual (2026-09-22): IE3 Fuego Explosivo (issue #90 y #91-#96) y llevar el nuevo reparto de
  3 × 37 al IE1 y al IE2 (#95). IE1 e IE2 siguen en QA por el usuario.
- IE3: la fuente de texto, gráficos, voces y vídeos es la CIA europea de Fuego Explosivo (trae en `es/`
  los guiones `inazuma3` —Fuego y Rayo Celeste, idénticos— e `inazuma3_ogre`). El motor de diálogo es
  el de @AlbertooCh (`ie123kit.ie3`, referencias `@offset,longitud` de eve→evet) con el reparto y la
  codificación del IE2. Capas en `work/ie3/<versión>/capas` y `work/ie3/shared/capas`.
- Leer `CLAUDE.md` y `docs/PROTOCOLO_QA_IE1.md`. El protocolo es una instrucción
  explícita del usuario: cajas de diálogo sin bugs gráficos; recorrido hasta la
  primera pachanga con varios NPC; detenerse ante cada fallo, corregirlo y repetir
  exactamente su reproducción antes de continuar.
- Consultar `docs/SSD_REGISTROS_IE1.md` antes de tocar el texto. El reinsertor
  antiguo omite el tamaño de cada registro inline. Las conclusiones históricas de
  imposibilidad no son evidencia de que el formato correcto falle.
- Flujo acordado con el usuario el 2026-09-05: el usuario juega y prueba; el agente
  observa el emulador y sus logs sin enviar entradas de teclado/ratón durante la
  prueba. Preparar correcciones y volver al punto del fallo con el usuario.
- No subir ROMs, extracciones, logs ni datos oficiales recuperados. Mantener los
  originales y distinguir una candidata de una build verificada en juego.

## Después de construir una candidata: versión visible (instrucción del usuario, 2026-09-22)

- La pantalla de aviso del arranque muestra la versión del parche. **Cada candidata nueva la actualiza**
  antes de instalarse: `VERSION` en `work/ie1/capas/graficos/creditos_javiju/render.py` (formato
  `vX.Y beta - IE3 vNN`, o el de la release), `python render.py`, `python video.py logo_l5_original_jp.moflex
  extra/movie/logo_l5.moflex` y sustituir `movie/logo_l5.moflex` en el archive.fa de la candidata.
- Nunca instalar una candidata cuya pantalla de aviso diga otra versión.

## Espacio en disco: instrucción del usuario

- No acumular builds ni copias históricas en `work/`. Mantener solo la candidata
  actual y sus entradas necesarias. Tras verificar la nueva candidata y su copia
  instalada, borrar los binarios de la anterior, no archivarlos en otra carpeta.
- No generar una ROM completa adicional si basta actualizar el mod de Azahar.
- Eliminar intermediarios de extracción y empaquetado, cachés regenerables y logs
  duplicados al terminar. Conservar informes pequeños útiles para el diagnóstico.
- Nunca borrar originales, guardados, traducciones revisadas, manifiestos,
  recursos únicos o herramientas necesarias para reconstruir la candidata.
- Antes de borrar, comprobar las rutas absolutas, las dependencias y la candidata
  instalada. Si el usuario ha limpiado archivos manualmente, inventariar el estado
  real y no asumir que siguen existiendo builds citadas en notas históricas.

## Herramientas (ie123kit)

- El código Python vive en `tools/src/ie123kit` (instalar con `pip install -e tools[dev]`); en `tools/`
  solo hay shims generados con `python -m ie123kit.nucleo.compat.shims generar`. Mapa en `tools/README.md`.
- Los 5 congelados (`dialogue_typography.py`, `font_patch.py`, `dialogue_lock.py`, `build_ie1_probe.py`,
  `build_ui_revision.py`) siguen en `tools/` y no se tocan ni se copian.
- Tests: `python -X utf8 -m pytest tools/tests -m "not requiere_rom"` (y `-m requiere_rom` en local con
  `work/`). Guardias: `python -m ie123kit.nucleo.compat.guardia bloqueados`, `... guardia git` y
  `python -m ie123kit.nucleo.compat.shims comprobar`.
- No se desactiva ni se salta la CI `.github/workflows/toolkit.yml` (filtrada a `tools/**`) ni
  `.github/workflows/guardia.yml`, que corre **sin filtro de rutas** en todos los commits y es la que
  impide subir ROMs o datos extraídos en cualquier carpeta. No añadir `paths` a `guardia.yml`.
