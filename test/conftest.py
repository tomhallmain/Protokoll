"""
Root conftest for the Protokoll test suite.

IMPORTANT: the env vars below are set at module load time, before any `src` module
is imported. get_logger() (src/utils/logging_setup.py) attaches a real
logging.FileHandler to the real per-OS log directory the first time each named
logger is created, then caches it for the process lifetime - and ten `src` modules
create their logger as an import-time side effect, so a per-test fixture would
already be too late. Nested conftest.py files (test/unit, test/integration, test/ui)
mirror this same bootstrap for the same reason.
"""

import os
import sys
import tempfile

# Ensure the project root is on sys.path so `import src...` works regardless of
# which directory pytest is invoked from.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Bootstrap a safe temporary "home" so nothing imported below - or during test
# collection - can touch the real ~/.protokoll, the real per-OS log directory, or
# (via PassphraseManager's file-based fallback) ~/.config/<service>/<app>.enc.
_bootstrap_home = tempfile.mkdtemp(prefix="protokoll-test-home-")
os.environ["HOME"] = _bootstrap_home
os.environ["USERPROFILE"] = _bootstrap_home
os.environ["APPDATA"] = _bootstrap_home
os.environ["LOCALAPPDATA"] = _bootstrap_home
os.environ["PROGRAMDATA"] = _bootstrap_home
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTEST_QT_API", "pyqt6")
os.environ["PROTOKOLL_TEST_ISOLATED"] = "1"

import pytest


@pytest.fixture(autouse=True)
def isolated_app_dirs(tmp_path, monkeypatch):
    """
    Point every per-test ConfigManager/LogDirectoryFinder instance at its own
    tmp_path, so tests never share state with each other or with the real machine.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))

    real_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path, "expanduser",
        lambda p: str(tmp_path) if p in ("~", "~user") else real_expanduser(p)
    )

    # LogDirectoryFinder.CACHE_FILE is a class attribute fixed at import time -
    # the env vars above have no effect on it, it has to be patched directly.
    from src.internal.log_directory_finder import LogDirectoryFinder
    monkeypatch.setattr(LogDirectoryFinder, "CACHE_FILE", str(tmp_path / "custom_log_dirs.json"))

    yield tmp_path


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    """
    Replace src.utils.encryptor's `keyring` reference with an in-memory fake so no
    test ever touches the real OS keyring - which can hang on a headless box with
    no backend, or silently write real secrets on a dev machine.
    """
    store = {}

    class FakeKeyring:
        @staticmethod
        def get_password(service, key):
            return store.get((service, key))

        @staticmethod
        def set_password(service, key, value):
            store[(service, key)] = value

        @staticmethod
        def delete_password(service, key):
            if (service, key) not in store:
                raise KeyError((service, key))
            del store[(service, key)]

    import src.utils.encryptor as encryptor_module
    monkeypatch.setattr(encryptor_module, "keyring", FakeKeyring)
    return store


@pytest.fixture(autouse=True)
def reset_encryptor_cache():
    """
    get_encryptor() memoizes (service_name, app_identifier) -> encryptor class in
    the module-level ENCRYPTOR_CLASSES dict. Without a reset, one test's choice of
    Standard vs. Quantum encryptor for a given namespace would leak into any later
    test that reuses the same service_name/app_identifier.
    """
    import src.utils.encryptor as encryptor_module
    encryptor_module.ENCRYPTOR_CLASSES.clear()
    yield
    encryptor_module.ENCRYPTOR_CLASSES.clear()


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked `requires_oqs` when the optional oqs dependency isn't installed."""
    try:
        import oqs  # noqa: F401
        oqs_available = True
    except ImportError:
        oqs_available = False

    if oqs_available:
        return

    skip_oqs = pytest.mark.skip(reason="oqs/liboqs not installed (see requirements-optional.txt)")
    for item in items:
        if "requires_oqs" in item.keywords:
            item.add_marker(skip_oqs)
