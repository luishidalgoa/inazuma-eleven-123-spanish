# Auditoría de nombres de lugar (IE1 · IE2 · IE3)

> Petición del usuario (2026-10-31): «¿tienes los nombres de cada escenario originales? me refiero a los de este rótulo [captura 44, «Estación»] porque me parece que muchos hiciste una solución rápida de generarlos por IA en lugar de los auténticos».

Análisis **estático** (sin emulador) del 2026-11-09. La primera versión se hizo sobre el `archive.fa` `397673B7…4510`; **la segunda ronda (tarde, tras revisar las previews y aprobar el usuario la excepción de FONT8) se reconstruyó sobre el `archive.fa` instalado ese día (paquete conjunto v3), sha256 `BD646264…E2DA`**, con las mismas entradas (mismo sha256 y offset) para `eve`, `vs_stage_select` y `FONT8`. Solo identificadores y nombres cortos (Norma 2). Capas resultantes: `work/ie1/capas/rotulos_objetivos/lugares_oficiales`, `work/ie2/shared/capas/rotulos_objetivos/lugares_oficiales`, `work/shared/capas/lugares_oficiales_fuente` (se instalan juntas) y la capa informativa de IE3. Todas `runtime_verified: false`, `instalada: false`.

## 0. Respuesta corta

**Sí, los nombres originales existen y se pueden recuperar para los tres juegos, y el usuario tenía razón en IE1 e IE2**:

| Juego | Fuente oficial de los nombres de lugar | Estado de la build instalada | Qué se hace |
|---|---|---|---|
| IE1 (3DS) | El `code.bin` del IE1 europeo de 3DS: resolutor «clave japonesa → índice → cadena ES» (120 claves, ids 408-527, 561 cadenas). Las mismas cadenas están en el arm9 de la NDS española. | De 170 nombres de 7 fuentes solo 43 (25 %) son oficiales, 99 abreviados o derivados y 27 inventados. En los rótulos jugables solo 14 de 75 nombres. El «Estación» de la captura debe decir **«Estación Inazuma»**. | Capa IE1 (ronda 2): 110 registros (76 jugables + 34 de depuración) pasan al nombre oficial (rebanadas FONT8; 22 ya se dibujaban igual), 3 etiquetas de `gmapbase.dat` y 4 selectores de campo copian lo oficial del EU. Quedan pendientes los listados en §1 (6 nombres por anchura, 12 registros que no pueden crecer, mapa del mundo, `fieldinf`, tiendas de la CRO). |
| IE2 (NDS ES) | `evet.pkb` de la NDS española: cada mapa (evento 2504xxxx) trae su clave `mrXXxXX_mn` y su nombre oficial (181/181 eventos, idéntico en Tormenta de Fuego y Ventisca Eterna). | 29 de 182 rótulos son oficiales; 153 no (26 de tienda con sufijo de ciudad, 34 con la planta desplazada, 93 nombres propios o heredados de IE1). | Capa IE2 (ronda 2): los nombres no oficiales pasan al literal de la NDS (314 registros cambian entre las dos versiones; 50 ya se dibujaban igual; ninguno queda pendiente por anchura). |
| IE3 (3DS EU) | Los tres EU de IE3 comparten `eve.pkb`, `ShopName`, `gmap_b` y `vs_stage_select` (sha256 idéntico). | **Ya son el texto oficial EU**: 336 de 337 rótulos (Ogro) y 228 de 229 (Rayo/Fuego) coinciden con el EU por clave estructural; mapa del mundo, selector de campo y ShopName idénticos al EU. | Nada que sustituir. Pendientes: 3 nombres de datos que no caben en el campo japonés (§3). |

La captura 44 es de IE1 **o** de IE2 (la imagen sola no permite distinguirlos): IE1 lo dibuja desde `eve.pkb` evento 83000390 (instrucción 0x4037 argumento 3, clave `稲妻町駅 駅前`; la placa crema es `field_t.arc/ie01_minimap_t_window00` y no lleva texto) e IE2 desde el evento 25041550 (mismo rótulo «Estación», oficial NDS «Estación Inazuma»). Las dos capas lo corrigen, así que la respuesta vale para ambos.

## 1. IE1

### 1.1 Rótulos de mapa jugables (`eve.pkb` 0x4037/3, 73 claves con nombre oficial EU)

«clase»: `oficial` = idéntico al EU; `distinto` = abreviado, recortado, plural/«de» o numeración distinta; `inventado` = palabras que no están en el oficial. «Estado» = resultado de la capa `lugares_oficiales` (IE1).

