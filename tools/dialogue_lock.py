"""User-approved dialogue appearance. Fonts of probe_ie3_fuego_v16, approved in game on 2026-09-23 (European
advances in FONT12, FONT8 real width and ED/EE slices, dialogue with EU breaks 1:1); before: probe_ie2_v34 (#80).
No opt-out build switch."""
import hashlib
import inspect
from pathlib import Path

FONT_HASHES = {
    'font/FONT12.bcfnt': '222ae0f22ebf0d6dd55a2b76fa13b8d17857da350bb2532305af48681f88e3ff',
    'font/FONT12T.bcfnt': 'eb2a12cc633cb134cb1e668efef75eb57960cc52a6620e348ff4559bf8d35d8d',
    'font/FONT8.bcfnt': '3afc5bf8be9fdc752d8ccf1c5f2deba9bffbd68a9108ed3cffcf796c21826cb7',
    'inazuma1/data_iz/font/FONT12.NFTR': 'ef2841a5af60b21fa230a3cc35bedbf30aa8ddc18045abff852de3af38c88848',
    'inazuma1/data_iz/font/FONT8.NFTR': '548efc8649876fb98af8b26757702d723efe5aa58974a96dda73de4c060f6512',
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
