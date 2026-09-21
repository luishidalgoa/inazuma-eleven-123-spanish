# Retoma del proyecto

## Terminología confirmada por el usuario

- PT = puntos de técnica; PE = puntos de resistencia (versión castellana).
  Usar estas siglas también en indicadores gráficos y textos de ayuda.

## Estado actual y objetivo

- Objetivo actual: continuar la localización de Inazuma Eleven 3 dentro de
  Inazuma Eleven 1･2･3!! Endou Mamoru Densetsu para Nintendo 3DS.
- Prioridad actual:
  1. Spark / Rayo Celeste.
  2. Ogre / La Amenaza del Ogro.
  3. Bomber / Fuego Explosivo más adelante.
- Disponemos de los textos oficiales europeos de Spark y Ogre.
  Bomber se deja para cuando la lógica de cuadros de diálogo esté bien resuelta.
- Para pruebas de ejecución usar principalmente Spark: los primeros 2-3 minutos
  contienen textos cortos, largos y casos frontera muy útiles para validar cajas,
  saltos, paginación y caracteres españoles.
- El objetivo no es traducir únicamente los diálogos. También hay que localizar,
  cuando exista equivalente oficial: objetivos de misión de la pantalla superior,
  menús, descripciones, textos de ayuda, técnicas, objetos y demás strings visibles.

## Cuadros de diálogo y referencias

- No asumir que las antiguas restricciones de tamaño son límites reales del motor.
  Parte de ellas se introdujeron históricamente para evitar que agentes modificasen
  incorrectamente estructuras y tamaños.
- Antes de inventar una solución nueva, estudiar la implementación más reciente de
  cajas de diálogo existente en la rama `estado-ie2-cajas`:
  `https://github.com/luishidalgoa/inazuma-eleven-123-spanish/tree/estado-ie2-cajas`.
- Comparar nuestro estado con esa rama y traer, cuando sea seguro, documentación
  nueva o actualizada que falte localmente. No hacer merges ciegos ni sobrescribir
  documentación local útil.
- Estudiar específicamente qué se ha hecho en IE2 para tamaños, límites, párrafos,
  saltos, SSD, PKB/PKH y reinserción, y reutilizar ese conocimiento cuando sea
  aplicable a IE3.
- Revisar también la herramienta `IE-repack` antes de desarrollar desde cero una
  funcionalidad equivalente:
  `https://github.com/Javiju555/IE-repack`.
- Las versiones europeas oficiales deben utilizarse como referencia empírica:
  Spark JP ↔ Rayo Celeste ES y Ogre JP ↔ Amenaza del Ogro ES.
- No alinear únicamente por offsets binarios. Comparar estructura, eventos,
  registros, códigos de control, tamaños, saltos, párrafos y metadata.
- Separar siempre tamaño binario y tamaño visual. Un carácter puede ocupar más
  bytes en la codificación japonesa parcheada sin ocupar más ancho en pantalla.
- Reutilizar los encoders, parsers y métricas existentes antes de crear otros.

## Documentación y trazabilidad

- Leer antes de trabajar todos los `.md` relevantes, README y documentación técnica
  aplicable. Leer también `HISTORIAL_CODEX.md` y `EXPLICACIONES_CODEX.md` si existen.
- Mantener `HISTORIAL_CODEX.md` como registro cronológico del trabajo realizado.
  No registrar únicamente qué se cambió: explicar también por qué se cambió,
  qué problema resolvía, qué pruebas se hicieron y qué resultado se obtuvo.
- Mantener `EXPLICACIONES_CODEX.md` para justificar decisiones técnicas importantes.
  Antes de un cambio relevante documentar problema, evidencia, hipótesis, alternativas,
  solución elegida, riesgos y plan de validación. Después actualizar con el resultado.
- Diferenciar claramente hechos confirmados, observaciones e hipótesis.
  No presentar una hipótesis como un hecho.
- No borrar información histórica útil porque un enfoque quede obsoleto; marcarlo
  como sustituido, descartado u obsoleto y explicar el motivo.

## Uso de agentes y subagentes

- Usar subagentes cuando existan líneas de investigación independientes, por ejemplo:
  estudiar `estado-ie2-cajas`, analizar `IE-repack`, comparar JP/ES o localizar menús,
  objetivos y descripciones.
- Priorizar subagentes de exploración/solo lectura para estas tareas.
- El agente principal debe coordinar los resultados, esperar las investigaciones
  relevantes antes de tomar decisiones importantes y realizar o coordinar la
  implementación final.
- Evitar que varios agentes modifiquen simultáneamente los mismos archivos.
- No usar subagentes para tareas triviales cuando no aporten una ventaja real.

## Archivos oficiales y datos locales — orden explícita del usuario

- No borrar bajo ningún concepto los archivos oficiales disponibles localmente salvo
  petición explícita del usuario.
