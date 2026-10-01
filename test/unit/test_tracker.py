"""
Unit tests for src.internal.tracker.Tracker: log directory management, log file
discovery, and metadata persistence through the encrypted cache.
"""

import pytest

from src.internal.tracker import Tracker, app_identifier_from_log_name
from src.utils.config_manager import ConfigManager
from src.utils.globals import AppInfo

pytestmark = pytest.mark.unit


@pytest.fixture
def config_manager():
    return ConfigManager()


def test_add_log_directory_persists_and_updates_metadata(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", "desc", config_manager)

    tracker.add_log_directory(str(log_dir))

    assert str(log_dir) in tracker.get_log_directories()
    assert config_manager.get_tracker_metadata("my-app")["log_directories"] == [str(log_dir)]


def test_add_log_directory_rejects_nonexistent_path(tmp_path, config_manager):
    tracker = Tracker("my-app", config_manager=config_manager)

    with pytest.raises(ValueError):
        tracker.add_log_directory(str(tmp_path / "does-not-exist"))


def test_add_log_directory_rejects_file_path(tmp_path, config_manager):
    a_file = tmp_path / "not_a_dir.txt"
    a_file.write_text("x")
    tracker = Tracker("my-app", config_manager=config_manager)

    with pytest.raises(ValueError):
        tracker.add_log_directory(str(a_file))


def test_remove_log_directory(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))

    tracker.remove_log_directory(str(log_dir))

    assert str(log_dir) not in tracker.get_log_directories()


def test_get_log_files_finds_recognized_extensions_only(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_bytes(b"line one\n")
    (log_dir / "notes.md").write_bytes(b"not a recognized log extension")

    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))

    paths = {f["path"] for f in tracker.get_log_files()}

    assert str(log_dir / "app.log") in paths
    assert str(log_dir / "notes.md") not in paths


def test_get_log_files_includes_encrypted_logs(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log.enc").write_bytes(b"ciphertext-placeholder")

    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))

    paths = {f["path"] for f in tracker.get_log_files()}

    assert str(log_dir / "app.log.enc") in paths


def test_get_log_files_scans_nested_subdirectories(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    nested = log_dir / "2024" / "01"
    nested.mkdir(parents=True)
    (nested / "app.log").write_bytes(b"nested entry\n")

    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))

    paths = {f["path"] for f in tracker.get_log_files()}

    assert str(nested / "app.log") in paths


def test_save_and_load_metadata_roundtrip(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", "a description", config_manager)
    tracker.add_log_directory(str(log_dir))

    loaded = Tracker.load("my-app", config_manager)

    assert loaded is not None
    assert loaded.name == "my-app"
    assert loaded.description == "a description"
    assert loaded.get_log_directories() == [str(log_dir)]


def test_saving_a_renamed_tracker_leaves_only_the_new_name(tmp_path, config_manager):
    """A rename that kept both entries would list the tracker twice, and leave
    the old name loading a copy that no longer gets updated."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))

    tracker.name = "renamed-app"
    tracker.save_metadata()

    assert Tracker.load("my-app", config_manager) is None
    reloaded = Tracker.load("renamed-app", config_manager)
    assert reloaded.get_log_directories() == [str(log_dir)]
    assert [t.name for t in Tracker.list_trackers(config_manager)] == ["renamed-app"]


def test_load_returns_none_for_unknown_tracker(config_manager):
    assert Tracker.load("does-not-exist", config_manager) is None


def test_list_trackers_returns_all_saved_trackers(config_manager):
    Tracker("tracker-a", config_manager=config_manager).save_metadata()
    Tracker("tracker-b", config_manager=config_manager).save_metadata()

    names = {t.name for t in Tracker.list_trackers(config_manager)}

    assert names == {"tracker-a", "tracker-b"}


def test_set_log_directories_adds_and_removes_in_one_step(tmp_path, config_manager):
    keep = tmp_path / "keep"
    drop = tmp_path / "drop"
    add = tmp_path / "add"
    for d in (keep, drop, add):
        d.mkdir()

    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(keep))
    tracker.add_log_directory(str(drop))

    tracker.set_log_directories([str(keep), str(add)])

    assert set(tracker.get_log_directories()) == {str(keep), str(add)}


def test_set_log_directories_persists_to_metadata(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", config_manager=config_manager)

    tracker.set_log_directories([str(log_dir)])

    reloaded = Tracker.load("my-app", config_manager)
    assert reloaded.get_log_directories() == [str(log_dir)]


def test_set_log_directories_rejects_a_missing_directory(tmp_path, config_manager):
    existing = tmp_path / "logs"
    existing.mkdir()
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(existing))

    with pytest.raises(ValueError):
        tracker.set_log_directories([str(existing), str(tmp_path / "nope")])


def test_set_log_directories_leaves_the_tracker_untouched_when_one_path_is_bad(
        tmp_path, config_manager):
    """Validation happens up front, so a bad path can't half-apply the change."""
    existing = tmp_path / "logs"
    existing.mkdir()
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(existing))

    with pytest.raises(ValueError):
        tracker.set_log_directories([str(tmp_path / "nope")])

    assert tracker.get_log_directories() == [str(existing)]


