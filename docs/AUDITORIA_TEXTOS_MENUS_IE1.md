# Auditoría de textos de menú de IE1 frente al IE1 europeo de 3DS

Fecha: 2026-10-31. Petición del usuario: «hay muchos textos de menús que están inventados con respecto al original de 3DS de IE1, o
como el mensaje después de haberse guardado; esto es lo que debería mostrarse en el guardado» (capturas 30-34). Autorización explícita
del usuario para sustituir por el texto OFICIAL EU los textos de MENÚS (no diálogos); ajuste de ancho solo si el oficial no cabe y sin
reescribirlo. Norma 3 de CLAUDE.md. Análisis ESTÁTICO: sin emulador; todo lo marcado `runtime_verified: false` lo prueba el usuario.

Norma 2: este documento solo lleva identificadores, offsets, rótulos cortos y el texto propio del proyecto. El texto extraído completo
(frases largas del EU, tablas de 307 filas con el japonés original) queda en `work/ie1/qa/auditoria_textos_menus/` (ignorado por git).

## 1. Respuesta a la pregunta de las capturas 32-34

Las tres son texto OFICIAL EU y el proyecto NO lo usaba:

| Captura | Texto (oficial EU) | Qué lleva hoy la build | Dónde vive |
|---|---|---|---|
| 32 | «Se han guardado los datos.» + «Aceptar» | «Guardar completado.» (fragmentos pintados por el proyecto) | textura `ie01_menu_slot_b_msg01` de `slot_b.arc` |
| 33 | «Se van a sobrescribir los datos. ¿Quieres continuar?» + «S í» / «N o» | «Se borrará la partida. ¿Quieres continuar?» («borrar» no es «sobrescribir») | ídem, grupo QNA 40 |
| 34 | «No puedes guardar en una ranura diferente.» + «Aceptar» | «En otra ranura no puedes guardar.» | ídem, grupo QNA 38 |

No son cadenas de la CRO ni de `GameString` (el EU no las tiene como texto): son imagen. Por eso ningún inventario de literales las
encontraba. «Sí / No / Aceptar» con las letras separadas es el arte oficial `btn02` (3 filas de 16 px, «S í» y «N o» pintados así); la build
llevaba un `btn02` propio «OK / Si / No» (sin tilde). El «Guardar» del título es «GUARDAR» en el EU.

## 2. Capas creadas (todas con `runtime_verified: false`, `instalada: false`; base = ficheros instalados en el PC) — ronda 2

| Capa | Qué | Cambia | Verificación |
|---|---|---|---|
| `work/ie1/capas/graficos/guardado_oficial_eu` | mensajes de guardado/carga/error y botones Aceptar/Sí/No oficiales | `slot_b.arc` = EU (msg01 512x512, btn02, bg_p01, QNA) salvo «Espacio» del grupo 1, que conserva 56x14@-114 | 196 comprobaciones; los 107 grupos del QNA comparados parte a parte (`tabla_grupos.json`) |
| `work/ie1/capas/graficos/equipo_oficial_eu` | pantalla «miembros del intercambio» (capturas 30/31) | 5 texturas de `select_player_b.arc` | 17 comprobaciones; QNA idéntico |
| `work/ie1/capas/graficos/rotulos_menus_eu` | rótulos inventados en 19 arcs de `a_menu` | 44 texturas con las mismas cajas QNA (ronda 3: `form_mes_tp_b01` «TP» → «PT») | 160 comprobaciones (179 con `--copia`) |
| `work/ie1/capas/menus_cro/rotulos_oficiales_eu` | 2 literales de la CRO que caben (celdas y píxeles) | 28 B de `ina_main1.cro` | 18 comprobaciones + `ocupacion_px.json` |
| `work/ie1/capas/menus_cro/fundir_capas` | herramientas para FUNDIR capas (`fundir_cro.py`, `fundir_arcs.py`) | nada (solo copias locales) | probadas con las 4 capas de CRO y las 4 de arcs |

Cada una trae `apply.py`, `validate.py` (con `--copia` las gráficas), `README.md` (instalar directo sin copias de seguridad y deshacer sin copia), `informe.json`, `validacion.json` y `salida/`.
Las capas gráficas ya no dependen del orden: cada una parte del `archive.fa` instalado y entrega arcs distintos; `fundir_arcs.py` las funde en una copia exigiendo que no haya dos
capas con el mismo arc y que cada entrada de la copia sea todavía la de la base. Comprobado sobre una copia del instalado con guardado + equipo + rotulos + `salir_abandonar`: 22 entradas
distintas, `sincronia_usearch verificar` con código 0, `validate.py --copia` OK en las tres capas y `--deshacer` devuelve las 22 entradas (0 distintas de las 15 547 de la base; el fichero conserva el dato anexado).
sha256 de esa copia (orden documentado, con `form_mes_tp_b01` «PT» de la ronda 3): `397673b7aabe84a4a1d5dc7f74b011463af3c3536d2d228affa192ea9ea14510`. Paquete listo para instalar de una vez: `work/ie1/capas/menus_cro/fundir_capas/paquete_final/`.
Las capas de CRO (`fichar_rotulos_ranuras`, `panel_equipo_rotulos`, `estadisticas_sello_historia` —opcional—, `rotulos_oficiales_eu`) se funden con `fundir_cro.py`: sin solapes entre sus rangos
(`validate.py` de la capa lo comprueba con las salidas presentes en ese momento; quien añada una capa de CRO debe volver a pasar `fundir_cro.py`).

## 3. Pantalla de las capturas 30 y 31

La 30 es el EU oficial y la 31 la build, con las mismas texturas (`select_player_b.arc`): «Cambiar jugadores» → «miembros del intercambio»,
«Enseñar técnicas» → «Pasar técnicas», pestañas «Equipo/Reservas» → «Miembros/Reserva», botones «OK/Equipar/Listo/Opciones» →
«Aceptar/Equipo/Salir/Ajustes», columna «LV P» → «NiV.», «Reiniciar» → «Rehacer». Resuelto en `equipo_oficial_eu`.

## 4. Literales de la CRO (`ina_main1.cro` 1.4): 307 comparados

