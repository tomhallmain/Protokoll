"""
UI tests (pytest-qt) for the log viewer's automatic refresh: the shown file is
reloaded when it changes on disk, and left alone while anything else is on
screen or when reloading it would mean reading a large file whole.
"""

import gzip

import pytest

from src.internal.tracker import Tracker
from src.utils.config_manager import ConfigManager

pytestmark = pytest.mark.ui

#: Generous: loads run on a worker thread, and a loaded CI machine can be slow.
LOAD_TIMEOUT_MS = 10_000
INTERVAL_MS = 200
#: Long enough for several ticks, to show that none of them refreshed.
QUIET_MS = 1_000


def _enable_auto_refresh(window):
    window.config_manager.set(ConfigManager.AUTO_REFRESH_INTERVAL_MS, INTERVAL_MS)
    window.auto_refresh.setChecked(True)


def _display(qtbot, window, file_path):
    with qtbot.waitSignal(window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        window.display_log_file(str(file_path))


def _append(path, text):
    with open(path, "ab") as f:
        f.write(text.encode("utf-8"))


@pytest.fixture
def shown_window(qtbot, window):
    # The refresh is skipped while the window is hidden.
    window.show()
    qtbot.waitExposed(window)
    return window


def test_appended_lines_are_shown_without_a_manual_refresh(qtbot, shown_window, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"first line\n")
    _enable_auto_refresh(shown_window)
    _display(qtbot, shown_window, log_file)

    _append(log_file, "second line\n")
    with qtbot.waitSignal(shown_window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        pass

    assert "second line" in shown_window.log_viewer.toPlainText()


def test_toggle_is_persisted(shown_window):
    shown_window.auto_refresh.setChecked(True)
    assert shown_window.config_manager.get(ConfigManager.AUTO_REFRESH) is True
    shown_window.auto_refresh.setChecked(False)
    assert shown_window.config_manager.get(ConfigManager.AUTO_REFRESH) is False


def test_nothing_is_refreshed_when_disabled(qtbot, shown_window, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"first line\n")
    shown_window.auto_refresh.setChecked(False)
    _display(qtbot, shown_window, log_file)

    _append(log_file, "second line\n")
    with qtbot.assertNotEmitted(shown_window.log_displayed, wait=QUIET_MS):
        pass

    assert "second line" not in shown_window.log_viewer.toPlainText()


def test_search_results_are_not_replaced_by_a_refresh(qtbot, shown_window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"2024-01-01 INFO needle here\n2024-01-01 INFO other\n")
    tracker = Tracker("my-app", config_manager=shown_window.config_manager)
    tracker.add_log_directory(str(log_dir))
    shown_window.current_tracker = tracker
    _enable_auto_refresh(shown_window)
    shown_window.update_log_files_list()
    shown_window.files_list.setCurrentRow(0)

    shown_window.search_edit.setText("needle")
    with qtbot.waitSignal(shown_window.search_finished, timeout=LOAD_TIMEOUT_MS):
        shown_window.search_logs()
    shown_text = shown_window.log_viewer.toPlainText()

    _append(log_file, "2024-01-01 INFO appended\n")
    with qtbot.assertNotEmitted(shown_window.log_displayed, wait=QUIET_MS):
        pass

    assert shown_window.log_viewer.toPlainText() == shown_text


def test_compressed_file_over_the_cap_is_not_refreshed(qtbot, shown_window, tmp_path):
    log_file = tmp_path / "app.log.gz"
    log_file.write_bytes(gzip.compress(b"first line\n"))
    shown_window.config_manager.set(ConfigManager.AUTO_REFRESH_MAX_FULL_READ_BYTES, 10)
    _enable_auto_refresh(shown_window)
    _display(qtbot, shown_window, log_file)

    log_file.write_bytes(gzip.compress(b"first line\nsecond line\n"))
    with qtbot.assertNotEmitted(shown_window.log_displayed, wait=QUIET_MS):
        pass

    assert "second line" not in shown_window.log_viewer.toPlainText()


def test_refresh_keeps_the_scroll_position_when_not_at_the_bottom(qtbot, shown_window, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_bytes("".join(f"line {i}\n" for i in range(500)).encode("utf-8"))
    _enable_auto_refresh(shown_window)
    _display(qtbot, shown_window, log_file)
    vbar = shown_window.log_viewer.verticalScrollBar()
    assert vbar.maximum() > 20
    vbar.setValue(10)

    _append(log_file, "appended line\n")
    with qtbot.waitSignal(shown_window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        pass

    assert "appended line" in shown_window.log_viewer.toPlainText()
    assert vbar.value() == 10


def test_refresh_follows_the_end_when_at_the_bottom(qtbot, shown_window, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_bytes("".join(f"line {i}\n" for i in range(500)).encode("utf-8"))
    _enable_auto_refresh(shown_window)
    _display(qtbot, shown_window, log_file)
    vbar = shown_window.log_viewer.verticalScrollBar()
    vbar.setValue(vbar.maximum())

    _append(log_file, "".join(f"more {i}\n" for i in range(50)))
    with qtbot.waitSignal(shown_window.log_displayed, timeout=LOAD_TIMEOUT_MS):
        pass

    assert vbar.value() == vbar.maximum()
