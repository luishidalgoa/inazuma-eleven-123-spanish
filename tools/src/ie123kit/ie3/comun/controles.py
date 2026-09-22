"""Cotas del consumidor 4B424, sin modificar encoder ni tipografía aprobados."""

import math
import re

from ie123kit.ie3.comun.maqueta import maquetar_una_caja
from ie123kit.ie3.comun.referencias import instrucciones
from ie123kit.ie3.comun.reinsert import MARCA_FURIGANA
from ie123kit.ie3.comun.tipografia import AVANCES_ESPECIALES_FONT12, AVANCES_FONT12, avance_font12
from ie123kit.nucleo.texto.sjis_portador import es_encode

TOKEN = re.compile(r"%(?:[0-9]+)?[A-Za-z]")


def cota_pool(pool):
    """Domina todas las cadenas, no un ejemplo: bytes, caracteres y tinta."""
    if not pool or any(row["bytes"] > 31 or "\x00" in row["text"] for row in pool):
        raise ValueError("pool %s no acotado por el temporal de 32 bytes")
    return {"max_bytes": max(row["bytes"] for row in pool),
            # El número de bytes post-encoder domina el de glifos SJIS,
            # también si una normalización aprobada expande … a tres puntos.
            "max_chars": max(max(len(row["text"]), row["bytes"]) for row in pool),
            "max_ink": max(sum(avance_font12(c) if c in AVANCES_FONT12 or c in AVANCES_ESPECIALES_FONT12
                               else 14 for c in row["text"]) for row in pool),
            "entries": len(pool)}


def _aplicar_cota(result, spanish, sizes, token, bound, evidence):
    # Una palabra de igual máximo de caracteres y tinta >= máximo del pool.
    # No cambia la política de wrapping: se usa maquetar_una_caja tal cual.
    count = bound["max_chars"]
    wide = max(0, math.ceil((bound["max_ink"] - 3 * count) / 11))
    if wide > count:
        raise ValueError("cota de tinta fuera del alfabeto de reserva")
    marker = "W" * wide + "i" * (count - wide)
    if not marker or marker in spanish:
        return
    layout = maquetar_una_caja(spanish.replace(token, marker))
    formatted = None if layout is None else layout.replace(marker, token)
    result["blockers"].remove("estructura_controles_argumentos_pendiente")
    if formatted is None or token not in formatted:
        if "layout_paginacion" not in result["blockers"]:
            result["blockers"].append("layout_paginacion")
    elif not result["unsupported"]:
        payload = es_encode(formatted, 1 << 30)
        needed = (len(payload) + 8) & ~3
        span = max(sizes[0], needed) + sum(sizes[1:])
        expanded = len(payload) - len(token) + bound["max_bytes"] + 1
        result.update(formatted=formatted, encoded_hex=payload.hex(),
                      bytes_needed_record=needed, new_group_size=span)
        for condition, reason in ((needed > 252, "limite_real_registro_u8"),
                                  (span > 1024, "limite_real_grupo_1024"),
                                  (expanded > 512, "limite_real_buffer_expandido")):
            if condition and reason not in result["blockers"]:
                result["blockers"].append(reason)
        evidence.update(bound=bound, max_substitution_bytes=bound["max_bytes"],
                        expanded_bytes_including_nul=expanded, max_glyphs=count)


def compilar_contexto(japanese, spanish, sizes, ref, ssd, records, pools=None):
    """Tipos/orden de argumentos y expansión, no longitud típica.

    %d recibe int32: hasta 11 caracteres, convertidos a SJIS de dos bytes.
    %s dinámico sigue cerrado hasta demostrar terminación de TODOS los caminos
    del productor (incluidas cachés/guardados), no solo los nombres habituales.
    """
    from ie123kit.ie3.comun.emision import compilar

    result = compilar(japanese, spanish, sizes)
    if "estructura_controles_argumentos_pendiente" not in result["blockers"]:
        return result
    jt, st = TOKEN.findall(japanese), TOKEN.findall(spanish)
    remaining = MARCA_FURIGANA.sub("", japanese)
    evidence = {"jp_tokens": jt, "es_tokens": st, "argument_types": list(ref.instruccion.tipos)}
    if st == ["%d"] and spanish.count("%") == 1 and remaining.count("%") == 1 and TOKEN.findall(remaining) == ["%d"]:
        # Ruby anterior consumiría otro argumento: no reordenar ni saltarlo.
        if jt[0] == "%d" and len(ref.instruccion.tipos) > 1 and ref.instruccion.tipos[1] in (1, 2, 5):
            evidence["proof"] = "int32_signed_fullwidth_4B540_4B5DC"
            _aplicar_cota(result, spanish, sizes, "%d",
                          {"max_bytes": 22, "max_chars": 11, "max_ink": 154}, evidence)
    elif st == ["%s"] and spanish.count("%") == 1 and jt and jt[0] == "%s" and remaining.count("%") == 1:
        ins = ref.instruccion
        if len(ins.tipos) > 1 and ins.tipos[1] == 4:
            producers = {i.ident: i for i in instrucciones(ssd)}
            producer = producers.get(ins.valores[1])
            if producer:
                evidence.update(producer_opcode=f"{producer.opcode:04X}", producer_instruction=producer.ident,
                                pending="demostrar NUL y cota <=31 en todas las rutas del productor, incluidas cachés")
                if producer.opcode == 0x4099 and pools and "item" in pools:
                    evidence.pop("pending")
                    evidence["proof"] = "4099_47F24_178284_17DA4C_item_pool_all_entries"
                    _aplicar_cota(result, spanish, sizes, "%s", pools["item"], evidence)
    else:
        evidence["pending"] = "correspondencia de controles/orden no demostrada; no eliminar argumentos"
    result["control_evidence"] = evidence
    return result
