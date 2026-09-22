import hashlib
import struct
from pathlib import Path

import pytest

from ie123kit.ie3.comun.medios_es import (
    descriptor_moflex,
    inventariar_videos,
    leer_video,
    planificar_audio,
    planificar_videos,
)


def sad(name=b"V0101A01.SAD", payload=b"a" * 32):
    data = bytearray(256) + payload
    data[:4] = b"sadl"
    struct.pack_into("<I", data, 8, len(data))
    data[32:32 + len(name)] = name
    data[0x32:0x34] = b"\x01\xb4"
    struct.pack_into("<I", data, 0x40, len(data))
    struct.pack_into("<I", data, 0x48, 256)
    return bytes(data)


@pytest.fixture
def roots(tmp_path):
    roots = [tmp_path / n for n in ("jp", "spark", "ogre")]
    for i, root in enumerate(roots):
        for profile in ("inazuma3", "inazuma3_ogre"):
            (root / ("" if i == 0 else "es") / profile / "data_iz/sound").mkdir(parents=True)
    return roots


def write(roots, name="V0101a01.SAD", before=None, after=None):
    rel = Path("inazuma3_ogre/data_iz/sound") / name
    for i, root in enumerate(roots):
        path = root / ("" if i == 0 else "es") / rel
        path.write_bytes((before or sad()) if i == 0 else (after or sad(payload=b"b" * 32)))
    return rel.as_posix()


def test_audio_explicit_paths_and_no_writes(roots):
    rel = write(roots)
    paths, report = planificar_audio(*roots)
    assert paths == {rel: roots[1] / "es" / rel}
    assert report["rows"][0]["category"] == "voz_dialogo"
    assert not report["runtime_verified"] and not report["audio_decoded"]
    assert (roots[0] / rel).read_bytes() == sad()


def test_identical_instrumental_and_unknown_are_not_selected(roots):
    write(roots, "TITLE.SAD", sad(), sad())
    write(roots, "a3y01f.SAD")
    paths, report = planificar_audio(*roots)
    assert not paths
    assert {r["state"] for r in report["rows"]} == {
        "identico_preservado", "pendiente_categoria_no_auditada"}


@pytest.mark.parametrize("offset,value", [(8, 7), (0x40, 7), (0x48, 240), (0x32, 3), (0x33, 0xB2)])
def test_bad_header_closed(roots, offset, value):
    data = bytearray(sad())
    data[offset] = value
    write(roots, after=bytes(data))
    with pytest.raises(ValueError):
        planificar_audio(*roots)


def test_conflicting_editions_and_changed_identity(roots):
    rel = write(roots)
    (roots[2] / "es" / rel).write_bytes(sad(payload=b"c" * 32))
    with pytest.raises(ValueError, match="contradictorias"):
        planificar_audio(*roots)
    write(roots, after=sad(name=b"V0101A02.SAD"))
    with pytest.raises(ValueError, match="identidad"):
        planificar_audio(*roots)


def test_missing_and_banks_are_reported(roots):
    rel = write(roots)
    for root in roots[1:]:
        (root / "es" / rel).unlink()
    (roots[0] / rel).with_name("sound_sb.pkh").write_bytes(b"untouched")
    paths, report = planificar_audio(*roots)
    assert not paths
    assert {x["reason"] for x in report["pending"]} == {"sin_equivalente_ES", "banco_no_modificado"}


def movie():
    out = bytearray(4096)
    out[:4] = bytes.fromhex("4c32aaab")
    out[14:18] = b"\3\x0d\0\0"
    struct.pack_into(">HHHH", out, 18, 24, 1, 240, 320)
    out[26:29] = b"\1\1\x16"
    return bytes(out)


class Archive:
    def __init__(self, entries):
        self.index = entries

    def exists(self, key):
        return key in self.index

    def read(self, key):
        return self.index[key]


def test_movies_prefer_es_never_autoinstall():
    path = "inazuma3/data_iz/movie/op00f.moflex"
    txt = "inazuma3/data_iz/movie/txt/op00f.dat"
    jp = Archive({path: movie(), txt: b"jp"})
    es = Archive({"es/" + path: movie(), path: b"bad ignored", "es/" + txt: b"es"})
    report = inventariar_videos(jp, es, es)
    assert report["compatible"] == 1 and report["selected"] == 0
    assert report["rows"][0]["source"] == "es/" + path
    assert report["subtitles"][0]["state"] == "requiere_conversion_portadores_y_consumidor"


@pytest.mark.parametrize("offset,value", [(0, 0), (14, 1), (18, 1), (22, 2), (28, 6)])
def test_incompatible_movie_rejected(offset, value):
    data = bytearray(movie())
    data[offset] = value
    with pytest.raises(ValueError):
        descriptor_moflex(bytes(data))


def test_movie_conflicts_fail_closed():
    path = "inazuma3/data_iz/movie/op00f.moflex"
    other = movie()[:-1] + b"x"
    with pytest.raises(ValueError, match="ambigua"):
        inventariar_videos(Archive({path: movie()}), Archive({path: movie()}), Archive({path: other}))


def test_video_plan_requires_exact_timeline_and_hashes(monkeypatch):
    monkeypatch.setattr("ie123kit.ie3.comun.medios_es.comprobar_consumidores", lambda _: {"ok": True})
    path = "inazuma3/data_iz/movie/op00f.moflex"
    a = Archive({path: movie()})
    qa = {"results": [{"target": path, "frames": 120, "fps": 24,
                       "sha256": hashlib.sha256(movie()).hexdigest(), "decode": "sequential_eof"}]}
    plan, report = planificar_videos(a, a, a, b"", qa, qa)
    assert report["selected"] == 1 and not report["subtitle_localized"]
    assert leer_video(plan[path], a, a) == movie()
    for change in ({"frames": 121}, {"sha256": "wrong"}, {"fps": 25}, {"decode": "partial"}):
        changed = {"results": [dict(qa["results"][0], **change)]}
        with pytest.raises(ValueError):
            planificar_videos(a, a, a, b"", qa, changed)
    with pytest.raises(ValueError, match="falta QA"):
        planificar_videos(a, a, a, b"", qa, {"results": []})
    with pytest.raises(ValueError, match="duplicada"):
        planificar_videos(a, a, a, b"", qa, {"results": qa["results"] * 2})
    with pytest.raises(ValueError, match="cambió"):
        leer_video(plan[path], Archive({path: movie()[:-1] + b"x"}), a)
