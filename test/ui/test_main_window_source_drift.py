"""MainWindow tells the user when a build's startup check finds its source
checkout has changed; the check reports from a background thread."""

import threading

import pytest

from src.ui import main_window as main_window_module
from src.utils.translations import _

pytestmark = pytest.mark.ui


def test_drift_reported_from_a_worker_thread_shows_a_toast(qtbot, window, monkeypatch):
    shown = []
    monkeypatch.setattr(main_window_module, "show_toast",
                        lambda parent, message, duration_ms=2500: shown.append((message, duration_ms)))

    worker = threading.Thread(target=window.source_drift.emit, args=("2 commits behind",))
    worker.start()
    worker.join(5)
    qtbot.waitUntil(lambda: bool(shown), timeout=5000)

    message, duration_ms = shown[0]
    assert message == _("This build differs from its source checkout. Details are in the log.")
    assert duration_ms > 2500
