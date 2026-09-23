# IE3 — identidades oficiales por consumidor

## Problema

La clave histórica `(evento, texto JP)` no identifica una intervención. En
Ogre, los eventos `36134726` y `36134727` contienen ambos `それじゃ　やめますね。`
en la instrucción `1232`, pero el corpus también reúne otra fila igual con una
traducción distinta. Elegir una fila por texto, offset entre idiomas u orden de
CSV no es seguro.

## Regla implementada

`ie123kit.ie3.comun.identidades.resolver_overrides_por_identidad` emite un
override solo si, dentro del mismo evento:

1. existe una instrucción `301D` oficial con el mismo ID;
2. opcode y la tupla completa de tipos de argumento coinciden;
3. hay un consumidor común anterior y otro posterior, con firma igual, y la
   fuente oficial permanece entre esas mismas anclas en orden de bytecode.

El resultado va de `(evento, offset_JP)` a `source.event_id/source.offset`, la
identidad de instrucción y las dos anclas. Así `auditar` puede reextraer el
texto ES desde el recurso oficial y registrar su procedencia, sin que este
módulo copie contenido ni decida una traducción.

## Comprobación del caso Ogre

En ambos eventos anteriores, la cabeza JP `0x4B0` usa `301D`, instrucción
`1232`, tipos `(3,)`; la fuente ES verificada está en `0x2EC`, también `301D`
con `(3,)`. Las anclas comunes son las instrucciones `1216` y `1239`.
La instrucción previa inmediata `1225` **no** es un ancla: JP tiene tipos
`(3,4,3)` y ES `(3,4)`. Es además la que contiene la sustitución `%s` ES, por
lo que no demuestra que `1232` tenga un desajuste de controles. La anomalía era
de correspondencia del corpus, no de la cadena `1232`.

Los tests sintéticos cubren la resolución positiva y el cierre cuando falta una
de las anclas o cambia la firma del destino. La integración en `fase2.auditar`
queda para su propietario: debe llamar al resolvedor solo sobre sus filas
contradictorias y reextraer `source.offset` antes de aceptar el override.

## Revisión de los 88 bloqueos de controles Ogre

Las 88 filas con patrón JP `(%s, %3F, %1F, %1F)` y ES `(%s,)` no son el mismo
fallo de correspondencia. Cada una ya declara `official_verified: true` y la
fuente `offset_identity_and_official_reextraction`; por ejemplo `32010200:0`
es `301D` instrucción 1013 y tipos `(3,4,3,3,3)`. Los tres registros
adicionales son ruby/argumentos japoneses del grupo, mientras que el texto
oficial solo mantiene la sustitución dinámica. El resolvedor de identidad no
debe desbloquearlos: siguen pendientes de demostrar el consumo y la cota de
`%s` en el productor, sin eliminar secundarios ni argumentos.
