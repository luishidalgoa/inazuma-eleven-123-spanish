# IE3 fase 3: candidata integrada, no validación de campañas

## Referencia y alcance

El usuario aprobó en ejecución el piloto `spark:evet:32500100:00000064`, ROM
SHA-256 `967107bd55f8f6bb18df896f2564296f0b908163d5fe12a6027cacaad7644e79`.
La aprobación no se extiende a otras instrucciones, controles, campañas ni a
esta candidata. La tipografía del cuerpo v7 queda conservada.

El núcleo único está en `ie3.comun.emision`, `referencias` y `paquetes`.
`ie3.fase2` mantiene su CLI histórica; `ie3.fase3` activa la reconstrucción
general por perfiles. Nunca usa el antiguo `--crecer`. Parte del JP original,
verifica sus huellas y registra original→heredado→salida. Conserva bytecode,
IDs, argumentos y secundarios originales, actualizando tamaños y referencias.

## Categorías

| Categoría | Ruta aplicada | Pendiente |
| --- | --- | --- |
| Diálogo | 301D/evet + fuente ES reextraída | Validación de campañas en ejecución |
| `%d` | int32, hasta 11 glifos / 22 bytes SJIS | Otros formatos/órdenes |
| `%s` de objetos | 4099 → pool completo item.dat | Productores de personajes/cachés |
| Hablantes | unitbase 0x68, ID +4E, corto +1C:16 | NPC/ex_binder e identidades/encoding pendientes |
| Presentación | Una rama FONT8 del CRO IE3 | Otras pantallas FONT8 deben probarse |
| Objetos/equipamiento | Nombre de item.dat ofuscado; metadatos JP intactos | Identidades ambiguas y descripciones item.STR |
| Objetivos/lugares/nombres ocultos | SSD con identidad, dos anclas y cuerpo no mayor que el JP | Pares ordinales y crecimiento no demostrado rechazados |
| Menús/ayudas/técnicas/descripciones/cadenas | Inventario y análisis focal | Sin contrato suficiente; no se copian tablas EU |
| Gráficos/ejecutable | Categoría independiente conservada | No se cuentan como localizados por las tablas |

La revisión final rechazó la primera propuesta de correspondencia de textos
visibles por orden+rol. Se interrumpió aquella preparación antes de crear
archive/ROM. La ruta final exige identidad, argumentos no textuales iguales y
anclas inmediatas. Además, la cota de destino de esos consumidores IE3 no está
demostrada: solo se emite un cuerpo que no supere los bytes del texto JP,
conservando literalmente tamaño de registro, tabla y cabecera. El crecimiento
demostrado de 301D no autoriza crecer otros consumidores. Los informes iniciales
de 833/1139 candidatos no son cifras de inserción final.

Las cifras viven en `summary_plan.json` y `emission.json` de cada perfil.
Mensajes 301D, grupos legado y filas CSV no son el mismo universo. `reason`
es una partición excluyente; `blockers` conserva todas las causas simultáneas.
Las traducciones v7 de personajes con `%s` se conservan como **heredadas
pendientes de cota**, no como inserciones nuevas certificadas por este compilador.
De los 14 originales Spark ya idénticos a ES del universo legado, 13 son mensajes
301D y uno (`32109000:0`) está fuera de ese consumidor. No son inserciones nuevas.

## Resultado de la candidata integrada (2026-09-19)

**Spark + Ogre Fase 3 — pendiente de validación manual del conjunto.**
ROM ejecutable, no solo archive:
`work/build/inazuma123_spark_ogre_fase3_pendiente_validacion_manual.3ds`.
Tamaño: **2.147.483.648 bytes (2 GiB)**. SHA-256:
`34c2e9a3e79d7561ece763e41909f06db97601c98dbcd1d879100b38ddf4bc6e`.

Manifiestos en `work/ie3/shared/candidatas/spark_ogre_integrada_fase3/`:
`manifest.json` identifica la ROM y su reextracción; `integration.json` contiene
aprobación acotada, recursos y transiciones; `qa.json` resume controles finales.
Los subdirectorios `spark/` y `ogre/` contienen plan, messages, emission,
exceptions y unreferenced con procedencia y pendientes por clave.
`plan_summary.inserted_this_run=0` describe la fase de planificación, no la
emisión: las inserciones reales están en `emission.summary`.