- Esto incluye ROMs, CIAs, `.3ds`, dumps, RomFS, ExeFS, versiones europeas y japonesas,
  traducciones oficiales extraídas, PKB/PKH, SSD originales, audios, vídeos, fuentes,
  tablas y cualquier recurso oficial útil para comparación o reconstrucción.
- Los archivos oficiales pueden y deben mantenerse fuera de Git mediante `.gitignore`.
  Que un archivo esté ignorado por Git no autoriza a borrarlo del disco.
- No sustituir originales por archivos modificados. Mantener originales y derivados
  claramente diferenciados.
- No subir ROMs, extracciones, logs ni datos oficiales recuperados al repositorio.
- Antes de limpiar cualquier archivo, comprobar si es original, referencia JP/ES,
  entrada necesaria para reproducir una build o recurso único.
- Ante cualquier duda sobre si un archivo puede borrarse: no borrarlo.

## Git — orden explícita del usuario

- Antes de modificar nada ejecutar `git status` y conservar cualquier trabajo local.
- Se permite utilizar localmente `git status`, `git diff`, `git log`, `git show`,
  `git branch`, `git fetch`, comparar ramas y realizar commits locales cuando sea útil.
- BAJO NINGÚN CONCEPTO hacer `git push` salvo petición explícita del usuario.
- "Continúa", "termina", "integra", "haz commit", "actualiza el proyecto" o frases
  similares NO son autorización para hacer push.
- Solo hacer push si el usuario indica explícitamente que quiere subir los cambios
  al remoto.
- No hacer force push, crear ramas remotas, tags remotos o Pull Requests sin permiso.
- No hacer `git reset --hard`, `git clean -fd` ni descartar cambios locales no
  entendidos.
- No hacer merges ciegos. Comparar antes y conservar información útil de ambas partes.

## Espacio en disco: instrucción del usuario

- No acumular builds ni copias históricas innecesarias en `work/`.
- Se pueden eliminar temporales, cachés, logs duplicados e intermediarios claramente
  regenerables, pero nunca archivos oficiales ni referencias necesarias.
- No generar una ROM completa adicional si basta actualizar el mod de Azahar.
- Mantener los originales, guardados, traducciones revisadas, manifiestos, recursos
  únicos y herramientas necesarias para reconstruir la candidata.
- Antes de borrar, comprobar rutas absolutas, dependencias y si el archivo es necesario.
- Si el usuario ha limpiado archivos manualmente, inventariar el estado real y no
  asumir que siguen existiendo builds citadas en documentación antigua.

## Herramientas (ie123kit)

- El código Python vive en `tools/src/ie123kit` (instalar con `pip install -e tools[dev]`);
  en `tools/` solo hay shims generados con
  `python -m ie123kit.nucleo.compat.shims generar`. Mapa en `tools/README.md`.
- Antes de crear una herramienta nueva, buscar si ya existe funcionalidad equivalente
  en `ie123kit`, en `estado-ie2-cajas` o en `IE-repack`.
- Reutilizar y ampliar herramientas existentes antes de crear scripts ad-hoc.
- Los 5 congelados (`dialogue_typography.py`, `font_patch.py`, `dialogue_lock.py`,
  `build_ie1_probe.py`, `build_ui_revision.py`) siguen en `tools/` y no se tocan ni
  se copian salvo nueva instrucción explícita o documentación más reciente que
  indique otra cosa.
- Tests: `python -X utf8 -m pytest tools/tests -m "not requiere_rom"` (y
  `-m requiere_rom` en local con `work/`).
- Guardias: `python -m ie123kit.nucleo.compat.guardia bloqueados`,
  `python -m ie123kit.nucleo.compat.guardia git` y
  `python -m ie123kit.nucleo.compat.shims comprobar`.
- No se desactiva ni se salta la CI `.github/workflows/toolkit.yml` ni
  `.github/workflows/guardia.yml`.
- `.github/workflows/guardia.yml` debe seguir ejecutándose sin filtro de rutas y
  bloquear ROMs o datos extraídos. No añadir `paths` para evitar su ejecución.

## Forma de trabajo

- Antes de desarrollar algo nuevo: revisar código existente, documentación,
  `estado-ie2-cajas`, `IE-repack` cuando sea relevante y los originales europeos.
- No limitarse a elaborar informes: investigar, implementar, ejecutar herramientas
  y validar realmente los resultados.
- Para cambios importantes: evidencia → hipótesis → explicación → implementación
  → validación → historial.
- No declarar resuelto un problema únicamente porque la build compile o arranque.
- Distinguir siempre entre build generada, candidata y verificada en juego.
- Priorizar soluciones reproducibles, automatizadas, mantenibles y reutilizables.
- No ocultar warnings ni sortear guardias para obtener una build aparentemente válida.