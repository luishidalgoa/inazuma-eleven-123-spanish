# Auditoría de aplicación de gráficos IE2 (issue #77)

Candidata auditada: `work/shared/candidatas/probe_ie2_v21/archive.fa` (base v18 + v20 teclado/textos/gráficos + v21 tutorial).
Versión legible por máquina: `informe.json` (misma carpeta).

## 1. El rótulo 「バトル勝利」

- **Dónde está:** `inazuma2/data_iz/a_game/battle_start_b.arc`, textura CTPK `ie02_battle_start_result_plt_b01.tga`
  (256x128, RGBA5551). Es una textura 3DS dentro de un ARCV, no un sprite DS (pic2d/pic3d). Contiene tres placas:
  「バトル勝利」「タイムアップ」「バトル敗北」.
- **Causa:** **nunca se tradujo.** Ninguna capa la tocó (v03, v05, v06, v12, v20 y v21). v03 cambió en ese mismo `.arc` solo
  `ie02_battle_start_battle_b01` («DUELO»). La candidata lleva el `.arc` de v05 idéntico byte a byte, así que la placa sigue en japonés.
  Es fácil confundirla con `ie02_result_bt_win_t01` (「バトルしょうり」, en `game_result_t.arc`), que sí está traducida
  («¡Victoria!») y aparece correctamente en la candidata.
- **No es un duplicado ni una confusión entre data_iz y data_iz_blizzard:** la textura existe solo en ese `.arc`, y
  `data_iz_blizzard` solo contiene INAZUMA.INI, 4 `.pac_` de pic2d/ending, películas y eve.pkb/pkh.
- **Arreglo:** `v22/graficos_faltantes`. Se repinta con el estilo original (tres colores de la placa):
  «¡VICTORIA!», «¡TIEMPO!» y «DERROTA». No hay pieza equivalente en la 3DS europea.

## 2. Comparación byte a byte (1.605 ficheros; v03 incluido como referencia)

| Capa | Iguales | Distintos |
|---|---|---|
| v03 gráficos | 1468 | 67 |
| v05 snapshot | 1468 | 67 |
| v06 gráficos | 150 | 3 |
| v12 gráficos | 5 | 0 |
| v20 gráficos | 117 | 0 |
| v20 textos | 4 | 0 |
| v20 teclado | 2 | 0 |
| v21 tutorial (`work/ie2/tormenta_de_fuego/capas/v21/tutorial`) | 1 | 0 |

Ningún fichero falta en la candidata y no hay rutas erróneas. Las 137 discrepancias tienen una sola causa:
**una capa posterior sustituye el fichero partiendo de la salida anterior** (v05/v03 → v06, v12, v13/cro_ranura o v20
en battle_start_t). Esto afecta a 48 `.arc` de 3ddemo_technique, a los menús slot, name, title, option y connection, y a tokkun.
Por textura, las 115 texturas que alguna capa cambió están **conservadas o repintadas por una capa posterior**. **Ninguna ha vuelto al japonés.**
El detalle por fichero y por textura está en `informe.json` → `discrepancias[].texturas`.

Nota: v21/tutorial no está en `work/ie2/shared/capas/v21` sino en `work/ie2/tormenta_de_fuego/capas/v21/tutorial`.

## 3. Duplicados

Hay 22 nombres de textura repetidos en varios `.arc`. En 3 de ellos una copia está traducida y la otra no:
- `ie02_menu_form_button_b02` (wireless_member_b.arc) y `ie02_menu_form_parts_b02` (scout_b.arc): tienen el mismo nombre,
  pero son **gráficos distintos sin texto** (etiquetas FW/MF, flechas y botones). No hace falta hacer nada.
- `ie02_wireless_b_big_btn02` en `a_menu/wireless_off_b.arc` **conserva el japonés** (はい/いいえ/おわる/けってい).
  Su maqueta es distinta de la de wireless_b.arc, así que no basta con copiar el blob. **Pendiente**: repintarla en otra capa.

## 4. Otros rótulos de partido y batalla

He revisado textura a textura game_result_t/b, game_obj_b, battle_start_t/b, game_end_t/b, extra_result_b y wireless_result_b.
Todo lo que lleva texto está traducido salvo la placa del punto 1. Lo que sigue igual no lleva texto: fotos de falta y fuera
de juego, números, «LV», «NEXT», «PK» y marcos.
