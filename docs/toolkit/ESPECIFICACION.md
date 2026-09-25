# Especificación del toolkit ie123kit

> Generada por workflow (diseño + síntesis) a partir de `catalogo_auditoria.json`. Diseños completos: `diseno_completo.json`.

## Puntuación de diseños

- **Diseño A: comunidad y GUI primero (paquete inazuma, `inazuma <objetivo> <accion>`)** — 6.4
  - Fuertes: Subpuntuaciones: usabilidad para novatos y GUI 9, cohesión de API 8, seguridad de migración 3, mantenibilidad 7, preparación de release 6. Tiene el mejor vocabulario uniforme: un único verbo por acción, idéntico en todos los objetivos, con `doctor`, `init`, códigos de salida y `--json`. Resuelve bien el registro declarativo `assets.toml` con cadena de contenedores (fa>sszl>ctpk), las incidencias NOT_SUPPORTED para IE2/IE3 y la guía de novato. El bloqueo tipográfico queda como validador obligatorio del servicio, sin interruptor.
  - Débiles: Mueve al paquete `dialogue_typography.py` y `dialogue_lock.py`. El bloqueo hashea bytes crudos relativos a `parents[1]`, así que validate() fallaría en 26 capas y habría que actualizar hashes, algo que AGENTS.md prohíbe. Archiva `ds_official` con shim que lanza ImportError, pero lo importan 5 capas (v33 eve_labels/mch_story, v36 dialogo_ids/nombres). Fusiona `ds_roster` en ie1 aunque llega por importación transitiva desde `reinsert`, que usa el `layout` bloqueado. Además, `construir(objetivo)` ignora que un único archive.fa contiene los tres juegos y el menú. No hay gate de hash de candidata por fase, y convierte `tr_prepare`/`tr_merge` en API sin pasar por las reglas de FURIGANA_LECCIONES.
- **Diseño B: biblioteca primero (inazuma_kit, src layout, Protocol tipado)** — 6.8
  - Fuertes: Subpuntuaciones: usabilidad para novatos y GUI 7, cohesión de API 9, seguridad de migración 4, mantenibilidad 8, preparación de release 8. Tiene la mejor disciplina de biblioteca: codecs puros bytes→bytes, `__all__`, mypy estricto en nucleo y servicios, errores tipados, CancelToken explícito sin asyncio y datos de juego fuera del código. La API de FaArchive (`read`/`find_entry`/copy-on-write) y la de eventos (`rebuild(events: dict)`) están bien diseñadas. Es el único con suite de contrato sobre un paquete falso y gate de cobertura.
  - Débiles: Coloca `dialogue_lock` en `juegos/ie1`, pero FONT_HASHES bloquea `font/FONT12.bcfnt`, `FONT12T` y `FONT8`, que están en la raíz de archive.fa y los comparten los tres juegos y el menú. El bloqueo es de la recopilación, no de IE1. Moverlo rompe también `parents[1]`. Archiva `ds_roster` y marca como delete dos tests, sin revisar las cadenas transitivas (reinsert → ds_roster, reinsert_var, ssd_reinsert). Aplica ruff/mypy sin excluir los ficheros bloqueados, cuando un reformateo cambia el hash. Promueve a ie1 código ya sustituido (`fix_ie1_title_logo`, `build_match_content_patch`). Unifica las tres tablas NDS aunque difieren en bytes (0xB5, comillas SJIS).
- **Diseño C: seguridad de migración primero (ie123kit, tools/ plano permanente)** — 7.2
  - Fuertes: Subpuntuaciones: usabilidad para novatos y GUI 7, cohesión de API 6, seguridad de migración 9, mantenibilidad 6, preparación de release 8. Es el único que no toca físicamente los cuatro ficheros bloqueados. Mantiene congelado `build_ui_revision.py`, que v55 ejecuta con exec() tras str.replace. Usa shims con alias en `sys.modules`, para que la mutación de globales estilo V37 siga funcionando. Tiene línea base de fallos previos (v33/gamestring), superficie dir() capturada, gates por módulo, política SSZL sin unificar y copia (no traslado) hacia `work/juego_principal`.
  - Débiles: Deja una doble superficie permanente: tools/ plano más un paquete que importa hacia atrás desde tools/ con un hack de sys.path dentro de nucleo. Mantiene importable código peligroso en `_legacy` y usa diez etapas pesadas. Su golden set (v65/v66) ya no existe: hoy solo hay probe_ie1_v66 y v67. Propone `.gitattributes tools/*.py -text` para todo tools/, pero no ha detectado que `tools/font_patch.py` tiene EOL mixto en el árbol de trabajo. Su hash aprobado (04cf7ff5…) no se reproduce ni desde el blob LF de HEAD (91519b5d…) ni con conversión CRLF (b9ec8032…): un clon limpio rompe hoy el bloqueo. También ignora que la candidata es de toda la recopilación, y el CLI por juego repite el defecto de A.

## Paquete
ie123kit. Es el nombre de importación y coincide con la API propuesta en docs/toolkit/catalogo_auditoria.json. Se distribuye como `ie123kit` desde `tools/pyproject.toml` y la orden de consola es `ie123`. El código vive en `tools/src/ie123kit/` para respetar la Norma 3 («herramientas en tools/»). Decisión final del propietario: ver open_questions.

## Recuento de scripts
ANTES (medido hoy):
- tools/ tiene 77 ficheros planos con lógica: 71 .py (63 módulos y 8 tests) y 6 .ps1.
- 60 de esos .py tienen CLI propia, y la documentación contiene 138 referencias a 49 scripts distintos.
- work/ tiene 186 scripts .py de capa (el encargo estimaba ~250), de los que 110 hacen sys.path.insert de tools/.
- Hay 27 patrones de código repetido entre capas.
- Estado según el catálogo: 23 core_active, 11 active, 25 legacy_superseded, 10 obsolete_dangerous y 2 diagnósticos.

DESPUÉS DE LA FASE 1:
- tools/ conserva 5 ficheros reales intocables: 4 bloqueados más build_ui_revision congelado.
- tools/ tiene además 29 shims generados sin lógica: 23 nombres importados por capas (menos los 5 reales), 5 transitivos (bcfnt, fa_repack, ds_roster, reinsert_var, ssd_reinsert), 1 `validate` y CLIs documentadas (verify_candidate, limpiar_work, nds_unpack, blz, harvest_log).
- Siguen los 6 .ps1.
- tools/_archivo/ recibe 27 retirados.
  (Actualizado en la F2.6, #55: `tools/_archivo/` se borró del árbol. Los retirados están en el
  historial de git y sus motivos en [`SCRIPTS_RETIRADOS.md`](SCRIPTS_RETIRADOS.md); la lista viva es
  `ie123kit.nucleo.compat.superficie.RETIRADOS`. Las filas de la tabla de traslados que apuntan a
  `tools/_archivo/<script>.py` se leen como «retirado», no como una ruta existente.)
- El paquete ie123kit tiene unos 38 módulos con lógica, en lugar de 63 dispersos, y 6 tests en tools/tests.
- Resultado: de 77 ficheros con lógica en tools/ se pasa a 11 (5 congelados y 6 .ps1). Las CLIs pasan de 60 a 5 heredadas, pendientes de sustituir.

DESPUÉS DE LA FASE 2:
- Una sola orden, `ie123`, con 12 acciones uniformes × 8 objetivos, más órdenes de proyecto.
- tools/ queda en 5 congelados, ≤ 24 shims de importación (solo nombres que importan capas antiguas; los de CLI se retiran al actualizar la documentación) y 4 .ps1 finos.
- setup_mobipeg y setup_vgmstream se mantienen. extract_nds.ps1 pasa a envoltorio de una línea o se archiva según decida el propietario.
- El paquete crece hasta unos 50 módulos, con las primitivas consolidadas desde los 27 patrones.
- Las tandas nuevas no crean scripts: son capas declarativas capa.toml más recursos. Solo si hace falta lógica a medida se usa apply.py con Capa(__file__) en unas 10 líneas, frente a las 40-80 de arranque actuales.

## Árbol
```
tools/                                   # Norma 3: todo sigue bajo tools/
  pyproject.toml                         # paquete ie123kit (src layout), script `ie123 = ie123kit.cli.main:main`, extras [dev]=pytest
  README.md                              # inicio rápido + tabla de equivalencias órdenes antiguas -> `ie123`
  ── CAPA DE COMPATIBILIDAD PLANA (sys.path de las capas de work/) ──
  dialogue_typography.py                 # BLOQUEADO v20 (hash de bytes crudos). Intacto, -text en .gitattributes
  font_patch.py                          # BLOQUEADO v20 (EOL mixto actual = bytes aprobados). Intacto, -text
  dialogue_lock.py                       # BLOQUEADO (parents[1] = raíz). Intacto, -text
  build_ie1_probe.py                     # BLOQUEADO (LAYOUT_HASH de `layout` + alias R). Intacto, -text
  build_ui_revision.py                   # CONGELADO: v55/pachangas/empaquetar.py hace exec() de su texto. -text
  <29 shims generados>.py                # 3-8 líneas sin lógica: añaden src/ a sys.path y hacen sys.modules[__name__] = módulo real
  _archivo/                              # NO importable (sin __init__, fuera de sys.path). README.md con motivo + enlace a FURIGANA_LECCIONES/issue
    <27 módulos retirados>.py  tests/
  build_patch.ps1 extract_nds.ps1 extract_romfs.ps1 jugar.ps1 setup_mobipeg.ps1 setup_vgmstream.ps1   # fase 2: envoltorios finos de `ie123`
  bin/                                   # binarios externos (git-ignored), localizados vía nucleo/config/herramientas.py
  src/ie123kit/
    __init__.py                          # __version__, API_VERSION; sin efectos al importar
    nucleo/                              # MOTOR: no sabe nada de ningún juego; no importa juego_principal/ie1/ie2/ie3/servicio
      config/     raiz.py (find_root: IE123_ROOT o subir hasta AGENTS.md+tools/pyproject.toml; prohibido parents[N])
                  ajustes.py (ie123.toml + ie123.local.toml + IE123_*), herramientas.py (3dstool, xdelta3, mobipeg x86 v2.1, vgmstream, ffmpeg)
      tipos.py                           # (fase 2) AssetRef, Resultado, Incidencia, Progreso, CancelToken: dataclasses JSON
      juego.py                           # (fase 2) JuegoBase/AccionesJuego: interfaz uniforme que implementa cada juego
      errores.py                         # FormatoError, ValidacionError(codigo, ruta, detalle), BloqueoTipograficoError
      util.py                            # sha256_bytes/sha256_file, escribir_json (UTF-8, ensure_ascii=False)
      compresion/ lz10.py  blz.py  sszl.py (unwrap, compress, compress_literal, reenvolver_como(politica='keep'|'raw'|'sszl'))
      contenedores/ fa.py (FaArchive B123: .d/.entries/_name congelados + read/index/glob/exists; fe_offset_of, append alineado 16)
                    arcv.py (entries(off,size,crc), rebuild)  nds_rom.py (FNT/FAT)  exefs.py (hashes/relleno ExeFS, experimental)
      registros/  tabla_fija.py (RecordTable/TableSpec: nunca trunca)  rangos.py (diff_ranges, assert_only_changed)
      texto/      ancho_completo.py (re-export de tools/dialogue_typography + decode_fullwidth inverso nuevo)
                  tipografia_v20.py (perfil bloqueado de la RECOPILACIÓN: re-export de build_ie1_probe.layout, approved_layout, lista de fuentes)
                  nds_latin.py (NDS_DEC, NDS_SJIS, dec_es, dec_jp, decode_cadena; DS_TABLE/decode_ds como tabla distinta, sin unificar bytes)
                  sjis_portador.py (es_encode truncante, GREEK, BOX_W, avance FONT12: semántica de reinsert intacta)
      eventos/    packnum.py (parse_index, entry_data, rebuild(pkh,pkb,reemplazos,align))  ssd.py (parse/replace)
                  instrucciones.py (fase 2: EventPack eve|mch, instructions, stage)  alineado_ids.py (tabla_nds, tabla_3ds, emparejar por ID)
      graficos/   ctpk.py  qna.py  pac_sprite.py  pintado.py (paint, paint_condensed)
                  texturas.py (fase 2: iter_ctpk, find_texture, apply_plan, validate_plan, previsualizaciones)
      fuentes/    bcfnt.py (lectura)  glifos.py (re-export de tools/font_patch bloqueado)  nftr.py (read_metrics, ancho, cabe)
      ejecutable/ smdh.py (patch_title...)  cro.py (fase 2: Cro, CroPatcher literales y reubicaciones con rango declarado)
      media/      moflex.py (rotación 0x16, yuv420, probe, encoder mobipeg/ffmpeg)  subtitulos_dat.py (.dat<->SRT, 30 Hz)
                  audio.py (SADL inspección/SAD<->WAV vía vgmstream; SWD/SED solo lectura en fase 2)
      construir/  candidata.py (base + aportaciones -> archive.fa + CROs + build.json)  capas.py (Capa(__file__), capa.toml)
                  instalar.py (Azahar LayeredFS con rehash)  rom.py (3dstool)  parche.py (xdelta3)  limpieza.py  registro_azahar.py
      validar/    bloqueo.py (llama al tools/dialogue_lock.validate intacto; fuentes extraídas de la candidata)
                  contenido.py (guardia git ls-files, Norma 2)  candidata.py (diff genérico: solo entradas/rangos declarados)
      compat/     shims.py (generador)  superficie.py (snapshot dir()/firmas)  importaciones.py (comprobador AST de work/)  golden.py
    juego_principal/                     # la recopilación: menú, selector, cargas, OP, banner. Solo importa nucleo
      __init__.py (JUEGO)  activos.toml  acciones.py
      # menu/title.arc (selector), menu/common.arc (pantallas de carga), menu/content|result|sd|extra.arc, menu/data_replace/**,
      # movie/OP.moflex, movie/logo_l5.moflex, cro/ina_menu.cro, message/jp/GameString.*, common/system/passing/face2d.arc,
      # font/*.bcfnt (solo lectura: bloqueadas), import/sItxInazuma123.itx, ExeFS banner.bnr/icon.icn (SMDH)
    ie1/  __init__.py  activos.toml  acciones.py
          texto/ eventos.py (diálogo eve)  mch.py  tablas.py (item.dat/STR, unitbase +16)  glosario.py
          graficos/ teclado.py (ROWS, rejilla 20 px)  nds_piezas.py (API estable sobre V37 sin tocar su fichero)
          media/ voces.py (inventario SAD EU-3DS)  cinematicas.py + cinematicas.toml (21 películas, 0x16)
          verificar.py (reglas EVE/CRO ina_main1/fuentes/media)  datos/ (pcs_conocidos.toml, rangos de eventos protegidos)
    ie2/  comun/ (reglas y datos comunes a las dos versiones)  tormenta_de_fuego/  ventisca_eterna/     # cada una: __init__, activos.toml, acciones.py
    ie3/  comun/  rayo_celeste/  fuego_explosivo/  amenaza_del_ogro/                               # ie2.* e ie3.* solo importan nucleo y su propio comun
    _legado/                             # importable SOLO a través de shims; excluido del servicio y del registro
      reinsert.py reinsert_var.py ssd_reinsert.py ds_official.py ds_roster.py validate.py build_glossary.py pkb_unpack.py ...  # fachadas con globales y main() originales
    servicio/                            # (fase 2) capa headless: CLI y GUI solo hablan con esto
      api.py (ServicioToolkit)  proyecto.py (Workspace)  registro_activos.py  trabajos.py (hilos, eventos, cancelación)  esquemas/ (*.schema.json)
    cli/  main.py (argparse 1:1 sobre ServicioToolkit, --json)  (tabla de equivalencias en servicio/equivalencias.py)
  tests/
    unidad/ (codecs con fixtures sintéticos)  compat/ (baseline_importaciones.json, superficie_v0.json, test_bloqueo_bytes.py)
    arquitectura/ (reglas de importación por AST)  contrato/ (suite parametrizada sobre los 8 objetivos)  golden/ (solo hashes: candidatas.sha256, capa_referencia.sha256)
    requiere_rom/ (marcados; se saltan en CI)
work/ (git-ignored)
  shared/ base_3ds/  candidatas/<cadena global vNN>/ (archive.fa + romfs/cro/*.cro + manifest.json)  releases/  herramientas/  verificacion/
  juego_principal/ capas/vNN/<linea>/  qa/  exportaciones/  registro.json  historico.json (capas antiguas de work/ie1 que tocan el menú)
  ie1/ fuentes/  capas/vNN/<linea>/  qa/  legacy/  exportaciones/  registro.json
  ie2/ {tormenta_de_fuego,ventisca_eterna,shared}/  ie3/ {rayo_celeste,fuego_explosivo,amenaza_del_ogro,shared}/
translation/ juego_principal/ (nuevo: glosario de menús)  ie1/  ie2/  ie3/  shared/
```

