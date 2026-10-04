"""
UI tests (pytest-qt) for MainWindow.display_log_file: the "reading log files" path
that loads a selected file's content into the log viewer.
"""

import re

import pytest
from PyQt6.QtCore import QPoint

from src.internal.tracker import Tracker
from src.utils.file_handler import FileHandler
from src.utils.translations import _

pytestmark = pytest.mark.ui

#: The viewer's notice that only the end of a file is on screen.
_TAIL_NOTICE = ("⏱️  Showing the last {0} of {1}. Earlier lines are not loaded - "
                "open the file in an editor to see them.")


#: Space characters the rich-text rendering turns into an ordinary space. A
#: translation is free to use one -- German writes "10 KB" with a narrow
#: no-break space -- and it does not survive to toPlainText().
_SPACES = "\u00a0\u2009\u202f"


def _rendered(text):
    """Normalise text the way the viewer's HTML rendering does.

    Messages reach the log viewer as HTML, where the spaces above become
    ordinary ones and runs of them collapse to a single space, so a message
    does not appear on screen character for character.
    """
    for space in _SPACES:
        text = text.replace(space, " ")
    return re.sub(r" {2,}", " ", text)


def _assert_in(needle, haystack):
    """
    Assert membership without pytest dumping the (potentially huge) haystack on failure.
    Computing the bool on its own line matters: `assert needle in haystack, msg` still lets
    pytest's assertion rewriter introspect and print the full `in` comparison's operands
    regardless of the custom message, which is exactly the wall-of-text this is meant to avoid.
    """
    found = _rendered(needle) in _rendered(haystack)
    assert found, f"expected {needle!r} to be present (text length={len(haystack)})"


def _assert_not_in(needle, haystack):
    found = _rendered(needle) in _rendered(haystack)
    assert not found, f"expected {needle!r} to be absent (text length={len(haystack)})"


def _msg_start(msgid):
    """The literal opening of a translated message, before its first placeholder.

    Assertions compare against what _() returns, so they keep working when a
    locale is installed rather than pinning the English source.
    """
    return _(msgid).split("{0}")[0]


def test_display_log_file_shows_content_and_header(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"line one\nline two\nline three\n")

    _display(qtbot, window, str(log_file))

    result = window.log_viewer.toPlainText()
    assert "line one" in result
    assert "line two" in result
    assert "line three" in result
    assert "app.log" in result
    # 3 trailing-newline-terminated lines count as 4 by content.count('\n') + 1;
    # the "Unknown" placeholder header gets replaced with that once read.
    assert f'{_("Lines")}: {_("Unknown")}' not in result
    assert f'{_("Lines")}: 4' in result


def test_display_log_file_renders_ansi_codes(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"\x1b[31mred error\x1b[0m\n")

    _display(qtbot, window, str(log_file))

    result = window.log_viewer.toPlainText()
    assert "red error" in result
    assert "\x1b" not in result  # the raw escape code was converted, not passed through


def test_display_log_file_shows_error_for_missing_file(qtbot, window, tmp_path):
    _display(qtbot, window, str(tmp_path / "does-not-exist.log"))

    _assert_in(_msg_start("⚠️  Cannot display file: {0}"), window.log_viewer.toPlainText())


