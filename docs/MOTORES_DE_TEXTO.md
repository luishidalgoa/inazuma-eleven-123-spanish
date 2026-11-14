# Motores de texto del juego (IE1, IE2, IE3)

Inventario de los caminos por los que el juego dibuja texto: qué función lo hace, qué pantallas la usan y qué capas la tocan. Sirve para decidir qué codificación y qué ancho por letra son posibles en cada campo.

Estado: documentación estática, con una comprobación en juego (Supertécnicas, 2026-11-10). Etiquetas:
- **[verificado]**: leído en el código o en los bytes de esta sesión.
- **[prueba]**: confirmado por el usuario en el juego.
- **[doc]**: viene del docstring o del informe de una capa; no se ha vuelto a comprobar.

## IE3 (Amenaza del Ogro, `ina_main3ogre.cro`)

### Resumen de motores y zonas

| Motor | Dirección (`ina_main3ogre.cro`) | Qué dibuja | Avance por letra | Capas que lo tocan |
|---|---|---|---|---|
| **M1 · Pintores con furigana** | `0x17fc4c` (53 llamadas), `0x181370` (29), copia `0x23fd0` | Descripciones de objetos, tácticas, técnicas, jugadores y **Supertécnicas**; avisos en ventana; blog | Los del motor que dibuja (M3/M4) | `copia_1byte`, `descripciones_256` |
| **M2 · Motor de texto 2** | `0x19e4c` + DELTA2 (vtable+8 del gestor FONT12) | Ficha del Registro, placas de nombre, objetivos, textos con bigramas/piezas | `FontGetCharWidth(tipo)` (FONT12 12, FONT8 8, FONT12T 12, RUBI 4) salvo ancho forzado > 0 | `ficha_registro_proporcional` |
| **M3 · Motor de texto 1** | `0x180880` + DELTA1 (`0x1808f0`: avance por defecto del ITX) | Diálogo y texto general de menús | Modo DS: `redondeo(avance BCFNT / escala)` por letra; ITX123 por defecto (FONT8 6/7, FONT12 10 arriba) solo para textos con bigramas | `ficha_registro_proporcional`, `font12_proporcional` (sustituida), `font8_proporcional` |
| **M4 · DrawTextPrimitive** | `code.bin 0x164764` | Texto de maquetas (paneles) | `G+0xeef6c` (ancho fijo del último dibujo) a la pista de cada texto | `ficha_registro_proporcional` (lo pone a 0 antes de cada llamada) |
| **Medidor de ancho** | `0x16f554` (25 llamadores) | Mide el texto para centrarlo | Ancho real con `r2 ≠ 2`; fijo con `r2 = 2` | `medidor_ancho_real`, `nombres_casilla_resto` |
| **Centrado genérico** | `0x17fb4c` (53 llamadores), `0x18126c` (29) | Centrado de nombres y rótulos | `0x17fb4c`: `r2 = 0`, sin tope | — |
| **Ventana de diálogo** | `0x3a754`, ancho 0xF0 | Diálogo de la historia | Proporcional, reparto por ancho de ventana | **Bloqueo v20: no se toca** |
| **Campo de nombre / teclado** | `0x19a770` | Casillas de nombre | Paso fijo del ITX, letra centrada en su casilla | `ficha_registro_proporcional` |
| **Caja de partida** | `0x152edc` → `0x1526a0` / `0x1526a8` (búfer 224×128) | Pantalla de partida | `G+0xeef6c = G+0xeef7c = G+0xeef4c = 0` antes de cada dibujo (rutina `0x29bfd4`) | `ficha_registro_proporcional` |
| **Objetivos** | `0x83764` / `0x83788` | Rótulo de objetivo | `G+0xeef60` 480 → 608 (corte a 389 px) | `ficha_registro_proporcional` |

[doc] salvo lo indicado en M1. Las direcciones y el reparto de motores vienen de los docstrings de las capas; no he vuelto a ejecutarlos.

