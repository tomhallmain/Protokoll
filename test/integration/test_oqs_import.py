"""src/utils/encryptor.py's import of oqs: the bundled liboqs folder, and
liboqs-python's own errors. Each case imports the encryptor in a fresh
interpreter, since this runs at module load; oqs is a stub there, so
liboqs-python never tries to build liboqs."""

import json
import os
import subprocess
import sys

import pytest

from src.utils.app_paths import RESOURCE_ROOT

pytestmark = pytest.mark.integration

_PROBE = """
import json, os, sys, types
sys.path.insert(0, sys.argv[1])
resource_root, oqs_stub, preset = sys.argv[2], sys.argv[3], sys.argv[4]

class _Broken(types.ModuleType):
    def __getattr__(self, name):
        raise RuntimeError("cannot find or build liboqs")

sys.modules["oqs"] = None if oqs_stub == "missing" else _Broken("oqs")
os.environ.pop("OQS_INSTALL_PATH", None)
if preset:
    os.environ["OQS_INSTALL_PATH"] = preset
from src.utils import app_paths
app_paths.RESOURCE_ROOT = resource_root
from src.utils import encryptor
print(json.dumps({"install_path": os.environ.get("OQS_INSTALL_PATH"),
                  "oqs": encryptor.KeyEncapsulation is not None}))
"""


def _import_encryptor(resource_root, oqs_stub="missing", preset=""):
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, RESOURCE_ROOT, str(resource_root), oqs_stub, preset],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_bundled_liboqs_folder_becomes_the_install_path(tmp_path):
    (tmp_path / "liboqs").mkdir()
    assert _import_encryptor(tmp_path)["install_path"] == str(tmp_path / "liboqs")


def test_no_bundled_folder_leaves_the_install_path_unset(tmp_path):
    assert _import_encryptor(tmp_path)["install_path"] is None


def test_an_install_path_already_set_is_kept(tmp_path):
    (tmp_path / "liboqs").mkdir()
    preset = os.path.join(str(tmp_path), "elsewhere")
    assert _import_encryptor(tmp_path, preset=preset)["install_path"] == preset


@pytest.mark.parametrize("oqs_stub", ["missing", "broken"])
def test_unusable_oqs_leaves_key_encapsulation_off(tmp_path, oqs_stub):
    assert _import_encryptor(tmp_path, oqs_stub=oqs_stub)["oqs"] is False
