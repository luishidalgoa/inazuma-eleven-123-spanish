# Menús IE1 y siguiente recorrido

## Tanda de interfaz, 2026-09-06

Los menús señalados usan atlas CTPK en contenedores ARCV, algunos envueltos
en SSZL. `ie123kit._legado.ui_archive` decodifica ese envoltorio. `ie123kit.nucleo.graficos.ctpk`
permite leer y reescribir los píxeles conservando dimensiones y metadatos.
`ie123kit._legado.translate_ui_textures` aplica un manifiesto JSON local con rectángulos
de texto y produce vistas previas para revisión. Dependencias: Pillow y
opencv-python-headless (borrado del texto sobre fondos).

Los originales, manifiestos con traducciones y vistas previas permanecen en
`work/`. La candidata v6 conserva los cambios de diálogo y fuente de v5.
La revisión de imágenes y el roundtrip de archivos NO prueban el funcionamiento
en Azahar. Repetir partida nueva, menús, nombre y selección Sí/No con el usuario.
El teclado necesita resolver su correspondencia de entrada antes de cambiar
las teclas japonesas por letras latinas; no confundir rótulos con caracteres.

Vídeos: el usuario confirma que vuelven a verse tras el ajuste de presentación
del emulador. No modificar los vídeos de la ROM ni reabrir ese fallo sin evidencia.

## Siguiente tanda: cobertura del capítulo 1

Petición explícita del usuario del 2026-09-06: avanzar por la progresión del juego,
sin limitar la traducción a conversaciones mostradas en capturas. Intentar
completar el capítulo 1; si queda parcial, delimitar exactamente qué falta.

- Inventariar eventos de historia y variantes de NPC según progreso del capítulo.
- Traducir lugares, objetivos, nombres, equipamiento y pantallas/botones usados
  durante ese recorrido; conservar opciones, argumentos y referencias de eventos.
- Revisar el texto oficial español cuando exista correspondencia comprobada.
- Medir cobertura por registros y eventos realmente reinsertados; separar
  coincidencias ausentes, pendientes y verificadas. No contar textos del CSV
  como traducciones activas sin demostrar su reinserción.
- Probar con el usuario hasta la primera pachanga según PROTOCOLO_QA_IE1.md;
  ampliar después el recorrido del capítulo. Parar, corregir y repetir cada fallo.

Primera laguna conocida: evento 92010300 aún tiene coincidencias ausentes en v5.
Priorizar su revisión completa y los siguientes eventos conectados, además de
NPC opcionales, sin esperar nuevas capturas para localizar sus textos.

## Candidata v6 instalada

- Archivo local: `work/shared/candidatas/probe_ie1_v6/archive.fa`.
- SHA256: `649894fc3ef17c643a35589f52d721e4b7797dfe348ae2000adf003f4e5b7cdc`.
- Instalada con Azahar cerrado mediante enlace duro; copia anterior conservada
  en `work/shared/candidatas/probe_ie1_v6/previous-installed.fa`.
- 15 sustituciones de textura en 7 archivos ARCV (un botón común está duplicado
  en dos archivos). Menú inicial, volver, Extras, Sí/No, avisos de carga,
  avisos iniciales, instrucciones y botones de nombre.
- Pasan los fixtures sintéticos de los ocho formatos de píxel admitidos y SSZL;
  roundtrip real de cada textura, dimensiones, metadatos y entradas conservados.
- Verificados los hashes de los 12 recursos adicionales dentro del archivo final.
  Los 44 registros traducidos coinciden con v5.
- Vistas previas inspeccionadas; borrado inicial con restos de japonés rechazado
  y corregido antes de construir la candidata instalada.
- PENDIENTE: prueba en juego por el usuario. No certificada hasta la primera pachanga.
- Teclas de entrada hiragana/katakana pendientes; sus rótulos no se han sustituido
  por letras latinas sin localizar antes la correspondencia funcional.

## Candidata v7 preparada e instalada