### M1 · Pintores con furigana (`0x17fc4c`, `0x181370`, copia `0x23fd0`)

- **Qué hace:** copia el texto con `0x23fd0` a un búfer de pila de 256 B (el título de arriba, 152 B), separando la furigana `[base/lectura]`, y dibuja la copia. [doc: `textos_logic/comun.py`]
- **Antes de `copia_1byte`:** `0x23fd0` descartaba los bytes 0x20–0x7E, así que el latín de 1 byte no se dibujaba y todo campo que pasaba por aquí iba en ancho completo.
- **Con `menus_cro/copia_1byte`:** la copia deja pasar los bytes 0x20–0x7E (14 palabras en `0x24018`–`0x24050`). [verificado: la secuencia parcheada está en la CRO del mod 6f5f7c76 y en `paquete_final` 28C27F83, y **no** está en la CRO original del EU.] Con ella, el texto en latín de 1 byte con portadores (`comun.b1`) se ve en estos pintores. [prueba: las Supertécnicas en 1 byte se ven bien, 2026-11-10.]
- **Quién lo usa:**
  - Descripciones de objetos, tácticas, técnicas y jugadores: `textos_logic/objetos`, `tacticas`, `tecnicas` y `fichas`, con tope de 255 B (búfer de 0x100 por `descripciones_256` y `ficha_descripcion_256`). Estas capas fijan hoy `solo_fw=True` (ancho completo) por una regla anterior a `copia_1byte`. Con `copia_1byte` el 1 byte también pasaría.
  - **Supertécnicas** (Datos → Supertécnicas): variante `--un-byte` de `textos_logic/supertecnicas_oficial`. [prueba]
  - Mensajes con furigana de la ventana de menú (`menus_cro/menu_campo`, ventana H): `0x14fb18 → 0x90bc → 0x181370 → 0x23fd0`. `menu_campo` ya escribe en 1 byte.
  - Blog oficial (`blog/oficial`): llama a `0x17fc4c`.
- **Riesgo declarado por la capa:** un texto con bytes 0x20–0x7E que el juego no debía dibujar (por ejemplo un espacio de 1 byte entre palabras japonesas) ahora se dibuja. [doc]

### Lector de punteros de `sp_binder` (sin localizar)

- Dato: `sp_binder.dat` (registros de 12 B, `f5` = desplazamiento en bytes) y `sp_binder.STR` (cadenas con NUL). El japonés llega a 32 755 B de inicio máximo, justo bajo 0x8000. Con el EU en 1 byte, el STR mide 25 985 B.
- La capa de contactos documenta un `ldrsh` en `0x1b62d4`. [verificado: **no es el lector**; es un bucle de 5 entradas de 12 B que llama a `0x17e3c4`, la liberación de la estructura.]
- En la CRO de Ogro hay 55 `ldrsh [x,#0xA]` y ninguno aparece en un bucle ×12. `ina_menu.cro` no tiene ninguno. El nombre `/logic/sp_binder` está en la CRO (desplazamientos `0x1bea58` y `0x2b5f6c`), pero nada lo referencia ni con puntero absoluto, ni con desplazamiento, ni con `add rX, pc, #imm`. Una prueba con breakpoints en el emulador no fue fiable (el stub de Azahar paraba en direcciones ajenas). El lector no está localizado. [verificado]
- Consecuencia práctica: el tope de 0x8000 sigue siendo una suposición; en 1 byte no importa.

### Diálogo de eventos con marcadores de furigana (`%NF`)

- Es el texto de los eventos (`eve.pkb`, `evet.pkb`). El motor exige un número fijo de caracteres de ancho completo tras cada marcador `%NF`. Un marcador con 1 byte desalinea el motor y cuelga el juego. [doc: `docs/FURIGANA_LECCIONES.md`, líneas 259–282]

