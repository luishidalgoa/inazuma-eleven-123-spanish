# IE3 (Amenaza del Ogro): japonés y texturas que quedan — lista única para «¿hay más?»

Actualizado 2026-10-31 (ronda 2 de nombres/Fichar) y 2026-11-09 (ronda 4: correcciones de §1.1-§1.3; corrección 2: +10 literales y barrido con motivo individual). Análisis **estático**: nada de esto está probado en el juego. Orden: de más a menos visible sin Wi-Fi.
Solo se citan literales cortos y desplazamientos (Norma 2: no se copia contenido extraído).

Leyenda: **[hecho]** = ya corregido en una capa construida (sin instalar); **[pend]** = sin corregir (motivo); **[muerto]** = el código no lo lee.

## 1. CRO `ina_main3ogre.cro` (literales Shift-JIS)

Barrido de la corrección 2 de la ronda 4 (2026-11-09, estático; `menus_cro/fichar_literales_eu/barrido_referencias.py` → `barrido_referencias.json`, una fila por cadena con su motivo): **321 cadenas con ≥ 3 kana** = 64 traducidas por `fichar_literales_eu` (las 67 escritas menos 3 de 1-2 kana), 18 sin texto oficial (el EU deja el mismo japonés), 153 pendientes con motivo individual (72 sin gemela EU ≥ 0,78; 51 con gemela pero sin emparejamiento ordinal exacto; 2 que no caben; 9 que la capa rechaza por espacio y recoge `literales_cueva_eu`; 19 con motivo propio: decisión del usuario, nivel B, dato asociado), 24 solo con relocación (punteros de tabla) y 62 sin ninguna referencia (rótulos muertos, colas de textos pisados). Las cifras anteriores («355 = 56+180+71+48», «unas 34 con id demostrado») usaban otro filtro y NO se mantienen. Con el criterio de la capa no queda ninguna cadena con referencia que lo cumpla y no esté escrita.
Criterio de «referencia»: `add/sub rX,pc,#imm` (también condicionales `addeq/addne`), `ldr [pc,#imm]` (también `ldrne`) hacia una palabra con relocación, relocaciones, arrays de puntos de paso fijo. «Sin referencia» NO equivale a «muerto» en una función con ramas condicionales ni en un array de paso fijo (`base + idx·64/128`).

### 1.1 Visibles en juego (sin red)

