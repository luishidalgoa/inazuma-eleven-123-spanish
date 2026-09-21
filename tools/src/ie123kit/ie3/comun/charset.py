"""Comprobación reproducible de la cadena de caracteres de IE3.

No intenta dibujar una fuente: demuestra que cada carácter español se codifica
al portador esperado y que el BCFNT final contiene exactamente el parche
generado desde la fuente JP de referencia.
"""
from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path

from ie123kit.nucleo.config.congelados import cargar
from ie123kit.nucleo.config.raiz import find_root
from ie123kit.nucleo.contenedores.fa import FaArchive
from ie123kit.nucleo.texto import sjis_portador

CHARSET = "¡!¿?áéíóúÁÉÍÓÚñÑüÜÈªº“”—…"
FONTS = ("font/FONT12.bcfnt", "font/FONT12T.bcfnt", "font/FONT8.bcfnt")


def comprobar_codificacion(chars: str = CHARSET) -> list[tuple[str, bytes, int | None]]:
    """Devuelve ``(carácter, bytes SJIS, portador)`` y falla si no es estable."""
    plan = {ch: cp for ch, _base, _accent, cp in cargar("font_patch").PLAN}
    resultado = []
    for ch in chars:
        encoded = sjis_portador.es_encode(ch, 8)
        if ch in plan:
            esperado = chr(plan[ch]).encode("shift-jis")
            if encoded != esperado:
                raise ValueError(f"{ch!r}: {encoded.hex()} != portador {esperado.hex()}")
            resultado.append((ch, encoded, plan[ch]))
        else:
            esperado = ch.translate(sjis_portador.GREEK).encode("shift-jis", "replace")
            if encoded != esperado:
                raise ValueError(f"{ch!r}: {encoded.hex()} != {esperado.hex()}")
            resultado.append((ch, encoded, None))
    return resultado


def comprobar_fuentes(archive_path: Path, base_fonts: Path,
                      official_archive: Path | None = None) -> dict[str, str]:
    """Comprueba hash, CMAP y tamaño de las tres fuentes finales del archive."""
    font_patch = cargar("font_patch")
    plan = [cp for _ch, _base, _accent, cp in font_patch.PLAN]
    hashes: dict[str, str] = {}
    archive = FaArchive(str(archive_path))
    official_archive = official_archive or (
        find_root() / "work" / "ie3" / "rayo_celeste" / "fuentes" /
        "3ds_eu" / "romfs" / "archive_sz.fa"
    )
    official = FaArchive(str(official_archive))
    try:
        from ie123kit.ie3.comun.text import TextTable
        from ie123kit.ie3.comun.nombres import caracteres_cortos
        from ie123kit.ie3.comun.tipografia import adaptar_font12, adaptar_font8_nombres

        tabla_es = TextTable.from_codetable(official.read("font/CodeTable.bin"))
        unitbase = "inazuma3/data_iz/logic/unitbase.dat"
        caracteres_nombres = caracteres_cortos(
            archive.read(unitbase), official.read(f"es/{unitbase}"), tabla_es,
        )
        with tempfile.TemporaryDirectory(prefix="ie3_charset_") as tmp:
            temp = Path(tmp)
            for rel in FONTS:
                source = base_fonts / rel
                if not source.is_file():
                    raise ValueError(f"falta fuente base: {source}")
                actual = archive.read(rel)
                expected = (font_patch.patch_font_bytes(source)
                            if rel == "font/FONT12T.bcfnt" else source.read_bytes())
                if rel == "font/FONT12.bcfnt":
                    expected, _report = adaptar_font12(
                        expected, official.read(rel), tabla_es,
                    )
                elif rel == "font/FONT8.bcfnt":
                    expected, _report = adaptar_font8_nombres(
                        expected, official.read(rel), tabla_es,
                        caracteres_nombres,
                    )
                if actual != expected:
                    raise ValueError(f"{rel}: no coincide con font_patch de la fuente JP")
                emitted = temp / Path(rel).name
                emitted.write_bytes(actual)
                font = font_patch.Font(emitted)
                required = plan
                missing = [f"U+{cp:04X}" for cp in required if cp not in font.cmap]
                if missing:
                    raise ValueError(f"{rel}: CMAP sin {', '.join(missing)}")
                hashes[rel] = hashlib.sha256(actual).hexdigest()
    finally:
        cerrar_oficial = getattr(official, "close", None)
        if callable(cerrar_oficial):
            cerrar_oficial()
        cerrar = getattr(archive, "close", None)
        if callable(cerrar):
            cerrar()
    return hashes


def main(argv: list[str] | None = None) -> int:
    root = find_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="archive.fa candidato o extraído de la ROM")
    parser.add_argument("--base-fonts", type=Path, default=root / "work" / "fa_extract")
    args = parser.parse_args(argv)
    rows = comprobar_codificacion()
    hashes = comprobar_fuentes(args.archive, args.base_fonts)
    print("Charset SJIS-portador:")
    for ch, encoded, carrier in rows:
        suffix = f" -> U+{carrier:04X}" if carrier is not None else ""
        # La consola Windows activa puede no representar Unicode; la prueba no
        # debe fallar después de validar correctamente la fuente por ello.
        print(f"  {ch!a}: {encoded.hex()}{suffix}")
    print("Fuentes finales verificadas:")
    for rel, digest in hashes.items():
        print(f"  {rel}: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
