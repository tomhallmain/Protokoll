import os
import gzip
import bz2
import zipfile
import chardet
import sys
import warnings
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union

from .logging_manager import LoggingManager

logger = LoggingManager.get_logger('utils.file_handler')

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
    
    # File size limits (100MB max, 10MB warning)
    MAX_FILE_SIZE = 100 * 1024 * 1024
    WARN_FILE_SIZE = 10 * 1024 * 1024
    
    # Sample size for detection (4KB optimized for chunk size)
    DETECTION_SAMPLE_SIZE = 4096

    def __init__(self):
        # Removed python-magic dependency
        pass
    
    @classmethod
    def is_log_file(cls, file_path: str) -> bool:
        """Check if file has a log-like extension."""
        return bool(Path(file_path).suffix.lower() in cls.LOG_EXTENSIONS)
 
    @classmethod
    def is_compressed(cls, file_path: str) -> bool:
        """Check if file is compressed."""
        return bool(Path(file_path).suffix.lower() in cls.COMPRESSED_EXTENSIONS)
    
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
            return {"error": "File does not exist"}
        
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
                "extension": path.suffix.lower(),
                "last_modified": stat.st_mtime,
                "readable": os.access(file_path, os.R_OK),
                "warnings": []
            }
            
            # Size warnings
            if file_size > self.MAX_FILE_SIZE:
                info["warnings"].append(f"File too large ({info['size_human']})")
            elif file_size > self.WARN_FILE_SIZE:
                info["warnings"].append(f"Large file ({info['size_human']})")
            
            # Binary detection
            if info["is_file"] and info["readable"]:
                try:
                    with open(file_path, 'rb') as f:
                        sample = f.read(self.DETECTION_SAMPLE_SIZE)
                        info["is_binary"] = self._is_binary_sample(sample)
                        info["sample"] = sample  # Store for later use
                except Exception as e:
                    logger.error(f"Binary detection failed: {str(e)}")
                    info["is_binary"] = True
                    info["warnings"].append("Binary detection failed")
                
                if info.get("is_binary", False):
                    info["warnings"].append("Binary file detected")
            
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
    
    def read_file_safe(self, file_path: str, max_size: Optional[int] = None) -> Tuple[bool, Union[str, bytes], Dict[str, Any]]:
        """Safe file reading with compression support and optimizations."""
        max_size = max_size or self.MAX_FILE_SIZE
        file_info = self.get_file_info(file_path)
        
        # Error handling
        if "error" in file_info:
            return False, "", file_info
        if not file_info["is_file"]:
            return False, "", {"error": "Not a file"}
        if not file_info["readable"]:
            return False, "", {"error": "Not readable"}
        if file_info["size"] > max_size:
            return False, "", {"error": f"Size exceeds limit ({file_info['size_human']})"}
        if file_info.get("is_binary", False):
            return False, "", {"error": "Binary file", "warnings": file_info["warnings"]}
        
        try:
            # Handle compressed files
            if file_info["is_compressed"]:
                content = self._read_compressed_file(file_path)
            # Handle text files
            else:
                sample = file_info.get("sample", b"")
                encoding = self._detect_encoding(sample)
                
                # Read file with null byte handling
                with open(file_path, 'rb') as f:
                    raw_content = f.read()
                    
                    # Handle files with null bytes
                    if b'\x00' in raw_content:
                        # Replace null bytes with Unicode replacement character
                        raw_content = raw_content.replace(b'\x00', b'\xef\xbf\xbd')
                        content = raw_content.decode(encoding, errors='replace')
                    else:
                        content = raw_content.decode(encoding, errors='replace')
            
            return True, content, file_info
            
        except UnicodeDecodeError as e:
            return False, "", {"error": f"Encoding error: {str(e)}"}
        except Exception as e:
            logger.error(f"Read error: {str(e)}")
            return False, "", {"error": str(e)}

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
                    raise ValueError("Empty zip archive")
                
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
                
                raise ValueError("No log files in zip")
        
        raise ValueError(f"Unsupported compression: {ext}")
    
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
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (is_valid, reason, info)
        """
        file_info = self.get_file_info(file_path)
        
        if "error" in file_info:
            return False, file_info["error"], file_info
        
        if not file_info["is_file"]:
            return False, "Path is not a file", file_info
        
        if not file_info["readable"]:
            return False, "File is not readable", file_info
        
        if file_info.get("is_binary", False):
            return False, "Binary file detected", file_info
        
        if file_info["size"] > self.MAX_FILE_SIZE:
            return False, f"File too large ({file_info['size_human']})", file_info
        
        return True, "File is valid for viewing", file_info 