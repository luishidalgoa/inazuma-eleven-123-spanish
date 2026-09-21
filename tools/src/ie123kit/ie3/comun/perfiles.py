"""Datos de entrada de la reconstrucción IE3; ningún algoritmo por versión."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Perfil:
    nombre: str
    recurso: str
    oficial: str
    corpus: str
    alineado: str
    compartido: str
    revision: str = "JP CTR-P-AETJ / SSD v3 / PackNum tipo 0"
    base_sha256: str = "be78bb7290d87edd2ac8cd012edc6a8473868dbf1f8a41e2d3c081e4db3864d4"
    consumer_sha256: str = "280e423a5957ea5394de359fb37e2945c2e88856b7b45b8b63cb287be6193ff0"

    def datos(self):
        return asdict(self)


PERFILES = {
    "spark": Perfil(
        "spark",
        "inazuma3/data_iz/script",
        "work/ie3/rayo_celeste/fuentes/3ds_eu/romfs/archive_sz.fa",
        "translation/ie3/rayo_celeste/dialogo_oficial.csv",
        "work/ie3/shared/salida/aligned/spark_rayo.csv",
        "spark_bomber",
    ),
    "bomber": Perfil(
        "bomber",
        "inazuma3/data_iz/script",
        "work/ie3/shared/fuego/romfs/archive_bz.fa",
        "translation/ie3/fuego_explosivo/dialogo_oficial.csv",
        "work/ie3/shared/salida/aligned/spark_fuego.csv",
        "spark_bomber",
        "JP CTR-P-AETJ / Fuego CTR-P-AXBZ / SSD v3 / PackNum tipo 0",
    ),
    "ogre": Perfil(
        "ogre",
        "inazuma3_ogre/data_iz/script",
        "work/ie3/amenaza_del_ogro/fuentes/3ds_eu/romfs/archive_oz.fa",
        "translation/ie3/amenaza_del_ogro/dialogo_oficial.csv",
        "work/ie3/shared/salida/aligned/ogre_ogro.csv",
        "ogre",
    ),
}


def cargar_perfil(nombre: str, archivo: Path | None = None) -> Perfil:
    if archivo is not None:
        profile = Perfil(**json.loads(archivo.read_text(encoding="utf-8")))
        if profile.nombre != nombre:
            raise ValueError("nombre de perfil no coincide con la configuración")
        return profile
    if nombre not in PERFILES:
        raise ValueError(
            f"perfil {nombre!r} sin corpus/correspondencias validados; "
            "aportar configuración explícita, no heredar correspondencias de Spark"
        )
    return PERFILES[nombre]
