"""
UI tests (pytest-qt) for show_toast: the transient notification shown over a
parent widget (e.g. "Path copied to clipboard").
"""

import pytest
from PyQt6.QtWidgets import QFrame, QLabel

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
