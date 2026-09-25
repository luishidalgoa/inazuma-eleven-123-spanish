# Hallazgo: longitudes de registros SSD de IE1

2026-09-05. Validación sobre la CIA aportada, programa CTR-P-AETJ.

La tabla inline de texto NO es una lista de cadenas delimitadas solo por NUL.
Cada registro empieza con `<u16 instruction_id, u8 argument_number, u8 size>`.
`size` incluye los cuatro bytes de cabecera, texto, NUL y padding hasta múltiplo
de cuatro. El máximo representable con esa alineación es 252 bytes, dejando hasta
247 bytes de contenido. Cambiar la longitud de la frase exige cambiar este byte.

La cabecera SSD contiene `instSize` (longitud del código, sin cabecera de 32 bytes),
`textCount` y `textSize`. La tabla empieza en `32 + instSize`.

## Evidencia local

- 1.240 eventos SSD de los 1.293 registros del paquete IE1 llevan la firma
  `SSD\0`; otros 53 conservan exactamente la misma cabecera y tabla, pero la
  extracción omitió esos cuatro bytes iniciales. Ambos formatos se recorren con
  `textCount` y las longitudes inline; no se descartan como texto no estructurado.
- `ie123kit.nucleo.eventos.ssd` lee y reescribe ambos formatos SIN cambios byte por byte.
  En la variante sin firma conserva los cuatro bytes iniciales originales. También
  comprueba todos los índices String de las instrucciones.
- Algunas instrucciones reutilizan índices: el dueño almacenado en un registro
  no tiene por qué coincidir con cada instrucción que lo referencia.
- El reinsertor antiguo, aplicado a 92010100 con diez traducciones y crecimiento,
  produce una tabla inválida: el parser detecta `unterminated text` porque el
  terminador ya no está dentro de la longitud original del registro.
- Algunos prefijos basura del CSV (`$`, `@`, etc.) son el byte de tamaño pasado
  equivocadamente al decodificador Shift-JIS. Las lecturas ruby son argumentos
  String adicionales del diálogo, no cadenas flotantes separadas sin estructura.

Esto invalida la afirmación de que aquellos archivos eran estructuralmente
correctos tras crecer. NO demuestra por sí solo que cada crash o defecto visual
esté resuelto. Las lecciones históricas conservan valor como casos de regresión.

## Implementación experimental

`tools/build_ie1_probe.py --events 92010100 92010200 92010250` produce un archivo
LayeredFS local en `work/probe_ie1/archive.fa`, con informe de hashes y rechazos.
Traduce únicamente el argumento 1 de opcode 0x301d en los eventos elegidos y añade
los glifos españoles. Conserva las instrucciones, índices, lecturas ruby y demás
archivos. Quita los marcadores ruby de las frases españolas y actualiza el tamaño
de sus registros. El comportamiento debe verificarse en Azahar.

La primera candidata usó 34 caracteres por línea: las capturas del usuario
confirmaron cortes dentro de palabras en el club (QA-001). La segunda usa los
avances de FONT12, un presupuesto conservador de 132 píxeles y tres líneas por
página. Este presupuesto requiere regresión visual; no demuestra que el motor
aproveche todo el ancho de la caja. Rechaza frases
que no caben en el registro en lugar de cortarlas. La primera prueba rechaza una
línea de 92010250 por superar 247 bytes; queda original hasta resolverla.

El pipeline antiguo permanece disponible para comparación. No usar sus
validaciones por offsets como prueba de validez de este formato.
