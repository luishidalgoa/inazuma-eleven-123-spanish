# Retoma del proyecto

## Terminología confirmada por el usuario

- PT = puntos de técnica; PE = puntos de resistencia (versión castellana).
  Usar estas siglas también en indicadores gráficos y textos de ayuda.

## BLOQUEO DE CAJA Y TIPOGRAFÍA — orden explícita del usuario

- El usuario confirma que la apariencia de los diálogos de v20 está muy bien.
  Es la referencia aprobada. No modificar caja, dimensiones, posición, tamaño
  de letra, glifos, espaciado, fuentes, codificación ni algoritmo de saltos.
- Mantener fullwidth, avance de cálculo 11, límite 220 y tres líneas por página,
  con las cinco fuentes exactas verificadas por `tools/dialogue_lock.py`.
- Las nuevas traducciones deben adaptarse a esta configuración. Un texto largo
  no autoriza a cambiar la caja, las fuentes o el motor para hacerlo caber.
- No eliminar, desactivar, actualizar hashes ni sortear el bloqueo para compilar.
  Solo una nueva petición explícita del usuario sobre la tipografía permite
  revisar esta protección. Una petición general de continuar o traducir no basta.
- Esta aprobación se refiere al aspecto observado; no significa que toda la ROM
  o todos los capítulos hayan superado el recorrido QA.

### Actualización del 2026-11-10 (orden explícita del usuario): qué rige hoy en el diálogo

- El 2026-09-23 el usuario comparó con su 3DS el original europeo y autorizó, para el diálogo de
  IE1 e IE3: (a) los avances europeos en `FONT12.bcfnt`, (b) los saltos de línea y de caja del port
  europeo 1:1 y (c) la ventana ancha en la CRO (0x280, rejilla 0x2A0). Lo implementan las capas
  `work/shared/capas/fuentes/avances_eu`, `work/ie1/capas/dialogo/saltos_eu` y
  `work/shared/capas/menus_cro/dialogo_ancho_eu`. La release v3.0 salió con ellas.
- El 2026-11-10 el usuario confirmó que esa autorización sigue vigente y autorizó reflejarlo aquí.
  Por tanto, **la referencia del diálogo es el texto y los saltos del original (EU 3DS en IE1/IE3,
  NDS española en IE2), no «avance 11 / límite 220»**. Esos valores y los hashes de
  `tools/dialogue_lock.py` describen solo el constructor antiguo (`tools/build_ie1_probe.py`) y
  siguen congelados (los vigila la guardia): **no reconstruir el archive con ese constructor ni
  aplicar el v20 sobre el texto europeo**, porque sube las cajas un 29,9 % (26.003 → 33.773).
- Sigue vigente todo lo demás: Norma 3 (no condensar), Norma 4 (`docs/FURIGANA_LECCIONES.md`),
  `docs/PROTOCOLO_QA_IE1.md` y la prohibición de tocar fuentes, caja o codificación sin una nueva
  petición explícita del usuario.
- **Petición explícita del 2026-11-11 (codificación de las descripciones de menú de IE1):** el usuario autorizó
  cambiar a «una letra por byte» SOLO las descripciones de menú de IE1 (técnicas `command.STR`, objetos `item.STR`,
  jugadores `unitbase.STR`) para poner el texto oficial europeo. No alcanza al diálogo (ya hecho con ancho completo), ni a
  las fuentes ni a la caja. Se hace por lotes: primero un lote piloto pequeño que el usuario prueba en el juego (2 minutos);
  solo si pasa, se extiende. Con copia de seguridad y revisión independiente.

- Objetivo actual: traducir y depurar Inazuma Eleven 1 de la recopilación 3DS.
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
