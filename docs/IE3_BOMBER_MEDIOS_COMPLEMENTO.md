# Complemento Bomber de medios sobre Fase 5

## Alcance exacto

Esta es una ampliación incremental del material ya generado, no otra emisión de
fase3 ni una nueva localización de diálogos. No modifica `fase5.py`,
`medios_es.py`, los cinco congelados, fuentes/glifos/encoder, el CRO, corpus,
fuentes oficiales, ROMs originales o guardados. Solo añade módulos de complemento.

La entrada debe ser una candidata ya construida con el contrato de Fase 5:
`revision.json`, `verification.json`, `manifest.json`, `archive.fa`, `romfs/`,
`audio.json` y `videos.json`. El manifiesto final debe contener readback de
archive/CRO/ExeFS y de todos los archivos externos.

### Seis destinos registrados

Dentro de `archive.fa`:

- `inazuma3/data_iz/movie/a3y01b.moflex`
- `inazuma3/data_iz/movie/a3y02b.moflex`
- `inazuma3/data_iz/movie/a3y03b.moflex`
- `inazuma3/data_iz/movie/op00b.moflex`

En el overlay RomFS:

- `inazuma3/data_iz/sound/op00b.SAD`
- `inazuma3/data_iz/sound/end00b.SAD`

Las fuentes son las rutas españolas EXACTAS de la extracción indicada por el
perfil `bomber`. No se renombran películas `f` para fingir películas `b`.
Los hashes y tamaños permitidos están tomados de `informe.json` del diagnóstico
aportado el 21/09/2026; otro volcado incompatible debe revisarse, no forzarse.

Los dos SAD ES coinciden en bytes con las canciones ya seleccionadas para Spark,
pero se usan los ficheros de Fuego y se comprueba esa igualdad otra vez. El caso
`op00b` admite únicamente el alias interno `OP00B.SAD → OP00F.SAD`, condicionado
además a los dos hashes de la transición y a la corroboración con `op00f.SAD`.
Si las etiquetas son inesperadas, se detiene y las muestra. No se elimina el
control de identidad ni se amplían categorías arbitrariamente.

### Lo que queda intacto, no certificado como español completo

Los nueve audios `a3y` siguen como estuvieran en la base. La documentación los
clasifica como eyecatches cuya categoría aún no estaba auditada; no se habilitan
como voces por la mera existencia de una ruta ES. Por ello, los tres vídeos
`a3y*b` nuevos conservan la pista de audio de la base. Esto se indica en el plan:
no se proclama un conjunto audiovisual perfectamente sincronizado/localizado.

No se modifican DAT/subtítulos, bancos SAD/SED/SWD/SMD/PKB/PKH sin contrato, promos,
menús, nombres, diálogos ni recursos exclusivos de Bomber fuera de los seis
anteriores. Se mantienen sus pendientes. La igualdad de los corpus Spark/Fuego
no demuestra cobertura del 100 % de los recursos ni de la campaña.

## Decisiones de implementación

1. Se conserva físicamente la candidata base. No se mueve su `manifest.json` ni
   se copia un `verification.json` antiguo para hacerlo pasar como nuevo.
2. Se verifica su inventario real, fingerprints de revision/verification/manifest,
   overlay completo y código protegido. Así se rechaza una candidata a medio
   generar o alterada después del readback.
3. Se inspeccionan recursos JP/ES con los lectores existentes. Las películas nuevas
   se leen frame a frame con OpenCV. No se convierten ni se recodifican.
4. Solo después de esas comprobaciones se copia una vez el archive y el overlay
   a una carpeta nueva; se reinsertan los cuatro vídeos mediante el repacker FA
   existente y se copian los dos SAD completos.
5. Se reextraen todas las entradas: las no seleccionadas deben ser idénticas a
   las de la base. Se comprueban el CRO y todos los audios heredados. Fuentes y
   datos textuales quedan dentro de esa comprobación de identidad.
6. Se genera una verificación NUEVA del complemento. Su garantía textual es
   derivada: verificación de la base vinculada por hashes + identidad de todos
   los bytes de recursos no multimedia. NO afirma haber vuelto a ejecutar el
   análisis semántico de diálogos ni haber jugado todos los eventos.
7. Se invoca el `construir(..., revision=True)` de `build_piloto`, sin cambiarlo.
   Este genera la ROM y efectúa su readback normal. La referencia visual de esta
   transición es el manifiesto final de la candidata BASE, no el de fase4 a mano.

No se usa el `fase5 --verificar` antiguo sobre esta nueva transición. El módulo
`bomber_medios` tiene su verificador incremental, con alcance explícito.

## QA OpenCV

La documentación `IE3_MEDIOS_ES.md` describe una comprobación independiente con
OpenCV, no una ruta de transcodificación. El módulo `bomber_video_qa.py` hace
reproducible ese método para los cuatro pares nuevos JP/ES.

