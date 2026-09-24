# IE3 — traspaso: estado, qué funciona, qué no y qué hacer ahora

> **Continuidad actual 19-09-2026:** v7 aceptada visualmente solo en los casos
> probados; tipografía congelada. Fase 2 implementa referencias 301D verificadas
> con un núcleo Spark/Ogre y entrega un único mensaje piloto del prólogo.
> Consultar [IE3_FASE2_REFERENCIAS](IE3_FASE2_REFERENCIAS.md) y el último
> apartado de HISTORIAL_CODEX. **Esperar la prueba manual del piloto antes de
> activar el corpus o investigar cambios nuevos.** El resto de este documento
> conserva el estado histórico, no sustituye los manifiestos recalculados.

Documento de continuidad. Resume una sesión completa de trabajo sobre la
traducción de Inazuma Eleven 3 dentro del recopilatorio japonés de 3DS. Está
escrito para que otro agente o colaborador siga sin necesitar el chat.

Fecha: 2026-09-18. Rama local: `traduccion/ie3-extraccion` (fusionada con
`origin/estado-ie2-cajas`). **Nada se ha subido a GitHub**: ni push, ni issues,
por indicación expresa del usuario.

---

## 1. Qué se ha conseguido

**Extracción y alineamiento: terminado y fiable.**

| | Filas | Con traducción oficial |
|---|---|---|
| `translation/ie3/rayo_celeste/dialogo_oficial.csv` | 38 901 | 34 691 (89 %) |
| `translation/ie3/amenaza_del_ogro/dialogo_oficial.csv` | 40 814 | 37 607 (92 %) |

Columnas `event_id,japones,es_final,estado`, iguales a las de IE1 e IE2. Ambos
ficheros están en `.gitignore` (texto oficial de Nintendo, Norma 2).

**Reinserción: funciona, pero con un techo.** La mejor ROM es la **v106**, con
41 276 líneas de IE3 en español más 1 424 rótulos y objetivos. El resto se queda
en japonés por el problema del apartado 4.

---

## 2. Dónde está todo

```
Roms/shared/IE123_JP_CTR-P-AETJ.3ds          ROM japonesa (sha256 35f74970…)
Roms/ie3/rayo_celeste/…trim.3ds              Rayo Celeste (CTR-P-AXSZ)
Roms/ie3/amenaza_del_ogro/…cia               Amenaza del Ogro (CTR-P-AXGZ)

ie123kit.ie3.pipeline                        punto de entrada único
tools/src/ie123kit/ie3/comun/
    b123.py pack.py lz.py rom.py ssd.py text.py    formatos
    sheet.py align.py                              alineamiento y clasificación
    maqueta.py                                     saltos de línea
    reinsert.py                                    reinserción en evet y eve
    ancho_ventana.py                               parche del CRO
    diagnostico.py                                 reglas graduadas

work/build/inazuma123_es_v106.3ds            LA BUENA (sha256 30e64274…)
work/build/inazuma123_diag.3ds               build de diagnóstico
work/shared/candidatas/probe_ie1_v106/       su candidata
```

Órdenes:

```bash
python -m ie123kit.ie3.pipeline run          # extraer + alinear + CSV
python -m ie123kit.ie3.pipeline reinsert     # meter el español en archive.fa
python -m ie123kit.ie3.pipeline diagnostico  # reglas graduadas para medir la caja
```

Detalle de formatos en [`IE3_EXTRACCION.md`](IE3_EXTRACCION.md). Lecciones de
emulador en [`FURIGANA_LECCIONES.md`](FURIGANA_LECCIONES.md), apartados ❌#14
a ❌#17, que son de esta sesión.

---

## 3. Lo que se sabe del formato (verificado)

- **`evet.pkb`** es donde vive el diálogo de IE3: tabla plana, **sin comprimir**,
  de registros `u16 instrucción · u8 argumento · u8 tamaño · cuerpo NUL`. Los
  dos primeros campos están **a cero en los 102 419 registros**, así que el
  registro no lleva clave propia.