- Archivo: `work/shared/candidatas/probe_ie1_v7/archive.fa`.
- SHA256: `9d1a80d9cada5c39179356042b5a4f84268617591157373629b8d1776f78e26c`.
- Incluye menús de Extras y récords, guardado y sobrescritura, teclado latino,
  botones de partido, logos de la recopilación, pantallas iniciales y el aviso
  legal completo sin el recorte de la v6.
- Amplía la historia y los NPC hasta el tramo previo al partido contra la Royal,
  además de lugares, objetivos, 1.132 nombres cortos y 28 objetos.
- La copia de la candidata anterior queda en
  `work/shared/candidatas/probe_ie1_v7/previous-installed.fa`; el archivo nuevo está enlazado en
  la carpeta de mods de Azahar.
- El informe de construcción no contiene sustituciones rechazadas ni registros
  ausentes. Sigue pendiente la prueba de juego por el usuario y, por tanto, no
  se certifica todavía como traducción completa del capítulo 1.

## Candidata v8 preparada, pendiente de prueba

- Archivo local: work/shared/candidatas/probe_ie1_v8/archive.fa.
- SHA-256: 246341bad13ca68f36c7dffe221647b81fe7936e427138c8fe00fd59db9650f8.
- Incluye 184 registros SSD traducidos y validados estáticamente, sin rechazos
  ni registros ausentes en los 18 eventos seleccionados. Añade la ruta de la
  torre y la conversación del cuaderno de David Evans
  (92010520, 92010550, 92010600, 92010620 y 92010640).
- El transporte latino de ancho completo ahora toma los avances de cada glifo
  latino normal en FONT12 y FONT8. Conserva dibujos, mapas y tamaños de archivo;
  solo ajusta métricas BCFNT/NFTR. Es una corrección dirigida al espacio excesivo
  entre letras y requiere revisión visual en Azahar.
- El atlas de títulos contiene los rótulos de los capítulos 1 a 10 y sus
  indicadores Cap. y números. No se han cambiado coordenadas QNA ni
  animaciones.
- En el carrusel solo se reduce Ventisca Eterna al 84 % dentro de su casilla:
  era el único logo occidental sobredimensionado frente al original. El recorte
  parcial de la ficha lateral es parte del carrusel original.
- El registro corto del NPC 1049 muestra Veteran. El nombre canónico
  Sr. Veteran no cabe en sus 16 bytes con la codificación segura actual; los
  diálogos variables pueden conservar el nombre completo.
- La candidata no se ha instalado: Azahar seguía ejecutándose y el mod activo
  permanece en v7. Antes de sustituirlo, cerrar el emulador y conservar v7 como
  reversión. La prueba obligatoria sigue siendo una partida nueva hasta la
  primera pachanga, con los NPC y las escenas recién añadidos.

## Candidata v9 preparada, pendiente de prueba

- Archivo local: work/shared/candidatas/probe_ie1_v9/archive.fa.
- SHA-256: 6c8f154fce7e37a5d137043ae6783a545eb1f54ce758c43a68a940f1a6b16fff.
- Añade 21 diálogos de NPC normales en 81000040: instituto, puertas,
  aparcamiento, zona comercial y avisos de progreso temprano. No se modificaron
  elecciones, modales, puntos de recuperación ni activadores de escena.
- Cada registro nuevo conserva su hash de fuente, usa el mismo número de páginas
  que el japonés y pasa los límites de SSD. Frente a v8 no cambia ningún otro
  registro de ese evento ni su bytecode.
- El informe estático registra 205 sustituciones y no tiene rechazadas ni
  ausentes. Está instalada como mod LayeredFS; la v7 se conserva en
  work/shared/candidatas/probe_ie1_v9/previous-installed.fa. Sigue pendiente la prueba en Azahar
  con partida nueva.
- Para la siguiente tanda quedan la interfaz de pachangas, el rótulo rojo de
  límite de tiempo, más lugares y misiones, formación/equipamiento y el avance
  excesivo de los puntos suspensivos.
