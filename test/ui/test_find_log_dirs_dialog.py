"""
UI tests (pytest-qt) for FindLogDirsDialog and its background
DirectorySearchThread. LogDirectoryFinder.find_log_directories is monkeypatched
throughout so the dialog's background thread never touches the real filesystem -
same isolation concern as test/integration/test_directory_discovery.py, just
reached through the dialog this time instead of calling the finder directly.
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QMessageBox

from src.internal.log_directory_finder import LogDirectoryFinder
from src.ui.find_log_dirs_dialog import FindLogDirsDialog

pytestmark = pytest.mark.ui


def _stub_find_log_directories(monkeypatch, results=None, error=None):
    if error is not None:
        def fake_find(app_name, max_depth=3):
            raise RuntimeError(error)
    else:
        results = results or {"exact_matches": [], "potential_matches": []}

        def fake_find(app_name, max_depth=3):
            return results

    monkeypatch.setattr(LogDirectoryFinder, "find_log_directories", staticmethod(fake_find))


def test_search_complete_populates_exact_and_potential_lists(qtbot, monkeypatch):
    _stub_find_log_directories(
        monkeypatch,
        results={"exact_matches": ["/a/logs"], "potential_matches": ["/b/myapp-logs"]},
    )

    dialog = FindLogDirsDialog("MyApp")
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.progress_bar.isHidden(), timeout=2000)

    assert dialog.exact_list.count() == 1
    assert dialog.exact_list.item(0).text() == "/a/logs"
    assert dialog.potential_list.count() == 1
    assert dialog.potential_list.item(0).text() == "/b/myapp-logs"


def test_get_selected_directories_returns_only_checked_items(qtbot, monkeypatch):
    _stub_find_log_directories(
        monkeypatch,
        results={"exact_matches": ["/a/logs", "/a2/logs"], "potential_matches": ["/b/logs"]},
    )

    dialog = FindLogDirsDialog("MyApp")
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.progress_bar.isHidden(), timeout=2000)

    dialog.exact_list.item(0).setCheckState(Qt.CheckState.Checked)
    dialog.potential_list.item(0).setCheckState(Qt.CheckState.Checked)
    # a2/logs stays unchecked and must be excluded

    selected = dialog.get_selected_directories()

    assert set(selected) == {"/a/logs", "/b/logs"}


def test_search_error_shows_message_and_rejects_dialog(qtbot, monkeypatch):
    """
    Uses dialog.exec() rather than constructing the dialog and polling its state, to match
    how it's actually driven in production (TrackerDialog.find_directories() always calls
    exec()) - reject() normally runs from inside an active modal event loop started by
    exec(), which none of these tests had before, and that mismatch was suspected as a
    factor in a crash this test previously triggered under the construct-and-poll pattern.
    """
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    _stub_find_log_directories(monkeypatch, error="search blew up")

    dialog = FindLogDirsDialog("MyApp")
    qtbot.addWidget(dialog)

    result = dialog.exec()

    assert result == QDialog.DialogCode.Rejected
    assert dialog.exact_list.count() == 0
    assert dialog.potential_list.count() == 0


def test_invalid_app_name_rejects_dialog_without_searching(qtbot, monkeypatch):
    """A query matching a skip-list entry is rejected by validate_search_query before
    find_log_directories - and therefore the real filesystem - is ever touched."""
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

    dialog = FindLogDirsDialog("node_modules")
    qtbot.addWidget(dialog)

    result = dialog.exec()

    assert result == QDialog.DialogCode.Rejected
