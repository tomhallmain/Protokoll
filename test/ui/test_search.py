"""
UI tests (pytest-qt) for MainWindow's search feature: plain-text/regex matching,
multi-line entry grouping, before/after context grouping, and the "search all
files" mode.

These cover the wiring: toggles and config reaching the search core, and results
reaching the log viewer. The entry-splitting and match-grouping rules themselves are
pure functions tested directly in test/unit/test_log_entries.py.

Fixtures here are deliberately log-shaped - every line carries a timestamp, so each
one is its own logical entry and a test can isolate context/regex/line-number
behaviour from entry grouping. Tests that exercise grouping itself use fixtures with
genuine continuation lines.
"""

import pytest
from PyQt6.QtCore import Qt

from src.internal.tracker import Tracker
from src.utils.translations import _

pytestmark = pytest.mark.ui
def _msg_start(msgid):
    """The literal opening of a translated message, before its first placeholder.

    Assertions compare against what _() returns, so they keep working when a
    locale is installed rather than pinning the English source.
    """
    return _(msgid).split("{0}")[0]


def _select_tracker_with_log_file(window, tmp_path, content, filename="app.log"):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / filename
    # write_bytes: read_file_safe reads in binary mode, so write_text's \n -> \r\n
    # translation on Windows would otherwise leak stray \r characters into search results.
    log_file.write_bytes(content.encode("utf-8"))

    tracker = Tracker("my-app", config_manager=window.config_manager)
    tracker.add_log_directory(str(log_dir))
    window.current_tracker = tracker
    window.update_log_files_list()
    window.files_list.setCurrentRow(0)

    return log_file


def test_plain_text_search_finds_matching_line(qtbot, window, tmp_path):
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:01 INFO first line\n"
        "2026-08-24 10:00:02 ERROR something broke\n"
        "2026-08-24 10:00:03 INFO last line\n"
    )

    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ERROR something broke" in result_text
    assert "first line" not in result_text
    assert "last line" not in result_text


def test_search_via_return_key(qtbot, window, tmp_path):
    """Proves the returnPressed -> search_logs wiring, not just the search logic itself."""
    _select_tracker_with_log_file(window, tmp_path, "alpha\nbeta\ngamma\n")

    qtbot.keyClicks(window.search_edit, "beta")
    qtbot.keyClick(window.search_edit, Qt.Key.Key_Return)

    result_text = window.log_viewer.toPlainText()
    assert "beta" in result_text
    assert "alpha" not in result_text


def test_regex_search(qtbot, window, tmp_path):
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:01 INFO code 200 ok\n"
        "2026-08-24 10:00:02 WARNING code 404 missing\n"
        "2026-08-24 10:00:03 ERROR code 500 error\n"
    )

    window.use_regex.setChecked(True)
    window.search_edit.setText(r"code (4|5)\d\d")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "404" in result_text
    assert "500" in result_text
    assert "200" not in result_text


def test_context_lines_pulls_in_surrounding_lines(qtbot, window, tmp_path):
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:01 INFO line 1\n"
        "2026-08-24 10:00:02 INFO line 2\n"
        "2026-08-24 10:00:03 ERROR line 3\n"
        "2026-08-24 10:00:04 INFO line 4\n"
        "2026-08-24 10:00:05 INFO line 5\n"
    )

    window.context_before.setValue(1)
    window.context_after.setValue(1)
    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "line 2" in result_text
    assert "ERROR line 3" in result_text
    assert "line 4" in result_text
    assert "line 1" not in result_text
    assert "line 5" not in result_text


def test_context_lines_zero_matches_legacy_behavior(qtbot, window, tmp_path):
    """context_before/after default to 0, which must reproduce pre-context-lines output exactly."""
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:01 INFO line 1\n"
        "2026-08-24 10:00:02 INFO line 2\n"
        "2026-08-24 10:00:03 ERROR line 3\n"
        "2026-08-24 10:00:04 INFO line 4\n"
        "2026-08-24 10:00:05 INFO line 5\n"
    )

    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ERROR line 3" in result_text
    assert "line 2" not in result_text
    assert "line 4" not in result_text


def test_no_matches_shows_message(qtbot, window, tmp_path):
    _select_tracker_with_log_file(window, tmp_path, "nothing interesting here\n")

    window.search_edit.setText("nonexistent-term")
    window.search_logs()

    assert _msg_start("No matches found for '{0}' ({1}, {2})") in window.log_viewer.toPlainText()


def test_search_all_files_reports_matches_across_files(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "a.log").write_bytes(b"ERROR in file a\n")
    (log_dir / "b.log").write_bytes(b"all clear\n")

    tracker = Tracker("my-app", config_manager=window.config_manager)
    tracker.add_log_directory(str(log_dir))
    window.current_tracker = tracker
    window.search_all_files.setChecked(True)

    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "a.log" in result_text
    assert "ERROR in file a" in result_text
    assert "b.log" not in result_text


def test_toggle_state_persisted_to_config(qtbot, window):
    window.use_regex.setChecked(True)
    window.context_before.setValue(3)

    assert window.config_manager.get("search.use_regex") is True
    assert window.config_manager.get("search.context_before") == 3


