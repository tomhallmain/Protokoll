"""src/utils/app_paths.py: bundled resources and the app's own log directory."""

import os
import sys

import pytest

from src.utils import app_paths
from src.utils.translations import I18N
from src.utils.version import VERSION_FILE

pytestmark = pytest.mark.unit


def test_checkout_is_not_a_build():
    assert app_paths.IS_BUILD is False


def test_resource_root_is_the_repo_in_a_checkout():
    assert os.path.isfile(app_paths.resource_path("run.py"))
    assert os.path.isfile(app_paths.resource_path(VERSION_FILE))
    assert os.path.isdir(app_paths.resource_path("locale"))


def test_resource_path_follows_the_resource_root(monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "RESOURCE_ROOT", str(tmp_path))
    assert app_paths.resource_path("locale", "en") == os.path.join(str(tmp_path), "locale", "en")


def test_translations_load_from_the_bundled_locale_dir():
    assert I18N.localedir == app_paths.resource_path("locale")


def test_user_logs_dir_is_under_the_per_user_data_dir():
    if sys.platform == "win32":
        base = os.environ["APPDATA"]
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    assert app_paths.user_logs_dir() == os.path.join(base, "protokoll", "logs")
