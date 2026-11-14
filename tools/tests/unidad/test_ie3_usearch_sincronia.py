"""IE3: usearch.dat coherente con el nombre corto de unitbase.dat (datos sintéticos, sin ROM)."""
import struct

import pytest

from ie123kit.ie3.comun import registro_usearch as RU
from ie123kit.ie3.comun import usearch_sincronia as S

E_LOGIC = S.ESQUEMAS["ie3.inazuma3"]


def _us(nombre: bytes, uid: int, *, visible: bool = True) -> bytes:
    r = bytearray(RU.R_USEARCH)
    r[0:16] = nombre.ljust(16, b"\0")
    r[16:32] = "あ".encode("cp932").ljust(16, b"\0")  # clave kana
    struct.pack_into("<H", r, 0x24, uid)
    r[0x2A] = 1 if uid else 0
    r[0x2B] = 2 if visible else 0
    return bytes(r)


def _ub(corto: bytes, uid: int) -> bytes:
    r = bytearray(RU.R_UNITBASE)
    r[RU.CORTO:RU.CORTO + 16] = corto.ljust(16, b"\0")
    struct.pack_into("<H", r, RU.ID, uid)
    return bytes(r)


def _cuenta(h, gravedad="error"):
    return sorted({x.codigo for x in h if x.gravedad == gravedad})


def test_ya_coherente_y_ordenado_no_cambia_ni_un_byte():
    # usearch con el corto previo (largo) y unitbase ya acortado por nombres_cortos_6: es lo instalado
    us = _us(b"Abdulla", 2) + _us(b"Beta", 3) + _us(b"Zeta", 1) + _us(b"", 0)
    ub = _ub(b"Zeta", 1) + _ub(b"Abdul.", 2) + _ub(b"Beta", 3)
    nuevo, inf = S.sincronizar(E_LOGIC, us, ub)
    assert nuevo == us  # ni reescribe ni reordena
    assert (inf.iguales, inf.acortados, inf.reescritos, inf.sin_id, inf.posiciones_movidas) == (2, 1, 0, 1, 0)
    assert _cuenta(S.verificar(E_LOGIC, us, ub)) == []


def test_el_orden_incorrecto_es_error_y_el_hook_reordena_aunque_no_reescriba_nada():
    # caso «Sue»: el nombre ya es coherente con unitbase (una capa lo cambió in situ) pero está en la zona equivocada
    us = _us(b"Zeta", 1) + _us(b"Abdulla", 2) + _us(b"Beta", 3) + _us(b"", 0)
    ub = _ub(b"Zeta", 1) + _ub(b"Abdul.", 2) + _ub(b"Beta", 3)
    h = S.verificar(E_LOGIC, us, ub)
    assert _cuenta(h) == ["USEARCH_ORDEN"] and _cuenta(h, "aviso") == []
    nuevo, inf = S.sincronizar(E_LOGIC, us, ub)
    assert inf.reescritos == 0 and inf.reordenado and inf.posiciones_movidas == 3
    assert [nuevo[k * 44:k * 44 + 16].rstrip(b"\0") for k in range(3)] == [b"Abdulla", b"Beta", b"Zeta"]
    assert _cuenta(S.verificar(E_LOGIC, nuevo, ub)) == []
    assert S.sincronizar(E_LOGIC, nuevo, ub)[0] == nuevo  # idempotente


def test_mover_un_registro_conserva_el_resto_de_la_secuencia():
    """Único cambio de IE3 sobre lo instalado: un registro renombrado después de ordenar (Hartland -> Sue)."""
    nombres = [b"Abbey", b"Ben", b"Hartland", b"Mark", b"Nathan", b"Zeta"]
    ub = b"".join(_ub(n, i + 1) for i, n in enumerate(nombres[:2] + [b"Sue"] + nombres[3:]))
    us = b"".join(_us(n, i + 1) for i, n in enumerate(nombres))  # el hook ya los había ordenado con «Hartland»
    nuevo, inf = S.sincronizar(E_LOGIC, us, ub)
    assert inf.reescritos == 1 and inf.reordenado
    ids = lambda datos: [struct.unpack_from("<H", datos, k * 44 + 0x24)[0] for k in range(6)]
    assert sorted(ids(nuevo)) == sorted(ids(us))  # mismos registros
    sin_sue = [i for i in ids(nuevo) if i != 3]
    assert sin_sue == [i for i in ids(us) if i != 3]  # el resto, en la misma secuencia
    assert ids(nuevo).index(3) > ids(us).index(3)  # Sue baja a la zona S
    assert inf.mayor_desplazamiento == {"id": 3, "nombre": "Sue", "de": 2, "a": 4}


