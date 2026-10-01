"""Menús del CRO de IE2 (``ina_main2.cro``) con el camino proporcional del motor (capa ``menus_cro/menus``).

Parámetros de IE2 v23 (issue #77) y la orquestación de su ``apply.py`` (pasos 1 y 2: reparto y códigos
nuevos) sobre el motor genérico :mod:`ie123kit.nucleo.fuentes.rebanadas`. Los textos de los menús
(clave japonesa y alternativas) NO están aquí (Norma 2): los pasa quien llama, como ``bloques``
``{nombre: (inicio, fin, máx. bytes por entrada, fuente, [(clave, [alternativas])])}``.

- FONT12: reparto por trozos (letras nativas, códigos del registro con hueco de 1-2 px y códigos nuevos
  dibujados con el espaciado natural de la fuente), elegido por DP con un presupuesto de códigos.
- FONT8 (cajas Pasión/Amistad): tira con 2 px de núcleo cortada en rebanadas de 10 px con left 0 y
  avance 10; la colocación es la misma a paso fijo de 10 y por el camino proporcional
  (``trunc((11 - 10) / 2) = 0``). Cada rebanada usa el glifo FONT8 de un código que la capa dibuja en
  FONT12 (esos códigos solo se muestran en el menú, con FONT12).
"""
from __future__ import annotations

import string
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ie123kit.nucleo.fuentes import rebanadas as M

__all__ = [
    "F8",
    "F12",
    "HUECO8",
    "LETRAS",
    "PARAM",
    "PASO8",
    "repartir",
]

F12, F8 = "font/FONT12.bcfnt", "font/FONT8.bcfnt"
PARAM = {
    F12: M.ParametrosReparto("FONT12", ancho=15, umbral=1, permitidos=(1, 2), inicio={1: 0.0, 2: 0.0}),
    F8: M.ParametrosReparto("FONT8", ancho=11, umbral=8, permitidos=(1, 2, 3), inicio={0: 0.0, 1: 0.0}),
}
#: Letras nativas que el reparto puede reutilizar.
LETRAS = string.ascii_letters + "áéíóúñÁÉÍÓÚÑ."
PASO8, HUECO8 = 10, 2


def _rebanadas8(F: Mapping[str, Any], texto: str, codigos: list[str], hechas: list[str],
                por_sjis: dict[str, dict], codepoint: Callable[[str], int]):
    px = M.tira_nucleo(F[F8], texto, codepoint, umbral=PARAM[F8].umbral, hueco=HUECO8, inicio=1)
    body, cas = b"", []
    for k, rel in M.rebanar(px, PASO8):
        s = codigos[len(hechas)]
        ch = bytes.fromhex(s).decode("cp932")
        gi = F[F8].gi(ord(ch))
        viejo, cwdh = M.escribir_rebanada(F[F8], gi, rel, PASO8)
        por_sjis[s]["rebanada_FONT8_v23"] = {"texto": texto, "rebanada": k, "glifo": gi, "cwdh_antes": viejo, "cwdh": cwdh,
                                                 "pixeles_sha1": M.huella(rel)}
        hechas.append(s)
        body += bytes.fromhex(s)
        cas.append({"t": f"{texto}[{PASO8 * k}:{PASO8 * (k + 1)}]", "tipo": "rebanada", "codigo": s,
                        "columna": PASO8 * k, "lapiz": PASO8 * k, "avance": PASO8})
    return body, cas


