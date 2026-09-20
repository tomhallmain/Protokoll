"""
Unit tests for src.utils.config_manager.ConfigManager: the split between the plain
config file and the encrypted cache, and the migration off the plaintext files.

Relies on the root conftest's autouse `isolated_app_dirs` (redirects HOME and the
cache directory to a per-test tmp_path) and `fake_keyring` (so the encryption these
tests exercise never touches a real OS keyring) - see test/conftest.py.
"""

import json

import pytest

import src.utils.app_info_cache as app_info_cache_module
from src.utils.app_info_cache import AppInfoCache
from src.utils.config_manager import ConfigManager

pytestmark = pytest.mark.unit


@pytest.fixture
def config_manager():
    return ConfigManager()


def _cache_file(manager):
    return manager.cache_dir / AppInfoCache.CACHE_FILENAME


def _write_legacy_state(config_dir):
    """The files this app wrote before any of it was encrypted."""
    tracker_dir = config_dir / "trackers" / "my-app"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "metadata.json").write_text(json.dumps({
        "name": "my-app",
        "description": "a description",
        "created_at": "2026-01-01T00:00:00",
        "log_directories": ["/var/log/my-app"],
    }), encoding="utf-8")
    (config_dir / "custom_log_dirs.json").write_text(
        json.dumps(["/opt/logs"]), encoding="utf-8")
    (config_dir / "config.json").write_text(json.dumps({
        "theme": "light",
        "last_tracker": "my-app",
        "last_log_file_my-app": "/var/log/my-app/app.log",
    }), encoding="utf-8")


def test_config_dir_is_isolated_from_real_home(config_manager, tmp_path):
    """Sanity check for the isolation fixtures themselves: config_dir must live under
    this test's own tmp_path, never the real developer home."""
    assert str(config_manager.config_dir).startswith(str(tmp_path))


def test_get_set_dotted_keys(config_manager):
    config_manager.set("window.width", 1280)
    assert config_manager.get("window.width") == 1280
    assert config_manager.get("window.missing", "default") == "default"


def test_add_recent_tracker_caps_at_ten(config_manager):
    for i in range(15):
        config_manager.add_recent_tracker(f"tracker-{i}")

    recent = config_manager.get("recent_trackers")

    assert len(recent) == 10
    assert recent[0] == "tracker-14"  # most recently added stays first


def test_add_recent_tracker_moves_existing_entry_to_front(config_manager):
    config_manager.add_recent_tracker("a")
    config_manager.add_recent_tracker("b")
    config_manager.add_recent_tracker("a")

    assert config_manager.get("recent_trackers")[:2] == ["a", "b"]


def test_tracker_keys_never_reach_the_plain_config_file(config_manager):
    """Which application is tracked, and where its logs are, is the part worth
    encrypting - the window size and search toggles are not."""
    config_manager.set("last_tracker", "sensitive-app")
    config_manager.set("last_log_file_sensitive-app", "/var/log/sensitive-app/app.log")
    config_manager.set("window.width", 1280)
    config_manager.flush_cache()

    assert config_manager.get("last_tracker") == "sensitive-app"
    config_text = config_manager.config_file.read_text(encoding="utf-8")
    assert "sensitive-app" not in config_text
    assert "1280" in config_text


def test_cache_is_encrypted_at_rest(config_manager):
    config_manager.set("last_tracker", "super-secret-value")
    config_manager.flush_cache()

    raw_bytes = _cache_file(config_manager).read_bytes()

    assert b"super-secret-value" not in raw_bytes
    with pytest.raises(Exception):
        json.loads(raw_bytes.decode("utf-8"))


def test_cache_writes_are_held_until_flush(config_manager):
    """set() runs on every search toggle and log file selection, and encrypting
    the cache derives a key."""
    config_manager.set("last_tracker", "my-app")

    assert not _cache_file(config_manager).exists()

    config_manager.flush_cache()

    assert _cache_file(config_manager).exists()


def test_tracker_metadata_is_stored_immediately(config_manager):
    config_manager.save_tracker_metadata("my-app", {"name": "my-app"})

    assert _cache_file(config_manager).exists()
    assert config_manager.list_tracker_names() == ["my-app"]