24 ya oficiales, 260 inventados/abreviados, 12 siguen en japonés, 11 sin pareja EU. Las parejas de confianza «alta» se apoyan en el orden del
código y en el japonés original; las «media» solo en el sentido y el contexto (no verificadas de nuevo en este paso). Solo **2** se han
cambiado (ronda 2: «Equipo» `0x13a0b4` se revirtió porque no cabe en celdas): los demás no se pueden sustituir con seguridad estática. Motivos (sobre los 260): no cabe en el hueco en bytes (176), lleva
`%s/%d` y depende del código que lo rellena (34), pareja «media» por confirmar (20), literal compartido por varias ranuras (20), ventana o
líneas sin confirmar (7). Además, muchos literales los carga el código con `adr` (dirección fija relativa al PC): no se pueden reubicar
sin cambiar el código, así que su tamaño máximo es el hueco; solo los referenciados por relocación (como los de Fichar) se pueden mover a la
zona a cero `0x1b3ca0..0x1b4000`.

**12 literales siguen en japonés visible** (prioridad alta para la ronda siguiente; el oficial no cabe en su hueco y hay que cambiar cómo
se carga el literal): `0x654c0`, `0x656b8`, `0x657e4` (menú inalámbrico, EU 293/310/299), `0x8c740` (EU 315), `0xb60fc`, `0xb6490`, `0xb6694`
(intercambio, EU 273/200/272), `0x10727c` («Pasión necesaria», EU 175), `0x19f144` (Wi-Fi saturado, EU 18), `0x19fec4` («ひきぬき», lo trata
otro workflow) y las dos claves de comparación `0xfe84`/`0xfe90` (no se tocan).

**Criterio de ancho (ronda 2).** Cada literal está codificado en celdas de 2 bytes; el texto actual usa «bigramas del ritmo» (un código = dos letras, p. ej. «ui», «rr», «or») y
`encode_fullwidth` solo emite letras sueltas, de modo que contar caracteres no vale. `menus_cro/rotulos_oficiales_eu/ocupacion_celdas.py` mide en celdas, en píxeles proporcionales (CWDH de las
FONT12/FONT8 instaladas) y en paso fijo, y solo se cambia un literal si en ninguna línea supera al actual en ningún modelo (`ocupacion_px.json`). Resultado: `0x65730` 15→13 celdas, `0x11da0c`
4→3 celdas (con «rr»+«or»); `0x13a0b4` «Equipo» 4→5 o 6 celdas (el bigrama «po» solo tiene glifo en FONT12): no se cambia.

**Capitán (`0x12a35c/0x12a37c/0x12a394`, `0x19d300/320/338/370`).** La textura EU dice «Audaz/Calma/Apoyo» (botones); estos literales son las frases 263-265 del EU («A lo loco», «Con cabeza fría», «Con autoridad») y 262
(«Elige al capitán.»), no los botones. No caben (6/11/9/9 celdas y 66/107/96/120 px frente a 6/5/5/10 celdas y 37/35/38/62 px actuales, FONT12): pendiente de ancho de ventana. «Pasión» sigue siendo invento.

**Literales visibles que la ronda 1 no inventariaba** (solo identificados; sin pareja EU verificada, no se tocan): `0x354b4` «Error: conexión interrumpida.» (candidatas EU 27/29/4), `0x74470` y `0x774c4`
«Sin puntos.», `0x77494` «Ya no caben.», `0x3545c` en japonés «正常にダウンロードできませんでした。» (candidatas EU 28/30/15) y los kana con `adr` `0x6c240` «から», `0x6c26c` «とびら», `0x6c274` «ひら»,
`0x6c6ac` «せんしゅ» (¿visibles o claves? no determinable en estático). A los 12 literales en japonés visibles se suman estos.

**Sin texto oficial EU (no se inventan; pendiente de decisión):** «¿Conectarse?» `0x8c61c`, «Móvil» `0xc8294`/`0xc82b4` (el EU no tiene
equivalente), «Modo DL» `0x19eacc` (el EU lo conserva en japonés), «Un momento» `0x19e3d0`, «Fin» `0x19b31c` y los 5 mensajes de
StreetPass y novedades `0x1b1276…0x1b13b2` (el EU no tiene StreetPass).

**Compartidos por varias ranuras** (cambiar el literal cambia todas; para una sola hay que reapuntar su relocación a un literal nuevo):
«Fin» ×8 (oficial «Salir»), «Otro» ×4, «No» ×3 (EU «---»), «Fís» ×3, «Un momento…» ×3 y ×2, «Elige espacio.» ×2, «Ep.» ×2, «Jugador no apto.» ×2,
«Desconectado.» ×2, «Empieza el intercambio…» ×2, «¿Poner %s?» ×2, «Raimon», «Vale», «Cambiar», «Mantener», «Fich» ×2 y las abreviaturas de estadística.