- Importa `cv2` del Python actual, sin instalar nada automáticamente.
- Usa un temporal privado, libera el lector y lo elimina al terminar.
- Cuenta llamadas `read()` satisfactorias; NO usa solo `CAP_PROP_FRAME_COUNT`.
- Comprueba frames no vacíos, geometría nativa 240x320 y 24 fps.
- Si hay contador declarado positivo, exige que concuerde con la lectura real.
- Exige frames JP/ES iguales. No recorta, ralentiza ni salta una guardia si difieren.
- Guarda caché por SHA-256 y versión del comprobador; no reutiliza QA solo por ID.

**Límite importante:** OpenCV `read() == False` puede señalar EOF o un problema del
backend. Incluso dos lecturas con igual número de frames no son una prueba CRC
ni una certificación de montaje/idioma/sincronía. Se guarda explícitamente esta
limitación; cero frames, excepciones y discrepancias bloquean la emisión. Los
resultados `sequential_eof` significan lectura secuencial hasta la terminación
observada de OpenCV, no un test exhaustivo de integridad del códec.

Se mantienen `runtime_verified=False`, `audio_decoded=False` y
`subtitle_localized=False`. La prueba visual/escucha real sigue siendo necesaria.

## Uso

Después de instalar el complemento, desde la raíz:

```powershell
python -X utf8 -m ie123kit.ie3.bomber_medios
```

O doble clic en `CREAR_ROM_CON_BOMBER.bat`. El BAT establece `PYTHONPATH` al
`tools/src` local y prefiere el entorno activo, después `.venv`, después `python`.
No accede a una API, no consume créditos de IA y no hace operaciones Git.

Solo preparar (no crear una ROM completa):

```powershell
python -X utf8 -m ie123kit.ie3.bomber_medios --solo-preparar
```

Solo comprobar el complemento generado:

```powershell
python -X utf8 -m ie123kit.ie3.bomber_medios --verificar
```

Para otra base compatible, indicar `--base-candidate`, una `--salida` nueva y
opcionalmente `--rom`. El BAT comenta estas variables. No asume que la carpeta
más reciente por fecha sea la última versión válida. No sirve automáticamente
para esquemas desconocidos; se detiene antes de forzarlos.

## Salidas y espacio

Por defecto:

- Candidata: `work/ie3/shared/candidatas/spark_bomber_ogre_fase5_medios/`
- ROM: `work/build/inazuma123_fase5_con_bomber.3ds`
- Logs: `work/informes/complemento_bomber/`
- Caché de QA pequeña: `work/ie3/shared/bomber_media_qa/cache/`

Dentro de la candidata se guardan el plan, informes combinados `audio.json` y
`videos.json`, manifiestos y una verificación nueva. `build_complemento.json`
apunta a la ROM que realmente terminó y a su manifiesto. Ejecutar el BAT de
nuevo con las mismas entradas vuelve a comprobar y reutiliza la ROM, no genera
otros 2 GiB. No borra builds antiguas automáticamente: pueden ser dependencias.

Se exige espacio para la copia de la candidata más los 8 GiB libres que necesita
el builder: aproximadamente 10 GiB libres con los tamaños comunicados. Antes de
repetir con otra candidata, revisar dependencias; no borrar originales para liberar
espacio. La base anterior se mantiene porque forma parte de la prueba heredada.

## Si se interrumpe

Una decodificación fallida se detecta antes de crear la candidata grande. Su log
indica el recurso concreto. Si faltan dependencias originales/manifiestos, no se
fabrican reemplazos. Si falla durante la copia/repack, la carpeta parcial se
conserva y NO se presenta como válida. Si ya hay `revision.json`, una nueva
invocación intenta verificar, no sobrescribe la carpeta a ciegas.

Una ROM parcial sin manifiesto no se considera terminada. El próximo intento
usa otro nombre disponible. Una ROM terminada se reutiliza solo tras comprobar
su SHA-256 y el manifiesto. No existe una opción `--force` para saltar estas reglas.

## Prueba manual mínima

Seleccionar Bomber dentro de la misma recopilación, observar opening y escuchar
su canción; revisar los tres eyecatches en sus puntos de aparición, probar una
escena hablada y una secuencia posterior. El ending requiere llegar a su escena
correspondiente. Hacer regresión corta en Spark/Ogre, diálogos y menú. El paquete
no desbloquea eventos, modifica guardados ni sustituye todas las pantallas UI.

## Evidencia y pruebas de desarrollo

Los tests añadidos usan contenedores y pistas sintéticos. Ejecución local:

```powershell
python -X utf8 -m pytest tools/tests/unidad/test_ie3_bomber_medios.py -q
```

También se conserva, sin cambios, el contrato de `test_ie3_medios_es.py`: no se
ha reemplazado el módulo de medios existente. La prueba con las ROMs oficiales,
el builder Windows y la consola se realiza en el equipo del usuario; no se
presenta como ejecutada por el autor de este complemento en otro entorno.
