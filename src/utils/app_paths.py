"""Where the app's files live.

Bundled, read-only files (locale, the app icon) resolve through ``resource_path``: the repo
in a checkout, the unpack folder in a compiled build, which places them at the
same relative paths. What the app writes stays outside both. No app imports at
load time: the logger resolves its directory here.
"""

import os
import sys

#: True in a Nuitka-compiled build.
IS_BUILD = "__compiled__" in globals()

RESOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: The window icon, relative to RESOURCE_ROOT; build_exe.py bundles it and
#: makes it the Windows executable's icon.
ICON_FILE = os.path.join("src", "assets", "icon_light.ico")


def resource_path(*parts: str) -> str:
    """Absolute path of a bundled, read-only file."""
    return os.path.join(RESOURCE_ROOT, *parts)


def user_logs_dir() -> str:
    """This app's own log directory (not created here): ``%APPDATA%\\protokoll\\logs``
    on Windows, ``~/.local/share/protokoll/logs`` elsewhere."""
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    else:
        base = os.path.expanduser("~/.local/share")
    return os.path.join(base, "protokoll", "logs")
