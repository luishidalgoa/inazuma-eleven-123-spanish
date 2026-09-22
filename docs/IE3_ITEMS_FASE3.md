# IE3 — nombres de objetos (`item.dat`)

El consumidor CRO `0x178284` toma un índice `u16` del mapa `r0+0x7FC` y accede
a la tabla de `r0+0x7D8` con paso 44. Por tanto el contrato conserva la fila
física JP: los 1024 registros se comparan por el mismo índice, con metadatos
únicos como prueba adicional; no se alinea por nombre ni por `.STR`.

`items.py` reproduce el descifrado de `0x17DA4C`: XOR `AD`, ROR2 y los
intercambios primero/último de grupos 3, 5, 7 y 2; la escritura invierte el
orden. La tabla descifrada es `1024 × 44`: nombre NUL de `[0:28]`, metadatos
opacos `[28:44]`. El módulo exige NUL en todos los nombres antes de crear la
lista Unicode completa para el pool consumido por `%s`/`4099`.

Solo copia un nombre oficial no vacío, codificable y de menos de 28 bytes si
`[28:42]` (icono/tipo/efecto) es único en **ambas** tablas y está en la misma
fila física. El `u16` final `[42:44]` varía regionalmente; se infiere que es un
identificador regional, pero esta fase no atribuye su inicialización concreta al
mapa `+7FC`. Se conserva siempre del registro JP. No copia ni normaliza
metadatos. Después reofusca y descifra de nuevo cada registro; el
informe contiene aplicados, omisiones, lista de pool y prueba de cola/roundtrip.
`item.STR` queda fuera: solo se inventarió y no se presupone que use esta
ofuscación ni que comparta su contrato.

El informe final encuentra 793 identidades `[28:42]` unívocas y comunes en
Spark y 796 en Ogre. Sustituye el recuento preliminar que atribuía 796 a ambos;
la coincidencia de metadata tampoco basta sin comprobar la fila. Quedan 231 filas Spark y
228 Ogre fuera por identidad; se aplican 786 y 789 nombres respectivamente,
con cuatro vacíos, un fallo de encoding y dos ya idénticos por perfil. Todos
estos recuentos usan las 1024 filas físicas, no mensajes de diálogo.
La copia conserva el ID JP incluso cuando el `u16` final europeo es
distinto. La búsqueda de llamadas a `17DA4C` encuentra consumidores de 44 B
(`0x2C`, la ruta de objetos) y de 72 B (`0x48`), pero ninguna llamada de 32 ni
128 B que demuestre que `item.STR` usa la misma transformación. Por eso no se
emite ni modifica esa tabla de descripciones.

El informe expone `pool`: las 1024 cadenas visibles post-salida, con bytes,
longitud de glifos y cota de tinta. Para nombres modificados usa el Unicode ES
original aunque el payload use portadores del FONT v7; el latín se mide con el
avance FONT12 aprobado y cualquier Unicode no conocido usa 14 px. Incluye hashes
canónicos de pool y payload, y exige el máximo de 27 bytes más NUL para el pool
que consumirá `4099`/`%s`.