## IE2 (Tormenta de Fuego, `ina_main2.cro`)

### E1 · Motor 2 (FONT12, vtable+8 del gestor): `0x334b8`
- Dibuja el texto de los menús y de los blogs. El avance por letra sale de la tabla ITX123 (11 DS fijos) salvo que la bandera `G+0xeef78` esté a 1 (avance proporcional) o que `[gestor+0x28]` o `[r3+8]` sean distintos de 0. [verificado con unicorn en el análisis de la pachanga]
- Modo «_2» (`G+0xeef7c`): escala 1,5625; el avance efectivo es `round(CWDH/1,25) − 2` en el modo de glifo. [verificado en el análisis del Inablog]
- **Usado por:** Inablog (`0x15eb6c` título, `0x15ed84` cuerpo, `0x15e868` comentario, vía el utilitario `0x120a24`), pantalla previa de pachanga (`0x17b6d4`), menús de campo y franja de equipo (`cro_menu_franja_ie2`, `cro_textos_ie2_fase4`).
- **Bandera `G+0xeef78`:** la leen o escriben 14 sitios fuera de la pantalla previa (0x4d8f0, 0x76b04, 0x8a774, 0xc9a24, 0xe11e8, 0x121c1c, 0x1229f0, 0x189578, 0x18977c, 0x19db24, 0x19dd30, 0x1d9414, 0x1d95cc, 0x1f02a0). [verificado]

### E2 · Motor 1: `0x121bac`
- Mismo patrón con la bandera ≠ 0 que E1, 59 llamadores. No se toca. [verificado]

## IE1 (Inazuma Eleven 1, `ina_main1.cro`)

- **Motor unificado de diálogo:** `ie1/capas/dialogo/motor_unificado` (ver `docs/ARQUITECTURA.md`, línea 84). [doc]
- **Inablog:** modo 0 (escala 1,25), separación 0, tope 176 px DS (capa `blog_ie1_oficial_v3`). [verificado en la capa]
- **Pachangas:** utilitario `0x12cef4`, y `0x12cf60` en v2; la capa v3 añade la cueva `0x198500`. [verificado en la capa]

## Problema conocido: letras desalineadas y demasiado juntas en el texto de IE3

Reportado por el usuario el 2026-11-10 (descripción de supertécnica en Datos → Supertécnicas, captura `33.png`). **Medido el 2026-11-10** con la captura, las fuentes, el código del motor (unicorn) y los parches de la CRO instalada (sha 6f5f7c76). Estático; el cambio propuesto **no está aplicado ni probado en juego**.

**Letras demasiado juntas: causa confirmada, el «−2» del motor 2.**
- Supertécnicas pasa por el pintor `0x17fb4c`, que llama a la vtable+8 del gestor (motor 2). Ahí cada letra avanza `round(w/1,25) − 2` baldosas más 1 de espaciado, es decir, `1,25·(round(w/1,25) − 1)` px. Ejecutado con unicorn sobre 75 letras reales: 75 de 75 siguen esa fórmula. [verificado]
- Resultado: dentro de las palabras, cada letra avanza de media 0,98 px menos que su ancho BCFNT. En la línea de ejemplo, 32 de 45 pares de letras tienen la tinta solapada (la «i» pisa la «r» de «rivales»). [verificado con la captura]
- La palabra está en `0x1a548` de la CRO instalada (`a24aa002`, `subge sl, sl, #2`); en coordenadas 1.0 es `0x1a550`, donde la capa `ficha_registro_proporcional` la llama `DERIVA`. [verificado en el fichero]
- **Corrección del revisor:** el efecto está **dentro de las palabras**. Los espacios avanzan unos 6 px (no 1,25 como daba la simulación), así que la línea entera mide ≈172 px frente a 180 de ancho BCFNT (−4 %), no −18 %. La simulación no reproduce el avance del espacio (hay funciones del ejecutable sustituidas por stubs).

