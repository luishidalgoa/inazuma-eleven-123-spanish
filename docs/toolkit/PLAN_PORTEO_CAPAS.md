# Plan de porteo de los motores de capa a ie123kit

Estado (2026-09-19): **F2.4 portada** (#1, #2, #5, #6 y #7, rama `toolkit-f2.4`, #50); #3, #4 y #8
siguen pendientes para la F2.5 (tocan fuentes o la GUI). El plan se escribió al reanudar la migración en
la F2.3 (#49).

### Qué se porteó en la F2.4 y dónde quedó

| # | Motor | Módulos | Prueba de equivalencia (`requiere_rom`) |
|---|---|---|---|
| 1 | Paginado 37 × 3 / 131 B | `nucleo.texto.paginado` (`ModeloMotor`, `ajuste`, `problemas`, `repartir`, `partir_paginas`); límites en `ie1.texto.dialogo` (22 × 3) e `ie2.comun.dialogo` (37 × 3, 131 B, 247 B; `reparte`) | Punto fijo sobre todos los registros de diálogo de las 3167 salidas de `dialogo/saltos37` y comparación con `comun19`/`comun17` en una muestra |
| 2 | Parches de CRO | `nucleo.ejecutable.parches_cro` (palabra + contexto + relocalizaciones); direcciones en `ie2.comun.cro` | `menus_cro/cofres` -> `ancho_dialogo`: CRO idéntica e informe igual |
| 5 | Teclado en SPF_ | `nucleo.contenedores.spf`, `nucleo.texto.teclado` (el `patch_map` de IE1 delega en él), `ie2.comun.teclado` | Los dos `.SPF_` de `teclado/teclado/extra` desde la ROM japonesa, idénticos |
| 6 | Subtítulos incrustados | `nucleo.media.subtitulos` (dat, partición, tiempos, dibujo); estilo en `ie2.comun.subtitulos` | Pistas y fotogramas con texto de las 35 cinemáticas iguales al informe; plano Y quemado igual que `comun_sub` |
| 7 | DSP-ADPCM y sound.pb | `nucleo.media.dsp_adpcm`, `nucleo.media.procyon` (SWD/SED), `nucleo.contenedores.sound_pb`, `ie2.comun.voces` | `media/voces` (v23): `sound.pb`/`.ph` idénticos; `historial/media/v20_voces`: bancos 3D_003 idénticos; `media/voz_titulo` (v13): `3D_901.SWD` idéntico (remuestreo incluido) |

Las capas de `work/` no se han tocado (están fuera de git y la regla 2 prohíbe reescribirlas en el mismo
paso): el paquete reproduce su salida byte a byte. Los hashes de esas salidas están en
`tools/tests/compat/golden/motores_ie2.json` (solo hashes, Norma 2). Las bases de algunas capas ya no
existen (`probe_ie2_v17`/`v18`); por eso el paginado se prueba como punto fijo y el teclado desde la ROM
japonesa, que la propia capa comprobaba idéntica a su base. Cada motor tiene su orden `ie123 motor …`.

Mientras la migración estuvo pausada, el trabajo de IE1 (v82–v93) y de IE2 (v01–v34) dejó en `work/`
varios motores que hoy viven como scripts de capa. Son lógica reutilizable (IE3 los necesitará) pero
están copiados entre capas, calculan la raíz con `parents[N]` y no tienen tests fuera de su `validate.py`.
Este documento dice qué se portea, adónde, en qué subfase y con qué prueba de equivalencia.

## Reglas comunes a todo porteo

1. **Equivalencia byte a byte antes que limpieza.** Cada motor portado lleva un test `requiere_rom` que
   ejecuta la función del paquete sobre la misma entrada que la capa y exige la salida de la capa
   (`extra/`, `romfs/cro/*.cro`, `informe.json`) idéntica. Primero se captura el sha de la salida actual
   de la capa como golden (solo hashes, Norma 2); después se portea.
2. **La capa no se reescribe en el mismo paso.** Tras portear, la capa puede importar el paquete
   (`from ie123kit.nucleo.… import …`); el comprobador `nucleo.compat.importaciones` ya resuelve esos
   imports contra `tools/src`. Las capas de `historial/` no se tocan nunca.
3. **Tipografía bloqueada.** Nada de lo que toque fuentes (`font/*.bcfnt`), caja, espaciado o saltos se
   activa sin una petición explícita del usuario sobre tipografía (CLAUDE.md, AGENTS.md). Portear el código
   que *genera* las fuentes no cambia ninguna fuente, pero sus tests deben probar que la salida es la
   misma que la de la capa, no una «mejorada».
4. **Norma 4.** Antes de portear algo de diálogo/CRO se relee `docs/FURIGANA_LECCIONES.md`; el paquete
   codifica los límites medidos como constantes con su referencia (dirección, tanda, issue).
5. **Sin datos del juego en git.** Tablas con texto del juego (nombres, resúmenes de objetivos) siguen
   en `work/`; el paquete las recibe como parámetro.

## Inventario y destino

| # | Motor | Origen vigente en `work/` | Destino en ie123kit | Subfase | Riesgo |
|---|---|---|---|---|---|
| 1 | Reparto de páginas del diálogo: 37 car./línea y tope de 131 B por página (`2·car + (líneas−1) ≤ 131`), DP por costes sin cortar palabras | `ie2/shared/capas/dialogo/saltos37` (`comun19.py`), `ie2/shared/capas/historial/dialogo/v17_paginas/comun17.py` | `nucleo/texto/paginado.py` (función pura: texto → páginas con `\f`); límites en `ie2/comun/reglas.py` | F2.4 | Bajo: función pura, fácil de probar sin ROM |
| 2 | Parches de ancho de la ventana de diálogo en el CRO (inmediatos en su sitio: 0x66a24/0x4cabc → 0x1A0, 0x4d6a0 → 0x1C0; comprobación de que ninguna relocalización cubre los bytes) | `ie2/shared/capas/menus_cro/ancho_dialogo` | `nucleo/ejecutable/parches_cro.py` (motor genérico: parche de inmediato + verificación de relocs) y tabla de direcciones en `ie2/comun/` | F2.4 | Medio: toca código; el test compara la CRO de la capa |
| 3 | Registro de bigramas (par de letras → código kanji libre; solo se añade al final) y dibujo de cada código en FONT12/FONT8/FONT12T; escáner estricto de literales | `ie1/capas/fuentes/bigramas_ritmo` (`ritmo.py`, `escaneo_literales.py`), `ie2/shared/capas/nombres/nombres_compactos` (`registro.json`, `comun08.py`), `ie2/shared/capas/fuentes/fuentes` | `nucleo/fuentes/bigramas.py` (registro append-only con validación) + `nucleo/fuentes/glifos.py` (dibujo) + `nucleo/texto/escaneo.py` | F2.5 | **Alto:** produce fuentes → bloqueo v20; ver «Decisiones» |
| 4 | Glifos de menú en rebanadas (la etiqueta se dibuja como tira y se cubre con glifos existentes o rebanadas de ≤ ANCHO_CELDA columnas en códigos libres; modelo proporcional medido) | `ie2/shared/capas/menus_cro/menus` (`modelo23.py`, `apply.py`) | `nucleo/fuentes/rebanadas.py` sobre el registro del #3 | F2.5 (tras #3) | Alto: consume códigos del registro (quedan ~1) |
| 5 | Teclado de nombre en paquetes `SPF_` (LZ10; entradas FCODE0/1/2 de `MMName.SPF_` y `MMProfd.SPF_`) | `ie2/shared/capas/teclado/teclado` | `nucleo/contenedores/spf.py` (leer/escribir SPF_) + acción `teclado` en `ie2/*/acciones.py` | F2.4 | Medio: contenedor nuevo con roundtrip testeable |
| 6 | Subtítulos grabados en el vídeo (una sola codificación desde el original, QP 12; franja inferior en negro; carteles compuestos desde la NDS) | `ie2/shared/capas/media/subtitulos` (`comun_sub.py`), `ie2/shared/capas/media/media/rotulos.py` | `nucleo/media/subtitulos.py` junto a `nucleo/media/moflex.py` | F2.4 | Medio: depende de ffmpeg/mobipeg; test por hash de fotogramas, no del fichero |
| 7 | Bancos de sonido `sound.pb` (CWAV DSP-ADPCM en 3DS; remuestreo e IMA→DSP) | `ie2/shared/capas/media/voz_titulo` (`dsp_adpcm.py`, `sonido.py`), `ie2/shared/capas/media/media/bancos.py`, `shared/capas/media/voz_titulo_recopilatorio` | `nucleo/media/dsp_adpcm.py` + `nucleo/contenedores/sound_pb.py` | F2.4 | Medio: codificador; test de roundtrip y de igualdad con la capa |
| 8 | Banner y SMDH (icono y títulos de HOME; ExeFS) | `shared/capas/graficos/banner_home`, `ie1/capas/graficos/smdh` | `nucleo/contenedores/exefs.py` (ya existe, lectura) + escritura en `juego_principal/acciones.py` (hoy SMDH es solo lectura) | F2.5 | Medio: ExeFS experimental; la GUI lo necesita para el menú |

Nada de esto es trivial; por eso no se portea nada en la F2.3.

## Reparto por subfase

- **F2.3 (#49, esta rama).** Solo infraestructura: el paquete entiende la disposición `capas/<tema>/<linea>`
  y `historial/` (`nucleo.construir.capas.ubicacion` y `listar_capas`), las capas nuevas que crean las
  acciones van a su tema, el comprobador de importaciones resuelve `ie123kit` en las capas y los gates ya no
  dependen de candidatas borradas (referencia `work/shared/base_3ds` + `graficos/titulo_logo`).
- **F2.4 (#50).** Motores sin impacto tipográfico, en este orden: #1 paginado (puro), #5 SPF_, #7
  DSP-ADPCM/sound.pb, #6 subtítulos, #2 parches de CRO. Cada uno con su orden `ie123 <objetivo> …` y su
  test de equivalencia. Al acabar, las capas vigentes que los usan pueden importar el paquete.
- **F2.5 (#51).** Lo que toca fuentes o la GUI: #3 registro de bigramas y dibujo de glifos, #4 rebanadas,
  #8 escritura de SMDH/banner. Solo tras decidir el bloqueo v20 (abajo).
- **Después (#55, limpieza).** Retirar de las capas vigentes el código duplicado (`comun*.py`) ya portado.

## Decisiones que necesita el usuario

1. **Hashes del bloqueo (resuelto el 2026-09-19, #80).** El usuario autorizó actualizar las huellas a las
   fuentes de `probe_ie2_v34` («sí, actualiza las huellas a la actual versión que tiene un motor de textos de
   calidad»). `FONT_HASHES` de `tools/dialogue_lock.py` son ahora FONT12/FONT12T/FONT8 de v34 y las NFTR de
   IE1 (sin cambios); `congelados.sha256` se recapturó y los dos `xfail` se quitaron. Cualquier cambio
   posterior de fuentes vuelve a necesitar una petición explícita del usuario.
2. **Registro de bigramas agotado** (queda ~1 código libre). Antes de portear #3/#4 hay que decidir cómo
   se liberan códigos para IE3.
3. **Candidata vigente de los gates.** `golden.CANDIDATA_VIGENTE = probe_ie2_v34`. Si se borra, se cambia
   la constante y se recaptura `candidatas.sha256` (`python -m ie123kit.nucleo.compat.golden capturar`).
