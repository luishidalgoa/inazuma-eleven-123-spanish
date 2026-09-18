---
name: volcado-rom-nds
description: Checklist y lecciones para volcar y verificar la localización de Inazuma Eleven 1·2·3 (3DS) desde la ROM NDS española. Usar al traducir o auditar diálogos, nombres, rótulos, texturas de UI, iconos, teclado, eventos, doblaje, cinemáticas o subtítulos, o al preparar una candidata vN.
---

# Volcado y análisis desde la ROM NDS → 3DS

Referencia única: la ROM NDS española extraída en `work/ie1/fuentes/nds_es` (`data_iz/…`, `bin/strings.txt`).
Original japonés 3DS: `work/ie1/capas/v33/base/orig/…`. Nada extraído se sube (Norma 2). Leer antes
`CLAUDE.md`, `AGENTS.md` y `docs/FURIGANA_LECCIONES.md`.

## 0. Antes de tocar nada

- Issue de GitHub para la tanda (Norma 1). Comentar al terminar; no cerrar sin prueba en juego.
- Candidata nueva = capa nueva `work/vN/<linea>/` (apply.py + validate.py + extra/ o events/ + previews/).
  Base = candidata anterior instalada, nunca una más vieja: cada capa acumula sobre la previa.
- Tipografía v20 bloqueada (`tools/dialogue_lock.py`): no cambiar caja, fuentes, codificación ni saltos.
- No acumular builds: borrar las candidatas viejas que el usuario diga.

## 1. Inventario: qué hay que volcar

