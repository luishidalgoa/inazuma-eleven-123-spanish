# IE3: nombres cortos de más de 6 caracteres (análisis estático, 2026-09-26, #87)

Análisis estático, sin emulador. Offsets de fichero de la `ina_main3ogre.cro` japonesa 1.0
(`work/shared/base_3ds/romfs/cro/`). En memoria van a 0x939000 + offset. Las funciones de code.bin se citan por
su dirección virtual (`work/shared/base_3ds/code_audit.bin` = code.bin descomprimido, base 0x100000). La
comparación se ha hecho con la CRO europea de Fuego Explosivo (`work/ie3/fuego_explosivo/fuentes/3ds_eu/`).

## 1. El cuelgue: el cartel de cambio de jugador (confianza alta)

**Función:** 0x1ab388 (marco `sub sp, sp, #0x134`; guarda r4..fp y lr en sp+0x134..0x157). Prepara el texto
de un **cambio de jugador**, que el partido muestra en las paradas: descanso, después de un gol o en un fuera
de juego. Lo escribe en las cajas `this+0x490` (22 × 2 casillas).

```
1ab430  memset(sp+0x108, 0, 0x10)
1ab444  STD_CopyString(sp+0x108, unitbase+0x1C)        ; nombre corto (≤14 B + NUL: cabe)
1ab458  n = STD_GetStringLength(sp+0x108)
1ab45c  si n < 10: MI_CpuFill8(sp+0x108+n, ' ', (10-n)/2)   ; relleno con espacios ASCII
1ab490  0x175cb8(sp+0x108 -> sp+0x28 + i*0x20)          ; «hankaku -> zenkaku»: cada byte ASCII pasa a 2 B
                                                        ;   (el espacio de relleno pasa a «　» = 81 40)
1ab4d8  sprintf(sp+0x118, "%2d %-10s \x81\xa8 %2d %-10s", n1, sp+0x28, n2, sp+0x48)
1ab510  0x175cb8(sp+0x118 -> sp+0x68)                   ; salida ≤ 0x84 B antes de sp+0xec
1ab570  CFontManager::slot 2 (0x19e4c) en la caja [this+0x490+i*0x14]
```

**El búfer del sprintf mide 28 B** (sp+0x118..0x133) y justo encima están los registros guardados (r4 en
sp+0x134, r5 +0x138, r6 +0x13c, **r7 +0x140**, r8.. y lr en +0x154). El texto ocupa 10 + A + B bytes más el NUL, donde
A y B son los bytes de cada nombre ya pasado a ancho completo:

| nombres | A, B | bytes con NUL | qué pisa |
|---|---|---|---|
| japonés, 5 caracteres de ancho completo | 10, 10 | 31 | 3 B de r4 (ya ocurría en el original) |
| latino, 4-5 letras (2 relleno) | 14, 14 | 39 | r4, r5, r6 |
| latino, 6-7 letras (2/1 relleno) | 16, 16 | **43** | r4..r6 y **r7 = «　»+NUL = 0x00004081** |
| latino, 8-9 letras | 18, 18 | 47 | hasta r8 |
| latino, 14 letras | 28, 28 | 67 | hasta sb, sl |

Con dos nombres de 6-7 letras, el texto termina con el «　» del relleno en sp+0x140..0x141 y el NUL en 0x142. El
byte alto del r7 original ya era 0, así que queda **r7 = 0x00004081**, exactamente la firma del cuelgue. El r7
dañado vuelve al dibujo por fotograma, que hace `ldr r0, [r7]` en 0x28ee74 y llama a `BuildTextCommand` con
`this` = 0. Un nombre de 6 letras («Spires») rompe igual si el otro nombre del cambio también tiene 6-7 letras.
Si solo uno de los dos es largo, el NUL cae en el byte bajo de r7 y el puntero puede seguir siendo válido. Por eso
la bisección vio el fallo solo en los nombres de 7 o más.

- **Bigramas (v17):** un código kanji de 2 B no se convierte y cambia A y B. La corrupción llega a otros registros
  guardados, y de ahí la otra firma (objeto nulo en `BuildTextCommand` 0x1a1368, PC = 0 desde
  `blx [font->vtbl+0x48]` en 0x224028).
