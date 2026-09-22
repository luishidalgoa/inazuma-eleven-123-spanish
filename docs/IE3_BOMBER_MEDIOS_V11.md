# IE3 — complemento de medios Bomber v1.1

## Evidencia nueva: 21/09/2026

El log `20260921_145552_456250.log` termina en `comparar_pareja` después de
anunciar el vídeo op00b. Los contadores devueltos son JP 2213 y ES 2203.
No se llegó a crear la nueva candidata: v1 planifica antes de copiarla.

El diferencial medido de duración es -10/24 segundos ES respecto a JP.
No se deduce de ese total dónde difiere el montaje, si existen fotogramas
negros/repetidos, qué duración maneja el motor o si OpenCV terminó por EOF
o por un problema de backend. El código ya registraba esta última limitación.

## Decisión

No ampliar una tolerancia, no forzar el contador esperado y no recodificar.
Mantener la comparación estricta de todos los vídeos que se emitan.

Se introduce una política adicional **explícita** que NO intenta insertar el
opening: conserva op00b.moflex + op00b.SAD JP como pareja, comprueba los hashes
de ambos y marca sus destinos pendientes. Así se puede construir una candidata
con tres cortinillas ES y el ending ES, manteniendo todos los demás recursos.

La excepción es de selección (no se emite el recurso), no de validación temporal.
El modo de librería/CLI por defecto sigue siendo estricto.

## Implementación

Módulos nuevos:
- `ie3/bomber_medios_v11.py`: coordina preparar/verificar/construir.
- `comun/bomber_medios_integracion_v11.py`: plan, aislamiento y readback de candidata.
- `ie3/bomber_opening_diagnostico.py`: exportación privada del par original JP/ES.
- `comun/bomber_video_qa.py`: se reutiliza exactamente el de v1; no cambia.

No se modifican `fase5.py`, `medios_es.py`, `build_piloto.py`, perfiles,
fuentes, CRO, encoder o los cinco congelados.
El constructor existente se sigue encargando de reextraer la ROM completa.
La prueba textual se hereda solo tras verificar igualdad de todos los recursos
no multimedia con la base y enlazar sus evidencias existentes por hashes.

No se mueven manifiestos anteriores. La v1.1 tiene schema, módulos y salidas
separadas, de modo que no se reescribe código ligado a posibles candidatas v1.

## Contrato de la omisión

Con `--opening conservar-base`:
1. Se leen y validan los hashes JP/ES de cada vídeo.
2. Se decodifican o validan las QA existentes ligadas a SHA-256.
3. Para op00b se conserva evidencia exacta de ambos contadores y del diferencial.
4. Solo op00b puede quedar pendiente por esta política.
5. Se comprueba que el vídeo de base sea JP y que el audio efectivo sea JP.
6. No se cambia ni el vídeo ni el audio de op00b.
7. Los tres vídeos restantes deben pasar comparar_pareja sin cambios.
8. Solo se emite end00b.SAD de las dos canciones previstas.
9. La verificación recalcula el contrato y rechaza planes o políticas adulterados.

Los informes no eliminan op00b de la cobertura pendiente ni lo cuentan como
preparado; señalan que sus fuentes ES existen pero esta transición no se aplica.

## Continuación para resolver el opening

El exportador genera los dos MOFLEX y SADL originales, y DAT si existen,
sin modificarlos. A partir de ellos se podrá comparar el inicio, final y
montaje, contraste de decodificadores y relación vídeo/audio; si se propone
una integración ES de distinta duración, necesitará un contrato distinto
justificado y prueba dinámica. No basta convertir 2213 en 2203 en el JSON.

## Pendientes que no se resuelven

DAT JP, bancos de sonido, nueve audios a3y, promociones sin fuente y restantes
textos/UI conservan el estado de la base. Igualar duración en las cortinillas
tampoco certifica su mezcla con el sonido heredado.
No se marca el juego ni esta candidata como validado en consola.

## Pruebas

`python -X utf8 -m pytest tools/tests/unidad/test_ie3_bomber_medios_v11.py`

Las pruebas son sintéticas y no incluyen material comercial. El paquete contiene
un informe de su ejecución local; no sustituye las pruebas con originales.
