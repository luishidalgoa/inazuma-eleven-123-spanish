"""Pruebas sintéticas. No contienen ROMs, fuentes, pistas ni vídeos comerciales."""
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from ie123kit.ie3.comun import bomber_medios_integracion_v11 as core
from ie123kit.ie3.comun import bomber_video_qa as qa


@dataclass
class Frame:
    shape: tuple = (320, 240, 3)
    size: int = 320 * 240 * 3


class FakeCV:
    CAP_PROP_FPS = 1
    CAP_PROP_FRAME_COUNT = 2
    __version__ = "test-no-decodificacion-real"

    def __init__(self, count=3, declared=3, fps=24, shape=(320, 240, 3), opened=True, fail=None):
        self.count, self.declared, self.fps = count, declared, fps
        self.shape, self.opened, self.fail = shape, opened, fail
        self.reads, self.released = 0, False

    def VideoCapture(self, path):
        assert Path(path).is_file()
        return self

    def isOpened(self):
        return self.opened

    def get(self, prop):
        return self.fps if prop == 1 else self.declared

    def getBackendName(self):
        return "simulado"

    def read(self):
        if self.fail:
            raise RuntimeError(self.fail)
        self.reads += 1
        return (True, Frame(self.shape)) if self.reads <= self.count else (False, None)

    def release(self):
        self.released = True


def result(data=b"test", frames=3):
    return {"qa_version": qa.QA_VERSION, "sha256": core.digest(data), "frames": frames,
            "fps": 24, "width": 240, "height": 320, "decode": "sequential_eof",
            "termination": "opencv_read_false", "declared_frames": frames,
            "runtime_verified": False}


def test_qa_counts_reads_not_metadata_and_reuses_hash(tmp_path):
    cv = FakeCV(declared=0)
    row = qa.decodificar(b"source", tmp_path, cv=cv)
    assert row["frames"] == 3 and cv.reads == 4 and cv.released
    assert row["declared_frames"] is None
    assert qa.decodificar(b"source", tmp_path, cv=FakeCV(fail="no leer")) == row
    other = FakeCV(count=4, declared=4)
    assert qa.decodificar(b"different", tmp_path, cv=other)["frames"] == 4


@pytest.mark.parametrize("settings", [
    {"count": 0}, {"fps": 25}, {"fps": float("nan")}, {"shape": (240, 320, 3)},
    {"declared": 4}, {"opened": False}, {"fail": "decoder error"},
])
def test_qa_failures_not_accepted(tmp_path, settings):
    cv = FakeCV(**settings)
    with pytest.raises((ValueError, RuntimeError)):
        qa.decodificar(b"source", tmp_path, cv=cv)
    assert cv.released
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize("change", [
    {"sha256": "bad"}, {"frames": 0}, {"frames": True}, {"frames": 3.0},
    {"decode": "partial"}, {"fps": 25}, {"width": 320}, {"qa_version": "old"},
    {"termination": "exception"}, {"runtime_verified": True},
])
def test_qa_rejects_stale_or_invalid_fields(change):
    with pytest.raises(ValueError):
        qa.validar_resultado(dict(result(), **change), core.digest(b"test"))


def test_timeline_mismatch_rejected():
    with pytest.raises(ValueError, match="duración"):
        qa.comparar_pareja(result(), result(frames=4))


@pytest.mark.parametrize("relative", ["../outside", "/absolute", "C:/file", "a\\b", "x/../../b"])
def test_paths_cannot_escape(tmp_path, relative):
    with pytest.raises(ValueError):
        core.ruta_interna(tmp_path, relative)


def test_same_and_approved_transition_only():
    core.comprobar_transicion("jp", "jp", "es", "movie")
    core.comprobar_transicion("es", "jp", "es", "movie")
    with pytest.raises(ValueError):
        core.comprobar_transicion("other", "jp", "es", "movie")


