"""Pruebas de nucleo.texto.sjis_portador y de la fachada _legado.reinsert (F1.4, T2).

Las salidas esperadas se capturaron ejecutando tools/reinsert.py (hoy ``ie123kit._legado.reinsert``) del commit 0af2abd con
entradas sintéticas y una tabla de anchos inyectada (sin datos de juego).
"""
from __future__ import annotations

import hashlib
import inspect
import json

import pytest

from ie123kit.nucleo.config.congelados import preparar
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.texto import sjis_portador

ESPERADO = json.loads(''.join(
    '{"es_encode":[["Hola, \\u00bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!",0,""]'
    ',["Hola, \\u00bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!",5,"486f6c612c"],["'
    'Hola, \\u00bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!",17,"486f6c612c2083ad7'
    '17583a02074616c20"],["Hola, \\u00bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!"'
    ',1048576,"486f6c612c2083ad717583a02074616c20657374839f7320686f792c204d61726b3f2083ac56616d6f73206120'
    '656e7472656e6172206a756e746f7321"],["L\\u00ednea uno\\nl\\u00ednea dos muy larga que hay que reajustar '
    'sin partir palabras\\fp\\u00e1gina dos tambi\\u00e9n bastante larga para el ancho",0,""],["L\\u00ednea u'
    'no\\nl\\u00ednea dos muy larga que hay que reajustar sin partir palabras\\fp\\u00e1gina dos tambi\\u00e9n'
    ' bastante larga para el ancho",5,"4c83a16e65"],["L\\u00ednea uno\\nl\\u00ednea dos muy larga que hay qu'
    'e reajustar sin partir palabras\\fp\\u00e1gina dos tambi\\u00e9n bastante larga para el ancho",17,"4c83'
    'a16e656120756e6f0a6c83a16e6561"],["L\\u00ednea uno\\nl\\u00ednea dos muy larga que hay que reajustar si'
    'n partir palabras\\fp\\u00e1gina dos tambi\\u00e9n bastante larga para el ancho",1048576,"4c83a16e65612'
    '0756e6f0a6c83a16e656120646f73206d7579206c61726761207175652068617920717565207265616a75737461722073696'
    'e207061727469722070616c61627261730c70839f67696e6120646f732074616d626983a06e2062617374616e7465206c617'
    '26761207061726120656c20616e63686f"],["corto",0,""],["corto",5,"636f72746f"],["corto",17,"636f72746f"'
    '],["corto",1048576,"636f72746f"],["",0,""],["",5,""],["",17,""],["",1048576,""],["a\\u00f1o\\u00f1 \\u0'
    '0c1\\u00c9\\u00cd\\u00d3\\u00da \\u00fc 123 %s fin",0,""],["a\\u00f1o\\u00f1 \\u00c1\\u00c9\\u00cd\\u00d3\\u00da'
    ' \\u00fc 123 %s fin",5,"6183a56f"],["a\\u00f1o\\u00f1 \\u00c1\\u00c9\\u00cd\\u00d3\\u00da \\u00fc 123 %s fin"'
    ',17,"6183a56f83a52083a683a783a883a983aa"],["a\\u00f1o\\u00f1 \\u00c1\\u00c9\\u00cd\\u00d3\\u00da \\u00fc 123'
    ' %s fin",1048576,"6183a56f83a52083a683a783a883a983aa2083a4203132332025732066696e"]],"greek":["Hola, '
    '\\u039fqu\\u0392 tal est\\u0391s hoy, Mark? \\u039eVamos a entrenar juntos!","L\\u0393nea uno\\nl\\u0393nea'
    ' dos muy larga que hay que reajustar sin partir palabras\\fp\\u0391gina dos tambi\\u0392n bastante larg'
    'a para el ancho","corto","","a\\u0397o\\u0397 \\u0398\\u0399\\u039a\\u039b\\u039c \\u0396 123 %s fin"],"adva'
    'nce":{"a":10,"Z":10," ":7,"\\u00e1":10,"\\u00bf":3,"!":8,"\\u00f1":9,"1":3,".":7},"reflow":[["Hola, \\u0'
    '0bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!","Hola, \\u00bfqu\\u00e9 tal est\\'
    'u00e1s hoy,\\\\nMark? \\u00a1Vamos a entrenar\\\\njuntos!"],["L\\u00ednea uno\\nl\\u00ednea dos muy larga qu'
    'e hay que reajustar sin partir palabras\\fp\\u00e1gina dos tambi\\u00e9n bastante larga para el ancho",'
    '"L\\u00ednea uno\\nl\\u00ednea dos muy\\\\nlarga que hay que reajustar\\\\nsin partir palabras\\fp\\u00e1gina'
    '\\\\ndos tambi\\u00e9n bastante larga\\\\npara el ancho"],["corto","corto"],["",""],["a\\u00f1o\\u00f1 \\u00'
    'c1\\u00c9\\u00cd\\u00d3\\u00da \\u00fc 123 %s fin","a\\u00f1o\\u00f1 \\u00c1\\u00c9\\u00cd\\u00d3\\u00da \\u00fc '
    '123 %s fin"]],"repag":[["Hola, \\u00bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar junto'
    's!",1,["Hola, \\u00bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!"]],["Hola, \\u0'
    '0bfqu\\u00e9 tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!",2,null],["Hola, \\u00bfqu\\u00e9'
    ' tal est\\u00e1s hoy, Mark? \\u00a1Vamos a entrenar juntos!",3,null],["L\\u00ednea uno\\nl\\u00ednea dos '
    'muy larga que hay que reajustar sin partir palabras\\fp\\u00e1gina dos tambi\\u00e9n bastante larga par'
    'a el ancho",1,["L\\u00ednea uno\\nl\\u00ednea dos muy larga que hay que reajustar sin partir palabras\\f'
    'p\\u00e1gina dos tambi\\u00e9n bastante larga para el ancho"]],["L\\u00ednea uno\\nl\\u00ednea dos muy la'
    'rga que hay que reajustar sin partir palabras\\fp\\u00e1gina dos tambi\\u00e9n bastante larga para el a'
    'ncho",2,null],["L\\u00ednea uno\\nl\\u00ednea dos muy larga que hay que reajustar sin partir palabras\\f'
    'p\\u00e1gina dos tambi\\u00e9n bastante larga para el ancho",3,null],["corto",1,["corto"]],["corto",2,'
    'null],["corto",3,null],["",1,null],["",2,null],["",3,null],["a\\u00f1o\\u00f1 \\u00c1\\u00c9\\u00cd\\u00d3'
    '\\u00da \\u00fc 123 %s fin",1,["a\\u00f1o\\u00f1 \\u00c1\\u00c9\\u00cd\\u00d3\\u00da \\u00fc 123 %s fin"]],["a'
    '\\u00f1o\\u00f1 \\u00c1\\u00c9\\u00cd\\u00d3\\u00da \\u00fc 123 %s fin",2,null],["a\\u00f1o\\u00f1 \\u00c1\\u00c'
    '9\\u00cd\\u00d3\\u00da \\u00fc 123 %s fin",3,null]],"furi":[["82a025314682a082a020746578746f0c2532466f74'
    '7261","Hola que tal\\nadios",4,true,null],["82a025314682a082a020746578746f0c2532466f747261","Hola que'
    ' tal\\nadios",4,false,null],["82a025314682a082a020746578746f0c2532466f747261","Hola que tal\\nadios",2'
    '0,true,"253146814025324681408140486f6c6120717565"],["82a025314682a082a020746578746f0c2532466f747261"'
    ',"Hola que tal\\nadios",20,false,"253146814025324681408140486f6c6120717565"],["82a025314682a082a02074'
    '6578746f0c2532466f747261","Hola que tal\\nadios",60,true,"253146814025324681408140486f6c6120717565207'
    '4616c0a6164696f73202020202020202020202020202020202020202020202020202020202020"],["82a025314682a082a0'
    '20746578746f0c2532466f747261","Hola que tal\\nadios",60,false,"253146814025324681408140486f6c61207175'
    '652074616c0a6164696f73202020202020202020202020202020202020202020202020202020202020"],["82a025314682a'
    '082a020746578746f0c2532466f747261","uno\\fdos\\ftres",4,true,null],["82a025314682a082a020746578746f0c2'
    '532466f747261","uno\\fdos\\ftres",4,false,null],["82a025314682a082a020746578746f0c2532466f747261","uno'
    '\\fdos\\ftres",20,true,"253146814025324681408140756e6f0c646f730c"],["82a025314682a082a020746578746f0c2'
    '532466f747261","uno\\fdos\\ftres",20,false,"253146814025324681408140756e6f0c646f730c"],["82a025314682a'
    '082a020746578746f0c2532466f747261","uno\\fdos\\ftres",60,true,"253146814025324681408140756e6f0c646f730'
    'c74726573202020202020202020202020202020202020202020202020202020202020202020202020"],["82a025314682a0'
    '82a020746578746f0c2532466f747261","uno\\fdos\\ftres",60,false,"253146814025324681408140756e6f0c646f730'
    'c74726573202020202020202020202020202020202020202020202020202020202020202020202020"],["82a025314682a0'
    '82a020746578746f0c2532466f747261","a b c d e f",4,true,null],["82a025314682a082a020746578746f0c25324'
    '66f747261","a b c d e f",4,false,null],["82a025314682a082a020746578746f0c2532466f747261","a b c d e '
    'f",20,true,"2531468140253246814081406120622063206420"],["82a025314682a082a020746578746f0c2532466f747'
    '261","a b c d e f",20,false,"2531468140253246814081406120622063206420"],["82a025314682a082a020746578'
    '746f0c2532466f747261","a b c d e f",60,true,"2531468140253246814081406120622063206420652066202020202'
    '02020202020202020202020202020202020202020202020202020202020202020"],["82a025314682a082a020746578746f'
    '0c2532466f747261","a b c d e f",60,false,"2531468140253246814081406120622063206420652066202020202020'
    '20202020202020202020202020202020202020202020202020202020202020"],["73696e206d6172636173","Hola que t'
    'al\\nadios",4,true,"486f6c61"],["73696e206d6172636173","Hola que tal\\nadios",4,false,"486f6c61"],["73'
    '696e206d6172636173","Hola que tal\\nadios",20,true,"486f6c61207175652074616c0a6164696f732020"],["7369'
    '6e206d6172636173","Hola que tal\\nadios",20,false,"486f6c61207175652074616c0a6164696f732020"],["73696'
    'e206d6172636173","Hola que tal\\nadios",60,true,"486f6c61207175652074616c0a6164696f732020202020202020'
    '20202020202020202020202020202020202020202020202020202020202020202020"],["73696e206d6172636173","Hola'
    ' que tal\\nadios",60,false,"486f6c61207175652074616c0a6164696f732020202020202020202020202020202020202'
    '02020202020202020202020202020202020202020202020"],["73696e206d6172636173","uno\\fdos\\ftres",4,true,"7'
    '56e6f0c"],["73696e206d6172636173","uno\\fdos\\ftres",4,false,"756e6f0c"],["73696e206d6172636173","uno\\'
    'fdos\\ftres",20,true,"756e6f0c646f730c747265732020202020202020"],["73696e206d6172636173","uno\\fdos\\ft'
    'res",20,false,"756e6f0c646f730c747265732020202020202020"],["73696e206d6172636173","uno\\fdos\\ftres",6'
    '0,true,"756e6f0c646f730c7472657320202020202020202020202020202020202020202020202020202020202020202020'
    '2020202020202020202020202020"],["73696e206d6172636173","uno\\fdos\\ftres",60,false,"756e6f0c646f730c74'
    '7265732020202020202020202020202020202020202020202020202020202020202020202020202020202020202020202020'
    '20"],["73696e206d6172636173","a b c d e f",4,true,"61206220"],["73696e206d6172636173","a b c d e f",'
    '4,false,"61206220"],["73696e206d6172636173","a b c d e f",20,true,"612062206320642065206620202020202'
    '0202020"],["73696e206d6172636173","a b c d e f",20,false,"6120622063206420652066202020202020202020"]'
    ',["73696e206d6172636173","a b c d e f",60,true,"6120622063206420652066202020202020202020202020202020'
    '20202020202020202020202020202020202020202020202020202020202020202020"],["73696e206d6172636173","a b '
    'c d e f",60,false,"612062206320642065206620202020202020202020202020202020202020202020202020202020202'
    '020202020202020202020202020202020202020"],["2533466162630c6465660c676869","Hola que tal\\nadios",4,tr'
    'ue,null],["2533466162630c6465660c676869","Hola que tal\\nadios",4,false,null],["2533466162630c6465660'
    'c676869","Hola que tal\\nadios",20,true,"253346814081408140486f6c6120717565207461"],["2533466162630c6'
    '465660c676869","Hola que tal\\nadios",20,false,"253346814081408140486f6c6120717565207461"],["25334661'
    '62630c6465660c676869","Hola que tal\\nadios",60,true,"253346814081408140486f6c61207175652074616c0a616'
    '4696f73202020202020202020202020202020202020202020202020202020202020202020"],["2533466162630c6465660c'
    '676869","Hola que tal\\nadios",60,false,"253346814081408140486f6c61207175652074616c0a6164696f73202020'
    '202020202020202020202020202020202020202020202020202020202020"],["2533466162630c6465660c676869","uno\\'
    'fdos\\ftres",4,true,null],["2533466162630c6465660c676869","uno\\fdos\\ftres",4,false,null],["2533466162'
    '630c6465660c676869","uno\\fdos\\ftres",20,true,"253346814081408140756e6f0c646f730c747265"],["253346616'
    '2630c6465660c676869","uno\\fdos\\ftres",20,false,"253346814081408140756e6f0c646f730c747265"],["2533466'
    '162630c6465660c676869","uno\\fdos\\ftres",60,true,"253346814081408140756e6f0c646f730c74726573202020202'
    '020202020202020202020202020202020202020202020202020202020202020202020"],["2533466162630c6465660c6768'
    '69","uno\\fdos\\ftres",60,false,"253346814081408140756e6f0c646f730c74726573202020202020202020202020202'
    '020202020202020202020202020202020202020202020202020"],["2533466162630c6465660c676869","a b c d e f",'
    '4,true,null],["2533466162630c6465660c676869","a b c d e f",4,false,null],["2533466162630c6465660c676'
    '869","a b c d e f",20,true,"2533468140814081406120622063206420652066"],["2533466162630c6465660c67686'
    '9","a b c d e f",20,false,"2533468140814081406120622063206420652066"],["2533466162630c6465660c676869'
    '","a b c d e f",60,true,"253346814081408140612062206320642065206620202020202020202020202020202020202'
    '020202020202020202020202020202020202020202020"],["2533466162630c6465660c676869","a b c d e f",60,fal'
    'se,"253346814081408140612062206320642065206620202020202020202020202020202020202020202020202020202020'
    '202020202020202020202020"]],"BOX_W":208}'
))
TABLA = {cp: (cp % 7) + 3 for cp in range(0x20, 0x3000)}


