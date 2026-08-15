"""
Unit tests for src.utils.encryptor - StreamingLogCipher, SymmetricEncryptor, and
PassphraseManager. Relies on the root conftest's autouse `fake_keyring` fixture, so
none of this ever touches a real OS keyring - see test/conftest.py.

PersonalQuantumEncryptor is intentionally not covered here: it requires the
optional `oqs`/liboqs dependency (see requirements-optional.txt / pytest.ini's
`requires_oqs` marker).
"""

import io
import os

import pytest
from cryptography.exceptions import InvalidTag

from src.utils.encryptor import (
    PassphraseManager,
    StreamingLogCipher,
    encrypt_log_record,
    get_log_cipher_key,
    namespaced_key,
    symmetric_decrypt_data_from_file,
    symmetric_encrypt_data_to_file,
)

pytestmark = pytest.mark.unit


def test_namespaced_key_joins_nonempty_parts():
    assert namespaced_key("app", "salt") == "app__salt"
    assert namespaced_key("", "salt") == "salt"
    assert namespaced_key("app", None, "salt") == "app__salt"


def test_streaming_log_cipher_roundtrip():
    key = get_log_cipher_key("TestService", "logs")
    stream = io.BytesIO(
        encrypt_log_record(key, b"hello world") + encrypt_log_record(key, b"second line")
    )

    decrypted = list(StreamingLogCipher.iter_decrypt(key, stream))

    assert decrypted == [b"hello world", b"second line"]


def test_streaming_log_cipher_same_service_app_id_gives_same_key():
    """Producer and reader derive the key independently but must land on the same
    bytes - this is what lets a decryptor work without any key file ever being
    transferred between machines."""
    key_a = get_log_cipher_key("TestService", "logs")
    key_b = get_log_cipher_key("TestService", "logs")

    assert key_a == key_b


def test_streaming_log_cipher_wrong_key_raises_invalid_tag():
    key_a = get_log_cipher_key("AppA", "logs")
    key_b = get_log_cipher_key("AppB", "logs")
    stream = io.BytesIO(encrypt_log_record(key_a, b"secret"))

    with pytest.raises(InvalidTag):
        list(StreamingLogCipher.iter_decrypt(key_b, stream))


def test_streaming_log_cipher_stops_cleanly_on_truncated_trailing_record():
    """A reader tailing a log file that's still being written to shouldn't raise on
    a partially-flushed final record - it should just stop at the last complete one."""
    key = get_log_cipher_key("TestService", "logs")
    full = encrypt_log_record(key, b"complete record") + encrypt_log_record(key, b"truncated")
    truncated = full[:-4]
    stream = io.BytesIO(truncated)

    decrypted = list(StreamingLogCipher.iter_decrypt(key, stream))

    assert decrypted == [b"complete record"]


def test_symmetric_encryptor_roundtrip_compressible_data(tmp_path):
    data = b"log payload " * 200  # highly redundant, should compress
    out = tmp_path / "out.enc"

    symmetric_encrypt_data_to_file(data, str(out), b"correct horse battery staple")
    result = symmetric_decrypt_data_from_file(str(out), b"correct horse battery staple")

    assert result == data


def test_symmetric_encryptor_roundtrip_incompressible_data(tmp_path):
    data = os.urandom(64)  # high entropy, shouldn't compress smaller
    out = tmp_path / "out.enc"

    symmetric_encrypt_data_to_file(data, str(out), b"another passphrase")
    result = symmetric_decrypt_data_from_file(str(out), b"another passphrase")

    assert result == data


def test_symmetric_encryptor_wrong_passphrase_fails(tmp_path):
    out = tmp_path / "out.enc"
    symmetric_encrypt_data_to_file(b"payload", str(out), b"right passphrase")

    with pytest.raises(Exception):
        symmetric_decrypt_data_from_file(str(out), b"wrong passphrase")


def test_passphrase_manager_env_var_takes_precedence(monkeypatch, fake_keyring):
    monkeypatch.setenv("TESTSVC_PASSPHRASE", "explicit-value")

    passphrase = PassphraseManager.get_passphrase("TestSvc", "app1")

    assert passphrase == "explicit-value"
    assert fake_keyring == {}  # keyring was never consulted


def test_passphrase_manager_persists_via_keyring(fake_keyring):
    first = PassphraseManager.get_passphrase("TestSvc", "app1")
    second = PassphraseManager.get_passphrase("TestSvc", "app1")

    assert first == second
    assert fake_keyring  # something was actually written to the fake store


def test_passphrase_manager_different_app_ids_get_different_passphrases(fake_keyring):
    p1 = PassphraseManager.get_passphrase("TestSvc", "app1")
    p2 = PassphraseManager.get_passphrase("TestSvc", "app2")

    assert p1 != p2
