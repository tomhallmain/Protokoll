"""
Unit tests for src.internal.log_search.search_files: driving a search across files,
and recording the ones that could not be searched. No Qt.
"""

import pytest

from src.internal import log_search
from src.internal.log_search import search_files
from src.utils.file_handler import FileHandler
from src.utils.globals import AppInfo
from src.utils.translations import _

pytestmark = pytest.mark.unit

LOG_SERVICE = AppInfo.LOG_ENCRYPTION_SERVICE


def _matches_error(content):
    """A stand-in for log_entries.find_matches: one block per line containing ERROR."""
    return [line for line in content.splitlines() if "ERROR" in line]


def _write(path, data):
    path.write_bytes(data)
    return str(path)


def test_files_with_matches_are_reported_in_order(tmp_path):
    a = _write(tmp_path / "a.log", b"ERROR in a\n")
    b = _write(tmp_path / "b.log", b"all clear\n")
    c = _write(tmp_path / "c.log", b"ERROR in c\n")

    outcome = search_files([a, b, c], FileHandler(), _matches_error)

    assert outcome.file_results == [(a, ["ERROR in a"]), (c, ["ERROR in c"])]
    assert outcome.skipped_files == []
    assert outcome.files_searched == 3
    assert outcome.cancelled is False


def test_a_file_failing_validation_is_skipped_as_such(tmp_path):
    binary = _write(tmp_path / "app.log", bytes(range(256)) * 20)

    outcome = search_files([binary], FileHandler(), _matches_error)

    assert outcome.file_results == []
    assert outcome.skipped_files == [
        (binary, log_search.SKIP_VALIDATION,
         _("File may contain corrupted data or non-text content"))]
    assert outcome.files_searched == 1


def test_a_file_too_large_to_read_is_skipped_as_a_read_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(FileHandler, "MAX_FILE_SIZE", 10)
    large = _write(tmp_path / "app.log", b"ERROR " * 100)

    outcome = search_files([large], FileHandler(), _matches_error)

    assert [(path, kind) for path, kind, _reason in outcome.skipped_files] == [
        (large, log_search.SKIP_READ)]


def test_cancelling_stops_before_the_next_file(tmp_path):
    a = _write(tmp_path / "a.log", b"ERROR in a\n")
    b = _write(tmp_path / "b.log", b"ERROR in b\n")
    searched = []

    def find_matches(content):
        searched.append(content)
        return _matches_error(content)

    outcome = search_files([a, b], FileHandler(), find_matches,
                           should_cancel=lambda: len(searched) >= 1)

    assert outcome.cancelled is True
    assert outcome.files_searched == 1
    assert outcome.file_results == [(a, ["ERROR in a"])]


def test_each_file_gets_its_own_key_candidates(tmp_path, write_encrypted_log):
    encrypted = str(write_encrypted_log(
        tmp_path / "app.log.enc", ["ERROR from the encrypted log"], app_identifier="app"))
    asked_for = []

    def key_candidates(file_path):
        asked_for.append(file_path)
        return [(LOG_SERVICE, "app")]

    outcome = search_files([encrypted], FileHandler(), _matches_error,
                           key_candidates=key_candidates)

    assert asked_for == [encrypted]
    assert outcome.file_results == [(encrypted, ["ERROR from the encrypted log"])]
