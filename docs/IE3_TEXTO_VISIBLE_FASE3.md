# IE3 Fase 3 — texto visible no dialogado

## Cota de consumidor

Los campos visibles SSD no comparten la prueba de lectura variable que existe
para `301D`. Hasta demostrar sus buffers IE3, cada sustitución debe caber en el
cuerpo JP original; conserva tamaño de registro, tabla SSD y cabecera. Las
traducciones más largas se informan como
`capacidad_consumidor_visible_no_demostrada` y no se emiten.

## Integrado de forma conservadora

`ie123kit.ie3.comun.texto_visible.construir_payloads_texto_visible` produce un
diccionario `ruta -> payload` y un informe; no abre archivos para escritura ni
reconstruye ROMs. Su consumidor debe incorporar exclusivamente esos dos
payloads al contenedor ya validado:

- `<recurso>/eve.pkh`
- `<recurso>/eve.pkb`

La categoría integrada es la tabla SSD de eventos que contiene rótulos de
objetivo, nombres de lugar y nombres ocultos. La fuente europea se reextrae.
Cada pareja exige el mismo evento, ID de instrucción y slot físico, un rol
permitido, tipos/valores no textuales iguales y dos instrucciones vecinas
inmediatas con identidad y argumentos no textuales iguales. Los valores-puntero
tipo 3 se excluyen de la firma, no sus tipos. El ordinal es solo diagnóstico.
El informe conserva las transiciones y las causas de rechazo por campo.

| Universo final | Spark | Ogre |
| --- | ---: | ---: |
| Campos visibles JP inventariados | 833 | 1.139 |
| Identidad estructural confirmada | 501 | 761 |
| Ya idénticos en el original | 232 | 355 |
| Modificados respecto al JP y reextraídos | 95 | 104 |
| Admitidos sin crecimiento, incluidos idénticos | 327 | 459 |

Los campos modificados se cuentan frente al original JP, no como nuevas
traducciones frente a v7. No incluyen los nombres unitbase ni item.dat.

### Exploración preliminar sustituida

La tabla siguiente conserva el inventario inicial por orden y rol. Sus
833/1139 parejas **no son correspondencias confirmadas ni inserciones**;
aquella propuesta se rechazó antes de crear una ROM y fue sustituida por las
pruebas de identidad y capacidad anteriores.

| Perfil | Parejas preliminares JP ↔ ES | Pares de opcode observados |
| --- | ---: | --- |
| Spark | 833 | 2019→201A: 14; 201A→201A: 5; 201C→201D: 167; 201D→201D: 25; 3019→3019: 154; 4037→4037: 468 |
| Ogre | 1.139 | 2019→201A: 8; 201A→201A: 9; 201C→201D: 105; 201D→201D: 102; 3019→3019: 231; 4037→4037: 684 |

La diferencia 201C→201D y 2019→201A impide usar el opcode como única clave de
alineamiento entre regiones. En la ruta final, una cardinalidad distinta o un
rol no confirmado queda pendiente; la cardinalidad igual tampoco autoriza
una correspondencia sin las anclas descritas. El módulo conserva
literalmente el código SSD y las entradas no elegidas,
incluido el relleno residual de IE3. Reparsea el SSD y reconstruye PackNum con
la implementación de fase 2, que conserva compresión, metadatos, colas y
bloques no modificados; finalmente vuelve a extraer cada bloque sustituido del
payload producido y exige igualdad exacta.

Ejemplo de uso en un integrador, sin escribir la referencia:

```python
with B123Archive(base_jp) as jp, B123Archive(oficial_es) as es:
    payloads, report = construir_payloads_texto_visible(jp, es, "spark")
```

## Pendientes accionables

- `0x402F`: etiqueta fija `もくてき`; la referencia ES no aporta una traducción
  demostrada. Requiere identificar su consumidor/recurso antes de cambiarla.
- Menús, ayuda, descripciones, técnicas y cadenas de partidos:
  existen candidatas en `logic/*.STR`, `logic/*.dat`, `games.STR`,
  `command.STR`, `item.STR`, `unitbase.STR`, `Tournament*.dat` y `BattleRouteTitle.dat`.
  Las versiones europea y JP cambian tamaños y, en varios casos, geometría de
  registros. Falta documentar qué campos son texto y su consumidor; copiar
  archivos europeos completos alteraría IDs y datos de juego, por lo que no se
  emite payload para ellas. Los nombres de objetos sí se integran por el
  adaptador específico `items.py`; no sus descripciones `item.STR`.
- Texto incrustado en `a_menu/*.arc`, `a_data_replace/*` y gráficos: es otra
  categoría y no se declara localizado por esta fase.

La tipografía, los portadores, los cinco módulos congelados, el CRO y el cuerpo
del diálogo quedan fuera de este módulo.
