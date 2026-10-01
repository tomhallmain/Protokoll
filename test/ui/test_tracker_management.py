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
from src.ui.tracker_dialog import DELETE_REQUESTED

pytestmark = pytest.mark.ui


def _fake_tracker_dialog_class(return_data, accepted=True):
    """Build a TrackerDialog stand-in that returns fixed data instead of showing a real dialog."""

    class FakeTrackerDialog:
        def __init__(self, tracker=None, parent=None):
            self.tracker = tracker

        def exec(self):
            return accepted

        def get_tracker_data(self):
            # The real dialog always has these fields, left blank unless filled in.
            return {"log_encryption_service": "", "log_encryption_app_id": "", **return_data}

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


# ---------------------------------------------------------------------------
# Deleting a tracker from the edit dialog
# ---------------------------------------------------------------------------


def _deleting_tracker_dialog_class():
    """A TrackerDialog stand-in that reports a confirmed deletion."""

    class FakeTrackerDialog:
        def __init__(self, tracker=None, parent=None):
            self.tracker = tracker

        def exec(self):
            return DELETE_REQUESTED

    return FakeTrackerDialog


def _tracker_with_a_log_file(window, tmp_path, name="my-app"):
    log_dir = tmp_path / f"{name}-logs"
    log_dir.mkdir()
    log_file = log_dir / "app.log"
    log_file.write_bytes(b"line one\n")
    tracker = Tracker(name, "a description", window.config_manager)
    tracker.add_log_directory(str(log_dir))
    window.load_trackers()
    return log_file


def test_edit_tracker_deletes_when_the_dialog_asks_for_it(qtbot, window, tmp_path, monkeypatch):
    log_file = _tracker_with_a_log_file(window, tmp_path)
    item = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)[0]
    monkeypatch.setattr("src.ui.main_window.TrackerDialog", _deleting_tracker_dialog_class())

    window.edit_tracker(item)

    assert window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly) == []
    assert Tracker.load("my-app", window.config_manager) is None
    # The tracker was a record of where to look, and only that record is gone.
    assert log_file.exists()


def test_deleting_the_selected_tracker_clears_what_it_was_showing(qtbot, window, tmp_path, monkeypatch):
    _tracker_with_a_log_file(window, tmp_path)
    item = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)[0]
    window.tracker_list.setCurrentItem(item)
    assert window.current_tracker is not None
    monkeypatch.setattr("src.ui.main_window.TrackerDialog", _deleting_tracker_dialog_class())

    window.edit_tracker(item)

    assert window.current_tracker is None
    assert window.files_list.count() == 0


def test_deleting_a_tracker_forgets_where_it_was_left(qtbot, window, tmp_path, monkeypatch):
    """A deleted tracker left in the last-used state would be selected again on
    the next launch, or listed as recent with nothing behind it."""
    _tracker_with_a_log_file(window, tmp_path)
    window.config_manager.add_recent_tracker("my-app")
    window.config_manager.set("last_tracker", "my-app")
    item = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)[0]
    window.tracker_list.setCurrentItem(item)
    monkeypatch.setattr("src.ui.main_window.TrackerDialog", _deleting_tracker_dialog_class())

    window.edit_tracker(item)

    assert window.config_manager.get("recent_trackers", []) == []
    assert window.config_manager.get("last_tracker") is None
    assert window.config_manager.get(
        window.config_manager.last_log_file_key("my-app")) is None


def test_editing_a_tracker_without_a_delete_leaves_it_alone(qtbot, window, tmp_path, monkeypatch):
    """The dialog's other outcomes must not be mistaken for the new one."""
    _tracker_with_a_log_file(window, tmp_path)
    item = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)[0]
    monkeypatch.setattr(
        "src.ui.main_window.TrackerDialog",
        _fake_tracker_dialog_class({}, accepted=False),
    )

    window.edit_tracker(item)

    assert Tracker.load("my-app", window.config_manager) is not None



def test_create_tracker_saves_the_log_encryption_identity(qtbot, window, tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(
        "src.ui.main_window.TrackerDialog",
        _fake_tracker_dialog_class({
            "name": "my-app",
            "description": "",
            "log_directories": [str(log_dir)],
            "log_encryption_service": "SomeService",
            "log_encryption_app_id": "some_app",
        }),
    )

    window.create_tracker()

    loaded = Tracker.load("my-app", window.config_manager)
    assert loaded.log_encryption_service == "SomeService"
    assert loaded.log_encryption_app_id == "some_app"


def test_edit_tracker_can_clear_the_log_encryption_identity(qtbot, window, tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", config_manager=window.config_manager)
    tracker.set_log_encryption("SomeService", "some_app")
    tracker.set_log_directories([str(log_dir)])
    window.load_trackers()
    item = window.tracker_list.findItems("my-app", Qt.MatchFlag.MatchExactly)[0]
    monkeypatch.setattr(
        "src.ui.main_window.TrackerDialog",
        _fake_tracker_dialog_class({
            "name": "my-app",
            "description": "",
            "log_directories": [str(log_dir)],
        }),
    )

    window.edit_tracker(item)

    loaded = Tracker.load("my-app", window.config_manager)
    assert loaded.log_encryption_service == ""
    assert loaded.log_encryption_app_id == ""
