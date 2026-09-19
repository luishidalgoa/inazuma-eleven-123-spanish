# Cómo clonar el proyecto y trabajar con él

Guía de desarrollo para retomar la traducción (tú, un colaborador o un modelo de IA).
Todos los comandos están verificados contra el código actual. Lee también las
**[lecciones de qué NO funciona](FURIGANA_LECCIONES.md)** (Norma 4 — ahorra builds de 15 min)
y los **[formatos técnicos](FORMATOS.md)** + **[formato del script de evento](EVENT_SCRIPT_FORMAT.md)**.

> ⚖️ **Antes de nada:** nunca subas ROMs ni contenido extraído de ellas (incluido
> `dialogo_oficial.csv`). El `.gitignore` lo bloquea a propósito. Ver [`LEGAL.md`](../LEGAL.md) y la Norma 2 de [`CLAUDE.md`](../CLAUDE.md).

---

## 0. Estado del proyecto (pausado)

Build final **v27**: arranca, **crea partida**, e **intro + diálogo de historia en español**
(gameplay completo sin truncar; intro a mismo tamaño, truncado). Parche distribuible:
[`patch/inazuma123-es-v27.xdelta`](../patch/).

**Muros definitivos** (no reintentar, ver [`FURIGANA_LECCIONES.md`](FURIGANA_LECCIONES.md)):
1. **Parchear el código del juego es IMPOSIBLE de forma fiable.** La zona de "caves" del CRO
   (`ina_main1.cro`, file `0x50E14` / cargado `0xAD9E14`) es **memoria de relocalización**: el
   loader la sobreescribe al cargar → crash `0xAD9E1C`. Ni la ruby (`0xABFCC0`) ni `code.bin`
   (`strcpy 0x14AC5C` / `getc 0x1B3788` / `strcmp 0x184AAC`) son parcheables.