| k | JP | Build instalada | Oficial EU | Clase | Estado con la capa |
|---|---|---|---|---|---|
| 0 | 正門エリア | Entrada | Entrada principal | distinto | sustituido |
| 1 | テニスコートエリア | Pista de tenis | Pistas de tenis | distinto | sustituido |
| 2 | 野球場エリア | Campo béisbol | Área del pabellón | inventado | sustituido |
| 3 | サークル棟エリア | Zona de clubes | Área de la caseta | inventado | sustituido (salvo 3 registros de eventos que no pueden crecer) |
| 4 | プール・文化棟エリア | Piscina | Act. culturales | inventado | sustituido |
| 5 | 体育館エリア | Gimnasio | Área del gimnasio | distinto | sustituido |
| 6 | 稲妻総合病院 中庭 | Patio hospital | Hospital - Patio | distinto | sustituido |
| 7 | 本校舎１Ｆ | Raimon, pl. 1 | Ed. principal - P. B. | inventado | sustituido |
| 8 | 本校舎２Ｆ ２年教室 | Segundo (pl.2) | Ed. principal - 1.º | inventado | sustituido |
| 9 | 本校舎３Ｆ | Raimon, pl. 3 | Ed. principal - 2.º | inventado | sustituido |
| 10 | 本校舎屋上 | Azotea | Azotea | oficial | ya era oficial |
| 11 | 北校舎１Ｆ | Norte, pl. 1 | Ed. norte - P. B. | distinto | sustituido |
| 12 | 北校舎２Ｆ ３年教室 | Tercero (pl.2) | Ed. norte - 1.º | inventado | sustituido |
| 13 | 北校舎３Ｆ ３年教室 | Tercero (pl.3) | Ed. norte - 2.º | inventado | sustituido |
| 14 | 西校舎１Ｆ | Oeste, pl. 1 | Ed. oeste - P. B. | distinto | sustituido |
| 15 | 西校舎２Ｆ １年教室 | Primero (pl.2) | Ed. oeste - 1.º | inventado | sustituido |
| 16 | 西校舎３Ｆ １年教室 | Primero (pl.3) | Ed. oeste - 2.º | inventado | sustituido |
| 17 | サッカー部室 | Caseta (evento 92010100) | Caseta del club | distinto | NO se toca: evento protegido de «crear partida» |
| 17 | サッカー部室 | Caseta del club | Caseta del club | oficial | ya era oficial |
| 18 | 野球部室 | Club de béisbol | Club de béisbol | oficial | ya era oficial |
| 19 | テニス部室 | Club de tenis | Club de tenis | oficial | ya era oficial |
| 20 | 陸上部室 | Club atletismo | Club de atletismo | distinto | sustituido |
| 21 | サイクリング部室 | Club ciclismo | Club de ciclismo | distinto | sustituido |
| 22 | 体育館裏 スラム | Callejón | Gimnasio - Guarida | inventado | sustituido |
| 23 | 駄菓子屋付近 | Quiosco | Área t. de chuches | inventado | sustituido |
| 24 | 駄菓子屋 | Quiosco | Tienda de chuches | inventado | sustituido |
| 25 | 体育館 | Gimnasio | Gimnasio | oficial | ya era oficial |
| 26 | 相撲部室 | Club de sumo | Club de sumo | oficial | ya era oficial |
| 27 | 柔道場 | Sala de judo | Club de judo | distinto | sustituido |
| 28 | 剣道場 | Sala de kendo | Club de kendo | distinto | sustituido |
| 29 | 漫研＆囲碁将棋部室 | Club manga y go | Manga y ajedrez | distinto | sustituido |
| 30 | 新聞部室 | Club periodismo | Club de periodismo | distinto | sustituido |
| 31 | 水泳部室 | Club natación | Club de natación | distinto | sustituido |
| 32 | プール更衣室 | Vestuario | Piscina - Vestuario | distinto | sustituido |
| 33 | 稲妻総合病院 ２Ｆ | Hospital pl. 2 | Hospital - 1.ª planta | distinto | sustituido (la «ª» se dibuja en la rebanada) |
| 34 | 稲妻総合病院 ３Ｆ | Hospital pl. 3 | Hospital - 2.ª planta | distinto | PENDIENTE: no cabe en 100 px (102 px con el hueco de palabra mínimo) |
| 35 | 稲妻総合病院 １Ｆ | Hospital pl. 1 | Hospital - P. B. | distinto | sustituido |
| 36 | 体育館 裏部屋 ２Ｆ | Anexo, pl. 2 | Trastero superior | inventado | sustituido |
| 37 | 体育館 裏部屋 １Ｆ | Anexo, pl. 1 | Trastero | inventado | sustituido |
| 38 | 鉄塔 | Torre | Torre | oficial | ya era oficial |
| 39 | 河川敷グラウンド | Campo del río | Campo del río | oficial | ya era oficial |
| 40 | 河川敷 | Ribera | Ribera del río | distinto | sustituido |
| 41 | 住宅街 | Zona residencial | Zona residencial | oficial | ya era oficial |
| 42 | 稲妻町駅 駅前 | Estación | Estación Inazuma | distinto | sustituido |
| 43 | 商店街 | Zona comercial | Barrio de tiendas | inventado | sustituido |
| 44 | 商店街アーケード | Calle peatonal | Calle peatonal | oficial | ya era oficial |
| 45 | 商店街倉庫 | Almacenes | Almacén | distinto | sustituido |
| 46 | 商店街 路地裏 | Callejón | Calle de bares | inventado | sustituido |
| 47 | 商店街グラウンド | Descampado | Descampado | oficial | ya era oficial |
| 48 | 鉄塔上 | Torre (cima) | Torre - Plataforma | distinto | sustituido |
| 49 | 商店街 コンビニ | Tienda 24h | Barrio t. - T. 24 h. | distinto | sustituido |
| 50 | スポーツ店 | Tienda deportes | Tienda de deportes | distinto | sustituido |
| 51 | 商店街 薬局 | Farmacia | Barrio t. - Farmacia | distinto | sustituido |
| 52 | プラモ屋 | Tienda maquetas | Tienda de maquetas | distinto | PENDIENTE: no cabe en 100 px (104 px) |
| 53 | 雷雷軒 | Rai Rai | Restaurante Rai Rai | distinto | PENDIENTE: no cabe en 100 px (102 px; con el hueco de palabra de 2 px de la primera versión cabía pero se leía «RestauranteRaiRai») |
| 54 | ゲームショップ | Tienda juegos | Tienda videojuegos | distinto | PENDIENTE: no cabe en 100 px (102 px) |
| 55 | 総合スポーツショップ | Macrodeportes | Macrotienda dep. | distinto | sustituido |
| 56 | メイド喫茶 | Cafetería | Cafetería | oficial | ya era oficial |
| 57 | コンピュータールーム | Informática | Sala de ordenadores | inventado | PENDIENTE: no cabe en 100 px (108 px) |
| 58 | 秘密の倉庫 | Almacén oculto | Almacén secreto | inventado | sustituido |
| 59 | 秘密の小屋 | Cabaña secreta | Caseta | inventado | sustituido |
| 60 | 円堂家 | Casa de Mark | Casa de Mark | oficial | ya era oficial |
| 61 | コンビニ 駅前店 | Tienda 24h | Estación - T. 24 h. | distinto | sustituido |
| 62 | 薬局 駅前店 | Farmacia | Estación - Farmacia | distinto | PENDIENTE: no cabe en 100 px (102 px) |
| 63 | 帝国学園 正面 | Entrada Royal | Royal A. - Entrada | distinto | sustituido (salvo 2 registros de eventos que no pueden crecer) |
| 63 | 帝国学園 正面 | Royal Academy | Royal A. - Entrada | distinto | sustituido (salvo 2 registros de eventos que no pueden crecer) |
| 64 | 帝国学園 通路 | Pasillo Royal | Royal A. - Pasillo | distinto | sustituido |
| 65 | 世宇子グラウンド | Estadio Zeus | Estadio del Zeus | distinto | sustituido |
| 66 | 空中要塞 廊下 | Pasillo | Fortaleza - Pasillo | distinto | sustituido |
| 67 | 空中要塞 控え室１ | Vestuario 1 | F. - Vestuario 1 | distinto | sustituido |
| 68 | 空中要塞 控え室２ | Vestuario 2 | F. - Vestuario 2 | distinto | sustituido |
| 69 | 空中要塞 警備室 | Sala vigilancia | Fortaleza - Control | inventado | sustituido |
| 70 | 空中要塞 総帥室 | Sala de mando | Fortaleza - Mando | distinto | sustituido |
| 71 | イナビカリ 受付 | Recepción | Recepción C.C. | distinto | sustituido |
| 72 | 野生中 | Instituto Wild | Instituto Wild | oficial | ya era oficial |

