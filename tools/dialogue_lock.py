"""User-approved dialogue appearance (v20 layout; fonts of probe_ie2_v34, approved 2026-09-19, #80).
No opt-out build switch."""
import hashlib
import inspect
from pathlib import Path

FONT_HASHES = {
    'font/FONT12.bcfnt': '2e2312671b0b136d3059b401d626050180ad7311b6f29fef7604116a3c5cc88e',
    'font/FONT12T.bcfnt': 'eb2a12cc633cb134cb1e668efef75eb57960cc52a6620e348ff4559bf8d35d8d',
    'font/FONT8.bcfnt': 'bec491a0eedbe6c87454b68da3a7097e7d37730301fbec1f52e53fdc812be7db',
    'inazuma1/data_iz/font/FONT12.NFTR': 'b43cfc73407c928272a001f04b85380976348e30da528b5938a3e45b87ea85c7',
    'inazuma1/data_iz/font/FONT8.NFTR': '6f683a8cef209d6e9eb9b31be5cadaad5eb90bf5ccd5e5c01c40afdf89984865',
}
SOURCE_HASHES = {
    'tools/dialogue_typography.py': '8e983419465a36460da722df4fccdb18b18b56836dc47fbc618974c18c4f42fa',
    'tools/font_patch.py': '04cf7ff5ed019f78f05b8b4912d483fbbd6c33268e1c21e85d7d1dbbe75655dc',
}
LAYOUT_HASH = '9af32753aa26c1a6738c8e76ec0816d82ed901b6b46dab5e26f51f1ed1d102b2'


def validate(fullwidth, extra_files, layout):
    """Fail before compilation if approved typography has drifted."""
    def fail(detail):
        raise ValueError('Tipografia v20 bloqueada por el usuario: ' + detail)
    if not fullwidth:
        fail('se requiere --fullwidth; ASCII no esta autorizado')
    if extra_files is None:
        fail('faltan las fuentes aprobadas en --extra-files')
    root = Path(__file__).resolve().parents[1]
    for base, manifest in ((root, SOURCE_HASHES), (Path(extra_files), FONT_HASHES)):
        for rel, expected in manifest.items():
            path = base / rel
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                fail('archivo cambiado o ausente: ' + rel)
    source = inspect.getsource(layout).replace('\r\n', '\n')
    if hashlib.sha256(source.encode()).hexdigest() != LAYOUT_HASH:
        fail('se ha cambiado el ajuste de lineas')


def approved_layout(text, layout):
    return layout(text, advance=lambda ch: 11, width=220)