def test_non_media_protection():
    before = {"dialogue": "text", "font": "glyph", "movie": "jp"}
    after = dict(before, movie="es")
    core.comprobar_aislamiento(before, after, {"movie": "es"})
    for broken in (dict(after, dialogue="changed"), dict(after, extra="x"), {"movie": "es"}):
        with pytest.raises(ValueError):
            core.comprobar_aislamiento(before, broken, {"movie": "es"})


def test_duplicate_json_rejected(tmp_path):
    path = tmp_path / "a.json"
    path.write_text('{"x":1,"x":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicada"):
        core.leer_json(path)


# Un contenedor JSON de tests: NO es un parser FA/B123 alternativo de producción.
class FakeArchive:
    def __init__(self, path):
        self.data = {k: bytes.fromhex(v) for k, v in json.loads(Path(path).read_text()).items()}
        self.entries = [SimpleNamespace(path=k.encode()) for k in self.data]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, key):
        if not isinstance(key, str):
            key = key.path.decode()
        return self.data[key]


def write_arc(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: v.hex() for k, v in data.items()}))


def fake_repack(path, changes):
    with FakeArchive(path) as arc:
        data = dict(arc.data)
    data.update(changes)
    write_arc(path, data)


def fake_sad(path):
    data = Path(path).read_bytes()
    return data, {"size": len(data), "data_size": len(data), "sha256": core.digest(data),
                  "channels": 2, "sample_rate": 32728, "codec_flag": "0xb4",
                  "loop": False, "start_offset": 256}


def fake_descriptor(data):
    return {"sha256": core.digest(data), "bytes": len(data), "width": 240,
            "height": 320, "fps": [24, 1], "layout": 22}


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def song(name, payload):
    data = bytearray(256) + payload
    data[32:32+len(name)] = name
    return bytes(data)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    root = tmp_path
    base = root / "work/ie3/shared/candidatas/base"
    source = root / "work/fuego/romfs/archive_bz.fa"
    output = root / "work/ie3/shared/candidatas/complemento"
    jpdir = root / "work/shared/base_3ds/romfs"
    video_contracts, jpdata, esdata = {}, {"font/FONT12.bcfnt": b"font", "dialogue": b"keep"}, {}
    for i, name in enumerate(core.VIDEOS):
        old, new = f"jp{i}".encode(), f"es{i}".encode()
        video_contracts[name] = (core.digest(old), core.digest(new), len(old), len(new))
        jpdata[core.MOVIE_PREFIX + name + ".moflex"] = old
        esdata["es/" + core.MOVIE_PREFIX + name + ".moflex"] = new
    monkeypatch.setattr(core, "VIDEOS", video_contracts)
    audio_contracts, audio_rows, external = {}, [], {}
    for name in core.CANCIONES:
        stem = name[:-1]
        old = song((name.upper() + ".SAD").encode(), b"japanese")
        internal = "OP00F.SAD" if stem == "op00" else "END00B.SAD"
        new = song(internal.encode(), b"spanish")
        audio_contracts[name] = (core.digest(old), core.digest(new), len(old), len(new))
        target = core.SOUND_PREFIX + name + ".SAD"
        common = core.SOUND_PREFIX + stem + "f.SAD"
        put(jpdir / target, old)
        put(source.parent / "es" / target, new)
        put(base / "romfs" / common, new)
        audio_rows.append({"target": common, "state": "preparado", "after": {"sha256": core.digest(new)}})
        external[common] = core.huella_local(base / "romfs" / common)
    monkeypatch.setattr(core, "CANCIONES", audio_contracts)
    write_arc(jpdir / "archive.fa", jpdata)
    write_arc(base / "archive.fa", jpdata)
    write_arc(source, esdata)
    put(base / "romfs" / core.CRO_PATH, b"unchanged-cro")
    put(root / "work/shared/base_3ds/exefs.bin", b"exefs")
    put(root / "protected.py", b"not modified")
    inv = {k: core.digest(v) for k, v in jpdata.items()}
    rev = {"archive": core.huella_local(base / "archive.fa"),
           "cro": core.huella_local(base / "romfs" / core.CRO_PATH),
           "protected_code": {"x": core.huella_local(root / "protected.py")},
           "protected_hashes_match": True, "cro_patches": {"no_changes": True},
           "resources_after": inv, "external_romfs": external}
    qa.escribir_json(base / "revision.json", rev)
    qa.escribir_json(base / "verification.json", {"archive": rev["archive"], "cro": rev["cro"],
                                                 "no_truncations_accepted": True})
    built = {"archive": rev["archive"], "cro": rev["cro"],
             "emission_manifest": core.huella_local(base / "revision.json"),
             "independent_verification": core.huella_local(base / "verification.json"),
             "exefs": core.huella_local(root / "work/shared/base_3ds/exefs.bin"),
             "readback": {"archive.fa": rev["archive"], core.CRO_PATH: rev["cro"],
                          "all_archive_entries_verified": len(inv), "exefs_unchanged": True,
                          "external_media_verified": len(external)}}
    qa.escribir_json(base / "manifest.json", built)
    qa.escribir_json(base / "audio.json", {"rows": audio_rows})
    qa.escribir_json(base / "videos.json", {"rows": []})
    motor = core.Motor(FakeArchive, fake_repack, core.huella_local, fake_sad, fake_descriptor, lambda _: {"mock": True})
    monkeypatch.setattr(core.shutil, "disk_usage", lambda _: SimpleNamespace(free=100 * 1024**3))
    return root, base, source, output, motor


