# Auditoría de la interfaz de IE2 (3DS) frente al original NDS en español

> Petición del usuario (2026-11-09), tras probar IE2 en el PC y compararlo con una foto del juego original en NDS: «fíjate en el gráfico de la pantalla de arriba, nada que ver con el nuestro, por no hablar de los menús del juego que de hecho faltan botones y las letras en el original son más pequeñas y encajan mejor»; y, sobre IE1: «muchos [gráficos, botones y textos] los tradujiste con IA en lugar de extraerlos de las traducciones originales. Fíjate en el gráfico de salir del juego: no dicen lo mismo. Esto es solo un ejemplo pero hay muchos más».

Análisis **estático** (sin emulador, sin tocar el PC ni los 5 ficheros congelados del bloqueo v20; no se ha creado ninguna capa). Solo ids, rutas, hashes, cifras y rótulos cortos (Norma 2). Todo `runtime_verified: false`. Bases (estado del PC según `docs/BACKLOG.md`, «Estado del PC» y «Paquete conjunto v3»): instalados HOY `archive.fa` `6878CC93…B3A3` y `ina_main2.cro` `CE0449BF…E008`. Las texturas y la CRO se leyeron del **paquete v3** (construido, **sin instalar**): `archive.fa` `BD646264…E2DA` (solo difiere de la instalada en las 2 entradas del Inablog; las texturas de interfaz son las mismas) y `ina_main2.cro` `E20D93B4…8D8C` (= `CE0449BF` + `slot_guardado_ie2`, 38 B; byte a byte igual a la salida de esa capa). Todo lo que este documento dice de `0x3364c`, `0x2119f0` y `slot_guardado_ie2` debe leerse así: en la CRO **instalada** (`CE0449BF`) `0x3364c` vale `0a00000d` y no hay cueva; en `E20D93B4` (v3) ya lleva `beq 0x2119f0` y la cueva `0x2119f0`. ROM NDS española de IE2 (`work/ie2/tormenta_de_fuego/fuentes/nds_es`). Los volcados y comparativas están en el scratchpad de la sesión (`aud_ie2/`, `u1_ie2/`, `u3_metodo/`), no en el repo.

## 0. Respuesta corta

**El usuario tiene razón.** En IE2 el problema es más grande que en IE1: las capas gráficas no usaron la NDS ni el arte europeo, sino que **repintaron** los rótulos con el rasterizador propio sobre la NFTR japonesa (acentos compuestos, TTF de Windows), y los textos de la CRO salen en su mayoría de IE1 v89 (anterior a su revisión) o son abreviaturas del hueco japonés.

- Textos de la CRO: de 298 elementos comparados con la tabla de cadenas del ARM9 NDS, solo **69 son iguales**; 192 distintos, 11 faltan, 7 son estructura, 16 sin oficial y 3 siguen en **japonés**.
- Texturas: de 1 008 de interfaz, el proyecto tocó 272-284; unas 251-264 son **pintadas** (no oficiales) y solo unas 8 salen de píxeles oficiales. 724 siguen como el original japonés, incluido su latín (`LV`, `NEXT`, `NEW`, `GAME OVER`) y restos de japonés.
- Hay fuente oficial en español: la tabla de cadenas del ARM9 NDS (textos) y los gráficos NDS; además, **IE1 ES e IE3 ES (3DS europeos, ya en disco) comparten motor y formato CTPK/QNA** y traen el arte oficial en español: 609 y 662 texturas con pareja por arc+sufijo, **168 con mismo tamaño, mismo QNA y píxeles distintos**. «Mismo QNA» significa mismas cajas UV de la textura, no la misma posición en pantalla; y el texto de cada pieza trasplantada debe contrastarse con la NDS antes de aceptarla (§5.0, regla V), porque IE1 ES e IE3 ES no son la fuente canónica de IE2 (Norma 3).
- Parte de lo que ve el usuario **no es corregible** (§3): el 7.º botón del menú, «Móvil», StreetPass, el tamaño de letra del motor.

## 1. Petición y evidencia