| Prioridad | Pantalla | Literales | Estado |
|---|---|---|---|
| Alta | Fichar/Contactos (capturas 22-24) | `0x213a38`, `0x2139f0`, `0x213a14`, `0x2aea4c`, `0x2ae26c`, `0x2ccd5d`, `0x2cccf4`, `0x2ae824` | **[hecho]** `menus_cro/fichar_literales_eu` (ronda 1) |
| Alta | Equipo/Jugadores, Formación, Selección de equipo/campo/uniforme, guardar y terminar, técnicas, tienda, recuperación PE/PT, Cápsulas, Fichaje/Objetos del Ogro | 40 literales (ids EU 38, 68-71, 153-156, 164-166, 173, 178-180, 190-193, 233-235, 348, 510, 522, 524, 575, 577, 578, 758, 759, 766, 848-854, 862) | **[hecho]** ronda 2 de la misma capa (README, tabla) |
| Alta | Cápsulas `0xdd8e8` «ざんねん！%s だった。» (EU 585, 56 B) | no cabe en 23 B y se carga con `add pc` | **[construido, NO entra en el paquete]** `menus_cro/literales_cueva_eu` (stub en `0x29bf00`; opcional, desactivada por defecto: sigue en japonés en el juego) |
| Alta | Jugadores/CharaSelect `0x1d8774`, `0x93ba4` «despedir» (EU 146, 41 B en 31 B) y `0x2b13b4`, `0x2b2940` (EU 147, 44 B en 33/31 B), `0x2b250c` «tirar» (EU 158) y `0x2b1960` (EU 517) | no caben; `0x1d8774` y `0x93ba4` (`add pc`) con stub; `0x2b13b4`, `0x2b2940`, `0x2b250c`, `0x2b1960` (pool+relocación) reapuntados a rótulos japoneses muertos | **[construido, NO entra en el paquete]** `menus_cro/literales_cueva_eu` (opcional; sigue en japonés en el juego) |
| Media | Tienda `0x7ac90` (EU 401, 28 B en 19 B), `0x7aee4` (EU 402, 28 B en 23 B) | no caben | **[construido, NO entra en el paquete]** `literales_cueva_eu` (stub; sigue en japonés en el juego) |
| Media | Cápsulas `0xdce88` «この音…レアがきたぞ！» (EU 583, 33 B en 31 B) | pegado a una palabra de código | **[construido, NO entra en el paquete]** `literales_cueva_eu` (stub; sigue en japonés en el juego) |
| Media | Fichaje del Ogro `0x2b6840` (EU 852, 27 B en 22 B) | no cabe; pool+relocación | **[construido, NO entra en el paquete]** `literales_cueva_eu` (reubicación; sigue en japonés en el juego) |
| Alta | Fin de partido `0x1ffb88` (EU 432), `0x1ffbb0` (433), `0x2b6034` (434) y edición de perfil `0x20c544` (696), `0x20c56c` (697) | tenían referencia (`addeq/addne`, `ldrne`+relocación); identidad por gemela y ejecución diferencial | **[hecho]** `fichar_literales_eu` (ronda 4) |
| Media | `0xb7b44` (181, reglas), `0xd0068` (856, ya en el equipo), `0x1dad40` (571, «Equipo»), `0x123940` (710) | referencia por `add pc`; gemela ≥ 0,78 | **[hecho]** `fichar_literales_eu` (ronda 4) |
| Media | Comunicación local / inalámbrico: `0x653d8` (632), `0x653f8` (643), `0x9f300` (611), `0x2b4ec4` (580, mismo texto que 181), `0x2b88cc` (859, teclado), `0x2b4a10` (579), `0x2b906c` (689), `0x2b9028` (617), `0x86dd0` y `0x87864` (331, código de error; `%d`→`%s`) | referencia de código; gemela 0,86-0,98 con emparejamiento ordinal exacto; ES oficial sin kana; caben | **[hecho]** `fichar_literales_eu` (ronda 4, corrección 2): un revisor demostró que cumplían el criterio y estaban bajo «baja visibilidad» |
| Media | `0xd0048` (855), `0xd008c` (857), `0x68380` (647) | no caben; `add pc`; piden el «modo rodata» de `cuevas_pc` (apuesta no probada) | **[pend]** |
| Media | `0x19a7d8` (761), `0x19a83c` (760), `0x2b15cc` (245), `0x1c7790` (693), `0x1c77b0` (694), `0x68368` (644), `0x68348` (632) | identidad solo de nivel B (semejanza de mnemónicos 0,56-0,57; `0x68368` sin vecindad demostrada) | **[pend]** pregunta al usuario |
| Media | `0xd02b0` (858) | el EU 858 lleva `%s` (su código sí pasa un argumento) y el sitio JP deja `r2 = 0x40`, no un puntero a cadena: traducirlo tal cual leería `0x40` como puntero | **[pend]** no traducir tal cual (hace falta una solución específica) |
| Media | Teclado de nombre `0x2ce658` (idéntico byte a byte al EU), `てんま` (`0x2b7b78`, el EU lo deja igual), `なし` `0x2405f8` y `エラー` `0x26c7cc` (claves de `STD_CompareString`, no texto) | nada que traducir en el CRO | **[sin acción]** |
| Media | `カップ` (`0x1c64dc`, `0x23c870`, `0x2b3e84`) y `%sカップ` (`0x23e4e8`) | el EU usa `GetString(752)` = un ESPACIO; el efecto depende de `TournamentName*.dat` (japonés) | **[pend]** traducir junto a esos datos |
| Media | `0x70d24` «…がチームをさることになった。» (EU 42 «%s ha dejado el equipo.») | el JP no lleva `%s` (el nombre se antepone con concat): quitar el `%s` es una derivación | **[pend]** pregunta al usuario (literal « ha dejado el equipo.», 21 B en 31) |
| Baja | Contraseñas (`PasswordIssue`, `0x22eef0`, `0x22f290`; EU 699/700) y Mistorene/Escaba/Cañón Dios (`0x12350c`, `0x12353c`, `0x12356c`, `0x1235a8`, `0x1235cc`, `0x1235f0`, `0x123928`, `0x2b7a54`, `0x2b7ac0`, `0x2b7b08`; EU 701-709, 711) | el EU deja el MISMO japonés (comprobado carácter a carácter): no hay texto oficial | **[sin texto oficial]** |