- **`eve.pkb`** son los scripts SSD (LZ10). De su tabla de textos solo se ve en
  pantalla lo que cuelga de seis opcodes: `0x2019`, `0x201a`, `0x201c`, `0x201d`
  (rótulos de objetivo), `0x3019` (nombre tapado) y `0x4037` (nombre de sitio).
  Todo lo demás son nombres de recurso y depuración.
- **Codificación**: Shift-JIS con portadores griegos (`sjis_portador`), que es lo
  que el proyecto ya usa para IE1 e IE2. Los 15 glifos parcheados cubren el
  español: solo 164 de 78 260 líneas pierden algún carácter (`È ã è ì ê Ç ö ă`,
  nombres extranjeros).
- **Ventana de diálogo**, valores de fábrica y sitios de parcheo:

  | juego | módulo | por defecto | ancho | líneas |
  |---|---|---|---|---|
  | IE1 | `ina_main1.cro` | 0x0465B4 | `[+0x1316]`=0xF0 | `[+0x1318]`=3 |
  | **IE3** | **`ina_main3ogre.cro`** | **0x039CE0** | **`[+0x131A]`=0xF0** | **`[+0x131C]`=3** |
  | IE2 | `ina_main2.cro` | 0x04CAB0 | `[+0x131E]`=0xF0 | `[+0x1320]`=3 |

  0xF0 + 0x20 = 272, a 12 px fijos por carácter → **22 caracteres**.

- **El motor reajusta con avance FIJO de 12 px pero DIBUJA proporcional.** Son
  dos límites distintos: el de caracteres decide dónde parte, y la tinta real
  (caja ≈ 354 px según `capas/ie1/v86/ancho_ventana/informe.md`) decide si se
  sale.
- **Bomber / Fuego Explosivo no tiene texto propio**: `data_iz_bomber` no lleva
  `script/` y su `MCSFILE.TXT` redirige a `data_iz`. Su diálogo es el de Rayo
  Celeste.

---

## 4. EL PROBLEMA ABIERTO

**El motor lee `evet` por offset de bytes, no por índice.** Si un registro
cambia de tamaño, los siguientes se desplazan y el diálogo sale con los primeros
bytes comidos.

Medido al byte en tres builds, con capturas del usuario:

| build | suma de registros anteriores | delta | bytes comidos |
|---|---|---|---|
| v102 | 260 → 260 | 0 | ninguno |
| v103 | 100 → 80 | −20 | 20 |
| v105 | 260 → 256 | −4 | 4 |

**Consecuencia:** cada registro tiene que conservar sus bytes. Lo único que se
puede hacer es repartir dentro de un grupo (un diálogo y sus lecturas furigana),
porque el diálogo va primero y el total del grupo se conserva. Eso es lo que
hace la v106, y por eso solo entran 41 276 de 78 260 líneas.

**Para subir de ahí hay que encontrar dónde guarda el `eve` esos offsets.** Dos
intentos, los dos fallidos, documentados como ❌#16 y ❌#17:

1. *«Va por índice»* — deducido comparando con la ROM europea (eventos cuyos
   offsets se mueven y cuyo código del `eve` es idéntico). **No vale**: Level-5
   reconstruyó las dos cosas al localizar, su bloque tiene 8 registros donde el
   japonés tiene 22 porque eliminó las lecturas furigana.
2. *«Es `0x301a` argumento 2»* — 95,0 % de 54 380 usos caían en inicio de
   registro. **Artefacto**: los valores reales son 0, 2, 8… mientras los
   registros están en 204, 216, 228. Se lo comen los ceros. Y de 2 181 eventos
   con registros movidos, recolocar solo cambiaba algo en 2.

**Comprobación obligatoria antes de creerse cualquier candidato nuevo:** coger
UN evento suelto y mirar si los valores tienen el orden de magnitud de los
offsets del bloque. Un minuto, y habría ahorrado las dos veces.

---

## 5. Lo que NO hay que reintentar

Además de lo de arriba:

