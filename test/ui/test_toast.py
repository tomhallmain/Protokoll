"""
UI tests (pytest-qt) for show_toast: the transient notification shown over a
parent widget (e.g. "Path copied to clipboard").
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


def test_show_toast_fades_out_and_removes_itself(qtbot, window):
    show_toast(window, "brief message", duration_ms=20)

    qtbot.waitUntil(lambda: window.findChild(QFrame, "toast") is None, timeout=2000)


def test_the_fade_timer_does_not_outlive_the_toast(qtbot):
    """A pending fade timer that survives its widget fires into a deleted
    QFrame. PyQt turns that unhandled exception into an abort, and it lands on
    whichever test is running when the timer happens to expire."""
    parent = QWidget()
    qtbot.addWidget(parent)
    show_toast(parent, "brief message", duration_ms=30)
    toast = parent.findChild(QFrame, "toast")

    toast.deleteLater()  # what closing a window does to a toast still showing
    qtbot.wait(150)      # past the fade; pytest-qt fails the test on a raise

    assert parent.findChild(QFrame, "toast") is None
