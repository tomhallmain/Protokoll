"""
conftest for test/ui/.

Mirrors the module-level env var bootstrap from the root conftest.py. Pytest loads
each directory's conftest.py before collecting tests in that directory; this file
re-applies the same guard defensively in case test/ui is ever collected in a
context where the root conftest's module-level code hasn't already run - which
matters more here than elsewhere, since QT_QPA_PLATFORM has to be set before
pytest-qt's qapp fixture creates the first QApplication.
"""

import os
import tempfile

if "PROTOKOLL_TEST_ISOLATED" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="protokoll-ui-home-")
    os.environ["HOME"] = _tmp
    os.environ["USERPROFILE"] = _tmp
    os.environ["APPDATA"] = _tmp
    os.environ["LOCALAPPDATA"] = _tmp
    os.environ["PROGRAMDATA"] = _tmp
    os.environ["XDG_DATA_HOME"] = os.path.join(_tmp, "data")
    os.environ.setdefault("PROTOKOLL_CACHE_DIR", os.path.join(_tmp, "cache"))
    # See _pin_key_backup_dir in the root conftest: an unpinned destination is a
    # real external drive, and the backup carries the passphrase in the clear.
    os.environ["PROTOKOLL_KEY_BACKUP_DIR"] = os.path.join(
        os.environ["PROTOKOLL_CACHE_DIR"], "key_backup")
    os.environ["PROTOKOLL_TEST_ISOLATED"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTEST_QT_API", "pyqt6")

import pytest

from src.ui.main_window import MainWindow


@pytest.fixture
def window(qtbot):
    """A real MainWindow, isolated per test via the root conftest's autouse fixtures."""
    win = MainWindow()
    qtbot.addWidget(win)
    return win
