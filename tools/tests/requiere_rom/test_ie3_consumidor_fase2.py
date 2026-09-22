"""Anclas independientes del escritor: instrucciones ARM del consumidor JP."""

import hashlib

import pytest

from ie123kit.nucleo.config.raiz import find_root

pytestmark = pytest.mark.requiere_rom


def test_runtime_consumer_exact_revision_and_operations():
    path = find_root() / "work/shared/base_3ds/romfs/cro/ina_main3ogre.cro"
    if not path.is_file():
        pytest.skip("CRO oficial local no disponible")
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == "280e423a5957ea5394de359fb37e2945c2e88856b7b45b8b63cb287be6193ff0"
    for offset, expected in {
        0x4F0C4: "400051e3",  # cmp prefix @
        0x4F120: "0c1081e0",  # event base + relative byte offset
        0x4F174: "03005ce3",  # type 3 only
        0x4F180: "04a08ce2",  # record header +4
        0x4F188: "03c0dce5",  # unsigned byte record size
        0x4F18C: "0c3083e0",  # advance cursor
        0x267ACC: "6962f6eb",  # FS_SeekFile thunk
        0x267ADC: "6762f6eb",  # FS_ReadFile thunk
    }.items():
        assert data[offset : offset + 4].hex() == expected