@pytest.fixture
def tabla(monkeypatch):
    monkeypatch.setattr(sjis_portador, "_ADV", TABLA)
    yield TABLA


@pytest.fixture
def R(tabla):
    from ie123kit._legado import reinsert
    return reinsert


def test_es_encode_truncado():
    for texto, budget, hexa in ESPERADO["es_encode"]:
        assert sjis_portador.es_encode(texto, budget).hex() == hexa


def test_greek():
    textos = [t for t, n, _ in ESPERADO["repag"] if n == 1]
    assert [t.translate(sjis_portador.GREEK) for t in textos] == ESPERADO["greek"]


def test_box_w():
    assert sjis_portador.BOX_W == ESPERADO["BOX_W"] == 208


def test_advance_con_tabla(tabla):
    for ch, ancho in ESPERADO["advance"].items():
        assert sjis_portador._advance(ch) == ancho
    assert sjis_portador.avance is sjis_portador._advance


def test_adv_restaurado():
    assert sjis_portador._ADV is not TABLA


def test_reflow_repaginate_furigana(R):
    for texto, salida in ESPERADO["reflow"]:
        assert R.reflow(texto) == salida
    for texto, n, salida in ESPERADO["repag"]:
        assert R._repaginate(texto, n) == salida
    for cuerpo, es, budget, repag, salida in ESPERADO["furi"]:
        r = R._furigana_body_bytes(bytes.fromhex(cuerpo), es, budget, repag)
        assert (None if r is None else r.hex()) == salida


def test_identidades_reinsert(R):
    assert R.es_encode is sjis_portador.es_encode
    assert R._advance is sjis_portador._advance
    assert R.BOX_W == 208
    assert R._ADV is sjis_portador._ADV is TABLA


def test_layout_hash():
    preparar(find_root())
    import build_ie1_probe
    import dialogue_lock
    fuente = inspect.getsource(build_ie1_probe.layout).replace("\r\n", "\n")
    assert hashlib.sha256(fuente.encode()).hexdigest() == dialogue_lock.LAYOUT_HASH
