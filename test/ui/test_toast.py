"""
UI tests (pytest-qt) for show_toast: the transient notification shown over a
parent widget (e.g. "Path copied to clipboard").

Several of these show their parent first. That is not scene-setting: a toast is
only raised over a window that is on screen, and the fade it schedules is what
has twice outlived a test and taken the run down with it.
"""

import pytest
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

from src.ui.toast import show_toast

pytestmark = pytest.mark.ui


def test_show_toast_displays_message_immediately(qtbot, window):
    # isVisible() reflects actual on-screen visibility, which requires the whole
    # ancestor chain to be shown - not just the toast itself - so the parent window
    # has to be shown too, or this would report False regardless of the toast's own state.
    window.show()
    qtbot.waitExposed(window)

    show_toast(window, "Copied to clipboard", duration_ms=10000)

    toast = window.findChild(QFrame, "toast")
    assert toast is not None
    assert toast.isVisible()
    label = toast.findChild(QLabel, "toastLabel")
    assert label.text() == "Copied to clipboard"

    # The long duration keeps the toast up for the assertions above; deleting it
    # here means the suite carries no fade pending into a later test.
    toast.deleteLater()


def test_show_toast_fades_out_and_removes_itself(qtbot, window):
    window.show()
    qtbot.waitExposed(window)

    show_toast(window, "brief message", duration_ms=20)

    qtbot.waitUntil(lambda: window.findChild(QFrame, "toast") is None, timeout=2000)


def test_nothing_is_scheduled_over_a_window_that_is_not_on_screen(qtbot):
    """A toast nobody can see, whose fade comes due seconds later against a
    parent that may be gone by then. The MainWindow tests raise toasts on
    windows they never show, and those were the ones expiring mid-run."""
    parent = QWidget()
    qtbot.addWidget(parent)

    show_toast(parent, "brief message", duration_ms=30)

    assert parent.findChild(QFrame, "toast") is None
    qtbot.wait(100)  # nothing pending: the wait would have run it by now
    assert parent.findChild(QFrame, "toast") is None


def test_the_fade_does_not_outlive_the_toast(qtbot):
    """Deleting the toast has to take the timer and the animation with it.
    Anything left pending fires into freed memory, which on Windows ends the
    process rather than raising."""
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitExposed(parent)
    show_toast(parent, "brief message", duration_ms=30)
    toast = parent.findChild(QFrame, "toast")

    toast.deleteLater()  # what tearing down a window does to a toast still up
    qtbot.wait(150)      # past the fade

    assert parent.findChild(QFrame, "toast") is None


def test_a_toast_survives_its_window_being_closed(qtbot):
    """Closing a window does not delete it, so the fade still comes due - it
    just has to finish without touching anything Qt has freed."""
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    qtbot.waitExposed(parent)
    show_toast(parent, "brief message", duration_ms=30)

    parent.close()
    qtbot.wait(400)  # past the delay and the 300ms fade

    assert parent.findChild(QFrame, "toast") is None