- **Añadir páginas `\f`.** De 79 715 líneas japonesas solo 22 las llevan, y
  ninguna pasa de 3 líneas. El manejador de `\f` (0x0C) solo hace `x=0, línea=0`:
  no borra la caja ni espera al botón. Todo lo que se ponga detrás se pierde.
  (❌#14)
- **Maquetar midiendo la tinta real de cada letra.** El motor cuenta 12 px
  fijos. Medir el ancho real da de más y parte la palabra. (❌#15)
- **Encoger las lecturas furigana.** Cambia los tamaños declarados. Se vacían a
  su tamaño original. (❌#12)
- **Code caves en el CRO.** Las zonas aparentemente libres son memoria de
  relocalización. Lo que SÍ está hecho y es distinto: cambiar inmediatos que ya
  existen, en su sitio, comprobando antes que la dirección no aparece en las
  tablas de reubicación (`ancho_ventana.comprobar`).

---

## 6. La build de diagnóstico

`work/build/inazuma123_diag.3ds` mete en 86 diálogos del prólogo italiano
(eventos 32010200, 32010300, 32500100, 32500120, 32500130) una regla graduada:

```
A234567890B234567890C234567890D234567890E2345
```

La letra marca la decena: `A`=1, `B`=11, `C`=21, `D`=31, `E`=41.

Se aplica a **mismo tamaño**, así que no introduce el fallo que quiere medir.
Lleva el CRO parcheado a 0x1E0 (42 caracteres teóricos).

**Qué responde:**

| Observación | Conclusión |
|---|---|
| La primera línea no empieza por `A` | El motor lee desplazado: confirma ❌#16 y el carácter inicial dice cuántos bytes |
| Empieza por `A` | ❌#16 solo se manifiesta al cambiar tamaños; mismo tamaño es seguro |
| Último carácter visible | Caracteres por línea reales |
| Número de líneas dibujadas | Alto real de la caja |
| Sale ~22 pese al parche | El parche del CRO no hace efecto y hay que revisarlo |
| Sale ~42 | El parche funciona y el límite es el esperado |

---

## 7. Qué haría a continuación

1. **Jugar la build de diagnóstico** y anotar las cuatro observaciones. Sin eso,
   cualquier decisión sobre el ancho vuelve a ser una suposición.
2. Según salga:
   - Si la regla empieza por `A` y caben ~42 → ajustar `maqueta.MAX_CAR` y
     `ancho_ventana.ANCHO` al valor medido y rehacer la v106. Ganancia inmediata
     sin tocar el problema del offset.
   - Si no empieza por `A` → el modelo del offset es más complicado de lo
     descrito y hay que medirlo con una segunda regla en un evento donde se
     encoja a propósito un registro anterior una cantidad conocida.
3. **El offset** es lo que desbloquea las 37 000 líneas restantes. La vía
   razonable es desensamblar el manejador del diálogo de `ina_main3ogre.cro`
   (el patrón está en `capas/ie1/v82/saltos_dialogo/comun82.py` para IE1) y ver
   de dónde saca el puntero al texto, en lugar de buscarlo por correlación.
4. **Los menús** (`menu/content.arc`, `es/menu/common.arc`, `es/localize/`)
   siguen sin extraer y son independientes de todo esto. Mismo método que el
   diálogo: localizar formato, extraer, alinear con el europeo, reinsertar.

---

## 8. Avisos de proceso

- **El bloqueo tipográfico v20** (`AGENTS.md`, `tools/dialogue_lock.py`) fija
  *fullwidth, avance 11, límite 220, 3 líneas*, o sea **20 caracteres**. Este
  trabajo usa medio ancho y avances distintos, así que está fuera del bloqueo.
  El usuario autorizó levantarlo de forma explícita para IE3; conviene
  confirmarlo antes de llevar nada al repo oficial.
- **La Norma 1** pide un issue de GitHub por tarea. No se ha creado ninguno por
  indicación del usuario. Al retomar, conviene abrirlos.
- **Antes de construir**, ejecutar siempre la comprobación de que ningún diálogo
  se ha movido. Es lo que habría cazado las builds v102 a v105 y está en
  `scratchpad/verif_final.py` (conviene moverla a `tools/`).
