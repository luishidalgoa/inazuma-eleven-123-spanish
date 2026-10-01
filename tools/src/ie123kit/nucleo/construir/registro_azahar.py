"""Cosechador de errores de runtime de Azahar.

IDEA (peticion del usuario): CADA vez que se arranca el juego, recoger
automaticamente el log de errores de Azahar y acumularlo en NUESTRO PROPIO
registro persistente, para detectar cosas que mejorar en la siguiente version
SIN depender de que alguien este mirando el log en vivo (mas eficiente que
"escuchar" en directo: se acumula solo, partida tras partida).

Que hace:
  1. Lee el log de Azahar (por defecto el actual + el .old).
  2. Extrae las lineas <Error>/<Critical>. Las de memoria
     ('unmapped ReadN @ 0xADDR at PC 0xPC') se agrupan por (op, tamano, PC):
     el PC es la posicion de codigo -> firma ESTABLE del mismo bug; la direccion
     leida varia y se descarta. El resto se normaliza (se quitan numeros/hex) por
     subsistema+mensaje.
  3. Funde el resultado en logs/runtime_errors.json (registro persistente): cada
     firma guarda primera/ultima vez, veces totales, nº de sesiones, estado y una
     nota nuestra. Anota PCs ya diagnosticados desde KNOWN_PCS.
  4. Imprime (y escribe logs/INFORME_ERRORES.md) un informe: firmas NUEVAS de esta
     sesion (candidatas a mejorar), las mas frecuentes y el total abierto.

Para no contar dos veces el mismo log, se guarda una "huella" (tamano+mtime) de
cada fichero ya procesado; jugar.ps1 ademas vacia el log antes de cada partida,
asi que cada cosecha = una partida limpia.

Uso:
  python tools/harvest_log.py                 # log actual + .old, registra
  python tools/harvest_log.py --session NAME  # solo el actual (lo usa jugar.ps1)
  python tools/harvest_log.py --report        # solo reimprime el informe
  python tools/harvest_log.py --force         # ignora la huella (re-procesa)
"""
import os
import re
from datetime import datetime

from ie123kit.nucleo.config.raiz import find_root

REPO = str(find_root())
LOGDIR = os.path.join(os.path.expandvars("%APPDATA%"), "Azahar", "log")
REG = os.path.join(REPO, "logs", "runtime_errors.json")
INFORME = os.path.join(REPO, "logs", "INFORME_ERRORES.md")

# PCs ya diagnosticados: PC -> (estado, explicacion). Se amplia segun investiguemos.
# estados: abierto | investigando | resuelto | conocido_no_arreglable
KNOWN_PCS = {
    "0x001C8D68": ("resuelto", ("Read32 del contador SSD: crash 'unmapped Read32' por "
                                "el offset-fixup. ARREGLADO con el fixup preciso por string-slots.")),
}

LINE = re.compile(r"\[\s*[\d.]+\]\s+(?P<sub>\S+)\s+<(?P<lvl>\w+)>\s+(?P<body>.*)$")
LOC = re.compile(r"^.*?:\d+:\s*(?P<msg>.*)$")
MEM = re.compile(r"unmapped\s+(?P<op>Read|Write)(?P<sz>\d+)\s+@\s+0x[0-9A-Fa-f]+\s+"
                 r"at\s+PC\s+0x(?P<pc>[0-9A-Fa-f]+)")
HEX = re.compile(r"0x[0-9A-Fa-f]+")
NUM = re.compile(r"\b\d+\b")
LEVELS = ("Error", "Critical")
# housekeeping benigno del emulador: NO son bugs nuestros (stubs de servicios, saves
# que ya existen, certificados/relojes por defecto...). Se etiquetan como "ruido".
BENIGN = re.compile(r"already exists|using default|not init|ClCertA|Delay generator|"
                    r"MBoxInfo|Path not found|missing|stubbed|unimplemented", re.IGNORECASE)


