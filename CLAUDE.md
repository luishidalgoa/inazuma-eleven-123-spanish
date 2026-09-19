# Guía para Claude (y colaboradores) — Proyecto de traducción Inazuma Eleven 1·2·3

> TIPOGRAFÍA BLOQUEADA por petición explícita del usuario: v20 es la referencia
> visual aprobada. Cumplir el bloqueo de AGENTS.md y tools/dialogue_lock.py.
> No cambiar caja, fuentes, codificación, espaciado o saltos ni desactivar sus
> comprobaciones al continuar la traducción. Requiere una nueva petición explícita
> del usuario sobre la tipografía; no una orden general de continuar.

Este archivo lo lee Claude Code al inicio de cada sesión. Resume las **normas de
trabajo** del proyecto. Léelo antes de actuar.

## Norma 1 — Todo el trabajo se gestiona con GitHub Issues + Project board

**Cada tarea pendiente o nueva se registra como un issue de GitHub.** Nada se queda
solo "en la cabeza" o en el chat. En concreto:

- Antes de empezar algo nuevo, comprueba si existe un issue; si no, **créalo**
  (`gh issue create`) con título claro, descripción y etiqueta(s).
- Al **empezar** una tarea, deja constancia (asignación/comentario) y, si hay
  Project board, muévela a "In progress".
- Al **terminar**, **cierra el issue** (`gh issue close` o `Closes #N` en el commit/PR)
  y muévelo a "Done".
- Si surge trabajo derivado (un bug, un formato nuevo que decodificar, una mejora),
  **abre un issue** en el momento en lugar de dejarlo suelto.
- Usa el Project board del repo para la visión de conjunto.

> Si `gh` no está autenticado en una sesión, redacta los issues nuevos en
> `docs/ISSUES_PENDIENTES.md` y créalos en GitHub en cuanto haya autenticación.

## Norma 2 — Copyright: nunca subir ROMs ni contenido extraído

- **Jamás** se suben ROMs (`.3ds`, `.nds`, `.cia`…) ni contenido extraído de ellas
  (RomFS, `.STR`, `.dat`, `.arc`, diálogos/descripciones completas, fuentes, gráficos).
- El `.gitignore` bloquea `roms/` y `work/`. No lo desactives.
- Se distribuye **solo el parche `.xdelta`** + herramientas/scripts + glosarios de
  términos cortos. Ver [`LEGAL.md`](LEGAL.md).
- Antes de cada push, verifica con `git ls-files` que no se cuela nada sensible.

## Norma 3 — Estilo y decisiones del proyecto

- Traducción al **español de España**, con **nombres europeos oficiales**
  (Mark Evans, Axel Blaze, Raimon…). Fuente canónica: el texto oficial ES de las
  ROMs NDS (ver `translation/shared/glossary/`).
- Commits incrementales y descriptivos. Documenta los formatos en `docs/FORMATOS.md`
  y el avance en `docs/PROGRESO.md`.
- Herramientas en `tools/` (Python/PowerShell, sin GUI: el proyecto se maneja por CLI).
- El código Python vive en el paquete `tools/src/ie123kit`; en `tools/` quedan shims con los
  nombres antiguos y los 5 ficheros congelados del bloqueo v20.

- **Los diálogos no se reescriben para que quepan.** Se usa el texto oficial íntegro (el port europeo de 3DS para el IE1, la NDS española para el IE2). Si una frase no cabe en la ventana, se reparte en más cajas o páginas, o se amplía la ventana, pero nunca se condensa ni se le quitan palabras.

## Norma 4 — NO repetir errores ya detectados

Antes de tocar la **reinserción de diálogo / furigana** (`tools/reinsert.py`, código real en `ie123kit._legado.reinsert`), lee
**[`docs/FURIGANA_LECCIONES.md`](docs/FURIGANA_LECCIONES.md)**: lista cada enfoque que
YA se probó en emulador y FALLÓ (con el motivo). Cada entrada costó una build de
~15 min + una prueba del usuario. **No reintentar lo que está marcado como ❌.**
Si descubres un fallo/limitación nuevo, **añádelo a ese documento** en el momento.

## Norma 5 — Arquitectura por juego

Todo recurso se guarda en la carpeta de su juego (`ie1/`, `ie2/<versión>/`, `ie3/<versión>/`) o en
`shared/` si es común a la recopilación, tanto en `work/` como en `Roms/` y `translation/`. Nada nuevo en
la raíz de `work/`. Ver **[`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md)**; tras instalar una candidata,
`ie123 work limpiar --borrar`.

## Estado y documentación

- **Criterio obligatorio del usuario para IE1 (2026-09-05):** seguir
  **[`docs/PROTOCOLO_QA_IE1.md`](docs/PROTOCOLO_QA_IE1.md)**. Probar hasta la primera
  pachanga, hablar con varios NPC, detenerse ante el primer fallo, corregirlo y
  repetir su reproducción antes de continuar. No aceptar cajas de diálogo con bugs
  gráficos ni declarar estabilidad solo con validación offline.

- **⚠️ Lecciones (qué NO funciona): [`docs/FURIGANA_LECCIONES.md`](docs/FURIGANA_LECCIONES.md)**
- Avance: [`docs/PROGRESO.md`](docs/PROGRESO.md)
- Formatos técnicos (B123, ARCV, .STR, .dat, codificación): [`docs/FORMATOS.md`](docs/FORMATOS.md)
- Herramientas: [`tools/README.md`](tools/README.md)
- Especificación del toolkit ie123kit: [`docs/toolkit/ESPECIFICACION.md`](docs/toolkit/ESPECIFICACION.md)
- CI del toolkit (Windows y Ubuntu; no se desactiva): [`.github/workflows/toolkit.yml`](.github/workflows/toolkit.yml)
- Guardia global anti-ROM (Norma 2) y bloqueo v20, en todos los commits y sin filtro de rutas:
  [`.github/workflows/guardia.yml`](.github/workflows/guardia.yml)
- Glosario: [`translation/shared/glossary/`](translation/shared/glossary/)