**Letras que no se mantienen rectas: casi no existe; hay dos causas menores.**
- 47 de 49 letras medidas están a menos de 0,5 filas del modelo; en la 2.ª línea no hay ninguna desviación. [verificado]
- La «a» y la «s» de la FONT12 instalada llevan tinta fuerte una fila por debajo de la base (arte del EU subido una fila): quedan unas 0,4 filas más bajas que c, e, o, d. Otras 13 letras llevan una fila tenue. [verificado]
- La «o» y la «n» de «con» bajan una fila en esa línea. Caso aislado sin causa conocida.

**Descartadas:** el avance en rejilla del motor 1 (Supertécnicas no pasa por él) y los portadores de tilde (comparten hoja, celda, base y ancho con su vocal; solo la «í» y la «Í» cambian de ancho).

**Cambio mínimo propuesto (no aplicado):** `0x1a548`: `a24aa002` → `a24aa001` (`−2` → `−1`). Deja el avance en el ancho BCFNT ±0,5 px y quita el solape. Efecto secundario esperado: las líneas crecen. Con los espacios reales, la línea 1 pasaría de ≈172 a ≈207 px, en el tope del rango de las líneas japonesas de esa caja (182–208 px).
- Afecta a todo texto que llegue a esa rama del motor 2 con el modo «_2» y `G+0xeef54 = −100`. Solo está ejecutado el caso de Supertécnicas; objetos, tácticas, técnicas, jugadores, avisos y blog son inferencia por el reparto de motores.
- **Riesgo principal:** la ficha del Registro, para la que la capa se diseñó con el «−2» y de la que no hay captura.
- No usar `--sin-deriva` (equivale a −0): las líneas se irían a ≈230 px.
- Es un cambio de tipografía: requiere petición explícita del usuario.

**Sin comprobar:** qué otras pantallas pasan por esa rama; el efecto en la ficha del Registro; dónde se escribe el espaciado `mgr+0x14`; si las líneas de la traducción se ajustaron al avance actual. Más cosas menores en el informe del análisis.

## Recomendación: ¿un solo motor o los mismos siempre que se pueda?

- **Un camino por tipo de texto, el mismo que ya usa el juego.** Las descripciones largas (objetos, técnicas, jugadores y Supertécnicas) pasan por M1: conviene que todas usen el mismo códec (1 byte con portadores, ahora que `copia_1byte` está) y el mismo tope de 255 B. Así los arreglos de la copia y del búfer valen para todas a la vez.
- **Arreglar el espaciado una vez, en el motor, no pantalla por pantalla.** Si la causa es el avance en rejilla (candidata 1 o 2), un solo cambio en el motor 3 cubriría las descripciones, el blog y los avisos. Hacerlo por campo repetiría el trabajo y dejaría pantallas distintas entre sí.
- **No forzar a todos los textos por el mismo motor.** El diálogo (bloqueo v20) y los campos de rejilla fija (casillas de nombre, teclado, rótulos de baldosas) necesitan otro avance. Mover esos a un motor distinto cambiaría su geometría.
- **Antes de cambiar nada global, medir.** Un cambio en M3 afecta a todo el texto FONT12/FONT8 superior (lo dice la propia capa `font12_proporcional`). Hay que probarlo con una captura de cada zona de la tabla de arriba.

## Huecos pendientes

- Medir en el motor real la causa del espaciado y la desalineación (arriba).
- Confirmar qué pintor usa exactamente la pantalla Datos → Supertécnicas (M1 o la copia `0x181370`): funciona, pero no está identificado el lector.
- Las capas `objetos`, `tacticas`, `tecnicas` y `fichas` siguen fijando ancho completo; revisar si conviene pasarlas a 1 byte ahora que `copia_1byte` está.
- Motores E1 y E2 de IE2 solo documentados en los informes de sus capas; no hay inventario completo de sus llamadores.