| Qué | 3DS | NDS (fuente oficial) | Clave de emparejado |
|---|---|---|---|
| Diálogo de eventos | `script/eve.pkb` (SSD) | `script/sp/evet.pkb` | **ID de instrucción** alineado por patrón de saltos + anclas ASCII |
| Nombre del hablante | `unitbase.dat +16` | `unitbase.dat +32` (nombre corto) | índice de registro |
| Nombre completo | `unitbase.dat +0/+32` | — | **no tocar** (issue #16) |
| Rótulo de lugar del minimapa | `eve.pkb` op `0x4037` arg 3 | `bin/strings.txt` | texto japonés original |
| Objetivos | `eve.pkb` op `0x402f` arg 2/3 | última línea imperativa del evento NDS | evento |
| Campos de partido | `fieldinf.dat +144` (20 B) | `fieldinf.dat` | índice |
| Títulos / Contactos | `rpgtitle.STR`, `JinmyakuData.dat` | equivalentes NDS | índice |
| Literales del ejecutable | `cro/ina_main1.cro` | `bin/` | referencia verificada en código |
| Equipos | texturas | `translation/shared/glossary/equipos.csv` | — |
| Teclado | `fcode0/1/2.txt` + `name_b` font_hira01/kana01 | — | rejilla de 20×20 px |
| Frases con voz | `eve.pkb`, primera frase tras la llamada `NN_N.SAD` | `evet.pkb`, idem | `work/ie1/capas/v51/voces/auditoria.py` |
| Sprites de DS heredados | `pic3d/*.SPD/SPL/pac_` | `pic3d/sp/*` | nombre de paquete |
| Texturas de UI | `.arc` ARCV (SSZL) con CTPK | sprites SFP `pic3d/sp/*.SPL/SPD`, `pic2d/**/*.pac_` | celda del atlas |

## 2. Diálogos: método que funciona

- **Nunca emparejar por orden de líneas** (`tools/ds_official.py` lo hacía: 621 eventos desplazados).
  Usar `tools/audit_dialogo_ids.py`: IDs de instrucción, alineando la secuencia de *saltos* entre IDs con
  difflib y validando con anclas ASCII (12.617 iguales / 72 distintas).
- Clasificar: igual / editado (parecido ≥ 0,55, se respeta) / desplazado / distinto / protegido.
  Protegidos: crear partida `92010100..92010509` y `81000040`.
- Límite de registro de texto 247 B; `%s`/`%d` deben coincidir con el japonés; sin furigana.
- Apóstrofo y comillas **no tienen glifo** en NFTR: «O'Reilly» → «OReilly». Lo que no quepa va a
  `no_caben.json` para condensar a mano, no se trunca.
- **Los registros de rótulo/objetivo comparten eventos con el diálogo**: una tanda de diálogo puede
  meter frases largas en rótulos (`0x4037`). Excluir esos opcodes o medirlos después (sección 4).

## 3. Nombres

- Hablante = `unitbase.dat +16`, máx. 7 caracteres de ancho completo + NUL. El nombre NDS está en
  `+32`, casi nunca es la primera palabra del completo (Max, Timmy, King…). Recortar a 7 si el usuario lo pide.

## 4. Medir en píxeles, no en caracteres

- Avances de `font/FONT12.NFTR` con `tools/nftr_metrics.read_metrics` (claves Shift-JIS).
- Hueco disponible = ancho del japonés original más ancho del mismo tipo de texto
  (rótulo del minimapa: 117 px). Todo lo que lo supere se desborda en juego.
- Script de referencia: `work/ie1/capas/v39/estado/medir_rotulos.py`. Validar la candidata con él.

- **Nombres de equipo, supertécnicas y objetos**: se vuelcan por ID desde la NDS (`team.pkb`,
  `command.STR`, `item.dat`), pero después hay que **medir cada nombre contra el hueco de su pantalla**.
  El cuadro de equipo pinta con paso fijo: máximo 11 caracteres (el japonés más largo).
- **Objetos**: campo de 18 B + NUL (9 letras de ancho completo). Latín de 1 byte **no sirve**: el menú
  parte la fila tras 10 caracteres aunque las letras sean estrechas (prueba v47, issue #39).
- **Títulos de equipo** (`rpgtitle.STR`): hueco de 32 B pero búfer de 18 B: máximo 9 caracteres.

## 4b. Literales del CRO

- Hueco = del inicio al siguiente dato **y** sin referencias dentro (`work/ie1/capas/v33/cro/analysis/crorefs.py`).
- Solo ancho completo (las métricas ASCII de las fuentes solo tienen el espacio).
- **No superar el número de caracteres del japonés** si a continuación va un número u otro texto: el
  juego lo pinta en posición fija («Jug.» se montaba con «10»).
- **El juego copia el literal a un búfer del tamaño del japonés**: más bytes que el original salen como
  basura («Niv. Equ?7&», «Ran»). Límite real = longitud en bytes del japonés.
- **Comprobar el glifo en la fuente que pinta esa pantalla** (a menudo `FONT12.NFTR`, no la BCFNT): los
  números romanos existen en la BCFNT pero no en la NFTR y salían en blanco.
- **Nunca dejar un literal vacío**: pinta basura («*&»). Usar un espacio de ancho completo.

## 5. Texturas de UI: checklist por pantalla

0. Colocar cada pieza en su **rectángulo QNA** (`tools/qna_regions.py`), no en la celda de 16/32/64 px,
   con la alineación y el ancho del japonés; auditar con `work/ie1/capas/v42/auditoria/celdas.py`.
1. Volcar **todas** las texturas del `.arc` (no solo las ya pintadas) de la candidata actual y del
   original japonés; hoja ampliada con rejilla de 16 px (`work/ie1/capas/v38/estado/`).
2. Por cada texto: ¿japonés visible, resto de trazo, artefacto, término no oficial, texto cambiado?
   El informe `work/ie1/capas/v33/tex_residual/report.json` está desfasado: comprobar sobre la candidata.
3. **Buscar primero la pieza NDS** (`work/ie1/capas/v37/graficos_nds/piezas_nds.py`):
   - posiciones DL/MD/DF/PR: `menu_member/NID_I00`
   - afinidad aire/bosque/fuego/montaña: `menu_special_comand/HWD_I03` (sustituye 風林火山)
   - tipos de técnica: `HWD_I02`; «PT»: `HWD_N01`
   - rótulos cian Tiro…Valor/EXP.: `pic2d/menu/sp/msup_bg02.pac_` (mapa de 32 teselas)
   - capitán Pasión/Calma/Seguir y «Táctica»: `captainselect/CSDN_B01`, `CSDN_W02`
   - `.SPF_` son layouts, no imágenes; pac de equipos/jugadores no son UI.
4. Si no hay pieza NDS: pintar en español con el estilo de la textura (`translate_ui_textures.paint`,
   `arialbd`, `crisp` para alfa de 1 bit) y comprobar que no se sale de la celda.
5. Comparar con el **original japonés** cuando algo parezca raro: así se vio que `ts001lp/rp` eran
   1P/2P (no «Raimon») y que las barras estaban cortadas.
6. Grep global de nombres de textura parecidos (`top_plt`, `attribute`…) para no dejar copias en otras pantallas.

### Trampas de texturas (ya pasaron)

- `paint()` **rellena su caja con `background`**: si hay fondo debajo, pintar en una capa transparente y
  componer, o pasar el color real del fondo.
- Color dominante: **ignorar píxeles con alfa 0** (el transparente es `(255,32,230,0)`).
- No mover coordenadas de atlas ni tamaños; `metadata(CTPK)` idéntica y códec ida y vuelta.
- Al recortar piezas NDS, dejar fuera los bordes del botón origen (aparecen barras laterales).
- Extraer glifos de otra textura: limitar la región y quitar píxeles aislados.
- Heredoc de bash convierte `\0`/`\x01` en bytes reales dentro de `.py`: escribir con la herramienta Write.

## 6. Teclado de nombre

- `fcodeN.txt`: 26 celdas × 6 filas + CRLF; cada letra ocupa 2 celdas, hueco tras la 5.ª, `AAAA` cambia
  modo, `DDDD` borra.
- La **rejilla de selección es de 20×20 px** (fila k en y = 20k, controles en x 200–224). Pintar filas de
  16 px descuadra el cursor y hace pulsar la fila vecina (issue #38). La flecha de borrar debe estar en
  mayúsculas y minúsculas.

## 7. Doblaje, cinemáticas y subtítulos

Docs: `docs/IE1_AUDIO_CINEMATICAS_V34.md`, `docs/IE1_AUDIO_CINEMATICAS_V35.md`.
Herramientas: `tools/ie1_media.py`, `tools/mods_to_moflex.py`, `tools/build_ie1_movies.py`,
`tools/validate_ie1_media.py`, `tools/audit_ie1_voiced_text.py`.

### Inventario

| Qué | NDS ES (`data_iz/`) | 3DS | Instalación |
|---|---|---|---|
| Voces / música de escena | `sound/sp/*.SAD` (72) | 70 SADL con el mismo nombre | **LayeredFS** en `romfs/` del mod (fuera de `archive.fa`) |
| Cinemáticas | `movie/*.mods`, variante ES `movie/sp/am0102.mods` (21) | `movie/*.moflex` (21) | dentro de `archive.fa` |
| Subtítulos de cinemática | `movie/txt/sp/*.dat` (intervalos de fotogramas) | no existen: se incrustan en el vídeo | — |
| Texto de eventos con voz | `evet.pkb` | `eve.pkb` | auditar con `audit_ie1_voiced_text.py` |

- `J18.SAD`/`J19.SAD` solo existen en DS: no se instalan.
- SADL: copiar el archivo europeo **entero, sin recodificar**; la frecuencia va en su cabecera
  (ES 32728 Hz, JP 16364 Hz). Comprobar byte a byte y descodificar con vgmstream.
- Cada build nueva debe **conservar los 70 SAD** en la carpeta del mod (contar tras instalar).

### Vídeo

- `mods_to_moflex.py`: YCgCo DS → YCbCr y giro 256×192 → 240×320.
- Descriptor de sincronía **layout 0x16** (Simple2D, ImageRotation 1). Con 0x06 el vídeo sale girado.
- Usar **mobipeg x86**; la x64 falla con vídeo complejo en Windows.
- Descodificar cada MOFLEX completo después de generarlo.

### Subtítulos sin retraso (checklist)

1. **Unidad de los `.dat`: ticks de 30 Hz (comprobado)**. `op00` tiene 1.763 fotogramas a 20 fps y su último
   subtítulo acaba en 2.675 = 1.763 × 30/20. `mods_to_moflex.py` usa `tick = fotograma × 30 / fps`
   (`SUBTITLE_TICK_RATE`). Tratar los ticks como fotogramas retrasa los subtítulos ×1,5 y corta los finales.
2. **fps**: el MOFLEX debe declarar el mismo `r_frame_rate` que el `.mods` de origen. Nunca forzar
   24 fps sobre un origen distinto: el vídeo, y con él el subtítulo, deriva respecto a la voz.
3. **No perder ni duplicar fotogramas** en la conversión: el número de fotogramas MOFLEX debe ser igual
   al del `.mods` (p. ej. am0102 = 361).
4. **Voz frente a vídeo**: la voz es un SAD que el juego lanza aparte. Comparar la duración del SAD
   con la del vídeo, y el primer subtítulo con el primer tramo con voz del SAD (energía > umbral).
   Una diferencia sistemática indica unidad o fps mal interpretados, no un fallo de texto.
5. Generar una **tira de control** por cinemática (fotograma de inicio y fin de cada subtítulo con su
   marca de tiempo) y revisarla antes de construir.
6. Prueba en juego: opening, `am0102` y al menos una narrativa. Comprobar orientación horizontal,
   subtítulos españoles, sincronía con la voz y ausencia de cortes.

## 8. Construir, verificar, instalar

```
python work/vN/<linea>/apply.py
python work/vN/<linea>/validate.py          # solo cambian las texturas/registros declarados
python tools/build_ui_revision.py --base work/probe_ie1_v(N-1)/archive.fa --ui work/vN/<linea> \
    --extra work/vN/<linea>/extra --cro work/probe_ie1_v(N-1)/romfs/cro/ina_main1.cro \
    --output work/probe_ie1_vN/archive.fa
python tools/verify_candidate.py --base work/probe_ie1_v(N-1) --candidate work/probe_ie1_vN \
    --layer work/vN/<linea>/extra [--events work/vN/<linea>/events]
```

- PASS esperado: reemplazos = los declarados, 22 fuentes idénticas, CRO idéntico, bloqueo PASS.
- Instalar solo con Azahar cerrado: copiar `archive.fa` a
  `%APPDATA%/Azahar/load/mods/00040000000BB800/romfs`; comprobar que siguen los 70 `.SAD` de audio.
- Revisar **visualmente cada preview** antes de construir; corregir y repetir.
- Documentar en `docs/IE1_VN_TANDA.md`: tabla antes/ahora/origen, lo que «se queda» con motivo, sha,
  comandos. Comentar el issue.

## 9. Cierre

- `runtime_verified=false` hasta que el usuario pruebe (`docs/PROTOCOLO_QA_IE1.md`).
- Dar al usuario una lista corta de qué probar y dónde.
- Fallo nuevo o enfoque que no funciona → añadirlo a `docs/FURIGANA_LECCIONES.md` y a esta skill.

## 10. Lo que se quedó sin traducir en IE1 y hay que revisar de entrada en IE2/IE3

Lista de comprobación nacida de la prueba en juego de IE1 (v36–v56). Cada punto costó una o varias
candidatas; en el siguiente juego se revisa **antes** de la primera prueba.

### Texto que no está donde se busca primero
- **Diálogos de pachanga (`script/mch.pkb`)**: además de `eve.pkb`. Tandas antiguas los dejaron en latín de
  1 byte (letras juntas y montadas). Convertir solo instrucción `0x301d` argumento 1 a ancho completo
  (`work/ie1/capas/v55/pachangas`). Reempaquetar `mch.pk*` aparte: `build_ui_revision` solo reempaqueta `eve.pk*`.
- **Eventos protegidos** (crear partida, tutorial): se excluyen del volcado masivo y conservan texto viejo.
  Si llevan **voz**, la frase debe ser la oficial NDS (auditoría `work/ie1/capas/v51/voces/auditoria.py`).
- **Reparto en cajas**: 3 líneas × 20 caracteres; lo que sobra abre caja nueva. Repartir por frases con el
  salto de caja explícito (`por_frases` en `work/ie1/capas/v51/voces/apply.py`), sin tocar el ajuste bloqueado.
- **Literales del CRO** en menús: caja de partida (nivel, jugadores, capítulo), ventana de equipo,
  estrategias (がんばれ/まもれ/せめろ), cabecera de estadísticas de tienda (キック…ガッツ), tienda
  (かう/うる, nombres de tienda con furigana), tabla de números del capítulo (一…十, punteros).
- **Nombres de NPC genéricos** (`unitbase.dat +16`): alumnos, alumnas, profesores y apellidos sueltos que la
  NDS no nombra (en DS no había recuadro de hablante). Filtrar `ダミー` (no sale). Se rotulan por papel.
- **Nombre principal de jugador** (`unitbase.dat +0`): la ficha de Formación lo usa; no basta con `+16`.
- **Títulos de equipo** (`rpgtitle.STR`): búfer de 9 caracteres aunque el hueco sea de 32 B.

### Gráficos que no son texturas CTPK
- **Sprites de DS heredados** (`pic3d/*.pac_`, `*.SPL/SPD`): burbujas de partido (ナイス!, ミス!), もどる,
  はい/いいえ, リプレイ, placas de escuela, menús de pausa. La NDS española trae los mismos en
  `pic3d/sp/` con el mismo formato: copiar tal cual (`work/ie1/capas/v56/sprites`). `mln_i02` no es 4 bpp.
- **Fondos `.lzs`** fuera de los `.arc` (p. ej. créditos de la canción del opening,
  `menu/data_replace/title_movie_bg/*.lzs` = SSZL(CTPK)). Reenvolver en SSZL con literales.
- **Placas pintadas sobre el campo** (`form_ground_*`: GK → POR) y posiciones FW/MF/DF/GK en otras vistas.

### Medidas y límites que el juego impone
- Rectángulo QNA real por pieza, alineación del japonés y ancho máximo cuando va un número al lado.
- Equipos: 9 caracteres (el cuadro de pachanga sale pegado al borde de la pantalla).
- Objetos: 9 caracteres (18 B). Latín de 1 byte no sirve: el menú parte la fila tras 10 caracteres.
  Botas/guantes/pulseras: quitar la palabra del tipo (el icono lo indica) aunque el nombre se repita.
- Supertécnicas en objetos (manuales): el menú de Técnicas usa textura con el nombre entero; los mensajes
  usan el nombre de objeto de 9. Abreviar solo la palabra genérica con abreviatura fija («R.», «Tor.»),
  nunca la distintiva. Al usuario le importan los nombres oficiales: no renombrar.
- Glifos: la caja de partida y otros menús pintan con **FONT12.NFTR**, que no tiene romanos ni números en
  círculo; comprobar en esa fuente antes de usar un carácter especial. El guion `-` no existe en ancho
  completo en Shift-JIS.

### Medios
- **Subtítulos de cinemáticas y opening**: ticks de 30 Hz (sección 7).
- **Voces y efectos** (`sound/*.SED/SWD/SMD`): la NDS española los trae en `sound/sp/sound.pb` (índice
  `sound.ph`: nombre 24 B + offset + tamaño). En IE1 3DS los `.SWD` pesan más que los de DS y las voces de
  gol se parten en `3D_003_NNa…z`: no sustituir en bloque; identificar el banco (grito del título, gol)
  y probar pares SED+SWD de uno en uno.
- **Pantalla de aviso/créditos del proyecto**: se añade al final de `movie/logo_l5.moflex`
  (`work/ie1/capas/v54/pantalla_inicio`: fuente del juego, lista de colaboradores). Confirmar en juego que el
  arranque reproduce el vídeo entero.

### Distribución
- Nunca alojar `archive.fa`, `.SAD` ni ningún fichero del juego. Para herramientas de terceros: xdelta por
  fichero contra el original + manifiesto con SHA-256 (`work/paquete_v55/generar.py`).

### Fuente mejor que la NDS: la versión europea de 3DS (CTR-N-JEUP)

- La CIA europea descifrada trae `archive.fa` con carpetas `es/`, `en/`, `fr/`, `it/` (1.179 ficheros por idioma) y `romfs/es/inazuma1/data_iz/sound` (184 voces oficiales en formato 3DS: SAD, voces de gol `3D_003_NNa…z`, `2D_020_*`).
- Las voces se instalan tal cual por LayeredFS: mismo nombre que la japonesa.
- `es/…/unitbase.dat` tiene 96 B por registro alineados con el japonés (nombre en +0 y corto en +32, ASCII de 1 byte). Sirvió para detectar NPC desplazados en 1167–1265. Los registros ≥1266 son «ダミー» en japonés.
- Su texto es de 1 byte con fuentes europeas: sirve como fuente de traducción, no como fichero para copiar.

- **Texturas `.lzs`/`.arc` SSZL: comprimir de verdad** (`tools/sszl.py`). Envolver solo con literales dejó `ie99_title_movie_bg_b01.lzs` en 147 KB frente a 24 KB: el juego no la cargó y en el opening se quedó la ventana de «Cargando» en lugar de los créditos de T-Pistonz.

## 11. Lecciones del IE2 (Tormenta de Fuego, v01–v22) — aplicar también al IE3

### Reglas de texto (obligatorias)
- **Volcado literal:** el IE1 sale del port europeo de 3DS (`work/ie1/fuentes/3ds_eu`, carpetas `es/`, misma
  estructura que el japonés) y el IE2 de la NDS española. **Los diálogos nunca se recortan ni se reescriben.**
  Si no caben, se reparten en más páginas con `\f`, sin cortar palabras. Solo se resumen los **objetivos**,
  y únicamente porque el usuario lo pidió.
- La IA solo se usa donde no hay fuente oficial. En IE1 muchas filas `auto-ia` tenían fuente en el port
  europeo; romanizaron nombres («Mikage» en vez de «Brain»). Revisar con el glosario.
- Lo que no tiene fuente (rótulos inventados, textos propios de gráficos) se lista para que lo revise el usuario.

### Caja de diálogo (CRO de cada juego; direcciones del IE2 `ina_main2.cro`)
- Límite 1, reajuste de líneas: `mov #0xF0` en el manejador de 0x301a (0x66a24) y el valor por defecto
  (0x4cabc). Se cambia en su sitio a 0x1A0 y se obtienen **37 caracteres por línea**.
- Límite 2, dibujo de la página: `mov r2,#0x120` en 0x4d6a0 → 0x1C0. El carácter que no cabe se dibuja al
  principio de la línea siguiente (sale un espacio inicial).
- Tope 3, **búfer de 132 B en la pila** (0x4d638, `sp+0x40`). **No se puede ampliar.** Regla por página:
  `2 × caracteres + (líneas − 1) ≤ 131`. Si se pasa, el texto se corta, sale «?» (carácter partido) y se
  corrompe la pila, con riesgo de cuelgue. Afecta también al reparto de 22 × 3.
- Los parches en su sitio de un inmediato, **verificando que ninguna entrada de relocalización cubre esos
  bytes**, funcionan. Lo que falla es el código nuevo en huecos («caves»).
- Reparto: `work/ie2/shared/capas/v17/paginas/comun17.py` (DP por costes: fin de frase, sin páginas
  huérfanas) y `v19/saltos37`. **El IE1 no tiene este parche todavía:** sigue en 22 × 3.

### Otros límites medidos
- **Objetivo:** 40 B (20 casillas); el juego escribe el fin de texto en ese punto (0x8a104).
- **Rótulo:** 10 casillas, FONT8 a 10 px. **Pestaña del nombre:** FONT8 a 10 px. **Menús de campo:** FONT12
  con paso fijo de 15 px.
- **Literales del CRO en lista (strlen+1):** si solo el primer elemento tiene referencia, los bytes del bloque
  se pueden **redistribuir** entre sus entradas (así caben «Inventario», «Sistema»…). Comprobar antes que
  nada apunta dentro del bloque. Ojo con las copias comparadas (el texto de guardar en 0xbd35c).

### Bigramas (parejas de letras en kanji sin uso)
- Registro único y compartido por toda la recopilación: `work/ie2/shared/capas/v08/nombres_compactos/
  registro.json`, solo se añade al final. Las fuentes son comunes a los tres juegos: FONT12, FONT8 y FONT12T.
- Cada pareja debe dibujarse en **todas** las fuentes que muestren ese texto: la pestaña y el rótulo usan
  FONT8; la ficha, las descripciones y los objetivos, FONT12; los partidos, FONT12T.
- **Los códigos libres se han agotado** (queda ~1). Para el IE3 habrá que liberar códigos o reutilizar
  celdas. Usar el escáner estricto (`escaneo_literales.py`), que también detecta literales en code.bin y
  los CRO.

### Teclado del IE2
- La tabla **no** son ficheros sueltos: está en los paquetes LZ10 `inazuma2/data_iz/pic2d/menu/MMName.SPF_`
  y `MMProfd.SPF_` (entradas FCODE0/1/2). Los `fcode*.txt` sueltos en romfs **no se leen**. Las texturas
  `name_b` son idénticas a las del IE1.

### Cinemáticas
- **La 3DS no muestra nunca `movie/txt/*.dat`**: dibuja en una capa oculta. El japonés lleva los subtítulos
  grabados en el vídeo, así que hay que **grabar los españoles en el vídeo**:
  `work/ie2/shared/capas/v11/subtitulos` (una sola codificación desde el original, QP 12).
- La franja inferior es negro plano, así que el japonés se borra sin reconstruir nada. Los carteles
  dentro de la imagen (marcadores, pizarras, logos) se componen desde el fotograma NDS alineado
  (`v07/media/rotulos.py`).
- Algunos montajes NDS difieren del 3DS (a2m14, op00): hay que seguir la línea de tiempo de la voz española.

### Gráficos
- Pintar siempre sobre una capa transparente y comprobar el estado pulsado. Copiar el **estilo** del
  japonés (degradado, contorno): los rótulos planos se rechazan.
- En la NDS del IE2 muchos sprites están **dentro de paquetes** (`pic3d/sp/common.pkb`, `mbd_s.pkb`), no sueltos.
- Las **capturas de ayuda** (`help_b/data/ie02_tt*.arc`, 71) se hacen a partir de `pic3d/script/sp/tt*.pac_`
  de la NDS (escala ×1,25, pegando solo donde difieren). `MASTutorial.SPF_` no se usa en 3DS.
- **Logo del título:** las piezas son compartidas por Fuego y Ventisca. Cada versión solo cambia el fondo
  (`bg_fire01`, `bg_blzd01`), que es donde va el PNG oficial entero.
- Auditar siempre las copias duplicadas de una misma textura en otros `.arc` (por ejemplo `wireless_off_b`).

### Sonido
- Bancos en `sound.pb` (CWAV DSP-ADPCM en 3DS; IMA en NDS): hay que remuestrear y recodificar. Grito del
  título: `3D_901`. Goles: `3D_003_*`. No dejar muestras en silencio sin saber qué secuencia las usa.
- El IE2 tiene 477 SAD (472 comunes y 5 de Fuego) instalados por LayeredFS.

### Construcción e instalación
- `candidata.construir` **rechaza entradas nuevas** en archive.fa. Los ficheros de romfs sueltos (SAD,
  sound.pb) se copian a la carpeta `romfs/` de la candidata y el instalador los copia enteros.
- Los eventos protegidos (inicio, tutorial) pueden crecer si ya no llevan marcadores de furigana; el
  build tiene que eximirlos explícitamente.
- Con el disco justo, borrar solo candidatas cuyo contenido ya esté en otra, y **nunca** una que otra capa
  use como referencia.
