"""
UI tests (pytest-qt) for TrackerDialog: create/edit prefill, directory list
management, and the accept() validation that gates saving a tracker.

QFileDialog.getExistingDirectory, FindLogDirsDialog, and QMessageBox.warning are
all monkeypatched throughout - each would otherwise open a real native/modal
dialog and block a headless test run waiting for a user who isn't there.
"""

import pytest
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QPushButton

from src.internal.tracker import Tracker
from src.ui.tracker_dialog import DELETE_REQUESTED, TrackerDialog
from src.utils.translations import _

pytestmark = pytest.mark.ui


def test_create_mode_starts_empty(qtbot):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)

    assert dialog.name_input.text() == ""
    assert dialog.desc_input.toPlainText() == ""
    assert dialog.dirs_list.count() == 0
    assert dialog.windowTitle() == "Create New Tracker"


def test_edit_mode_prefills_from_tracker(qtbot, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    tracker = Tracker("my-app", "a description")
    tracker.log_directories.add(str(log_dir))

    dialog = TrackerDialog(tracker=tracker)
    qtbot.addWidget(dialog)

    assert dialog.name_input.text() == "my-app"
    assert dialog.desc_input.toPlainText() == "a description"
    assert dialog.dirs_list.count() == 1
    assert dialog.dirs_list.item(0).text() == str(log_dir)
    assert dialog.windowTitle() == "Edit Tracker"


def test_get_tracker_data_reflects_current_form_state(qtbot, tmp_path):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.name_input.setText("new-tracker")
    dialog.desc_input.setPlainText("desc text")
    dialog.dirs_list.addItem(str(tmp_path))

    data = dialog.get_tracker_data()

    assert data == {
        "name": "new-tracker",
        "description": "desc text",
        "log_directories": [str(tmp_path)],
    }


def test_remove_directory_removes_selected_item(qtbot, tmp_path):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.dirs_list.addItem(str(tmp_path))
    dialog.dirs_list.setCurrentRow(0)

    dialog.remove_directory()

    assert dialog.dirs_list.count() == 0


def test_remove_directory_does_nothing_when_none_selected(qtbot, tmp_path):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.dirs_list.addItem(str(tmp_path))
    dialog.dirs_list.setCurrentRow(-1)

    dialog.remove_directory()

    assert dialog.dirs_list.count() == 1


def test_add_directory_adds_selected_path(qtbot, tmp_path, monkeypatch):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))

    dialog.add_directory()

    assert dialog.dirs_list.count() == 1
    assert dialog.dirs_list.item(0).text() == str(tmp_path)


def test_add_directory_skips_duplicate(qtbot, tmp_path, monkeypatch):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.dirs_list.addItem(str(tmp_path))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(tmp_path)))

    dialog.add_directory()

    assert dialog.dirs_list.count() == 1


def test_add_directory_does_nothing_when_dialog_cancelled(qtbot, monkeypatch):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))

    dialog.add_directory()

    assert dialog.dirs_list.count() == 0


def test_find_directories_adds_selected_dirs_from_finder(qtbot, tmp_path, monkeypatch):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.name_input.setText("MyApp")

    class FakeFindDialog:
        def __init__(self, app_name, parent=None):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_selected_directories(self):
            return [str(tmp_path)]

    monkeypatch.setattr("src.ui.tracker_dialog.FindLogDirsDialog", FakeFindDialog)

    dialog.find_directories()

    assert dialog.dirs_list.count() == 1
    assert dialog.dirs_list.item(0).text() == str(tmp_path)


def test_find_directories_does_nothing_when_finder_cancelled(qtbot, monkeypatch):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.name_input.setText("MyApp")

    class FakeFindDialog:
        def __init__(self, app_name, parent=None):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

        def get_selected_directories(self):
            return []

    monkeypatch.setattr("src.ui.tracker_dialog.FindLogDirsDialog", FakeFindDialog)

    dialog.find_directories()

    assert dialog.dirs_list.count() == 0


def test_accept_rejects_empty_name(qtbot, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok)
    )
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)

    dialog.accept()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert len(warnings) == 1


def test_accept_rejects_nonexistent_directory(qtbot, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok)
    )
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.name_input.setText("my-app")
    dialog.dirs_list.addItem("/definitely/does/not/exist")

    dialog.accept()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert len(warnings) == 1


def test_accept_succeeds_with_valid_data(qtbot, tmp_path):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)
    dialog.name_input.setText("my-app")
    dialog.dirs_list.addItem(str(tmp_path))

    dialog.accept()

    assert dialog.result() == QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# Deleting a tracker: offered while editing one, and confirmed first
# ---------------------------------------------------------------------------


def _fake_question(answer, recorder=None):
    """Stand in for the confirmation box, answering *answer* without showing it."""
    def question(parent, title, text, buttons=None, default_button=None):
        if recorder is not None:
            recorder.append({"title": title, "text": text, "default": default_button})
        return answer
    return staticmethod(question)


def test_edit_mode_offers_deletion(qtbot):
    dialog = TrackerDialog(tracker=Tracker("my-app"))
    qtbot.addWidget(dialog)

    assert dialog.findChild(QPushButton, "deleteButton") is not None


def test_create_mode_has_nothing_to_delete(qtbot):
    dialog = TrackerDialog()
    qtbot.addWidget(dialog)

    assert dialog.findChild(QPushButton, "deleteButton") is None


def test_confirmed_deletion_ends_the_dialog_asking_for_it(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", _fake_question(QMessageBox.StandardButton.Yes))
    dialog = TrackerDialog(tracker=Tracker("my-app"))
    qtbot.addWidget(dialog)

    dialog.request_delete()

    assert dialog.result() == DELETE_REQUESTED


def test_declined_deletion_leaves_the_dialog_as_it_was(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", _fake_question(QMessageBox.StandardButton.No))
    dialog = TrackerDialog(tracker=Tracker("my-app"))
    qtbot.addWidget(dialog)

    dialog.request_delete()

    assert dialog.result() != DELETE_REQUESTED


def test_the_confirmation_names_the_tracker_and_spares_the_log_files(qtbot, monkeypatch):
    """Deleting a tracker deletes a record of where to look, and the prompt has
    to say so - the same words would otherwise read as deleting the logs."""
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question", _fake_question(QMessageBox.StandardButton.No, asked))
    dialog = TrackerDialog(tracker=Tracker("my-app"))
    qtbot.addWidget(dialog)

    dialog.request_delete()

    assert _('Delete the tracker "{0}"?').format("my-app") in asked[0]["text"]
    assert _("This removes the tracker and the directories it watches from "
             "Protokoll. The log files themselves are left where they are.") in asked[0]["text"]
    # The destructive answer is never the one a stray Enter picks.
    assert asked[0]["default"] == QMessageBox.StandardButton.No