- **Europa** reescribió esta función (EU 0x1b5d38..0x1b60c4): marco de 0x24c B, búferes de 0x40 B, sin pasar
  a ancho completo, relleno a 12 y tres textos separados («%2d %-12s», «%s», «→»).
- El IE1 y el IE2 no tienen este formato.
- La hipótesis anterior (`bufer_rubi`: el pintor con furigana desborda) no explica este caso. La v16 ya tiene los
  dos pintores ampliados y esta función sin tocar.

### Parche propuesto (sin código nuevo): `ie123kit.ie3.comun.cartel_cambio`

El marco crece 0x80 B y el sprintf escribe en esa zona nueva (sp+0x134, 128 B; con dos nombres de 14 letras
hacen falta 67 B). No hay argumentos en la pila y ningún otro acceso llega a sp+0x118. Al aplicar se comprueba toda
la función y se exige que ninguna palabra coincida con las tablas de relocalización (`parches_cro.aplicar`).

| offset | antes | después | |
|---|---|---|---|
| 0x1ab394 | `e24ddf4d` sub sp, sp, #0x134 | `e24ddf6d` sub sp, sp, #0x1b4 | marco |
| 0x1ab3cc | `e3a02018` mov r2, #0x18 | `e3a02080` mov r2, #0x80 | borrar el búfer nuevo entero |
| 0x1ab3dc | `e28d0f46` add r0, sp, #0x118 | `e28d0f4d` add r0, sp, #0x134 | memset |
| 0x1ab4d0 | `e28d0f46` add r0, sp, #0x118 | `e28d0f4d` add r0, sp, #0x134 | destino del sprintf |
| 0x1ab4dc | `e28d0f46` add r0, sp, #0x118 | `e28d0f4d` add r0, sp, #0x134 | origen de la conversión |
| 0x1ab5f0 | `e28ddf4d` add sp, sp, #0x134 | `e28ddf6d` add sp, sp, #0x1b4 | marco |

La función se localiza por su prólogo (firma de 20 B, única), así que el parche vale también para la 1.4 si el
prólogo no cambia. Pruebas: `tools/tests/unidad/test_ie3_cartel_cambio.py` (sintética) y
`tools/tests/requiere_rom/test_ie3_cartel_cambio_oficial.py` (CRO japonesa local). **No se ha aplicado a
ninguna candidata.**

Los demás búferes de la función ya aguantan 14 letras: el nombre en sp+0x108 (16 B, 14 + NUL), el paso a ancho
completo en sp+0x28/0x48 (32 B, 28 + NUL) y la conversión final en sp+0x68 (132 B libres, como mucho 75).

**Queda por ver:** el texto convertido de dos nombres de 7 letras son unas 25 casillas de ancho completo, frente a
las 19 del japonés, y la caja mide 176 px. Puede partirse en otra línea o salirse de la caja: es visual, no
corrompe memoria (véase el apartado 2).

## 2. Letras sueltas en las placas: la caja de texto de 64 px (confianza media)

- El motor 1 (`CFontManager` slot 2, 0x19e4c) pinta cada carácter en su casilla de 0x20 B (8×8, 4 bpp), en
  secuencia (`r7 += 0x20` en 0x1a80c), y llama a `DrawTextHintOnVram` con la posición (x, y).
- **Corte de línea:** en 0x1a560, si x + avance > ancho de la caja (arg `sp+0xe8`), llama a 0x173a98 (nueva línea):
  el 7.º carácter baja a la línea siguiente, que cae fuera de la placa.
- **Sin desbordamiento de memoria:** hay un tope por carácter (0x1a608: casilla + 0x20 > base + ancho × alto / 2
  → fin).
- La reserva de casillas (0x1a198) cuenta `strlen/2` casillas, porque supone 2 B por carácter; con latín reserva
  la mitad. Tampoco desborda: cada casilla ocupada queda marcada y el tope anterior sigue valiendo.