## CLI
Orden única: `ie123`, también accesible como `python -m ie123kit`. Cada subcomando es un adaptador argparse 1:1 sobre ServicioToolkit, sin lógica propia. `--json` imprime el Resultado serializado y `--proyecto RUTA` fija la raíz. Los verbos van en español y hay alias en inglés opcionales (ver open_questions).

Códigos de salida:
- 0: ok
- 1: incidencias de validación
- 2: uso incorrecto
- 3: violación del bloqueo tipográfico
- 4: falta una herramienta externa
- 5: operación no soportada por el objetivo

ÓRDENES DE PROYECTO (recopilación):
- `ie123 doctor`: comprueba Python, dependencias, 3dstool, xdelta3, mobipeg x86, vgmstream y ffmpeg, los sha de las ROM, el EOL y hash de los ficheros bloqueados, y el espacio libre (≥ 4 GB).
- `ie123 proyecto init --rom3ds X [--nds-es-ie1 Y ...]`: crea ie123.local.toml, work/<objetivo>/ (incluido work/juego_principal/) y translation/juego_principal/.
- `ie123 proyecto estado`
- `ie123 objetivos`: lista juego_principal, ie1, ie2.tormenta_de_fuego, ie2.ventisca_eterna, ie2.comun, ie3.rayo_celeste, ie3.fuego_explosivo, ie3.amenaza_del_ogro, con sus capacidades.
- `ie123 extraer romfs|nds [--objetivo ie1]`
- `ie123 construir --base vNN [--objetivos ie1,juego_principal] [--capas RUTA...] --salida vMM`: construye una candidata de toda la recopilación. Siempre ejecuta el bloqueo v20 y la guardia de contenido. Se niega a sobrescribir.
- `ie123 verificar --candidata vMM [--golden]`
- `ie123 instalar --candidata vMM [--lanzar] [--registro]`: instala en Azahar LayeredFS con rehash; se niega si azahar.exe está en ejecución.
- `ie123 parche --rom-base X --rom-parcheada Y --salida patch/…xdelta`
- `ie123 work limpiar [--borrar]`
- `ie123 compat comprobar [--golden]`: ejecuta los gates de migración.

ACCIONES POR OBJETIVO (idénticas para los 8; si el objetivo no las soporta devuelven NOT_SUPPORTED con código 5):
- `ie123 <objetivo> activos [--tipo grafico|texto|cinematica|voz|fuente|ejecutable] [--filtro PATRON]`
- `ie123 <objetivo> graficos exportar [--id ID|--todos] --a DIR`: genera PNG RGBA más <tex>.qna.json con rectángulos y metadatos CTPK.
- `ie123 <objetivo> graficos importar --id ID --desde PNG [--simular]`
- `ie123 <objetivo> textos exportar [--ambito eventos|tablas|cro] [--formato tsv|po] --a DIR`: una fila por registro, con id, jp, es_oficial, traduccion, max_px, max_bytes y estado.
- `ie123 <objetivo> textos importar --desde DIR [--simular]`
- `ie123 <objetivo> cinematicas exportar|importar [--id]`: MOFLEX↔MP4+SRT.
- `ie123 <objetivo> voces exportar|importar [--id]`: SADL→WAV. La importación acepta .SAD validado; WAV→SADL devuelve NOT_SUPPORTED hasta que exista codificador.
- `ie123 <objetivo> capas listar|aplicar [--hasta vNN]`: aplica capa.toml o apply.py heredado en subproceso con cwd=raíz.
- `ie123 <objetivo> construir|verificar|instalar`: atajos de las órdenes de proyecto restringidos a las aportaciones de ese objetivo sobre la última candidata.
- `ie123 <objetivo> estado`

COMPATIBILIDAD: toda orden documentada `python tools/X.py args` que siga viva reenvía sys.argv sin cambios a la misma main() a través del shim. Los scripts archivados no tienen shim; tools/_archivo/README.md y `ie123 compat equivalencias` indican la orden que los sustituye.

## API de servicio (GUI)
Paquete ie123kit.servicio (fase 2). La CLI y la futura GUI solo dependen de esta capa, y la GUI nunca toca ficheros directamente.