def fake_decoder(data, cache):
    return result(data)


def test_complete_preparation_and_verification_preserves_all_other_bytes(environment):
    root, base, source, output, motor = environment
    before_files = {str(p): p.read_bytes() for p in base.rglob("*") if p.is_file()}
    proof = core.preparar(root, base, source, output, motor=motor, decoder=fake_decoder)
    assert proof["no_truncations_accepted"] and proof["bomber_video_targets"] == 4
    assert proof["bomber_song_targets"] == 2 and not proof["runtime_verified"]
    assert core.verificar(root, output, motor=motor) == proof
    assert before_files == {str(p): p.read_bytes() for p in base.rglob("*") if p.is_file()}
    with FakeArchive(output / "archive.fa") as arc:
        assert arc.read("dialogue") == b"keep" and arc.read("font/FONT12.bcfnt") == b"font"
    assert not (output / "manifest.json").exists()  # No se finge construir una ROM.
    with pytest.raises(FileExistsError):
        core.preparar(root, base, source, output, motor=motor, decoder=fake_decoder)


def test_bad_source_fails_before_creating_candidate(environment):
    root, base, source, output, motor = environment
    with FakeArchive(source) as arc:
        data = arc.data
    data[next(iter(data))] = b"wrong-translation"
    write_arc(source, data)
    with pytest.raises(ValueError, match="extracción auditada"):
        core.preparar(root, base, source, output, motor=motor, decoder=fake_decoder)
    assert not output.exists()


def test_missing_decode_fails_before_creating_candidate(environment):
    root, base, source, output, motor = environment
    def fail(data, cache):
        raise RuntimeError("codec unavailable")
    with pytest.raises(RuntimeError):
        core.preparar(root, base, source, output, motor=motor, decoder=fail)
    assert not output.exists()


def test_changed_base_verification_rejected(environment):
    root, base, _, _, motor = environment
    qa.escribir_json(base / "verification.json", {"no_truncations_accepted": True})
    with pytest.raises(ValueError, match="Hash/tamaño"):
        core.comprobar_base(root, base, motor)


def test_unknown_base_overlay_rejected(environment):
    root, base, _, _, motor = environment
    put(base / "romfs/unknown.bin", b"not documented")
    with pytest.raises(ValueError, match="overlay"):
        core.comprobar_base(root, base, motor)


def test_modified_final_cro_rejected(environment):
    root, base, source, output, motor = environment
    core.preparar(root, base, source, output, motor=motor, decoder=fake_decoder)
    put(output / "romfs" / core.CRO_PATH, b"changed")
    with pytest.raises(ValueError, match="CRO"):
        core.verificar(root, output, motor=motor)


