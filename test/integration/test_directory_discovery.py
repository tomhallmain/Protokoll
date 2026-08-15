"""
Integration test: LogDirectoryFinder.find_log_directories() searching a
constructed directory tree end-to-end - custom directories, "app data"
directories, skip rules, and log-file detection all working together. This is
the engine behind the "find log directories" dialog used when setting up a tracker.
"""

import platform

import pytest

from src.internal.log_directory_finder import LogDirectoryFinder

pytestmark = pytest.mark.integration


def _use_app_data_dirs(monkeypatch, dirs):
    """
    Isolate find_log_directories() to exactly the given base directories.

    get_app_data_directories() alone isn't enough: on Windows, find_log_directories()
    separately hardcodes %ProgramFiles%/%ProgramFiles(x86)% into its search regardless
    of what get_app_data_directories() returns, which walks the real machine's real
    Program Files - patch platform.system() too so that branch never triggers.
    """
    monkeypatch.setattr(LogDirectoryFinder, "get_app_data_directories", staticmethod(lambda: dirs))
    monkeypatch.setattr(platform, "system", lambda: "Linux")


def test_find_log_directories_returns_exact_match(tmp_path, monkeypatch):
    app_dir = tmp_path / "MyApp" / "logs"
    app_dir.mkdir(parents=True)
    (app_dir / "app.log").write_bytes(b"entry\n")
    _use_app_data_dirs(monkeypatch, [str(tmp_path)])

    results = LogDirectoryFinder.find_log_directories("logs")

    assert results["exact_matches"] == [str(app_dir)]
    assert results["potential_matches"] == []


def test_find_log_directories_returns_potential_match_when_no_exact_match(tmp_path, monkeypatch):
    app_dir = tmp_path / "myapp-logs"
    app_dir.mkdir()
    (app_dir / "app.log").write_bytes(b"entry\n")
    _use_app_data_dirs(monkeypatch, [str(tmp_path)])

    results = LogDirectoryFinder.find_log_directories("myapp")

    assert results["exact_matches"] == []
    assert str(app_dir) in results["potential_matches"]


def test_find_log_directories_skips_configured_skip_dirs(tmp_path, monkeypatch):
    skipped_dir = tmp_path / "node_modules" / "logs"
    skipped_dir.mkdir(parents=True)
    (skipped_dir / "app.log").write_bytes(b"entry\n")
    _use_app_data_dirs(monkeypatch, [str(tmp_path)])

    results = LogDirectoryFinder.find_log_directories("logs")

    assert results["exact_matches"] == []


def test_find_log_directories_includes_custom_directories(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom" / "logs"
    custom_dir.mkdir(parents=True)
    (custom_dir / "app.log").write_bytes(b"entry\n")
    LogDirectoryFinder.add_custom_directory(str(custom_dir.parent))
    _use_app_data_dirs(monkeypatch, [])

    results = LogDirectoryFinder.find_log_directories("logs")

    assert results["exact_matches"] == [str(custom_dir)]


def test_find_log_directories_rejects_invalid_query():
    """A query matching a skip-list entry (e.g. a system directory name) is rejected
    up front, before any directory is ever walked."""
    results = LogDirectoryFinder.find_log_directories("node_modules")

    assert results == {"exact_matches": [], "potential_matches": []}