2. **Los eventos de SISTEMA/INTRO no pueden crecer** (la ruby cuelga al avanzar, ❌#9) → van a
   **mismo tamaño** → el español se trunca. La **apertura/crear-partida** (eid `92010100..92010249`)
   exige sus eventos intactos (❌#1) → no se tocan con el fallback global ni con re-paginación.
3. **Techo de DATOS:** ~48 % del diálogo tiene traducción disponible; el resto no existe en
   nuestros datos (habría que traducirlo a mano). No es un problema de motor.

---

## 1. Qué hay en el repo y qué NO

| En GitHub ✅ | NO en GitHub (lo aportas/regeneras) ❌ |
|---|---|
| `tools/` — todo el pipeline (Python + PowerShell) | `roms/` — tus ROMs legales |
| `docs/` — formatos y lecciones | `work/` — extracción + builds intermedios (regenerable) |
| `translation/*/dialogo.csv` — traducciones del proyecto | `translation/*/dialogo_oficial.csv` — texto oficial Nintendo (copyright) |
| `translation/shared/glossary/` — glosarios (términos cortos) | `tools/bin/` — binarios de terceros |
| `patch/*.xdelta` — el parche distribuible | `logs/` — cosecha de errores local |

---

## 2. Requisitos

**Python 3.7+** y la librería de ensamblado ARM (solo la importa `patch_code.py`, *obsolete_dangerous* y ya archivado en `tools/_archivo` en F1.4; keystone solo hace falta para consultar ese histórico):
```
pip install keystone-engine
# opcional, solo si vas a DESensamblar para RE: pip install capstone
```

**Binarios de terceros** → colócalos en `tools/bin/` (ignorado por git):

| Binario | Para qué | Fuente |
|---|---|---|
| `3dstool.exe` | Extraer/reconstruir NCSD/NCCH/ExeFS/RomFS | https://github.com/dnasdw/3dstool |
| `xdelta3.exe` | Generar/aplicar el parche `.xdelta` | https://github.com/jmacd/xdelta |
| `ext_key.txt` | Claves 3DS que `3dstool` necesita para ROMs descifradas | (tus propias claves) |
| Pingouin / Nyanko | *(opcional)* GUIs de Level-5 para inspección | https://github.com/Tiniifan |

**Emulador** para probar: [Azahar](https://azahar-emu.org/) o Lime3DS. (La ruta de Azahar está
hardcodeada en `tools/jugar.ps1` — ajústala a tu máquina.)

**ROMs (tu copia legal, descifrada):**

| ROM | Obligatoria | Para qué |
|---|---|---|
| **Inazuma Eleven 1·2·3** (3DS, JP, `CTR-P-AETJ`, **descifrada**) | ✅ Sí | Es la ROM que se parchea + de donde sale todo el contenido |
| Inazuma Eleven 1 (NDS, EU/ES, `YEES`) | Para regenerar el oficial | Texto español oficial de referencia (game1) |
| Inazuma Eleven 2 (NDS, EU/ES, `BEES`) | Para regenerar el oficial | Texto español oficial de referencia (game2) |

> Si tu 3DS está **encriptada**, descífrala antes (GodMode9 en consola real). El parche está
> hecho contra la versión **descifrada** (flag NoCrypto).

---

## 3. Clonar y preparar

```bash
git clone https://github.com/luishidalgoa/inazuma-eleven-123-spanish.git
cd "inazuma-eleven-123-spanish"
pip install keystone-engine
# 1) copia los binarios a tools/bin/ (3dstool.exe, xdelta3.exe, ext_key.txt)
# 2) copia tu ROM 3DS descifrada a roms/
#    roms/shared/Inazuma Eleven 1-2-3 - Endou Mamoru Densetsu.3ds
# 3) (opcional) copia las ROMs NDS ES a roms/ si vas a regenerar el oficial
```

---

## 4. Regenerar los datos que no están en git

El repo trae `dialogo.csv` y los glosarios, pero **NO** `dialogo_oficial.csv` (copyright) ni la
extracción de la ROM. Para reconstruirlos desde tus ROMs:

```bash
# A) extraer el 3DS (una sola vez) -> work/shared/base_3ds/romfs/, work/shared/base_3ds/exefs/
pwsh -File tools/extract_romfs.ps1

# B) desempaquetar el contenedor Level-5 archive.fa -> work/fa_extract/
python tools/fa_unpack.py work/shared/base_3ds/romfs/archive.fa -o work/fa_extract

# C) extraer las NDS ES (referencia oficial) -> work/ie1/fuentes/nds_es/, work/ie2_es/
pwsh -File tools/extract_nds.ps1 -Rom "roms/Inazuma Eleven.nds" -Name ie1_es
pwsh -File tools/extract_nds.ps1 -Rom "roms/Inazuma Eleven 2 - Tormenta de Fuego.nds" -Name ie2_es

# D) regenerar el diálogo OFICIAL (alinea 3DS-JP <-> NDS-ES) — GITIGNORED, copyright
python tools/ds_official.py game1     # -> translation/ie1/dialogo_oficial.csv
python tools/ds_official.py game2     # -> translation/ie2/dialogo_oficial.csv

# E) (opcional) regenerar glosarios (jugadores/equipos/menús)
python tools/build_glossary.py game1
python tools/build_glossary.py game2
```

> `dialogo_oficial.csv` (game1 ~7.516 líneas, game2 ~24.338) es el **texto oficial de Nintendo**
> alineado por `event_id`. Es la mayor parte de la cobertura. Si lo tienes en un backup local,
> cópialo a `translation/gameN/` y te saltas el paso D.

---

## 5. El pipeline de build (clon → ROM parcheada → parche)

> **Pipeline HISTÓRICO (build v27).** `build_3ds_var.py` y `verify_build.py` están archivados en
> `tools/_archivo/` (motivos en [`tools/_archivo/README.md`](../tools/_archivo/README.md)). La ROM IE1 vigente se construye con
> `work/ie1/capas/v33/_final/build_rom.py`; las candidatas, con `tools/build_ui_revision.py` sobre
> `work/shared/candidatas/probe_ie1_vNN`, y se verifican con `ie123 verificar`.
> Lo que sigue se conserva como registro de la cadena v27.

```bash
# 1) fuentes (acentos) + roster + UI  ->  work/archive_es.fa   (una vez por sesión)
python tools/reinsert.py

# 2) diálogo de longitud variable     ->  work/eve_var/gameN.pkb/.pkh
python tools/reinsert_var.py game1            # (sin arg = game1 + game2)

# 3) compilar la ROM (VALIDA -> repack -> recalcula CXI/3DS)  ->  work/build/inazuma123_es_var.3ds
#    Flags de la build v27 (intro+historia ES, crear-partida estable):
SKIP_CRO=1 NO_CODE_PATCH=1 python tools/_archivo/build_3ds_var.py game1   # (archivado)
#    (en PowerShell:  $env:SKIP_CRO="1"; $env:NO_CODE_PATCH="1"; python tools\_archivo\build_3ds_var.py game1)

# 4) generar el parche distribuible    ->  patch/inazuma123-es-vNN.xdelta
pwsh -File tools/build_patch.ps1 -Translated "work\build\inazuma123_es_var.3ds" -Patch "patch\inazuma123-es-v28.xdelta"

# El parche se aplica y se distribuye con DeltaPatcher; la ROM traducida solo se
# genera localmente al fusionarlo con la copia legal del usuario. Consulta
# `DISTRIBUCION_DELTAPATCHER.md` para el flujo de usuario y la comprobación de
# hashes. No se debe guardar ni publicar la ROM resultante.

# 5) probar en emulador (cosecha errores al cerrar)
pwsh -File tools/jugar.ps1 work\build\inazuma123_es_var.3ds
```

`tools/_archivo/build_3ds_var.py` (archivado) hacía por dentro: `fa_repack` (mete `eve_var` en `archive.fa`) → `patch_exefs`/
`patch_code` (code.bin plano) → **`validate.py`** (aborta si hay regresión) → `3dstool -ctf`
romfs → cxi → 3ds. El `archive.fa` y el CRO originales **se restauran siempre** al terminar.

---

## 6. Tabla de flags de entorno

Se leen en `reinsert_var.py` (paso 2) y `tools/_archivo/build_3ds_var.py` (paso 3, archivado). **La build v27 NO define
ninguno salvo `SKIP_CRO=1` + `NO_CODE_PATCH=1`** (todo lo demás por defecto).

| Flag | Efecto | Paso |
|---|---|---|
| `SYS_ORIG` | Deja SISTEMA/INTRO 100 % **original** (japonés). Útil para garantizar crear-partida. | reinsert_var |
| `SAME_SIZE` | **Todo** a mismo tamaño (sin crecer). Estable pero trunca mucho; furigana en japonés. | reinsert_var |
| `FULLTEXT` | Traduce **todo** (sistema incluido) a texto completo. **Requiere parche CRO** → en la práctica crashea (muro #1). | reinsert_var |
| `NO_BLANK` | Conserva siempre las lecturas furigana (no las vacía). Diagnóstico. | reinsert_var |
| `NO_GLOBAL` | Desactiva el fallback global `{japonés→es}` (solo por-evento). Por defecto: **activo** (+~22 % cobertura). | reinsert_var |
| `EID_LO` / `EID_HI` | Traducir **solo** eventos en `[EID_LO, EID_HI)`. Para bisección (cazar el evento que crashea). | reinsert_var |
| `STRIP_ALL` | Stripear furigana de **todos** los eventos incl. intro → cuelga crear-partida (❌#12). | reinsert_var |
| `GROW_INTRO` | Hacer crecer el intro conservando furigana → cuelga al avanzar (❌#9). | reinsert_var |
| `DEBUG_IDS` | Antepone `[event_id]` a cada línea de gameplay (para identificar eventos jugando). | reinsert_var |
| `SKIP_CRO` | **(v27 = 1)** No parchea el CRO; lo restaura del `.orig`. El parche es inútil (muro #1). | build_3ds_var (archivado) |
| `NO_CODE_PATCH` | **(v27 = 1)** No parchea `code.bin` (lo deja plano sin bounds-checks). | patch_code |
| `SKIP_VALIDATE` | Salta la validación pre-build. **Peligroso** — solo builds de prueba. | build_3ds_var (archivado) |

---

## 7. Validar y probar (red de seguridad)

- **`python tools/validate.py [game1]`** — chequeo OFFLINE antes de compilar: operandos corruptos,
  refs string a media cadena, diálogo vaciado, estructura SSD inválida, **furigana que crece (❌#9)**,
  desbalance marcador↔lectura (bug NPC). Es consciente del modo: en builds que crecen tolera el
  cambio de `textSize` pero verifica que sea coherente; en `SAME_SIZE` es estricto. Debe dar
  **`RESULTADO: TODO OK ✅`**. (`tools/_archivo/build_3ds_var.py`, archivado, lo corría solo y aborta si falla.)
- **`python tools/_archivo/verify_build.py game1`** (histórico, archivado; ver [`tools/_archivo/README.md`](../tools/_archivo/README.md)) — verificación estática de los artefactos de una build
  de **mismo tamaño** (CRO byte-idéntico, sistema byte-idéntico, `textSize` intacto, furigana
  intacto, español presente). Útil tras builds `SAME_SIZE`.
- **`pwsh -File tools/jugar.ps1 [build.3ds]`** — lanza Azahar y, **al cerrarlo, cosecha** los
  errores de runtime a `logs/runtime_errors.json` agrupados por **PC** (firma estable del crash).
- **`ie123 registro [--sesion NOMBRE]`** (antes `harvest_log.py`) — recompone/reimprime el informe de errores.

> **Para diagnosticar un crash nuevo:** mira el PC en `logs/runtime_errors.json`. Si está en
> `0x14AC5C`/`0x1B3788`/`0x184AAC`/`0xABFCC0` es un desbordamiento de las funciones de texto →
> mete ese evento en `DONT_TOUCH` (japonés estable). Usa `DEBUG_IDS=1` para saber qué evento es.

---

## 8. Arquitectura del diálogo (resumen)

El diálogo vive en `archive.fa → inazuma{1,2}/data_iz/script/eve.pkb` (+ `.pkh` índice "PackNum").
Cada evento va **comprimido con LZ10**; descomprimido es un **SSD** (bytecode + texto).

- **El texto se referencia por ÍNDICE de entrada, no por offset** (descubierto vía
  [Tiniifan/SceneScriptData](https://github.com/Tiniifan/SceneScriptData)). Por eso `ssd_reinsert.py`
  **no reubica nada**: el bytecode queda intacto y el diálogo puede crecer libre.
- **Gameplay** (eid `< 90000000`): se quita el furigana (`%NF`) y se traduce a **texto completo**
  (crece). Las lecturas de líneas traducidas se vacían (balance marcador↔lectura, fix bug #2).
- **Sistema/Intro** (eid `>= 90000000`): **INPLACE** a mismo tamaño, conservando los marcadores
  (`_furigana_body_bytes`) + **re-paginación** (reparte el ES en las mismas páginas `\f` que el JP,
  recupera líneas que se rechazaban). La apertura `92010100..92010249` no se re-pagina (crear-partida).
- **Fallback global:** si una línea no tiene traducción por-evento pero su mismo japonés está
  traducido en **otro** evento, se reusa (solo en gameplay; en intro descuadra y cuelga).

Detalle completo: [`FORMATOS.md`](FORMATOS.md) y [`EVENT_SCRIPT_FORMAT.md`](EVENT_SCRIPT_FORMAT.md).

---

## 9. Cómo continuar (problemas abiertos)

1. **Subir cobertura > 48 %** (lo más rentable): traducir a mano lo que falta en `dialogo.csv`
   (estado `pendiente`/`revisar`), u objetos/técnicas (`item.dat`/`command.STR`, que no casan 1:1).
   El motor ya aguanta; el límite es de datos.
2. **Reducir truncado del intro:** los eventos de sistema no pueden crecer. Solo mejoraría con
   traducciones más cortas que quepan, o aceptando el truncado.
3. **Objetos y técnicas** (issues #1/#2): pendientes de parsear sus índices.
4. **Juego 3:** sin empezar.
5. **NO reintentar:** parchear `code.bin`/CRO (muro #1), hacer crecer furigana (❌#9), stripear el
   intro (❌#1/#12). Está todo en [`FURIGANA_LECCIONES.md`](FURIGANA_LECCIONES.md).
