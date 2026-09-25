# API de servicio de ie123kit 1.0 (contrato para la GUI)

Estado: congelada en la F2.5 (#51). La CLI `ie123` y la futura GUI solo hablan con
`ie123kit.servicio.api.ServicioToolkit`; la GUI nunca toca ficheros de `work/` por su cuenta.

## Versión y compatibilidad

- `ie123kit.API_VERSION == "1.0"` (también `ServicioToolkit.API_VERSION` y el campo `api_version` de
  cada `Resultado`).
- Versionado semántico. Una versión **menor** solo añade métodos, parámetros opcionales o campos de
  `datos`. Quitar o cambiar algo sube la versión **mayor**.
- Al abrir un proyecto, la GUI llama a `ie123kit.servicio.contrato.compatible(version_de_la_gui)`.
  Devuelve `True` si la versión mayor coincide y la menor del servicio es igual o superior.

## Tipos

Todo método devuelve un `Resultado` (`ie123kit.nucleo.tipos`), una dataclass congelada con
`to_json()`:

| Campo | Tipo | Notas |
|---|---|---|
| `ok` | bool | `False` si hay alguna incidencia de severidad `error` |
| `datos` | objeto | forma fija por método (tabla de abajo) |
| `incidencias` | lista de `Incidencia` | `codigo`, `severidad` (`error`/`aviso`/`info`), `mensaje`, y `activo_id`, `ruta`, `ubicacion` y `pista` opcionales |
| `artefactos` | lista de rutas | ficheros escritos |
| `duracion_s` | número | |
| `api_version` | cadena | `"1.0"` |

Los esquemas JSON (draft 2020-12, con ejemplos en `examples`) se publican en
`tools/src/ie123kit/servicio/esquemas/`. Se cargan con `esquemas.cargar(nombre)` y se validan con
`esquemas.validar(instancia, nombre)`. Si `jsonschema` no está instalado, se usa un validador propio.

- Contrato común: `resultado`, `incidencia`, `progreso`, `assetref`, `info_objetivo`,
  `manifiesto_candidata`, `registro_activos` y `evento_trabajo`.
- `datos` de cada método: `datos_objetivos`, `datos_activos`, `datos_exportar`, `datos_importar`,
  `datos_construir`, `datos_verificar` y `datos_instalar`. Admiten campos adicionales; los
  obligatorios no desaparecen dentro de la 1.x.

`ie123kit.servicio.contrato` reúne todo esto en código:

- `METODOS`: cada método, con el esquema de su `datos`, si escribe en disco y si se puede simular;
- los `TypedDict` `DatosObjetivos`, `DatosActivos`, `DatosExportar`, `DatosImportar`,
  `DatosConstruir`, `DatosVerificar` y `DatosInstalar`;
- `validar_resultado(metodo, resultado)`: valida el `Resultado` y, si es correcto, su `datos`.

## El ciclo de la GUI

```python
from ie123kit.servicio import contrato
from ie123kit.servicio.api import ServicioToolkit, SolicitudConstruccion

s = ServicioToolkit.abrir()                              # abrir (raíz por find_root o explícita)
assert contrato.compatible("1.0", s.API_VERSION)
s.objetivos()                                            # datos_objetivos
refs = s.activos("ie1", tipo="grafico").datos["activos"] # datos_activos
s.exportar("ie1", [refs[0]["id"]], "salida/")            # datos_exportar; PNG + .qna.json en artefactos
# ... editar el PNG fuera del servicio ...
s.importar("ie1", refs[0]["id"], "salida/", simular=True)   # no escribe NADA
r = s.importar("ie1", refs[0]["id"], "salida/", simular=False)
capa = r.datos["capa"]                                   # work/ie1/capas/graficos/gui_<aaaammdd_hhmm>/
s.construir(SolicitudConstruccion(base="probe_ie2_v34", objetivos=(), capas=(capa,),
                                  salida="probe_ie2_v35"))  # el bloqueo tipográfico se comprueba siempre
s.verificar("probe_ie2_v35")                             # bloqueo + hash contra archive.build.json
s.instalar("probe_ie2_v35")                              # Azahar ([azahar] mods_dir o IE123_AZAHAR)
```

| Paso | Método | Escribe | Notas |
|---|---|---|---|
| abrir | `ServicioToolkit.abrir(raiz=None)` | no | Workspace: `ie123.toml`, `ie123.local.toml` y las variables `IE123_*` |
| listar | `objetivos()`, `activos(objetivo, tipo, filtro)` | no | el inventario funde el escaneo de `archive.fa` y lo que aporta cada juego |
| exportar | `exportar(objetivo, ids, destino, formato=None)` | sí, en `destino` | |
| importar (simular) | `importar(..., simular=True)` | **no** | valida; `datos.diff` dice qué cambiaría |
| importar | `importar(..., simular=False)` | una capa nueva | `gui_<fecha>` con `capa.toml`; si la importación falla, la capa se borra |
| construir | `construir(SolicitudConstruccion)` | una candidata nueva | nunca sobrescribe; cada capa aporta su `extra/`, eventos y CRO («la última gana») |
| verificar | `verificar(candidata, golden=None)` | no | |
| instalar | `instalar(candidata, emulador="azahar")` | los mods del emulador | `runtime_verified` siempre es `False`: la QA la hace el usuario |

### Capas GUI

Una importación confirmada crea siempre una capa **nueva** y nunca edita una candidata. La carpeta es
`work/<objetivo>/capas/<tema>/gui_<aaaammdd_hhmm>[_N]/`, con `capa.toml` (`objetivo`, `tema`,
`version` de la próxima candidata y `linea`) y los ficheros en `extra/<ruta del archive>` (o
`romfs/cro/*.cro`). `construir` la aplica como cualquier otra capa, se pase su ruta en `capas` o la
aporte el objetivo con `objetivos=(...)`. Si varias capas de un objetivo tocan entradas distintas, se
funden como entradas sueltas en orden.

### Trabajos en segundo plano y eventos

`enviar_trabajo(nombre_metodo, **kw)` ejecuta un método en un hilo. `trabajos.esperar(id)` espera a que
acabe y `trabajos.cancelar(id)` lo cancela. Los eventos (`Progreso` e `Incidencia`) quedan en
`work/shared/verificacion/trabajos/<id>.jsonl` y cumplen `evento_trabajo.schema.json`. No hay asyncio:
la GUI llama desde un `QThread` o un executor.

## Cliente de referencia y gates

- `tools/tests/contrato/test_flujo_gui.py` recorre el ciclo completo sobre un proyecto sintético.
  Comprueba que solo cambia la entrada editada, que el bloqueo se comprueba sobre la candidata nueva y
  que cada `Resultado`, `datos` y evento cumple su esquema. También valida los ejemplos publicados.
- `tools/tests/requiere_rom/test_flujo_gui_real.py` hace el mismo ciclo sobre
  `inazuma1/data_iz/a_title/title_t.arc`, con la candidata vigente y el bloqueo real. La candidata
  resultante solo difiere de la base en esa entrada. El test borra todo lo que crea.
