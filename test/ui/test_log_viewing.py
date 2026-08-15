"""
UI tests (pytest-qt) for MainWindow.display_log_file: the "reading log files" path
that loads a selected file's content into the log viewer.
"""

import os

import pytest

pytestmark = pytest.mark.ui


def _assert_in(needle, haystack):
    """
    Assert membership without pytest dumping the (potentially huge) haystack on failure.
    Computing the bool on its own line matters: `assert needle in haystack, msg` still lets
    pytest's assertion rewriter introspect and print the full `in` comparison's operands
    regardless of the custom message, which is exactly the wall-of-text this is meant to avoid.
    """
    found = needle in haystack
    assert found, f"expected {needle!r} to be present (text length={len(haystack)})"


def _assert_not_in(needle, haystack):
    found = needle in haystack
    assert not found, f"expected {needle!r} to be absent (text length={len(haystack)})"


def test_display_log_file_shows_content_and_header(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"line one\nline two\nline three\n")

    window.display_log_file(str(log_file))

    result = window.log_viewer.toPlainText()
    assert "line one" in result
    assert "line two" in result
    assert "line three" in result
    assert "app.log" in result
    # 3 trailing-newline-terminated lines count as 4 by content.count('\n') + 1;
    # the "Unknown" placeholder header gets replaced with that once read.
    assert "Lines: Unknown" not in result
    assert "Lines: 4" in result


def test_display_log_file_renders_ansi_codes(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"\x1b[31mred error\x1b[0m\n")

    window.display_log_file(str(log_file))

    result = window.log_viewer.toPlainText()
    assert "red error" in result
    assert "\x1b" not in result  # the raw escape code was converted, not passed through


def test_display_log_file_shows_error_for_missing_file(qtbot, window, tmp_path):
    window.display_log_file(str(tmp_path / "does-not-exist.log"))

    assert "Cannot display file" in window.log_viewer.toPlainText()


def test_display_log_file_shows_error_for_binary_file(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    binary_file = log_dir / "app.log"
    binary_file.write_bytes(bytes(range(256)) * 20)

    window.display_log_file(str(binary_file))

    assert "Cannot display file" in window.log_viewer.toPlainText()


def test_display_log_file_truncates_single_very_long_line(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    long_line = b"x" * 1_200_000  # over the 1MB threshold, single line (no newline)
    log_file.write_bytes(long_line)

    window.display_log_file(str(log_file))

    result = window.log_viewer.toPlainText()
    _assert_in("Showing first 10KB", result)
    _assert_in("truncated", result)
    assert len(result) < len(long_line)


def test_display_log_file_loads_large_multiline_file_in_chunks(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    line = "x" * 600
    content = ("\n".join([line] * 2000) + "\n").encode("utf-8")  # over 1MB, over 100 lines
    log_file.write_bytes(content)

    window.display_log_file(str(log_file))

    result = window.log_viewer.toPlainText()
    _assert_in(line, result)
    assert len(result) > 1_000_000  # loaded in full, unlike the single-long-line truncation path
    _assert_in("app.log", result)  # header line intact
    _assert_in("Size:", result)  # size/line-count header line intact too


def test_display_log_file_handles_encrypted_log_without_crashing(qtbot, window, tmp_path):
    """read_file_safe returns raw bytes (not str) for .enc files; display_log_file must
    show that plainly instead of feeding bytes into its str-only content handling."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    encrypted_file = log_dir / "app.log.enc"
    encrypted_file.write_bytes(os.urandom(64))

    window.display_log_file(str(encrypted_file))

    result = window.log_viewer.toPlainText()
    _assert_in("encrypted", result.lower())