def test_saving_a_tracker_under_a_new_name_drops_the_old_entry(config_manager):
    config_manager.save_tracker_metadata("my-app", {"name": "my-app"})

    config_manager.save_tracker_metadata(
        "renamed-app", {"name": "renamed-app"}, previous_name="my-app")

    assert config_manager.list_tracker_names() == ["renamed-app"]
    assert config_manager.get_tracker_metadata("my-app") is None


def test_remove_tracker_forgets_the_state_pointing_at_it(config_manager):
    config_manager.save_tracker_metadata("my-app", {"name": "my-app"})
    config_manager.add_recent_tracker("my-app")
    config_manager.add_recent_tracker("other-app")
    config_manager.set("last_tracker", "my-app")
    config_manager.set(ConfigManager.last_log_file_key("my-app"), "/var/log/my-app/app.log")

    config_manager.remove_tracker("my-app")

    assert config_manager.list_tracker_names() == []
    assert config_manager.get("recent_trackers") == ["other-app"]
    assert config_manager.get("last_tracker") is None
    assert config_manager.get(ConfigManager.last_log_file_key("my-app")) is None


def test_remove_tracker_leaves_the_other_trackers_alone(config_manager):
    config_manager.save_tracker_metadata("my-app", {"name": "my-app"})
    config_manager.save_tracker_metadata("other-app", {"name": "other-app"})
    config_manager.set("last_tracker", "other-app")

    config_manager.remove_tracker("my-app")

    assert config_manager.list_tracker_names() == ["other-app"]
    assert config_manager.get("last_tracker") == "other-app"


def test_legacy_plaintext_state_is_migrated_into_the_cache(tmp_path):
    config_dir = tmp_path / ".protokoll"
    config_dir.mkdir(parents=True)
    _write_legacy_state(config_dir)

    manager = ConfigManager()

    assert manager.get_tracker_metadata("my-app")["log_directories"] == ["/var/log/my-app"]
    assert manager.get_custom_log_directories() == ["/opt/logs"]
    assert manager.get("last_tracker") == "my-app"
    assert manager.get("last_log_file_my-app") == "/var/log/my-app/app.log"


def test_migrated_plaintext_is_deleted_once_the_cache_reads_back(tmp_path):
    config_dir = tmp_path / ".protokoll"
    config_dir.mkdir(parents=True)
    _write_legacy_state(config_dir)

    manager = ConfigManager()

    assert not (config_dir / "trackers" / "my-app" / "metadata.json").exists()
    assert not (config_dir / "custom_log_dirs.json").exists()
    stored_config = json.loads(manager.config_file.read_text(encoding="utf-8"))
    assert "last_tracker" not in stored_config
    assert "last_log_file_my-app" not in stored_config
    assert stored_config["theme"] == "light"  # the rest of the config is untouched


def test_migration_keeps_the_plaintext_when_the_cache_cannot_be_encrypted(
        tmp_path, monkeypatch):
    """Deleting the only readable copy of this state on the strength of a write
    that did not happen would lose it outright."""
    config_dir = tmp_path / ".protokoll"
    config_dir.mkdir(parents=True)
    _write_legacy_state(config_dir)

    def _boom(*args, **kwargs):
        raise OSError("no key material")

    monkeypatch.setattr(app_info_cache_module, "encrypt_data_to_file", _boom)

    manager = ConfigManager()

    assert (config_dir / "trackers" / "my-app" / "metadata.json").exists()
    assert (config_dir / "custom_log_dirs.json").exists()
    stored_config = json.loads(manager.config_file.read_text(encoding="utf-8"))
    assert stored_config["last_tracker"] == "my-app"


def test_an_unreadable_cache_is_never_overwritten(config_manager):
    """Rewriting it would replace state that a restored key could still open."""
    config_manager.set("last_tracker", "my-app")
    config_manager.flush_cache()
    cache_file = _cache_file(config_manager)
    cache_file.write_bytes(b"not an encrypted cache")
    AppInfoCache.clear_instances()

    reopened = ConfigManager()

    assert reopened.app_info_cache.load_error
    reopened.set("last_tracker", "something-else")
    reopened.flush_cache()

    assert cache_file.read_bytes() == b"not an encrypted cache"