def test_no_rewriting_existing_verification_after_build(environment):
    root, base, source, output, motor = environment
    proof = core.preparar(root, base, source, output, motor=motor, decoder=fake_decoder)
    put(output / "manifest.json", b"already-built")
    saved = (output / "verification.json").read_bytes()
    assert core.verificar(root, output, motor=motor) == proof
    assert saved == (output / "verification.json").read_bytes()
    qa.escribir_json(output / "verification.json", {"bad": True})
    with pytest.raises(ValueError, match="ya construida"):
        core.verificar(root, output, motor=motor)


def mismatch_opening_decoder(data, cache):
    frames = 2213 if data == b"jp3" else 2203 if data == b"es3" else 120
    return result(data, frames=frames)


def test_v11_strict_still_rejects_exact_reported_mismatch(environment):
    root, base, source, output, motor = environment
    with pytest.raises(ValueError, match="JP=2213 frames, ES=2203"):
        core.preparar(root, base, source, output, motor=motor, decoder=mismatch_opening_decoder)
    assert not output.exists()
    evidence = core.leer_json(root / "work/ie3/shared/bomber_media_qa/comparacion_op00b.json")
    assert evidence["delta_frames_es_menos_jp"] == -10
    assert evidence["delta_seconds_es_menos_jp"] == pytest.approx(-10 / 24)
    assert evidence["timeline_counts_match"] is False
    assert evidence["selected"] is False


def test_v11_conservative_keeps_whole_opening_pair_and_all_base_bytes(environment):
    root, base, source, output, motor = environment
    before = {str(p): p.read_bytes() for p in base.rglob("*") if p.is_file()}
    proof = core.preparar(root, base, source, output, motor=motor,
                          decoder=mismatch_opening_decoder, opening="conservar-base")
    assert proof["bomber_video_targets"] == 3
    assert proof["bomber_song_targets"] == 1
    assert not proof["all_requested_bomber_media_integrated"]
    assert proof["media_pending"][0]["frames_jp"] == 2213
    assert proof["media_pending"][0]["frames_es"] == 2203
    assert proof["media_pending"][0]["timeline_counts_match"] is False
    assert not (output / "romfs" / (core.SOUND_PREFIX + "op00b.SAD")).exists()
    assert (output / "romfs" / (core.SOUND_PREFIX + "end00b.SAD")).is_file()
    with FakeArchive(output / "archive.fa") as arc:
        assert arc.read(core.MOVIE_PREFIX + "op00b.moflex") == b"jp3"
        assert arc.read(core.MOVIE_PREFIX + "a3y01b.moflex") == b"es0"
        assert arc.read("dialogue") == b"keep"
        assert arc.read("font/FONT12.bcfnt") == b"font"
    assert before == {str(p): p.read_bytes() for p in base.rglob("*") if p.is_file()}
    videos = core.leer_json(output / "videos.json")
    audio = core.leer_json(output / "audio.json")
    assert videos["selected"] == 3
    assert audio["selected"] == 3  # dos canciones heredadas + end00b nuevo
    assert any(r["target"].endswith("op00b.moflex") for r in videos["pending"])
    assert any(r["target"].endswith("op00b.SAD") for r in audio["pending"])
    assert all(not r["target"].endswith("op00b.moflex") for r in videos["rows"])
    assert core.verificar(root, output, motor=motor) == proof


@pytest.mark.parametrize("change", [{"fps": 25}, {"sha256": "bad"}, {"decode": "partial"},
                                    {"frames": 0}, {"declared_frames": 2202}])
def test_v11_pending_does_not_allow_invalid_decode(environment, change):
    root, base, source, output, motor = environment
    def invalid(data, cache):
        row = mismatch_opening_decoder(data, cache)
        return dict(row, **change) if data == b"es3" else row
    with pytest.raises(ValueError):
        core.preparar(root, base, source, output, motor=motor, decoder=invalid,
                      opening="conservar-base")
    assert not output.exists()


def test_v11_other_video_mismatch_cannot_be_omitted(environment):
    root, base, source, output, motor = environment
    def invalid(data, cache):
        return result(data, frames=121 if data == b"es0" else 120)
    with pytest.raises(ValueError, match="duración"):
        core.preparar(root, base, source, output, motor=motor, decoder=invalid,
                      opening="conservar-base")
    assert not output.exists()