### 1.2 Huérfanos de verdad (el código no los lee) y corrección de la ronda 3

Sin ningún mecanismo de referencia (ni `add/sub rX,pc,#imm`, ni `ldr [pc]` a una palabra con relocación, ni relocación, ni array de paso fijo, ni interior): rótulos de estadísticas `0x2cd210-0x2cd248` (ボディ, キック, ガッツ, ガード, スピード, スタミナ, ＧＰ, ＴＰ, コントロール), del menú `0x2cd37c-0x2cd52f` (アイテム, ひっさつわざ, そうび, わかれる, …),
`0x2aea04`/`0x2aea20` (el código ya apunta a las versiones ES `0x2cd873`/`0x2a40f0`) y 10 colas de textos que una capa anterior pisó. En total ~70 cadenas sin referencia demostrable (62 con ≥ 3 kana en el barrido de la corrección 2; casi todas en rodata junto a vecinas ya referenciadas que apuntan al español; 8 existen también sin uso en la CRO EU). Los textos de la ficha («Tiro», «Rapidez»…) son TEXTURAS EU (`status_t`), no estos literales.

**Corrección (2026-11-09).** La versión anterior de este apartado decía que `0x1ffb88`, `0x1ffbb0`, `0x1c9820`, `0x1c9848`, `0x20c544`, `0x2b6034` (y, por extensión, `0x20c56c`, `0x1c980c`) no tenían «ninguna `add pc`/`ldr [pc]` (ni en dos pasos) ni relocación». Era **falso**: todos tienen referencia de código y son alcanzables. Causa: el extractor solo contaba `add`/`ldr` incondicionales y las instrucciones condicionales (`addeq fp,pc,#0x160` en `0x1ffa20`; `addeq fp,pc,#0x16c` en `0x1ffa3c`; `ldrne fp,[pc,#0x19c]` en `0x1ffa38` → palabra reubicada `0x1ffbdc` → `0x2b6034`; `addeq r8,pc,#0x268`/`addne r8,pc,#0x28c` en `0x20c2d4`/`0x20c2d8`; `addeq r5,pc` en `0x1c9698`, `0x1c96a4`, `0x1c96b0`) se descartaban. Confirmado ejecutando la CRO real con unicorn (función `0x1ff710` con `[this+0xc]` = 9, 10 y 10 con `0x158f34()≠0`; `0x20c058` con `[this+0xe]` = 2 y 3; `0x1c9580` con `[this+0xd]` = 8, 9 y 10). Cinco de ellos ya están traducidos (`fichar_literales_eu`, ronda 4); `0x1c9820`, `0x1c9848` y `0x1c980c` (flujo de torneos por StreetPass, función `0x1c9580` sin gemela EU) quedan pendientes por identidad.
**Lección**: antes de declarar «muerto» un literal hay que buscar también las formas condicionales (`add<cc>`, `ldr<cc>`), y no confiar en que «sin referencia» sea «muerto» (`docs/FURIGANA_LECCIONES.md`).

