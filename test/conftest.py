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

import atexit
import os
import shutil
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
# The key store defaults to the per-user data directory, which on Linux is
# XDG_DATA_HOME before it is anything under HOME.
os.environ["XDG_DATA_HOME"] = os.path.join(_bootstrap_home, "data")
os.environ.setdefault("PROTOKOLL_CACHE_DIR", os.path.join(_bootstrap_home, "cache"))


def _pin_key_backup_dir() -> None:
    """Keep automatic key backups inside whichever cache directory is in effect.

    Assigned rather than defaulted: with no destination the encryptor writes the
    backup to the first writable external drive it finds, which on a developer
    machine is a real USB stick, and the backup holds the passphrase in the
    clear. A developer who has this set in their own environment has it pointing
    somewhere real, which is the case that most needs overriding.
    """
    os.environ["PROTOKOLL_KEY_BACKUP_DIR"] = os.path.join(
        os.environ["PROTOKOLL_CACHE_DIR"], "key_backup"
    )


_pin_key_backup_dir()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTEST_QT_API", "pyqt6")
os.environ["PROTOKOLL_TEST_ISOLATED"] = "1"
# Anything written after a test's monkeypatched values are restored lands here
# rather than in the real home, so the run leaves nothing outside this directory.
atexit.register(shutil.rmtree, _bootstrap_home, True)

import pytest

try:
    import src.utils.encryptor as encryptor_module
    from src.utils.app_info_cache import AppInfoCache
except ImportError:  # no keyring/cryptography here, so nothing can reach a real store
    encryptor_module = None
    AppInfoCache = None


class FakeKeyring:
    """In-memory stand-in for the OS credential store."""

    def __init__(self):
        self.store = {}

    def get_password(self, service, key):
        return self.store.get((service, key))

    def set_password(self, service, key, value):
        self.store[(service, key)] = value

    def delete_password(self, service, key):
        # The real backends raise when the entry is absent, and the encryptor's
        # quiet-delete helpers rely on that.
        if (service, key) not in self.store:
            raise KeyError((service, key))
        del self.store[(service, key)]


# Substituted at import, not from the fixture below, because a test that reaches
# the real store is now destructive: the encryptor migrates pre-consolidation
# keychain items into a key store and deletes the originals once it reads back,
# which would take the developer's own key material with it.
if encryptor_module is not None:
    encryptor_module.keyring = FakeKeyring()


def _clear_app_info_cache_instances() -> None:
    if AppInfoCache is not None:
        AppInfoCache.clear_instances()


@pytest.fixture(autouse=True)
def isolated_app_dirs(tmp_path, monkeypatch):
    """
    Point every per-test ConfigManager/AppInfoCache instance at its own
    tmp_path, so tests never share state with each other or with the real machine.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    # Per test, so one test's key store never meets another's keyring: the
    # passphrase that opens a key store lives in the fixture-scoped fake keyring
    # below, and a store left from an earlier test would outlive it. Tests that
    # care about the backup destination set their own value over this one.
    monkeypatch.setenv("PROTOKOLL_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PROTOKOLL_KEY_BACKUP_DIR", str(tmp_path / "cache" / "key_backup"))

    real_expanduser = os.path.expanduser
    monkeypatch.setattr(
        os.path, "expanduser",
        lambda p: str(tmp_path) if p in ("~", "~user") else real_expanduser(p)
    )

    # AppInfoCache keeps one instance per directory for the life of the process,
    # holding the whole cache in memory, so a test would otherwise read the cache
    # of whichever test created that directory first.
    _clear_app_info_cache_instances()
    yield tmp_path
    _clear_app_info_cache_instances()


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch):
    """
    Give each test its own in-memory credential store, so no test touches the real
    OS keyring - which can hang on a headless box with no backend, or silently
    write real secrets on a dev machine.
    """
    fake = FakeKeyring()
    if encryptor_module is not None:
        monkeypatch.setattr(encryptor_module, "keyring", fake)
    return fake.store


@pytest.fixture
def write_encrypted_log(fake_keyring):
    """
    Append lines to a StreamingLogCipher log as a producer app would, and return its path.

    The app's passphrase goes straight into the fake keyring, as the producer's
    first run leaves it. Going through PassphraseManager instead would also try
    to lock the real Secret Service collection over D-Bus on Linux.
    """
    if encryptor_module is None:
        pytest.skip("cryptography/keyring not installed")
    from src.utils.globals import AppInfo

    def write(path, lines, service_name=AppInfo.LOG_ENCRYPTION_SERVICE, app_identifier="app"):
        fake_keyring.setdefault(
            (service_name, encryptor_module.namespaced_key(app_identifier, "passphrase")),
            f"test-passphrase-{service_name}-{app_identifier}")
        key = encryptor_module.StreamingLogCipher.find_key(service_name, app_identifier)
        with open(path, "ab") as f:
            for line in lines:
                f.write(encryptor_module.StreamingLogCipher.encrypt_record(key, line.encode("utf-8")))
        return path

    return write


@pytest.fixture(autouse=True)
def reset_encryptor_cache():
    """
    Reset the encryptor's module-level state between tests.

    get_encryptor() memoizes (service_name, app_identifier) -> encryptor class in
    ENCRYPTOR_CLASSES, and the key store and passphrase are cached per
    (service_name, app_identifier) for the life of the process. Without a reset,
    one test's keys and choice of Standard vs. Quantum encryptor would answer
    another test's read, over a different tmp_path and a different fake keyring.
    """
    def _reset():
        if encryptor_module is None:
            return
        encryptor_module.ENCRYPTOR_CLASSES.clear()
        encryptor_module.clear_key_store_cache()
        encryptor_module._auto_backup_warned.clear()

    _reset()
    yield
    _reset()


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