| Diálogos: universos y estados | Spark | Ogre |
| --- | ---: | ---: |
| Grupos originales, denominador legado | 39.189 | 40.852 |
| Oficiales disponibles, denominador legado | 34.101 | 36.749 |
| Mensajes JP del consumidor 301D | 39.145 | 40.801 |
| Oficiales referenciados / identidad verificada | 34.100 | 36.705 |
| Admitidos y reextraídos exactamente | 31.833 | 34.212 |
| Cobertura sobre oficiales referenciados | 93,3519 % | 93,2080 % |
| Cobertura sobre oficiales del universo legado | 93,3492 % | 93,0964 % |
| Nuevos frente a la referencia aprobada | 14.566 | 34.198 |
| Heredados oficiales retenidos y reextraídos | 17.231 | 0 |
| Traducciones heredadas corregidas | 23 | 0 |
| Originales ya idénticos, dentro de 301D | 13 | 14 |
| Pendientes preservados en japonés | 5.095 | 6.589 |
| Heredados preservados pero pendientes de cota dinámica | 2.217 | 0 |

Las 23 correcciones se cotejaron con las alertas del piloto y su fuente ES.
El decimocuarto original Spark ya idéntico es ajeno a 301D y sigue literal;
no se suma como nueva inserción. Las dos identidades Ogre pendientes quedaron
resueltas. El universo legado se conserva: no se eliminan inline, huérfanos ni
referencias ausentes para mejorar porcentajes.

| Pendiente 301D, causa primaria excluyente | Spark | Ogre | Próxima evidencia necesaria |
| --- | ---: | ---: | --- |
| Controles/argumentos | 2.217 | 2.437 | NUL y cota de productores dinámicos, incluidas instancias/cachés; orden de argumentos |
| Encoding | 41 | 47 | Ampliación autorizada del encoder/portadores, ahora congelados |
| Layout/paginación | 9 | 9 | Representación de continuación con semántica demostrada |
| Sin correspondencia | 1.605 | 1.758 | Fuente oficial y consumidor equivalentes |
| Correspondencia ambigua | 3.440 | 2.338 | Identidad estructural adicional, no parecido textual |

Entre oficiales referenciados quedan **2.267 Spark y 2.493 Ogre** no admitidos;
considerando todos los mensajes 301D, **7.312 y 6.589**. No todos permanecen JP:
los 2.217 Spark heredados se preservan explícitamente sin certificarlos como
emisión nueva. Los JSON conservan todas las causas simultáneas en `blockers`.
Encoding de diálogos: `è ì ã ê ö` en Spark, además `ă` en Ogre; esto no modifica
el `È` aprobado. No se sustituyen por interrogaciones ni se eliminan diacríticos.

Se admitieron **471 controles Spark y 499 Ogre** antes pendientes, mediante
pool completo de objetos y `%d` int32. La comprobación post-encoder de los
66.045 mensajes admitidos, incluidas cotas de sustitución, da como máximos
151 bytes expandidos con NUL, 51 glifos por línea y 322 píxeles de tinta; no
equivale a ejecución. Se revisaron también las imágenes offline de diálogos y
nombres, etiquetadas como simulaciones, sin modificar las fuentes aceptadas.

| Otras categorías (universos separados) | Spark | Ogre |
| --- | ---: | ---: |
| Nombres cortos unitbase nuevos | 11 | 2.372 |
| Nombres cortos heredados oficiales | 2.345 | 0 |
| Nombres cortos originales ya oficiales | 5 | 5 |
| Nombres de objetos modificados respecto a JP | 786 / 1.024 | 789 / 1.024 |
| Campos SSD visibles modificados respecto a JP | 95 / 833 | 104 / 1.139 |
| Campos SSD visibles originales ya idénticos | 232 | 355 |

Objetos: 231/228 identidades pendientes, cuatro vacíos, dos ya idénticos y un
`Doppelgänger` (`ä`) no codificable por perfil. Hablantes: 219/203 IDs cero
reservados y dos nombres no codificables por perfil (`Völz`, `Luceafăr`).
Los 506/680 campos SSD visibles no admitidos se reparten en identidad
(332/378) y capacidad no demostrada (174/302). No se amplió su buffer.
Menús generales, ayudas, descripciones, técnicas, cadenas de partidos y texto
en gráficos **no quedan completados**: faltan contratos de sus campos/lectores;
los nombres de objetos no equivalen a localizar todas esas interfaces.

### Validación y advertencias

- Suite completa sin ROM: **1.154 passed, 17 deselected, 8 subtests passed**.
- Tres archivos de pruebas con oficiales: **5 passed**, consumidor ARM,
  tipografía y ajuste FONT8 sobre el CRO real.
- Guardias bloqueados, git y shims: correctas; cinco congelados intactos,
  641 archivos rastreados, cero prohibidos y 31 shims puros. Lint pasa.
- Round-trip de ocho pares PKB/PKH y 11.669 eventos JP/ES; emisión y reextracción
  exacta, código/secundarios y metadatos conservados, límites y terminadores
  comprobados. Incluye colas FF 0/4/8/12 y regresiones del centinela PKH.