### 1.3 Red / Wi-Fi / intercambio (baja visibilidad: funciones deshabilitadas o raras en esta compilación)

**Corrección**: la versión anterior hablaba de «~95 cadenas Wi-Fi en `0x217b8-0x2b96f8`», un rango demasiado amplio que escondía literales vivos y visibles sin sitio en ningún documento (`0xd0048`, `0xd0068`, `0x12350c`…, `0x19a7d8`, `0x19a83c`, `0x22eef0`, `0x22f290`, `0x1c7790`, `0x1c77b0`, `0xb7b44`, `0x1dad40`, `0x1cc8c0`, `0x68368`; todos reclasificados arriba). Son cadenas vivas raras (red, Wi-Fi, StreetPass, intercambio, enlace con otro juego; la cifra «180» de la ronda 4-A era aproximada y no se mantiene: ver el barrido de arriba), agrupadas por función:

| Offsets (mín-máx) | n | Función | Pantalla probable |
|---|---|---|---|
| `0x8f28`-`0x8f34` | 2 | `0x8ac4` | StreetPass: descarga de equipos (すれちがい) |
| `0x21774`-`0x2b96f8` | 15 | `0x215e0` | Wi-Fi: errores de conexión / servicio terminado |
| `0x4f558`-`0x4f564` | 2 | `0x4f228` | datos de prueba: nombres sin sentido, idénticos en el EU |
| `0x51d30`-`0x51d30` | 1 | `0x51c88` | rótulo «はいし» en función sin ruta estática |
| `0x6476c`-`0x6476c` | 1 | `0x64590` | Cooperación con Spark/Bomber (comunicación local) |
| `0x649b0`-`0x64a0c` | 3 | `0x647b0` | Comunicación local: corte / límite de conexiones |
| `0x653d8`-`0x653f8` | 2 | `0x650e8` | Comunicación local: confirmar equipo y esperar **[hecho]** |
| `0x682e8`-`0x2a33c4` | 17 | `0x67a9c` | Menú de comunicación local / intercambio de equipos |
| `0x86dd0`-`0x86dd0` | 1 | `0x86b6c` | Diálogo de error con código **[hecho]** |
| `0x87864`-`0x87864` | 1 | `0x875fc` | Diálogo de error con código **[hecho]** |
| `0x97264`-`0x97264` | 1 | `0x97108` | Intercambio: faltan puntos de amistad (función sin ruta) |
| `0x97920`-`0x2a25fc` | 5 | `0x97604` | Intercambio: motivos por los que no se puede intercambiar |
| `0x9f300`-`0x9f300` | 1 | `0x9f06c` | Comunicación cortada **[hecho]** |
| `0xa1378`-`0xa1394` | 2 | `0xa1088` | Wi-Fi / comunicación: corte |
| `0xa1c8c`-`0x2b8bbc` | 11 | `0xa1af8` | Wi-Fi: descarga de datos (A) |
| `0xa2b68`-`0xa2b98` | 2 | `0xa2880` | Wi-Fi: interrupción de la comunicación |
| `0xa352c`-`0x2a3f74` | 12 | `0xa3398` | Wi-Fi: descarga de datos (B) |
| `0xe77b8`-`0xe77e0` | 2 | `0xe752c` | Comunicación local / modo secreto |
| `0xe7b34`-`0xe7b68` | 2 | `0xe7818` | Comunicación local: conexión |
| `0xe846c`-`0xe84c4` | 3 | `0xe828c` | Comunicación local: conexión (oculto) |
| `0x1216f0`-`0x121c20` | 3 | `0x12121c` | Comunicación local: conectar / sin destino / cortada |
| `0x12350c`-`0x2b7b08` | 11 | `0x123334` | Minijuego de preguntas Mistorene/Escaba/Cañón Dios (el EU conserva el  |
| `0x146f30`-`0x147d90` | 11 | `0x146a28` | Intercambio de jugadores |
| `0x1836e8`-`0x1836f4` | 2 | `0x183538` | StreetPass: textos |
| `0x1bac5c`-`0x2b8e30` | 2 | `0x1baa0c` | Carné/tabla: pregunta (el EU conserva el japonés) |
| `0x1bbe60`-`0x1bbe60` | 1 | `0x1bbac4` | Recepción de datos |
| `0x1bc29c`-`0x1bc29c` | 1 | `0x1bbe7c` | Datos recibidos de otro jugador |
| `0x1c7790`-`0x1c77b0` | 2 | `0x1c7188` | Equipos recibidos (StreetPass/Wi-Fi) |
| `0x1c980c`-`0x1c9848` | 3 | `0x1c9580` | Torneos recibidos: confirmar / guardar y terminar / salir sin guardar  |
| `0x1cc81c`-`0x2b81c0` | 11 | `0x1cc3dc` | Actualización de torneos por Wi-Fi/StreetPass |
| `0x22eef0`-`0x22f290` | 2 | `0x22e728` | Contraseña: emitir (el EU conserva el japonés) |
| `0x26c7c0`-`0x26c7cc` | 2 | `0x26c1bc` | datos de prueba / depuración (ScoutSpCode) sin ruta estática |
| `0x2a258c`-`0x2a25dc` | 4 | `0x97ae8` | Intercambio: texto de espera animado |
| `0x2a2640`-`0x2a2640` | 1 | `0x9c210` | Intercambio: inicio |
| `0x2a2c44`-`0x2a2c44` | 1 | `0x15a618` | Partido por comunicación: elegir COM |
| `0x2a3940`-`0x2a3940` | 1 | `0x5f3c0` | Enlace con otro juego: elegir datos a vincular |
| `0x2b48ec`-`0x2b4968` | 2 | `0x18d114` | Partido por comunicación: conexión |
| `0x2b4a10`-`0x2b4a10` | 1 | `0x18d2a4` | Partido por comunicación: equipo insuficiente **[hecho]** |
| `0x2b4b2c`-`0x2b4bdc` | 2 | `0xfc37c` | Enlace con Inazuma Eleven 2: datos recibidos |
| `0x2b4e88`-`0x2b4e88` | 1 | `0xb8260` | Partido por comunicación: espera |
| `0x2b4ec4`-`0x2b4ec4` | 1 | `0xb63e0` | Partido por comunicación: elegir reglas **[hecho]** |
| `0x2b4eec`-`0x2b4eec` | 1 | `0xb6a90` | Partido por comunicación: confirmar reglas |
| `0x2b69a8`-`0x2b69a8` | 1 | `0x1f5078` | Partido por comunicación: espera elección de campo |
| `0x2b6b7c`-`0x2b6b7c` | 1 | `0x1c3804` | Partido por comunicación: espera a que el rival elija equipo |
| `0x2b6d34`-`0x2b6d34` | 1 | `0x2029b8` | Partido por comunicación: espera elección de uniforme |
| `0x2b8210`-`0x2b8210` | 1 | `0x1caaf0` | StreetPass: torneos |
| `0x2b871c`-`0x2b8764` | 2 | `0x20b374` | Enlace con Spark/Bomber: fichajes/objetos especiales |
| `0x2b8c10`-`0x2b8c10` | 1 | `0xa13cc` | Wi-Fi / comunicación: conexión |
| `0x2b9028`-`0x2b9028` | 1 | `0x1bc400` | Nombre y escudo para partidos por comunicación **[hecho]** |
| `0x2b906c`-`0x2b906c` | 1 | `0x1bc2a8` | Datos recibidos: guardar **[hecho]** |
| `0x2cd48f`-`0x2cd49f` | 3 | `?` | Órdenes del capitán (がんばれ/まもれ/せめろ): sus usuarios no tienen ruta |
| `0x2cdc84`-`0x2ce3d1` | 16 | `?` | Menú de enlace/Wi-Fi: descripciones |

Notas: las 4 funciones sin ruta estática desde la entrada (`0x4f228`, `0x51c88`, `0x97108`, `0x26c1bc`) y el bloque de órdenes `0x2cd48f-0x2cd49f` son probablemente código muerto. El EU de Nintendo Network no coincide con la redacción Wi-Fi JP (ids 0-31 y 670-671 solo orientativos). **Corrección 2.** La versión anterior de esta nota decía que «unas 34» de estas cadenas tendrían id EU demostrado y cabrían y las dejaba sin tratar «por su baja visibilidad». Ese motivo no vale con la autorización «traducir el texto japonés que queda». Repetido el barrido con el criterio exacto de la capa, cumplían todo 10 (marcadas **[hecho]** arriba y en §1.1); de las demás, cada una tiene su motivo individual en `barrido_referencias.json`: p. ej. la función de intercambio `0x146a28` (14 literales JP frente a 12 llamadas EU) y la de motivos de intercambio `0x97604` (14 frente a 6) NO tienen emparejamiento ordinal exacto, así que su id no está demostrado; `0x51d30` (EU 320) mide 8 B en 7 B y su función no tiene ruta estática; `0x6476c` (EU 612) mide 99 B en 63 B. Los casos «misma gemela, distinto número de literales» (51) son una pregunta al usuario (¿se acepta un emparejamiento aproximado por vecindad de bloques?): no se hace sin su respuesta.

## 2. Texturas con japonés o recortadas (QNA japonés con píxeles EU)

Verificado en la ronda 2 (píxeles instalados frente a EU, partes del QNA): `connection_b` → **[hecho]** `graficos/contactos_mensajes_eu` (`mes_b01`, 8 mensajes + 4 furigana; ninguna de las 21 partes de
texto mostraba su mensaje entero). Los botones «S í / N o» de `b_win_b01` son arte EU idéntico (0 diferencias en los 10 rectángulos dibujados); sus columnas japonesas (やめる, けってい, OK) no las dibuja ningún rectángulo.

De la ronda 1 (inspección visual, **no repetida**): `23pl_b` (`btn01` «キャンセル/けってい», logo «オーガ プレミアム リンク», `sldn_b01_2` con líneas japonesas intercaladas), `stage_select_b` (`bg09` «たいせんCOM»), `game_command_select_b`
(`command_msg_b01`, faltan 3 líneas ES), `menu_movview_b` (`font01`, `button03` «もどる») y recortadas respecto al EU: `23pl_t sc_psdn_t01`, `game_obj_b change_logo`, `battle_start new_b01`, `title_t logo03`,
`tournament_b victory_b01`, `training_f_menu_b un01`, `formation_b form_mes_b02`. Mismo método que `mes_b01` (repintar solo los rectángulos que dibuja el QNA) si caben. Sin tratar.

## 3. Tablas de datos con ES oficial (reemplazo directo o por registro)

Mismo offset y tamaño (reemplazo directo, comprobar que el resto de campos no cambia): `bgm_collection.bin` (59 títulos), `rpgtitle.STR` (5), `ScoutSpCode.dat` (5, son contraseñas),
`CapsulePoint.dat` (15 de 19), `JinmyakuTreasure.dat` (3 de 12). Otro layout (alinear por registro): `sp_binder.STR` (≈350 descripciones de supertácticas: **alta visibilidad**), `item.STR` (34), `fieldinf.dat` (129),
`ClearCondition/OpenCondition.dat`, `TournamentName*.dat`, `team.pkb` (23 equipos), `CapsuleComment.dat`, `JinmyakuData.dat`, `unitbase.STR` (40 biografías solo JP, sin ES). No tratadas.

## 4. Otros

- `ina_menu.cro`: 72 cadenas UTF-8 con nombres de catálogo; sin cruzar con el EU.
- Diálogos residuales de `eve.pkb`/`evet.pkb` (fuera del alcance de UI).
- Nombres con furigana: **[hecho]** `nombres_casilla_resto` (compositor `0x1440bc` en blanco: «Jérome Hervaud», «Joan Rodríguez», «Ramón Martínez»).
- Motores genéricos de centrado `0x17fb4c` (medidor con r2 = 0, sin clamp; 53 llamadores) y `0x18126c` (ancho real; solo recoloca X de −5 a −1 a 0; 29): qué texto de jugador llega por ellos no se puede enumerar en estático; hace falta una captura de la pantalla.
  Ronda 3: el inventario de los 25 llamadores del medidor `0x16f554` está cerrado (`menus_cro/nombres_casilla_resto/README.md`); la variante global `menus_cro/medidor_ancho_real` no cambia ninguno de esos dos motores.
- Captura 25 («Cambiar jugadores»): letras con ~2 px de separación (bloque ITX), no es una posición; la fila pequeña del nombre no está localizada.

## Actualización ronda 4 · C (2026-11-09): dónde alojar lo que no cabe

Diseño en `work/ie3/shared/capas/menus_cro/cuevas_pc/` (detalle y riesgos en `docs/BACKLOG.md`, «IE3 ronda 4 · C»). Zonas demostrablemente libres: `0x29bf00-0x29bfff` (texto, ejecutable) y `0x2ced34-0x2cefff` (rodata). Cubre los `add r1,pc,#imm` de `0xdd8e8`, `0xdce88`, `0x1d8774`, `0x93ba4`, `0x7ac90`, `0x7aee4`, `0xd0048`, `0xd008c`, `0x68380` con un `bl`/`b` a un stub (sin relocaciones nuevas ni cambios de cabecera). El modo que usa el rodata depende de una apuesta no probada (`add pc` entre segmentos) y es opcional. `0x29f09c` (antes «bloque de uso desconocido») está dentro de una racha con 440 destinos de relocación: no es cueva.

## Ronda 4 · D — texturas y datos con japonés (2026-11-09, estático; construido sin instalar, `runtime_verified: false`)

Tabla completa (por arc y textura, veredicto y motivo): scratchpad `ie3_r4/texturas.json`. Hallazgo de fuente: `work/ie3/amenaza_del_ogro/fuentes/3ds_eu/romfs/archive_oz.fa` trae los arcs `es/inazuma3_ogre/…` del propio Ogro (las rondas anteriores comparaban con el archive_bz.fa de Fuego); en la raíz Ogro **4139 de 4208 arcs** (sin minimap ni vs_school_name) ya son idénticos byte a byte al EU, y los 69 restantes son parches del proyecto, EU peor (p. ej. 23pl_b de inazuma3, EU en japonés) o los pendientes de abajo.

- **Seguro sustituir (mismo tamaño/formato y mismas cajas QNA; píxeles distintos solo dentro de las cajas):** `23pl_b/ie03_ogpl_it_pldn_t00` (logo japonés -> «Ogro Conexión especial»), `game_command_select_b/ie03_command_net_ok_btn_b01` («OK» -> «Aceptar») -> capa `graficos/logo_y_botones_ogro_eu` (construida y validada, no instalada; se funde con `fundir_arcs.py`). Tercera, fuera de la capa: `name_b/ie03_window_btn00_p01` («O K» -> «Aceptar»; name_b es de la capa teclado).
- **Sin efecto visible (no se dibuja):** `stage_select_b/ie03_stageselect_bg09` («たいせんCOM»: 0 cajas QNA, EU incluido), `connection_b/ie03_menu_connection_b_win_b01` (las columnas japonesas caen fuera de las 10 cajas dibujadas), `23pl_b/ie03_23pl_b_btn01`.
- **No seguro (tamaño distinto de la CTPK o cajas/QNA distintas), con japonés visible:** `23pl_b/ie03_ogpl_b_sldn_b01_2` (4 líneas japonesas + 2 ES recortadas; repintar y ensanchar cajas), `game_command_select_b/ie03_command_msg_b01` (faltan 3 mensajes ES y quedan 3 tiras verticales japonesas: 256x256 LA4 frente a 256x512), `menu_movview_b/ie03_button03`, `stage_select_b/ie03_button03`, `wireless_b` (cssele_pt01, msg02, vs_rulu_font01, button03), `wireless_t/ie03_wireless_t_window02`, `a_common/wireless_common_b/ie03_wireless_common_b02`; `binder_b/ie03_menu_binder_mes_b04` (el EU también deja «レイトンチーム»: sin texto oficial). Wi-Fi/StreetPass: baja visibilidad.
- **Texto ES recortado sin japonés:** `extra_team_b` (mes_b01: 238 de 2052 px EU quedan fuera de las cajas QNA japonesas; caution_b03: 97 de 2405), `game_obj_b/change_logo`, `battle_start_b/new_b01`, `formation_b/form_mes_b02` (faltan «Duelo 2/3»), `wireless_result_b`.
- **Candidatos a «arc EU entero»** (QNA con los mismos grupos y escenas, como `menu_slot`): game_command_select_b, menu_movview_b, stage_select_b, formation_b, wireless_result_b, wireless_common_b; riesgo: texturas mayores en memoria y pisar parches del proyecto.
- **Raíz `inazuma3/`:** 38 arcs (a_game 12, a_common 4…) no existen en `es/` y siguen en japonés en la instalada; no se puede demostrar en estático que la CRO los cargue (la raíz se concatena en ejecución).
- **Datos con ES oficial:** «mismo offset y tamaño» NO es reemplazo directo (el EU usa otra codificación: hay que recodificar con `textos_logic/comun.codificar`). `bgm_collection.bin`: 60 registros; caben (ancho completo, ≤ 82 B) pero el ancho en pantalla (hasta 41 letras frente a 18 japonesas) no está comprobado. `rpgtitle.STR`: 5 restantes no caben (lector `0x1fb118` ≤ 18 B). `ScoutSpCode.dat`: 8 registros (no 5), contraseñas de 10-13 letras frente al tope de 8. `CapsulePoint.dat`: 15 no caben (furigana: solo ancho completo, 31 B). `JinmyakuTreasure.dat`: 7 nombres con ES caben (no 3). `sp_binder.STR`: no entra (desplazamientos `ldrsh` < 0x8000, ya 32 826 B en japonés). `fieldinf.dat`, `games.*`, `premiumcondition.dat`, `phone_password.txt`: el EU del Ogro los deja idénticos al japonés (sin texto oficial).

## Ronda 4 · I1 (2026-11-09): resumen de literales de CRO (estático, sin instalar, `runtime_verified: false`)

- `menus_cro/fichar_literales_eu`: 48 → 57 → **67** literales (+9: `0x1ffb88`, `0x1ffbb0`, `0x2b6034`, `0x20c544`, `0x20c56c`, `0xb7b44`, `0xd0068`, `0x1dad40`, `0x123940`; +10 de la corrección 2, listados en §1.1). Evidencia nueva: `ejecucion.py` (ejecución diferencial JP/EU con unicorn) y `evidencia.py` con `mov<cc>/ldr<cc>`.
- `menus_cro/literales_cueva_eu` (NUEVA, OPCIONAL, desactivada por defecto, NO entra en el paquete final): 11 literales que no caben (6 con stub en `0x29bf00-0x29bfe6`, 5 con addend de relocación reapuntado a rótulos japoneses muertos). Detalle y riesgos en su README.
- Pendientes con motivo en las tablas de §1.1; preguntas para el usuario: `0x70d24`, `0x1c9820`/`0x1c9848`, `カップ`+`TournamentName*.dat`, el nivel B (`0x19a7d8` y compañía) y si se quiere el «modo rodata» de `cuevas_pc`.
