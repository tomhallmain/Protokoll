"""
Unit tests for src.internal.log_directory_finder.LogDirectoryFinder: custom
directory list management and the individual candidate/skip heuristics.
End-to-end find_log_directories() coverage lives in
test/integration/test_directory_discovery.py.
"""

import os

import pytest

from src.internal.log_directory_finder import LogDirectoryFinder

pytestmark = pytest.mark.unit


def test_add_custom_directory_success(tmp_path):
    success, message = LogDirectoryFinder.add_custom_directory(str(tmp_path))

    assert success is True
    assert str(tmp_path) in LogDirectoryFinder.get_custom_directories()


def test_add_custom_directory_rejects_nonexistent_path(tmp_path):
    success, message = LogDirectoryFinder.add_custom_directory(str(tmp_path / "missing"))

    assert success is False
    assert LogDirectoryFinder.get_custom_directories() == []


def test_add_custom_directory_rejects_duplicate(tmp_path):
    LogDirectoryFinder.add_custom_directory(str(tmp_path))

    success, message = LogDirectoryFinder.add_custom_directory(str(tmp_path))

    assert success is False
    assert LogDirectoryFinder.get_custom_directories() == [str(tmp_path)]


def test_remove_custom_directory_success(tmp_path):
    LogDirectoryFinder.add_custom_directory(str(tmp_path))

    success, message = LogDirectoryFinder.remove_custom_directory(str(tmp_path))

    assert success is True
    assert LogDirectoryFinder.get_custom_directories() == []


def test_remove_custom_directory_not_found(tmp_path):
    success, message = LogDirectoryFinder.remove_custom_directory(str(tmp_path))

    assert success is False


def test_get_custom_directories_empty_by_default():
    assert LogDirectoryFinder.get_custom_directories() == []


def test_validate_search_query_rejects_empty_string():
    is_valid, reason = LogDirectoryFinder.validate_search_query("")
    assert is_valid is False


def test_validate_search_query_rejects_system_directory_name():
    is_valid, reason = LogDirectoryFinder.validate_search_query("node_modules")
    assert is_valid is False


def test_validate_search_query_accepts_normal_app_name():
    is_valid, reason = LogDirectoryFinder.validate_search_query("MyApplication")
    assert is_valid is True


def test_is_potential_candidate_matches_log_pattern_with_app_name_in_path():
    assert LogDirectoryFinder._is_potential_candidate("/home/user/myapp-logs", "myapp") is True


def test_is_potential_candidate_rejects_log_pattern_without_app_name():
    assert LogDirectoryFinder._is_potential_candidate("/home/user/otherapp-logs", "myapp") is False


def test_is_potential_candidate_rejects_short_unrelated_name():
    assert LogDirectoryFinder._is_potential_candidate("/home/user/misc", "myapp") is False


def test_should_skip_respects_max_depth(tmp_path):
    shallow = str(tmp_path / "a")
    deep = str(tmp_path / "a" / "b")

    assert LogDirectoryFinder._should_skip(shallow, str(tmp_path), max_depth=0) is False
    assert LogDirectoryFinder._should_skip(deep, str(tmp_path), max_depth=0) is True


def test_should_skip_skips_hidden_directories():
    hidden = os.path.join("some", "path", ".git")
    assert LogDirectoryFinder._should_skip(hidden, "some", max_depth=5) is True


def test_should_skip_allows_conventional_os_dot_directories():
    allowed = os.path.join("some", "path", ".config")
    assert LogDirectoryFinder._should_skip(allowed, "some", max_depth=5) is False


def test_should_skip_skips_configured_skip_dirs():
    node_modules = os.path.join("some", "path", "node_modules")
    assert LogDirectoryFinder._should_skip(node_modules, "some", max_depth=5) is True


def test_has_log_files_finds_nested_log_file(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "app.log").write_bytes(b"entry\n")

    assert LogDirectoryFinder._has_log_files(str(tmp_path), max_depth=5) is True


def test_has_log_files_false_when_none_present(tmp_path):
    (tmp_path / "readme.md").write_text("no logs here")

    assert LogDirectoryFinder._has_log_files(str(tmp_path), max_depth=5) is False