def test_display_log_file_shows_error_for_binary_file(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    binary_file = log_dir / "app.log"
    binary_file.write_bytes(bytes(range(256)) * 20)

    _display(qtbot, window, str(binary_file))

    _assert_in(_msg_start("⚠️  Cannot display file: {0}"), window.log_viewer.toPlainText())


def test_display_log_file_truncates_single_very_long_line(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    long_line = b"x" * 1_200_000  # over the 1MB threshold, single line (no newline)
    log_file.write_bytes(long_line)

    _display(qtbot, window, str(log_file))

    result = window.log_viewer.toPlainText()
    _assert_in(_("⚠️  File contains a very long line. Showing first 10KB:"), result)
    _assert_in(_msg_start("... (truncated, original length: {0} characters)"), result)
    assert len(result) < len(long_line)


def test_display_log_file_loads_large_multiline_file_in_chunks(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    line = "x" * 600
    content = ("\n".join([line] * 2000) + "\n").encode("utf-8")  # over 1MB, over 100 lines
    log_file.write_bytes(content)

    _display(qtbot, window, str(log_file))

    result = window.log_viewer.toPlainText()
    _assert_in(line, result)
    assert len(result) > 1_000_000  # loaded in full, unlike the single-long-line truncation path
    _assert_in("app.log", result)  # header line intact
    _assert_in(_msg_start("Size: {0}"), result)  # size/line-count header line intact too


#: Generous: the file is read on a worker thread, and a loaded CI machine can be slow.
LOAD_TIMEOUT_MS = 10_000


def _display(qtbot, window, file_path):
    """Display *file_path* and wait for it to reach the viewer."""
    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.display_log_file(file_path)


def _select_tracker_for(window, log_dir, **encryption):
    tracker = Tracker("my-app", config_manager=window.config_manager)
    if encryption:
        tracker.set_log_encryption(encryption.get("service", ""), encryption.get("app_id", ""))
    tracker.add_log_directory(str(log_dir))
    window.current_tracker = tracker
    return tracker


def test_display_log_file_decrypts_an_encrypted_log(qtbot, window, tmp_path, write_encrypted_log):
    """No settings on the tracker: the app ID is guessed from the file name."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    encrypted_file = write_encrypted_log(
        log_dir / "app_2026-09-30.log.enc", ["INFO started", "ERROR it broke"], app_identifier="app")
    _select_tracker_for(window, log_dir)

    _display(qtbot, window, str(encrypted_file))

    result = window.log_viewer.toPlainText()
    _assert_in("INFO started", result)
    _assert_in("ERROR it broke", result)
    _assert_in(_("🔒 Encrypted log, decrypted for viewing"), result)


def test_display_log_file_explains_an_encrypted_log_it_cannot_open(
        qtbot, window, tmp_path, write_encrypted_log):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    encrypted_file = write_encrypted_log(log_dir / "app.log.enc", ["INFO secret"], app_identifier="app")
    _select_tracker_for(window, log_dir, app_id="wrong")

    _display(qtbot, window, str(encrypted_file))

    result = window.log_viewer.toPlainText()
    _assert_not_in("INFO secret", result)
    _assert_in(_msg_start("This log is encrypted, and no key found for it opens it (tried: {0})."), result)


def test_display_log_file_shows_only_the_tail_of_a_large_file(qtbot, window, tmp_path):
    """The whole point of the tail read: what is on screen is the end of the
    file, and the cost of getting there does not grow with the file."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"".join(b"line %05d\n" % i for i in range(2000)))
    window.config_manager.set("log_viewer.max_load_bytes", 2048)

    _display(qtbot, window, str(log_file))

    result = window.log_viewer.toPlainText()
    _assert_in("line 01999", result)
    _assert_not_in("line 00000", result)
    _assert_in(_msg_start(_TAIL_NOTICE), result)
    _assert_in(f'{_("Lines shown")}:', result)


def test_display_log_file_does_not_announce_a_tail_for_a_small_file(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"line one\nline two\n")
    window.config_manager.set("log_viewer.max_load_bytes", 2048)

    _display(qtbot, window, str(log_file))

    result = window.log_viewer.toPlainText()
    _assert_not_in(_msg_start(_TAIL_NOTICE), result)
    _assert_in(f'{_("Lines")}: 3', result)


def _wait_for_all_workers(qtbot, window):
    """Wait until every worker has stopped and its result, stale or not, has arrived."""
    qtbot.waitUntil(
        lambda: all(w.isFinished() and w.delivered for w in window._workers),
        timeout=LOAD_TIMEOUT_MS)


def _counting(monkeypatch, method_name):
    """Wrap a FileHandler method so each call's file path is recorded."""
    calls = []
    original = getattr(FileHandler, method_name)

    def wrapper(self, file_path, *args, **kwargs):
        calls.append(file_path)
        return original(self, file_path, *args, **kwargs)

    monkeypatch.setattr(FileHandler, method_name, wrapper)
    return calls


def test_a_newer_request_replaces_a_load_still_in_flight(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    first = log_dir / "first.log"
    first.write_bytes(b"content of the first file\n")
    second = log_dir / "second.log"
    second.write_bytes(b"content of the second file\n")

    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS,
                          check_params_cb=lambda path: path == str(second)):
        window.display_log_file(str(first))
        window.display_log_file(str(second))
    _wait_for_all_workers(qtbot, window)

    result = window.log_viewer.toPlainText()
    _assert_in("content of the second file", result)
    _assert_not_in("content of the first file", result)


def test_refresh_reads_the_selected_file_once(qtbot, window, tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"line one\n")
    _select_tracker_for(window, log_dir)
    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.update_log_files_list()
    _wait_for_all_workers(qtbot, window)
    reads = _counting(monkeypatch, "read_tail_safe")

    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.refresh_current_log()
    _wait_for_all_workers(qtbot, window)

    assert reads == [str(log_file)]


def test_viewing_a_file_inspects_it_once(qtbot, window, tmp_path, monkeypatch):
    """Validation's file info is handed to the read rather than gathered twice."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"line one\n")
    inspections = _counting(monkeypatch, "get_file_info")

    _display(qtbot, window, str(log_file))

    assert inspections == [str(log_file)]


def _numbered_lines(count):
    return b"".join(b"line %05d\n" % i for i in range(count))


def _load_earlier(qtbot, window):
    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.load_earlier_lines()


def test_load_earlier_lines_is_offered_only_for_a_partly_shown_plain_file(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    large = log_dir / "large.log"
    large.write_bytes(_numbered_lines(2000))
    small = log_dir / "small.log"
    small.write_bytes(b"line one\n")
    window.config_manager.set("log_viewer.max_load_bytes", 2048)

    _display(qtbot, window, str(large))
    assert not window.load_earlier_btn.isHidden()

    _display(qtbot, window, str(small))
    assert window.load_earlier_btn.isHidden()


def test_load_earlier_lines_prepends_the_preceding_lines(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(_numbered_lines(2000))
    window.config_manager.set("log_viewer.max_load_bytes", 2048)
    _display(qtbot, window, str(log_file))
    _assert_not_in("line 01700", window.log_viewer.toPlainText())

    _load_earlier(qtbot, window)

    result = window.log_viewer.toPlainText()
    _assert_in("line 01700", result)
    _assert_in("line 01999", result)
    _assert_not_in("line 01500", result)
    # Contiguous: the line before the old start is followed by the old start.
    _assert_in("line 01795\nline 01796", result)


def test_load_earlier_lines_until_the_start_of_the_file(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(_numbered_lines(2000))
    window.config_manager.set("log_viewer.max_load_bytes", 2048)
    _display(qtbot, window, str(log_file))

    for _attempt in range(20):
        if window.load_earlier_btn.isHidden():
            break
        _load_earlier(qtbot, window)

    result = window.log_viewer.toPlainText()
    assert window.load_earlier_btn.isHidden()
    _assert_in("line 00000", result)
    _assert_in("line 01999", result)
    _assert_not_in(_msg_start(_TAIL_NOTICE), result)
    assert result.count("line 01000") == 1


def test_load_earlier_lines_starts_over_when_the_file_was_replaced(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(_numbered_lines(2000))
    window.config_manager.set("log_viewer.max_load_bytes", 2048)
    _display(qtbot, window, str(log_file))
    log_file.write_bytes(b"".join(b"rotated %05d\n" % i for i in range(500)))

    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.load_earlier_lines()
    _wait_for_all_workers(qtbot, window)

    result = window.log_viewer.toPlainText()
    _assert_in("rotated 00499", result)
    _assert_not_in("line 01999", result)


def _first_shown_line(file_path, max_bytes):
    """The line a tail view of *file_path* starts at, read the way the viewer reads it."""
    _success, content, _info = FileHandler().read_tail_safe(str(file_path), max_bytes)
    return content.splitlines()[0]


def _line_before(numbered_line):
    """"line 01814" -> "line 01813"."""
    return "line %05d" % (int(numbered_line.split()[1]) - 1)


def _large_plain_log(tmp_path, window, line_count=2000):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(_numbered_lines(line_count))
    window.config_manager.set("log_viewer.max_load_bytes", 2048)
    return log_file


def test_load_earlier_lines_scrolls_to_where_the_previous_view_began(qtbot, window, tmp_path):
    log_file = _large_plain_log(tmp_path, window)
    old_first = _first_shown_line(log_file, 2048)
    with qtbot.waitExposed(window):
        window.show()
    _display(qtbot, window, str(log_file))

    _load_earlier(qtbot, window)

    # A few pixels in, so the document margin is not what gets hit. One line of
    # slack either way of the boundary: the point is that the reader is left at
    # the join, not at the top or bottom of everything now loaded.
    top_line = window.log_viewer.cursorForPosition(QPoint(5, 5)).block().text()
    assert top_line in (old_first, _line_before(old_first))


def test_load_earlier_lines_joins_up_on_a_log_that_has_grown(qtbot, window, tmp_path):
    """Appending to a log does not move the bytes already shown, so the offsets
    the view keeps still point at the right place."""
    log_file = _large_plain_log(tmp_path, window)
    old_first = _first_shown_line(log_file, 2048)
    _display(qtbot, window, str(log_file))
    with open(log_file, "ab") as f:
        f.write(b"".join(b"line %05d\n" % i for i in range(2000, 2100)))

    _load_earlier(qtbot, window)

    result = window.log_viewer.toPlainText()
    _assert_in(f"{_line_before(old_first)}\n{old_first}", result)
    _assert_in("line 01999", result)


def test_a_failed_earlier_read_leaves_the_view_as_it_was(qtbot, window, tmp_path, monkeypatch):
    log_file = _large_plain_log(tmp_path, window)
    _display(qtbot, window, str(log_file))
    before = window.log_viewer.toPlainText()
    monkeypatch.setattr(FileHandler, "read_range_safe",
                        lambda self, *args, **kwargs: (False, "", {"error": "disk on fire"}))

    _load_earlier(qtbot, window)

    assert window.log_viewer.toPlainText() == before
    assert not window.load_earlier_btn.isHidden()  # still offered, so it can be retried


def test_an_earlier_read_superseded_by_another_file_is_dropped(qtbot, window, tmp_path):
    log_file = _large_plain_log(tmp_path, window)
    other = log_file.parent / "other.log"
    other.write_bytes(b"content of the other file\n")
    _display(qtbot, window, str(log_file))

    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS,
                          check_params_cb=lambda path: path == str(other)):
        window.load_earlier_lines()
        window.display_log_file(str(other))
    _wait_for_all_workers(qtbot, window)

    result = window.log_viewer.toPlainText()
    _assert_in("content of the other file", result)
    _assert_not_in("line 01", result)
    assert window.load_earlier_btn.isHidden()


def test_load_earlier_lines_is_withdrawn_for_search_results_and_back_after(qtbot, window, tmp_path):
    log_file = _large_plain_log(tmp_path, window)
    _select_tracker_for(window, log_file.parent)
    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.update_log_files_list()
    assert not window.load_earlier_btn.isHidden()

    window.search_edit.setText("line 01999")
    with qtbot.waitSignal(window.search_finished, timeout=LOAD_TIMEOUT_MS):
        window.search_logs()
    assert window.load_earlier_btn.isHidden()

    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.clear_search_and_reload()
    assert not window.load_earlier_btn.isHidden()


def test_load_earlier_lines_is_not_offered_for_an_encrypted_log(
        qtbot, window, tmp_path, write_encrypted_log):
    """Encrypted records cannot be found from an offset, so only the tail is offered."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    encrypted_file = write_encrypted_log(
        log_dir / "app_2026-09-30.log.enc",
        ["INFO record %05d" % i for i in range(500)], app_identifier="app")
    _select_tracker_for(window, log_dir)
    window.config_manager.set("log_viewer.max_load_bytes", 2048)

    _display(qtbot, window, str(encrypted_file))

    _assert_in(_msg_start(_TAIL_NOTICE), window.log_viewer.toPlainText())
    assert window.load_earlier_btn.isHidden()
