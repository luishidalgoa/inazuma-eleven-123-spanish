# Notas de pendientes (v03/graficos)

## Teclado kana (name_b) y tabla fcode
- IE1 tiene `inazuma1/data_iz/fcode0..2.txt` (314 B, 26 celdas x 6 filas + CRLF) sueltos en archive.fa.
- IE2 NO tiene `fcode*.txt` en `inazuma2/data_iz/` (solo SCRIPTINFO, MCSFILE, ROM_TIME, DEBUG_*, INAZUMA.INI, EVENTINFO).
- Los fcode de IE1 difieren de cualquier fichero IE2, así que la tabla de IE2 estará incrustada en
  `romfs/cro/ina_main2.cro` (o se reutilizan los de inazuma1). Hay que localizarla en el CRO buscando la
  secuencia SJIS de la primera fila (あいうえお...) antes de tocar `ie02_menu_name_b_font_hira01/kana01`.
- Hasta entonces el teclado queda en japonés (la celda IE1 del teclado se aceptó solo parcialmente y
  la textura se excluye por cobertura incompleta).