def repartir(F: Mapping[str, Any], cro: bytes, registro: Sequence[Mapping[str, Any]],
             bloques: Mapping[str, tuple], recuperar: Sequence[str], codepoint: Callable[[str], int],
             forzados: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
             espejo: tuple[int, int, bytes] | None = None) -> dict[str, Any]:
    """Reparte los bloques de menú del CRO y dibuja los códigos nuevos en ``F`` (fuentes en memoria).

    ``recuperar`` son los códigos libres que se pueden usar (en orden); ``forzados`` fija las
    alternativas de alguna entrada por bloque; ``espejo`` = (inicio, fin, bytes) de una copia fija.
    Devuelve ``{cro, registro, anadidas, libres, bloques, usados}``; las fuentes quedan dibujadas en ``F``.
    """
    reg = [dict(e) for e in registro]
    cro = bytearray(cro)
    Rs = {f: M.Reparto.con(F[f], M.CAJA[f], codepoint, PARAM[f],
                           M.existentes(F[f], f, reg, LETRAS, codepoint, excluir=recuperar)) for f in (F12, F8)}
    frentes = {n: M.frente_bloque(Rs[b[3]], b, (forzados or {}).get(n))
               for n, b in bloques.items() if b[3] == F12}
    usados, (_clave, eleccion) = M.elegir(frentes, len(recuperar))
    eleccion = dict(eleccion)

    pool = list(recuperar)
    nuevo_reg = [dict(e) for e in reg if e["sjis"] not in recuperar]
    anadidas: list[dict] = []
    usados_f12: list[str] = []
    rebanadas_f8: list[str] = []
    por_sjis: dict[str, dict] = {}
    informe: dict[str, Any] = {}
    for nombre, (ini, fin, max_e, f, entradas) in bloques.items():
        filas, buf = [], b""
        if f == F8:
            eleccion[nombre] = [(jp, alts[0], None) for jp, alts in entradas]
        for jp, texto, cas in eleccion[nombre]:
            if f == F8:
                body, cas8 = _rebanadas8(F, texto, usados_f12, rebanadas_f8, por_sjis, codepoint)
                if len(body) > max_e or b"\0" in body:
                    raise ValueError(f"{nombre}/{texto}: {len(body)} B")
                buf += body + b"\0"
                filas.append({"japones": jp, "texto": texto, "bytes": len(body), "despues_hex": body.hex(), "casillas": cas8})
                continue
            body = b""
            for c in cas:
                if c["tipo"] == "nueva":
                    s = pool.pop(0)
                    ch = bytes.fromhex(s).decode("cp932")
                    gi = F[f].gi(ord(ch))
                    viejo, cwdh = M.escribir_glifo(F[f], gi, c["rel"], c["x"], c["lapiz"], c["adv"],
                                                   PARAM[f].ancho, M.CAJA[f])
                    c["codigo"], c["gi"] = bytes.fromhex(s), gi
                    nombre_f = PARAM[f].nombre
                    e = {"sjis": s, "unicode": f"U+{ord(ch):04X}", "kanji": ch, "par": c["t"],
                             "clave": f"{nombre_f}v23{nombre}{c['x']:+d}{c['t']}",
                             "origen": "v23_recuperado_v22", "campos": ["cro_ie2_v23"],
                             "variante": f"v23 pieza {nombre_f} de «{texto}» (tinta desde la columna {c['x']}, "
                                      f"lápiz {c['lapiz']}, camino proporcional)",
                             "fuentes": {f: {"glifo": gi, "cwdh_antes": viejo, "cwdh": cwdh, "columna": c["x"],
                                              "pixeles_sha1": M.huella(c["rel"])}},
                             "glifo": gi, "cwdh": cwdh}
                    nuevo_reg.append(e)
                    anadidas.append(e)
                    usados_f12.append(s)
                    por_sjis[s] = e
                body += c["codigo"]
            if len(body) > max_e or b"\0" in body:
                raise ValueError(f"{nombre}/{texto}: {len(body)} B")
            buf += body + b"\0"
            filas.append({"japones": jp, "texto": texto, "bytes": len(body), "despues_hex": body.hex(),
                              "casillas": [{"t": c["t"], "tipo": c["tipo"], "codigo": c["codigo"].hex().upper(),
                                             "columna": c["x"], "lapiz": c["lapiz"], "avance": c["adv"]} for c in cas]})
        if len(buf) > fin - ini + 1:
            raise ValueError(f"{nombre}: {len(buf)} B > {fin - ini + 1}")
        cro[ini:fin + 1] = buf + bytes(fin - ini + 1 - len(buf))
        informe[nombre] = {"inicio": hex(ini), "fin": hex(fin), "fuente": PARAM[f].nombre, "bytes_usados": len(buf),
                               "bytes_disponibles": fin - ini + 1, "entradas": filas}
    if espejo is not None:
        ini, fin, datos = espejo
        cro[ini:fin + 1] = datos + bytes(fin + 1 - ini - len(datos))
    return {"cro": bytes(cro), "registro": nuevo_reg, "anadidas": anadidas, "libres": pool, "bloques": informe,
                "usados": usados}
