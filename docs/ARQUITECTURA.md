# Arquitectura del proyecto

La recopilación *Inazuma Eleven 1·2·3!! Endō Mamoru Densetsu* es **un único juego de 3DS**
(`archive.fa` + `ina_main1.cro`) que contiene tres juegos: IE1, IE2 (Fuego / Ventisca) e IE3
(Rayo Celeste / Fuego Explosivo / La amenaza del Ogro). Por eso cada carpeta se divide en:

- `shared/`: lo que pertenece a la recopilación entera (la base 3DS, las candidatas `archive.fa`, las releases, las herramientas externas, el glosario común).
- `ie1/`, `ie2/`, `ie3/`: lo propio de cada juego (sus fuentes oficiales, capas de traducción, QA).
- Dentro de `ie2/` e `ie3/`, una subcarpeta por versión (`tormenta_de_fuego`, `ventisca_eterna`, `rayo_celeste`, `fuego_explosivo`, `amenaza_del_ogro`) para lo que difiere entre versiones, y `shared/` para lo común a las versiones de ese juego.

## Árbol

```
Roms/                         (git lo ignora; nunca se sube)
  shared/                     recopilación 3DS japonesa (.3ds, .cia)
  ie1/                        Inazuma Eleven NDS ES, IE1 3DS europeo (CTR-N-JEUP)
  ie2/tormenta_de_fuego/      NDS ES
  ie2/ventisca_eterna/        NDS ES
  ie3/fuego_explosivo/        IE3 3DS europeo (Bomb Blast)

translation/                  (en git: solo glosarios y CSV de términos)
  shared/glossary/            equipos, jugadores, técnicas, objetos, menús comunes
  juego_principal/            glosario de los menús de la recopilación
  ie1/  ie2/  ie3/            diálogo alineado y términos propios de cada juego

tools/                        herramientas (CLI; ver tools/README.md)
  src/ie123kit/               paquete (pip install -e tools[dev])
    nucleo/                   común a la recopilación: compresion, contenedores, graficos, fuentes,
                              texto, eventos, media, ejecutable, construir, validar, config, compat
    juego_principal/          menú de la recopilación (activos.toml)
    ie1/                      graficos, media, texto, verificar
    ie2/{comun,tormenta_de_fuego,ventisca_eterna}/
    ie3/{comun,rayo_celeste,fuego_explosivo,amenaza_del_ogro}/
    _legado/                  fachadas CLI de los scripts antiguos y cuarentena (--legado-lo-se)
  tests/{unidad,arquitectura,compat,requiere_rom}/
  _archivo/                   scripts retirados: se archivan, no se borran; no importables
  <nombre>.py (29)            shims: alias puros de sys.modules hacia ie123kit
  dialogue_typography.py, font_patch.py, dialogue_lock.py,
  build_ie1_probe.py, build_ui_revision.py   congelados del bloqueo v20 (intactos)
  *.ps1, pyproject.toml       scripts PowerShell y configuración del paquete
  bin/                        (git lo ignora) ejecutables locales

work/                         (git lo ignora)
  shared/
    base_3ds/romfs, exefs     RomFS/ExeFS japoneses originales: base de todo parche. No se borra.
    candidatas/probe_ie1_vNN  archive.fa + CRO construidos (solo las dos últimas)
    releases/                 paquetes de releases publicadas
    herramientas/media_tools  mobipeg x86, vgmstream
    trailer/                  proyecto del tráiler
  juego_principal/            menú de la recopilación: quinto ámbito, igual que ie1/ie2/ie3
    capas/vNN/<linea>/        capas nuevas del menú (las antiguas siguen en ie1/capas, ver abajo)
    qa/  exportaciones/       pruebas en juego y volcados de trabajo
    registro.json             inventario de activos (caché del escaneo del archive.fa)
    historico.json            índice de las capas VIEJAS de ie1/capas que tocan el menú
  ie1/
    fuentes/nds_es            ROM NDS española extraída. No se borra.
    fuentes/3ds_eu            IE1 3DS europeo extraído (es/, voces, cinemáticas, code_dec.bin). No se borra.
    capas/<tema>/<linea>/     capa vigente de cada línea: apply.py, validate.py, extra/, events/, previews/
    capas/historial/<tema>/vNN_<linea>/   versiones anteriores sustituidas (solo consulta)
    qa/                       capturas y registros de pruebas en juego
    legacy/                   carpetas de trabajo anteriores a esta organización (siguen leídas por algún script)
  ie2/{tormenta_de_fuego,ventisca_eterna,shared}/
  ie3/{rayo_celeste,fuego_explosivo,amenaza_del_ogro,shared}/
```

Al empezar IE2/IE3 se repite el patrón de `ie1/`: `fuentes/`, `capas/<tema>/`, `qa/`, dentro de la versión
cuando el recurso es propio de ella o en `ieN/shared/` cuando es común a las versiones.

## Capas: por juego y tema

Las capas no se agrupan por número de versión (`v01`…`v94`) sino por juego y tema. `<juego>` es `ie1`,
`ie2/shared`, `ie2/tormenta_de_fuego`, `ie2/ventisca_eterna`, `ie3/...` o `shared` (lo común a la recopilación):

