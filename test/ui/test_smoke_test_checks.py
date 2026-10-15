"""The smoke test's checks, run against the test suite's isolated environment.

The keyring and OQS checks depend on the machine and are covered with stubs in
test/unit/test_smoke_test.py.
"""

import faulthandler

import pytest
from PyQt6 import QtCore

from src.ui import qt_message_log
from src.utils import crash_log, smoke_test
from src.utils.globals import AppInfo

pytestmark = pytest.mark.ui


@pytest.fixture
def smoke(monkeypatch, tmp_path):
    """A SmokeTest under the smoke identity, its passphrases in the environment."""
    monkeypatch.setattr(AppInfo, "SERVICE_NAME", smoke_test.SMOKE_SERVICE_NAME)
    monkeypatch.setattr(AppInfo, "LOG_ENCRYPTION_SERVICE", smoke_test.SMOKE_LOG_SERVICE_NAME)
    monkeypatch.setattr(AppInfo, "APP_IDENTIFIER", smoke_test.SMOKE_APP_IDENTIFIER)
    for service in (smoke_test.SMOKE_SERVICE_NAME, smoke_test.SMOKE_LOG_SERVICE_NAME):
        monkeypatch.setenv(smoke_test.passphrase_env_var(service), f"passphrase-{service}")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    return smoke_test.SmokeTest(str(scratch))


@pytest.mark.parametrize("check", [
    "check_bundled_files",
    "check_config",
    "check_encrypted_cache",
    "check_encrypted_log",
    "check_compressed_logs",
    "check_encoding_detection",
])
def test_check_passes(smoke, check):
    smoke.guarded(check, getattr(smoke, check))
    assert smoke.failures == []


def test_qt_thread_check_passes(smoke, qtbot):
    smoke.guarded("Qt worker thread", smoke.check_qt_thread)
    assert smoke.failures == []


def test_process_list_check_passes(smoke):
    pytest.importorskip("psutil")
    smoke.check_process_list()
    assert smoke.failures == []


def test_encrypted_cache_check_writes_nothing_to_the_keyring(smoke, fake_keyring):
    smoke.check_encrypted_cache()
    smoke.check_encrypted_log()
    assert fake_keyring == {}


def test_fault_log_check_passes(smoke, monkeypatch, tmp_path):
    monkeypatch.setattr(crash_log, "user_logs_dir", lambda: str(tmp_path / "logs"))
    monkeypatch.setattr(crash_log, "_fault_log", None)
    monkeypatch.setattr(faulthandler, "enable", lambda **kwargs: None)
    try:
        smoke.check_fault_log()
    finally:
        if crash_log._fault_log is not None:
            crash_log._fault_log.close()
    assert smoke.failures == []


def test_qt_check_passes(smoke, qtbot, monkeypatch):
    from src.utils.theme_manager import ThemeManager

    # The stylesheet would stay on the QApplication the other tests share.
    themed = []
    monkeypatch.setattr(ThemeManager, "apply_dark_theme", staticmethod(themed.append))
    monkeypatch.setattr(qt_message_log, "_installed", False)
    previous = []
    monkeypatch.setattr(qt_message_log, "qInstallMessageHandler",
                        lambda handler: previous.append(QtCore.qInstallMessageHandler(handler)))
    qt_message_log.install_qt_message_handler()
    try:
        smoke.guarded("Qt", smoke.check_qt)
    finally:
        QtCore.qInstallMessageHandler(previous[0] if previous else None)
    assert smoke.failures == []
    assert len(themed) == 1