def test_nombre_nuevo_en_unitbase_se_copia_y_se_reordena():
    us = _us(b"Alfa", 1) + _us(b"Beta", 2) + _us(b"Gama", 3)
    ub = _ub(b"Alfa", 1) + _ub(b"Zulu", 2) + _ub(b"Gama", 3)  # una capa renombra el jugador 2
    assert _cuenta(S.verificar(E_LOGIC, us, ub)) == ["USEARCH_DESINCRONIZADO"]
    nuevo, inf = S.sincronizar(E_LOGIC, us, ub)
    assert inf.reescritos == 1 and inf.reordenado
    assert [nuevo[k * 44:k * 44 + 16].rstrip(b"\0") for k in range(3)] == [b"Alfa", b"Gama", b"Zulu"]
    assert _cuenta(S.verificar(E_LOGIC, nuevo, ub)) == []
    assert S.sincronizar(E_LOGIC, nuevo, ub)[0] == nuevo  # idempotente


def test_solo_cambia_el_nombre_y_lo_reordenado_conserva_los_registros_enteros():
    us = _us(b"Alfa", 1) + _us(b"Beta", 2)
    ub = _ub(b"Alfa", 1) + _ub(b"Bea", 2)
    nuevo, _ = S.sincronizar(E_LOGIC, us, ub)
    antes = {struct.unpack_from("<H", us, k * 44 + 0x24)[0]: us[k * 44 + 16:(k + 1) * 44] for k in range(2)}
    despues = {struct.unpack_from("<H", nuevo, k * 44 + 0x24)[0]: nuevo[k * 44 + 16:(k + 1) * 44] for k in range(2)}
    assert antes == despues  # clave kana, id, flags: intactos


def test_equivale_a_nombres_mas_ordenar_de_album_usearch():
    # Estado «japonés» (nombres kana en +0x00 y en el unitbase japonés) y unitbase español previo al acortado
    nombres = [b"Mark", b"Axel", b"\x83\xa6lvaro", b"Jude", b"Hartland", b"Abdulla", b"Nathan"]
    us_jp = b"".join(_us("ア".encode("cp932") + bytes([0x40 + i]), i + 1) for i in range(len(nombres)))
    us_jp += _us(b"", 0) + _us(b"\x81\x48\x81\x48", 99, visible=False)
    ub_jp = b"".join(_ub("ア".encode("cp932") + bytes([0x40 + i]), i + 1) for i in range(len(nombres)))
    ub_jp += _ub(b"", 0) + _ub("？？".encode("cp932"), 99)
    ub_es = b"".join(_ub(n, i + 1) for i, n in enumerate(nombres)) + _ub(b"", 0) + _ub("？？".encode("cp932"), 99)
    esperado_nombres, _ = RU.nombres(us_jp, ub_jp, ub_es)
    esperado = RU.ordenar(us_jp, esperado_nombres)
    obtenido, inf = S.sincronizar(E_LOGIC, us_jp, ub_es)
    assert obtenido == esperado
    assert (inf.reescritos, inf.iguales) == (len(nombres), 1)  # los siete jugadores; el «？？» ya era coherente
    # y partiendo del resultado ya no hay nada más que hacer
    assert S.sincronizar(E_LOGIC, obtenido, ub_es)[0] == obtenido


