"""
Unit tests for src.utils.file_handler.FileHandler.

Rewritten from the old test/test_file_handler.py, which was a manual print-based
script with no assertions that could actually fail a regression.
"""

import gzip
import os

import pytest

from src.utils.file_handler import FileHandler
from src.utils.globals import AppInfo
from src.utils.translations import _

pytestmark = pytest.mark.unit

LOG_SERVICE = AppInfo.LOG_ENCRYPTION_SERVICE


def _msg_start(msgid):
    """The literal opening of a translated message, before its first placeholder."""
    return _(msgid).split("{0}")[0]


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


def test_read_file_safe_decrypts_an_encrypted_log(tmp_path, handler, write_encrypted_log):
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", ["first", "second"])

    success, content, info = handler.read_file_safe(
        str(encrypted_file), key_candidates=[(LOG_SERVICE, "app")])

    assert success is True
    assert content == "first\nsecond\n"
    assert info["skipped_records"] == 0


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


# ---------------------------------------------------------------------------
# read_tail_safe: loading the end of a file without reading all of it
# ---------------------------------------------------------------------------


def _numbered_lines(count):
    """Bytes, not text: the tail read works in binary, so on-disk content has to
    be exact - write_text would translate the line endings on Windows."""
    return b"".join(b"line %05d\n" % i for i in range(count))


def test_read_tail_safe_returns_a_small_file_whole(tmp_path, handler):
    """A file that already fits comes back untouched, so a caller can use this
    for every file and let the size decide."""
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"line one\nline two\n")

    success, content, info = handler.read_tail_safe(str(log_file), max_bytes=4096)

    assert success is True
    assert content == "line one\nline two\n"
    assert info["is_tail"] is False


def test_read_tail_safe_returns_only_the_end_of_a_large_file(tmp_path, handler):
    log_file = tmp_path / "app.log"
    log_file.write_bytes(_numbered_lines(2000))

    success, content, info = handler.read_tail_safe(str(log_file), max_bytes=2048)

    assert success is True
    assert info["is_tail"] is True
    assert "line 01999" in content      # the end of the file is what is shown
    assert "line 00000" not in content  # the start of it is not


def test_read_tail_safe_starts_at_a_line_boundary(tmp_path, handler):
    """A slice taken mid-file starts mid-line, and half a log entry reads as a
    corrupt one."""
    log_file = tmp_path / "app.log"
    log_file.write_bytes(_numbered_lines(2000))

    _success, content, _info = handler.read_tail_safe(str(log_file), max_bytes=2048)

    assert all(line.startswith("line ") for line in content.splitlines())


def test_read_tail_safe_honours_the_byte_budget(tmp_path, handler):
    log_file = tmp_path / "app.log"
    log_file.write_bytes(_numbered_lines(2000))

    _success, _content, info = handler.read_tail_safe(str(log_file), max_bytes=2048)

    assert info["shown_bytes"] <= 2048
    assert info["shown_size_human"]


def test_read_tail_safe_keeps_content_with_no_line_break(tmp_path, handler):
    """Dropping the partial first line would leave nothing at all to show."""
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"x" * 5000)

    success, content, info = handler.read_tail_safe(str(log_file), max_bytes=1024)

    assert success is True
    assert info["is_tail"] is True
    assert len(content) == 1024


def test_read_tail_safe_reads_the_end_of_a_compressed_file(tmp_path, handler):
    gz_file = tmp_path / "app.log.gz"
    with gzip.open(gz_file, "wt", encoding="utf-8", newline="") as f:
        f.write(_numbered_lines(2000).decode("ascii"))

    success, content, info = handler.read_tail_safe(str(gz_file), max_bytes=2048)

    assert success is True
    assert info["is_tail"] is True
    assert "line 01999" in content
    assert "line 00000" not in content


def test_read_tail_safe_returns_a_small_compressed_file_whole(tmp_path, handler):
    gz_file = tmp_path / "app.log.gz"
    with gzip.open(gz_file, "wt", encoding="utf-8", newline="") as f:
        f.write("compressed content\n")

    success, content, info = handler.read_tail_safe(str(gz_file), max_bytes=4096)

    assert success is True
    assert content == "compressed content\n"
    assert info["is_tail"] is False


def test_read_tail_safe_ignores_the_whole_file_size_limit(tmp_path, handler, monkeypatch):
    """The point of reading the tail: the cost does not depend on the size, so
    the ceiling that protects whole-file reads does not apply."""
    monkeypatch.setattr(FileHandler, "MAX_FILE_SIZE", 10)
    log_file = tmp_path / "app.log"
    log_file.write_bytes(_numbered_lines(100))

    success, content, info = handler.read_tail_safe(str(log_file), max_bytes=256)

    assert success is True
    assert "line 00099" in content


def test_read_tail_safe_rejects_a_binary_file(tmp_path, handler):
    binary_file = tmp_path / "app.log"
    binary_file.write_bytes(bytes(range(256)) * 20)

    success, _content, info = handler.read_tail_safe(str(binary_file))

    assert success is False
    assert "error" in info


