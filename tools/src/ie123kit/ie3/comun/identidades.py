"""Identidades JP→oficial para consumidores ``301D`` de un mismo evento.

Un texto japonés no es una identidad: puede repetirse en una escena y tener
traducciones oficiales distintas.  Este módulo resuelve únicamente una fuente
oficial por la instrucción que la consume y dos anclas de ejecución alrededor
de ella.  No mira offsets entre idiomas ni escoge por orden de CSV.
"""

from collections.abc import Iterable

from ie123kit.ie3.comun.referencias import Referencia


def _firma(ref: Referencia) -> tuple[int, tuple[int, ...]]:
    """Parte del consumidor que debe conservarse entre ediciones."""
    ins = ref.instruccion
    return ins.opcode, ins.tipos


def _por_instruccion(refs: Iterable[Referencia]) -> dict[int, tuple[int, Referencia]]:
    result = {}
    for index, ref in enumerate(refs):
        ident = ref.instruccion.ident
        if ident in result:
            raise ValueError(f"consumidor 301D duplicado para instrucción {ident}")
        result[ident] = index, ref
    return result


def resolver_overrides_por_identidad(
    event_id: int,
    japonesas: Iterable[Referencia],
    oficiales: Iterable[Referencia],
    solicitados: Iterable[int] | None = None,
) -> dict[tuple[int, int], dict]:
    """Devuelve ``(evento, offset_jp) -> procedencia ES`` verificable.

    El candidato debe ser la *misma instrucción* ``301D`` en el mismo evento,
    conservar opcode y tipos de argumentos y quedar entre dos consumidores
    comunes (uno anterior y otro posterior) con la misma firma.  Las anclas
    prueban el contexto de ejecución aun si el texto JP y los IDs de cadena se
    repiten.  Si falta cualquier condición, se omite en vez de adivinar.

    ``solicitados`` limita la emisión a cabezas JP concretas; es útil para que
    una auditoría trate solo filas contradictorias sin codificar casos aquí.
    """
    jp = tuple(japonesas)
    es = tuple(oficiales)
    jp_by_id, es_by_id = _por_instruccion(jp), _por_instruccion(es)
    wanted = None if solicitados is None else set(solicitados)
    if wanted is not None and wanted - {r.inicio for r in jp}:
        raise ValueError("offset JP solicitado sin consumidor 301D")

    # Solo los consumidores que pueden anclar la secuencia a ambos lados.
    comunes = {
        ident
        for ident, (_jp_index, jp_ref) in jp_by_id.items()
        if ident in es_by_id and _firma(jp_ref) == _firma(es_by_id[ident][1])
    }
    result = {}
    for jp_index, jp_ref in enumerate(jp):
        if wanted is not None and jp_ref.inicio not in wanted:
            continue
        ident = jp_ref.instruccion.ident
        candidate = es_by_id.get(ident)
        if candidate is None or _firma(jp_ref) != _firma(candidate[1]):
            continue
        es_index, es_ref = candidate
        # La cercanía se calcula en orden real del bytecode, no por ID/offset.
        left = next((r.instruccion.ident for r in reversed(jp[:jp_index]) if r.instruccion.ident in comunes), None)
        right = next((r.instruccion.ident for r in jp[jp_index + 1 :] if r.instruccion.ident in comunes), None)
        if left is None or right is None:
            continue
        left_es_index, _ = es_by_id[left]
        right_es_index, _ = es_by_id[right]
        if not (left_es_index < es_index < right_es_index):
            continue
        result[(event_id, jp_ref.inicio)] = {
            "source": {"event_id": event_id, "offset": es_ref.inicio},
            "identity": {
                "instruction": ident,
                "opcode": f"{jp_ref.instruccion.opcode:04X}",
                "argument_types": list(jp_ref.instruccion.tipos),
            },
            "anchors": {
                "before_instruction": left,
                "after_instruction": right,
                "method": "same_event_301D_instruction_with_bracketing_consumers",
            },
        }
    return result
