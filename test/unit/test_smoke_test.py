"""src/utils/smoke_test.py: the isolated environment and the check bookkeeping."""

import os

import pytest

from src.utils import smoke_test
from src.utils.globals import AppInfo

pytestmark = pytest.mark.unit


def test_environment_points_every_location_into_scratch(tmp_path):
    env = smoke_test.smoke_test_environment(str(tmp_path))
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME",
                 "PROTOKOLL_CACHE_DIR", "PROTOKOLL_KEY_BACKUP_DIR"):
        assert env[name].startswith(str(tmp_path)), name
    assert env[smoke_test.SCRATCH_DIR_ENV] == str(tmp_path)
    assert env["QT_QPA_PLATFORM"] == "offscreen"


def test_environment_supplies_passphrases_for_the_smoke_identity(tmp_path):
    """Read from the environment, so nothing is written to the OS keyring."""
    env = smoke_test.smoke_test_environment(str(tmp_path))
    assert env[smoke_test.passphrase_env_var(smoke_test.SMOKE_SERVICE_NAME)]
    assert env[smoke_test.passphrase_env_var(smoke_test.SMOKE_LOG_SERVICE_NAME)]


def test_passphrase_variable_matches_what_the_encryptor_reads(monkeypatch):
    from src.utils import encryptor

    monkeypatch.setenv(smoke_test.passphrase_env_var("SomeService"), "from-env")
    assert encryptor.peek_passphrase("SomeService", "app") == "from-env"


def test_smoke_identity_is_not_the_real_one():
    assert smoke_test.SMOKE_SERVICE_NAME != AppInfo.SERVICE_NAME
    assert smoke_test.SMOKE_LOG_SERVICE_NAME != AppInfo.LOG_ENCRYPTION_SERVICE
    assert smoke_test.SMOKE_APP_IDENTIFIER != AppInfo.APP_IDENTIFIER


def test_isolate_environment_overrides_inherited_values(monkeypatch, tmp_path):
    for name in ("SERVICE_NAME", "LOG_ENCRYPTION_SERVICE", "APP_IDENTIFIER"):
        monkeypatch.setattr(AppInfo, name, getattr(AppInfo, name))
    monkeypatch.setattr(os, "environ", dict(os.environ))
    os.environ["PROTOKOLL_CACHE_DIR"] = "/somewhere/real"
    os.environ[smoke_test.SCRATCH_DIR_ENV] = str(tmp_path)

    assert smoke_test.isolate_environment() == str(tmp_path)

    assert os.environ["PROTOKOLL_CACHE_DIR"].startswith(str(tmp_path))
    assert AppInfo.SERVICE_NAME == smoke_test.SMOKE_SERVICE_NAME
    assert AppInfo.LOG_ENCRYPTION_SERVICE == smoke_test.SMOKE_LOG_SERVICE_NAME
    assert AppInfo.APP_IDENTIFIER == smoke_test.SMOKE_APP_IDENTIFIER


def test_result_is_zero_only_when_every_check_passed(tmp_path):
    smoke = smoke_test.SmokeTest(str(tmp_path))
    smoke.check("first", True)
    assert smoke.result() == 0
    smoke.check("second", False, "detail")
    assert smoke.result() == 1
    assert smoke.failures == ["second"]


@pytest.mark.parametrize("error", [RuntimeError("boom"), SystemExit(3), KeyError(2)])
def test_guarded_fails_the_check_and_carries_on(monkeypatch, tmp_path, error):
    smoke = smoke_test.SmokeTest(str(tmp_path))
    logged = []
    # The logger is shared for the process, so the patch has to be undone.
    monkeypatch.setattr(smoke.logger, "error", logged.append)

    def failing():
        raise error

    smoke.guarded("failing", failing)
    smoke.guarded("passing", lambda: smoke.check("passing", True))

    assert smoke.failures == ["failing"]
    assert "Traceback" in logged[0]


def test_keyring_check_rejects_the_fail_backend(monkeypatch, tmp_path):
    import keyring
    import keyring.backends.fail

    smoke = smoke_test.SmokeTest(str(tmp_path))
    monkeypatch.setattr(keyring, "get_keyring", lambda: keyring.backends.fail.Keyring())
    smoke.check_keyring_backend()
    assert smoke.failures == ["keyring backend"]


def test_keyring_check_accepts_another_backend(monkeypatch, tmp_path):
    import keyring

    class _Backend:
        pass

    smoke = smoke_test.SmokeTest(str(tmp_path))
    monkeypatch.setattr(keyring, "get_keyring", lambda: _Backend())
    smoke.check_keyring_backend()
    assert smoke.failures == []


def test_oqs_is_required_only_when_expected(monkeypatch, tmp_path):
    from src.utils import encryptor

    monkeypatch.setattr(encryptor, "KeyEncapsulation", None)
    smoke = smoke_test.SmokeTest(str(tmp_path))
    smoke.check_oqs(expect_oqs=False)
    assert smoke.failures == []
    smoke.check_oqs(expect_oqs=True)
    assert smoke.failures == ["OQS key encapsulation"]