def _relevancia(sub, pc, msg):
    """crash = error de memoria con PC (NUESTRO bug) · ruido = housekeeping benigno
    del emulador · otro = sin PC pero no es ruido conocido (revisar)."""
    if pc:
        return "crash"
    if sub.startswith("Service.") or BENIGN.search(msg):
        return "ruido"
    return "otro"


def _now():
    # Hora local: la lee una persona en logs/INFORME_ERRORES.md junto al emulador. Se marca
    # con la zona (astimezone) para que la marca sea inequívoca y no dependa de la máquina.
    return datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")


def _stamp(path):
    try:
        st = os.stat(path)
        return f"{st.st_size}:{int(st.st_mtime)}"
    except OSError:
        return None


def _classify(sub, msg):
    """Devuelve (firma, tipo, pc, mensaje_normalizado, relevancia)."""
    m = MEM.search(msg)
    if m:
        op, sz = m["op"], m["sz"]
        pc = "0x" + m["pc"].upper().rjust(8, "0")
        return (f"mem:{op}{sz}:{pc}", f"unmapped {op}{sz}", pc,
                f"unmapped {op}{sz} @ 0x<addr> at PC {pc}", "crash")
    # normaliza separadores de ruta (Azahar mezcla \ y /) + numeros/hex -> misma firma
    norm = NUM.sub("<n>", HEX.sub("0x<a>", msg.replace("\\", "/"))).strip()
    return (f"{sub}|{norm}"[:180], sub, None, norm, _relevancia(sub, None, norm))


def parse(path, levels=LEVELS):
    """Devuelve {firma: {tipo, pc, msg, veces}} para un log."""
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            data = fh.read()
    except FileNotFoundError:
        return out
    for ln in data.splitlines():
        m = LINE.match(ln)
        if not m or m["lvl"] not in levels:
            continue
        body = m["body"]
        lm = LOC.match(body)
        msg = lm["msg"] if lm else body
        sig, tipo, pc, norm, rel = _classify(m["sub"], msg)
        e = out.setdefault(sig, {"tipo": tipo, "pc": pc, "msg": norm, "rel": rel, "veces": 0})
        e["veces"] += 1
    return out


def merge(reg, found, build):
    """Funde lo hallado en el registro. Devuelve la lista de firmas NUEVAS."""
    errs = reg.setdefault("errores", {})
    now = _now()
    nuevas = []
    for sig, e in found.items():
        if sig in errs:
            r = errs[sig]
            r["veces"] += e["veces"]
            r["sesiones"] += 1
            r["ultima_vez"] = now
        else:
            st, nota = "abierto", ""
            if e["pc"] in KNOWN_PCS:
                st, nota = KNOWN_PCS[e["pc"]]
            errs[sig] = {"tipo": e["tipo"], "pc": e["pc"], "mensaje": e["msg"],
                         "rel": e["rel"], "primera_vez": now, "ultima_vez": now,
                         "veces": e["veces"], "sesiones": 1, "estado": st, "nota": nota}
            nuevas.append(sig)
        # reanota PC conocido aunque la firma ya existiera sin nota
        if e["pc"] in KNOWN_PCS and not errs[sig]["nota"]:
            errs[sig]["estado"], errs[sig]["nota"] = KNOWN_PCS[e["pc"]]
    reg.setdefault("sesiones", []).append({
        "fecha": now, "build": build or "?",
        "lineas_error": sum(e["veces"] for e in found.values()),
        "firmas": len(found), "firmas_nuevas": len(nuevas)})
    return nuevas


def _line(e):
    nota = f" — {e['nota']}" if e.get("nota") else ""
    return (f"- `{e['tipo']}` · PC `{e['pc'] or '-'}` · ×{e['veces']} · "
            f"{e['sesiones']} ses · [{e['estado']}]{nota}\n    - {e['mensaje']}")