**Limitados por el paso fijo de la pantalla de elegir espacio (#97):** «Nivel»/«Jug» (EU «Niv. Equipo»/«Jugadores»), «Mtro.» (EU «Maestro») y
«Elige espacio.» (EU «Elige un espacio de guardado.»): el texto cabe en bytes pero no en píxeles con el paso fijo de ~10,5 px. La capa `menus_cro/panel_equipo_rotulos` (otro workflow, 2026-10-31) los resuelve con cuevas; esta auditoría no la toca.

Tabla completa de los 260 inventados/abreviados (columna «Oficial B» = bytes del oficial con `encode_fullwidth`, sin repartir en líneas):

| Offset | Actual | EU id | Oficial EU (corto) | Pareja | Hueco B | Oficial B | Estado |
|---|---|---|---|---|---|---|---|
| 0x25df8 | y cía. | 346 | %s y amigos | alta | 12 | - | marcador %s/%d: depende del código |
| 0x650bc | Crea un / partido local. | 552 | (60 car.) | alta | 52 | 121 | no cabe en el hueco |
| 0x650f0 | Crea un / intercambio. | 555 | (48 car.) | alta | 52 | 97 | no cabe en el hueco |
| 0x65124 | Busca un / partido local. | 553 | (59 car.) | alta | 48 | 119 | no cabe en el hueco |
| 0x65154 | Busca un / intercambio. | 556 | (47 car.) | alta | 48 | 95 | no cabe en el hueco |
| 0x65184 | Esperando a / otro juga… | 308 | (62 car.) | media | 60 | 125 | no cabe en el hueco |
| 0x654fc | ¿Intercambiar? | 309 | (46 car.) | media | 32 | 93 | no cabe en el hueco |
| 0x6551c | ¿Enfrentarte? | 294 | (35 car.) | media | 32 | 71 | no cabe en el hueco |
| 0x6553c | Elige con quién / cambiar. | 557 | (39 car.) | alta | 58 | 79 | no cabe en el hueco |
| 0x656f4 | Buscando rival. / Un mo… | 296 | (70 car.) | media | 60 | 141 | no cabe en el hueco |
| 0x65730 | Elige con quién / jugar. | 554 | Elige un contrincante. | alta | 56 | 45 | **HECHO** |
| 0x65768 | Un momento... | 153 | Espera unos instantes... | media | 32 | 49 | compartido (3 ranuras) |
| 0x65788 | Esperando... | 298 | Esperando respuesta... | media | 32 | 45 | no cabe en el hueco |
| 0x657a8 | ¡Intercambio! | 312 | (41 car.) | media | 32 | 83 | no cabe en el hueco |
| 0x6b410 | deja el club. / | 42 | %s ha dejado el equipo. | alta | 32 | - | marcador %s/%d: depende del código |
| 0x6be4c | Pasión | 36 | (36 car.) | media | 16 | - | marcador %s/%d: depende del código |
| 0x6be70 | (man) | 33 | Has conseguido: %s | media | 12 | - | marcador %s/%d: depende del código |
| 0x6be88 | / (táctica) | 34 | (40 car.) | media | 28 | - | marcador %s/%d: depende del código |
| 0x6bea4 | / (duelo) | 35 | (41 car.) | media | 16 | - | marcador %s/%d: depende del código |
| 0x6bed0 | ¡Premio! | 33,38 | Has conseguido: %s | media | 24 | - | marcador %s/%d: depende del código |
| 0x6c22c | ¡Vacío! | 39 | Está vacío. | media | 20 | 23 | no cabe en el hueco |
| 0x6c248 | ¡Puerta abierta! | 40 | (32 car.) | media | 36 | 65 | no cabe en el hueco |
| 0x6c43c | Pasión: | 41 | (56 car.) | media | 16 | - | marcador %s/%d: depende del código |
| 0x6c44c | puntos | 41 | (56 car.) | media | 12 | - | marcador %s/%d: depende del código |
| 0x6c460 | Amistad: | 41 | (56 car.) | media | 16 | - | marcador %s/%d: depende del código |
| 0x6c470 | ¡Perdidos! | 41 | (56 car.) | media | 16 | - | marcador %s/%d: depende del código |
| 0x6c66c | ¡Fichero lleno! / | 43 | (49 car.) | media | 36 | - | marcador %s/%d: depende del código |
| 0x6c694 | ¡Premio! | 43 | (49 car.) | media | 24 | - | marcador %s/%d: depende del código |
| 0x6cf70 | Te falta la llave. | 32 | (34 car.) | alta | 40 | 69 | no cabe en el hueco |
| 0x6e2a0 | No se puede usar. | 202 | (26 car.) | media | 40 | 53 | no cabe en el hueco |
| 0x6e2c8 | No se puede usar más. | 559 | (25 car.) | media | 48 | 51 | no cabe en el hueco |
| 0x6e2f8 | ¿Lo tiras? | 203 | (28 car.) | media | 32 | 57 | no cabe en el hueco |
| 0x6e31c | %s / recupera %s PE. | 158 | %s ha recuperado %d PE. | media | 40 | - | marcador %s/%d: depende del código |
| 0x6e344 | %s / recupera %s PT. | 159 | %s ha recuperado %d PT. | media | 40 | - | marcador %s/%d: depende del código |
| 0x6e36c | %s / recupera %s PE / y… | 160 | (35 car.) | media | 54 | - | marcador %s/%d: depende del código |
| 0x71f10 | Mtro. | 97 | Maestro | alta | 16 | 15 | ventana/líneas: confirmar |
| 0x71f3c | Nivel | 98 | Niv. Equipo | alta | 16 | 23 | no cabe en el hueco |
| 0x71f50 | Jug | 60 | Jugadores | alta | 12 | 19 | no cabe en el hueco |
| 0x71f6c | Ep. | 172 | Ep. %d | alta | 4 | - | marcador %s/%d: depende del código |
| 0x74494 | %s x%d / %d puntos. / ¿… | 211 | (45 car.) | alta | 58 | - | marcador %s/%d: depende del código |
| 0x74e68 | V. | 213 | Ven. | alta | 16 | 9 | ventana/líneas: confirmar |
| 0x74e78 | C. | 212 | Com. | alta | 8 | 9 | no cabe en el hueco |
| 0x7c938 | %s / (Error %s) | 357 | %s Código de error: %d | alta | 28 | - | marcador %s/%d: depende del código |
| 0x7d3cc | %s / (Error %s) | 357 | %s Código de error: %d | alta | 28 | - | marcador %s/%d: depende del código |
| 0x7fd88 | No equipable | 201 | (30 car.) | alta | 30 | 61 | no cabe en el hueco |
| 0x83980 | Faltan puntos de / Amis… | 279 | (51 car.) | alta | 72 | 103 | no cabe en el hueco |
| 0x83f64 | Jugador no apto. | 275 | (26 car.) | alta | 40 | 53 | compartido (2 ranuras) |
| 0x83f8c | No está listo. | 274 | (32 car.) | alta | 40 | 65 | no cabe en el hueco |
| 0x83fb4 | El otro ya / lo tiene. | 276 | (42 car.) | alta | 56 | 85 | no cabe en el hueco |
| 0x83fec | El otro lo está / ficha… | 277 | (48 car.) | alta | 60 | 97 | no cabe en el hueco |
| 0x8c604 | ¿Descargar? | 314 | (26 car.) | media | 24 | 53 | no cabe en el hueco |
| 0x8c63c | Conexión | 316 | Conectando... | media | 20 | 27 | no cabe en el hueco |
| 0x8c650 | Conectando... / Un mome… | 321 | (71 car.) | media | 56 | 143 | no cabe en el hueco |
| 0x8c688 | Descargado. | 318 | Descarga completada. | media | 32 | 41 | no cabe en el hueco |
| 0x8c6a8 | Actualizado. | 323 | (29 car.) | media | 28 | 59 | no cabe en el hueco |
| 0x8c6c4 | Sin novedades. | 324 | No hay datos nuevos. | media | 36 | 41 | no cabe en el hueco |
| 0x8c6e8 | Sin señal. | 319 | (25 car.) | media | 24 | 51 | no cabe en el hueco |
| 0x8dd90 | ¿Descargar? | 0 | (26 car.) | media | 24 | 53 | no cabe en el hueco |
| 0x8dda8 | ¿Conectar a / la CWF? | 8 | (49 car.) | media | 40 | - | pareja media: confirmar |
| 0x8ddd0 | Conexión | 1 | Conectando... | media | 24 | 27 | no cabe en el hueco |
| 0x8dde8 | Descargado. | 7 | Descarga completada. | media | 32 | 41 | no cabe en el hueco |
| 0x8de08 | Sin novedades. | 14 | No hay datos nuevos. | media | 36 | 41 | no cabe en el hueco |
| 0x8de2c | Actualizado. | 13 | (29 car.) | media | 28 | 59 | no cabe en el hueco |
| 0x8de48 | Sin señal. | 5 | (25 car.) | media | 24 | 51 | no cabe en el hueco |
| 0x8de60 | Cancelado. | 4 | Conexión interrumpida. | media | 24 | 45 | no cabe en el hueco |
| 0x8de78 | Has salido / de la CWF. | 12 | (44 car.) | media | 44 | - | pareja media: confirmar |
| 0x8ec54 | .º | 50 | %s, %d.º | media | 8 | - | marcador %s/%d: depende del código |
| 0x8f24c | ¡Datos al ficharlo! | 186 | (63 car.) | alta | 64 | 127 | no cabe en el hueco |
| 0xb5bbc | %s / Cambiar | 390 | Intercambiar con %s | alta | 24 | - | marcador %s/%d: depende del código |
| 0xb5c18 | ¡Completado! | 271 | Intercambio realizado. | alta | 38 | 45 | no cabe en el hueco |
| 0xb611c | ¿Intercambiarlo? | 269 | (35 car.) | alta | 41 | 71 | no cabe en el hueco |
| 0xb64ac | El otro lo ha / rechazado. | 270 | (40 car.) | alta | 60 | 81 | no cabe en el hueco |
| 0xb64e8 | Fallido. | 391 | Intercambio fallido. | alta | 28 | 41 | no cabe en el hueco |
| 0xb6504 | Un momento... | 153 | Espera unos instantes... | alta | 37 | 49 | compartido (2 ranuras) |
| 0xc7f0c | Equipo | 60 | Jugadores | media | 7 | 19 | no cabe en el hueco |
| 0xc7f48 | Jug. | 60 | Jugadores | media | 8 | 19 | no cabe en el hueco |
| 0xc7f50 | Relevo | 105 | Ordenar | media | 9 | 15 | no cabe en el hueco |
| 0xc825c | Táctica | 62 | Estrategia | media | 12 | 21 | no cabe en el hueco |
| 0xc8268 | Part. | 108 | Partido | media | 7 | 15 | no cabe en el hueco |
| 0xc8288 | Fichar | 75 | Ojear | media | 12 | 11 | pareja media: confirmar |
| 0xc82a8 | Robo | 45 | Fichar | media | 12 | 13 | no cabe en el hueco |
| 0xc82c0 | Miemb. | 103 | Miembros | media | 12 | 17 | no cabe en el hueco |
| 0x113d78 | ¿Seguro? | 182 | ¿Te parece bien? | alta | 28 | 33 | no cabe en el hueco |
| 0x11d97c | Sobra titular. | 187 | Sobran titulares. | alta | 32 | 35 | no cabe en el hueco |
| 0x11d99c | Falta titular. | 188 | Faltan titulares. | alta | 32 | 35 | no cabe en el hueco |
| 0x11d9bc | Sin cambios | 189 | Sobran suplentes. | alta | 24 | 35 | no cabe en el hueco; «Sin cambios» no es una abreviatura sino un sentido distinto (japonés: demasiadas sustituciones) |
| 0x11d9d4 | Sin POR. | 190 | No hay portero. | alta | 20 | 31 | no cabe en el hueco |
| 0x11d9e8 | No puedes / moverlo. | 191 | (37 car.) | alta | 36 | 75 | no cabe en el hueco |
| 0x11da0c | Error. | 193 | Error | alta | 12 | 6 (3 celdas con «rr»+«or») | **HECHO** (4→3 celdas) |
| 0x128cfc | Más Tiro | 375 | (26 car.) | media | 28 | 53 | no cabe en el hueco |
| 0x128d18 | Más Físico | 376 | (28 car.) | media | 24 | 57 | no cabe en el hueco |
| 0x128d30 | Más Control | 377 | (29 car.) | media | 32 | 59 | no cabe en el hueco |
| 0x128d50 | Más Defensa | 378 | (29 car.) | media | 24 | 59 | no cabe en el hueco |
| 0x128d68 | Más Rapidez | 379 | (29 car.) | media | 28 | 59 | no cabe en el hueco |
| 0x128d84 | Más Aguante | 380 | (29 car.) | media | 28 | 59 | no cabe en el hueco |
| 0x128da0 | Más Valor | 381 | (27 car.) | media | 28 | 55 | no cabe en el hueco |
| 0x12a2c0 | ¡Más Rapidez y Valor! | 382 | (39 car.) | media | 44 | 79 | no cabe en el hueco |
| 0x12a2ec | ¡Más Control y Aguante! | 383 | (45 car.) | media | 52 | 91 | no cabe en el hueco |
| 0x12a320 | ¡Más Control y Físico! | 384 | (40 car.) | media | 60 | 81 | no cabe en el hueco |
| 0x12a35c | Pasión | 263 | A lo loco | media | 32 | 19 | cabe en bytes; en celdas y px no (ver §4 «Capitán») |
| 0x12a37c | Calma | 264 | Con cabeza fría | media | 24 | 31 | no cabe en el hueco |
| 0x12a394 | Apoyo | 265 | Con autoridad | media | 24 | 27 | no cabe en el hueco |
| 0x13480c | ¿Quitar a / %s? | 150 | (40 car.) | alta | 32 | - | marcador %s/%d: depende del código |
| 0x13482c | %s / es necesario. | 151 | (43 car.) | alta | 40 | - | marcador %s/%d: depende del código |
| 0x134854 | ¿Guardar / cambios? | 534 | ¿Confirmar cambios? | alta | 36 | 39 | no cabe en el hueco |
| 0x134878 | %s / es clave. | 535 | %s es un jugador clave. | alta | 28 | - | marcador %s/%d: depende del código |
| 0x134894 | %s no / puede unirse. | 536 | (25 car.) | alta | 36 | - | marcador %s/%d: depende del código |
| 0x1348b8 | No puedes / quitar más. | 168 | (38 car.) | alta | 64 | 77 | no cabe en el hueco |
| 0x13a0b4 | Equip. | 247 | Equipo | alta | 16 | 12 | no cabe en celdas (5-6 frente a 4): pendiente (ronda 2) |
| 0x13a0c4 | ¿Te parece / bien así? | 248 | (48 car.) | alta | 48 | 97 | no cabe en el hueco |
| 0x13db74 | ¿Dónde lo colocas? | 204 | (37 car.) | alta | 44 | 75 | no cabe en el hueco |
| 0x144824 | Jug | 60 | Jugadores | alta | 12 | 19 | no cabe en el hueco |
| 0x1449d0 | Nivel | 98 | Niv. Equipo | alta | 26 | 23 | ventana/líneas: confirmar |
| 0x150ba0 | Ya fichado. | 54 | Ya está en tu equipo. | alta | 36 | 43 | no cabe en el hueco |
| 0x150bc4 | El comienzo. | 52 | Este es el comienzo. | alta | 28 | 41 | no cabe en el hueco |
| 0x150bf8 | Fichable | 55 | (29 car.) | alta | 20 | 59 | no cabe en el hueco |
| 0x150c0c | ¡Avanza más! | 56 | (26 car.) | alta | 28 | 53 | no cabe en el hueco |
| 0x150c28 | ¡Ficha más! | 57 | ¡Ficha para desbloquear! | alta | 24 | 49 | no cabe en el hueco |
| 0x1553b0 | ¿Poner %s? | 205 | ¿Quieres aprender "%s"? | alta | 24 | - | marcador %s/%d: depende del código |
| 0x1553d8 | Se sobrescribirá. / ¿Se… | 206 | (64 car.) | alta | 56 | 129 | no cabe en el hueco |
| 0x155410 | ¡Ya la sabe! | 207 | (30 car.) | alta | 28 | 61 | no cabe en el hueco |
| 0x15542c | ¡No apta para / %s! | 208 | (39 car.) | alta | 40 | - | marcador %s/%d: depende del código |
| 0x155454 | ¡%s aprendió! | 209 | (40 car.) | alta | 36 | - | marcador %s/%d: depende del código |
| 0x155478 | No necesita / compañero. | 210 | (37 car.) | alta | 48 | 75 | no cabe en el hueco |
| 0x1678d0 | .º | 50 | %s, %d.º | media | 4 | - | marcador %s/%d: depende del código |
| 0x1678d4 | Amistad | 51 | Puntos de Amistad | media | 20 | 35 | no cabe en el hueco |
| 0x17d1c8 | .º | 50 | %s, %d.º | media | 4 | - | marcador %s/%d: depende del código |
| 0x17d1cc | Amistad | 51 | Puntos de Amistad | media | 20 | 35 | no cabe en el hueco |
| 0x19afb0 | Conectando / a la CWF. … | 9 | (70 car.) | media | 68 | - | pareja media: confirmar |
| 0x19aff4 | Saliendo de / la CWF... | 11 | (44 car.) | media | 44 | - | pareja media: confirmar |
| 0x19b020 | Cancelando. | 3 | (26 car.) | media | 24 | 53 | no cabe en el hueco |
| 0x19b038 | Descargando. | 2 | Descargando... | media | 28 | 29 | no cabe en el hueco |
| 0x19b054 | Descargando... / Espera. | 10 | (50 car.) | media | 48 | 101 | no cabe en el hueco |
| 0x19b084 | Tus datos de CWF / podr… | 16 | (193 car.) | media | 120 | - | pareja media: confirmar |
| 0x19b0fc | Sin señal. | 5 | (25 car.) | media | 23 | 51 | no cabe en el hueco |
| 0x19b9b8 | Web | 65 | Futblog | media | 7 | 15 | no cabe en el hueco |
| 0x19b9bf | Fichero | 111 | Álbum | media | 15 | 11 | pareja media: confirmar |
| 0x19b9ce | Fich | 75 | Ojear | media | 9 | 11 | no cabe en el hueco |
| 0x19b9d7 | Robo | 45 | Fichar | media | 9 | 13 | no cabe en el hueco |
| 0x19b9e0 | Camis. | 66 | Uniformes | media | 13 | 19 | no cabe en el hueco |
| 0x19b9ed | Récord | 67 | Logros | media | 13 | 13 | pareja media: confirmar |
| 0x19c654 | Espera... | 153 | Espera unos instantes... | media | 25 | 49 | no cabe en el hueco |
| 0x19d300 | Pasión | 263 | A lo loco | media | 32 | 19 | cabe en bytes; en celdas y px no (ver §4 «Capitán») |
| 0x19d320 | Calma | 264 | Con cabeza fría | media | 24 | 31 | no cabe en el hueco |
| 0x19d338 | Apoyo | 265 | Con autoridad | media | 20 | 27 | no cabe en el hueco |
| 0x19d370 | Tu capitán | 262 | Elige al capitán. | media | 21 | 35 | no cabe en el hueco |
| 0x19e3e8 | Un momento. | 392 | Espera unos instantes. | media | 28 | 45 | no cabe en el hueco |
| 0x19e404 | Un momento.. | 393 | Espera unos instantes.. | media | 28 | 47 | no cabe en el hueco |
| 0x19e420 | Un momento... | 394 | Espera unos instantes... | media | 32 | 49 | no cabe en el hueco |
| 0x19e440 | Empieza el / intercambi… | 313 | (79 car.) | alta | 128 | 159 | compartido (2 ranuras) |
| 0x19e814 | Desconexión | 272 | Conexión interrumpida. | media | 23 | 45 | no cabe en el hueco |
| 0x19eae0 | Desconectado. | 326 | (47 car.) | media | 32 | 95 | compartido (2 ranuras) |
| 0x19eb00 | Cortado | 315 | Conexión interrumpida. | media | 16 | 45 | no cabe en el hueco |
| 0x19eb10 | No se encontró. | 327 | (25 car.) | media | 31 | 51 | no cabe en el hueco |
| 0x19f1c0 | ID de CWF borrado / por… | 19 | (162 car.) | media | 120 | 325 | no cabe en el hueco |
| 0x19f238 | Servicio de CWF / final… | 20 | (208 car.) | media | 92 | - | pareja media: confirmar |
| 0x19f294 | No se detecta el / Cone… | 24 | (205 car.) | media | 136 | - | pareja media: confirmar |
| 0x19f31c | Sin respuesta. El / otr… | 26 | (150 car.) | media | 140 | - | pareja media: confirmar |
| 0x19f3a8 | No se puede acceder / a… | 25 | (175 car.) | media | 104 | - | pareja media: confirmar |
| 0x19f410 | Sin acceso a la / CWF. … | 17 | (173 car.) | media | 80 | - | pareja media: confirmar |
| 0x19f460 | Punto de acceso / satur… | 21 | (151 car.) | media | 92 | 303 | no cabe en el hueco |
| 0x19f4bc | Sin punto de / acceso. … | 22 | (136 car.) | media | 92 | 273 | no cabe en el hueco |
| 0x19f518 | Sin puntos de / acceso … | 23 | (185 car.) | media | 108 | 371 | no cabe en el hueco |
| 0x19f584 | Error en la CWF. / Apag… | 31 | (114 car.) | media | 104 | - | pareja media: confirmar |
| 0x1a02ec | Ro | 353 | Royal Academy | media | 8 | 27 | no cabe en el hueco |
| 0x1a02f4 | Zeu | 354 | Zeus | media | 7 | 9 | no cabe en el hueco |
| 0x1a0bbc | Ro | 353 | Royal Academy | media | 5 | 27 | no cabe en el hueco |
| 0x1a1b00 | sube! | 174 | (30 car.) | media | 16 | - | marcador %s/%d: depende del código |
| 0x1a3600 | Ir a | 156 | Destino | media | 12 | 15 | no cabe en el hueco |
| 0x1a3e8c | Elige espacio. | 537 | (29 car.) | alta | 33 | 59 | compartido (2 ranuras) |
| 0x1a496c | Tir | 134 | Tiro | alta | 8 | 9 | no cabe en el hueco |
| 0x1a4974 | Fís | 135 | Físico | alta | 8 | 13 | no cabe en el hueco |
| 0x1a497c | Contr. | 138 | Control | alta | 16 | 15 | ventana/líneas: confirmar |
| 0x1a498c | Def | 136 | Defensa | alta | 8 | 15 | no cabe en el hueco |
| 0x1a4994 | Rap. | 137 | Rapidez | alta | 12 | 15 | no cabe en el hueco |
| 0x1a49a0 | Agu. | 140 | Aguante | alta | 12 | 15 | no cabe en el hueco |
| 0x1a49ac | Val | 139 | Valor | alta | 8 | 11 | no cabe en el hueco |
| 0x1a49dc | %s:%s+%s! / %s:%s al máx. | 173,174 | (41 car.) | media | 60 | - | marcador %s/%d: depende del código |
| 0x1a4a18 | %s:%s+%s! | 174 | (30 car.) | media | 28 | - | marcador %s/%d: depende del código |
| 0x1a4c38 | Pasión | 175 | Pasión necesaria | media | 20 | 33 | no cabe en el hueco |
| 0x1a4c4c | Falta Pasión | 176 | Faltan puntos de Pasión. | media | 25 | 49 | no cabe en el hueco |
| 0x1a51c4 | ¡Uy! Te falta / Pasión. | 179 | (34 car.) | alta | 44 | 69 | no cabe en el hueco |
| 0x1a51f0 | ¡Esa ya / la sabe! | 178 | (29 car.) | alta | 40 | 59 | no cabe en el hueco |
| 0x1a5218 | Le va grande. / ¿Te da … | 181 | (63 car.) | alta | 56 | 127 | no cabe en el hueco |
| 0x1a5250 | Elige la técnica / y la… | 177 | (54 car.) | alta | 68 | 109 | no cabe en el hueco |
| 0x1a5294 | Se sobrescribirá. / ¿Te… | 183 | (49 car.) | alta | 77 | 99 | no cabe en el hueco |
| 0x1a5440 | No tiene técnicas / que… | 184 | (53 car.) | alta | 60 | 107 | no cabe en el hueco |
| 0x1a6838 | Ordena los tiradores co… | 257 | (46 car.) | media | 71 | 93 | no cabe en el hueco |
| 0x1a6c8c | Espera... | 153 | Espera unos instantes... | media | 28 | 49 | no cabe en el hueco |
| 0x1b0959 | P1 | 260 | 1p | media | 5 | 5 | pareja media: confirmar |
| 0x1b0995 | 1T | 258 | 1P | media | 5 | 5 | pareja media: confirmar |
| 0x1b099a | 2T | 259 | 2P | media | 5 | 5 | pareja media: confirmar |
| 0x1b099f | P2 | 261 | 2p | media | 5 | 5 | pareja media: confirmar |
| 0x1b1133 | Intercambio / local. | 551 | (46 car.) | alta | 38 | 93 | no cabe en el hueco |
| 0x1b1159 | Juega con / amigos. | 550 | (57 car.) | alta | 38 | 115 | no cabe en el hueco |
| 0x1b17e1 | Vale | 46 | Aceptar | alta | 9 | 15 | compartido (2 ranuras) |
| 0x1b17ea | Cambiar | 49 | Cambiar condición | alta | 19 | 35 | compartido (2 ranuras) |
| 0x1b17fd | Otro | 44 | Buscar otros | alta | 13 | 25 | compartido (4 ranuras) |
| 0x1b180a | Mantener | 48 | Misma condición | alta | 19 | 31 | compartido (2 ranuras) |
| 0x1b181d | Fin | 47 | Salir | alta | 7 | 11 | compartido (8 ranuras) |
| 0x1b1835 | Robo | 45 | Fichar | alta | 9 | 13 | no cabe en el hueco |
| 0x1b19e2 | PE y PT+ | 131 | Aumenta los PE y PT. | media | 19 | 41 | no cabe en el hueco |
| 0x1b19f5 | Tir/Fís+ | 126 | (32 car.) | media | 17 | 65 | no cabe en el hueco |
| 0x1b1a06 | Val/Res+ | 130 | (34 car.) | media | 19 | 69 | no cabe en el hueco |
| 0x1b1a19 | Fís/Contr+ | 129 | (39 car.) | media | 23 | 79 | no cabe en el hueco |
| 0x1b1a30 | Defensa+ | 127 | (30 car.) | media | 21 | 61 | no cabe en el hueco |
| 0x1b1a45 | Rapidez+ | 128 | Mejora la velocidad. | media | 23 | 41 | no cabe en el hueco |
| 0x1b1a5c | Sin camb. | 132 | (38 car.) | media | 19 | 77 | no cabe en el hueco |
| 0x1b1d5f | ZeusX | 68 | Ultra Zeus | media | 11 | 21 | no cabe en el hueco |
| 0x1b1e1a | Amis | 69 | Amistoso | media | 9 | 17 | no cabe en el hueco |
| 0x1b1e23 | Campo | 70 | Elegir campo | media | 15 | 25 | no cabe en el hueco |
| 0x1b1e41 | Fich | 75 | Ojear | alta | 9 | 11 | compartido (2 ranuras) |
| 0x1b1e4a | Atr | 76 | Salir | media | 7 | 11 | no cabe en el hueco |
| 0x1b1ec5 | Delan | 85 | Delantero | alta | 11 | 19 | no cabe en el hueco |
| 0x1b1ed0 | Clb | 77 | Club | alta | 7 | 9 | no cabe en el hueco |
| 0x1b1ed7 | Pos. | 78 | Posición | alta | 11 | 17 | no cabe en el hueco |
| 0x1b1ee2 | A | 90 | Aire | alta | 3 | 9 | no cabe en el hueco |
| 0x1b1ee5 | Sabe | 86 | Inteligencia | alta | 9 | 25 | no cabe en el hueco |
| 0x1b1eee | Veloz | 87 | Rapidez | alta | 11 | 15 | no cabe en el hueco |
| 0x1b1ef9 | Hábil | 89 | Destreza | alta | 13 | 17 | no cabe en el hueco |
| 0x1b1f06 | Af | 80 | Afinidad | alta | 5 | 17 | no cabe en el hueco |
| 0x1b1f0b | No | 81 | --- | alta | 5 | - | compartido (3 ranuras) |
| 0x1b1f1d | Contac | 96 | Contactos | alta | 13 | 19 | no cabe en el hueco |
| 0x1b1f2a | Condición | 94 | Características | alta | 19 | 31 | no cabe en el hueco |
| 0x1b1f3d | At | 79 | Habilidad | alta | 5 | 19 | no cabe en el hueco |
| 0x1b1f42 | F | 92 | Fuego | alta | 3 | 11 | no cabe en el hueco |
| 0x1b1f45 | B | 91 | Bosque | alta | 3 | 13 | no cabe en el hueco |
| 0x1b1f48 | Fuert | 88 | Fortaleza | alta | 11 | 19 | no cabe en el hueco |
| 0x1b21bf | Fís | 135 | Físico | alta | 7 | 13 | compartido (3 ranuras) |
| 0x1b21c6 | Tir | 134 | Tiro | alta | 7 | 9 | compartido (2 ranuras) |
| 0x1b226d | Val | 139 | Valor | alta | 7 | 11 | compartido (2 ranuras) |
| 0x1b2274 | Def | 136 | Defensa | alta | 7 | 15 | compartido (2 ranuras) |
| 0x1b227b | Rap. | 137 | Rapidez | alta | 9 | 15 | compartido (2 ranuras) |
| 0x1b2284 | Agu. | 140 | Aguante | alta | 9 | 15 | compartido (2 ranuras) |
| 0x1b22b9 | Contr. | 138 | Control | alta | 13 | 15 | compartido (2 ranuras) |
| 0x1b2401 | M | 93 | Montaña | alta | 3 | 15 | no cabe en el hueco |
| 0x1b2404 | Ave | 245 | Sallys | media | 7 | 13 | no cabe en el hueco |
| 0x1b2504 | RaOB | 246 | Veteranos | media | 9 | 19 | no cabe en el hueco |
| 0x1b250d | Kids | 243 | Inazuma Kids FC | media | 11 | 31 | no cabe en el hueco |
| 0x1b2518 | Occ | 235 | Occult | media | 7 | 13 | no cabe en el hueco |
| 0x1b251f | Zeu | 242 | Zeus | media | 7 | 9 | no cabe en el hueco |
| 0x1b2558 | Roya | 234 | Royal Academy | media | 9 | 27 | no cabe en el hueco |
| 0x1b2561 | Wi | 236 | Wild | media | 5 | 9 | no cabe en el hueco |
| 0x1b256f | Shur | 239 | Shuriken | media | 9 | 17 | no cabe en el hueco |
| 0x1b2578 | Kir | 241 | Kirkwood | media | 7 | 17 | no cabe en el hueco |
| 0x1b257f | Umb | 244 | Umbrella | media | 7 | 17 | no cabe en el hueco |
| 0x1b2d13 | Macro dep. | 543 | Macrotienda dep. | alta | 28 | 33 | no cabe en el hueco |
| 0x1b2d2f | Maqueta | 547 | Tienda de maquetas | alta | 16 | 37 | no cabe en el hueco |
| 0x1b2d3f | Quiosco | 548 | Tienda de chuches | alta | 22 | 35 | no cabe en el hueco |
| 0x1b2d55 | Tienda Raimon | 541 | Tienda del Raimon | alta | 43 | 35 | ventana/líneas: confirmar |
| 0x1b2d80 | 24h Estación | 545 | Estación - T. 24h | alta | 32 | - | ventana/líneas: confirmar |
| 0x1b2eab | Dep.Inazuma | 542 | Tienda dep. peq. | alta | 26 | 33 | no cabe en el hueco |
| 0x1b2ec5 | 24h Tiendas | 544 | Barrio.t - T. 24h | alta | 34 | - | ventana/líneas: confirmar |
| 0x1b2efe | Juegos | 546 | Tienda de juegos | alta | 17 | 33 | no cabe en el hueco |
| 0x1b2f0f | Furukabu | 549 | Sr. Veteran | alta | 22 | 23 | no cabe en el hueco |
| 0x1b3406 | DF | 220 | Defensa | media | 5 | 15 | no cabe en el hueco |
| 0x1b340b | MD | 219 | Medio | media | 5 | 11 | no cabe en el hueco |
| 0x1b3410 | PR | 221 | Portero | media | 5 | 15 | no cabe en el hueco |
| 0x1b3415 | DL | 218 | Delantero | media | 5 | 19 | no cabe en el hueco |
| 0x1b341a | Rival | 217 | Equipo rival | alta | 15 | 25 | no cabe en el hueco |

## 5. Texturas de `a_menu` (instalado frente al EU; solo las de píxeles distintos)

Escaneo completo de `a_menu` (139 texturas con píxeles distintos del EU; `rotulos_menus_eu/tabla_texturas.json` con el estado y el contenido de cada una): **44 sustituidas** (`rotulos_menus_eu`), 12 de otras capas
(`select_player_b` 6, `slot_b` 3, `quit_b` 3), 29 con QNA que dibuja otras cajas y 28 de tamaño distinto (pendientes: hay que pegar celdas o ampliar textura y QNA) y 26 que cumplen mismo tamaño y cajas pero se descartan con motivo.
Ronda 3: la clasificación ya no es una lista de nombres sueltos sino una tabla por (arc, textura) hecha mirando los píxeles de la build y del EU lado a lado: mismo texto y solo cambia el trazo (14: `form_mes_cmd/men`, `sel_emb_btn_mes_b01`, `sel_cap_window_b05`, `sel_cap_pos_icon_b01`, `shop_trade_button_b01`, `teach_spm_mes_cmd_b01`, `big_btn03`, `trade04/09/10`, `member_gp_tp_bar` de `battle_member_b/_t`, `binder_number01`);
sin texto (4: iconos de elemento `form_mes_frkz_b01` y `status_mes02`, iconos `tu_pt01`, cursor `name_b_cursor01`); el EU quita o vacía el rótulo (3: `shop_item_plt_b01`, `wireless_b_stsele_pt01`, `teach_spm_mes_t01`, cuya textura del EU está vacía frente a la «P» de la build); rejilla distinta (`form_nmes_b01`); EU sin traducir (4, arc `battle_member` sin `_b`: `member_gp_tp_bar_b01` «GP/TP» en inglés frente a PE/PT, `member_lvup_b01`, `member_point_plt_b01`, `member_tec_learn_b01`, en japonés).
Corregido: `form_mes_tp_b01` decía «TP» (inglés) y el EU «PT»: ahora entra. Detalle por textura: `rotulos_menus_eu/README.md`.
Pendientes por tamaño/QNA: `bag_b`, `binder_b` mes_b01/02, `blog_*`, `connection_*`, `formation_b` mes_b01-04, `gameover_b`, `name_b` (4), `select_captain_b` mes_b02, `status_t` st_mes01/02, `system_*`,
`teach_sp_move_*`, `training_f_*`, `uniform_b` mes_b01, `wireless_b` (varias), `wireless_off_b`, `wireless_t`; lista completa en `work/ie1/qa/auditoria_textos_menus/texturas_1_menus.tsv.txt`.

Otros directorios con el mismo criterio, **sin hacer** (partido, órdenes, pausa, título): `a_game` 60 texturas con mismo tamaño y cajas (`game_command_select_b/t`, `game_obj_b` —ayuda, error, repetición—, `game_end_b/t`,
`game_result_b/t`, `game_pk_*`, `game_formation_*`, `game_3ddemo_t`), `a_title` 3 (`title_b_level5`, `title_t_ball`, `wireless_b_btn02`), `a_event` 1, `a_field` 2: son HUD del partido, no menús; necesitan su propia revisión
visual (backlog). `a_data_replace` (566) es contenido (técnicas, retratos), no menú.

No se han revisado en este paso los arcs de partido, campo, título y eventos (`a_game`, `a_field`, `a_title`, `a_event`): las auditorías previas
cuentan decenas de rótulos propios allí (órdenes, resultado, pausa, burbujas, «Tú/Rival», «DESCANSO»…). Pendiente.

## 6. Datos de `archive.fa` (contenido, no menú; no tocado)

Comparación por texto normalizado (puede incluir falsos distintos por los bigramas): `rpgtitle.STR` 35/35 oficial; `games.STR` (134 pistas de
objetivo) todas condensadas; `item.STR` 321/327 distintas del EU; `command.STR` 116/245; `unitbase.STR` 158/1040. `GameString.bin` en el EU sigue en
japonés: no hay texto oficial que lo respalde y no llega a la pantalla 3DS. Es contenido; queda para otro paso.

## 7. Decisiones y pendientes (para el usuario)

1. Prueba en juego con las preguntas de cada README. Riesgos conocidos: `slot_b.arc` del EU es 2,3 veces mayor (¿carga bien en la CRO 1.4?); posible doble pintado del mensaje de datos corruptos (G43 con G57-59, mismas tablas A/B que la build).
2. ¿Arte oficial «S í / N o / Aceptar» (letras separadas) o redibujar más compacto con las mismas palabras? Por defecto, oficial.
3. «Audaz / Calma / Apoyo» (textura EU) y los literales «Pasión / Calma / Apoyo» de las órdenes del capitán (frases EU 263-265, no caben): ver §4.
4. Los literales en japonés requieren cambiar el código que los carga (o ampliar el hueco): siguiente ronda, con revisión de cada ventana. «Equipo» (`0x13a0b4`) necesita un glifo «po» en FONT8 o más ancho.
5. Etiquetas de elegir espacio (#97, capa `panel_equipo_rotulos`) y mensajes largos de supertécnicas y Wi-Fi (el EU mide 70-215 caracteres; el proyecto los recortó; la Norma 3 exige repartir en líneas o ampliar la ventana, nunca condensar).
6. Issues (Norma 1): `gh` SÍ está autenticado en esta sesión, pero este agente no los crea (decisión del usuario): los borradores están en `docs/BACKLOG.md`, sección «Borradores de issues».