def test_read_tail_safe_keeps_the_last_whole_records_of_an_encrypted_log(
        tmp_path, handler, write_encrypted_log):
    lines = [f"line {i:05d}" for i in range(2000)]
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", lines)

    success, content, info = handler.read_tail_safe(
        str(encrypted_file), max_bytes=256, key_candidates=[(LOG_SERVICE, "app")])

    assert success is True
    assert info["is_tail"] is True
    assert content.endswith("line 01999\n")
    assert "line 00000" not in content
    assert all(line.startswith("line ") and len(line) == 10 for line in content.splitlines())


def test_read_tail_safe_shows_a_small_encrypted_log_whole(tmp_path, handler, write_encrypted_log):
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", ["only line"])

    success, content, info = handler.read_tail_safe(
        str(encrypted_file), max_bytes=256, key_candidates=[(LOG_SERVICE, "app")])

    assert success is True
    assert info["is_tail"] is False
    assert content == "only line\n"


def test_encrypted_log_opens_with_the_first_candidate_that_fits(
        tmp_path, handler, write_encrypted_log, fake_keyring):
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", ["hello"], app_identifier="app")
    # A second identity with a passphrase of its own: found, but the wrong key.
    write_encrypted_log(tmp_path / "other.log.enc", ["x"], app_identifier="other")

    success, content, _info = handler.read_file_safe(
        str(encrypted_file),
        key_candidates=[(LOG_SERVICE, "missing"), (LOG_SERVICE, "other"), (LOG_SERVICE, "app")])

    assert success is True
    assert content == "hello\n"


def test_encrypted_log_candidates_that_miss_leave_no_keyring_entry(
        tmp_path, handler, write_encrypted_log, fake_keyring):
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", ["hello"])
    before = dict(fake_keyring)

    success, _content, info = handler.read_file_safe(
        str(encrypted_file), key_candidates=[(LOG_SERVICE, "typo"), ("TypoService", "app")])

    assert success is False
    assert fake_keyring == before
    assert _msg_start("This log is encrypted, and no key found for it opens it (tried: {0}).") in info["error"]
    assert f"{LOG_SERVICE} / typo" in info["error"]


def test_encrypted_log_without_candidates_says_so(tmp_path, handler, write_encrypted_log):
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", ["hello"])

    success, _content, info = handler.read_file_safe(str(encrypted_file))

    assert success is False
    assert _("This log is encrypted, and there is no service name and app ID "
             "to look up its key with.") in info["error"]


def test_encrypted_log_record_that_fails_is_skipped_and_counted(tmp_path, handler, write_encrypted_log):
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", ["first", "second", "third"])
    data = bytearray(encrypted_file.read_bytes())
    # Flip a ciphertext byte in the second record; its length prefix stays intact.
    first_length = int.from_bytes(data[:4], "big")
    data[4 + first_length + 4 + 12 + 16] ^= 0xFF
    encrypted_file.write_bytes(bytes(data))

    success, content, info = handler.read_file_safe(
        str(encrypted_file), key_candidates=[(LOG_SERVICE, "app")])

    assert success is True
    assert content == "first\nthird\n"
    assert info["skipped_records"] == 1


def test_encrypted_log_ignores_a_record_still_being_written(tmp_path, handler, write_encrypted_log):
    encrypted_file = write_encrypted_log(tmp_path / "app.log.enc", ["done", "in progress"])
    encrypted_file.write_bytes(encrypted_file.read_bytes()[:-5])

    success, content, _info = handler.read_file_safe(
        str(encrypted_file), key_candidates=[(LOG_SERVICE, "app")])

    assert success is True
    assert content == "done\n"


def test_empty_encrypted_log_reads_as_empty(tmp_path, handler):
    encrypted_file = tmp_path / "app.log.enc"
    encrypted_file.write_bytes(b"")

    success, content, _info = handler.read_file_safe(
        str(encrypted_file), key_candidates=[(LOG_SERVICE, "app")])

    assert success is True
    assert content == ""


def test_enc_file_that_is_not_a_record_stream_is_an_error(tmp_path, handler):
    encrypted_file = tmp_path / "app.log.enc"
    # A length prefix far past the end of the file: no whole record.
    encrypted_file.write_bytes(b"\xff\xff\xff\xff" + os.urandom(64))

    success, _content, info = handler.read_file_safe(
        str(encrypted_file), key_candidates=[(LOG_SERVICE, "app")])

    assert success is False
    assert info["error"] == _("This file does not contain any readable encrypted log records.")


def test_tail_safe_encodings_exclude_the_multi_byte_ones():
    """A tail is cut at a b'\\n', which only means a line break in these."""
    assert FileHandler._is_tail_safe_encoding("utf-8")
    assert FileHandler._is_tail_safe_encoding("ascii")
    assert FileHandler._is_tail_safe_encoding("cp1252")
    assert not FileHandler._is_tail_safe_encoding("utf-16")
    assert not FileHandler._is_tail_safe_encoding("utf-16-le")


def test_validate_file_for_viewing_no_longer_rejects_on_size(tmp_path, handler, monkeypatch):
    monkeypatch.setattr(FileHandler, "MAX_FILE_SIZE", 10)
    log_file = tmp_path / "app.log"
    log_file.write_bytes(b"x" * 100)

    is_valid, _reason, _info = handler.validate_file_for_viewing(str(log_file))

    assert is_valid is True