- **Cajas de nombre `this+0x440`** (4 por equipo): el constructor 0x1acad8 hace `0x163394(obj, 8, 2)`, es decir
  8 × 2 casillas (64 × 16 px, 0x200 B), y el dibujo 0x1ace90 le pasa `W = 0x40, H = 0x10` con el texto
  `unitbase+0x1C`. La copia a VRAM (0x1a8af4) va de 0x200 en 0x200 B. En el mapa BG (0x1aa180) el ancho es 8.
- **Europa** conserva la caja de 8 × 2 (0x1b75c4), pero para nombres de 9 bytes o más:
  - pinta con W = 0x50 (0x48 si no; EU 0x1b4e0c-0x1b4e24);
  - ensancha el mapa BG de 8 a 10 casillas (EU 0x1b4578-0x1b458c);
  - reinicia el estado del sistema de texto con x + 2 (EU 0x1b4fc0-0x1b5118).
- **No se propone parche aquí todavía.** Ensanchar la caja mueve la distribución de VRAM (0x200 por jugador,
  seguido de 0x540 y 0x2c × 0x20 en 0x1a8a40-0x1a8c90) y el mapa BG que pinta las placas. Hace falta confirmar en
  juego que esta es la pantalla de la alineación (hay otros 43 llamadores de 0x163470) antes de tocar
  tamaños. Candidato mínimo, como el europeo: W 0x40 → 0x50 en 0x1ace90 (`e3a00040` → `e3a00050`) y el ancho del
  mapa 8 → 10 en 0x1aa180 (`e3a01008` → `e3a0100a`). Así caben 10 casillas en lugar de 8, no 14.

## 3. Placa de nombre del partido (`ply_name.ctpk`): corte a 8 bytes (confianza media)

- 0x26860: si `strlen(nombre) > 8`, lo copia a sp+0x38 y pone un NUL en sp+0x40. Así el nombre se **trunca a 8
  bytes** y no hay desbordamiento.
- Después lo centra en 40 px (0x268a4 `rsb r0, r0, #0x28`) y fija el panel a 0x28 × 10 (0x24584 `mov r3, #0x28`).
- Europa no trunca (EU 0x29c7c), centra en 0x30 o 0x38 (EU 0x29ca4) y da al panel 0x30 o 0x38 (EU 0x27b60).
- Parche mínimo posible:
  - `cmp r0, #8` → `cmp r0, #0xe` en 0x26864 (`e3500008` → `e350000e`), para no truncar;
  - `rsb r0, r0, #0x28` → `#0x38` en 0x268a4;
  - `mov r3, #0x28` → `#0x38` en 0x24584.
- **Queda por comprobar:** que el panel y la textura `ply_name` admitan 56 px sin pisar al jugador de al lado.

## Descartado

- `sjis_to_utf8` (0x1a0f4c): acotado por la capacidad. Tiene un fallo aparte: el espacio ASCII 0x20 se escribe
  como E3 80 80 pero **resta** 3 al contador (0x1a1004). No afecta, porque los nombres usan 0x8140.
- `DrawTextHintOnVram` (0x1648f4): copia como mucho 7 B + NUL a la casilla (0x14e394).
- `BuildTextCommand` y `DrawTextPrimitive`: 0x200 órdenes de 0x100 B, acotadas.
- 0x1320a8: rellena con «　» hasta 5 caracteres de ancho completo y se salta los nombres de más de 5 (acotado).
- Motor 1 0x19e4c: casillas acotadas por el tope de 0x1a608; su efecto es visual (apartado 2).

## Qué comprobar en el emulador (con el parche del apartado 1 aplicado a una candidata)

1. Nombres cortos latinos sin acortar (7-14 letras). Jugar un partido con cambios automáticos y llegar al
   descanso; marcar un gol y provocar un fuera de juego. **No debe colgarse.**
2. Cartel de cambio: que se lean el número y el nombre de los dos jugadores, y si el texto largo se parte o se sale
   de la caja.
3. Por separado (apartados 2 y 3): letras sueltas en la alineación y en las placas del partido. Anotar la pantalla
   exacta para decidir si hay que ensanchar la caja `+0x440` o la placa `ply_name`.