1) TIPOS (ie123kit.nucleo.tipos). Son dataclasses congeladas con to_json() y un JSON Schema publicado en servicio/esquemas/*.schema.json:
- `AssetRef{id, objetivo, tipo, ruta_romfs, cadena_contenedores:['fa','sszl','arcv','ctpk'], subruta, rects?:[{x0,y0,x1,y1,parte}], tamano, editable:bool, estado:'original'|'editado'|'traducido'|'construido', origen:'3ds_jp'|'3ds_eu'|'nds_es'|'manual', vista_previa?, sha256}`
  - Formato del id: `ie1:grafico:inazuma1/data_iz/a_title/title_t.arc#ie01_title_t_tlogo.tga`
  - Ejemplo de juego_principal: `juego_principal:cinematica:movie/OP.moflex`
- `Resultado{ok, datos, incidencias:[Incidencia], artefactos:[ruta], duracion_s, api_version}`
- `Incidencia{codigo, severidad:'error'|'aviso'|'info', mensaje, activo_id?, ruta?, ubicacion?, pista?}`. Códigos estables: TAMANO_PNG, RECT_QNA, GLIFO_NO_SOPORTADO, EXCEDE_PX, EXCEDE_BYTES, BLOQUEO_V20, NF_HUERFANO, PAGINAS_DISTINTAS, CRO_FUERA_DE_RANGO, LAYOUT_MOFLEX, HERRAMIENTA_AUSENTE, NOT_SUPPORTED, CONTENIDO_EN_GIT, GATE_FALLIDO (F2.4: un gate de `ie123 compat comprobar` que falla).
- `Progreso{fase, actual, total, mensaje}`
- `CancelToken{cancelar(), cancelado}`

2) INTERFAZ UNIFORME DE JUEGO (ie123kit.nucleo.juego.JuegoBase, abstracta). La implementan juego_principal, ie1, ie2.* e ie3.*, así que el servicio nunca ramifica por juego:
- `info() -> InfoObjetivo{id, nombre, prefijos_romfs, cros, capacidades:set}`
- `activos(ws, tipo=None, filtro=None) -> list[AssetRef]`
- `exportar(ws, ref, destino, formato=None, progreso, cancel) -> Resultado`
- `importar(ws, ref, origen, simular=True, progreso, cancel) -> Resultado`. Valida y devuelve un diff antes de escribir. Nunca trunca en silencio.
- `aportaciones(ws, capas) -> Aportacion{entradas_fa:{ruta:bytes|Path}, eventos:{'eve'|'mch': dir}, literales_cro:{cro: json}, romfs_sueltos:{ruta: Path}}`
- `reglas_validacion() -> list[Regla]`
- `perfil_texto(ambito) -> PerfilTexto` (para la recopilación hoy siempre es tipografia_v20)

La implementación por defecto de JuegoBase delega en nucleo según el tipo de activo, de modo que los juegos solo declaran datos (activos.toml) y reglas.

3) FACHADA (ie123kit.servicio.api.ServicioToolkit(workspace)):
- `objetivos()`
- `activos(objetivo, tipo, filtro)`
- `exportar(objetivo, ids, destino)`
- `importar(objetivo, id, fichero, simular)`
- `construir(SolicitudConstruccion{base, objetivos, capas, salida})`: la candidata es de TODA la recopilación, porque un único archive.fa contiene menú, IE1, IE2 e IE3 y las CRO son ina_menu, ina_main1, ina_main2 e ina_main3ogre. Se componen las aportaciones de cada objetivo en orden declarado, con conflictos de entrada como error. Se ejecutan SIEMPRE bloqueo.validate, la guardia de contenido y validar/candidata.
- `verificar(candidata, golden=None)`
- `instalar(candidata, emulador='azahar', lanzar=False)`
- `parche(rom_base, rom_parcheada, salida)`
- `limpiar(borrar=False)`
- `doctor()`

Todo método síncrono admite `progreso` y `cancel`.

4) TRABAJOS (servicio/trabajos.py):
- `enviar(fn, **kw) -> id_trabajo`
- `estado(id)`
- `eventos(id)`: iterador de Progreso e Incidencia para el hilo de la GUI.
- `cancelar(id)`

Los eventos también se registran en JSONL en work/shared/verificacion/trabajos/. No depende de asyncio: la GUI ejecuta en un hilo de trabajo (QThread o executor).

5) PROYECTO (servicio/proyecto.py Workspace):
- `ie123.toml` (en git, sin contenido de ROM): objetivos habilitados, convención de nombres de candidata y ruta de los manifiestos golden.
- `ie123.local.toml` (ignorado): rutas y sha256 de ROM, directorio de Azahar, fuente TTF y herramientas.
- `Workspace.dirs(objetivo)` devuelve work/<objetivo>/{capas, qa, exportaciones, registro.json}. Para ie2/ie3 incluye versión: work/ie2/tormenta_de_fuego/…, y su comun corresponde a work/ie2/shared/ según ARQUITECTURA.md.
- Las candidatas forman una cadena global inmutable en work/shared/candidatas/<nombre_vNN>/ con manifest.json (base y su sha, capas y sus hashes, salidas sha256, objetivos incluidos, runtime_verified:false).

6) REGISTRO DE ACTIVOS (servicio/registro_activos.py):
- Se construye a partir de `activos.toml` de cada juego, que es declarativo: familias con prefijo romfs, cadena de contenedores, perfil de texto, ámbito y contrapartida NDS/EU.
- Añade un escaneo perezoso: índice FaArchive, hijos ARCV, texturas CTPK, rectángulos QNA y registros SSD.
- Se cachea en work/<objetivo>/registro.json con clave sha de la base.
- El estado de cada activo sale de comparar con la base y con la última candidata.

7) EDICIÓN DESDE GUI: cada importación confirmada crea una capa nueva work/<objetivo>/capas/vNN/gui_<aaaammdd_hhmm>/ con capa.toml (operaciones reemplazar_entrada, textura_png, textos_tsv, literal_cro, cinematica_mp4, voz_sad) más sus recursos. Nunca se edita una candidata existente. Las capas Python antiguas siguen siendo ejecutables como capas de tipo `script`.

8) CÓMO APARECE work/juego_principal/:
- `ie123 proyecto init` crea work/juego_principal/{capas,qa,exportaciones} y translation/juego_principal/.
- `ie123 proyecto migrar-juego-principal --simular` escribe work/juego_principal/historico.json con la lista de capas existentes en work/ie1/capas que tocan activos del menú, como v33/smdh, v54/pantalla_inicio, v58/carga y v58/logos. NO las mueve, porque sus rutas parents[N] y los importlib de V37 dependen de su sitio.
- Las capas nuevas del menú van a work/juego_principal/capas/vNN/<linea>, con numeración vNN global compartida con la cadena de candidatas.
- limpieza.py y docs/ARQUITECTURA.md incorporan la nueva carpeta.

## API de librería
REGLAS DE IMPORTACIÓN. Las verifica tools/tests/arquitectura/test_importaciones.py, que analiza por AST todo src/:
- ie123kit.nucleo.* no importa juego_principal, ie1, ie2, ie3, servicio ni cli.
- juego_principal e ie1 importan solo ie123kit.nucleo.
- ie2.<version> importa solo nucleo e ie2.comun (análogo para ie3). Ningún juego importa otro.
- servicio importa nucleo y descubre los juegos mediante un registro explícito, sin importaciones cruzadas. cli importa solo servicio.
- _legado solo lo importan los shims de tools/.
- Prohibido en src/: `parents[` o `dirname(dirname`, rutas absolutas de máquina (C:/Users, Downloads), print/sys.exit en nucleo y efectos al importar.

API ESTABLE DE NUCLEO (nombres en `__all__`, codecs puros sobre bytes/Path/PIL.Image, binarios externos inyectados vía config.herramientas):
- compresion:
  - `lz10.compress/decompress/compress_optimal/compress_store`
  - `blz.decompress`
  - `sszl.unwrap/compress/compress_literal`
  - `sszl.reenvolver_como(original, nuevo_raw, politica='keep'|'raw'|'sszl', crecimiento_max=None)` (fase 2)
- contenedores:
  - `fa.FaArchive(path)` con .d, .entries, _name() congelados, y `.read(ruta)` (KeyError con rutas parecidas), `.index`, `.glob(prefijo)`, `.exists(ruta)`
  - `fa.fe_offset_of`
  - `fa.reemplazar_entrada(handle, arc, ruta, payload)` (anexión alineada 16)
  - `arcv.entries/rebuild`
  - `nds_rom.extraer(rom, destino)`
  - `exefs.reconstruir`
- registros:
  - `tabla_fija.RecordTable(data, TableSpec).get/text/set_text(..., max_chars, max_bytes)`: lanza excepción, nunca trunca
  - `rangos.diff_ranges`, `rangos.assert_only_changed`
- texto:
  - `ancho_completo.encode_fullwidth` (el mismo objeto que dialogue_typography) y `decode_fullwidth` (inverso exacto, nuevo)
  - `tipografia_v20.layout` (el mismo objeto que build_ie1_probe.layout), `approved_layout(texto)`, `FUENTES_BLOQUEADAS`
  - `nds_latin.NDS_DEC/NDS_SJIS/dec_es/dec_jp/decode_cadena` y `nds_latin.DS_TABLE/decode_ds`, distintos y documentados
  - `sjis_portador.es_encode(s, budget)` (trunca, heredado), `GREEK`, `BOX_W`, `avance`
- eventos:
  - `packnum.parse_index/entry_data/rebuild(pkh, pkb, reemplazos, comprimir=True, align=4|'auto')`
  - `ssd.parse/replace/TextRecord`
  - `alineado_ids.tabla_nds/tabla_3ds/emparejar`
  - `instrucciones.EventPack.from_archive(arc, 'eve'|'mch').events()/instructions(eid)/find(eid, opcode, argumento)/stage(...)` (fase 2)
- graficos:
  - `ctpk.decode/encode/metadata`
  - `qna.regions` y `QnaLayout` (fase 2)
  - `pac_sprite.decode/encode/index`
  - `pintado.paint/paint_condensed`
  - `texturas.iter_ctpk/find_texture/load_texture/apply_plan(base, plan, salida, previews, rewrap='raw')/validate_plan` (fase 2), además de ayudas de imagen (preview_pair, paste_centered, fit_into, drop_shadow)
- fuentes:
  - `bcfnt.BCFNT`
  - `glifos.Font/PLAN/patch_font_bytes` (re-export del bloqueado)
  - `nftr.read_metrics/ancho/cabe`
- ejecutable:
  - `smdh.patch_title`
  - `cro.Cro(data).segments/relocations/retarget` y `cro.CroPatcher(base).literal(offset, esperado, nuevo, capacidad, encoder=encode_fullwidth)` (fase 2)
- media:
  - `moflex.set_moflex_rotation/disposicion/from_mp4/to_mp4`
  - `subtitulos_dat.leer/escribir/a_srt/desde_srt`
  - `audio.inspect_sad/sad_a_wav`
- construir:
  - `candidata.construir(base, salida, aportaciones, rehusar_sobrescribir=True) -> build.json`
  - `capas.Capa(__file__).raiz/aqui/extra(rel)/romfs(rel)` y `capas.ejecutar(main)`
  - `instalar.azahar(candidata, title_id='00040000000BB800')`
  - `rom.build_3ds`, `parche.xdelta`, `limpieza.objetivos/limpiar`, `registro_azahar.parse/merge`
- validar:
  - `bloqueo.validar(candidata_o_dir_fuentes)`: llama al tools/dialogue_lock.validate intacto
  - `contenido.guardia_git()`
  - `candidata.verificar(base, candidata, capas, literales)`
- config:
  - `raiz.find_root()`
  - `ajustes.cargar()`
  - `herramientas.localizar(nombre)`

Los módulos bloqueados se exponen por re-export con importación perezosa de tools/. No se copian, y los tests verifican la identidad de objetos.

## Configuración
RESOLUCIÓN, por orden de precedencia: flags de CLI > variables IE123_* (IE123_ROOT, IE123_AZAHAR, IE123_FUENTE_TTF, IE123_HERRAMIENTAS) > ie123.local.toml (raíz, git-ignored) > ie123.toml (raíz, en git) > valores por defecto. Los valores por defecto reproducen exactamente el comportamiento de hoy.

1) ie123.toml (en git, sin secretos ni contenido): [proyecto] idioma='es-ES', nombres_europeos=true; [candidatas] patron='probe_ie1_v{n}', conservar=2 y golden=['probe_ie1_v66','probe_ie1_v67']; [objetivos] habilitados con su versión; [golden] manifiestos='tools/tests/golden'.

2) ie123.local.toml (ignorado; lo crea `ie123 proyecto init`): [roms] rutas y sha256 (3DS JP, NDS ES IE1/IE2, 3DS EU IE1/IE3); [azahar] mods_dir, cuyo valor por defecto es %APPDATA%/Azahar/load/mods; [fuentes] ttf_ui, que por defecto es C:/Windows/Fonts/arialbd.ttf y es el valor actual en 11 capas; [herramientas] 3dstool, xdelta3, mobipeg (x86 v2.1), vgmstream, ffmpeg, con valor por defecto tools/bin y work/shared/herramientas/media_tools.

3) Datos de juego como ficheros de paquete, no como código: juego_principal/activos.toml, ie1/activos.toml, ie1/media/cinematicas.toml, ie1/datos/pcs_conocidos.toml, rangos de eventos protegidos (DONT_TOUCH 81000040, apertura 90000000..92010249) y prefijos romfs (inazuma1/, inazuma2/, inazuma3/, inazuma3_ogre/, menu/, movie/, font/, message/, patchscript/).

4) Rutas rancias convertidas en ajustes con nombre y error claro: work/probe_ie1_v14_inputs/extra_ascii, que no existe y citan 29 scripts, pasa a `bloqueo.fuentes`. Por defecto, bloqueo.validar extrae las 5 fuentes aprobadas de la candidata base a un temporal. Los logos de C:/Users/luish/Downloads pasan a `recursos_usuario.dir`, las bases fijadas probe_ie1_vNN a `candidata('anterior')` y work/romfs y work/exefs.bin a `base_3ds()`.

5) Lo que la configuración NO puede tocar: los hashes del bloqueo v20 (viven en tools/dialogue_lock.py), la política SSZL de capas ya aprobadas, el encoder de diálogo y el layout 0x16. No existe clave para desactivar validadores.

6) Raíz: find_root busca IE123_ROOT o sube hasta encontrar AGENTS.md junto a tools/pyproject.toml. Los shims de tools/ conservan parents[1] porque siguen en tools/.

## Compatibilidad
GARANTÍAS, verificadas con los gates:

(a) Shims generados. `python -m ie123kit.nucleo.compat.shims generar` escribe tools/<nombre>.py. Contenido:
- Sin paquete instalado: `sys.path.insert(0, <tools>/src)` si falta.
- `import importlib, sys; sys.modules[__name__] = importlib.import_module('ie123kit.…')`.
- Si es CLI: `if __name__ == '__main__': sys.modules[__name__].main()` con el mismo argv.

Consecuencias:
- Como el shim es un alias del módulo real, la mutación de globales (lz10.MAX_CAND, build_glossary.REPO/DS/ES/OUT, validate.REPO) actúa sobre el objeto que usa el código.
- Los módulos divididos o fusionados apuntan a una fachada ie123kit/_legado/<nombre>.py que conserva nombres públicos y privados (pkb_unpack._decode_string, FaArchive._name, reinsert.BOX_W/_advance/es_encode) y su main().
- No se emiten avisos por stdout/stderr salvo con IE123_AVISOS=1, para no alterar informes ni bytes.
- El código trasladado se copia literalmente (git mv y cambio de líneas de importación). Las refactorizaciones van en commits posteriores y solo tras pasar los gates.

(b) Ficheros bloqueados físicamente intactos: tools/dialogue_typography.py, tools/font_patch.py, tools/dialogue_lock.py y tools/build_ie1_probe.py.
- .gitattributes pone `-text` en esos 4 y en build_ui_revision.py.
- Hallazgo: font_patch.py tiene hoy EOL mixto. Su hash aprobado 04cf7ff5… solo coincide con el árbol de trabajo actual, no con el blob de HEAD (91519b5d…) ni con un clon CRLF (b9ec8032…). Hay que fijar esos bytes exactos en git (commit con -text) para que un clon limpio o la CI no rompan validate(). No cambia ningún byte ni hash, pero afecta a ficheros bloqueados, así que requiere confirmación explícita del propietario.
- ruff/black los excluyen.
- tools/tests/compat/test_bloqueo_bytes.py compara sha256 contra la línea base y ejecuta validate() con fuentes extraídas de probe_ie1_v67.

(c) Ficheros consumidos como texto o por ruta, congelados:
- tools/build_ui_revision.py (exec en v55; un test comprueba los literales eve.pkh/.pkb).
- work/ie1/capas/v37/graficos_nds/apply.py (14 capas lo cargan con importlib y mutan BASE/PLAN/HERE).
- v33/eve_labels/common.py (chdir al importar).
- v51/voces/apply.py (lee argv al importar).

La lista blanca de limpieza.py los protege. ie1/graficos/nds_piezas.py solo los envuelve.

(d) Nombres que colisionan en sys.path (validate, apply, common, prepare, check, lib): tools/validate.py se mantiene durante la fase 1 para que el orden de resolución no cambie.

(e) Rutas y cwd: las 48 capas dependientes de cwd siguen funcionando porque la invocación documentada es desde la raíz. gs_common.py de v33/gamestring (parents[2]) ya está roto: se registra en la línea base como fallo previo y se abre issue, sin arreglarlo en silencio.

(f) Bytes de salida: no se cambian políticas por defecto (SSZL raw/keep/literal, fuente arialbd, truncado de es_encode, tabla DS_TABLE frente a NDS_DEC).

(g) Retirada de shims: módulo a módulo, y solo cuando el comprobador AST y un smoke de importación real muestren cero importadores en work/ y el propietario lo apruebe. Los 5 ficheros congelados nunca se retiran.
- **Actualización F2.7 (#102, petición del usuario):** retirados los 22 shims restantes, `bcfnt` incluido. Antes se migraron todos sus importadores (capas de work/, tests, paquete, CI, docs) a `ie123kit.<...>`. Los congelados, que no se pueden editar, siguen importando 7 nombres planos (`fa_unpack`, `fa_repack`, `lz10`, `pkb_unpack`, `reinsert`, `ssd_records`, `bcfnt`): los resuelve `ie123kit.nucleo.config.congelados.preparar()` con un resolutor en `sys.meta_path` que devuelve el mismo objeto módulo que daba el shim. Como script se lanzan con `python -m ie123kit.nucleo.compat.congelados <nombre> …`. La tabla de equivalencias queda en `nucleo.compat.shims.DESTINOS` y `tools/README.md`.

(h) Capas antiguas: nunca se reescriben dentro de la migración. `ie123 <objetivo> capas aplicar` las ejecuta en subproceso con cwd=raíz.

## Empaquetado y release
- tools/pyproject.toml usa setuptools con src layout: requires-python >= 3.12, dependencias Pillow, numpy y capstone, extra [dev] con pytest y ruff (ruff excluye los ficheros bloqueados y _archivo/). Se instala en desarrollo con `pip install -e tools[dev]`. Sin instalar, los shims añaden src/ a sys.path, de modo que un clon nuevo y las capas existentes no necesitan pip.
- Script de consola: `ie123`. Versión del kit independiente del parche (ie123kit 0.x, tag `toolkit-v0.N`). `API_VERSION` semántica del servicio, que la GUI comprueba al abrir el proyecto.
- No se publica en PyPI. A los jugadores solo se distribuye el .xdelta con DeltaPatcher mediante el workflow existente .github/workflows/release.yml, que no cambia (Norma 2).
- CI nueva, .github/workflows/toolkit.yml, en windows-latest y ubuntu-latest:
  - checkout (gracias a `-text` los bytes bloqueados coinciden en ambos SO)
  - `pip install -e tools[dev]`
  - `python -m pytest tools/tests -m "not requiere_rom"` (unidad, arquitectura, contrato, compat sin ROM, esquemas JSON)
  - sha256 de los 4 ficheros bloqueados
  - guardia `git ls-files`, que falla si se rastrean Roms/, work/, .3ds/.cia/.nds/.fa/.arc/.lzs/.STR/.dat/.pkb/.pkh/.bcfnt/.NFTR/.moflex/.mods/.SAD o PNG de más de 256 KB fuera de logos/ autorizados
- Los gates con ROM (regeneración golden y hash de candidata) se ejecutan en local con `ie123 compat comprobar --golden` antes de cada merge de fase. Su resultado se anota en el issue.
- Paso previo obligatorio: commitear limpiar_work.py (hoy sin rastrear) y decidir los 40 ficheros de tools/ con cambios sin commitear. La línea base golden debe reflejar código commiteado.
- Documentación:
  - tools/README.md: inicio rápido y tabla de equivalencias.
  - docs/toolkit/GUIA_NOVATO.md: de la ROM a la candidata en 5 órdenes.
  - docs/toolkit/OBJETIVOS.md: capacidades por objetivo.
  - tools/_archivo/README.md: por qué se retiró cada script, con enlaces a FURIGANA_LECCIONES e issues.
  - Actualización de docs/ARQUITECTURA.md (juego_principal, tools/src) y de las órdenes de CLAUDE.md/AGENTS.md, sin tocar el bloqueo tipográfico.

## Tests
Cinco niveles. Ningún fixture contiene datos extraídos (Norma 2): son sintéticos y se generan en el propio test.

1) UNIDAD (tools/tests/unidad, CI):
- Se trasladan los 6 tests activos: bloqueo, ancho completo, layout v20, ssd, formatos UI, pac_sprite y lz10.
- Hoy: 27 tests, OK con 1 skip. Tras archivar test_compact_typography y test_validate_inputs se fija el nuevo recuento esperado en el issue.
- Round-trip decode(encode(x)) == x para lz10 (incluido compress_optimal mínimo), sszl (unwrap∘compress), arcv, ctpk en todos los formatos, pac_sprite, ssd, packnum.rebuild, fa (archivo B123 sintético con 3 entradas), smdh, subtitulos_dat↔SRT y decode_fullwidth∘encode_fullwidth.
- Las entradas malformadas lanzan FormatoError.
- Test que fija las diferencias entre NDS_DEC y DS_TABLE (0xB5, comillas SJIS) para impedir unificarlas por accidente.

2) ARQUITECTURA (CI):
- Reglas de importación por AST: nucleo no importa juegos, un juego no importa otro, ie2.* solo su comun.
- Sin parents[N] ni rutas de máquina en src/, sin efectos al importar (se importa cada módulo en un subproceso limpio y se comprueba que no hay escritura ni salida).
- Los shims no contienen lógica (AST: solo alias).

3) COMPAT (tools/tests/compat):
- (a) Superficie: dir() y firmas de los 71 módulos, capturadas en la fase 1.0 en superficie_v0.json. Los módulos con efectos al importar se capturan por AST. Se exige igualdad en cada shim.
- (b) Identidades: encode_fullwidth, layout y el objeto validate del paquete son los de tools/.
- (c) test_bloqueo_bytes: sha256 de los 4 bloqueados y de build_ui_revision igual a la línea base, más literales eve.pkh/.pkb presentes.
- (d) Comprobador de importaciones de work/ (ie123kit.nucleo.compat.importaciones, stdlib pura, ejecutable antes de existir el paquete):
  - Recorre work/**/*.py y extrae por AST los `import X` y `from X import …` absolutos.
  - Resuelve cada nombre con importlib.util.find_spec usando sys.path = [carpeta del script, carpetas hermanas insertadas por el propio script cuando son literales, tools/].
  - Resuelve `importlib.util.spec_from_file_location` con rutas literales.
  - Verifica que los nombres importados desde un módulo de tools (`from fa_unpack import FaArchive`) existen en su superficie.
  - Salida: conjunto de no resueltos, que debe ser ⊆ baseline_importaciones.json.