- 74 cadenas Spark 3070 sin NUL preservadas; cinco inline por perfil, siete/seis
  huérfanos inventariados. Las tres referencias Ogre a evet 90000002 ausente
  coinciden literalmente con el original: no se inventó ese recurso.
- La ROM final se reextrajo: archive, **15.547 entradas**, CRO y ExeFS coinciden.
  Solo doce recursos del archive cambian frente al piloto aprobado; las seis
  entradas de fuentes quedan idénticas. La ruta FONT12/cuerpo no cambia.
- El parche de nombres cambia un byte del CRO IE3 y afecta otras UI FONT8 sin
  override propio. Requiere prueba manual. El renderer no modela el espacio
  de 29 nombres por perfil; sus medidas no se dan como comprobadas.
- `git diff --check` conserva una advertencia de línea vacía final preexistente
  en `comun/reinsert.py:284`; no se tocó el componente aprobado para limpieza
  cosmética. No es un fallo binario ni una guardia desactivada.

No se ejecutó esta ROM ni se validaron campañas completas. Se generó una sola
ROM nueva; sin push, publicación, PR, eliminación de originales ni guardados.

## Comandos de reproducción

Desde la raíz del repositorio, Python 3.12 con ie123kit instalado:

```powershell
python -X utf8 -m pytest tools/tests -m "not requiere_rom"
python -X utf8 -m pytest tools/tests/requiere_rom/test_ie3_consumidor_fase2.py tools/tests/requiere_rom/test_ie3_tipografia_oficial.py tools/tests/requiere_rom/test_ie3_presentacion_nombres_oficial.py
python -X utf8 -m ie123kit.nucleo.compat.guardia bloqueados
python -X utf8 -m ie123kit.nucleo.compat.guardia git
python -X utf8 -m ie123kit.nucleo.compat.shims comprobar
python -X utf8 -m ie123kit.ie3.fase3 --referencia work/ie3/rayo_celeste/candidatas/spark_fase2_piloto_referencias/archive.fa --aprobacion work/ie3/shared/fase3/aprobacion_piloto.json --salida work/ie3/shared/candidatas/spark_ogre_integrada_fase3
python -X utf8 -m ie123kit.ie3.comun.build_piloto --integrated --candidate work/ie3/shared/candidatas/spark_ogre_integrada_fase3 --visual-manifest work/ie3/rayo_celeste/candidatas/spark_conservadora_v7_celdas_centrado/manifest.json --rom work/build/inazuma123_spark_ogre_fase3_pendiente_validacion_manual.3ds
```

Las salidas deben ser nuevas: no se sobrescriben originales ni candidatas
existentes. El constructor reextrae la ROM final y compara archive, todas sus
entradas, CRO y ExeFS. Un archive.fa solo no es una entrega ejecutable. Los
hashes del código/entradas y la procedencia de cada transición quedan registrados.

## Incorporar Bomber

Solo existen corpus locales Spark y Ogre en `translation/ie3`. Faltan fuente
oficial Bomber, corpus y correspondencias verificadas. Aportar JSON compatible
con `comun.perfiles.Perfil`: nombre, recurso, oficial, corpus, alineado,
compartido, revisión y hashes de base/consumidor. Se utiliza el mismo pipeline
con `--perfil bomber --perfil-json ruta/al/perfil.json`, sin duplicar algoritmos.
Compartir `inazuma3/data_iz` con Spark no prueba igualdad semántica. Se detectan
conflictos de payload entre perfiles y se aborta antes de sobrescribir otra
localización; los exclusivos sin fuente siguen intactos. Bomber no se declara
localizado por el efecto compartido del parche Spark.

## Prueba manual

- Spark con arranque limpio: Maserati, Bianchi, diálogos posteriores, textos
  largos/cortos, saltos, ¡/¿, acentos, ñ y È; sin cajas vacías ni pérdida inicial.
- Hablantes cortos/largos/con espacios, pestaña y otras listas/UI FONT8.
- Obtención de objeto/cuaderno con `%s`, nombre correcto y evento siguiente;
  confirmación con `%d`, importe y elección.
- Objetivos/lugares admitidos; mantener `????` si coincide con la fuente oficial.
- Menú de objetos/equipamiento: nombre, estadísticas/efectos y descripción
  (esta puede seguir japonesa).
- Arranque y varios eventos de Ogre; avance después de mensajes que crecen.
  Pasar el prólogo no valida toda la campaña.

La imagen offline de nombres es simulación, no captura del motor. Los JSON
locales mantienen pendientes por clave/carácter/causa e inventarios separados
de inline, huérfanos y recursos originalmente ausentes.
