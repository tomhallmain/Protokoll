"""
Unit tests for src.utils.file_handler.FileHandler.

Rewritten from the old test/test_file_handler.py, which was a manual print-based
script with no assertions that could actually fail a regression.
"""

import gzip
import os

import pytest

from src.utils.file_handler import FileHandler

pytestmark = pytest.mark.unit


@pytest.fixture
def handler():
    return FileHandler()


def test_is_log_file_recognizes_standard_extensions():
    assert FileHandler.is_log_file("app.log")
    assert FileHandler.is_log_file("app.txt")
    assert FileHandler.is_log_file("data.json")
    assert not FileHandler.is_log_file("photo.png")


def test_is_log_file_recognizes_encrypted_extension():
    """Files following the .enc naming convention for encrypted logs count as log files."""
    assert FileHandler.is_log_file("app.log.enc")
    assert FileHandler.is_encrypted_log("app.log.enc")


def test_is_encrypted_log_requires_exact_extension():
    assert not FileHandler.is_encrypted_log("app.log")
    assert not FileHandler.is_encrypted_log("app.enc.bak")


def test_is_compressed():
    assert FileHandler.is_compressed("app.log.gz")
    assert FileHandler.is_compressed("app.log.bz2")
    assert not FileHandler.is_compressed("app.log")


def test_get_file_info_plain_text_file(tmp_path, handler):
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"line one\nline two\n")  # write_bytes: exact bytes, no platform newline translation

    info = handler.get_file_info(str(log_file))

    assert "error" not in info
    assert info["is_file"] is True
    assert info["is_log_file"] is True
    assert info["is_encrypted"] is False
    assert info["is_binary"] is False
    assert info["size"] == len("line one\nline two\n")


def test_get_file_info_binary_file_is_flagged_binary(tmp_path, handler):
    binary_file = tmp_path / "app.log"
    binary_file.write_bytes(bytes(range(256)) * 20)  # plenty of nulls/non-printables

    info = handler.get_file_info(str(binary_file))

    assert info["is_binary"] is True


def test_get_file_info_encrypted_log_skips_binary_check(tmp_path, handler):
    """Ciphertext always looks binary to the printable-ratio heuristic; .enc files must bypass it."""
    encrypted_file = tmp_path / "app.log.enc"
    encrypted_file.write_bytes(os.urandom(256))

    info = handler.get_file_info(str(encrypted_file))

    assert info["is_encrypted"] is True
    assert info["is_binary"] is False


def test_get_file_info_missing_file(handler):
    info = handler.get_file_info("/nonexistent/path/app.log")
    assert "error" in info


def test_read_file_safe_returns_text_content(tmp_path, handler):
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"hello\nworld\n")  # write_bytes: read_file_safe reads in binary mode, so this must match exactly

    success, content, info = handler.read_file_safe(str(log_file))

    assert success is True
    assert content == "hello\nworld\n"
    assert isinstance(content, str)


def test_read_file_safe_encrypted_log_returns_raw_bytes(tmp_path, handler):
    """Decryption needs service_name/app_identifier the caller must supply - FileHandler
    itself just hands back the untouched ciphertext instead of trying to decode it as text."""
    encrypted_file = tmp_path / "app.log.enc"
    raw = os.urandom(128)
    encrypted_file.write_bytes(raw)

    success, content, info = handler.read_file_safe(str(encrypted_file))

    assert success is True
    assert isinstance(content, bytes)
    assert content == raw


def test_read_file_safe_rejects_oversized_file(tmp_path, handler):
    log_file = tmp_path / "app.log"
    log_file.write_text("x" * 100, encoding="utf-8")

    success, content, info = handler.read_file_safe(str(log_file), max_size=10)

    assert success is False
    assert "error" in info


def test_read_compressed_file_directly_handles_gzip(tmp_path, handler):
    """Covers the decompression logic in isolation from read_file_safe's surrounding checks."""
    gz_file = tmp_path / "app.log.gz"
    with gzip.open(gz_file, "wt", encoding="utf-8", newline="") as f:
        f.write("compressed content\n")

    content = handler._read_compressed_file(str(gz_file))

    assert content == "compressed content\n"


def test_read_file_safe_reads_gzip_compressed_file(tmp_path, handler):
    gz_file = tmp_path / "app.log.gz"
    with gzip.open(gz_file, "wt", encoding="utf-8", newline="") as f:
        f.write("compressed content\n")

    success, content, info = handler.read_file_safe(str(gz_file))

    assert success is True
    assert content == "compressed content\n"


def test_validate_file_for_viewing_rejects_binary(tmp_path, handler):
    binary_file = tmp_path / "app.log"
    binary_file.write_bytes(bytes(range(256)) * 20)

    is_valid, reason, info = handler.validate_file_for_viewing(str(binary_file))

    assert is_valid is False


def test_validate_file_for_viewing_accepts_encrypted_log(tmp_path, handler):
    encrypted_file = tmp_path / "app.log.enc"
    encrypted_file.write_bytes(os.urandom(128))

    is_valid, reason, info = handler.validate_file_for_viewing(str(encrypted_file))

    assert is_valid is True