| Pantalla | NDS ES (foto) | Nuestro IE2 3DS | Causa localizada |
|---|---|---|---|
| Superior de equipo, panel azul | `Niv.`, `PE`, `PT`, `SIG.` | `LV`, `NEXT` (latín del japonés) | Textura `battle_member_t`/`_b` `ie02_menu_member_status_plt_*` (256x128 f2), nadie la tocó |
| Superior, franja inferior | `Niv. equipo`, `Jugadores`, `Título` | `Nivel`, `Jug`, sin `Título`; letras separadas; «Arietes Maníacos» desbordado | Literales CRO `0x1a2e04/20/2c/34` con `adr` + paso fijo FONT12 de 11 DS (`0x3364c` = `0a00000d` en la CRO instalada `CE0449BF`; IE1 e IE3 llevan `0a00001f`; el paquete v3 lo corrige para titulo y equipo) |
| Menú de campo | 7 botones: Jugadores, Supertécnicas, Inventario, Estrategias, Datos, Recursos, Guardar | 6: Equipo, Inventario, Tácticas, Datos, Sistema, Guardar | Lista FONT12 de 56 B en `0xfc060` (CRO); array de ids del ov0 NDS en `0x2119190` |
| Submenú Datos | Futblog, Álbum… | Blog, Álbum, Móvil, Uniformes, Récords («Móv il», «Un iformes») | Lista CRO `0xfc3e0`; el hueco es de paso/bigramas del motor, no del texto |
| Salir | 4 rótulos + Sí/No | otro texto, hueco central, `Si` sin tilde | Textura pura `quit_b.arc` (13 835 B): `quit_logo01` 128x16, `quit_msg01` 256x64, `btn02`; la CRO solo carga el arc (`0x213084`) |

## 2. Método y fuentes

**Método de IE1 reutilizado** (`docs/AUDITORIA_TEXTOS_MENUS_IE1.md`, `docs/AUDITORIA_LUGARES.md`, `work/ie1/capas/graficos/rotulos_menus_eu`, `guardado_oficial_eu`, `menus_cro/salir_abandonar`): comparar cada textura y literal con la fuente oficial, copiar solo si tamaño, formato y cajas QNA coinciden, y justificar lo que queda fuera. Herramientas: `ie123kit` (`graficos/texturas`, `ctpk`, `qna`, `pac_sprite`, `lz10`), `fundir_arcs.py` (Lector por pread del archive), `tabla_texturas.py`, `ocupacion_celdas.py`, emulación unicorn de `slot_guardado_ie2`.

**Diferencias con IE1:** (1) no existe port europeo 3DS de IE2; (2) no hay ROM japonesa NDS que dé la clave id→literal japonés, así que el pareo CRO↔NDS es por orden de código y sentido (confianza «alta/media/baja»); (3) la NDS es de 256x192 y hay que adaptar (pantalla inferior 320x240 = ×1,25 exacto; la superior 400x240 se recompone).

| Fuente oficial | Qué da | Estado |
|---|---|---|
| Tabla de cadenas del ARM9 NDS (425 punteros en `0xb5b90`, ids T000-T424, `GetString` `0x020a0854`; ~135 cadenas más en overlays) | Textos de CRO. Acentos propios (é=BA, ó=C4, ñ=C2, í=BE, á=B2, ¿=A5, ¡=DF) | Decodificada; `strings.txt` la lee mal |
| Ficheros de datos NDS (`logic/sp`, `script/sp`) | command/item/rpgtitle/unitbase/ShopName/blog… | Ya en español en el archive 3DS (no revisados fila a fila) |
| NDS `pic3d/sp` (`.SPL/.SPD`, 707 piezas, 685 legibles) | Botones y rótulos (`Aceptar`, `Sí`, `No`, `Niv.`…) | Decodificable con `pac_sprite` |
| NDS `pic2d/**/*.pac_` (34 pantallas) | Cabeceras, listas | Decodificable con `mapa_pic2d` |
| NDS `pic2d/**/*.SPF_` (61; `MMQuit`, `MMSlot`…) | Diálogo de salir, guardado | Texto confirmado a ojo; **falta decodificador de celdas SFP** (no existe en el kit) |
| IE1 ES 3DS (`work/ie1/fuentes/3ds_eu`) e IE3 ES 3DS (`work/ie3/fuego_explosivo/fuentes/3ds_eu/romfs/archive_bz.fa`, `es/`) | Arte ES ya en formato 3DS | En disco; 168 trasplantes casi directos |

**Origen actual de los rótulos de IE2:** v03 pintada 167, v06 84, v12 13, IE1 v89 (no EU) 21; oficiales EU/NDS ~8 (`Límite`, `Furor`, ♂/♀, `Sonido`, títulos de episodio y mapa). En CRO: de 321 literales v03, 54 salen de la NDS, 234 de IE1 v89 y 22 «equivalente IE1»; las capas posteriores sí usaron la NDS pero emparejaron mal (なかま→«Equipo» en vez de Jugadores; せんじゅつ→«Tácticas» en vez de Estrategias). El informe `auditoria_graficos` que dice «LV, NEXT, PK no llevan texto» es **falso**.

## 3. Tabla resumen por pantalla/elemento