```
work/<juego>/capas/
  dialogo/            volcado, emparejado, reparto de cajas, páginas
  nombres/            unitbase, pestañas, descripciones, letras dobles de nombres
  rotulos_objetivos/  rótulos de lugar y objetivos
  menus_cro/          literales y parches del código (CRO)
  graficos/           texturas, sprites, ayuda, logos
  media/              voces, bancos de sonido, subtítulos, vídeos
  fuentes/            FONT12/8/12T y registro de letras dobles
  teclado/            teclado de nombre
  candidata/          scripts de montaje de candidatas
  historial/<tema>/vNN_<linea>/   versiones anteriores sustituidas, solo para consulta
```

- La versión **vigente** de cada línea está directamente en su tema, con nombre y sin número:
  `ie2/shared/capas/dialogo/saltos37`, `ie2/shared/capas/menus_cro/ancho_dialogo`,
  `ie1/capas/dialogo/motor_unificado`.
- **Una tanda nueva actualiza la carpeta del tema; la versión anterior pasa a
  `historial/<tema>/vNN_<linea>/`** (NN = tanda en que se hizo). Nada se borra.
- Al mover una capa se reescriben todas sus referencias (`spec_from_file_location`, `sys.path`, BASE,
  rutas de candidatas y rutas cruzadas entre capas) y se ajustan los `parents[N]`: una capa de `historial/`
  está un nivel más honda que una vigente. Después se busca con `grep -rE "capas[/\\]v[0-9]"` que no quede
  ninguna ruta vieja y se ejecuta el `validate.py` de las capas vigentes.
- El número vNN sigue identificando las candidatas (`work/shared/candidatas/probe_ie2_vNN`) y los issues.
- La reorganización del 2026-09-19 dejó la tabla origen → destino en `work/shared/reorganizacion_capas.json`.

## Reglas

1. **Nada nuevo en la raíz de `work/`**. Los cinco ámbitos son `shared/`, `juego_principal/`, `ie1/`,
   `ie2/` e `ie3/`: lo nuevo va en `work/<ámbito>/capas/<tema>/<linea>/` o, si es de la recopilación
   entera, en `work/shared/`. Pruebas e imágenes sueltas: scratchpad de la sesión.
   `ie123 proyecto init` crea los cinco (y sus `translation/<objetivo>/`); es idempotente.
2. Las candidatas se llaman `probe_ie1_vNN` y viven en `work/shared/candidatas/`, porque un `archive.fa`
   contiene los tres juegos.
3. Una capa lee su base de `work/shared/candidatas/probe_ie1_v(NN-1)` y escribe solo dentro de su carpeta.
4. **`work/juego_principal/historico.json` solo APUNTA**: lista las capas antiguas de `work/ie1/capas`
   que tocan el menú (v33/smdh, v54/pantalla_inicio, v58/carga, v58/logos…) con el motivo por el que
   se han detectado. Esas capas **no se mueven**, y `ie123 proyecto migrar-juego-principal --no-simular`
   responde `NOT_SUPPORTED` a propósito: sus rutas relativas al fichero y sus `importlib` (la V37)
   dependen de dónde están. El histórico se escribe igualmente, para poder mirar de un vistazo qué
   capas del menú viven todavía bajo `ie1/`. Las capas NUEVAS del menú van ya en
   `work/juego_principal/capas/`.
5. Las capas existentes de `work/` calculan la raíz del repo con `Path(__file__).resolve().parents[N]`; al
   mover una capa hay que ajustar `N` (lo hizo `tools/_archivo/reorganizar_proyecto.py` en la migración del
   2026-09-16). El código nuevo no usa `parents[N]`: usa `find_root` (`ie123kit.nucleo.config.raiz`) o la
   variable `IE123_ROOT`.
6. **Antes de construir**: ≥ 4 GB libres. **Al instalar**: comprobar el hash del `archive.fa` copiado.
   **Después**: `ie123 work limpiar --borrar` (o `python tools/limpiar_work.py --borrar`). La limpieza
   nunca lista `shared/base_3ds`, ninguna carpeta `fuentes`, los congelados del bloqueo v20 ni una
   candidata con `.conservar`.

## Reglas de importación de ie123kit

1. `nucleo` no importa ningún juego (`juego_principal`, `ie1`, `ie2`, `ie3`).
2. Un juego no importa otro juego.
3. `ie2.<versión>` e `ie3.<versión>` solo importan el `comun` de su juego (además de `nucleo`).
4. `_legado` solo es una fachada: el código del paquete no depende de él.
5. En `src/` no hay `parents[N]` ni rutas de máquina: la raíz sale de `find_root` o de `IE123_ROOT`.
6. Importar un módulo no tiene efectos (ni E/S, ni `print`, ni `sys.exit`).
7. Los shims de `tools/` son alias puros de `sys.modules`; los 5 congelados nunca se copian al paquete, se
   cargan con re-exports perezosos.

Los tests de `tools/tests/arquitectura` comprueban estas reglas y la CI (`.github/workflows/toolkit.yml`)
los ejecuta en Windows y Ubuntu.

`tools/_archivo/` guarda los scripts retirados: se archivan con `git mv` en lugar de borrarse, para
conservar su historia y sus motivos ([`tools/_archivo/README.md`](../tools/_archivo/README.md)). No es
importable ni tiene shims.

## Limpieza

`python tools/limpiar_work.py` lista lo que sobra y con `--borrar` lo elimina: candidatas salvo las dos
últimas, `.3ds` reconstruidas de releases publicadas, `fuentes/` intermedias de cinemáticas, `__pycache__`,
`*.partial`, `*.yuv`, `*_x2.png` y logs de comprobación. No toca `Roms/`, `shared/base_3ds`, `ieN/fuentes`,
capas con scripts, `docs/` ni `tools/`.