def test_context_lines_merges_overlapping_windows_into_one_block(qtbot, window, tmp_path):
    """Two matches whose context windows touch must produce one combined block, not
    two separate ones with a '--' separator and/or duplicated lines between them."""
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:00 INFO line0\n"
        "2026-08-24 10:00:01 INFO line1\n"
        "2026-08-24 10:00:02 ERROR at idx2\n"
        "2026-08-24 10:00:03 INFO line3\n"
        "2026-08-24 10:00:04 ERROR at idx4\n"
        "2026-08-24 10:00:05 INFO line5\n"
        "2026-08-24 10:00:06 INFO line6\n"
    )

    window.context_before.setValue(1)
    window.context_after.setValue(1)
    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    rendered_lines = result_text.split("\n")
    assert "--" not in rendered_lines
    assert "line1" in result_text
    assert "ERROR at idx2" in result_text
    assert "line3" in result_text
    assert "ERROR at idx4" in result_text
    assert "line5" in result_text
    assert "line0" not in result_text
    assert "line6" not in result_text
    assert _("File: {0} Found {1} matches").format("app.log", 2) in result_text


def test_context_lines_separates_non_adjacent_blocks(qtbot, window, tmp_path):
    """Matches far enough apart that their context windows don't touch must render as
    two separate blocks with a '--' separator, and exclude the lines between them."""
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:00 INFO line0\n"
        "2026-08-24 10:00:01 ERROR first\n"
        "2026-08-24 10:00:02 INFO line2\n"
        "2026-08-24 10:00:03 INFO line3\n"
        "2026-08-24 10:00:04 INFO line4\n"
        "2026-08-24 10:00:05 INFO line5\n"
        "2026-08-24 10:00:06 ERROR second\n"
        "2026-08-24 10:00:07 INFO line7\n"
    )

    window.context_before.setValue(1)
    window.context_after.setValue(1)
    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    rendered_lines = result_text.split("\n")
    assert "--" in rendered_lines
    assert "line0" in result_text
    assert "ERROR first" in result_text
    assert "line2" in result_text
    assert "line5" in result_text
    assert "ERROR second" in result_text
    assert "line7" in result_text
    assert "line3" not in result_text
    assert "line4" not in result_text


def test_context_before_clipped_at_file_start(qtbot, window, tmp_path):
    """A match on the first line with context_before larger than the file must clip to 0,
    not wrap around to negative indices and pull in lines from the end of the file."""
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:01 ERROR first line\n"
        "2026-08-24 10:00:02 INFO middle1\n"
        "2026-08-24 10:00:03 INFO middle2\n"
        "2026-08-24 10:00:04 INFO middle3\n"
        "2026-08-24 10:00:05 INFO last line\n"
    )

    window.context_before.setValue(3)
    window.context_after.setValue(0)
    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ERROR first line" in result_text
    assert "last line" not in result_text
    assert "middle3" not in result_text


def test_context_after_clipped_at_file_end(qtbot, window, tmp_path):
    """A match on the last line with context_after larger than the file must clip to the
    last line, not raise an IndexError past the end of the content."""
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:01 INFO first line\n"
        "2026-08-24 10:00:02 INFO middle1\n"
        "2026-08-24 10:00:03 INFO middle2\n"
        "2026-08-24 10:00:04 ERROR last line\n"
    )

    window.context_before.setValue(0)
    window.context_after.setValue(5)
    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ERROR last line" in result_text
    assert "first line" not in result_text
    assert "middle1" not in result_text
    assert "middle2" not in result_text


def test_search_all_files_applies_context_lines_per_file(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "a.log").write_bytes(
        b"2026-08-24 10:00:01 INFO before a\n"
        b"2026-08-24 10:00:02 ERROR in a\n"
        b"2026-08-24 10:00:03 INFO after a\n"
    )
    (log_dir / "b.log").write_bytes(
        b"2026-08-24 10:00:01 INFO before b\n"
        b"2026-08-24 10:00:02 ERROR in b\n"
        b"2026-08-24 10:00:03 INFO after b\n"
    )

    tracker = Tracker("my-app", config_manager=window.config_manager)
    tracker.add_log_directory(str(log_dir))
    window.current_tracker = tracker
    window.search_all_files.setChecked(True)
    window.context_before.setValue(1)
    window.context_after.setValue(1)

    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "before a" in result_text
    assert "ERROR in a" in result_text
    assert "after a" in result_text
    assert "before b" in result_text
    assert "ERROR in b" in result_text
    assert "after b" in result_text


def test_limit_to_line_start_matches_only_after_log_level_prefix(qtbot, window, tmp_path):
    """"Limit to line start" strips the leading timestamp/log-level prefix, then requires
    the search text at the start of what's left - not just anywhere in the line."""
    _select_tracker_with_log_file(
        window, tmp_path,
        "2024-01-01 ERROR database connection lost\n"
        "2024-01-01 ERROR something failed in database\n"
    )

    window.limit_to_line_start.setChecked(True)
    window.search_edit.setText("database")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "database connection lost" in result_text
    assert "something failed in database" not in result_text