Totales: oficial 14, distinto 40, inventado 21 (75 pares, 105 registros). Dos claves de la build usan dos nombres (`サッカー部室` «Caseta»/«Caseta del club»; `帝国学園 正面` «Royal Academy»/«Entrada Royal»): el oficial es único.

Notas de la capa (ronda del 2026-11-09, tarde):

- «º» y «ª» **se dibujan de verdad** en la rebanada (letra pequeña de 5x5 px subrayada; `lugares.PROPIOS` del motor): FONT8 no tiene «º» ni «ª» (solo el «°» de 4x4 px), pero el rótulo es una rebanada que dibuja la propia capa, no un glifo del diálogo. Ya no se usa el `°`. Hay que mirarlo en juego (§5).
- El guion «-» del oficial se dibuja como guion corto de 5 px (antes salía el «–» de ancho completo de 9 px).
- **Espacios**: hueco de palabra de 5 px (4 si así comparte baldosas; mínimo 3). FONT8 no tiene espacio de imprenta (solo `8140`, la baldosa vacía de delante): la primera versión dejaba 2-4 px y daba «RestauranteRaiRai».
- **Caja real de IE1**: placa de 165 px (QNA de `field_t.arc`, nodo 11, 3 piezas) y búfer de dibujo de 10 celdas = 100 px (`ina_main1.cro`: `add r5,#0x1500` en 0x7a548/0x7af4c; sin el parche de 16 baldosas; el de 15 baldosas es solo de IE2). **Pendientes por anchura, 6 nombres** (con hueco de palabra 3 y letras normales; el oficial íntegro, sin abreviar): «Estación - Farmacia» (102 px), «Hospital - 2.ª planta» (102), «Restaurante Rai Rai» (102), «Tienda videojuegos» (102), «Tienda de maquetas» (104), «Sala de ordenadores» (108). Con las letras pegadas (hueco 0) caben (88-98 px) pero se funden; pegar solo los pares sin solape de filas alcanzaría para 2 de los 6 con contacto en diagonal: no se aplica. Ensanchar exige parchear la CRO (búfer de 16 baldosas, como IE2/IE3): pregunta en §5.
- **12 registros** de eventos ≥ 90 000 000 o con `%nF` no pueden crecer y conservan su nombre actual (la documentación decía 5; la versión de la mañana, 9): 5 de partida normal (92010510#7, 92104100#3, 92104200#2 «Área de la caseta»; 92031395#66, 92060100#9 «Royal A. - Entrada») y 7 del evento de depuración 91990000 (#2 «Patio principal», #8 «Área del pabellón», #17 «Zona del gimnasio», #29 «Edificio 1 - 3.º», #35 «Edificio 2 - 1.º», #44 «Edificio 3 - 1.º», #47 «Edificio 3 - 2.º»).
- **Cuadre exacto de los 170 registros de IE1** (`informe.json` → `cuadre_de_registros`, comprobado por `validate.py`): 110 cambian al oficial; 22 ya se dibujaban igual; 1 («Azotea», 91990000#32) queda byte a byte como estaba tras recortar (23 sin cambio de dibujo; una versión anterior contaba 22); 12 no pueden crecer; 7 registros pendientes por anchura (6 nombres: «Tienda videojuegos» tiene 2); 15 sin nombre oficial; 1 protegido; 2 vacíos.
- **11 rótulos de IE1 que se cambian pero quedan descentrados**: son de los 4 eventos que no pueden crecer y que, por eso, se recortan (91990000, 92010600, 92011050, 92062100). Para que el cuerpo oficial quepa se quitan baldosas vacías de delante (10 px cada una) y el nombre queda más a la izquierda que el resto: 91990000 #5 (-20 px), #11 (-20), #23 (-30), #26 (-20), #32 (-60, igual que estaba), #38 (-20), #41 (-20), #50 (-10); 92010600#3 «Torre» (-20); 92011050#2 y 92062100#10 «Entrada principal» (-10; pegadas a x=0). El texto sale entero y dentro del búfer; no es un desborde. Sin arreglo posible sin hacer crecer el evento (`informe.json` → `rotulos_descentrados_por_recorte`).
- Evento de depuración 91990000 (63 registros que enumeran mapas): 34 pasan al oficial (así se liberan códigos de FONT8); 15 claves no tienen entrada EU (`病院`, `病院付近`, `稲妻町　コンビニ`, `稲妻町　ショップ２`, `稲妻町　プラモ屋`, `稲妻町　倉庫近辺`, `稲妻町　薬屋`, `空中要塞　グラウンド`, `空中要塞　影山の部屋`, `空中要塞　控え室`, `空中要塞　控え室前`, `空中要塞　通路`, `空中要塞　部屋前`, `野生中　グラウンド付近`, `雷門中　プール付近`) y se quedan como están: no se inventa.

### 1.2 Otras fuentes de nombres de lugar en IE1

| Fuente | Build | Oficial EU | Estado |
|---|---|---|---|
| `logic/gmapbase.dat` idx 5, 6, 7 (registros de 18 B) | «Barrio», «Estac.», «Royal» | «Área r.», «Estación», «Royal A.» | **Sustituido** por la capa IE1 (caben; no se sabe si el juego las muestra: si no, es inocuo). Los 4 primeros ya son oficiales |
| `a_field/gmap_b.arc` textura `name01` | «Zona comercial», «Torre Inazuma», «Raimon», «Ribera», «Residencial» | «Barrio de tiendas», «Torre», «Instituto Raimon», «Ribera del río», «Zona residencial» (2 líneas) | PENDIENTE, cotejado con el EU: `bg01` es idéntico al EU; el **QNA difiere** (mismo tamaño, 202 B / 157 palabras: coordenadas y tamaños de las piezas de los nombres); `name01` es otro arte (naranja de 2 líneas, frente al blanco de 1 línea del instalado) y `map01` difiere en 819 px. Sin «mismo QNA» no se copia; copiar el arc EU entero daría el mapa oficial con el estilo del EU, sin poder probarlo: decisión del usuario |
| `a_game/stage_vs_name_b.arc` (título de campo, p01 256x512) | «Wild», «Brain»… «Solar del barrio», «Almacén secreto» dibujados por el proyecto | **no hay oficial**: el arc del EU es el **japonés** (kanji con furigana), idéntico en es/en/fr/it; el QNA coincide pero no hay arte en español que copiar | PENDIENTE: los nombres del instalado («Solar del barrio», «Almacén secreto», «Ribera») no coinciden con los nuevos del selector |
| `vs_stage_select_04..07` (textura 512x128, sin QNA) | «Estadio Zeus», «Almacén secreto», «Campo de la ribera», «Solar del barrio» | «Campo del Zeus», «Campo del almacén secreto», «Campo de la ribera del río», «Campo del barrio de tiendas» | **Sustituido** por el arte EU (capa IE1). Las otras 9 (01-03, 08-13) ya dicen el texto oficial (solo cambia el trazo) y no se tocan |
| `logic/fieldinf.dat` (44 nombres de campo más un «なし»; campo de 20 B = 10 caracteres de ancho completo) | abreviaturas («Est. Royal», «Ens.Ribera», «P. Torre»…) | «Estadio de la Royal», «Ensayo - Ribera», «Peloteo （Torre）»… (15-20 B) | PENDIENTE: los oficiales miden 10-20 caracteres; en ancho completo solo cabe 1 («Partidillo»), en Latin de 1 byte caben los 44. Falta saber qué función lee el campo (+16 de cada registro de 128 B) y si acepta Latin de 1 byte: exige la CRO (no se toca). El EU 3DS deja `ミニバトル（体育館）` en japonés (reg. 30) |
| `ina_main1.cro` cabeceras del menú de tienda (9 literales) | «Macro dep.», «Maqueta», «Quiosco», «Tienda Raimon», «24h Estación», «Dep.Inazuma», «24h Tiendas», «Juegos», «Furukabu» | «Macrotienda dep.», «Tienda de maquetas», «Tienda de chuches», «Tienda del Raimon», «Estación - T. 24h», «Tienda dep. peq.», «Barrio.t - T. 24h», «Tienda de juegos», «Sr. Veteran» | PENDIENTE (capa `rotulos_oficiales_eu` de menus_cro; no se toca la CRO). Medida indicativa del hueco de ceros que sigue a cada literal: solo «Tienda del Raimon» cabría en ancho completo; la cifra «6 no caben» de la primera versión no se ha podido reproducir (entre 6 y 8 según se cuente el terminador) |
| `logic/schinfo.dat` (institutos, no son lugares) | «Royal Ac.», «Kids FC» | «Royal Academy», «Inazuma Kids FC» | PENDIENTE (caben en 32 B; fuera del alcance «lugares») |

Sin texto de lugar (comprobado): minimapas `ie01_minimap_mr*`, `minimap_t window00` (solo «Objetivo»), `field_select_b`, `field_icon_b`, `field_message_b/t`, `training_f_map_t`, `stage_title_b`, `games.STR`, `mch.pkb`.

### 1.3 Corrección de documentación

`ie1/…/objetivos.py` (v92: «0x4037 sin texto oficial») y `historial/rotulos_objetivos/v76_rotulos_largos/propuesta.md` presentan nombres propuestos por el proyecto como si fueran los del juego: **no lo son**; la fuente canónica es la tabla EU de `code.bin` (arriba).

## 2. IE2 (Tormenta de Fuego y Ventisca Eterna)

182 rótulos de lugar con texto (186 registros, 4 vacíos) en 182 mapas; idénticos en las dos versiones. Oficial 27 + 2 (solo cambia el guion de «Nara - Este/Oeste»), distinto 153. Se sustituyen **los 153** por el literal de la NDS (los oficiales abreviados por la propia NDS se dejan literales: «Entrada R. Academy», «Rec. Nara D. TV», «Campo Mensaj. Estr.», «Aparcam. laboratorio», «C. E. Osakaland»; a «Entrada Nara D. TV » se le quita el espacio final; «Casa Terror （p. sup.）» conserva el paréntesis de ancho completo). Los 84 nombres oficiales caben en el rótulo ampliado (≤ 15 baldosas, 150 px): con el hueco de palabra real el más ancho mide 110 px; ninguno queda pendiente por anchura. La placa de IE2 mide 239 px (QNA de `field_t.arc`, nodo 11, 5 piezas, comprobado en el archive instalado) y el búfer ampliado está en la CRO del paquete v3 (`add r5,#0x3e00` en 0x8a67c; no comprobado en el PC).

Errores objetivos de la build (no solo estilo): numeración de plantas desplazada (34 registros: «Laboratorio pl. 2» donde el oficial es «Laboratorio P1»; «Hospital pl. 3» → «Hospital P2»), sufijo de ciudad en las tiendas (26 registros: «Mercazuma - Nara» → «Mercazuma»; el título de la ventana de tienda, `ShopName.dat`, sí lleva ciudad y ya es oficial) y nombres sin base oficial («Zona residencial», «Zona comercial», «Descampado», «Callejón», «Junto a las vías», «Camino perdido», «Cueva del confín»).

Lista de los que NO eran oficiales (build → oficial NDS) y que la capa sustituye:

| Build | Oficial NDS ES | Mapa |
|---|---|---|
| Patio hospital | Hospital | mr01b07 |
| Hospital pl. 3 | Hospital P2 | mr01i27 |
| Ribera | Ribera del río | mr02b04 |
| Zona residencial | Calle de Mark | mr02b05 |
| Estación | Estación Inazuma | mr02b07 |
| Zona comercial | Barrio de tiendas | mr02b08 |
| Almacenes | Almacén | mr02b10 |
| Callejón | Calle de bares | mr02b11 |
| Descampado | Campo barrio tiendas | mr02b12 |
| Torre (cima) | Torre - Plataforma | mr02b13 |
| Mercazuma - Inazuma | Mercazuma | mr02i01 |
| Balón Bazar - Inazuma | Balón Bazar | mr02i02+ |
| Tienda maquetas | Tienda de maquetas | mr02i04 |
| Rai Rai | Restaurante Rai Rai | mr02i05 |
| Tienda juegos | Videojuegos | mr02i06 |
| Informática | Sala ordenadores | mr02i09 |
| Almacén oculto | Almacén secreto | mr02i10 |
| Cabaña de la torre | Caseta | mr02i11 |
| Mercazuma - Estación | Mercazuma | mr02i13 |
| Todotécnicas - Estación | Todotécnicas | mr02i99 |
| Pasillo Royal | Entrada R. Academy | mr03i01 |
| Puerta Raimon | Entrada del Raimon | mr07b01+ |
| Caseta del club | Área de la caseta | mr07b02+ |
| Puerta Nuevo Raimon | Nuevo Raimon | mr07b03 |
| Cámara subterránea | Búnker presidente | mr07i01 |
| Cuarto de Mark | Habitación Mark | mr07i02 |
| Hospital pl. 2 | Hospital P1 | mr07i03 |
| Pasillo subterráneo | Pasillo del búnker | mr07i06 |
| Deerfield 1 | Parque Deerfield | mr09b01 |
| Deerfield 2 | Estatua P. Deerfield | mr09b02 |
| Entrada Nara Deer TV | Entrada Nara D. TV | mr09b05 |
| Todotécnicas - Nara | Todotécnicas | mr09i01 |
| Mercazuma - Nara | Mercazuma | mr09i02 |
| Balón Bazar - Nara | Balón Bazar | mr09i03 |
| Azotea Nara Deer TV | Tejado Nara D. TV | mr09i04 |
| Vestíbulo Nara Deer TV | Rec. Nara D. TV | mr09i05 |
| Campo del Alpino | Campo Alpino | mr10b02 |
| Hokkaido este | Calle Nevada este | mr10b03 |
| Hokkaido O | Calle Nevada oeste | mr10b04 |
| Todotécnicas/Mercazuma/Balón Bazar - Hokkaido | solo nombre de tienda | mr10i01 |
| Entrada Claustro Sagrado | Entrada del Claustro | mr11b01 |
| Claustro Sagrado | Claustro | mr11b02 |
| Avenida de Kioto | Calle Principal Kioto | mr11b03 |
| Callejón este | Calle Este Kioto | mr11b04 |
| Callejón oeste | Calle Oeste Kioto | mr11b05 |
| Todotécnicas/Mercazuma/Balón Bazar - Kioto | solo nombre de tienda | mr11i01 |
| Ehime oeste | Calle Oeste Ehime | mr12b03 |
| Ehime este | Calle Este Ehime | mr12b04 |
| Royal Academy Redux | R. Academy Redux | mr12b05 |
| tiendas - Ehime | solo nombre de tienda | mr12i01 |
| Entrada Osakaland | Entrada | mr13b01 |
| Atracciones | Atracción Osakaland | mr13b03 |
| Osaka zona comercial | Barrio de tiendas | mr13b05 |
| tiendas - Osaka | solo nombre de tienda | mr13i01 |
| Desván Casa del Terror | Casa Terror (p. sup.) | mr13i05 |
| Instituto Fauxshore | Fauxshore | mr14b01 |
| Junto a las vías | Centro Luckyhill | mr14b02 |
| tiendas - Luckyhill | solo nombre de tienda | mr14i01 |
| Instituto Mary Times | Mary Times | mr15b01 |
| Azotea del faro | Parte superior faro | mr15b04 |
| tiendas - Okinawa | solo nombre de tienda | mr15i01 |
| Faro, pl. 1 | Faro PB | mr15i05 |
| Cuarto del faro | Casa del faro | mr15i06 |
| Camino al laboratorio | Camino laboratorio | mr16b02+ |
| Sala Piedra Alius | Cámara Piedra Alius | mr16i05+ |
| Campo de los Mensajeros | Campo Mensaj. Estr. | mr16i06 |
| Aparcamiento | Aparcam. laboratorio | mr16i07 |
| Laboratorio pl. 1 | Laboratorio PB | mr16i10+ |
| Laboratorio pl. 2 | Laboratorio P1 | mr16i13+ |
| Laboratorio pl. 3 | Laboratorio P2 | mr16i20+ |
| Laboratorio pl. 4 | Laboratorio P3 | mr16i30+ |
| Camino perdido | Laberinto del bosque | mr16b20+ |
| Cueva del confín | Cueva del bosque | mr16b40 |
| Centro de entrenamiento | C. E. Osakaland | mr17d00 |

(Las líneas «solo nombre de tienda» de Hokkaido, Kioto, Ehime, Osaka, Luckyhill y Okinawa son las 26 tiendas con sufijo de ciudad.)

### 2.1 Otras fuentes IE2

- `logic/ShopName.dat`: 36 nombres de tienda, coinciden con la NDS (solo el guion). Nada que hacer.
- `logic/fieldinf.dat`: 11 campos con abreviaturas propias y 7 «Peloteo (…)» oficiales en la NDS (ids 25-29, 43, 44) que siguen en japonés; el oficial no cabe en 10 caracteres de ancho completo. PENDIENTE (mismo bloqueo que IE1); 78 registros más siguen en japonés también en la NDS: sin oficial, no se inventa.
- `gmapbase*.dat`: la NDS los trae en inglés de desarrollo, no es texto oficial ES; probablemente no se muestran. PENDIENTE de confirmar en juego.
- `schinfo.dat` (escuelas): 11 abreviaturas propias («Royal», «Géminis», «Claustro»…) frente al oficial largo. No son lugares; PENDIENTE.
- Texturas `gmap_b name01/02` («Emisora de TV», «Bosque del monte Fuji», «Laboratorio M. de las Estrellas»…), `stage_vs_name_b` («Solar del barrio», «Centro Osakaland» dudosos): origen sin verificar, PENDIENTES. Quedan incoherentes con los rótulos nuevos («Zona residencial» en el mapa frente a «Calle de Mark» en el rótulo): se decide con el usuario.

## 3. IE3

Rótulos de lugar (Ogro 337 con texto, Rayo/Fuego 229), texturas del mapa del mundo (`gmap_b`, 25 arcs), selector de campo (31) y `ShopName.dat` (65 líneas): **idénticos al texto oficial EU**; ningún nombre es generado. Los 170 nombres JP→ES de la tabla 0x4037 se han vuelto a comprobar contra el `eve.pkb` EU del Ogro (170/170 existen) y 284 de 337 rótulos instalados se dibujan píxel a píxel como la tira oficial (los 53 restantes difieren en la colocación de ±4 px de la tira ampliada, no en el texto). **Pendientes** (el oficial no cabe en el campo de datos japonés; Norma 3 prohíbe condensar):

| Dato | Japonés | Oficial EU | Motivo |
|---|---|---|---|
| `BinderData_AREA.dat` 0x324, `clubinfo.dat` 0x2c0 | ヤマネコ島 | Isla del Gato Montés | 20 car.; el campo admite 19 B (BinderData) / 18 B (clubinfo) |
| `BinderData_AREA.dat` 0x384, `clubinfo.dat` 0x320 | ウミガメ島 | Isla de la Tortuga Marina | 25 car. |
| `clubinfo.dat` 0x1a0 | イギリスエリア | Área de Inglaterra | 19 B frente a 18 |

También pendientes (no son lugares; otro flujo, «japonés residual IE3»): 60 títulos de BGM (16 con nombre de lugar), 20 nombres de copa `TournamentName01-16`, `stage_select_b.arc` (bg09/button03), `stage_title_b` p02 y las abreviaturas propias de títulos de pachanga/copa («Torneo esp. del detective Smith» frente al EU «Torneo especial del detective Smith»). Ningún nombre de lugar vive en los literales del CRO.

## 4. Qué hacen las capas (resumen técnico)

- **Método**: el nombre oficial se dibuja una vez con las letras nativas de FONT8 (1 px entre núcleos; 5/4/3 px entre palabras; «º», «ª» y «-» dibujados en la propia rebanada), se centra en la placa (100 px; 150 px en IE2 para nombres de 11-15 baldosas) con una holgura de 4 px para compartir baldosas entre nombres, y se corta en baldosas de 10 px; cada baldosa es un código de 2 B del texto del rótulo (rebanada). No se cambia caja, codificación, espaciado de diálogos ni CRO. **Sí se cambia la fuente**: 193 glifos de rebanada de `font/FONT8.bcfnt` (ver abajo): excepción a la regla «no cambiar fuentes» **aprobada por el usuario el 2026-11-09** («Sí, apruebo»; el bloqueo `dialogue_lock.py` no se toca). Motor común: `work/shared/capas/lugares_oficiales_motor`.
- **Códigos**: la reserva de 1366 rebanadas estaba agotada. Los rótulos viejos de IE1 e IE2 dejan de usar sus códigos al pasar a oficiales; 193 de esos códigos se reescriben en `font/FONT8.bcfnt` (solo píxeles y CWDH; CMAP y hojas intactos; la primera versión reescribía 264). Quedan 85 libres. El espaciado más ancho de la ronda 2 multiplicó la demanda (415 baldosas distintas con la colocación centrada fija); la holgura de posición de 4 px y elegir entre 5 y 4 px de hueco de palabra la baja a 193. Por eso IE1, IE2 y la capa de fuente **se instalan juntas**. Ningún código que use un rótulo de IE3 se reescribe: la validación redibuja los 694 rótulos no tocados de los cinco `eve.pkb` con el FONT8 nuevo y compara píxel a píxel.
- **Excepción de tipografía (aprobada el 2026-11-09)**: la regla del proyecto es «no cambiar caja, fuentes, codificación». Esta entrega toca solo los **píxeles y el CWDH (-1,10,8) de 193 glifos de rebanada** de `FONT8.bcfnt` (códigos que ya eran rebanadas de rótulo en la reserva `ie2_rotulos_completos`, no letras ni kanji de diálogo); CMAP, hojas, tamaño y letras nativas quedan igual, y no se tocan los ficheros congelados de `dialogue_lock` (el FONT8 instalado ya difiere del hash congelado por las capas de rebanadas anteriores). Aun así es un cambio de fuente (el usuario aprobó la cifra de la versión de la mañana, 264; esta versión reescribe 193, menos de lo aprobado): el usuario lo aprobó el 2026-11-09 y el bloqueo sigue sin tocar. Escaneo (versión de la mañana, 264 códigos): ninguna de las 135 secuencias antiguas de rótulo (≥ 6 B) aparece en otra entrada del `archive.fa` instalado que no sea el `eve.pkb` de IE1/IE2 que la propia capa reescribe; **no repetido** para los 27 códigos de la versión actual que no estaban en aquella. Disjunción comprobada con las demás capas que entregan FONT8 (0 glifos comunes con las 4 capas IE2 ni con `fuente_latina_occidental_prueba`; las variantes `*_con_lugares` de esta última están obsoletas y hay que regenerarlas). Registro: los 264 códigos ya figuran en `registro.json` (origen `ie2_rotulos_completos`), por lo que ninguna capa puede asignarlos como libres; el estado nuevo de cada uno está en `work/shared/capas/lugares_oficiales_fuente/registro_codigos.json` (superposición; no se edita el registro de la capa ajena).
- **Verificación sin emulador**: reproducibilidad byte a byte, sincronía `usearch` (`sincronia_usearch verificar` = 0 sobre la copia fundida), guardias de congelados y suite de tests. Nada probado en juego.

## 5. Preguntas para la prueba del usuario

1. IE1, entrar en la estación: ¿el rótulo dice «Estación Inazuma», entero, centrado y sin recorte en la placa crema?
2. IE1, instituto Raimon, edificio principal (planta baja, 1.º y 2.º): ¿se lee «Ed. principal - P. B.», «… - 1.º», «… - 2.º» con la «º» pequeña y subrayada (ya no el punto cuadrado `°`)? Igual en «Hospital - 1.ª planta».
3. IE1, tiendas y barrio comercial: «Barrio de tiendas», «Calle de bares», «Tienda de chuches», «Caseta»: ¿sin glifos raros ni letras cortadas?
4. IE1, pantalla de selección de campo: ¿«Campo del Zeus», «Campo del almacén secreto», «Campo de la ribera del río», «Campo del barrio de tiendas» se ven enteros?
5. IE2 (Tormenta o Ventisca): «Laboratorio PB/P1/P2/P3», «Hospital P1», una tienda sin ciudad («Mercazuma»), «Estatua P. Deerfield» (15 baldosas): ¿rótulo completo y dentro de la placa?
6. IE3: «Estadio Monumental», «Centro de entrenamiento», «Laberinto del bosque»: ¿siguen igual que antes (no deben cambiar)? Cualquier letra distinta aquí indicaría un código reasignado mal.
7. IE1: ¿el evento 91990000 (lista de depuración de mapas) es alcanzable en una partida normal? Si no lo es, sus registros no necesitaban cambio.

8. ~~Excepción de tipografía~~: **aprobada por el usuario el 2026-11-09**.
9. **Decisión nueva (IE1)**: 6 nombres oficiales no caben en las 10 baldosas (100 px) con un espacio legible («Estación - Farmacia», «Hospital - 2.ª planta», «Restaurante Rai Rai», «Tienda de maquetas», «Tienda videojuegos», «Sala de ordenadores»). ¿Se parchea la CRO de IE1 (búfer de 16 baldosas, como IE2/IE3) o siguen con el nombre actual?
10. **Decisión nueva (mapa del mundo)**: el `gmap_b.arc` oficial del EU (QNA distinto) no se copió. ¿Se copia entero (nombres oficiales con el estilo naranja del EU) o se deja la mezcla actual?
11. IE2: el centrado asume una placa de 165 px y la de IE2 mide 239: ¿los nombres cortos se ven bien o se recentran a 119,5 px?
12. IE1: «Torre» (subida a la torre) y «Entrada principal» (92011050 / 92062100): ¿se leen enteras aunque algo más a la izquierda que las demás? (son los rótulos recortados).
