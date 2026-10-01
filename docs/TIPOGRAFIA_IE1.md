# Tipografía IE1: NFTR y BCFNT

## Evidencia reproducible — 2026-09-05

- El CRO original contiene referencias a `data_iz/font/FONT12.NFTR`, FONT8,
  FONT12T y RUBI8. Estos archivos existen dentro del archivo original.
- `ie123kit._legado.nftr_metrics` permite leer sus mapas y avances sin modificar datos.
  Los códigos de su mapa son Shift-JIS. En FONT12 las letras ASCII a/i/m/n/t/W
  no están mapeadas; sus equivalentes latinos de ancho completo sí, con avance 11.
- FONT12.bcfnt contiene ambos repertorios. Los avances ASCII son variables
  (a=9, i=4, m=13); las equivalentes de ancho completo avanzan 14.
- Las capturas de la candidata v2 muestran espaciado irregular. La participación
  exacta de ambas fuentes en el cálculo runtime sigue pendiente de trazado; la
  diferencia anterior no prueba por sí sola la causa del solapamiento.

## Experimento v3

`build_ie1_probe.py --fullwidth` utiliza el repertorio latino de ancho completo
mediante `dialogue_typography.py`. Conserva controles ASCII de salto/página y
marcadores, falla ante caracteres no codificables y mantiene el límite de 247
bytes del registro. Los acentos portadores usan ahora la base de ancho completo.
El ajuste provisional es de 20 columnas y tres líneas por página. No representa
una medición definitiva del máximo ancho útil del motor.

FONT12T.bcfnt tiene formato 9 y un byte por píxel según la geometría de su hoja;
el editor antiguo asume medio byte por píxel en todas las fuentes. V3 conserva
FONT12T original en lugar de aplicar ese editor incompatible. FONT12 y FONT8
tienen formato 11 y la geometría de cuatro bits usada por el editor.

Candidata local: `work/shared/candidatas/probe_ie1_v3/archive.fa`, SHA-256
`7d3dd8e883733d036e2fa7b76ef31464022004dc23fab74975590dc0817b4589`.
Instalada con Azahar cerrado. Verificados 15 diálogos y bytecode intacto;
92010250 registros 8 y 25 quedan originales por longitud. Siete pruebas de
codificación/ajuste pasan. Regresión visual pendiente: repetir todo el club,
especialmente la frase sobre entrenamiento, las tildes y los cambios de página.

Objetivo solicitado: convertir los hallazgos en herramientas documentadas para
edición comunitaria. Publicar código y documentación, nunca fuentes o ROMs.
No afirmar que el trabajo es el primero de su tipo sin investigar antecedentes.

## Capturas v3 y candidata v4

El usuario confirma mejora en v3 y aporta capturas sin los solapamientos
anteriores, aunque con separación excesiva. No equivale a validar todo el juego.
`compact_typography.py` prepara una reducción conservadora de los avances
BCFNT y los correspondientes NFTR. Respeta ancho de glifo más margen; no cambia
el dibujo de letras normales. FONT8.NFTR queda byte-idéntico porque los avances
calculados redondean a los originales. La reducción todavía requiere prueba.

V4 SHA-256: `c0b7c1d944db669fa7c275f7bb415230cdc30807f466a6c9a1e2390d864b24d9`.
Incluye 34 textos, nombres cortos/lecturas de 15 personajes iniciales y los
rótulos iniciales de lugar y objetivo. La revisión de NPC se limita a registros
identificados de 81000040 y 91010000, no a traducir indiscriminadamente esos eventos.
En 81000040 se conservan el bytecode completo y los registros 119/120 que nombran
los recursos del modal. Falta verificar en juego apertura, cierre y recuperación
del control. Dos frases de 92010250 siguen originales por tamaño y 21 registros
de 92010300 no encuentran traducción exacta en el cargador actual.

La comparación del archivo completo detecta seis recursos modificados:
eve.pkb/pkh, FONT12/8.bcfnt, FONT12.NFTR de IE1 y unitbase.dat de IE1. Todos los
demás recursos son idénticos al original. No se han cambiado archivos de vídeo.

### Edición revisada por registro

El generador acepta `--reviewed-json` con `records` (mapa de evento a filas con
`index`, `source_sha256` del registro original completo, `text` y `wrap`) y
`reviewed_only` (eventos donde solo se aplican esas filas). Falla ante un hash
distinto o índice inexistente. `--extra-files` acepta un directorio local con
rutas ya existentes dentro de archive.fa y registra sus hashes. Los manifiestos
con traducciones y los recursos binarios se conservan en work, fuera de Git.

## Candidata v8: métricas latinas nativas

Las capturas de v7 aún mostraban letras separadas. La comparación de FONT12
confirma que los glifos latinos normales y los de ancho completo usan los mismos
dibujos, pero no los mismos avances: por ejemplo, i avanza 4 píxeles en el
repertorio normal y 14 en el transportado.

compact_typography.patch_pair con mode=native copia el trío
left/width/advance del glifo latino normal a su equivalente de ancho completo
en BCFNT. En NFTR calcula la métrica correspondiente a su escala, conservando
los offsets, mapas y tamaño del archivo. Los rodamientos negativos se tratan
como valores con signo; la prueba incluye j además de i para impedir que se
salte esa ruta.

La candidata local v8 usa este modo en FONT12 y FONT8. El ejemplo de frase que
tenía 645 píxeles de avances BCFNT con el repertorio japonés pasa a 457 sin
alterar los bitmaps. FONT12T sigue intacta: su formato no es compatible con el
editor de cuatro bits. La validación estática y las pruebas unitarias pasan,
pero la aceptación queda pendiente de comprobar en Azahar que no haya
solapamiento, cortes ni cambios de página incorrectos.