def test_v11_unknown_mode_rejected(environment):
    root, base, source, output, motor = environment
    with pytest.raises(ValueError, match="Política"):
        core.preparar(root, base, source, output, motor=motor, decoder=fake_decoder,
                      opening="tolerancia_10")
    assert not output.exists()


def test_v11_preservation_mode_does_not_autoinstall_even_if_counts_equal(environment):
    root, base, source, output, motor = environment
    proof = core.preparar(root, base, source, output, motor=motor, decoder=fake_decoder,
                          opening="conservar-base")
    assert proof["bomber_video_targets"] == 3 and proof["bomber_song_targets"] == 1
    assert proof["media_pending"][0]["timeline_counts_match"] is True
    assert proof["media_pending"][0]["selected"] is False


def test_v11_refuses_unexpected_original_audio_when_preserving_opening(environment):
    root, base, source, output, motor = environment
    put(root / "work/shared/base_3ds/romfs" / (core.SOUND_PREFIX + "op00b.SAD"),
        song(b"OP00F.SAD", b"incorrect pair"))
    with pytest.raises(ValueError, match="opening JP"):
        core.preparar(root, base, source, output, motor=motor,
                      decoder=mismatch_opening_decoder, opening="conservar-base")
    assert not output.exists()


def test_v11_verifier_rejects_pending_evidence_modified_even_with_fingerprints_updated(environment):
    root, base, source, output, motor = environment
    core.preparar(root, base, source, output, motor=motor,
                  decoder=mismatch_opening_decoder, opening="conservar-base")
    plan = core.leer_json(output / "medios_bomber.json")
    plan["pending"][0]["frames_es"] = 2213  # intenta ocultar los 10 frames
    qa.escribir_json(output / "medios_bomber.json", plan)
    revision = core.leer_json(output / "revision.json")
    revision["media_plan"] = core.huella_local(output / "medios_bomber.json")
    revision["media_pending"] = plan["pending"]
    qa.escribir_json(output / "revision.json", revision)
    with pytest.raises(ValueError, match="pendiente alterada"):
        core.verificar(root, output, motor=motor)


def test_v11_verifier_rejects_policy_change(environment):
    root, base, source, output, motor = environment
    core.preparar(root, base, source, output, motor=motor,
                  decoder=mismatch_opening_decoder, opening="conservar-base")
    revision = core.leer_json(output / "revision.json")
    revision["opening_policy"] = "estricto"
    qa.escribir_json(output / "revision.json", revision)
    with pytest.raises(ValueError, match="discrepan"):
        core.verificar(root, output, motor=motor)


def test_v11_exporter_is_readonly_and_hash_checked(environment, monkeypatch):
    import zipfile

    from ie123kit.ie3 import bomber_opening_diagnostico as exporter
    root, base, source, output, motor = environment
    monkeypatch.setattr(exporter, "VIDEOS", core.VIDEOS)
    monkeypatch.setattr(exporter, "CANCIONES", core.CANCIONES)
    monkeypatch.setattr(FakeArchive, "exists", lambda self, key: key in self.data, raising=False)
    before = {str(p): p.read_bytes() for folder in (base, source.parent)
              for p in folder.rglob("*") if p.is_file()}
    file = exporter.exportar(root, source, motor=motor)
    with zipfile.ZipFile(file) as z:
        assert set(z.namelist()) == {"op00b_JP.moflex", "op00b_ES.moflex",
                                    "op00b_JP.SAD", "op00b_ES.SAD", "diagnostico.json"}
        assert z.read("op00b_JP.moflex") == b"jp3"
        assert z.read("op00b_ES.moflex") == b"es3"
        manifest = json.loads(z.read("diagnostico.json"))
        assert manifest["no_media_modified"] is True
        assert manifest["runtime_verified"] is False
    assert before == {str(p): p.read_bytes() for folder in (base, source.parent)
                      for p in folder.rglob("*") if p.is_file()}
    assert not output.exists()
