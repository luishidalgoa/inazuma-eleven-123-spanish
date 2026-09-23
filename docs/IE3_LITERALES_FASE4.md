# Fase 4 — literales comunes de interfaz

## Diseño previo a la implementación

Problema: las etiquetas principales no están en `games.STR` ni como ASCII en
el CRO europeo. El CRO japonés sí contiene literales SJIS consumidos directamente.
Copiar textos por coincidencia de offset, traducirlos manualmente o trasplantar
un CRO europeo completo no demuestra equivalencia y puede alterar código/punteros.

Evidencia: el consumidor europeo llama a `_ZN2iz8localize9GetStringEi`, importado
en CRO `0x1038`. La importación nombrada `0x2ECA70` apunta al símbolo `0x2F1EA8`
y al fixup `0x2E653C` (destino `0x103C`). El export CRS `0x16EC` resuelve la
función a VA `0x17AF84`, offset `0x7AF84` del `.code` BLZ descomprimido. Allí el
selector español usa la tabla VA `0x2B4A18`, offset `0x1B4A18`. Sus 864 entradas
son punteros de 32 bits. Se reutilizan ExeFS, BLZ y CodeTable existentes.

| Consumidor equivalente | ID ES | Destino JP | Capacidad |
| --- | ---: | --- | ---: |
| Título del menú, EU `1734DC`, JP `165D78` | 435 | `165E80` | 12 |
| Lista seis entradas, EU `1734FC`, JP `165D94` | 436 | `165E8C` | 56 |
| Nivel maestro, EU `208198`, JP `1F9B54` | 93 | `1F9E44` | 12 |
| Nivel equipo, EU `2083BC`, JP `1F9B90` | 94 | `1F9E54` | 16 |
| Título equipo, EU `208344`, JP `1F9DC8` | 96 | `1F9E84` | 8 |
| Puntos, slot11/r4+10, EU `627B0`, JP `5EB58` | 58 | `5EEEC` | 12 |
| Puntos, slot12/r4+14, EU `62858`, JP `5EC14` | 59 | `5EEFC` | 12 |
| Contador jugadores, EU `208230`, JP `1F9C9C` | 60 | `1F9E70` | 8, no cabe |

La lista oficial completa ocupa 56 bytes incluyendo seis NUL y consume los dos
bytes de padding originales. El lector JP `1755E8` avanza `strlen+1`, no offsets
fijos; la siguiente constante `165EC4` queda intacta. El título usa copia máxima
15 en `175608`. Las etiquetas de puntos tienen un puntero reubicado a +12:
**no son ranuras de 16 bytes**. Maestro termina antes de la relocación `1F9E50`.
El contador jugadores necesita 10 bytes, frente a 8 existentes; su sufijo 人 y
punteros siguientes están vivos. Se mantiene japonés, sin inventar abreviaturas.

Solución: nuevo `tools/src/ie123kit/ie3/comun/ui_literales.py`, función pura sobre
bytes, tests nuevos `tools/tests/unidad/test_ie3_ui_literales.py` y
`tools/tests/requiere_rom/test_ie3_ui_literales_oficial.py`. Verifica fuentes EU
por hash, cadena import/export/ID y consumidores; destino por anclas locales y
rangos literales, sin hash global (composición con geometría/nombres). Rechaza
relocaciones intersectantes y cualquier cambio inesperado en los rangos. Sólo
recodifica texto oficial con encoder existente; no cambia fuente ni métricas.

Riesgos/validación: pendiente prueba visual de encaje y ejecución. Tests comprueban
fuente equivocada, capacidad sin truncar, padding, relocaciones, idempotencia y
composición con cambios ajenos. La fuente auditada es Spark EU y el consumidor
JP es el CRO común compartido con Ogre; no se certifica Bomber.

## Resultado y corroboración Ogre

Implementados los 7 bloques / 12 etiquetas de la tabla, pendiente sólo el
contador superior `Jugadores` por falta de espacio. La lista lateral utiliza
los seis nombres oficiales completos, sin inventar traducciones. Su encaje
visual todavía requiere juego, no se declara verificado.

Ogre EU se comprobó independientemente: CRO idéntico al Spark EU, por tanto
iguales consumidores/importaciones e IDs; CRS hash
`101e0cf3d52eb1cbb17423c148f2d0c880d8e5c572c8e2ce6a3737c9f11cca87`,
export `16EC` idéntico y función `7AF84` idéntica. Su `.code` descomprimido tiene
SHA `6a2f8b407f4db73bd4c16cb5539e3a889e0de885e9e8f4a770af4812235bd828`.
Selector español `7AFE0` y tabla `1B4A18` iguales; los 12 textos recuperados
mediante los mismos IDs son exactamente iguales y la CodeTable también.
La función acepta ambas fuentes con pares de hashes propios (no mezclables),
con el mismo algoritmo y prueba de igualdad de salida. No se heredan supuestos
de Spark sin comprobar la fuente Ogre.

Validación: 15 tests de este módulo pasan (13 sintéticos y2 con originales),
incluyendo fuentes Ogre/Spark independientes y salida compartida idéntica;
Ruff sin incidencias. No se escribió ningún CRO, ExeFS, FA ni ROM como parte
del adaptador o de estos tests; la integración corresponde al constructor.
