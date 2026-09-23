#!/usr/bin/env python3
"""Pone los NOMBRES oficiales europeos del roster (Mark Evans, Axel Blaze, Nathan Swift...)
en el unitbase.dat del 3DS, tomandolos del unitbase.dat del DS (lanzamiento ES oficial).

unitbase.dat = tabla de registros FIJOS de 96 bytes (cabecera 0..95, registros desde 96).
Campos de nombre por registro (verificado):
  +0  (16B) nombre completo  (3DS: '円堂　守'      | DS: 'Mark Evans')   -> roster/perfil
  +16 (16B) lectura corta    (3DS: 'えんどう'       | DS: vacio)          -> RECUADRO AZUL del hablante
  +32 (16B) nombre dado      (3DS: 'えんどう　まもる' | DS: 'Mark')          -> nombre corto europeo
  +48..96   stats binarios (NO se tocan).
El motor JAPONES del 3DS pinta en el recuadro azul el campo +16; el DS (motor europeo) usa +32.
Por eso ponemos el nombre DADO del DS (+32) en el +16 del 3DS -> el recuadro muestra 'Mark'.

El .dat del DS tiene MISMO tamano (230400B) y misma estructura -> mapeo por posicion de registro.
Reemplazo IN-PLACE (mismo tamano): no hay que mover offsets del archive.fa.
"""
import os, sys
from ie123kit.nucleo.texto.nds_latin import DS_TABLE, decode_ds
from ie123kit._legado import reinsert as R

REC = 96
HEADER = 96
FIELD = 16

# game -> (carpeta DS, sufijo del unitbase.dat 3DS dentro de archive.fa)
GAMES = {
    "game1": ("ie1/fuentes/nds_es", "inazuma1/data_iz/logic/unitbase.dat"),
    "game2": ("ie2/tormenta_de_fuego/fuentes/nds_es", "inazuma2/data_iz/logic/unitbase.dat"),
}


def _field(ds_bytes, size):
    """Decodifica un campo de nombre del DS y lo re-codifica para la fuente del 3DS
    (acentos via es_encode/griego). SIEMPRE reserva el terminador NUL: codifica con
    presupuesto size-1 y rellena a 'size'. Asi un nombre largo (>=size) nunca se queda
    SIN NUL (eso hacia que el motor leyera el campo siguiente como continuacion del
    nombre; 98 nombres de +0 llenaban 16B exactos). Devuelve None si el campo va vacio."""
    raw = ds_bytes.split(b"\x00")[0]
    if not raw:
        return None
    s = decode_ds(raw)
    e = R.es_encode(s, size - 1)                    # -1 = reservar el terminador
    return e + b"\x00" * (size - len(e))


def patch_unitbase(orig, ds):
    """Devuelve un unitbase.dat 3DS (mismo tamano) con el NOMBRE del recuadro azul en
    europeo. CONSERVADOR: solo se toca el campo +16 (lectura corta = lo que el motor
    JAPONES pinta en el recuadro azul del hablante). Se DEJAN en japones:
      - +0  (nombre completo kanji '円堂　守')   -> el motor lo parte por el espacio de
            ancho completo (0x8140) para separar apellido/nombre; escribir ASCII sin ese
            separador descuadra el parse.
      - +32 (lectura completa 'えんどう　まもる') -> idem, lleva separador 0x8140.
    Escribir esos dos campos era la causa probable del crash 'unmapped Read8' al hablar
    con ciertos personajes (Kabeyama): el motor leia mas alla del separador inexistente
    y usaba bytes ASCII como puntero. El +16 es un token UNICO (sin separador) -> seguro.
    El recuadro azul es justo lo que el usuario pide. Ampliar a +0/+32 solo tras
    confirmar en emulador que no crashea (ver issue #16)."""
    assert len(orig) == len(ds), f"tamanos distintos {len(orig)} != {len(ds)}"
    out = bytearray(orig)
    nrec = (len(orig) - HEADER) // REC
    changed = 0
    for n in range(nrec):
        rec = HEADER + n * REC
        given = ds[rec + 2 * FIELD:rec + 3 * FIELD]   # DS +32 = nombre dado ('Mark')
        eg = _field(given, FIELD)
        # solo si el original +16 era un nombre (lectura) y hay nombre europeo
        if eg and orig[rec + FIELD:rec + 2 * FIELD].strip(b"\x00"):
            out[rec + FIELD:rec + 2 * FIELD] = eg     # recuadro azul <- nombre dado europeo
            changed += 1
    return bytes(out), changed


def main():
    if "--legado-lo-se" not in sys.argv:
        sys.stderr.write("ERROR: ds_roster está en cuarentena (obsolete_dangerous; ver docs/FURIGANA_LECCIONES.md). Sustituto: work/ie1/capas/historial/nombres/v36_nombres (regla +16/NUL, #16). Para ejecutarlo igualmente añade --legado-lo-se.\n")
        return 2
    sys.argv.remove("--legado-lo-se")
    sys.stdout.reconfigure(encoding="utf-8")
    from ie123kit.nucleo.contenedores.fa import FaArchive
    arc = FaArchive(os.path.join(R.REPO, "work", "shared", "base_3ds", "romfs", "archive.fa"))
    data = arc.d
    for game, (dsdir, suf) in GAMES.items():
        if game not in sys.argv and len(sys.argv) > 1:
            continue
        off = nxt = None
        for p, o, s in arc.entries:
            if p.endswith(suf):
                off, sz = o, s
        orig = bytes(data[off:off + sz])
        ds = open(os.path.join(R.REPO, "work", dsdir, "data_iz", "logic", "sp", "unitbase.dat"), "rb").read()
        patched, n = patch_unitbase(orig, ds)
        outdir = os.path.join(R.REPO, "work", "roster")
        os.makedirs(outdir, exist_ok=True)
        open(os.path.join(outdir, f"{game}_unitbase.dat"), "wb").write(patched)
        print(f"{game}: {n} registros con nombre europeo -> work/roster/{game}_unitbase.dat")


if __name__ == "__main__":
    raise SystemExit(main())
