# Harness de trabajo (agente)

Reglas de trabajo para el agente en este proyecto. Complementan `CLAUDE.md` y `AGENTS.md`;
si hay conflicto, mandan esos dos ficheros.

## 1. Sin emulador para localizar nada

- El emulador **no** se usa para encontrar direcciones, funciones, textos ni causas.
  Eso se resuelve con documentación y análisis estático.
- El emulador lo maneja el usuario y solo para la prueba final, según
  `docs/PROTOCOLO_QA_IE1.md`. El agente no envía entradas ni deja puntos de parada
  activos en el depurador.
- Si un dato solo se puede obtener en ejecución, se deja como pendiente en el backlog
  con la pregunta exacta, y no se improvisa con el depurador.

## 2. Fuentes, por orden

1. **Documentación del proyecto**: `docs/FORMATOS.md`, `docs/SKILL_volcado-rom-nds.md`,
   `docs/FURIGANA_LECCIONES.md`, `docs/ARQUITECTURA.md`, `docs/DESARROLLO.md`,
   las notas `docs/IE1_*`, `docs/IE3_*` y `docs/IE2_*` según el juego.
2. **Fuente oficial en español**: la versión europea de 3DS, `work/ie1/fuentes/3ds_eu`
   (`archive.fa`, carpetas `es/`, `en/`, `fr/`, `it/`). Y la NDS española,
   `work/ie1/fuentes/nds_es`, para diálogos e índices.
3. **Original japonés**: el CRO y los ficheros extraídos de la ROM 1.0 y de la 1.4.
4. **Build actual**: lo que contiene el mod instalado; se compara con 2 y 3.

Un texto que no existe en 1 o 2 no se inventa: se marca como pendiente.

## 3. Análisis estático de código (CRO)

- Herramienta: `tools/src/ie123kit/nucleo/ejecutable/cro.py` (segmentos, relocaciones,
  referencias y desensamblado con capstone en el entorno del agente).
- Método para una cadena o un literal:
  1. Localizar el texto en el fichero (codificación cp932 o ancho completo).
  2. Mirar sus relocaciones (`c.relocations`, `seg_index`, `addend`): el segmento de
     referencia es el que da la dirección del literal.
  3. Buscar qué código carga esa dirección: `ldr rX,[pc,#…]` (pool) o
     `add rX,pc,#…`.
  4. Desensamblar la función que contiene la carga y seguir la llamada.
- Los objetos y métodos virtuales se crean en ejecución. Si el método no está en el
  fichero, se marca como pendiente y no se adivina.

## 4. Cambios

- Cada cambio es una **capa** reproducible en `work/ie1/capas/<tema>/`, con `apply.py`,
  `informe.json` (origen, sha256, offsets y bytes antes/después) y `runtime_verified: false`.
- Antes de escribir en el PC: copia del fichero original en `C:\IE_backups`, y
  verificación de sha256 después. Azahar tiene que estar cerrado.
- Un cambio solo se da por bueno cuando el usuario lo prueba (`PROTOCOLO_QA_IE1.md`).
- **Nombres de jugador (hook de usearch). Regla exacta.** `usearch.dat` es un dato derivado de `unitbase.dat` y nunca
  se deja desincronizado. Hay tres rutas de producción de un `archive.fa` y las tres acaban igual (sincronizado o con
  error); la protección fiable es la VALIDACIÓN DE LA SALIDA, no acordarse de ejecutar un paso:
  1. **Construcción por capas** (`ie123 construir`, `ServicioToolkit.construir`, `candidata.construir` y su
     `python -m ie123kit.nucleo.construir.candidata`, y cualquier `build.py` de `work/` que llame a
     `candidata.construir`): sincronizan `usearch.dat` como PASO FINAL por defecto. El único opt-out es NOMBRADO:
     `--sin-sincronia-usearch` (CLI y `__main__` de candidata), `omitir_sincronia_usearch=True` (servicio) o
     `sincronia_usearch=False` (`candidata.construir`). Solo se usa para reproducir un hash anterior al hook (p. ej.
     `probe_ie1_v67`, `72ef7133…fa91`) o en los tests de la propia validación; esa salida no pasa `verificar` ni
     `instalar` si queda desincronizada. `tools/build_ui_revision.py` (congelado) no lleva el paso: su salida solo sirve
     para el golden y, si se quiere instalar, se cierra con la ruta 2.
  2. **Cadena en sitio** (`apply.py <archive.fa>` de las capas de `servicio.capas_nombres.CAPAS_NOMBRES_JUGADOR`, p. ej.
     sobre el `archive.fa` instalado), SIEMPRE sobre una COPIA: la cadena termina OBLIGATORIAMENTE con
     `python -X utf8 -m ie123kit.servicio.sincronia_usearch cerrar <copia>` (sincroniza IE1, IE2 e IE3, vuelve a
     verificar desde el disco e imprime el sha256). Código de salida 1 = la copia NO se copia al PC ni se instala. Es el
     único paso de cierre: no hay que acordarse de qué capa de nombres se ha ejecutado ni de qué juego. Las
     `apply.py` de las 13 capas de nombres no se tocan (son históricas y de formatos distintos); la regla vive aquí y en
     `verificar`/`instalar`.
  3. **Validación de la salida** (la que bloquea): `ServicioToolkit.verificar` falla con `USEARCH_DESINCRONIZADO` (o
     `USEARCH_SIN_DECODIFICADOR` si falta `work/` con el registro de bigramas) e `instalar` se niega; a mano,
     `python -X utf8 -m ie123kit.servicio.sincronia_usearch verificar <archive.fa>` antes de cualquier `scp` al PC
     (código 1 = desincronizado). Instalar con `instalar.azahar` directamente (sin pasar por la fachada) exige hacer esa
     comprobación a mano antes.
  Procedimiento de instalación en el PC y de deshacer (una sola copia previa, sha de referencia calculado): README de
  `busqueda_usearch` de cada juego.

## 5. Trabajo orientado a backlog

- El trabajo sale de `docs/BACKLOG.md` (que enlaza a los issues de GitHub).
- Se toma el primer ítem con el siguiente paso estático definido; cada ítem se cierra
  con un informe en su issue (qué se encontró, qué se cambió, qué se verificó).
- El agente no pregunta por pasos que puede resolver con estas reglas. Solo pide
  intervención cuando hace falta una prueba en el juego o una decisión de diseño
  que no está en la documentación.