def test_limit_to_line_start_disabled_matches_anywhere_in_line(qtbot, window, tmp_path):
    """Contrast case for the test above: with the toggle off, the same text matches
    as a plain substring anywhere in the line."""
    _select_tracker_with_log_file(window, tmp_path, "2024-01-01 ERROR something failed in database\n")

    window.limit_to_line_start.setChecked(False)
    window.search_edit.setText("database")
    window.search_logs()

    assert "something failed in database" in window.log_viewer.toPlainText()


def test_line_numbers_render_inline_with_content(qtbot, window, tmp_path):
    """Regression test: line numbers must render to the left of the matched content on
    the same line, not as a separate line above it (see main_window.py's _append_search_match)."""
    _select_tracker_with_log_file(
        window, tmp_path,
        "2026-08-24 10:00:01 INFO first\n"
        "2026-08-24 10:00:02 ERROR second\n"
        "2026-08-24 10:00:03 INFO third\n"
    )

    window.show_line_numbers.setChecked(True)
    window.search_edit.setText("error")
    window.search_logs()

    rendered_lines = window.log_viewer.toPlainText().split("\n")
    matching_lines = [line for line in rendered_lines if "ERROR second" in line]
    assert len(matching_lines) == 1
    assert matching_lines[0].startswith("2:")


TRACEBACK_LOG = (
    "2026-08-24 10:00:01 INFO Starting up\n"
    "2026-08-24 10:00:02 ERROR Failed to connect\n"
    "Traceback (most recent call last):\n"
    '  File "app.py", line 12, in <module>\n'
    "    connect()\n"
    "ConnectionError: refused\n"
    "2026-08-24 10:00:03 INFO Retrying\n"
)


def test_match_inside_traceback_returns_whole_entry(qtbot, window, tmp_path):
    """The point of the feature: a term found on a continuation line returns the entry
    it belongs to - header included - not the isolated line."""
    _select_tracker_with_log_file(window, tmp_path, TRACEBACK_LOG)

    window.search_edit.setText("ConnectionError")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ERROR Failed to connect" in result_text
    assert "Traceback (most recent call last):" in result_text
    assert "ConnectionError: refused" in result_text
    # Neighbouring entries stay out with no context configured.
    assert "Starting up" not in result_text
    assert "Retrying" not in result_text


def test_multiline_entry_counts_as_a_single_match(qtbot, window, tmp_path):
    """Two matching physical lines inside one entry are one match, not two."""
    _select_tracker_with_log_file(window, tmp_path, TRACEBACK_LOG)

    window.search_edit.setText("connect")
    window.search_logs()

    assert _("File: {0} Found {1} matches").format("app.log", 1) in window.log_viewer.toPlainText()


def test_multiline_disabled_returns_only_the_matching_line(qtbot, window, tmp_path):
    """The pre-grouping per-line path stays available behind the toggle."""
    _select_tracker_with_log_file(window, tmp_path, TRACEBACK_LOG)

    window.multiline_entries.setChecked(False)
    window.search_edit.setText("ConnectionError")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ConnectionError: refused" in result_text
    assert "ERROR Failed to connect" not in result_text
    assert "Traceback (most recent call last):" not in result_text


def test_context_counts_entries_not_physical_lines(qtbot, window, tmp_path):
    """One entry of context pulls in a whole neighbouring entry, however many
    physical lines it spans."""
    _select_tracker_with_log_file(window, tmp_path, TRACEBACK_LOG)

    window.context_before.setValue(1)
    window.context_after.setValue(1)
    window.search_edit.setText("ConnectionError")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "Starting up" in result_text
    assert "Retrying" in result_text


def test_long_entry_is_truncated_at_max_entry_lines(qtbot, window, tmp_path):
    """One deep stack trace must not flood the results view."""
    frames = "".join(f"    frame {i}\n" for i in range(10))
    _select_tracker_with_log_file(window, tmp_path, "2026-08-24 10:00:02 ERROR boom\n" + frames)
    window.config_manager.set("search.max_entry_lines", 3)

    window.search_edit.setText("boom")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ERROR boom" in result_text
    assert "frame 1" in result_text
    assert "frame 9" not in result_text
    assert "more lines truncated" in result_text


def test_multiline_toggle_persisted_to_config(qtbot, window):
    window.multiline_entries.setChecked(False)
    assert window.config_manager.get("search.multiline_entries") is False

    window.multiline_entries.setChecked(True)
    assert window.config_manager.get("search.multiline_entries") is True


def test_search_all_files_includes_encrypted_logs(qtbot, window, tmp_path, write_encrypted_log):
    log_file = _select_tracker_with_log_file(
        window, tmp_path, "2026-08-24 10:00:01 INFO plain line\n")
    write_encrypted_log(
        log_file.parent / "app.log.enc",
        ["2026-08-24 10:00:02 ERROR from the encrypted log"], app_identifier="app")
    window.search_all_files.setChecked(True)

    window.search_edit.setText("error")
    window.search_logs()

    result_text = window.log_viewer.toPlainText()
    assert "ERROR from the encrypted log" in result_text
    assert "plain line" not in result_text
