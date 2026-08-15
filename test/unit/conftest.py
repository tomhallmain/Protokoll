"""
conftest for test/unit/.

Mirrors the module-level env var bootstrap from the root conftest.py. Pytest loads
each directory's conftest.py before collecting tests in that directory; this file
re-applies the same guard defensively in case test/unit is ever collected in a
context where the root conftest's module-level code hasn't already run.
"""

import os
import tempfile

if "PROTOKOLL_TEST_ISOLATED" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="protokoll-unit-home-")
    os.environ["HOME"] = _tmp
    os.environ["USERPROFILE"] = _tmp
    os.environ["APPDATA"] = _tmp
    os.environ["LOCALAPPDATA"] = _tmp
    os.environ["PROGRAMDATA"] = _tmp
    os.environ["PROTOKOLL_TEST_ISOLATED"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
