#!/usr/bin/env python3
"""Reinsercion SSD con el formato CORRECTO (descubierto via Tiniifan/SceneScriptData).

CLAVE: el bytecode referencia el texto por INDICE de entrada (estable), NO por offset de
byte. Cada instruccion lleva el TIPO de cada arg en 4 bits (String=0x3). Asi que al traducir:
  - NO se reubica nada (los indices no cambian) -> adios offset-fixup (que CORROMPIA indices
    = vacio/crash/Read32, ❌#11/#12/#13).
  - El texto crece LIBRE (los diálogos se traducen completos, sin truncar).
  - Las lecturas furigana se VACIAN (sin eliminarlas -> el indice no se desplaza) -> sin
    japones, sin desbalance.
  - El bytecode queda INTACTO.

Layout (ssdReader.ts de SceneScriptData), little-endian:
  Header 0x20: magic 'SSD\\0', version u32, size u32, instCount i16, textCount i16,
               instSize u32, textSize u32, pad0 u32, pad1 u32.
  Instruccion: id i16, size i16, opcode u16, argsCount u8, unk u8,
               [4*ceil(argsCount/8) bytes de nibbles de tipo], [argsCount * u32 args].
  Texto: secuencia de entradas (chunks NUL-delimitados): byte-id (1B>=0x80) + contenido.
"""
import struct, re as _re, sys, os
from ie123kit._legado import reinsert as R
from ie123kit.nucleo.texto.nds_latin import decode_cadena as _decode_string


def _text_start(dec):
    """Offset donde acaban las instrucciones (= inicio del texto)."""
    instCount = struct.unpack_from("<h", dec, 12)[0]
    p = 0x20
    for _ in range(instCount):
        p += struct.unpack_from("<h", dec, p + 2)[0]
    return p