def test_ex_binder_usa_su_regla_de_orden():
    # nombre NO visible con inicial en portador: ordenable para registro_usearch, no para lista_registro_latina
    us = _us(b"Zeta", 1) + _us(b"\x83\xa6lvaro", 2, visible=False) + _us(b"Beta", 3)

    def nombres(datos):
        return [datos[k * 44:k * 44 + 16].rstrip(b"\0") for k in range(3)]

    assert nombres(S.ordenar(us, "logic")) == [b"\x83\xa6lvaro", b"Beta", b"Zeta"]
    assert nombres(S.ordenar(us, "ex_binder")) == [b"Beta", b"\x83\xa6lvaro", b"Zeta"]
    with pytest.raises(ValueError):
        S.ordenar(us, "otro")


def test_verificar_huerfanos_tamanos_y_byte15():
    us = _us(b"Alfa", 9)
    ub = _ub(b"Alfa", 1)
    assert _cuenta(S.verificar(E_LOGIC, us, ub)) == ["USEARCH_ID_HUERFANO"]
    assert _cuenta(S.verificar(E_LOGIC, us[:-1], ub)) == ["USEARCH_TAMANO"]
    assert _cuenta(S.verificar(E_LOGIC, us, ub[:-1])) == ["UNITBASE_TAMANO"]
    marca = bytearray(_us(b"Alfa", 1))
    marca[15] = 0x41
    assert _cuenta(S.verificar(E_LOGIC, bytes(marca), ub), "aviso") == ["USEARCH_BYTE15"]
    assert S.contar(S.verificar(E_LOGIC, bytes(marca), ub))["aviso:USEARCH_BYTE15"] == 1


# ------------------------------------------------------------------ renombrado que coincide con el acortado


def test_recorte_legitimo_de_nombres_cortos_6_sigue_siendo_coherente_con_la_base():
    """Con la base conocida, acortar el corto de la base (lo que hace nombres_cortos_6) no se reescribe."""
    us = _us(b"Abdulla", 2) + _us(b"Beta", 3)
    base = _ub(b"Abdulla", 2) + _ub(b"Beta", 3)
    ub = _ub(b"Abdul.", 2) + _ub(b"Beta", 3)
    nuevo, inf = S.sincronizar(E_LOGIC, us, ub, base_unitbase=base)
    assert nuevo == us and (inf.acortados, inf.reescritos, inf.renombrados_coincidentes) == (1, 0, 0)


def test_renombrado_que_solo_coincide_con_el_acortado_se_reescribe_si_se_conoce_la_base():
    # la base ya venía desincronizada: unitbase decía «Zeta» y usearch «Abdulla». Una capa renombra a «Abdul.»,
    # que coincide con acortar(usearch) sin ser el recorte del nombre anterior: es un renombrado, se copia.
    us = _us(b"Abdulla", 2) + _us(b"Beta", 3)
    base = _ub(b"Zeta", 2) + _ub(b"Beta", 3)
    ub = _ub(b"Abdul.", 2) + _ub(b"Beta", 3)
    sin_base, inf0 = S.sincronizar(E_LOGIC, us, ub)  # sin base no es detectable: pasa como coherente
    assert sin_base == us and inf0.renombrados_coincidentes == 0
    con_base, inf = S.sincronizar(E_LOGIC, us, ub, base_unitbase=base)
    assert inf.renombrados_coincidentes == 1 and inf.reescritos == 1
    assert con_base[:16].rstrip(b"\0") == b"Abdul."
    assert inf.a_json()["renombrados_coincidentes_con_acortado"] == 1
    assert _cuenta(S.verificar(E_LOGIC, con_base, ub)) == []


def test_renombrado_exactamente_al_acortado_del_nombre_anterior_no_es_detectable():
    """Límite documentado: es indistinguible del recorte de nombres_cortos_6 (y tiene el mismo efecto)."""
    us = _us(b"Abdulla", 2)
    base, ub = _ub(b"Abdulla", 2), _ub(b"Abdul.", 2)
    assert S.sincronizar(E_LOGIC, us, ub, base_unitbase=base)[0] == us