def informe(reg, nuevas=()):
    errs = reg.get("errores", {})
    cerradas = ("resuelto", "conocido_no_arreglable")
    abiertos = {s: e for s, e in errs.items() if e["estado"] not in cerradas}
    by = lambda rel: sorted((e for e in abiertos.values() if e.get("rel") == rel),
                            key=lambda e: -e["veces"])
    crashes, otros, ruido = by("crash"), by("otro"), by("ruido")
    L = [f"# Informe de errores de runtime — {_now()}", "",
         (f"- Firmas totales **{len(errs)}** · abiertas **{len(abiertos)}** "
          f"(🎯 crash {len(crashes)} · ❓ otro {len(otros)} · ⚙️ ruido {len(ruido)}) · "
          f"sesiones **{len(reg.get('sesiones', []))}**")]

    nuevas_rel = [errs[s] for s in nuevas if errs[s].get("rel") in ("crash", "otro")]
    if nuevas_rel:
        L += ["", f"## 🆕 NUEVAS esta sesion ({len(nuevas_rel)}) — candidatas a mejorar"]
        L += [_line(e) for e in sorted(nuevas_rel, key=lambda e: -e["veces"])]

    L += ["", "## 🎯 Crashes (bugs nuestros — prioridad)"]
    L += [_line(e) for e in crashes] or ["- _(ninguno)_ ✅"]
    if otros:
        L += ["", "## ❓ Otros (revisar)"] + [_line(e) for e in otros]
    if ruido:
        L += ["", f"## ⚙️ Ruido del emulador (benigno, {len(ruido)}) — ignorar",
              "<details><summary>ver</summary>", ""]
        L += [_line(e) for e in ruido] + ["</details>"]
    cerr = [e for e in errs.values() if e["estado"] in cerradas]
    if cerr:
        L += ["", "## ✅ Conocidas (resueltas / no arreglables)"]
        L += [f"- `{e['tipo']}` · PC `{e['pc'] or '-'}` · [{e['estado']}] — {e['nota']}"
              for e in cerr]
    return "\n".join(L)


def cosechar(sesion=None, logdir=None, forzar=False, avisos=False, registro=None, informe_md=None):
    """Funde el log de Azahar en el registro persistente y escribe el informe.

    Misma lógica que ``harvest_log.py`` (retirado en la F2.4; la orden es ``ie123 registro``):
    con ``sesion`` solo se lee el log actual (no el ``.old``) y se marca la build. Devuelve
    ``{procesados, firmas, nuevas, registro, informe, texto}``.
    """
    import json

    registro = registro or REG
    informe_md = informe_md or INFORME
    logdir = logdir or LOGDIR
    os.makedirs(os.path.dirname(registro), exist_ok=True)
    reg = {}
    if os.path.exists(registro):
        with open(registro, encoding="utf-8") as f:
            reg = json.load(f)
    levels = LEVELS + ("Warning",) if avisos else LEVELS
    logs = [os.path.join(logdir, "azahar_log.txt")]
    if not sesion:
        logs.append(os.path.join(logdir, "azahar_log.old.txt"))
    procesado = reg.setdefault("_procesado", {})
    found, procesados = {}, []
    for lp in logs:
        st = _stamp(lp)
        if st is None or (not forzar and procesado.get(lp) == st):
            continue
        procesados.append(lp)
        procesado[lp] = st
        for sig, e in parse(lp, levels).items():
            if sig in found:
                found[sig]["veces"] += e["veces"]
            else:
                found[sig] = dict(e)
    if not procesados:
        return {"procesados": [], "firmas": 0, "nuevas": [], "registro": registro, "informe": None,
                "texto": informe(reg)}
    nuevas = merge(reg, found, sesion)
    with open(registro, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
    texto = informe(reg, nuevas)
    with open(informe_md, "w", encoding="utf-8") as f:
        f.write(texto)
    return {"procesados": procesados, "firmas": len(found), "nuevas": list(nuevas), "registro": registro,
            "informe": informe_md, "texto": texto}
