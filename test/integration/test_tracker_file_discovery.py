"""
Integration test: a Tracker discovering log files on disk, then FileHandler
analysing and reading each one - the "browse a tracker's log files" path the UI
drives (files_list population -> validate_file_for_viewing -> read_file_safe).
"""

import os

import pytest

from src.internal.tracker import Tracker
from src.utils.config_manager import ConfigManager
from src.utils.file_handler import FileHandler

pytestmark = pytest.mark.integration


def test_tracker_discovers_and_file_handler_analyses_mixed_log_directory(tmp_path, write_encrypted_log):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # write_bytes throughout: read_file_safe reads in binary mode, so on-disk content must
    # be exact - write_text would translate \n to \r\n on Windows and break the comparisons.
    (log_dir / "app.log").write_bytes(b"startup\nERROR disk full\nshutdown\n")
    (log_dir / "corrupt.log").write_bytes(bytes(range(256)) * 10)  # unreadably binary
    # Encrypted by a producer under the app ID "app", which the reader guesses from the name.
    write_encrypted_log(log_dir / "app.log.enc", ["secret startup", "ERROR secret"], app_identifier="app")
    (log_dir / "notes.txt").write_bytes(b"plain text notes\n")

    config_manager = ConfigManager()
    tracker = Tracker("my-app", config_manager=config_manager)
    tracker.add_log_directory(str(log_dir))
    file_handler = FileHandler()

    discovered = {f["path"] for f in tracker.get_log_files()}

    assert discovered == {
        str(log_dir / "app.log"),
        str(log_dir / "corrupt.log"),
        str(log_dir / "app.log.enc"),
        str(log_dir / "notes.txt"),
    }

    # Plain-text log: valid to view, reads back exactly as written.
    is_valid, _, _ = file_handler.validate_file_for_viewing(str(log_dir / "app.log"))
    assert is_valid is True
    success, content, _ = file_handler.read_file_safe(str(log_dir / "app.log"))
    assert success is True
    assert "ERROR disk full" in content

    # Binary garbage: discovered (it has a recognized extension) but rejected for viewing.
    is_valid, _, _ = file_handler.validate_file_for_viewing(str(log_dir / "corrupt.log"))
    assert is_valid is False

    # Encrypted log: bypasses the binary check, and decrypts with the key the
    # tracker finds for it without being told the app ID.
    encrypted_path = str(log_dir / "app.log.enc")
    is_valid, _, _ = file_handler.validate_file_for_viewing(encrypted_path)
    assert is_valid is True
    success, content, _ = file_handler.read_file_safe(
        encrypted_path, key_candidates=tracker.log_key_candidates(encrypted_path))
    assert success is True
    assert content == "secret startup\nERROR secret\n"


def test_enc_file_that_is_not_an_encrypted_log_is_reported_not_shown(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    not_a_log = log_dir / "app.log.enc"
    not_a_log.write_bytes(b"\xff\xff\xff\xff" + os.urandom(92))
    tracker = Tracker("my-app", config_manager=ConfigManager())
    tracker.add_log_directory(str(log_dir))

    success, content, info = FileHandler().read_file_safe(
        str(not_a_log), key_candidates=tracker.log_key_candidates(str(not_a_log)))

    assert success is False
    assert content == ""
    assert "error" in info