def test_set_log_directories_rejects_a_file_path(tmp_path, config_manager):
    not_a_dir = tmp_path / "app.log"
    not_a_dir.write_bytes(b"content\n")
    tracker = Tracker("my-app", config_manager=config_manager)

    with pytest.raises(ValueError):
        tracker.set_log_directories([str(not_a_dir)])


def test_set_log_directories_can_clear_everything(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))

    tracker.set_log_directories([])

    assert tracker.get_log_directories() == []


def test_search_logs_finds_matching_lines(tmp_path, config_manager):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_bytes(b"first line\nERROR something broke\nlast line\n")
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))

    results = tracker.search_logs("error")

    assert len(results) == 1
    assert results[0]["line"] == 2
    assert "ERROR" in results[0]["content"]


# ---------------------------------------------------------------------------
# Encrypted logs: which keyring identities to try
# ---------------------------------------------------------------------------


def test_log_encryption_settings_survive_a_save_and_load(tmp_path, config_manager):
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.set_log_encryption("  SomeService ", " some_app ")
    tracker.save_metadata()

    loaded = Tracker.load("my-app", config_manager)

    assert loaded.log_encryption_service == "SomeService"
    assert loaded.log_encryption_app_id == "some_app"


def test_a_tracker_saved_before_log_encryption_loads_with_none_set(config_manager):
    config_manager.save_tracker_metadata("old", {
        "name": "old", "description": "", "created_at": "2026-01-01T00:00:00",
        "log_directories": [],
    })

    loaded = Tracker.load("old", config_manager)

    assert loaded.log_encryption_service == ""
    assert loaded.log_encryption_app_id == ""


def test_key_candidates_guess_the_app_id_from_the_file_then_the_tracker_name(config_manager):
    tracker = Tracker("SD Runner", config_manager=config_manager)

    candidates = tracker.log_key_candidates("/logs/sd_runner_2026-09-30.log.enc")

    # Both guesses land on the same identifier here, so it is tried once.
    assert candidates == [(AppInfo.LOG_ENCRYPTION_SERVICE, "sd_runner")]


def test_key_candidates_try_both_guesses_when_they_differ(config_manager):
    tracker = Tracker("My Tool", config_manager=config_manager)

    candidates = tracker.log_key_candidates("/logs/worker.log.enc")

    assert candidates == [
        (AppInfo.LOG_ENCRYPTION_SERVICE, "worker"),
        (AppInfo.LOG_ENCRYPTION_SERVICE, "my_tool"),
    ]


def test_key_candidates_use_only_an_app_id_set_on_the_tracker(config_manager):
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.set_log_encryption("", "explicit")

    assert tracker.log_key_candidates("/logs/other_2026-09-30.log.enc") == [
        (AppInfo.LOG_ENCRYPTION_SERVICE, "explicit")]


def test_key_candidates_use_a_service_set_on_the_tracker(config_manager):
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.set_log_encryption("OtherService", "")

    assert tracker.log_key_candidates("/logs/app.log.enc")[0] == ("OtherService", "app")


@pytest.mark.parametrize("file_name, expected", [
    ("sd_runner_2026-09-30.log.enc", "sd_runner"),
    ("app-2026-09-30.log.enc", "app"),
    ("app.log.enc", "app"),
    ("2026-09-30.log.enc", ""),
])
def test_app_identifier_from_log_name(file_name, expected):
    assert app_identifier_from_log_name(file_name) == expected
