"""
Unit tests for src.internal.tracker.Tracker: log directory management, log file
discovery, and metadata persistence.
"""

import pytest

from src.internal.tracker import Tracker
from src.utils.config_manager import ConfigManager

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
    assert (tracker.tracker_dir / "metadata.json").exists()


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


def test_load_returns_none_for_unknown_tracker(config_manager):
    assert Tracker.load("does-not-exist", config_manager) is None


def test_list_trackers_returns_all_saved_trackers(config_manager):
    Tracker("tracker-a", config_manager=config_manager).save_metadata()
    Tracker("tracker-b", config_manager=config_manager).save_metadata()

    names = {t.name for t in Tracker.list_trackers(config_manager)}

    assert names == {"tracker-a", "tracker-b"}


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
