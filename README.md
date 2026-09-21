# Inazuma Eleven 1·2·3!! Endō Mamoru Densetsu — traducción al español

Traducción de aficionados, sin ánimo de lucro, de la recopilación de Nintendo 3DS que
solo salió en Japón.

**Aquí no hay ROMs.** Solo el parche y las herramientas. Pones tu copia, que debe ser
legal. Ver [`LEGAL.md`](LEGAL.md).

## Qué está traducido

- **Inazuma Eleven 1**: historia, menús, objetos, técnicas y jugadores, con nombres
  europeos oficiales (Mark Evans, Axel Blaze, Raimon…).
- **Voces y cinemáticas** en español.
- **Interfaz de la recopilación**.
- Los juegos **2 y 3 siguen en japonés**.

Estado de desarrollo local de IE3: Spark/Ogre disponen de una reconstrucción
general de textos soportados y una candidata pendiente de validación manual,
no una traducción completa verificada ni una publicación. Véase
[integración IE3 fase 3](docs/IE3_FASE3_INTEGRACION.md).

Detalle en [`docs/PROGRESO.md`](docs/PROGRESO.md).

## Cómo jugarlo

> **Por ahora solo emulador.** El `.3ds` que genera IE-repack funciona en Azahar y Lime3DS,
> pero no pasa la verificación en una 3DS real. Es un fallo de la herramienta, ya comunicado.

**Necesitas:** tu copia de *Inazuma Eleven 1·2·3!!* (3DS, `CTR-P-AETJ`) volcada y
**descifrada**, en `.3ds` o `.cia`; el paquete `inazuma123-es-v1.0-pack.zip` de [Releases](../../releases); la herramienta [IE-repack](https://github.com/Javiju555/IE-repack)
de Javiju555; y unos 12 GB libres.

1. Descomprime IE-repack entero (necesita su carpeta `sidecars` al lado) y el paquete en
   otra carpeta.
2. Abre IE-repack y elige el modo **Pack (manifiesto)**.
3. Base: tu copia japonesa. Pack: la carpeta `pack` (la que trae `manifiesto.json`).
   Elige dónde guardar y pulsa el botón.
4. Abre el `.3ds` resultante en **Azahar** o **Lime3DS**: Archivo → Cargar archivo.

La herramienta verifica el hash de cada archivo antes y después de parchear. Si sale
**«ningún origen cuadra con el manifiesto»**, tu copia no es la ROM japonesa original:
no vale una ya traducida, ni una cifrada, ni otra región.

Si usas la carpeta de mods de Azahar (`load/mods/<TitleID>/romfs/`), desactívala para
probar el `.3ds`: sus archivos tienen prioridad sobre cualquier ROM que cargues.

> Las releases **v1 y v1.1** siguen publicadas para DeltaPatcher, pero exigen un volcado
> byte a byte idéntico al nuestro. Ver [`docs/DISTRIBUCION_DELTAPATCHER.md`](docs/DISTRIBUCION_DELTAPATCHER.md).

## Límites conocidos

Parchear el código del juego es inviable, los eventos de sistema y de intro no pueden
crecer, y parte del diálogo no tiene datos de traducción. No es un fallo del motor: es el
techo de lo que hay. Cada intento fallido está documentado en
[`docs/FURIGANA_LECCIONES.md`](docs/FURIGANA_LECCIONES.md); léelo antes de reintentar nada.

## Colaborar

Estado local IE3: [fase 4, candidata de colocación/nombres/interfaz pendiente
de validación manual](docs/IE3_FASE4_INTEGRACION.md). Sus límites demostrados son
específicos de IE3; las restricciones históricas anteriores no se generalizan
a los consumidores auditados en ese informe.

- **Desarrollo** (clonar, requisitos, build): [`docs/DESARROLLO.md`](docs/DESARROLLO.md)
- **Traducir texto** (estilo, glosario): [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
- **Formatos técnicos**: [`docs/FORMATOS.md`](docs/FORMATOS.md) ·
  [`docs/EVENT_SCRIPT_FORMAT.md`](docs/EVENT_SCRIPT_FORMAT.md)
- **Herramientas** (paquete `ie123kit`): [`tools/README.md`](tools/README.md)

## Créditos

- Dirección y traducción: **luishidalgoa**
- Colaboración: **TitoGalan**
- Herramienta de parcheo [IE-repack](https://github.com/Javiju555/IE-repack): **Javiju555**
- Terceros: ver [`tools/README.md`](tools/README.md)

No asociado a LEVEL-5. Las marcas y el contenido del juego pertenecen a sus dueños.