- (e) Smoke de importación real, solo local: importa en subproceso con cwd=raíz cada módulo de tools/ que usan las capas.

4) CONTRATO (fase 2, CI):
- Suite parametrizada sobre los 8 objetivos: implementan JuegoBase; activos.toml valida contra su esquema; toda capacidad declarada es invocable y las no declaradas devuelven NOT_SUPPORTED.
- Resultados serializables (json.dumps(to_json())) y conformes a su JSON Schema.
- Progreso monótono, cancelación respetada, `importar(simular=True)` no escribe nada (hash del árbol antes y después).
- Incidencias en lugar de excepciones para PNG de tamaño erróneo, texto que excede px/bytes, glifo no soportado y %NF huérfano.
- Flujo GUI sin cabeza sobre un proyecto sintético: abrir, listar, exportar PNG, modificar un píxel dentro del rect QNA, importar con simulación, importar, construir, verificar. Solo cambia esa entrada y el bloqueo pasa.

5) GOLDEN, local con ROM (@requiere_rom, tools/tests/requiere_rom):
- (a) Regenerar work/ie1/capas/v67/titulo_logo/apply.py, cuya base probe_ie1_v66 existe hoy. Antes se hace copia de seguridad de su extra/ en el temporal del sistema y después se compara sha256 de cada fichero de extra/ con capas_v67.sha256. Si hay diferencia se restaura y el gate falla.
- (b) Reconstruir la candidata: `python -m ie123kit.nucleo.compat.congelados build_ui_revision --base work/shared/candidatas/probe_ie1_v66/archive.fa --ui work/ie1/capas/v67/titulo_logo --output <TEMP>/ie123_regen/probe_ie1_v67/archive.fa`. El sha256 debe ser 72ef7133924e981e4736e240368f716140ca35f62a5c131d7f01c1ead9cffa91 (archive_sha256 de probe_ie1_v67/archive.build.json) y la CRO resultante debe coincidir con probe_ie1_v67/romfs/cro/ina_main1.cro. En fase 2 se exige lo mismo con `ie123 construir`.
- (c) `ie123 verificar` devuelve el mismo informe que verify_candidate.py (sin campos de tiempo ni rutas absolutas).
- (d) bloqueo.validar sobre probe_ie1_v67.
- (e) Round-trips de exportar e importar sin cambios sobre menu/title.arc e inazuma1/data_iz/a_title/title_t.arc: las entradas quedan idénticas.

6) EMULADOR: manual y obligatorio según docs/PROTOCOLO_QA_IE1.md para cualquier fase que cambie código de construcción o instalación. Se prueba hasta la primera pachanga hablando con varios NPC, y el proceso se detiene en el primer fallo. Ningún test automático marca runtime_verified=true.

