import os
import gzip
import bz2
import zipfile
import chardet
import sys
import warnings
from collections import deque
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Sequence

from cryptography.exceptions import InvalidTag

from .encryptor import StreamingLogCipher
from .logging_setup import get_logger
from .translations import _

logger = get_logger('utils.file_handler')

if sys.platform == 'win32':
    try:
        import msvcrt  # Windows file locking
    except ImportError:
        logger.error("msvcrt module not found. Please install the python-msvcrt package.")
        raise ImportError("msvcrt module not found. Please install the python-msvcrt package.")
else:
    try:
        import fcntl  # Unix file locking
    except ImportError:
        logger.error("fcntl module not found. Please install the python-fcntl package.")
        raise ImportError("fcntl module not found. Please install the python-fcntl package.")

class FileHandler:
    """
    A comprehensive file handler that provides safe file operations,
    binary detection, compression support, and extended functionality.
    """
    
    # Extended log file extensions
    LOG_EXTENSIONS = [
        '.log', '.txt', '.csv', '.json', '.xml', 
        '.yaml', '.yml', '.ini', '.conf', '.cfg',
        '.out', '.err', '.trace', '.dump',
        '.gz', '.bz2', '.zip'
    ]
    
    # Compression extensions
    COMPRESSED_EXTENSIONS = ['.gz', '.bz2', '.zip']

    # Naming convention for logs encrypted with StreamingLogCipher (e.g. "app.log.enc").
    # Ciphertext looks binary to the printable-ratio heuristic below, so files matching
    # this extension skip binary detection instead of being rejected as corrupted.
    # Reading one takes key candidates: (service_name, app_identifier) pairs, tried in
    # order until one opens the file.
    ENCRYPTED_LOG_EXTENSION = '.enc'

    # File size limits for whole-file reads (100MB max, 10MB warning). Tail reads
    # are bounded by their own budget and ignore the maximum.
    MAX_FILE_SIZE = 100 * 1024 * 1024
    WARN_FILE_SIZE = 10 * 1024 * 1024

    # How much of a file's end read_tail_safe() loads by default. Reading the end
    # of a file costs the same whatever the file's size, which is what keeps
    # opening a multi-gigabyte log as cheap as opening a small one.
    DEFAULT_TAIL_BYTES = 2 * 1024 * 1024

    # Read granularity when decompressing to reach a tail.
    COMPRESSED_READ_CHUNK = 1024 * 1024

    # Encodings in which b'\n' means a line break and nothing else, so a tail can
    # be cut at one. UTF-16 gives no such guarantee -- that byte occurs inside
    # ordinary characters -- so files detected as UTF-16 are read whole instead.
    TAIL_SAFE_ENCODING_PREFIXES = ('utf-8', 'ascii', 'latin', 'iso-8859', 'cp', 'windows-')
    
    # Sample size for detection (4KB optimized for chunk size)
    DETECTION_SAMPLE_SIZE = 4096

    def __init__(self):
        # Removed python-magic dependency
        pass
    
    @classmethod
    def is_log_file(cls, file_path: str) -> bool:
        """Check if file has a log-like extension."""
        return bool(Path(file_path).suffix.lower() in cls.LOG_EXTENSIONS) or cls.is_encrypted_log(file_path)

    @classmethod
    def is_compressed(cls, file_path: str) -> bool:
        """Check if file is compressed."""
        return bool(Path(file_path).suffix.lower() in cls.COMPRESSED_EXTENSIONS)

    @classmethod
    def is_encrypted_log(cls, file_path: str) -> bool:
        """Check if file follows the encrypted-log naming convention (e.g. 'app.log.enc')."""
        return Path(file_path).suffix.lower() == cls.ENCRYPTED_LOG_EXTENSION
    
    def _lock_file(self, file_obj):
        """Apply file locking appropriate for the OS."""
        try:
            if os.name == 'posix':
                fcntl.flock(file_obj, fcntl.LOCK_SH | fcntl.LOCK_NB)
            elif os.name == 'nt':
                msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
        except (IOError, OSError):
            warnings.warn("File is locked by another process", RuntimeWarning)
            return False
        return True

    def _unlock_file(self, file_obj):
        """Release file lock."""
        try:
            if os.name == 'posix':
                fcntl.flock(file_obj, fcntl.LOCK_UN)
            elif os.name == 'nt':
                msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
        except (IOError, OSError):
            pass

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get comprehensive file information with optimizations."""
        path = Path(file_path)
        if not path.exists():
            return {"error": _("File does not exist")}
        
        try:
            stat = path.stat()
            file_size = stat.st_size
            
            info = {
                "path": str(path.resolve()),
                "size": file_size,
                "size_human": self._format_size(file_size),
                "is_file": path.is_file(),
                "is_compressed": self.is_compressed(file_path),
                "is_log_file": self.is_log_file(file_path),
                "is_encrypted": self.is_encrypted_log(file_path),
                "extension": path.suffix.lower(),
                "last_modified": stat.st_mtime,
                "readable": os.access(file_path, os.R_OK),
                "warnings": []
            }

            # Size warnings. Over the maximum a file can still be viewed, since
            # the viewer reads its tail; what it cannot be is read whole, which
            # is what searching it needs.
            if file_size > self.MAX_FILE_SIZE:
                info["warnings"].append(
                    _("Very large file ({0}); too large to search").format(info["size_human"]))
            elif file_size > self.WARN_FILE_SIZE:
                info["warnings"].append(_("Large file ({0})").format(info["size_human"]))

            # Binary detection - skipped for encrypted logs (ciphertext always looks binary
            # to the printable-ratio heuristic; _read_encrypted_log decrypts it) and for
            # compressed files (their raw, still-compressed bytes look binary too; the
            # decompressed content is validated separately when it's actually decoded as
            # text in _read_compressed_file/read_file_safe).
            if info["is_encrypted"] or info["is_compressed"]:
                info["is_binary"] = False
            elif info["is_file"] and info["readable"]:
                try:
                    with open(file_path, 'rb') as f:
                        sample = f.read(self.DETECTION_SAMPLE_SIZE)
                        info["is_binary"] = self._is_binary_sample(sample)
                        info["sample"] = sample  # Store for later use
                except Exception as e:
                    logger.error(f"Binary detection failed: {str(e)}")
                    info["is_binary"] = True
                    info["warnings"].append(_("Binary detection failed"))
                
                if info.get("is_binary", False):
                    info["warnings"].append(_("File may contain corrupted data or non-text content"))
            
            return info
            
        except Exception as e:
            logger.error(f"File info error: {str(e)}")
            return {"error": str(e)}

    def _get_printable_ratio(self, sample: bytes) -> float:
        """Calculate the ratio of printable characters in a byte sample."""
        if not sample:
            return 1.0  # Empty sample is considered 100% printable
        
        printable = 0
        for byte in sample:
            # Consider tab, newline, carriage return as printable
            if 32 <= byte <= 126 or byte in (9, 10, 13):
                printable += 1
        return printable / len(sample)

    def _is_binary_sample(self, sample: bytes) -> bool:
        """Improved binary detection with null byte handling."""
        if not sample:
            return False
        
        # Check for consecutive null bytes which indicate binary
        null_count = sample.count(b'\x00')
        if null_count > len(sample) / 4:  # More than 25% null bytes
            return True
        
        # Calculate printable ratio
        printable_ratio = self._get_printable_ratio(sample)
        
        # Consider files with low printable ratio as binary
        if printable_ratio < 0.65:
            return True
            
        # Files with moderate null bytes but high printable ratio are text
        return False
    
    def _format_size(self, size_bytes: int) -> str:
        """Human-readable file size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    def read_file_safe(self, file_path: str, max_size: Optional[int] = None,
                       key_candidates: Sequence[Tuple[str, str]] = ()) -> Tuple[bool, str, Dict[str, Any]]:
        """Safe file reading with compression and encrypted-log support."""
        max_size = max_size or self.MAX_FILE_SIZE
        file_info = self.get_file_info(file_path)
        
        # Error handling
        if "error" in file_info:
            return False, "", file_info
        if not file_info["is_file"]:
            return False, "", {"error": _("Not a file")}
        if not file_info["readable"]:
            return False, "", {"error": _("Not readable")}
        if file_info["size"] > max_size:
            return False, "", {"error": _("Size exceeds limit ({0})").format(file_info["size_human"])}
        if file_info.get("is_binary", False):
            return False, "", {"error": _("File may contain corrupted data or non-text content"), "warnings": file_info["warnings"]}
        
        try:
            if file_info.get("is_encrypted", False):
                return self._read_encrypted_log(file_path, file_info, key_candidates)
            # Handle compressed files
            if file_info["is_compressed"]:
                content = self._read_compressed_file(file_path)
            # Handle text files
            else:
                encoding = self._detect_encoding(file_info.get("sample", b""))
                with open(file_path, 'rb') as f:
                    content = self._decode_bytes(f.read(), encoding)
            
            return True, content, file_info
            
        except UnicodeDecodeError as e:
            return False, "", {"error": _("Encoding error: {0}").format(str(e))}
        except Exception as e:
            logger.error(f"Read error: {str(e)}")
            return False, "", {"error": str(e)}

    def read_tail_safe(self, file_path: str, max_bytes: Optional[int] = None,
                       key_candidates: Sequence[Tuple[str, str]] = ()) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Read the end of a file, up to *max_bytes*, starting at a line boundary.

        Returns (success, content, info) as read_file_safe does, with
        info["is_tail"] saying whether the start of the file was left out, and
        info["shown_size_human"] how much came back. There is no size ceiling
        here: the read is bounded by max_bytes however large the file is.

        A file that already fits comes back whole, so a caller can use this for
        every file and let the size decide.
        """
        max_bytes = max_bytes or self.DEFAULT_TAIL_BYTES
        file_info = self.get_file_info(file_path)

        if "error" in file_info:
            return False, "", file_info
        if not file_info["is_file"]:
            return False, "", {"error": _("Not a file")}
        if not file_info["readable"]:
            return False, "", {"error": _("Not readable")}
        if file_info.get("is_binary", False):
            return False, "", {"error": _("File may contain corrupted data or non-text content"), "warnings": file_info["warnings"]}

        try:
            if file_info.get("is_encrypted", False):
                return self._read_encrypted_log(file_path, file_info, key_candidates, max_bytes)

            if file_info["is_compressed"]:
                # Compressed formats have no seekable end, so the stream is
                # decompressed in full; only the tail is held.
                raw_content, is_tail = self._read_compressed_tail(file_path, max_bytes)
                encoding = 'utf-8'
            else:
                encoding = self._detect_encoding(file_info.get("sample", b""))
                is_tail = file_info["size"] > max_bytes
                if is_tail and not self._is_tail_safe_encoding(encoding):
                    logger.info(
                        f"{file_path} is {encoding}, which has no unambiguous line "
                        f"boundary in bytes; reading it whole")
                    return self.read_file_safe(file_path)
                with open(file_path, 'rb') as f:
                    if is_tail:
                        f.seek(-max_bytes, os.SEEK_END)
                    raw_content = f.read()

            if is_tail:
                raw_content = self._drop_partial_first_line(raw_content)

            info = dict(file_info)
            info["is_tail"] = is_tail
            info["shown_bytes"] = len(raw_content)
            info["shown_size_human"] = self._format_size(len(raw_content))
            return True, self._decode_bytes(raw_content, encoding), info

        except UnicodeDecodeError as e:
            return False, "", {"error": _("Encoding error: {0}").format(str(e))}
        except Exception as e:
            logger.error(f"Tail read error: {str(e)}")
            return False, "", {"error": str(e)}

    def _read_encrypted_log(self, file_path: str, file_info: Dict[str, Any],
                            key_candidates: Sequence[Tuple[str, str]],
                            max_bytes: Optional[int] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Decrypt a StreamingLogCipher log, one record per line.

        The key is the first candidate that opens the file's first record. With
        *max_bytes*, only the last whole records fitting it are kept -- records
        cannot be read from an arbitrary offset, so the whole file is still
        decrypted. A later record that fails to decrypt is skipped and counted
        in info["skipped_records"]; the ones after it are still tried, and a
        wrong key never yields text, so this cannot show garbage.
        """
        records = deque()
        kept_bytes = 0
        is_tail = False
        skipped = 0
        key = None
        with open(file_path, 'rb') as f:
            for payload in StreamingLogCipher.iter_payloads(f):
                if key is None:
                    key, record = self._open_first_record(payload, key_candidates)
                    if key is None:
                        return False, "", {"error": self._no_log_key_message(key_candidates)}
                else:
                    try:
                        record = StreamingLogCipher.decrypt_record(key, payload)
                    except (InvalidTag, ValueError):
                        skipped += 1
                        continue
                records.append(record)
                kept_bytes += len(record) + 1
                while max_bytes and kept_bytes > max_bytes and len(records) > 1:
                    kept_bytes -= len(records.popleft()) + 1
                    is_tail = True

        # Bytes but not one whole record: not this format (a whole-file encrypted
        # .enc, say), or a first record caught mid-write.
        if key is None and file_info.get("size", 0) > 0:
            return False, "", {"error": _("This file does not contain any readable encrypted log records.")}

        raw_content = b"".join(record + b"\n" for record in records)
        info = dict(file_info)
        info["is_tail"] = is_tail
        info["shown_bytes"] = len(raw_content)
        info["shown_size_human"] = self._format_size(len(raw_content))
        info["skipped_records"] = skipped
        if skipped:
            logger.warning(f"{file_path}: {skipped} record(s) did not decrypt and were skipped")
        return True, self._decode_bytes(raw_content, 'utf-8'), info

    @staticmethod
    def _open_first_record(payload: bytes, key_candidates: Sequence[Tuple[str, str]]):
        """(key, plaintext) for the first candidate whose key decrypts *payload*, else (None, None)."""
        for service_name, app_identifier in key_candidates:
            key = StreamingLogCipher.find_key(service_name, app_identifier)
            if key is None:
                continue
            try:
                return key, StreamingLogCipher.decrypt_record(key, payload)
            except (InvalidTag, ValueError):
                continue
        return None, None

    @staticmethod
    def _no_log_key_message(key_candidates: Sequence[Tuple[str, str]]) -> str:
        advice = _("Set the service name and app ID under \"Encrypted logs\" in this "
                   "tracker's settings to the ones the app writing this log uses.")
        if not key_candidates:
            return _("This log is encrypted, and there is no service name and app ID "
                     "to look up its key with.") + " " + advice
        tried = ", ".join(f"{service} / {app}" for service, app in key_candidates)
        return _("This log is encrypted, and no key found for it opens it (tried: {0}).").format(tried) + " " + advice

    @classmethod
    def _is_tail_safe_encoding(cls, encoding: str) -> bool:
        return str(encoding).lower().startswith(cls.TAIL_SAFE_ENCODING_PREFIXES)

    @staticmethod
    def _drop_partial_first_line(raw_content: bytes) -> bytes:
        """Cut everything before the first line break.

        A slice taken from the middle of a file starts mid-line. Content with
        nothing after its first line break is returned untouched -- a single
        long line, or a budget smaller than one line -- since cutting it would
        leave nothing to show.
        """
        newline = raw_content.find(b'\n')
        if newline == -1 or newline + 1 >= len(raw_content):
            return raw_content
        return raw_content[newline + 1:]

    def _decode_bytes(self, raw_content: bytes, encoding: str) -> str:
        """Decode file bytes to text, keeping null bytes visible as replacement characters."""
        if b'\x00' in raw_content:
            raw_content = raw_content.replace(b'\x00', b'\xef\xbf\xbd')
        return raw_content.decode(encoding, errors='replace')

    def _read_compressed_tail(self, file_path: str, max_bytes: int) -> Tuple[bytes, bool]:
        """Decompress a file, keeping only its last *max_bytes*."""
        tail = bytearray()
        is_tail = False

        def consume(stream):
            nonlocal is_tail
            while True:
                chunk = stream.read(self.COMPRESSED_READ_CHUNK)
                if not chunk:
                    return
                tail.extend(chunk)
                if len(tail) > max_bytes:
                    del tail[:len(tail) - max_bytes]
                    is_tail = True

        ext = Path(file_path).suffix.lower()
        if ext == '.gz':
            with gzip.open(file_path, 'rb') as f:
                consume(f)
        elif ext == '.bz2':
            with bz2.open(file_path, 'rb') as f:
                consume(f)
        elif ext == '.zip':
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                if not zip_ref.namelist():
                    raise ValueError(_("Empty zip archive"))
                for name in zip_ref.namelist():
                    if self.is_log_file(name) and not name.endswith('/'):
                        with zip_ref.open(name) as f:
                            consume(f)
                        break
                else:
                    raise ValueError(_("No log files in zip"))
        else:
            raise ValueError(_("Unsupported compression: {0}").format(ext))

        return bytes(tail), is_tail

    def _read_compressed_file(self, file_path: str) -> str:
        """Read compressed files with null byte handling."""
        path = Path(file_path)
        ext = path.suffix.lower()
        
        if ext == '.gz':
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                return f.read()
        
        elif ext == '.bz2':
            with bz2.open(file_path, 'rt', encoding='utf-8') as f:
                return f.read()
        
        elif ext == '.zip':
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                if not zip_ref.namelist():
                    raise ValueError(_("Empty zip archive"))
                
                for name in zip_ref.namelist():
                    if self.is_log_file(name) and not name.endswith('/'):
                        with zip_ref.open(name) as f:
                            content = f.read()
                            
                            # Handle null bytes in zip content
                            if b'\x00' in content:
                                # Replace null bytes with replacement character
                                content = content.replace(b'\x00', b'\xef\xbf\xbd')
                                return content.decode('utf-8', errors='replace')
                            return content.decode('utf-8', errors='replace')
                
                raise ValueError(_("No log files in zip"))
        
        raise ValueError(_("Unsupported compression: {0}").format(ext))
    
    def _detect_encoding(self, sample: bytes) -> str:
        """Detect encoding with null byte awareness."""
        if not sample:
            return 'utf-8'
        
        # Handle null byte patterns
        if sample.startswith(b'\x00\x00') or b'\x00\x00' in sample:
            return 'utf-16-be'
        elif sample.startswith(b'\x00') or b'\x00' in sample:
            # Check for alternating null bytes (UTF-16 LE pattern)
            if len(sample) > 1 and sample[1] == 0:
                return 'utf-16-le'
        
        # Check for UTF BOMs first (fastest method)
        if sample.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        if sample.startswith(b'\xff\xfe'):
            return 'utf-16'
        if sample.startswith(b'\xfe\xff'):
            return 'utf-16-be'
        
        # For files with ANSI escape codes, try UTF-8 first since most modern logs use UTF-8
        try:
            # Test if sample can be decoded as UTF-8
            sample.decode('utf-8')
            return 'utf-8'
        except UnicodeDecodeError:
            pass
        
        # Use chardet as fallback
        try:
            result = chardet.detect(sample)
            if result['confidence'] > 0.7:
                return result['encoding'] or 'utf-8'
        except Exception:
            pass
        
        return 'utf-8'
    
    def get_file_preview(self, file_path: str, max_lines: int = 10, max_chars: int = 1000) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Get a preview of a file (first few lines).
        
        Args:
            file_path: Path to the file
            max_lines: Maximum number of lines to preview
            max_chars: Maximum characters to preview
            
        Returns:
            Tuple of (success, preview_content, info)
        """
        success, content, info = self.read_file_safe(file_path)
        
        if not success:
            return False, "", info
        
        # Take first few lines
        lines = content.split('\n')[:max_lines]
        preview = '\n'.join(lines)
        
        # Truncate if too long
        if len(preview) > max_chars:
            preview = preview[:max_chars] + "..."
        
        # Add preview info
        info["preview_lines"] = len(lines)
        info["total_lines"] = content.count('\n') + 1
        info["is_truncated"] = len(content) > len(preview)
        
        return True, preview, info
    
    def validate_file_for_viewing(self, file_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate if a file is suitable for viewing in the log viewer.

        Size is not a bar: the viewer reads the tail, and that costs the same
        whatever the file's size. get_file_info() still warns about a large file,
        and whole-file readers keep their own MAX_FILE_SIZE limit.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (is_valid, reason, info)
        """
        file_info = self.get_file_info(file_path)
        
        if "error" in file_info:
            return False, file_info["error"], file_info
        
        if not file_info["is_file"]:
            return False, _("Path is not a file"), file_info
        
        if not file_info["readable"]:
            return False, _("File is not readable"), file_info
        
        if file_info.get("is_binary", False):
            return False, _("File may contain corrupted data or non-text content"), file_info
        
        return True, _("File is valid for viewing"), file_info 