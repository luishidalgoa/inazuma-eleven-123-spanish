> Actualización 2026-09-24: toolkit F2.7 (#102), `tools/` sin shims
>
> Retirados los 22 shims de `tools/`: todo el código (capas de `work/`, tests, paquete, CI y documentación)
> importa ya `ie123kit.<...>`. En `tools/` solo quedan los 5 congelados del bloqueo tipográfico y los `.ps1`.
> Equivalencias en [`tools/README.md`](../tools/README.md) y
> [`toolkit/ESTADO_MIGRACION.md`](toolkit/ESTADO_MIGRACION.md). Sin cambios en la tipografía ni en las candidatas.

> Actualización 2026-09-11: v33, partidos de historia, rótulos, CRO, datos y texturas
>
> Candidata `work/shared/candidatas/probe_ie1_v33/archive.fa` (SHA-256
> `b65cd7eacc170580b9b24c1da1921fe488b33ab44cd769679d28dc0b48285314`), sobre v32.
> 4.628 diálogos de los partidos de historia (oficial NDS alineado), 336 rótulos y
> objetivos, 155 literales del CRO, títulos/Contactos/campos/jugadores, mensajes del
> sistema, menú común de la recopilación y unas 400 texturas (supertécnicas 3D,
> institutos, partido, menús, fondos de historia, 87 páginas de ayuda y créditos).
> Prueba jugable pendiente. Detalle: [`IE1_V33_TANDA.md`](IE1_V33_TANDA.md).
> Publicada como **release v1** (`patch/inazuma123-es-v1.xdelta`, SHA-256
> `19fb1f41…7266b05`; zip con DeltaPatcher montado por `.github/workflows/release.yml`).
> Ver [`DISTRIBUCION_DELTAPATCHER.md`](DISTRIBUCION_DELTAPATCHER.md).

> Actualización 2026-09-11: v32, blog, textos de partido y pantallas restantes
>
> Candidata `work/shared/candidatas/probe_ie1_v32/archive.fa` instalada (SHA-256
> `4043c5c979d4d5f272567edecfba6db96355ab06764d7c1f737567e9a8a7498a`), sobre v31.
> Futblog completo (310 textos del oficial NDS condensados a las líneas del 3DS),
> gritos de partido, objetivos restantes, nombres de escuela y 30 texturas de fin de
> partido, blog, uniformes, capitán, carpeta, Centella, entrenamiento especial,
> transferencia de técnicas y penaltis. Verificación estática completa; prueba
> jugable pendiente. Detalle: [`IE1_V32_TANDA.md`](IE1_V32_TANDA.md).

> Actualización 2026-09-11: v31, técnicas, objetos y equipos oficiales
>
> Candidata `work/shared/candidatas/probe_ie1_v31/archive.fa` instalada (SHA-256
> `e19252b1e6cc2ddf4a0b8b46c7baddea1182d7f7b87bcfae51bd8003eb00f746`), sobre v30.
> Con la ROM NDS española como fuente oficial: 131 supertécnicas y sus 114
> descripciones, 261 rótulos de supertécnica en partido, 307 nombres y 300
> descripciones de objetos, y 130 nombres de equipo corregidos (con sus placas y
> diálogos). Glosarios versionados: `equipos.csv`, `tecnicas.csv`, `objetos.csv`.
> Verificación estática completa; prueba jugable pendiente.
> Detalle: [`IE1_V31_TANDA.md`](IE1_V31_TANDA.md). Issues #21, #22 y #23.

> Actualización 2026-09-11: v30, menú de la bolsa y sus pantallas
>
> Candidata `work/shared/candidatas/probe_ie1_v30/archive.fa` instalada (SHA-256
> `447f2bd8b44081f5b039c62ce2f20f2fc315713c1106496d847a1eea430f31af`), sobre v29.
> Traduce el menú de la bolsa, las pantallas de Cambios, Tácticas, Fichar, Fichero,
> Tienda y subida de nivel, y corrige temas mal traducidos de la guía del sistema.
> Solo texturas; verificación estática completa y prueba jugable pendiente.
> Detalle: [`IE1_V30_TANDA.md`](IE1_V30_TANDA.md). Issue #23. Técnicas y objetos
> (#22) esperan los nombres oficiales de la versión NDS española.

> Actualización 2026-09-11: v29, descripciones de jugadores, pantalla VS y equipos
>
> Candidata `work/shared/candidatas/probe_ie1_v29/archive.fa` instalada en Azahar (SHA-256
> `cbada7a494f1b392dd7f9260830d208986583fef8c10e3c8a68a49fa89eaf465`), generada sobre
> v28. Incluye las 1.040 descripciones de perfil, las placas y rótulos de campo de
> la pantalla VS, nombres oficiales Brain/Farm/Inazuma Kids FC/Kasamino en
> `team.pkb` y 9 diálogos, PE/PT en recuperación de objetos y el lote de interfaz
> `ui_followup`. Verificación estática completa; prueba jugable pendiente. Detalle:
> [`IE1_V29_TANDA.md`](IE1_V29_TANDA.md). Issues #21 y #22.

> Actualización 2026-09-09: v27, auditoría completa de diálogos
>
> La candidata actual era `work/shared/candidatas/probe_ie1_v27/archive.fa`, instalada en Azahar con hash
> `91f816060775190e994f585fae5e09c8adab4cc1998b059f250372387ab10369`. La auditoría
> directa de los 982 eventos seleccionados encuentra 18.806 diálogos visibles y ningún
> carácter japonés; el reinserto deja 19.039 textos y 0 rechazos. Se eliminaron los tres
> restos de pausa que quedaban en 9210.

> Auditoría de alcance IE1 (2026-09-09): los bloques de historia `9201`–`9210`
> cubren los diez capítulos del atlas (de «¡Llega la Royal!» a «¡La batalla
> final!»): 289 eventos y 5.164 diálogos visibles, todos en español. Las zonas y
> variantes de NPC auditadas (`8100`, `6200`, `6300`, `8400`, `8500`, `8600`,
> `9000`–`9120`, `9340`, `9341`, `9380`, `9391`, `9700`, `9713` y `9799`)
> suman 1.953 diálogos de Raimon y 1.836 de eventos compartidos, también sin
> japonés visible. La auditoría completa queda en
> `work/shared/candidatas/probe_ie1_v27/chapter_coverage_audit.json`. La cobertura es estática;
> todavía falta recorrer una partida nueva en Azahar para validar cada capítulo,
> NPC y transición en juego.

> Distribución 2026-09-09: el parche `patch/inazuma123-es-v27.xdelta` se ha
> regenerado contra esta candidata y su SHA-256 es
> `40d81657b9612b4bf232d92e1ae42fc35ddc03f2bbceeb1e94d67187c0e54d47`.
> El paquete portable local `work/shared/releases/release_inazuma123_es_v27_deltapatcher.zip`
> contiene las instrucciones, el lanzador, DeltaPatcher portable y solo el
> parche; la ROM traducida temporal se eliminó después de verificarlo.

> Actualización 2026-09-09: v26 instalada y verificada
>
> La candidata actual es `work/shared/candidatas/probe_ie1_v26/archive.fa`, con hash
> `394b3ea3f986204a5ed7bb9d8fb2a349333d6b15490736cf16f259ca1dcfa27f`.
> Se corrigieron los 27 registros que aún rechazaba el límite de tamaño y el informe
> queda con 19.036 textos traducidos, 0 rechazos y 106 registros vacíos/no visibles.
> La auditoría de pachangas, cadena y Royal mantiene 1.422 líneas visibles sin japonés,
> además de 158 nombres de equipo y 32 categorías de clubes. La prueba jugable guiada
> en Azahar sigue pendiente; la instalación coincide byte a byte con la candidata.

> Actualización 2026-09-06: candidata IE1 v9 instalada para prueba; añade 21 diálogos normales de NPC y conserva la interfaz de v8. Sigue pendiente QA desde partida nueva.
> Ver [detalle y limitaciones](IE1_UI_Y_CAPITULO1.md). Las etiquetas históricas
> de estabilidad que aparecen abajo no sustituyen el protocolo QA vigente.

> Actualización 2026-09-07: la candidata local v14 ya está generada como archivo
> de datos y ROM `.3ds`, sin instalar y sin verificación jugable. La entrada local de trabajo cubre 19.039 registros en 982 eventos:
> diálogos de historia y NPC de 9202–9209, las zonas 8100 de Raimon, la caseta,
> la torre Inazuma, ubicaciones, misiones, variantes de reclutamiento y visor de
> eventos. La validación estática conserva hashes e instrucciones, con 0 rechazos
> de longitud en la auditoría recuperada. Falta la prueba guiada en Azahar; no se
> considera una build estable hasta repetir allí las conversaciones y la primera
> pachanga.

> Actualización 2026-09-07 (continuación): se corrigieron 199 textos que habían
> heredado otra variante o mostraban marcadores antiguos pegados. La validación
> vuelve a pasar los 19.039 registros, con instrucciones intactas, cero japonés
> visible y máximo de 245 bytes codificados. También se añadieron ocho diálogos
> visibles de transición de 9201 y se limpiaron marcadores antiguos en NPC, rótulos
> y escenas de la torre. Las elipsis intencionadas se dejaron sin
> cambios. La candidata se generó después de esta validación y queda pendiente
> de prueba guiada en Azahar.

> Actualización 2026-09-08: la candidata v16 está generada e instalada en Azahar.
> Conserva la imagen original de `FONT12T`, añade un píxel de avance a las letras
> latinas y usa 208 px útiles para reflujo, de modo que las frases ocupen el ancho
> de la caja sin cortes extraños. Se ajustó el rótulo «Objetivo» al interior del
> marco y se corrigieron 18 pares desalineados de NPC y partidillos en 8100.
> Validación: 19.039 hashes, 965 eventos modificados, 0 rechazos y 3 pausas de
> puntos suspensivos intencionadas. Falta la prueba jugable guiada.

> Actualización 2026-09-08 (v20): tras confirmar que v19 seguía dejando media
> caja vacía y juntando letras, se recuperó el transporte `fullwidth` usado en
> v13 junto con sus fuentes coordinadas. Se revisaron 36 textos que excedían el
> límite con la codificación anterior. V20 está instalada en Azahar; validación:
> 19.036 textos, 1.293 eventos, instrucciones intactas y cero rechazos. La v19
> fue eliminada después de comprobar el hash de la instalación.

> Actualización 2026-09-08 (v17): se regeneró `field_t.arc` con el rectángulo
> interior correcto para «Objetivo»; la candidata v17 (`work/shared/candidatas/probe_ie1_v17/`)
> sustituye a v16 en Azahar y conserva su copia de seguridad. El resto de los
> recursos gráficos permanece igual. Validación: SHA-256 de `archive.fa`
> `307e3bcec3d084021535b943123e2a511a43cc7274eb54621346d37b19c38cf9`, cero
> rechazos, cero cambios en instrucciones y roundtrip íntegro en la ROM de 2 GiB.

# Progreso del proyecto

- 2026-09-15 · Toolkit F1.1: esqueleto del paquete `ie123kit` (`tools/src`, `tools/pyproject.toml`), plantilla de shims de compatibilidad, tests de arquitectura y unidad; puertas 1-4 en verde (pytest 75 passed, unittest OK, importaciones y golden v67 a 0). Ficheros bloqueados v20 intactos.
- 2026-09-15 · Toolkit F1.2: archivados 25 scripts retirados en `tools/_archivo` (con README); `patch_code.py` y `patch_cro.py` siguen en `tools/` porque un script activo los importa (pasan a `_legado` en F1.4). Añadido `nucleo/compat/importadores.py`. Ficheros bloqueados v20 intactos.
- 2026-09-15 · Toolkit F1.3: 16 módulos de motor trasladados a ie123kit.nucleo (compresion, contenedores, graficos, fuentes, eventos, ejecutable, construir) con shims de alias en tools/; CLI con salida en fachadas _legado; nuevo nucleo/validar/bloqueo (puerta del bloqueo v20); REPO/ROOT de fa_repack, harvest_log y limpiar_work vía find_root (mods_to_moflex queda para F1.4). Ficheros bloqueados v20 intactos.
- 2026-09-16 · Toolkit F1.4: 13 módulos más trasladados a ie123kit (texto NDS y eventos, re-exports perezosos de los bloqueados, sjis_portador, gráficos y media, verificación de candidatas, nucleo/construir/candidata) con shims de alias (29 en total); cuarentena _legado con --legado-lo-se para ds_roster, reinsert_var, ssd_reinsert y validate; archivados ie1_tables, ie1_media, validate_ie1_media, patch_exefs, patch_code y patch_cro; activos.toml por objetivo. Ficheros bloqueados v20 intactos.
- 2026-09-16 · Toolkit F1.5: tests heredados trasladados de tools/test_*.py a tools/tests/unidad; shims regenerados y comprobados por AST (29); tests requiere_rom de los gates 3-5 (capa v67, candidata v67 por build_ui_revision y nucleo/construir/candidata, clon limpio); CI toolkit.yml (Windows y Ubuntu) con guardias de bloqueados y de git ls-files; documentación actualizada (tools/README, ARQUITECTURA, CLAUDE, AGENTS). Recuento de tests en #46. Fase 1 cerrada. Ficheros bloqueados v20 intactos.
- 2026-09-16 · Toolkit F1.5 (arreglo de CI): la primera ejecución de `toolkit.yml` falló en los dos SO por `ModuleNotFoundError: cv2` en `test_scaled_image_is_centered_inside_its_original_box` (`nucleo/graficos/pintado.py:70` importa cv2 para cualquier operación con `image`); en local pasaba porque OpenCV ya estaba en el entorno. `opencv-python-headless` pasa al extra `dev` de `tools/pyproject.toml` (#58). Los 5 saltos de más de Ubuntu son los hashes de `unidad/test_pintado.py`, capturados con Arial (fuente no redistribuible): el salto es legítimo y la cobertura de esas rutas (condensado, rotación, texto que no cabe, padding negativo) se recupera en Linux con tests independientes de la fuente (#59). #46 y #40 siguen abiertos hasta ver la CI verde en Windows y Ubuntu.
- 2026-09-16 · Toolkit F1.5 (alcance de la guardia): el filtro `paths` de `toolkit.yml` (tools/**, .gitattributes, AGENTS.md, CLAUDE.md) anulaba en la práctica la Norma 2: en GitHub Actions `paths` filtra el workflow entero, no un job, así que un commit que añadiera una ROM o datos extraídos en `translation/`, `docs/` o una carpeta nueva no disparaba el workflow y `guardia git` -que es de alcance de repositorio (`git ls-files`)- no llegaba a ejecutarse. Nuevo workflow `.github/workflows/guardia.yml` sin filtro de rutas, en todos los push y PR: ejecuta `guardia todo` (bloqueados + git) en ubuntu-latest sin instalar nada (solo biblioteca estándar, `PYTHONPATH=tools/src`). `toolkit.yml` conserva sus pasos de guardia (no se quita ninguna comprobación) y documenta el porqué del filtro. Actualizados tools/README, AGENTS y CLAUDE.

- 2026-09-16 · Toolkit F2.1: capa de servicio `ie123kit.servicio` (API única `ServicioToolkit` con Resultado/Incidencia, progreso y cancelación), tipos y vocabularios cerrados en `nucleo/tipos.py`, modelo de juego y capacidades en `nucleo/juego.py`, utilidades comunes en `nucleo/util.py`, configuración de proyecto `ie123.toml` con `Workspace`, inventario perezoso de activos con caché `registro.json` dentro de `work/`, esquemas JSON y suite de contrato (`tools/tests/contrato`) más tests de capas y de descubrimiento unittest. Ficheros bloqueados v20 intactos.
- 2026-09-16 · Toolkit F2.2 (#48): primitivas que hasta ahora se copiaban y pegaban en las capas de `work/` consolidadas en `ie123kit.nucleo` (contenedor FA y rewrap, plan de texturas ARCV→CTPK e imagen, QnaLayout, Cro/CroPatcher, tablas fijas y rangos, `packnum.rebuild` y EventPack, localización de herramientas externas), construcción de candidatas generalizada a las cuatro CRO y con aportaciones por objetivo, más `nucleo/construir/{capas,instalar,rom,parche}.py`. La fachada `ServicioToolkit` deja de devolver NOT_SUPPORTED en `construir`, `verificar`, `instalar` y `parche` (el bloqueo tipográfico v20 se ejecuta siempre, nunca es opcional) y se adelanta la CLI mínima `python -m ie123kit.cli` / `ie123` con `construir`, `parche` y `doctor`, porque el gate de la subfase exige poder ejecutarlos literalmente. Queda para F2.3 el traslado de las capas de `work/` a cada juego (aportaciones por objetivo) y para F2.4 el resto de verbos de la CLI, los alias en inglés y su tabla de equivalencias. Ficheros bloqueados v20 intactos.
- 2026-09-16 · Toolkit F2.2 (cierre, #48): repaso de la subfase antes de commitear. La regla «la última capa gana» se aplica ahora siempre al grano más fino y ninguna aportación se descarta en silencio: fichero a fichero en el archive, nombre a nombre en las CRO (aditivas) e **id a id** en los eventos —antes, si dos capas preparaban `.ssd` del mismo paquete, se guardaba solo la ÚLTIMA carpeta y los eventos de las anteriores se perdían sin error—; cada anulación queda anotada en `overridden_by_later_overlay`. Una CRO **declarada** (`cro=` o una aportación) que no exista deja de saltarse en silencio y da `CRO_DECLARADA_AUSENTE`. **Cambio de comportamiento a tener en cuenta:** una capa que no aporte nada reconocible (ni ficheros de `archive/`, ni `extra/`, ni `.ssd`, ni `cro/*.cro`) ya no se construye «igualmente»: el servicio la rechaza pidiendo ejecutar su `apply.py`; y el servicio arrastra todas las `*.cro` que encuentre junto a la base, no solo `ina_main1.cro`, así que el contenido de `romfs/cro` de una candidata puede cambiar aunque no se mueva el sha del archive. Suite completa en verde (984 passed, 1 skipped) incluida `tools/tests/compat` (golden de probe_ie1_v66/v67). Ficheros bloqueados v20 intactos.
- 2026-09-16 · Toolkit F2.3 (servicio, CLI y work/, #49): `juego_principal` pasa a ser el **quinto ámbito de primera clase** de `work/` (junto a `shared`, `ie1`, `ie2` e `ie3`). Cambios de comportamiento observables: (1) el inventario ya no es solo el `archive.fa` — `<objetivo> activos` funde el escaneo del archive con lo que cada juego aporta fuera de él (`cro/*.cro`, los `.SAD` de voces y `banner.bnr`/`icon.icn` del ExeFS), deduplicando por id, y además escanea los prefijos de `[romfs].solo_lectura`, así que las fuentes del bloqueo v20 aparecen listadas con `editable: false` en vez de no aparecer; (2) la CLI gana `proyecto init`, `proyecto migrar-juego-principal`, `objetivos`, `work limpiar [--borrar]` y `<objetivo> activos`, con `--json`/`--proyecto` válidos antes y después del verbo y los primeros alias en inglés; (3) `ie123 proyecto init` crea `work/juego_principal/{capas,qa,exportaciones}` y `translation/juego_principal/` y anota en `ie123.local.toml` solo RUTAS de ROM; (4) `migrar-juego-principal` escribe `work/juego_principal/historico.json` con las capas viejas de `work/ie1/capas` que tocan el menú **sin moverlas** (mover responde NOT_SUPPORTED a propósito: sus rutas relativas e `importlib` dependen de su sitio); (5) `work limpiar` recorre los cinco ámbitos y una lista explícita de PROTEGIDOS filtra la salida entera, así que nunca puede proponer `shared/base_3ds`, una carpeta `fuentes`, un congelado del bloqueo v20 ni una candidata con `.conservar`. Una aportación con `entradas_fa` que sea un árbol ya volcado en disco se colapsa a `extra=<raíz>` en vez de rechazarse; sin raíz común se sigue reportando. Ficheros bloqueados v20 intactos.

## Actualización 2026-09-09: v23, pachangas y cadena de partidos

La candidata actual es `work/shared/candidatas/probe_ie1_v23/archive.fa` y ya sustituye a la v22
en la instalación activa de Azahar. Esta tanda añade los diálogos de pachangas
y de la cadena de partidos del paquete `mch.pkb` (eventos `9420xxxx`), conserva
los 143 diálogos traducidos del partido de la Royal (`94001500`) y localiza los
158 nombres de equipo de `team.pkb`, los 20 títulos de `teamtitle.dat` y las 32
categorías de `clubinfo.dat` que aparecen en el selector de pachangas.

La auditoría estática confirma 1.422 registros visibles de partido/pachanga sin
japonés, instrucciones SSD intactas y ningún desbordamiento en los campos fijos
de nombres. Las fuentes y la caja aprobadas de v20 no se han modificado. El hash
de la candidata y de la copia instalada es
`bf1e194564170d86cffcf3acfa70409420584ca048b699253611011e35614393`.
La prueba jugable sigue pendiente de reiniciar Azahar y repetir las pachangas,
la cadena y el partido de la Royal desde un estado creado con esta candidata.
Las v21 y v22 se eliminaron tras verificar la sustitución para no acumular builds en
`work/`.

## Actualización 2026-09-08: v21 y partido de la Royal

La candidata histórica `work/shared/candidatas/probe_ie1_v21/archive.fa` estuvo instalada en Azahar. Se
localizó el origen de los diálogos de partido en `mch.pkb` y se tradujeron los
143 registros visibles del evento `94001500`, incluida la línea de la captura.
La comprobación estática deja cero japonés visible en ese evento y mantiene los
otros eventos, el bytecode y la tipografía aprobada. La prueba jugable sigue
pendiente; el hash instalado es `45377d4e6a4987301d8770e454ce883124806ffc9b8674d8385762a22ff4f566`.

La build intermedia v20 se eliminó después de comprobar la copia instalada para
no acumular binarios en `work/`; las v21 y v22 también se retiraron al instalar v23.

## Retoma 2026-09-05: diagnóstico y prueba pendiente

- Protocolo obligatorio del usuario: [PROTOCOLO_QA_IE1.md](PROTOCOLO_QA_IE1.md).
- CIA convertida localmente a NCSD conservando programa y manual, verificados
  contra SHA-256 del TMD y contra las particiones de salida. Script temporal
  eliminado por petición del usuario. La nueva base NO equivale al cartucho usado
  para los xdelta antiguos.
- Descubierto el tamaño por registro de texto inline SSD, omitido por el motor
  anterior. Ver [SSD_REGISTROS_IE1.md](SSD_REGISTROS_IE1.md). Lectura y roundtrip
  exactos de 1.240 SSD originales; cinco pruebas sintéticas de regresión pasan.
- Corregido el falso éxito del validador cuando faltan PKB/PKH o la selección está
  vacía; tres pruebas de regresión pasan.
- Preparada prueba local de 92010100, 92010200 y 92010250. Verificado que cambia
  solo esos eventos y tres fuentes; 16 textos insertados, uno rechazado por longitud.
  Instalado como mod local de Azahar; el usuario confirmó arranque y diálogo
  español dentro del club con capturas. QA-001 abierto: cortes dentro de palabras
  y fragmento al cambiar de página. Evidencias locales en `work/ie1/qa/qa_dialogue_001/`.
  Corregido el reflujo por caracteres en el generador; nueva candidata por avances
  de FONT12 instalada tras cerrar Azahar: `work/shared/candidatas/probe_ie1_v2/archive.fa`, SHA-256
  `a2cb278c36866fedfad569bed436986de59596f1107aab7d3bc433f7050a1c4c`.
  Cuatro pruebas de reflujo pasan; verificados 16 registros insertados, anchos
  calculados, instrucciones y demás registros intactos. Pendiente repetir toda
  esa conversación en Azahar, incluidos los cambios de página y el cierre.
- Original convertido probado en Azahar 2126.0: llega al recopilatorio; al entrar
  en IE1 se observó pantalla negra prolongada y 0 FPS de aplicación, sin excepción
  CPU en el log. Se detuvo esa prueba. En la repetición con región japonesa y
  control del usuario se observó al personaje jugable frente al club. La
  configuración anterior era europea; no atribuir una causa única sin aislarla.
- `tools/jugar.ps1` usa la instalación de Program Files (o parámetro `-Azahar`),
  conserva el log previo y evita mezclar sesiones simultáneas.

Las conclusiones antiguas siguientes son históricas; no sustituyen las pruebas
actuales ni demuestran estabilidad de la nueva reinserción.

Leyenda: ⬜ pendiente · 🟡 en curso · ✅ hecho

---

## ⏸️ ESTADO FINAL (proyecto pausado, build v27) — 2026-06

**Build v27** = la mejor lograda: **arranca, crea partida, intro + diálogo de historia en
español**. Parche [`patch/inazuma123-es-v27.xdelta`](../patch/). Cómo trabajar:
[`DESARROLLO.md`](DESARROLLO.md).

**Motor nuevo de reinserción** (`tools/ssd_reinsert.py`): el texto SSD se referencia por
**índice** (no por offset) → el bytecode queda intacto, el diálogo de **gameplay crece libre**
(sin truncar), y los eventos de **sistema/intro** van INPLACE a mismo tamaño con **re-paginación**
(reparte el ES en las páginas `\f` del JP) + **fallback global** (reusa traducción del mismo
japonés en otro evento, +~22 % cobertura). Validador `validate.py` consciente del crecimiento.

**Muros DEFINITIVOS** (no reintentar — [`FURIGANA_LECCIONES.md`](FURIGANA_LECCIONES.md)):
- ❌ **Parchear el código es inviable**: la zona de caves del CRO (`0x50E14`) es de
  **relocalización** → el loader la pisa → crash `0xAD9E1C`. Ni ruby (`0xABFCC0`) ni `code.bin`.
- ❌ **Sistema/intro no puede crecer** (ruby cuelga al avanzar, ❌#9) → mismo tamaño → truncado.
  La apertura/crear-partida (`92010100..92010249`) exige eventos intactos (❌#1).
- 📉 **Techo de datos: ~48 %** del diálogo tiene traducción; el resto no existe en los datos.

**Qué queda** para subir cobertura: traducir a mano lo `pendiente`/`revisar` de `dialogo.csv`,
objetos/técnicas (#1/#2), juego 3. El motor ya aguanta; el límite es de datos.

---

## Fase 0 — Infraestructura
- ✅ Diagnóstico de las ROMs (formato, cifrado, regiones)
- ✅ Estructura del repositorio + git init
- ✅ `.gitignore`, `README.md`, `LEGAL.md`, `CLAUDE.md` (normas de trabajo)
- ✅ Repo en GitHub (privado) + push: `luishidalgoa/inazuma-eleven-123-spanish`
- ✅ Workflow de Issues: #1 objetos, #2 técnicas, #3 diálogo, #4 juego 2, #5 juego 3
  (Project board pendiente: el token necesita scope `project`)
- 🟡 Herramientas (3dstool ✅, extractores propios ✅; xdelta3 pendiente p/ release)

## Fase 1 — Extracción y mapeo
- ✅ Extraer RomFS/ExeFS de la ROM 3DS (1·2·3) → `work/shared/base_3ds/romfs`, `work/shared/base_3ds/exefs`
- ✅ Mapa de primer nivel del RomFS 3DS
- ✅ **`archive.fa` decodificado** (magic `B123` = variante ARC0/XFSA) y
  **extractor propio** `tools/fa_unpack.py` (15.547 archivos, rutas correctas)
- ✅ Verificado que las herramientas de la comunidad NO soportan `B123` (plan B)
- ✅ Localizado el texto: `message/jp/GameString.bin` (UTF-8), `import/*.itx`
  (parámetros), `field_message*.arc` (diálogos, en contenedores ARCV)
- ✅ Primer vistazo a texto real del juego 1 (cadenas de sistema en UTF-8)
- ✅ **Diálogo localizado**: `inazuma1/data_iz/script/eve.pkb` (4,2 MB, historia)
  + `mch.pkb` (combates), paquete "PackNum". Texto en bytecode Shift-JIS (issue #3)
- 🟡 Parser del script de evento (bytecode) para volcar diálogo a CSV/JSON + alinear
  con el español oficial del NDS `evet.pkb` (misma estructura)
- ⬜ Extraer sistema de archivos completo del IE1 / IE2 (NDS, ES) con `nds_unpack.py`
- ⬜ **Mapa de textos** del juego 1 (NDS ES) y del 3DS, y **emparejado (match)**

### Hallazgos de la extracción 3DS (RomFS)
- Estructura por juego: `inazuma1/`, `inazuma2/`, `inazuma3/`, `inazuma3_ogre/`
  → contienen sobre todo **sonido/voces** (`.SAD/.SWD/.SED/.SMD`).
- `sound/` → audio global.
- **`archive.fa` (1,2 GB, magic `B123H`)** → contenedor Level-5 con TOC propia.
  Aquí viven texto, scripts, tablas y gráficos de los 3 juegos. **Es el objetivo
  principal a desempaquetar.**
- `cro/`, `.crr` → módulos de código 3DS (CRO). `icon/`, `import/` auxiliares.
- Herramienta candidata para `.fa`: **Inazuma-Eleven-Toolbox v0.6.1**
  (SwareJonge) — tiene binario en releases.

## Fase 2 — Glosario y terminología
- ✅ Extraído el filesystem de IE1/IE2 NDS (ES) → `work/ie1/fuentes/nds_es`, `work/ie2_es`
- ✅ Localizado el texto español oficial en carpetas `data_iz/logic/sp/` y
  `data_iz/script/sp/`: `command.STR` (técnicas), `item.STR` (objetos),
  `unitbase.STR/.dat` (jugadores), `evet.pkb`/`mcht.pkb` (eventos), `team.pkb`
- ✅ Confirmados términos oficiales (Regate, Bloqueo, Vaselina, Testarazo…) con
  `tools/nds_str_dump.py`
- ✅ Mapear la **tabla de codificación** NDS (parcial: á é í ó ú ñ ü ¿ ¡ Í)
- ✅ **Glosario JP↔ES del juego 1** generado (`tools/build_glossary.py`):
  ~1174 jugadores, 20 títulos de equipo, 133 menús = **~1327 parejas exactas**
  (alineadas por índice de registro). Verificado: 円堂守→Mark Evans, 鬼道有人→Jude Sharp
- 🟡 Objetos y técnicas/hissatsu: el `item.dat`/`command.STR` no casan 1:1
  (estructura/recuento distintos) → pendiente parsear su índice real

## Juego 2
- ✅ Extraído + alineado con NDS IE2 (74% con ES oficial, `translation/ie2/dialogo.csv`)
- ✅ **Reinsertado en la build** (multi-juego): 2610 eventos / 24843 líneas ES

## UI / menús (AMBOS juegos)
- ✅ **Re-insertor de UI** (`tools/ui_insert.py`): inserta en la ROM (mismo tamaño,
  acentos vía griego→SJIS): menús (`games.STR`), jugadores (`unitbase.dat`),
  equipos (`teamtitle.dat`). `build_glossary` multi-juego.
  - Juego 1: menús 133, jugadores 1170, equipos 20
  - Juego 2: menús 209, jugadores 2032, equipos 20  (verificado: Axel Blaze, etc.)
- ⬜ Objetos/técnicas (#1/#2) · GameString.bin (textos de sistema)

## Builds / parches
- v1–v5 (ver historial) · v6 (4.95M): j1+j2 diálogo + UI completa
- Compresor LZ10 (lazy + cap 256) — recuperada la cobertura del juego 1

### Investigación "pantalla negra / japonés" (v7–v13) — 2026-06
Tras crear partida la build se quedaba en negro o el diálogo seguía en japonés.
Aislado por bisección:
- **Causa del cuelgue (v1–v6):** traducir cadenas **estructurales** del script
  (etiquetas, comentarios `(`, debug en inglés) corrompía el bytecode →
  `looks_like_dialogue()` las excluye. **v10 ARRANCA** y se juega.
- **Furigana:** v10 **salta** los diálogos con furigana (`%NF`) → solo ~30% del
  texto sale en español (el 70% lleva furigana). Quitar los marcadores (v12) o las
  lecturas (v11) **descuadra el consumo de lecturas y cuelga**.
- **v13 (candidata, `FURIGANA_KEEP_MARKERS`):** traduce el furigana pero
  **reinyecta los mismos marcadores** (conteo invariante) → las lecturas se siguen
  consumiendo. Invariantes verificadas offline (tamaño, nº de chunks y de
  marcadores) en muestra de 240 eventos: **OK**. Cobertura real game1: **4923
  líneas de furigana aplicadas (44,8% de las disponibles)** + 1741 sin furigana =
  6664 (vs v10 que aplicaba 0 furigana). El total es parejo a v10 porque al
  competir por el presupuesto de bytes se revierten más líneas, pero el **diálogo
  de historia visible** sube mucho. **Riesgo restante: cosmético** (ruby kana
  flotante), no de cuelgue. **Falta prueba visual.** Ver FORMATOS.md §"SSD".
- **Recomendación actual:** **v10 = estable** (arranca seguro, ~30% diálogo).
  **v13 = a probar** (≈90% diálogo si el motor tolera el ruby sobrante).
- ⬜ Verificación de arranque/visual de v13 en emulador (**usuario**)

## Fase 3 — Traducción
- ✅ Contenedor **PackNum resuelto** (`tools/pkb_unpack.py`): 1293 eventos
- ✅ **Entradas comprimidas con LZ10** → diálogo extraído **LIMPIO** (no eran
  códigos de control). Etapa 3 resuelta.
- ✅ **Alineado por `event_id`** JP(3DS)↔ES(NDS): 1289 ids comunes; **133 eventos
  con nº de líneas idéntico → ES oficial aplicado** (934 líneas), `tools/align_events.py`
- ✅ **Alineado fino (Needleman-Wunsch)** con señal de longitud + formato (%s/%d/\n):
  `translation/ie1/dialogo.csv` (29985 líneas). **Cobertura con ES: 66,2%**
  (oficial 3,1% + revisar 56,4% + auto-dup 6,7%); pendiente 33,8%
  (`tools/align_events.py`, `tools/build_translation.py`)
- 🟡 Traducir a mano lo `pendiente` (33,8%) y revisar lo `revisar`
- ⬜ Juego 2 · ⬜ Juego 3

## Fase 4 — Fuente y gráficos
- ✅ **Fuente BCFNT ampliada** (`tools/bcfnt.py`, `tools/font_patch.py`): añadidos
  ñÑáéíóúüÁÉÍÓÚ¡¿ reusando glifos griegos (swizzle morton + LA4 validados, CWDH
  copiado). Mapeo byte→glifo: ES→griego→SJIS (0x839F+). Parcheadas FONT12T/12/8.
- ⬜ Gráficos con texto incrustado

## Fase 5 — Build y release
- ✅ Re-encoder real del ES (`tools/reinsert.py`): 477 eventos, 6893 líneas ES
  (sin acentos; saltados 531 por tamaño LZ10)
- ✅ Reinsertar + reconstruir la ROM (parche in-place de archive.fa, `tools/build_3ds.py`)
- ✅ **Parche v1** `patch/inazuma123-es.xdelta` (~416 KB, sin acentos, 477 eventos)
- ✅ **LZ10 con lazy matching** → más eventos caben
- ✅ **Parche v2** `patch/inazuma123-es-v2.xdelta` (~1,14 MB): con acentos, 821 eventos
- ✅ **Ajuste parcial por evento** (revierte líneas que no caben en vez de saltar
  el evento) → **Parche v3** `patch/inazuma123-es-v3.xdelta` (~1,53 MB):
  **992/1008 eventos (≈98% de los traducibles), 12343 líneas ES**, roundtrip OK
- ⬜ Pruebas en emulador (Lime3DS / Azahar) — **lo verifica el usuario**
- 🟡 Traducir manualmente el 33,8% pendiente (líneas JP SIN equivalente oficial NDS)
- ⬜ Primera release pública

## Notas de las ROMs (referencia)
| ROM | Plataforma | Región | Código | Tamaño |
|---|---|---|---|---|
| Inazuma Eleven 1·2·3 | 3DS (NCSD, descifrado) | JP | CTR-P-AETJ | 2 GB |
| Inazuma Eleven 1 | NDS | EU (ES) | YEES | 256 MB |
| Inazuma Eleven 2 (Tormenta de Fuego) | NDS | EU (ES) | BEES | 256 MB |