## Mapa de módulos
| Antiguo | Nuevo | Acción | Nota |
|---|---|---|---|
| tools/fa_unpack.py | ie123kit/nucleo/contenedores/fa.py | move | 67 capas lo importan. El traslado es literal, cambiando solo las líneas de importación, con shim de alias en sys.modules. Se congelan .d, .entries (path, abs_off, size), data_off, de_off, fe_off, de_cnt y _name(). read/index/glob/exists se añaden en fase 2 sin tocar ese contrato. v33/eve_labels/validate.py pasa un Stub. |
| tools/fa_repack.py | ie123kit/nucleo/contenedores/fa.py | merge | fe_offset_of y la anexión alineada a 16 bytes se integran en fa.py. El shim es obligatorio, porque build_ie1_probe (bloqueado) lo importa transitivamente. Su main() solo lo usaba build_3ds_var y va a _archivo. ROOT pasa de parents[1] a find_root. |
| tools/lz10.py | ie123kit/nucleo/compresion/lz10.py | move | 23 capas lo importan. Alias en sys.modules para que siga funcionando la mutación de la global MAX_CAND. Primer candidato de la subfase 1.3. |
| tools/blz.py | ie123kit/nucleo/compresion/blz.py | move | Solo descompresión. Mantiene la CLI documentada `python tools/blz.py in out` mediante shim hasta la fase 2 (`ie123 nds blz`). No se reintroduce la recompresión BLZ (FURIGANA_LECCIONES). |
| tools/sszl.py | ie123kit/nucleo/compresion/sszl.py | merge | Absorbe unwrap (desde ui_archive). compress y compress_literal siguen siendo funciones con nombre propio, y no se cambia ningún valor por defecto, porque v54, v64 y v65 dependen de su política exacta. reenvolver_como(politica) llega en fase 2 y es explícita. |
| tools/ui_archive.py | ie123kit/nucleo/contenedores/arcv.py (+ unwrap en nucleo/compresion/sszl.py) | split | 33 capas lo importan. La fachada _legado/ui_archive.py re-exporta entries y unwrap con el orden de tuplas (off, size, crc). |
| tools/nds_unpack.py | ie123kit/nucleo/contenedores/nds_rom.py | move | Extractor en Python puro de las ROM NDS ES; sustituye a ndstool, que no está en tools/bin. Se conserva la estructura de salida outdir/data_iz/... Shim de CLI hasta `ie123 extraer nds`. |
| tools/pkb_unpack.py | ie123kit/nucleo/eventos/packnum.py + nucleo/texto/nds_latin.py (decode_cadena) | split | parse_index lo usan 20 capas y _decode_string (privado) 8 tools. La fachada _legado conserva los nombres privados. lz10_decompress, copia literal, pasa a ser alias de lz10.decompress. El paquete importa NDS_DEC explícitamente. El fallback silencioso a {} solo ocurría si se ejecutaba fuera de la raíz, nunca en la invocación documentada. |
| tools/pkb_scan.py | tools/_archivo/pkb_scan.py | archive | Diagnóstico sin importadores. Su premisa (texto en bytecode sin LZ10) es errónea según EVENT_SCRIPT_FORMAT.md. |
| tools/ssd_records.py | ie123kit/nucleo/eventos/ssd.py | move | Implementación correcta del formato SSD, importada por 18 capas. Traslado literal con alias. Su test pasa a tests/unidad. |
| tools/ssd_reinsert.py | ie123kit/_legado/ssd_reinsert.py | archive | obsolete_dangerous: ignora el byte de tamaño de registro y genera tablas inválidas. Solo lo importan transitivamente reinsert y reinsert_var, así que conserva shim. Su CLI se niega a ejecutarse y remite a ssd.replace. |
| tools/reinsert.py | ie123kit/nucleo/texto/sjis_portador.py (es_encode, GREEK, BOX_W, _advance, FONTS) + ie123kit/_legado/reinsert.py (load_translations, main etapa 7) | split | El `layout` bloqueado usa R.BOX_W y R._advance por nombre, por lo que la fachada _legado debe exponerlos idénticos. es_encode mantiene su truncado, que usan v43/equipos y v50, y NO se unifica con encode_fullwidth. |
| tools/reinsert_var.py | ie123kit/_legado/reinsert_var.py | archive | obsolete_dangerous: el offset-fixup corrompía eventos (FURIGANA_LECCIONES ❌#8/#11/#13). Es transitivo desde reinsert, por eso conserva shim. Su CLI se niega a ejecutarse. |
| tools/reinsert_test.py | tools/_archivo/reinsert_test.py | archive | Prueba de concepto de la etapa 7. Nadie la referencia. |
| tools/recompress_test.py | tools/_archivo/recompress_test.py | archive | Diagnóstico v9 con efectos al importar y rutas inexistentes (work/fa_extract). No debe quedar importable. |
| tools/dialogue_typography.py | tools/dialogue_typography.py (re-exportado por ie123kit/nucleo/texto/ancho_completo.py) | keep_script | BLOQUEADO v20 (SOURCE_HASHES 8e983419…), importado por 44 capas. No se mueve, reformatea ni renombra. Se le aplica `-text` en .gitattributes para que un clon con autocrlf=true no lo convierta a CRLF. ruff/black lo excluyen. |
| tools/dialogue_lock.py | tools/dialogue_lock.py (envuelto por ie123kit/nucleo/validar/bloqueo.py) | keep_script | BLOQUEADO y dependiente de parents[1]. Es un validador de TODA la recopilación: FONT_HASHES incluye font/FONT12/FONT12T/FONT8.bcfnt, que están en la raíz de archive.fa, e inazuma1/.../FONT*.NFTR. El servicio lo llama siempre, sin opción para saltarlo. |
| tools/font_patch.py | tools/font_patch.py (re-exportado por ie123kit/nucleo/fuentes/glifos.py) | keep_script | BLOQUEADO (04cf7ff5…). OJO: su EOL actual es mixto y el hash aprobado no se reproduce desde git (blob LF 91519b5d…, CRLF b9ec8032…). En la fase 1.0 se fijan esos bytes exactos con `-text`, previa confirmación del propietario y sin cambiar ni un byte ni el hash. Hace `from bcfnt import BCFNT`, así que el shim de bcfnt es permanente. |
| tools/build_ie1_probe.py | tools/build_ie1_probe.py (layout re-exportado por ie123kit/nucleo/texto/tipografia_v20.py) | keep_script | BLOQUEADO: LAYOUT_HASH cubre el texto de `layout` y su alias R. El fichero queda intacto. Su main() (candidatas v7-v27) es legado y no se porta, porque construir/candidata.py lo sustituye. Las 26 capas lo importan solo por `layout`, así que el código nuevo usa tipografia_v20 con importación perezosa. |
| tools/build_ui_revision.py | ie123kit/nucleo/construir/candidata.py + nucleo/eventos/packnum.py (rebuild); el fichero original queda congelado en tools/ | split | Es el ensamblador actual (probe_ie1_v67/archive.build.json). v55/pachangas/empaquetar.py hace exec() de su TEXTO tras str.replace de 'inazuma1/data_iz/script/eve.pkh/.pkb', así que no puede sustituirse por un shim. Un test comprueba que esos literales siguen presentes. La lógica se generaliza en el paquete: eve/mch y todas las CRO. |
| tools/ds_official.py | ie123kit/nucleo/texto/nds_latin.py (DS_TABLE, decode_ds) + ie123kit/_legado/ds_official.py (load_ds_events, load_3ds_events, ds_lines, jp_lines, align, main) | split | Prohibido para regenerar (#36), pero 5 capas lo importan (v33 eve_labels y mch_story, v36 dialogo_ids y nombres). La fachada _legado se conserva. main()/align() se niegan a ejecutarse sin --legado-lo-se, y se excluye del servicio. DS_TABLE se mantiene como tabla distinta de NDS_DEC (0xD9=É, 0xA6=Í). |
| tools/ds_roster.py | ie123kit/_legado/ds_roster.py | archive | Sustituido por v36/nombres (+16, fullwidth, 7 caracteres). Es transitivo desde reinsert, por eso conserva shim. La regla +16/NUL (issue #16) se reimplementa en ie1/texto/tablas.py en la fase 2. |
| tools/audit_dialogo_ids.py | ie123kit/nucleo/eventos/alineado_ids.py (tabla_nds, tabla_3ds, emparejar) + ie123kit/ie1/verificar.py (auditoría IE1) | split | Método canónico de emparejamiento por ID (18.343 pares). Lo usan 1 capa y v51/voces/auditoria.py, así que la fachada _legado conserva los nombres. Es genérico: IE2 lo reutilizará desde nucleo. |
| tools/audit_ie1_voiced_text.py | tools/_archivo/audit_ie1_voiced_text.py | archive | Sustituido por work/ie1/capas/v51/voces/auditoria.py (por ID). Sin importadores. Su regla (película o voz posterior acota la búsqueda) se documenta en ie1/media/voces.py. |
| tools/build_glossary.py | ie123kit/nucleo/texto/nds_latin.py (NDS_DEC, NDS_SJIS, dec_es, dec_jp) + nucleo/registros/tabla_fija.py (names_from_dat, strings_from_str) + acción `glosario` de cada juego (fase 2) | split | Lo importan 4 capas y pkb_unpack. La fachada _legado conserva REPO/DS/ES/OUT como globales que main() reasigna. La semántica de dec_es (salto de línea→espacio, '~'→'º', colapso de espacios) debe quedar intacta. |
| tools/build_translation.py | tools/_archivo/build_translation.py | archive | obsolete_dangerous: sobrescribe translation/ie*/dialogo.csv con emparejamiento por orden (#36). |
| tools/str_align.py | tools/_archivo/str_align.py | archive | Emparejamiento por índice ingenuo (item.STR 300 frente a 603). Su tabla NDS_FIX queda superada por nds_latin. |
| tools/nds_str_dump.py | tools/_archivo/nds_str_dump.py | archive | Volcado ASCII trivial de la fase 2 inicial. Sin importadores. |
| tools/tr_prepare.py | tools/_archivo/tr_prepare.py | archive | Flujo de lotes IA de 2026-06-14 ya terminado, con rutas rotas. Sus invariantes pasan a validaciones de `textos importar`: %NF fuera y conteo de \f. |
| tools/tr_merge.py | tools/_archivo/tr_merge.py | archive | Mitad de fusión del mismo flujo. La regla «solo rellenar pendiente o vacío» se convierte en validación del importador de textos en fase 2. |
| tools/align_events.py | tools/_archivo/align_events.py | archive | Alineador por orden (Needleman-Wunsch), fallido según #36. dialogue_runs/is_furigana siguen en la fachada _legado de pkb_unpack. |
| tools/patch_code.py | tools/_archivo/patch_code.py | archive | obsolete_dangerous: saltos a cuevas de la CRO imposibles (crash 0xAD9E38). NO_CODE_PATCH=1 queda como regla documentada. |
| tools/patch_cro.py | tools/_archivo/patch_cro.py | archive | obsolete_dangerous: la cueva 0x50E14 es zona de reubicación (crash 0xAD9E1C). El CroPatcher de nucleo (fase 2) solo edita literales y reubicaciones declaradas, nunca cuevas. |
| tools/patch_exefs.py | ie123kit/nucleo/contenedores/exefs.py (hashes y relleno ExeFS) + tools/_archivo/patch_exefs.py (ruta code.bin/exheader) | split | La primitiva ExeFS se necesita para banner.bnr/icon.icn de juego_principal y se marca experimental. No se cambia code_size (Azahar se cierra). |
| tools/patch_smdh_title.py | ie123kit/nucleo/ejecutable/smdh.py (usado por juego_principal) | move | Importado por v33/smdh. Se conservan patch_title, TITLE_TABLE_OFFSET, TITLE_SLOT_SIZE y SMDH_MAGIC. Nunca sobrescribe el SMDH fuente. |
| tools/ie1_keyboard.py | ie123kit/ie1/graficos/teclado.py | move | v41/teclado importa ROWS. La rejilla de 20 px y el mapa de 314 bytes con CRLF son reglas de IE1. |
| tools/ie1_tables.py | ie123kit/nucleo/registros/tabla_fija.py (genérico) + ie123kit/ie1/texto/tablas.py (TableSpec item.dat/STR) | split | Sin importadores. Se toma la regla más estricta de v33/data/lib.encode_field: nunca truncar, emparejar el texto JP antes de editar y ranuras de 32 bytes. |
| tools/validate.py | ie123kit/_legado/validate.py | archive | Validador del pipeline eve_var abandonado. Conserva shim durante la fase 1, porque el nombre `validate` colisiona en sys.path con los validate.py de las capas y no debe alterarse su resolución. Se retira en fase 2 solo si el comprobador AST y la importación real lo permiten. |
| tools/verify_build.py | tools/_archivo/verify_build.py | archive | Comprobaciones SAME_SIZE de la era v27. Sin llamadores. |
| tools/verify_candidate.py | ie123kit/nucleo/validar/candidata.py (diff genérico, sha, rangos declarados) + ie123kit/ie1/verificar.py (EVE, ina_main1.cro, fuentes) | split | Paso de verificación documentado. El shim de CLI reenvía el mismo argv hasta `ie123 verificar`. runtime_verified sigue siendo False. |
| tools/verify_v21.py | tools/_archivo/verify_v21.py | archive | Aserciones puntuales contra v21, que ya no existe. |
| tools/ctpk_ui.py | ie123kit/nucleo/graficos/ctpk.py | move | 33 capas lo importan. encode(decode(x)) == x byte a byte y los bloques ETC1A4 no editados se copian literalmente. |
| tools/qna_regions.py | ie123kit/nucleo/graficos/qna.py | move | Solo lectura. En fase 2 exporta los rectángulos como sidecar .qna.json junto al PNG. Índice 0xFFFFFFFF = parte sin textura. |
| tools/translate_ui_textures.py | ie123kit/nucleo/graficos/pintado.py (paint, paint_condensed) + nucleo/graficos/texturas.py (bucle de manifiesto → apply_plan, fase 2) | split | Lo usan 9 capas y V37. La salida ARCV sin envolver ('raw') y la fuente por defecto arialbd se mantienen en la ruta del shim para no alterar bytes. En el paquete la fuente pasa a ser un ajuste con nombre. |
| tools/legacy_sprite.py | ie123kit/nucleo/graficos/pac_sprite.py | move | Sprites DS PAC 4bpp, activos. «legacy» no significa obsoleto. Se preservan los índices de paleta duplicados. |
| tools/fix_ie1_title_logo.py | tools/_archivo/fix_ie1_title_logo.py | archive | Rehecho por v60, v62, v63 y v67/titulo_logo. Tenía una ruta fija a Downloads. |
| tools/bcfnt.py | ie123kit/nucleo/fuentes/bcfnt.py | move | Shim PERMANENTE: el font_patch.py bloqueado hace `from bcfnt import BCFNT`. La semántica de parse no cambia (claves TGLP, offsets relativos al cuerpo). |
| tools/nftr_metrics.py | ie123kit/nucleo/fuentes/nftr.py | move | Lo usan 3 capas. Solo lectura. Bearing con signo ('<bBB'). En fase 2 añade ancho() y cabe() para el límite de 117 px. |
| tools/compact_typography.py | tools/_archivo/compact_typography.py | archive | Experimentos v4/v8 superados por el bloqueo v20. No debe ser alcanzable desde construir. |
| tools/build_match_content_patch.py | tools/_archivo/build_match_content_patch.py | archive | Produjo mch v23-v27; sustituido por v33/mch_story y v55/pachangas. Sus invariantes (solo 0x301D arg 1, conjunto visible == claves) pasan como reglas a ie1/texto/mch.py en fase 2. |
| tools/build_mch_patch.py | tools/_archivo/build_mch_patch.py | archive | Variante solo Royal (v21), contenida en la anterior. |
| tools/build_3ds.py | tools/_archivo/build_3ds.py | archive | Constructor in situ de la etapa 8 (parches v1-v9). |
| tools/build_3ds_var.py | tools/_archivo/build_3ds_var.py | archive | obsolete_dangerous: sin SKIP_CRO/NO_CODE_PATCH aplica parches fallidos. |
| tools/build_fontui.py | tools/_archivo/build_fontui.py | archive | obsolete_dangerous: diagnóstico v7 con efectos al importar. Pasa FONT12T por el editor 4bpp incompatible. |
| tools/ui_insert.py | tools/_archivo/ui_insert.py | archive | obsolete_dangerous: escribía unitbase +0 en ASCII sin NUL (issue #16). |
| tools/probe_ie1_spacing.py | tools/_archivo/probe_ie1_spacing.py | archive | Experimento v18 retirado. Sus fuentes chocan con el bloqueo v20. |
| tools/test_compact_typography.py | tools/_archivo/tests/test_compact_typography.py | archive | Prueba un módulo archivado. Ya se saltaba porque falta work/fa_extract. |
| tools/test_dialogue_lock.py | tools/tests/unidad/texto/test_dialogue_lock.py | move | No se debilita ni se actualizan hashes. Se ejecuta contra los originales de tools/ y además comprueba identidad con nucleo.validar.bloqueo. |
| tools/test_dialogue_typography.py | tools/tests/unidad/texto/test_ancho_completo.py | move | Los bytes esperados son el transporte aprobado v20. Añade la identidad nucleo.texto.ancho_completo.encode_fullwidth is dialogue_typography.encode_fullwidth. |
| tools/test_legacy_sprite.py | tools/tests/unidad/graficos/test_pac_sprite.py + tools/tests/unidad/compresion/test_lz10.py | split | El caso compress_optimal pasa a compresion. |
| tools/test_probe_layout.py | tools/tests/unidad/texto/test_tipografia_v20.py | move | Añade la identidad nucleo.texto.tipografia_v20.layout is build_ie1_probe.layout. |
| tools/test_ssd_records.py | tools/tests/unidad/eventos/test_ssd.py | move | Sintético, sin cambios de expectativa. |
| tools/test_ui_formats.py | tools/tests/unidad/graficos/test_formatos_ui.py | move | Cubre ctpk, qna, arcv y paint. Se mantiene verde. |
| tools/test_validate_inputs.py | tools/_archivo/tests/test_validate_inputs.py | archive | Prueba validate.py, que queda en cuarentena en _legado. |
| tools/ie1_media.py | ie123kit/nucleo/media/audio.py (inspect_sad genérico) + ie123kit/ie1/media/voces.py (inventario) | split | Enfoque v34/v35 (SAD de DS) superado: la fuente es el 3DS europeo. Se conservan las reglas: copiar SADL entero con sha256, no instalar J18/J19 y entrar por LayeredFS romfs/. |
| tools/mods_to_moflex.py | ie123kit/nucleo/media/moflex.py (set_moflex_rotation, rgb_to_yuv420, ycgco420_to_rgb, probe, encoder) + nucleo/media/subtitulos_dat.py (Subtitle, read_subtitles, add_caption, fit_caption) | split | Lo importan v54/pantalla_inicio y v58/cinematicas. DEFAULT_MOBIPEG y DEFAULT_FONT se conservan en la fachada _legado. Layout 0x16 obligatorio. DS_TABLE pasa a ser alias de nds_latin.DS_TABLE. |
| tools/build_ie1_movies.py | tools/_archivo/build_ie1_movies.py | archive | Sustituido por v58/cinematicas/build.py: las 21 películas de v66/v67 son idénticas a su extra/. El manifiesto de datos de ie1/media/cinematicas.toml se toma de v58, no de este script. |
| tools/validate_ie1_media.py | ie123kit/ie1/verificar.py (reglas de media) + nucleo/media/moflex.py (disposicion_rotacion) | merge | Las rutas del stage legado ya no son válidas. Se conservan las invariantes: audio instalado idéntico a la fuente y MOFLEX solo 0x16 decodificable. |
| tools/harvest_log.py | ie123kit/nucleo/construir/registro_azahar.py | move | Lo llama jugar.ps1, que conserva shim de CLI hasta la fase 2. KNOWN_PCS pasa a ser un dato por juego (ie1/datos/pcs_conocidos.toml). |
| tools/limpiar_work.py | ie123kit/nucleo/construir/limpieza.py (+ Workspace.limpiar y `ie123 work limpiar` en fase 2) | move | Sin rastrear en git: se commitea en la fase 1.0. Conserva shim de CLI, porque CLAUDE.md documenta `python tools/limpiar_work.py --borrar`. Aprende work/juego_principal y una lista blanca de ficheros congelados (V37, v33/eve_labels/common.py, v51/voces). Respeta el marcador .conservar de las candidatas golden. |
| tools/reorganizar_proyecto.py | tools/_archivo/reorganizar_proyecto.py | archive | Migración del 2026-09-16 ya aplicada. La nueva migración a juego_principal es una acción aparte que copia, no mueve. |
| tools/build_patch.ps1 | tools/build_patch.ps1 (fase 2: envoltorio de `ie123 parche`) | keep_script | Entrada documentada. La lógica xdelta pasa a nucleo/construir/parche.py solo tras reproducir su .xdelta byte a byte. |
| tools/extract_nds.ps1 | tools/extract_nds.ps1 (fase 2: envoltorio de `ie123 extraer nds`) | keep_script | Hoy requiere ndstool.exe, que no existe en tools/bin. El envoltorio usará nds_rom.py en Python puro. |
| tools/extract_romfs.ps1 | tools/extract_romfs.ps1 (fase 2: envoltorio de `ie123 extraer romfs`) | keep_script | 3dstool vía nucleo/construir/rom.py. Escribe work/shared/base_3ds, que nunca se borra. |
| tools/jugar.ps1 | tools/jugar.ps1 (fase 2: envoltorio de `ie123 instalar --lanzar` + registro_azahar) | keep_script | Hoy busca rutas obsoletas (work\build, roms\*ES*). Se corrige al convertirlo en envoltorio. |
| tools/setup_mobipeg.ps1 | tools/setup_mobipeg.ps1 | keep_script | Arranque de herramienta externa (mobipeg x86 v2.1; la x64 crashea). nucleo/config/herramientas.py solo localiza el resultado, y `ie123 doctor` lo comprueba. |
| tools/setup_vgmstream.ps1 | tools/setup_vgmstream.ps1 | keep_script | Igual que setup_mobipeg. |
| tools/bin/ | tools/bin/ (git-ignored; resuelto por nucleo/config/herramientas.py) | keep_script | 3dstool.exe y xdelta3.exe. No se empaquetan ni se suben. |

## Fases de migración

> **Nota del 2026-09-19 (#49): referencia de los gates.** Las candidatas `probe_ie1_v66` y `probe_ie1_v67`
> se borraron. Donde los gates de abajo citan v66, v67, `capas_v67.sha256` o el sha `72ef7133…fa91`, rige
> esta equivalencia (ver `nucleo/compat/golden.py` y [`ESTADO_MIGRACION.md`](ESTADO_MIGRACION.md)):
> base `work/shared/base_3ds/romfs`; capa `work/ie1/capas/graficos/titulo_logo`; regeneración de la capa en
> un temporal (`capa_referencia.sha256`); reconstrucción `golden comprobar --capa … --referencia` con
> archive `6f23e4d5…d7f1`; la CLI `construir` reaplica la capa sobre la candidata vigente
> (`probe_ie2_v34`, archive `5f52d315…7948`, mismo contenido entrada a entrada). Las capas viven por tema
> (`capas/<tema>/<linea>` y `historial/`), no por tanda `vNN/`. Plan de porteo de los motores de capa
> nuevos: [`PLAN_PORTEO_CAPAS.md`](PLAN_PORTEO_CAPAS.md).

### 1. F1.0: Línea base, protección de bytes y registro de trabajo (no se mueve código) (fase1_segmentacion)
- Abrir en GitHub la épica «Toolkit ie123kit» y un issue por subfase F1.0-F2.5, añadidos al Project board (Norma 1). Sin autenticación de gh, redactarlos en docs/ISSUES_PENDIENTES.md.
- Resolver el árbol sucio: commitear tools/limpiar_work.py (hoy sin rastrear) y decidir con el propietario los 40 ficheros de tools/ con cambios sin commitear, para que la línea base refleje código versionado.
- Con la confirmación explícita del propietario (afecta a ficheros bloqueados, aunque no cambia bytes): crear .gitattributes con `-text` para dialogue_typography.py, font_patch.py, dialogue_lock.py, build_ie1_probe.py y build_ui_revision.py. Commitear sus bytes actuales exactos y comprobar que el sha256 de font_patch.py sigue siendo 04cf7ff5… y el de dialogue_typography.py 8e983419….
- Crear tools/tests/compat/ con scripts stdlib: importaciones.py (comprobador AST de work/), superficie.py (dir y firmas de los 71 módulos; por AST los que tienen efectos al importar) y golden.py (capturar y comprobar).
- Capturar baseline_importaciones.json con los fallos previos, incluido v33/gamestring (parents[2]), y abrir un issue por ese fallo. Capturar también superficie_v0.json y golden/: sha de los 5 ficheros congelados, capas_v67.sha256 (extra/ de v67/titulo_logo) y candidatas.sha256 (archive.fa y CRO de probe_ie1_v66 y v67). Solo hashes.
- Proteger las candidatas golden: marcador .conservar en probe_ie1_v66 y v67, que limpiar_work respeta (cambio mínimo y aditivo en limpiar_work.py), y no ejecutar `--borrar` sobre ellas hasta cerrar la fase 2.

**Gate:** Se ejecuta en local desde la raíz y todas las órdenes deben devolver 0:
(1) `python -m unittest discover -s tools -p "test_*.py"` devuelve «Ran 27 tests … OK (skipped=1)».
(2) `python tools/tests/compat/importaciones.py --work work --baseline tools/tests/compat/baseline_importaciones.json` termina con 0 no resueltos nuevos.
(3) `python tools/tests/compat/golden.py comprobar --capa work/ie1/capas/v67/titulo_logo` regenera extra/ byte a byte.
(4) `python -m ie123kit.nucleo.compat.congelados build_ui_revision --base work/shared/candidatas/probe_ie1_v66/archive.fa --ui work/ie1/capas/v67/titulo_logo --output %TEMP%/ie123_regen/probe_ie1_v67/archive.fa` produce archive sha256 72ef7133924e981e4736e240368f716140ca35f62a5c131d7f01c1ead9cffa91 y la CRO coincide con probe_ie1_v67.
(5) Tras `git worktree add %TEMP%/ie123_clon HEAD`, el sha256 de tools/font_patch.py y tools/dialogue_typography.py en el clon coincide con SOURCE_HASHES, lo que prueba que el bloqueo se reproduce desde git.

### 2. F1.1: Esqueleto del paquete y reglas de arquitectura (fase1_segmentacion)
- Crear tools/pyproject.toml y tools/src/ie123kit/ con nucleo/, juego_principal/, ie1/, ie2/{comun,tormenta_de_fuego,ventisca_eterna}/, ie3/{comun,rayo_celeste,fuego_explosivo,amenaza_del_ogro}/ y _legado/, solo con __init__.py sin efectos.
- Implementar nucleo/config/raiz.py (find_root por IE123_ROOT o AGENTS.md + tools/pyproject.toml) y nucleo/errores.py.
- Mover los comprobadores de F1.0 a ie123kit/nucleo/compat/, dejando en tools/tests/compat envoltorios que los llaman, y añadir el generador shims.py sin aplicarlo aún.
- Añadir tools/tests/arquitectura/test_importaciones.py (reglas nucleo↛juegos, juego↛juego, ie2.*→solo ie2.comun, sin parents[N], sin rutas de máquina) y la exclusión de ruff para los ficheros bloqueados.

**Gate:** (1) `pip install -e tools[dev]` y después `python -m pytest tools/tests -m "not requiere_rom" -q` en verde, con los tests de tools/ intactos.
(2) `python -m unittest discover -s tools -p "test_*.py"` sigue devolviendo 27 OK (1 skip).
(3) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline tools/tests/compat/baseline_importaciones.json` devuelve 0.
(4) `python -m ie123kit.nucleo.compat.golden comprobar --capa work/ie1/capas/v67/titulo_logo --candidata probe_ie1_v67` devuelve 0, lo que exige extra/ idéntico y archive sha 72ef7133…fa91.
(5) El sha de los 5 ficheros congelados es igual a golden/.

### 3. F1.2: Archivar los 27 scripts retirados (fase1_segmentacion)
- Con el comprobador AST, confirmar cero importadores en tools/ y work/ para cada uno: pkb_scan, reinsert_test, recompress_test, build_translation, str_align, nds_str_dump, tr_prepare, tr_merge, align_events, audit_ie1_voiced_text, patch_code, patch_cro, verify_build, verify_v21, fix_ie1_title_logo, compact_typography, build_match_content_patch, build_mch_patch, build_3ds, build_3ds_var, build_fontui, ui_insert, probe_ie1_spacing, build_ie1_movies, reorganizar_proyecto, test_compact_typography y test_validate_inputs.
- Moverlos con `git mv` a tools/_archivo/ (tests en tools/_archivo/tests/), sin __init__.py, y escribir tools/_archivo/README.md con el motivo de cada uno y enlaces a FURIGANA_LECCIONES y a los issues #9, #16 y #36.
- Actualizar las referencias en docs/DESARROLLO.md, docs/FORMATOS.md, tools/README.md y docs/SKILL_VOLCADO_ROM_NDS.md hacia el README de _archivo o hacia la herramienta que los sustituye. No se crean stubs en tools/.
- Si un script archivado aparece importado en el smoke real (no solo en AST), revertir su traslado y pasarlo a la lista de _legado de F1.4.

**Gate:** (1) `python -m unittest discover -s tools -p "test_*.py"` en verde con el recuento nuevo anotado en el issue (27 menos los tests de los 2 ficheros archivados) y `python -m pytest tools/tests -m "not requiere_rom"` en verde.
(2) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` devuelve 0.
(3) `python -m ie123kit.nucleo.compat.golden comprobar --capa work/ie1/capas/v67/titulo_logo --candidata probe_ie1_v67` devuelve 0 (extra/ idéntico y archive sha 72ef7133…fa91).
(4) `git ls-files tools/_archivo` lista los 27 y `python -c "import sys; sys.path.insert(0,'tools'); import pkb_scan"` falla con ModuleNotFoundError.

### 4. F1.3: Traslado 1:1 de los módulos de motor a nucleo con shims de alias (fase1_segmentacion)
- Un commit por módulo, en este orden: lz10, blz, sszl (absorbe unwrap), ui_archive→contenedores/arcv, nds_unpack→nds_rom, qna_regions→qna, legacy_sprite→pac_sprite, nftr_metrics→nftr, bcfnt, ctpk_ui→ctpk, ssd_records→eventos/ssd, fa_unpack (y fa_repack fusionado)→contenedores/fa, patch_smdh_title→ejecutable/smdh, harvest_log→construir/registro_azahar y limpiar_work→construir/limpieza.
- Cada traslado es literal. Solo se cambian las líneas de importación y `sys.path.insert(0,'tools')` pasa a importaciones del paquete. Se sustituye parents[1] por find_root en fa_repack, mods_to_moflex y limpiar_work.
- Generar el shim de cada módulo con `python -m ie123kit.nucleo.compat.shims generar <nombre>`. Para ui_archive y fa_repack se genera una fachada en _legado/ que re-exporta la unión de nombres.
- Tras cada commit, ejecutar el gate completo. Si falla, revertir ese módulo antes de pasar al siguiente.

**Gate:** Por cada módulo y al final de la subfase:
(1) `python -m pytest tools/tests -m "not requiere_rom"` más `python -m unittest discover -s tools -p "test_*.py"` en verde.
(2) `python -m ie123kit.nucleo.compat.superficie comparar tools/tests/compat/superficie_v0.json` sin diferencias en los módulos trasladados.
(3) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` devuelve 0.
(4) `python -m ie123kit.nucleo.compat.golden comprobar --capa work/ie1/capas/v67/titulo_logo --candidata probe_ie1_v67` devuelve 0. La capa v67 importa fa_unpack, ui_archive, ctpk_ui y sszl, así que ejercita los shims, y se exige archive sha 72ef7133…fa91.
(5) `python -m ie123kit.nucleo.validar.bloqueo --candidata work/shared/candidatas/probe_ie1_v67/archive.fa` devuelve 0 (fuentes extraídas a temporal, SOURCE_HASHES y LAYOUT_HASH intactos).

### 5. F1.4: Divisiones, fachadas de legado y reparto por juego (fase1_segmentacion)
- Crear las fachadas _legado para los módulos divididos que siguen importados (pkb_unpack, build_glossary, ds_official, reinsert, translate_ui_textures, mods_to_moflex y audit_dialogo_ids) con sus globales, nombres privados y main(). Mover su lógica a nucleo/eventos/packnum, texto/nds_latin (DS_TABLE y NDS_DEC separadas), texto/sjis_portador, graficos/pintado, media/moflex, media/subtitulos_dat y eventos/alineado_ids.
- Poner en cuarentena en _legado, con shim, ds_roster, reinsert_var, ssd_reinsert y validate. Sus CLI se niegan a ejecutarse sin --legado-lo-se, y quedan excluidos del futuro registro de activos.
- Dividir verify_candidate (nucleo/validar/candidata + ie1/verificar), ie1_tables (registros/tabla_fija + ie1/texto/tablas), ie1_media (media/audio + ie1/media/voces), validate_ie1_media (ie1/verificar) y patch_exefs (contenedores/exefs + archivo de la ruta code.bin). Trasladar ie1_keyboard a ie1/graficos/teclado.
- Crear nucleo/texto/ancho_completo.py, tipografia_v20.py y fuentes/glifos.py como re-exports perezosos de los ficheros bloqueados, y nucleo/validar/bloqueo.py sobre dialogue_lock.validate. Crear nucleo/construir/candidata.py a partir de build_ui_revision, dejando el fichero congelado en tools/.
- Escribir juego_principal/activos.toml, ie1/activos.toml y los activos.toml de ie2 e ie3 (solo prefijos: inazuma2/, inazuma3/, inazuma3_ogre/, CRO ina_main2/ina_main3ogre, capacidades vacías). Son solo rutas y datos cortos.

**Gate:** (1) `python -m pytest tools/tests -m "not requiere_rom"` en verde, incluidos los tests de identidad (tipografia_v20.layout is build_ie1_probe.layout, ancho_completo.encode_fullwidth is dialogue_typography.encode_fullwidth) y el test de diferencias NDS_DEC/DS_TABLE.
(2) `python -m ie123kit.nucleo.compat.superficie comparar …` sin diferencias en los 71 nombres que siguen con shim o fachada.
(3) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` devuelve 0.
(4) `python -m ie123kit.nucleo.compat.golden comprobar --capa work/ie1/capas/v67/titulo_logo --candidata probe_ie1_v67` devuelve 0 (archive sha 72ef7133…fa91).
(5) `python tools/verify_candidate.py --base work/shared/candidatas/probe_ie1_v66 --candidate work/shared/candidatas/probe_ie1_v67 --layer work/ie1/capas/v67/titulo_logo` produce un informe igual al capturado en F1.0, sin campos de tiempo.
(6) Test de arquitectura en verde: ie1 no importa ie2 ni ie3, y nucleo no importa juegos.

### 6. F1.5: Tests trasladados, documentación y cierre de la fase 1 (fase1_segmentacion)
- Mover los 6 tests activos a tools/tests/unidad (test_legacy_sprite se divide en pac_sprite y lz10). Las expectativas no cambian.
- Regenerar todos los shims desde el generador y comprobar por AST que no contienen lógica. Confirmar que tools/ solo tiene los 5 congelados, 29 shims, 6 .ps1, bin/, _archivo/, src/, tests/, pyproject.toml y README.md.
- Actualizar tools/README.md (mapa antiguo→nuevo), docs/ARQUITECTURA.md (tools/src, _archivo, reglas de importación) y las referencias de CLAUDE.md/AGENTS.md a rutas de herramientas, sin tocar el texto del bloqueo tipográfico.
- Añadir .github/workflows/toolkit.yml (tests sin ROM, sha de bloqueados, guardia git ls-files) y cerrar los issues de la fase 1.

**Gate:** GATE DE FASE 1, todo desde la raíz:
(1) `python -m pytest tools/tests -m "not requiere_rom" -q` en verde en local y en toolkit.yml (windows-latest y ubuntu-latest).
(2) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline tools/tests/compat/baseline_importaciones.json` devuelve 0, es decir, cada import de los 186 scripts de work/ resuelve igual que en la línea base.
(3) `python -m pytest tools/tests/requiere_rom -q` regenera work/ie1/capas/v67/titulo_logo con extra/ byte a byte igual a capas_v67.sha256.
(4) La reconstrucción con build_ui_revision (shim y paquete) desde probe_ie1_v66 reproduce archive sha256 72ef7133924e981e4736e240368f716140ca35f62a5c131d7f01c1ead9cffa91 y la CRO de probe_ie1_v67.
(5) Clon limpio con `git worktree add`: sha de los 4 bloqueados igual a SOURCE_HASHES y test_dialogue_lock en verde dentro del clon.

### 7. F2.1: Contrato, tipos, proyecto y servicio sin cabeza (fase2_preparacion_gui)
- Implementar nucleo/tipos.py (AssetRef, Resultado, Incidencia, Progreso, CancelToken con to_json) y nucleo/juego.py (JuegoBase con delegación por tipo de activo en nucleo).
- Implementar servicio/proyecto.py (Workspace, ie123.toml, ie123.local.toml, Workspace.dirs, manifiestos de candidata), servicio/registro_activos.py (activos.toml + escaneo perezoso + work/<objetivo>/registro.json), servicio/trabajos.py (hilos, eventos JSONL, cancelación), servicio/api.py y servicio/esquemas/*.schema.json.
- Crear un JuegoFalso sobre un archive.fa sintético en tools/tests/contrato para validar el servicio sin ROM.
- Añadir ie123.toml (en git) y ie123.local.toml a .gitignore.

**Gate:** (1) `python -m pytest tools/tests -m "not requiere_rom" -q` en verde, incluida la suite de contrato: json.dumps de todo Resultado conforme a su esquema, progreso monótono, cancelación y `importar(simular=True)` sin escrituras (hash del árbol antes y después).
(2) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` devuelve 0.
(3) `python -m ie123kit.nucleo.compat.golden comprobar --capa work/ie1/capas/v67/titulo_logo --candidata probe_ie1_v67` devuelve 0 (archive sha 72ef7133…fa91).
(4) Test de arquitectura: servicio no es importado por nucleo ni por los juegos.

### 8. F2.2: Primitivas consolidadas desde los patrones de capas (fase2_preparacion_gui)
- Añadir, sin alterar el contrato congelado: FaArchive.read/index/glob/exists; texturas.iter_ctpk/find_texture/apply_plan/validate_plan con rewrap explícito ('raw' por defecto, como V37); ayudas de imagen; qna.QnaLayout; cro.Cro/CroPatcher (solo literales y reubicaciones declaradas); registros.RecordTable y rangos; eventos.instrucciones.EventPack; y packnum.rebuild parametrizado para eve y mch (sustituye el hack exec solo para capas NUEVAS).
- Generalizar construir/candidata.py a todas las CRO (ina_menu, ina_main1, ina_main2, ina_main3ogre) y a aportaciones por objetivo. Añadir construir/instalar.py (Azahar: se niega si azahar.exe corre, rehash por fichero, installation.json), rom.py (3dstool con RomFS temporal), parche.py (xdelta3) y capas.py (Capa(__file__), capa.toml).
- Test de equivalencia: ejecutar el PLAN de la capa v67 con texturas.apply_plan hacia un directorio temporal y compararlo con su extra/.

**Gate:** (1) `python -m pytest tools/tests -m "not requiere_rom" -q` en verde, con round-trips de las primitivas nuevas sobre datos sintéticos.
(2) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` devuelve 0.
(3) `python -m pytest tools/tests/requiere_rom -q`: la regeneración de v67 da extra/ idéntico, el apply_plan equivalente produce los mismos bytes, y `python -m ie123kit.cli construir --base probe_ie1_v66 --capas work/ie1/capas/v67/titulo_logo --salida %TEMP%/ie123_regen2/probe_ie1_v67` da archive sha256 72ef7133…fa91 y la CRO idéntica.
(4) Con la misma ROM base y ROM parcheada, `ie123 parche` genera un .xdelta byte a byte igual al de tools/build_patch.ps1 (misma versión y flags de xdelta3).

### 9. F2.3: Paquetes de juego completos, juego_principal y work/juego_principal (fase2_preparacion_gui)
- ie1/acciones.py: gráficos (PNG + .qna.json), textos (TSV/PO por evento, mch, tablas y literales de ina_main1.cro, con layout v20, bloqueo y reglas %NF, \f, 0x301D arg 1, +16/NUL de unitbase y rangos protegidos), cinemáticas (MOFLEX↔MP4+SRT, layout 0x16, mobipeg x86), voces (SAD→WAV; importar .SAD validado; WAV→SADL NOT_SUPPORTED) y aportaciones desde capas.
- juego_principal/acciones.py sobre menu/title.arc, common.arc, content.arc, result.arc, sd.arc, extra.arc y data_replace/**, movie/OP.moflex y logo_l5.moflex, cro/ina_menu.cro (literales), message/jp/GameString, SMDH/banner/icon (ExeFS experimental) y font/*.bcfnt como solo lectura bloqueada.
- ie2.* e ie3.*: InfoObjetivo con prefijos y capacidades vacías (NOT_SUPPORTED) hasta que exista su extracción. ie2/comun e ie3/comun con las reglas compartidas.
- `ie123 proyecto init` crea work/juego_principal/{capas,qa,exportaciones} y translation/juego_principal/. `ie123 proyecto migrar-juego-principal --simular` escribe historico.json con las capas de work/ie1/capas que tocan el menú, sin moverlas. limpieza.py y docs/ARQUITECTURA.md incorporan juego_principal (quinto ámbito junto a shared, ie1, ie2 e ie3).

**Gate:** (1) `python -m pytest tools/tests -m "not requiere_rom" -q` en verde: contrato parametrizado sobre los 8 objetivos y esquemas de activos.toml válidos.
(2) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` devuelve 0.
(3) `python -m pytest tools/tests/requiere_rom -q`: `ie123 juego_principal activos --json` incluye menu/title.arc, menu/common.arc, menu/data_replace, movie/OP.moflex, movie/logo_l5.moflex, cro/ina_menu.cro y SMDH; exportar e importar sin cambios cada textura de menu/title.arc e inazuma1/data_iz/a_title/title_t.arc deja las entradas byte a byte idénticas; exportar e importar textos sin cambios en ie1 produce 0 eventos preparados; la regeneración de v67 es idéntica.
(4) `ie123 construir --base probe_ie1_v66 --capas work/ie1/capas/v67/titulo_logo --salida %TEMP%/…` reproduce archive sha 72ef7133…fa91.
(5) Existe work/juego_principal/ y `ie123 work limpiar` (sin --borrar) no lista nada de base_3ds, fuentes, ficheros congelados ni candidatas con .conservar.

### 10. F2.4: CLI `ie123`, scripts finos y retirada de shims de CLI (fase2_preparacion_gui)
- Implementar cli/main.py como adaptador 1:1 del servicio (--json, códigos de salida 0-5), `ie123 doctor` y `ie123 compat comprobar [--golden]`, que ejecuta los cuatro gates.
- Convertir build_patch.ps1, extract_romfs.ps1, extract_nds.ps1 y jugar.ps1 en envoltorios de una orden, corrigiendo las rutas obsoletas de jugar.ps1.
- Actualizar la documentación (CLAUDE.md: `ie123 work limpiar --borrar`; SKILL_VOLCADO_ROM_NDS.md, tools/README.md y GUIA_NOVATO.md). Después retirar los shims que solo servían para CLI (verify_candidate, nds_unpack, blz, harvest_log y limpiar_work), siempre que el comprobador AST confirme que ninguna capa los importa y el propietario lo apruebe.
- Construir una candidata completa con `ie123 construir` e instalarla con `ie123 instalar` para la QA en emulador.

**Gate:** (1) `python -m pytest tools/tests -m "not requiere_rom" -q` en verde, incluida la validación de toda salida `--json` contra los esquemas.
(2) `ie123 compat comprobar --golden` devuelve 0. Internamente ejecuta el comprobador de importaciones (0 nuevos no resueltos), la regeneración de v67 (idéntica), la reconstrucción de probe_ie1_v67 (sha 72ef7133…fa91) y bloqueo.validar.
(3) `ie123 doctor` devuelve 0 en la máquina del propietario.
(4) QA manual según docs/PROTOCOLO_QA_IE1.md con la candidata instalada por `ie123 instalar`, hasta la primera pachanga hablando con varios NPC y sin fallos gráficos en cajas de diálogo. Resultado anotado en el issue; runtime_verified solo lo pone la persona.

### 11. F2.5: Preparación final para la GUI (fase2_preparacion_gui)
- Congelar API_VERSION 1.0 y publicar servicio/esquemas/*.schema.json con ejemplos. Documentar en docs/toolkit/API_SERVICIO.md el ciclo abrir → listar → exportar → editar → importar(simular) → importar → construir → verificar → instalar.
- Implementar las capas GUI (work/<objetivo>/capas/vNN/gui_<fecha>/capa.toml) y su aplicación dentro de `construir`.
- Añadir un cliente sin cabeza de referencia (tools/tests/contrato/test_flujo_gui.py) que recorre el ciclo completo sobre un proyecto sintético y, marcado requiere_rom, sobre la base real.
- Cerrar la épica y los issues, actualizar docs/PROGRESO.md y abrir el issue de la GUI con la tecnología elegida por el propietario.

**Gate:** (1) `python -m pytest tools/tests -m "not requiere_rom" -q` en verde en toolkit.yml, incluido test_flujo_gui sintético: solo cambia la entrada editada, el bloqueo pasa y todos los eventos serializan según esquema.
(2) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` devuelve 0.
(3) `python -m pytest tools/tests/requiere_rom -q`: el flujo GUI real sobre inazuma1/data_iz/a_title/title_t.arc genera una capa gui_* y una candidata cuya única entrada distinta de la base es esa. La regeneración de v67 es idéntica, y la reconstrucción de probe_ie1_v67 sigue dando sha 72ef7133…fa91.

### 12. F2.7: Retirada de los shims restantes (#102)
- Migrar cada `import X` / `from X import` / `python tools/X.py` / `sys.path` hacia `tools/` de los 22 shims al módulo real de `ie123kit`, en work/ (en su sitio), tools/tests, el paquete, la CI y la documentación.
- Borrar los 22 shims. `nucleo.compat.shims.MAPA` queda vacío; `DESTINOS` guarda la equivalencia y `RETIRADOS` los 31 retirados desde la F2.4; `shims comprobar` falla si uno reaparece.
- `nucleo.config.congelados.preparar()` + `nucleo.compat.congelados` sustituyen a los shims para los 5 congelados.

**Gate:** (1) `python -m pytest tools/tests -m "not requiere_rom"` en verde. (2) `python -m ie123kit.nucleo.compat.importaciones --work work --baseline …` sin nuevos fallos por los nombres retirados. (3) grep de los 22 nombres en todo el repo y en work/: 0 usos activos. (4) Guardias `bloqueados` y `git` en verde.

## Preguntas para el propietario
- Nombre del paquete y de la orden. Propuesta por defecto: paquete `ie123kit` (coincide con el catálogo de auditoría) y orden `ie123`. Alternativa: `inazuma` para ambos, más fácil de recordar pero genérico.
- Ubicación del código. Por defecto, `tools/src/ie123kit` con `tools/pyproject.toml`, que respeta la Norma 3 («herramientas en tools/»). ¿Prefieres `src/` y `pyproject.toml` en la raíz? Exigiría modificar la Norma 3 de CLAUDE.md.
- Fijar en git los bytes exactos de los ficheros bloqueados con `-text` en .gitattributes. Hoy `tools/font_patch.py` solo coincide con su hash aprobado en tu árbol de trabajo (EOL mixto), y un clon limpio rompería dialogue_lock.validate(). Por defecto: sí, sin cambiar ni un byte ni un hash. Toca ficheros del bloqueo tipográfico, así que necesito tu autorización explícita.
- Alcance del bloqueo v20 fuera de IE1. Las fuentes font/*.bcfnt están en la raíz de archive.fa y las comparten el menú, IE2 e IE3. Por defecto: el bloqueo y el perfil `tipografia_v20` se aplican a toda la recopilación, y cualquier perfil distinto para IE2/IE3 requerirá una petición tipográfica tuya expresa.
- Cambios sin commitear. Hay 40 ficheros de tools/ modificados y `tools/limpiar_work.py` sin rastrear. Por defecto se commitean tal cual antes de la línea base F1.0. ¿Hay alguno que deba descartarse?
- Qué se archiva. Por defecto, los 27 de tools/_archivo más 4 en cuarentena importable (ds_roster, reinsert_var, ssd_reinsert, validate) y fachadas de legado para ds_official y reinsert. ¿Prefieres borrar del árbol los obsolete_dangerous (quedarían en el historial de git) en lugar de archivarlos?
- Idioma de la CLI. Por defecto, verbos y mensajes en español (`exportar`, `importar`, `construir`) con alias en inglés (`export`, `import`, `build`) para contribuidores de fuera. ¿Solo español?
- Formato de edición de textos. Por defecto, TSV UTF-8 (id, jp, es_oficial, traduccion, max_px, max_bytes, estado), editable en hojas de cálculo, con exportación PO opcional para Poedit/Weblate. ¿Otro formato?
- Nombre de las candidatas. Hoy son `probe_ie1_vNN`, pero contienen toda la recopilación. Por defecto se mantiene el nombre durante la fase 1 y en la fase 2 se admite el alias `candidata_vNN` sin renombrar las existentes. ¿Renombrar?
- Correspondencia de versiones en la RomFS. inazuma2/ agrupa Tormenta de Fuego y Ventisca Eterna, e inazuma3/ con inazuma3_ogre/ agrupa Rayo Celeste, Fuego Explosivo y La amenaza del Ogro. Por defecto, los activos comunes van en ie2.comun/ie3.comun y lo específico de cada versión se declara cuando se decodifique el discriminador. ¿Tienes ya ese mapeo?
- Licencia del toolkit (el repo no tiene LICENSE). Por defecto, MIT para el código de tools/, con LEGAL.md aclarando que no cubre datos del juego ni los binarios externos de tools/bin (3dstool, xdelta3, mobipeg, vgmstream). Alternativa: GPL-3.0 para obligar a compartir derivados.
- Tecnología de la GUI futura. Por defecto, PySide6 (LGPL) como aplicación de escritorio en el mismo proceso, llamando a ServicioToolkit desde un QThread, sin servidor. Alternativa: interfaz web local (FastAPI + navegador) sobre la misma API JSON.
- Codificación de voces. No existe codificador WAV→SADL en el proyecto, y hoy se copian SAD europeos íntegros. Por defecto `voces importar` acepta solo .SAD validado y WAV devuelve NOT_SUPPORTED. ¿Quieres un issue para investigar un codificador?
- Retirada de shims de importación. Por defecto se mantienen mientras exista cualquier capa antigua que los importe, porque no se reescriben capas; los 5 ficheros congelados y el shim de bcfnt son permanentes. ¿Aceptas retirar capas antiguas (por ejemplo, anteriores a v58) para poder eliminar shims?
- Golden de migración. Solo existen probe_ie1_v66 y v67, así que el gate de regeneración solo cubre la capa v67/titulo_logo. Por defecto se marcan con `.conservar` y no se ejecuta `limpiar_work --borrar` sobre ellas hasta cerrar la fase 2. ¿Aceptas ese espacio en disco o prefieres conservar otra pareja?

## Riesgos
- Rotura del bloqueo v20 por EOL. tools/font_patch.py tiene hoy EOL mixto y su hash aprobado no se reproduce desde git: un clon limpio, la CI o una reescritura de autocrlf hacen fallar validate() en 26 capas. Mitigación: `-text` en .gitattributes con los bytes actuales (con autorización), comprobación en un clon con worktree en F1.0 y test de sha en CI.
- Modificación accidental de ficheros bloqueados por formateadores, limpiezas de importaciones o reubicación. Mitigación: ficheros físicamente congelados en tools/, exclusión de ruff/black, test de sha y re-export por identidad sin copiar código.
- Identidad de módulo en shims. Si un shim copia nombres en lugar de hacer alias, las mutaciones de globales (MAX_CAND, REPO, V37.BASE/PLAN) no llegan al código real y cambian bytes en silencio. Mitigación: alias en sys.modules, fachadas _legado que conservan globales y test de superficie y de identidad.
- exec() de texto en v55/pachangas. Si build_ui_revision.py deja de contener los literales eve.pkh/.pkb, str.replace no hace nada y se reconstruye el pack equivocado. Mitigación: el fichero se congela y un test comprueba esos literales.
- Redirección silenciosa de la raíz. Código trasladado que conserve parents[N] resolvería ROOT=tools/src. Mitigación: find_root, test AST que prohíbe parents[ en src/ y shims que siguen en tools/.
- Cambios de bytes al unificar políticas: SSZL raw/keep/literal, es_encode truncante frente a encode_fullwidth, DS_TABLE frente a NDS_DEC, o la fuente arialbd por defecto. Mitigación: funciones con nombre propio, sin cambiar valores por defecto en la ruta de shims, test de diferencias de tablas y gate golden por módulo.
- Golden insuficiente: solo existen probe_ie1_v66 y v67, así que la regeneración byte a byte cubre la capa v67 (fa_unpack, ui_archive, ctpk_ui, sszl) pero no las rutas de eventos ni de CRO. Mitigación: equivalencia por funciones sobre datos sintéticos para packnum y ssd, informe de verify_candidate comparado con la línea base y QA en emulador obligatoria en F2.4.
- Scripts de capa imposibles de probar en CI (git-ignored, dependen de ROM y de rutas de máquina como Downloads). Mitigación: comprobador AST ejecutable sin ROM, línea base de fallos previos y gates con ROM obligatorios en local antes de cada merge.
- Colisiones de nombres en sys.path (validate, apply, common, prepare, check, lib). Retirar tools/validate.py podría cambiar la resolución de alguna capa. Mitigación: se conserva en fase 1 y solo se retira con evidencia AST más smoke real.
- Reutilización de código peligroso. ds_official (#36), reinsert_var y ssd_reinsert siguen importables por compatibilidad. Mitigación: ubicación _legado, CLI que se niega sin flag explícito, exclusión del servicio y del registro, y tools/_archivo no importable para el resto.
- Filtración de contenido protegido (Norma 2) a través de exportaciones, registro.json, manifiestos golden o fixtures. Mitigación: exportaciones y cachés solo bajo work/ (ignorado), golden solo con hashes, fixtures sintéticos y guardia git ls-files en el servicio y en CI.
- Sobreestimar capacidades. juego_principal (ina_menu.cro, title.arc), IE2 e IE3 no están auditados como IE1, y no hay codificador WAV→SADL. Mitigación: capacidades declaradas por objetivo, NOT_SUPPORTED explícito y ExeFS marcado como experimental.
- Conflictos de la candidata compartida. Varios objetivos pueden aportar la misma entrada de archive.fa (por ejemplo font/ o common.arc). Mitigación: el orden de aportaciones es declarado, un conflicto es error y overridden_by_later_overlay aparece en build.json.
- La validación offline se confunde con estabilidad. Mitigación: runtime_verified siempre False en informes automáticos y QA en emulador según PROTOCOLO_QA_IE1 antes de declarar estable cualquier cambio de construcción o instalación.
- Desvío de foco. La infraestructura para la GUI puede retrasar la traducción. Mitigación: la fase 1 no añade funciones nuevas, cada subfase es un issue pequeño con gate ejecutable y la fase 2 solo empieza con el gate de fase 1 en verde.