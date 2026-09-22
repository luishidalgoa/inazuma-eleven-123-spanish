from ie123kit.ie3.comun.identidades import resolver_overrides_por_identidad
from ie123kit.ie3.comun.referencias import Instruccion, Referencia


def ref(ident, start, tipos=(3,), opcode=0x301D):
    ins = Instruccion(ident, opcode, 0, tipos, tuple(range(len(tipos))), tuple(range(len(tipos))))
    return Referencia(ins, 0, start, 8, (0,))


def test_resolves_by_same_instruction_and_bracketing_context_not_text_or_offset():
    jp = [ref(1200, 40), ref(1216, 80), ref(1232, 120), ref(1239, 160)]
    es = [ref(1200, 400), ref(1216, 480), ref(1232, 748), ref(1239, 840)]
    out = resolver_overrides_por_identidad(36134726, jp, es, [120])
    assert out == {
        (36134726, 120): {
            "source": {"event_id": 36134726, "offset": 748},
            "identity": {"instruction": 1232, "opcode": "301D", "argument_types": [3]},
            "anchors": {
                "before_instruction": 1216,
                "after_instruction": 1239,
                "method": "same_event_301D_instruction_with_bracketing_consumers",
            },
        }
    }


def test_rejects_same_instruction_without_two_matching_context_anchors():
    jp = [ref(1225, 80, (3, 4, 3)), ref(1232, 120), ref(1239, 160)]
    es = [ref(1225, 480, (3, 4)), ref(1232, 748), ref(1239, 840)]
    # El ancla izquierda 1225 cambia de firma; sin otra anterior común, cerrar.
    assert resolver_overrides_por_identidad(7, jp, es, [120]) == {}


def test_rejects_changed_target_signature_and_unknown_requested_offset():
    jp = [ref(1, 10), ref(2, 20), ref(3, 30)]
    es = [ref(1, 110), ref(2, 120, (3, 4)), ref(3, 130)]
    assert resolver_overrides_por_identidad(7, jp, es, [20]) == {}
    try:
        resolver_overrides_por_identidad(7, jp, es, [99])
    except ValueError as error:
        assert "sin consumidor" in str(error)
    else:
        raise AssertionError("debía rechazar un offset no referenciado")
