"""
UI tests (pytest-qt) for MainWindow's "setting trackers" flows: create_tracker,
edit_tracker, tracker selection, and restoring the last-used tracker on load.

TrackerDialog is monkeypatched throughout - it would otherwise open a real modal
dialog and block a headless test run waiting for a user who isn't there.
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from src.internal.tracker import Tracker

pytestmark = pytest.mark.ui


def _fake_tracker_dialog_class(return_data, accepted=True):
    """Build a TrackerDialog stand-in that returns fixed data instead of showing a real dialog."""

    class FakeTrackerDialog:
        def __init__(self, tracker=None, parent=None):
            self.tracker = tracker

        def exec(self):
            return accepted

        def get_tracker_data(self):
            return return_data

    return FakeTrackerDialog


def test_create_tracker_saves_and_selects_new_tracker(qtbot, window, tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(
        "src.ui.main_window.TrackerDialog",
        _fake_tracker_dialog_class({
            "name": "my-app",
            "description": "a description",
            "log_directories": [str(log_dir)],
        }),
    )

    window.create_tracker()

    items = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)
    assert len(items) == 1
    assert window.tracker_list.currentItem().text() == "my-app"

    loaded = Tracker.load("my-app", window.config_manager)
    assert loaded is not None
    assert loaded.description == "a description"
    assert loaded.get_log_directories() == [str(log_dir)]
    assert "my-app" in window.config_manager.get("recent_trackers", [])


def test_create_tracker_does_nothing_when_dialog_cancelled(qtbot, window, monkeypatch):
    monkeypatch.setattr(
        "src.ui.main_window.TrackerDialog",
        _fake_tracker_dialog_class({"name": "x", "description": "", "log_directories": []}, accepted=False),
    )

    window.create_tracker()

    assert window.tracker_list.count() == 0


def test_create_tracker_shows_error_for_invalid_directory(qtbot, window, monkeypatch):
    errors = []
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda *a, **k: errors.append(a) or QMessageBox.StandardButton.Ok)
    )
    monkeypatch.setattr(
        "src.ui.main_window.TrackerDialog",
        _fake_tracker_dialog_class({
            "name": "my-app",
            "description": "",
            "log_directories": ["/definitely/does/not/exist"],
        }),
    )

    window.create_tracker()

    assert len(errors) == 1
    assert window.tracker_list.count() == 0


def test_edit_tracker_updates_description_and_directories(qtbot, window, tmp_path, monkeypatch):
    old_dir = tmp_path / "old-logs"
    old_dir.mkdir()
    new_dir = tmp_path / "new-logs"
    new_dir.mkdir()

    tracker = Tracker("my-app", "old description", window.config_manager)
    tracker.add_log_directory(str(old_dir))
    window.load_trackers()
    item = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)[0]

    monkeypatch.setattr(
        "src.ui.main_window.TrackerDialog",
        _fake_tracker_dialog_class({
            "name": "my-app",
            "description": "new description",
            "log_directories": [str(new_dir)],
        }),
    )

    window.edit_tracker(item)

    loaded = Tracker.load("my-app", window.config_manager)
    assert loaded.description == "new description"
    assert loaded.get_log_directories() == [str(new_dir)]


def test_edit_tracker_does_nothing_when_no_item_given(qtbot, window):
    window.edit_tracker(None)  # must not raise


def test_edit_tracker_shows_error_for_unknown_tracker_name(qtbot, window, monkeypatch):
    errors = []
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda *a, **k: errors.append(a) or QMessageBox.StandardButton.Ok)
    )

    class FakeItem:
        def text(self):
            return "does-not-exist"

    window.edit_tracker(FakeItem())

    assert len(errors) == 1


def test_selecting_tracker_loads_it_and_persists_as_last_tracker(qtbot, window, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", config_manager=window.config_manager)
    tracker.add_log_directory(str(log_dir))
    window.load_trackers()

    item = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)[0]
    window.tracker_list.setCurrentItem(item)

    assert window.current_tracker is not None
    assert window.current_tracker.name == "my-app"
    assert window.config_manager.get("last_tracker") == "my-app"


def test_load_trackers_selects_last_used_tracker(qtbot, window):
    Tracker("tracker-a", config_manager=window.config_manager).save_metadata()
    Tracker("tracker-b", config_manager=window.config_manager).save_metadata()
    window.config_manager.set("last_tracker", "tracker-b")

    window.load_trackers()

    assert window.tracker_list.currentItem().text() == "tracker-b"
