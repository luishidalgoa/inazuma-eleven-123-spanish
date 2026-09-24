from ie123kit.ie3.comun import resolutores as RS
from ie123kit.ie3.comun.referencias import Instruccion, Referencia


def test_memoria_unanime():
    filas = [{"japones": "a", "es_final": "A", "estado": "oficial"},
             {"japones": "a", "es_final": "A", "estado": "memoria"},
             {"japones": "b", "es_final": "B1", "estado": "oficial"},
             {"japones": "b", "es_final": "B2", "estado": "oficial"},
             {"japones": "c", "es_final": "C", "estado": "revisar"},
             {"japones": "d", "es_final": "D", "estado": "oficial"}]
    assert RS.memoria_unanime(filas, {"A", "B1", "B2", "C"}) == {"a": "A"}


def test_reparto_valido():
    f = "¡Hola! ¿Qué tal?\\nMuy bien."
    assert RS.reparto_valido(f, ["¡Hola!", "¿Qué tal?\\nMuy bien."])
    assert RS.reparto_valido(f, ["¡Hola! ¿Qué tal?", "Muy bien."])
    assert not RS.reparto_valido(f, ["¡Hola!", "¿Qué tal?"])
    assert not RS.reparto_valido(f, ["¡Hola! ¿Qué", "tal? Muy bien."])
    assert not RS.reparto_valido(f, ["¡Hola! ¿Qué tal?\\n", "Muy bien."])


def test_indexar_lineas_y_vecinas():
    idx = RS.indexar_lineas([{"evento": 1, "ins": 2, "es": "x", "perfiles": ["bomber", "ogre"]},
                             {"evento": 1, "ins": 3, "es": None, "perfiles": ["bomber"]}], "m")
    assert idx == {("bomber", 1, 2): ("x", "m"), ("ogre", 1, 2): ("x", "m")}
    assert RS.repite_vecina("x", [None, "x"]) and not RS.repite_vecina("x", ["y"])


def test_intercambiar_referencia():
    ins = Instruccion(5, 0x301D, 0, (3, 3, 4, 3), (1, 2, 6, 3), (1, 2, 3, 4))
    r = RS.intercambiar_referencia(Referencia(ins, 0, 0, 8, (0, 1, 2)))
    assert r.instruccion.tipos == (3, 4, 3, 3) and r.instruccion.valores == (1, 6, 2, 3)
    assert RS.quitar_furigana("%1F今 %s") == "今 %s"


def test_cortar_en_dos():
    t = "Hola, amigo. ¿Qué tal estás?\fMuy bien, gracias."
    assert RS.cortar_en_dos(t, lambda s: len(s) < 40) == ("Hola, amigo. ¿Qué tal estás?", "Muy bien, gracias.")
    t = "Uno dos tres. Cuatro cinco seis siete ocho."
    a, b = RS.cortar_en_dos(t, lambda s: len(s) <= 30)
    assert (a, b) == ("Uno dos tres.", "Cuatro cinco seis siete ocho.")
    assert RS.cortar_en_dos("abc", lambda s: True) is None
    assert RS.cortar_en_dos("aaaa bbbb", lambda s: len(s) < 3) is None
