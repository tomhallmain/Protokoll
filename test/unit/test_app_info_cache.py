"""
Unit tests for src.utils.app_info_cache.AppInfoCache: the encrypted store, its
backups, and what it refuses to overwrite.

Relies on the root conftest's autouse fixtures for an isolated home, an isolated
key store and a fake keyring - see test/conftest.py.
"""

import json

import pytest

import src.utils.app_info_cache as app_info_cache_module
from src.utils.app_info_cache import AppInfoCache

pytestmark = pytest.mark.unit


@pytest.fixture
def cache_dir(tmp_path):
    directory = tmp_path / "protokoll-cache"
    directory.mkdir()
    return directory


def _cache_file(cache_dir):
    return cache_dir / AppInfoCache.CACHE_FILENAME


def _json_file(cache_dir):
    return cache_dir / AppInfoCache.JSON_FILENAME


def _raise(*args, **kwargs):
    raise OSError("no key material")


def test_values_survive_a_store_and_reload(cache_dir):
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "my-app")
    cache.set_tracker("my-app", {"name": "my-app", "log_directories": ["/var/log"]})
    cache.store()

    reloaded = AppInfoCache(str(cache_dir))

    assert reloaded.get("last_tracker") == "my-app"
    assert reloaded.get_tracker("my-app")["log_directories"] == ["/var/log"]
    assert reloaded.tracker_names() == ["my-app"]


def test_cache_is_encrypted_at_rest(cache_dir):
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "super-secret-value")
    cache.store()

    raw_bytes = _cache_file(cache_dir).read_bytes()

    assert b"super-secret-value" not in raw_bytes
    with pytest.raises(Exception):
        json.loads(raw_bytes.decode("utf-8"))


def test_store_if_dirty_writes_only_after_a_change(cache_dir):
    cache = AppInfoCache(str(cache_dir))

    cache.store_if_dirty()
    assert not _cache_file(cache_dir).exists()

    cache.set("last_tracker", "my-app")
    cache.store_if_dirty()
    assert _cache_file(cache_dir).exists()


def test_removing_a_tracker_marks_the_cache_dirty(cache_dir):
    cache = AppInfoCache(str(cache_dir))
    cache.set_tracker("my-app", {"name": "my-app"})
    cache.store()

    cache.remove_tracker("my-app")
    cache.store_if_dirty()

    assert AppInfoCache(str(cache_dir)).tracker_names() == []


def test_matches_stored_reports_what_is_on_disk(cache_dir):
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "my-app")
    cache.store()

    assert cache.matches_stored()

    cache.set("last_tracker", "changed-since-the-write")

    assert not cache.matches_stored()


def test_for_directory_hands_back_one_instance(cache_dir):
    """Two instances over one file would each overwrite the other's changes."""
    first = AppInfoCache.for_directory(str(cache_dir))
    second = AppInfoCache.for_directory(str(cache_dir))

    assert first is second


def test_plain_json_cache_is_migrated_to_the_encrypted_store(cache_dir):
    """What an install left holding the JSON fallback picks up on its next run."""
    _json_file(cache_dir).write_text(
        json.dumps({AppInfoCache.INFO_KEY: {"last_tracker": "my-app"}}), encoding="utf-8")

    cache = AppInfoCache(str(cache_dir))

    assert cache.get("last_tracker") == "my-app"
    assert _cache_file(cache_dir).exists()
    assert not _json_file(cache_dir).exists()


def test_failed_encryption_falls_back_to_json_and_keeps_the_values(cache_dir, monkeypatch):
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "my-app")
    monkeypatch.setattr(app_info_cache_module, "encrypt_data_to_file", _raise)

    assert cache.store() is False

    assert json.loads(_json_file(cache_dir).read_text(encoding="utf-8"))[
        AppInfoCache.INFO_KEY]["last_tracker"] == "my-app"


def test_a_successful_store_removes_a_stale_plaintext_fallback(cache_dir):
    """load() reads the fallback first, so one left behind would undo the
    values written after it."""
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "stale")
    original = app_info_cache_module.encrypt_data_to_file
    app_info_cache_module.encrypt_data_to_file = _raise
    try:
        cache.store()
    finally:
        app_info_cache_module.encrypt_data_to_file = original
    assert _json_file(cache_dir).exists()

    cache.set("last_tracker", "current")
    cache.store()

    assert not _json_file(cache_dir).exists()
    assert AppInfoCache(str(cache_dir)).get("last_tracker") == "current"


def test_loading_from_the_main_file_takes_a_backup(cache_dir):
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "my-app")
    cache.store()

    AppInfoCache(str(cache_dir))

    assert (cache_dir / f"{AppInfoCache.CACHE_FILENAME}.bak").exists()


def test_a_damaged_cache_falls_back_to_the_backup(cache_dir):
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "my-app")
    cache.store()
    AppInfoCache(str(cache_dir))  # first load writes the backup
    _cache_file(cache_dir).write_bytes(b"corrupted")

    recovered = AppInfoCache(str(cache_dir))

    assert recovered.get("last_tracker") == "my-app"
    assert recovered.load_error is None


def test_a_cache_that_cannot_be_read_is_not_overwritten(cache_dir):
    """The values are still there for a restored key to open; a write here would
    replace them with the empty cache this instance holds."""
    _cache_file(cache_dir).write_bytes(b"corrupted, and no backup beside it")

    cache = AppInfoCache(str(cache_dir))

    assert cache.load_error
    with pytest.raises(Exception):
        cache.store()
    assert _cache_file(cache_dir).read_bytes() == b"corrupted, and no backup beside it"


def test_a_missing_cache_is_not_an_error(cache_dir):
    cache = AppInfoCache(str(cache_dir))

    assert cache.load_error is None
    assert cache.get("last_tracker") is None


def test_export_as_json_writes_the_values_in_the_clear(cache_dir, tmp_path):
    cache = AppInfoCache(str(cache_dir))
    cache.set("last_tracker", "my-app")

    exported = cache.export_as_json(str(tmp_path / "exported.json"))

    assert json.loads(open(exported, encoding="utf-8").read())[
        AppInfoCache.INFO_KEY]["last_tracker"] == "my-app"