Clases: IGUAL, DISTINTO, FALTA, ESTRUCTURA (3DS vs NDS). Acción: dato, CRO, textura nueva (copia = trasplante IE1/IE3 ES; NDS = rehacer con glifos NDS), no corregible. «Cabe»: A = ancho completo, B = solo con bigramas, C = no cabe sin cueva y parche de código (estimación por bytes, sin medir píxeles ni comprobar que existan los bigramas: una fila B no es «bajo» hasta medirla). Cifras de los 192 DISTINTO (tabla de cadenas, columna `cabe`): A 6, B 113, C 67, sin clasificar 6; de ellos 56 son de comunicación inalámbrica (A 2, B 34, C 18, sin clasificar 2) y 136 no (A 4, B 79, C 49, sin clasificar 4).

| # | Pantalla / elemento | Hoy → oficial | Clase | Acción | Esfuerzo |
|---|---|---|---|---|---|
| 1 | Panel superior `status_plt_t01/_b01` | `LV`/`NEXT` → `Niv.`/`SIG.` | DISTINTO (sin traducir) | textura copia (IE1 ES misma maqueta, recortar 2 etiquetas) | bajo |
| 2 | Familia `LV`: `result_plate_b01`, `add_member_b window_b03`, `select_player_b window_b0x` | `LV` → `Niv.` | DISTINTO | textura copia (IE1/IE3 ES, mismo QNA) | bajo-medio |
| 3 | `PE`/`PT`, `Niv.`/`Reg.`/`Bloq.`/`Tiro`/`Atajo` en `status_t` | oficiales | IGUAL | verificar acentos | ok |
| 4 | Franja: `Nivel` (`0x1a2e04`, 12 B) | → `Niv. equipo` [T95] (11 letras: solo con bigramas) | DISTINTO | CRO (B) | medio (medir en px) |
| 5 | Franja: `Jug` (`0x1a2e20`, 6 B) | → `Jugadores` [T61] | DISTINTO | CRO (C: cueva + parche `adr`) | medio |
| 6 | Franja: rótulo `Título` (`0x1a2e34`, 4 B, en blanco) | → `Título` [T97] | FALTA | CRO (C) | medio |
| 7 | Franja: paso fijo, «Arietes Maníacos» desbordado, «Móv il» | tipografía del motor | DISTINTO | CRO: `slot_guardado_ie2` (marca -4, 38 B; está en el paquete v3 `E20D93B4`, **instalado en el PC el 2026-11-09 a las 20:31, sin probar en juego**; el modo «_2» es incierto) y extender | bajo (instalar el v3) / medio (extender) |
| 8 | Menú de campo: 6 vs 7 botones | — | ESTRUCTURA | no corregible el botón nuevo | — |
| 9 | Botón `Equipo` (A2, B1) | → `Jugadores` [T61] | DISTINTO | CRO (C: lista 60 B > 56 B, reubicar) | alto |
| 10 | Botón `Tácticas` (A4, C5, D2, D6, D18) | → `Estrategias` [T63] | DISTINTO | CRO (C) | alto |
| 11 | Botón `Sistema` (A6, C15) | → `Recursos` [T99] | DISTINTO (pareja media; `system_b` ya tiene la pestaña `Recursos`) | decisión: recomendado mantener `Sistema` (§6.3); si se cambia, CRO (B) | medio |
| 12 | `Menú`, `Inventario`, `Datos`, `Guardar`, `Supertécnicas` (pestaña) | oficiales | IGUAL | no tocar | — |
| 13 | `Supertécnicas` como botón principal | NDS 2.º botón | ESTRUCTURA | no corregible | — |
| 14 | Submenú Datos: `Blog` | → `Futblog` [T66] (la tabla lo marca C: 6 B no bastan salvo bigramas) | DISTINTO | CRO (C, B con bigramas) | medio |
| 15 | Submenú Datos: `Móvil` | sin texto NDS | ESTRUCTURA | no corregible | — |
| 16 | Pestañas Jugadores/menú objeto/equipo: `Jug.`, `Equipo`, `Equip.`, `Inv.`, `Habil.`, `Alinear` | → `Jugadores`, `Equipación` [T101], `Inventario`, `Habilidades`, `Alineación` | DISTINTO | CRO (mayoría C) | alto |
| 17 | Salir: `quit_logo01` | `¿SALIR?` → `¿Abandonar la partida?` | DISTINTO | textura 256x16 de IE1 ES + caja QNA ensanchada de 92 a 256 (§5.1, medida); **no requiere el decodificador SFP** | medio |
| 18 | Salir: `quit_msg01` | texto inventado con hueco → 2 frases oficiales | DISTINTO | textura de IE1 ES (256x256) con las cajas QNA de IE1 ES (la QNA actual solo tiene cajas de 138 y 226 px); **no requiere SFP** (§5.1) | medio-alto |
| 19 | Botones `Sí`/`No`/`OK`: `quit_b btn02`, `shop_b confirm_btn_b01`, `item_b button_b02`, `win_slot_b_btn02`, `slot_b btn02`, `select_emblem_b`, `connection_b`, `name_b keikoku01`, `add_member_b mes_b02` | `Si` sin tilde → `Sí`/`No`/`Aceptar` | DISTINTO | textura copia (IE1/IE3 ES) | bajo |
| 20 | Guardado `slot_b_font01` | `Jugadores`, `vic.` → `Niv. equipo`, `Tiempo de juego`, `Miembros`, `min`, `Victorias` | DISTINTO | textura nueva NDS `MMSlot` (cajas de 96 px) | medio |
| 21 | Mensajes de guardado `win_slot_b_msg01`, `menu_slot_b_msg01` (256x256) | frases inventadas → ~5 oficiales | DISTINTO | textura copia/NDS (IE3 ES `slot_window_win_msg_slot01`, IE1 ES, NDS `SFDN_W00-W10`) | medio-alto |
| 22 | Tienda: `trade_button_b01` (128x256), `decision_plt_b01` | japonés → `Comprar`/`Vender`/`Salir`, `Aceptar` | DISTINTO (JP) | textura copia + re-maquetar | medio |
| 23 | `wireless_common_b01`, `caution_t name_caution_t`, `wireless_member_b btn_b01/b02` | japonés → ES | DISTINTO (JP) | textura copia (IE3 ES, mismo tamaño y QNA) | bajo |
| 24 | `gameover_logo01`, `binder_b new01/new02` | `GAME OVER`/`TO BE CONTINUE`/`NEW` → `FIN DE LA PARTIDA`/`CONTINUARÁ`/`NUEVO` | DISTINTO (inglés) | textura copia (IE1/IE3 ES) | bajo-medio |
| 25 | `select_captain_b` (4 texturas; `mes_b01` conserva además muchos kana: もどる, えらぶ, ねっけつ…) | `Pasión/Calma/Seguir…` (IE1 v89) | DISTINTO (kana) / **sin oficial NDS en texto** | **NO copiar de IE1 ES**: su `Audaz/Calma/Apoyo` choca con la NDS, donde `Pasión` es término oficial [T59, T60]. Rehacer con el gráfico NDS `captainselect` (sin decodificar, fase 7) o dejar como está y limitarse a quitar el japonés | medio |
| 26 | Pantallas Wi-Fi/StreetPass (`wireless_b`, `_t`, `_off_b`, `_uniform_b`, `stage_select_b`) | japonés | DISTINTO (JP) / ESTRUCTURA | pintar con glifos NDS; sin pareja | alto, prioridad mínima |
| 27 | 3 frases CRO en japonés (`0x220564`, `0x2205a4`, `0x223898`) | → T071, T072, T173 | DISTINTO (JP) | CRO (B) | bajo-medio |
| 28 | Fichar: panel de detalle (G1-G34): `Fich`, `Atr`, `Sabe`, `Veloz`, `Hábil`, `PE y PT+`… | → `Fichar`, `Salir`, `Inteligencia`, `Rapidez`, `Destreza`, 7 frases 1:1 [T123-129] | DISTINTO | CRO (B/C) | medio-alto |
| 29 | Confirmaciones H1-H26 (`¿Seguro?` donde va T179, `¿Quitar a %s?` T166…) | abreviadas → íntegras | DISTINTO | CRO (A/B/C) | medio |
| 30 | Mensajes de aviso I1-I47 y técnicas J1-J14 (`Sin puntos.`, `Ya no caben.`, `¡Ya la sabe!`…) | abreviadas → íntegras | DISTINTO | CRO: 7 caben en ancho completo (A), el resto B/C | medio-alto |
| 31 | Comunicación inalámbrica K1-K66 | resumen inventado → frase NDS | DISTINTO | CRO (CWF/DS inalámbrica no existe en 3DS) | prioridad mínima |
| 32 | Etiquetas solo NDS (11 filas N1-N10 y E5) | ver §4 («FALTA»): cuatro grupos distintos | FALTA | **no investigado**, salvo lo anotado en §4 | — |
| 33 | StreetPass (K59, K62, H21) | sin texto NDS | ESTRUCTURA | no corregible | — |
| 34 | `Pasión/Calma/Apoyo`, `Normal/Defender/Atacar` | gráficos en la NDS (sin cadena) | SIN OFICIAL en texto | textura (ver #25) | bajo |
| 35 | Nombres de técnicas (521) y escuelas (528) | texto oficial NDS, rasterizado propio | IGUAL en texto, distinto en trazo | revisar solo texto; trazo = decisión de tipografía | prioridad baja |
| 36 | Títulos `rpgtitle.STR` (38) | `Espíritus Álgidos` (registro 0 de `rpgtitle.STR` NDS, acentos con el mapa del proyecto: 0xBE = í, 0xD1 = Á; coincide con `capas/nombres/titulos/informe.json`) recortado a `Espíritus` (búfer de 9 casillas; 38 registros en ambos ficheros) | DISTINTO | dato/CRO (comprobar) | bajo |

Muestras de la CRO que ya son correctas y **no se tocan**: `Menú`, `Inventario`, `Datos`, `Guardar`, `Ordenar`, `Todos`, `Supertécnicas`, `Objetos`, `Álbum`, `Uniformes`, `Récords`, `Ajustes`, `Grupo`, `Almacén`, `Tirar`, `Quitar`, `Echar`, `Aprender`, `Apodo`, `Maestro`, `PE`/`PT`.

## 4. Lo que NO se puede corregir y lo que NO está investigado (con evidencia)

**No corregible** (probado o inherente a la versión 3DS):

1. **Botón `Supertécnicas` de primer nivel.** El menú japonés 3DS (`0xfc060`) tiene 6 entradas (なかま, もちもの, せんじゅつ, じょうほう, システム, セーブ; lista de 56 B de `0xfc06c` a `0xfc0a4`); la NDS tiene 7 en el array de ids del ov0 (`0x2119190`: 61, 104, 62, 63, 64, 99, 65). La función existe en 3DS como **pestaña** dentro de Jugadores (`0xfc0c9`, ya oficial). No se puede añadir un botón.
2. **`Móvil`** (ケータイ): la función no existe en la NDS; es 3DS. **StreetPass** y «Modo DL»: solo 3DS.
3. **Montaje de frases en 3DS** (I8, I11): la 3DS ensambla prefijo + número + unidad con un orden distinto del NDS; no admite la frase entera.
4. **Pantalla superior del equipo NDS** (barras PE/PT, ocho filas): el 3DS dibuja paneles de 4 jugadores; se traducen las etiquetas, no se replica el diseño. Pieza NDS exacta no localizada.
5. **CWF/Wi-Fi de Nintendo** (K26-K31 y pantallas `wireless_*`): servicio cerrado; texto oficial disponible, utilidad nula.
6. **Textos que no caben** (clase C): por Norma 3 el texto oficial va íntegro; no se reescribe para que quepa. Requieren cueva y parche de código del `adr` (como en Fichar `0x211a90…0x212000`) o quedan sin corregir. Hay literales con tope duro de búfer.

**Letra «más pequeña y mejor encajada» (petición del usuario).** No es «no corregible» sin más, sino una **decisión ya tomada y reabrible solo por el usuario**: el 2026-11-09 (BACKLOG, «Decisión sobre la fuente») el usuario eligió mantener la fuente actual para los tres juegos (FONT12 con el dibujo del port EU, FONT8 sin cambios), y la sonda NFTR del mismo día mostró que las NFTR de IE2 no dibujan esas pantallas, de modo que un aspecto NDS en IE2 exige una sola fuente para los tres juegos o código nuevo de riesgo alto. Lo que sí es mitigable con la fuente actual es el **paso fijo** (FONT12 a 10/11 DS por letra en la CRO instalada porque `0x3364c` = `0a00000d`): la marca -4 de `slot_guardado_ie2` (en el paquete v3) lo arregla en titulo, equipo y listas del Inablog; extenderla a las listas del menú es trabajo de las fases 4-5. Cambiar el dibujo o el tamaño de la letra queda fuera del bloqueo v20 hasta nueva petición explícita (§6.2b).

**FALTA: tres grupos distintos, no «no corregible».** Los 11 rótulos FALTA (N1-N10 y E5) se separan por evidencia:

- **E5 `Título`** (`0x1a2e34`): sí corregible (#6, CRO clase C); el hueco en blanco está en la CRO.
- **N6 `Al equipo`, N7 `Al grupo`, N8 `Al almacén`:** el 3DS tiene `Equipo`, `Grupo` y `Almacén` (C19-C21, IGUAL a la NDS). Falta saber si el rótulo NDS «Al ...» corresponde a una pantalla 3DS (envío de jugadores entre equipo, grupo y almacén): **no investigado**; posible textura o frase de otra pantalla.
- **N9 `Cancelar`:** el inventario decodificado de la CRO (15 559 literales) solo lo trae en una frase (H24, `0x224271`); como rótulo de botón puede ser textura: `wireless_common_b01` y `wireless_member_b` aún tienen `キャンセル` y `やめる` en japonés (la NDS dice `Cancelar`). **No investigado**; en las texturas de Wi-Fi no sirve de nada (§4.5).
- **N1 `Logros`, N2 `Torneo`, N3 `Estado`, N4 `Detener`, N5 `Pachanga`, N10 `Duelo 1/2/3`:** 0 coincidencias en el inventario decodificado de la CRO (con el decodificador de bigramas; una búsqueda de texto plano no vale, los menús van codificados). Pueden ser textura (las 1 008 de interfaz no se han leído una a una) o función ausente en el 3DS: **no investigado**. Se resuelve en la fase 0 del plan (clasificación por textura).

El usuario dijo «faltan botones»: hasta cerrar estos grupos, lo único **confirmado** que falta es el 7.º botón (§4.1) y `Título` (E5); no se puede afirmar que el resto sean funciones ausentes.

## 5. Plan por fases (por lo que más se ve)

### 5.0 Reglas de cada fase

- **Regla V (verificación contra la NDS).** Antes de aceptar una pieza trasplantada de IE1 ES o IE3 ES: (1) leer el texto de la imagen y compararlo con la cadena NDS (id T de la tabla ARM9, o lámina NDS decodificada de `pic3d/sp` o `pic2d`; si el gráfico NDS no es decodificable, con la foto del usuario); (2) si difiere (caso `Audaz` frente a `Pasión`, #25), prevalece la NDS (Norma 3) y la pieza se rehace o se deja; (3) preview antes/después con la caja QNA real; (4) comprobación mecánica (tamaño, formato, QNA). La validación mecánica sola no basta: «mismo QNA» es mismo UV, no misma posición en pantalla.
- **Regeneración del archive.** El `archive.fa` de 1,6 GB es **uno solo para los tres juegos**. Cada capa gráfica de IE2 cambia su sha256, supera los `instalar_*` anteriores (el del paquete v3 espera `6878CC93` → `BD646264`), obliga a regenerar IE1 e IE3 sobre el nuevo y a copiar el archivo entero al PC. Por eso las capas gráficas se agrupan en **un solo archive por bloque de prueba** (§6.8), con un paquete conjunto nuevo y deshacer exacto. Las capas CRO no tocan el archive.
- **Jerarquía de hashes.** Archive: `6878CC93` (anterior) → `BD646264` (v3, **instalado hoy 20:31**) → archive de las fases 2-3 → …; CRO de IE2: `CE0449BF` (anterior) → `E20D93B4` (v3, **instalada hoy 20:31**) → fases 4-6. Si el paso 0 falla y hay que usar la variante `solo_modo0` (`3DE2DAED…`) la base CRO cambia y las capas CRO posteriores se rehacen sobre la que quede.
- Cada capa: `runtime_verified: false`, `instalada: false`, `validate.py --copia`, `fundir_arcs` sin conflicto, `sincronia_usearch verificar`, instalar/deshacer sin copia.

### 5.1 Caso «salir» medido en píxeles (el ejemplo del usuario)

Medido sobre las texturas del archive v3 (pieza de IE2) y de IE1 ES (`work/ie1/fuentes/3ds_eu`), con `QnaLayout`:

| Pieza | IE2 hoy | IE1 ES (texto oficial) |
|---|---|---|
| `quit_logo01`: textura | 128x16; texto pintado en x 15-76 (61 px) | 256x16; `¿Abandonar la partida?` en x 44-211 (**167 px**), alto 16 |
| `quit_logo01`: caja QNA | 0-92 x 0-16 (dos partes, ambas de 92 px) | una parte de 92 px y otra de **256 px** |
| `quit_msg01`: textura | 256x64 f4 | 256x256 f0 |
| `quit_msg01`: cajas QNA | 138x16, 226x16 y 164x12 (frases japonesas partidas) | 256x48 (cuerpo, 2 líneas, texto en x 2-251), 144x16 y 144x16 (aviso, 2 líneas), más las cajas de 164x12 y 102x12 que comparte con IE2 |

Conclusiones con evidencia: (1) el título oficial mide 167 px frente a una caja de 92 px y una textura de 128 px: **no cabe sin ensanchar caja y textura**, y la propia IE1 ES lo resolvió con una caja de 256 px; (2) las dos frases oficiales miden hasta ~250 px frente a las cajas de 138/226 px; (3) la pantalla inferior mide 320 px, de modo que el texto oficial cabe en pantalla: lo que no cabe son las cajas actuales; (4) por tanto **#17-18 no dependen del decodificador SFP** (fase 7) sino de editar la QNA de `quit_b` (ensanchar las cajas o adaptar la QNA de IE1 ES renombrando las texturas `ie01_` a `ie02_`); la ruta con glifos NDS tampoco evita ensanchar (no se ha medido su ancho). **No comprobado:** que el motor de IE2 centre o coloque la caja ensanchada como el de IE1 ES, y qué índices de parte lee la CRO (`0x213084` solo carga el arc). Plan B si la QNA ensanchada se descoloca: reescalar el título en la textura a 92 px es ilegible (167 → 92), así que el plan B es dejar el título actual y corregir solo `quit_msg01` y `btn02` (`Sí` con tilde, `No`). La primera entrega de la fase 3 es **solo `quit_b`** para una prueba mínima del usuario.

### 5.2 Fases

| Fase | Contenido | Entrega | Esfuerzo (estimado) |
|---|---|---|---|
| 0 | **Paso 0: probar el paquete v3** (INSTALADO el 2026-11-09 a las 20:31; falta que el usuario lo pruebe): corrige «Arietes Maníacos» desbordado y las letras separadas de titulo, equipo, Inablog y guardado, más el Inablog y las pachangas v3 de IE1. Solo es cambio de CRO y de 2 entradas del archive; el modo «_2» es incierto (variante `solo_modo0` si falla) | Prueba del usuario sobre el v3 | 0,5 d + prueba |
| 1 | Inventario: clasificar los FALTA por textura (§4), medir en píxeles las filas A/B visibles, ampliar el catálogo (hoy 1 008 texturas de interfaz; faltan las 2 494 de `a_data_replace`) | `catalogo_texturas_ie2` en repo (solo ids/hashes) y tabla A/B/C medida | 1-2 d |
| 2 | **Trasplantes directos con regla V** (168 parejas mismo tamaño+QNA): `LV`/`NEXT`→`Niv.`/`SIG.` (#1-2), `Sí`/`No`/`Aceptar` (#19), japonés de Wi-Fi/aviso (#23), `NEW`/`GAME OVER` (#24). **Fuera** `select_captain_b` (#25) hasta contrastar con la NDS | Capa gráfica con `apply.py`, `validate.py`, previews | 2-3 d |
| 3 | **Salir y guardado** (#17-18, #20-21) con edición de QNA (§5.1); tienda (#22). `slot_b_font01` y `MMSlot` NDS necesitan el SFP: se recompone desde IE1 ES/IE3 ES solo si pasa la regla V | Capa gráfica 2 (mismo archive que la fase 2) | 3-5 d |
| 4 | **CRO fácil** sobre la CRO del v3: 3 frases JP (#27), `Niv. equipo` (B, medir), las 6 clase A y las que se midan A/B | Capa CRO sobre `E20D93B4…` | 2-3 d |
| 5 | **Menú y franja con reubicación** (#5, #6, #9-11, #16): la lista de 56 B de `0xfc06c` no admite los rótulos NDS (60 B: 10+10+12+6+8+8 más 6 NUL) → cueva y parche de `adr`; `Jugadores`, `Estrategias`, `Título`; pruebas unicorn. **Criterio de abandono:** si tras 2 rondas de prueba del usuario el menú falla, se vuelve al estado del paso 0 y se documenta el límite (no se condensa el texto, Norma 3) | Capa CRO 2 | 3-5 d; riesgo alto, sin emulador propio |
| 6 | Fichar detalle, confirmaciones, avisos, técnicas (#28-30): A/B primero, C solo con cueva | Capa CRO 3 | 3-4 d |
| 7 | Decodificador SFP (`MMSlot`, partes NDS; **no** `MMQuit`, §5.1): `select_captain_b` desde la NDS, panel superior recompuesto, guardado NDS | Herramienta en `ie123kit` | 2 d de ingeniería + 2-3 d de aplicación |
| 8 | Prioridad mínima: Wi-Fi/StreetPass (#26, #31), nombres de técnicas y escuelas (#35), `rpgtitle` (#36) | Solo si se decide | 3-5 d |

Total orientativo (estimación, sin medir): fases 0-6, **15-23 días de trabajo**; fase 7 +4-5 d; fase 8 +3-5 d. Aparte: 3 ciclos de prueba e instalación del usuario (§6.8) y la regeneración de paquete por bloque (0,5-1 d cada una). El número anterior (17-27 d) no los contaba.

Riesgos: texto NDS más largo que el hueco japonés; QNA sin equivalente o descolocada (§5.1); el reescalado ×1,25 emborrona el píxel (los trasplantes IE1/IE3 ES no lo necesitan, solo lo que venga de la NDS); `adr` fijos al hueco japonés; pareo semántico sin clave (confianza media en #11); **que el v3 falle** (cambia la base de todas las capas CRO posteriores); regeneración del archive compartido (cambia el hash de IE1 e IE3).

## 6. Decisiones del usuario (con recomendación)

1. **Fuente de gráficos.** Recomendado: usar el arte de IE1 ES / IE3 ES solo como base de píxel donde coincida tamaño y QNA, y **aceptar cada pieza solo si su texto coincide con la NDS** (regla V); lo que difiera se rehace con la NDS o se deja. No se aparta de la Norma 3 (la fuente canónica sigue siendo la NDS), solo aprovecha la forma 3DS ya hecha. Alternativas: solo NDS escalada ×1,25 (más trabajo, necesita el SFP) o seguir repintando (descartado: es el origen del problema).
2. **Tipografía (bloqueo v20).** (a) ¿Se instala el paquete v3 (paso 0), que ya lleva el arreglo de paso fijo? Recomendado: sí, es gratis y arregla lo más visible. (b) ¿Se reabre la decisión del 2026-11-09 de mantener la fuente actual, para acercar la letra a la NDS? Recomendado: no por ahora; valorar tras la prueba de (a). Sin alternativa viable sin código nuevo: una sola fuente para los tres juegos o riesgo alto (§4).
3. **Menú de campo.** `Equipo`→`Jugadores` y `Tácticas`→`Estrategias` con reubicación y parche (fase 5, riesgo alto): recomendado sí, con el criterio de abandono de la fase 5. `Sistema`→`Recursos`: recomendado **mantener `Sistema`** (pareja de confianza media y `system_b` ya tiene la pestaña `Recursos`). Confirmado: no se añade el 7.º botón.
4. **`Jugadores` frente a `Miembros`.** Recomendado: seguir la NDS en cada pantalla (menú `Jugadores` [T61]; guardado `Miembros` [T100]); no cuesta más.
5. **`Ayuda` o `Tutoriales`.** No es una elección: la NDS usa `Ayuda` en el botón [T322] y `Tutoriales` en su submenú [T111]; se sigue cada uno.
6. **Alcance de textos.** De los 192 DISTINTO: A 6, B 113, C 67, sin clasificar 6; 56 son de comunicación inalámbrica y 136 no (A 4, B 79, C 49, sin clasificar 4). Recomendado: corregir A y B de las 136 visibles (83 filas, tras medir en píxeles) y de las C solo las del menú principal y la franja (~10: A2, A4, B1, B4, C1, C3, C5, C10, E3, E5); dejar documentados los 56 inalámbricos y el resto de C.
7. **Prioridad mínima** (Wi-Fi, StreetPass, nombres de técnicas y escuelas). Recomendado: dejar.
8. **Pruebas en el PC.** Recomendado: **tres bloques** y no una prueba por fase: A (paso 0 + fase 4, solo CRO), B (fases 2-3, un solo archive nuevo), C (fases 5-6, CRO). Cada bloque B regenera el archive compartido.

## 7. Límites

Análisis estático; nada probado en juego. No hay ROM ni archive japonés 3DS de IE2 en disco: el estado «sin tocar» se infiere de los informes de las capas. Los recuentos varían entre unidades (272 frente a 284 texturas tocadas; 251 frente a 264 pintadas) por el criterio de recuento y no se pueden comprobar con los ficheros. Las columnas «cabe» son estimaciones por bytes, no por píxeles ni por existencia de bigramas. Los ids del submenú Datos de la NDS se identificaron por vecindad en el ov0. No se localizó la pieza NDS del panel superior ni de la franja «Título / Equipo Victorioso», y no se decodificó el SFP: el texto oficial de «salir» sale de IE1 ES (su `quit_msg01` contiene las frases que el usuario describe de la NDS) y no del `MMQuit` NDS. No se comprobó en emulador que la QNA ensanchada de `quit_b` se coloque bien (§5.1). Los días son estimaciones. El paquete v3 no está probado: todo lo que dependa de él (§5.0) puede cambiar. Cobertura incompleta de las 2 494 texturas de `a_data_replace` y de los ficheros `.STR/.dat` fila a fila. Observado y no desglosado en la tabla: `select_captain_b` `mes_b01` conserva muchos kana (#25).

## 8. Issues

La fila 7 de `docs/BACKLOG.md` ([#111](https://github.com/luishidalgoa/inazuma-eleven-123-spanish/issues/111), «Botones de IE2 traducidos sin fuente») es el issue paraguas de esta auditoría. Esta tarea era solo de auditoría y no escribió en GitHub: los issues por fase (Norma 1) quedan como borradores para crear al aprobar el usuario cada fase: (a) instalar y probar el paquete v3; (b) trasplantes directos con regla V; (c) `quit_b` y guardado con edición de QNA; (d) CRO fácil sobre `E20D93B4`; (e) menú y franja (riesgo alto); (f) Fichar, confirmaciones, avisos; (g) decodificador SFP; (h) clasificación de los FALTA por textura.
