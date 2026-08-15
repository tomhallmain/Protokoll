"""
Unit tests for src.utils.config_manager.ConfigManager.

Relies on the root conftest's autouse `isolated_app_dirs` (redirects HOME/config_dir
to a per-test tmp_path) and `fake_keyring` (so the encryption these tests exercise
never touches a real OS keyring) - see test/conftest.py.
"""

import json

import pytest

from src.utils.config_manager import ConfigManager

pytestmark = pytest.mark.unit


@pytest.fixture
def config_manager():
    return ConfigManager()


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


def test_save_and_load_cache_roundtrip(config_manager):
    data = {"trackers": {"my-app": {"service_name": "MyApp", "app_identifier": "logs"}}}
    config_manager.save_cache("access_pointers", data)

    assert config_manager.load_cache("access_pointers") == data


def test_cache_is_encrypted_at_rest(config_manager):
    """The cache can hold key-access pointers for tracked apps, so it must never be
    plain JSON on disk."""
    config_manager.save_cache("secrets", {"token": "super-secret-value"})

    raw_bytes = config_manager.get_cache_path("secrets").read_bytes()

    assert b"super-secret-value" not in raw_bytes
    with pytest.raises(Exception):
        json.loads(raw_bytes.decode("utf-8"))


def test_load_cache_returns_default_when_missing(config_manager):
    assert config_manager.load_cache("does-not-exist", default="fallback") == "fallback"


def test_legacy_plaintext_cache_is_migrated(config_manager):
    """A .cache file written before encryption was added (plain JSON) must still load
    correctly, and get transparently re-saved encrypted - regression test for a bug
    that otherwise silently discards old cache data (see load_cache's fallback path)."""
    legacy_data = {"old": "data"}
    cache_file = config_manager.get_cache_path("legacy")
    cache_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    assert config_manager.load_cache("legacy") == legacy_data

    # The file on disk should no longer be plain JSON after migration.
    raw_bytes = cache_file.read_bytes()
    with pytest.raises(Exception):
        json.loads(raw_bytes.decode("utf-8"))

    # And it should still load correctly now that it's gone through the encrypted path.
    assert config_manager.load_cache("legacy") == legacy_data