def reencode_ssd(dec, trans, system=False, blank_readings=True, dbg_eid=None, gtrans=None, eid=None):
    """Devuelve (nuevo_dec, n_traducidas). Bytecode intacto; solo reescribe el texto.

    gtrans: mapa GLOBAL {japones: es} de TODAS las traducciones (cualquier evento). Si la
    busqueda por-evento (trans) falla, se usa el global -> recupera las lineas cuyo mismo
    texto japones esta traducido en OTRO evento (el emparejamiento por-evento las perdia:
    ~5575 lineas, +22% de cobertura). Solo lectura.

    system=True (eventos de SISTEMA/MENU/INTRO, eid>=90000000): conserva los marcadores
    furigana en el diálogo y lo deja a MISMO TAMAÑO (INPLACE). Quitar los marcadores en
    estos eventos cuelga el motor (FURIGANA_LECCIONES ❌#1, runtime, no de datos -> persiste
    aun con el formato correcto). system=False (gameplay): texto COMPLETO (crece libre)."""
    if dec[:4] != b"SSD\x00":
        return dec, 0
    ts = _text_start(dec)
    code = dec[0x20:ts]                       # bytecode INTACTO (indices estables)
    chunks = dec[ts:].split(b"\x00")
    out, n = [], 0
    # RE-PAGINAR el furigana de sistema (recupera lineas traducidas con paginas !=) SALVO en la
    # APERTURA/crear-partida (eid 90000000..92010249): ahi se mantiene byte-identico a la build
    # que SI crea partida (cualquier cambio de mas en la apertura la congela, ❌#1). Willy
    # (92010250) en adelante: re-paginar.
    _allow_repag = not (eid is not None and 90000000 <= eid <= 92010249)
    pending = 0          # nº de lecturas a VACIAR tras una linea TRADUCIDA (strip): 1 por marcador.
    #   CLAVE (lección ca9d078 / bug#2): solo se vacian las lecturas de lineas TRADUCIDAS (sus
    #   marcadores se quitan -> quedarian huerfanas). Las de lineas NO traducidas (que conservan
    #   sus marcadores en japones) se CONSERVAN -> el balance marcador<->lectura NO se rompe
    #   (vaciar TODO descuadra: marcador sin lectura -> desync -> bloqueo de controles del NPC).
    for c in chunks:
        # 1) LECTURA furigana: vaciar SOLO si pertenece a una linea recien traducida (pending>0).
        if R._is_reading(c):
            if blank_readings and pending > 0:
                # VACIAR a MISMO TAMAÑO (espacios ancho completo 0x8140), NO encoger (❌#12).
                body = c[2:]
                fill = b"\x81\x40" * (len(body) // 2) + (b"\x20" * (len(body) % 2))
                out.append(bytes(c[:2]) + fill); pending -= 1
            else:
                out.append(c)              # lectura de linea NO traducida (o NO_BLANK): INTACTA
                #   -> conserva su marcador+lectura japoneses, balanceado, sin tocar la ruby.
            continue
        s = _decode_string(c, "sjis") if len(c) >= 2 else ""
        # 2) DIALOGO traducible
        if len(c) >= 3 and c[0] in (1, 2, 4) and R.looks_like_dialogue(s):
            es = trans.get(s)                          # 1) traduccion POR-EVENTO (estructura exacta)
            if not es and gtrans and not system:       # 2) fallback GLOBAL: SOLO en gameplay.
                es = gtrans.get(s)                      #   En intro/sistema (system=True) el global
                #   mete una traduccion de OTRO evento con estructura de pagina/marcadores distinta
                #   -> el INPLACE se descuadra -> CONGELA el crear-partida. v23/v25 (que SI creaba
                #   partida) usaba solo por-evento en el intro. Por eso el global va atado a !system.
            nmarks = len(R._MK.findall(c))            # marcadores de ESTA linea original (= sus lecturas)
            if dbg_eid is not None:
                # DEBUG: antepone [eid] a CADA dialogo (texto completo). Los que petan la ruby
                # crashean igual, pero muestran su [id] antes -> identifica el evento a proteger.
                body = _re.sub(r"%[1-9]F", "", es) if es else ""
                out.append(bytes(c[:2]) + R.es_encode("[%d]%s" % (dbg_eid, body), 1 << 20)); n += 1
                if not system:
                    pending += nmarks
                continue
            if es:
                es = _re.sub(r"%[1-9]F", "", es)          # quitar marcadores del ES
                if system:
                    # SISTEMA/INTRO: a MISMO TAMAÑO (no crecer -> evita ❌#9). Las lineas CON
                    # furigana se traducen INPLACE conservando los marcadores (❌#1: quitarlos
                    # cuelga el crear-partida) + N espacios ancho completo por marcador (v25,
                    # _furigana_body_bytes; si la estructura de paginas no casa -> None -> japones).
                    # Las lecturas se CONSERVAN (system -> blank_readings=False) -> ruby OK.
                    if R._MK.search(c):
                        body = R._furigana_body_bytes(c[2:], es, len(c) - 2, allow_repaginate=_allow_repag)
                        if body is not None:
                            out.append(bytes(c[:2]) + body); n += 1
                        else:
                            out.append(c)                  # no cabe la estructura -> japones
                    else:
                        b = R.es_encode(es, len(c) - 2)    # plana -> INPLACE mismo tamaño
                        out.append(bytes(c[:2]) + b + b" " * max(0, len(c) - 2 - len(b))); n += 1
                else:
                    # GAMEPLAY: texto COMPLETO, crece libre, sin marcadores. Marca para vaciar
                    # las N lecturas de ESTA linea (sus marcadores se han quitado).
                    out.append(bytes(c[:2]) + R.es_encode(es, 1 << 20)); n += 1
                    pending += nmarks
            else:
                out.append(c)                              # sin traduccion -> japones (marcador+lectura intactos)
        else:
            out.append(c)                                  # byte-id / cue / texto-display: intacto
    new_text = b"\x00".join(out)
    nd = bytearray(dec[:0x20]) + code + new_text
    struct.pack_into("<I", nd, 8, len(nd))                 # size total
    struct.pack_into("<I", nd, 20, len(new_text))          # textSize
    return bytes(nd), n


def _validate(dec):
    """Comprueba que el SSD resultante es estructuralmente valido (instrucciones parsean,
    nº de entradas de texto intacto)."""
    if dec[:4] != b"SSD\x00":
        return False, "magic"
    instCount, textCount = struct.unpack_from("<hh", dec, 12)
    p = 0x20
    nstr = 0
    for i in range(instCount):
        if p + 8 > len(dec):
            return False, f"inst {i} fuera"
        size, opcode, argc = struct.unpack_from("<hHB", dec, p + 2)
        exp = 8 + 4 * ((argc + 7) // 8) + 4 * argc
        if size != exp:
            return False, f"inst {i} size {size}!={exp}"
        for a in range(argc):
            byte = dec[p + 8 + (a // 2)]
            t = (byte >> 4) if (a % 2) else (byte & 0xF)
            if t == 3:
                nstr += 1
        p += size
    return True, f"OK {instCount} instr, {nstr} String args (textCount={textCount})"


def main():
    if "--legado-lo-se" not in sys.argv:
        sys.stderr.write("ERROR: ssd_reinsert está en cuarentena (obsolete_dangerous; ver docs/FURIGANA_LECCIONES.md). Sustituto: ie123kit.nucleo.eventos.ssd (replace). Para ejecutarlo igualmente añade --legado-lo-se.\n")
        return 2
    sys.argv.remove("--legado-lo-se")
    from ie123kit.nucleo.contenedores.fa import FaArchive
    from ie123kit.nucleo.eventos.packnum import parse_index
    from ie123kit.nucleo.compresion.lz10 import decompress
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    a = FaArchive(os.path.join(R.REPO, "work", "shared", "base_3ds", "romfs", "archive.fa")); d = a.d
    def grab(ext):
        for pth, o, s in a.entries:
            if pth.endswith("inazuma1/data_iz/script/eve." + ext):
                return bytes(d[o:o + s])
    opkb = grab("pkb"); oidx = {e: (o, s) for e, o, s in parse_index(grab("pkh"))}
    trans = R.load_translations("game1")
    eid = 92062100
    o, s = oidx[eid]; dec = decompress(opkb[o:o + s])
    nd, n = reencode_ssd(dec, trans.get(eid, {}))
    ok, msg = _validate(nd)
    print(f"evento {eid}: {n} lineas traducidas | tamano {len(dec)}->{len(nd)} | valido={ok} ({msg})")
    # mostrar los dialogos resultantes
    ts = _text_start(nd)
    for c in nd[ts:].split(b"\x00"):
        ss = _decode_string(c, "sjis") if len(c) >= 2 else ""
        if len(c) >= 3 and c[0] in (1, 2, 4) and (R.looks_like_dialogue(ss) or any("a" <= ch.lower() <= "z" for ch in ss)):
            print(f"   {ss[2:60]!r}")


if __name__ == "__main__":
    raise SystemExit(main())
