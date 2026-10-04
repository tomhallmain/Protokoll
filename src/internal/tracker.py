from datetime import datetime
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .log_directory_finder import LogDirectoryFinder
from ..utils.config_manager import ConfigManager
from ..utils.globals import AppInfo
from ..utils.logging_setup import get_logger
from ..utils.translations import _
from ..utils.file_handler import FileHandler

logger = get_logger('internal.tracker')

#: A date in a log file name ("app_2026-08-14.log.enc"), and anything after it.
_LOG_NAME_DATE = re.compile(r'[_\-.]?\d{4}-\d{2}-\d{2}.*$')


def app_identifier_from_log_name(file_path: str) -> str:
    """The app identifier a log file's name suggests: "sd_runner_2026-08-14.log.enc" -> "sd_runner"."""
    stem = os.path.basename(file_path).split('.')[0]
    return _LOG_NAME_DATE.sub('', stem)


def app_identifier_from_tracker_name(name: str) -> str:
    """The identifier-style spelling of a tracker name: "SD Runner" -> "sd_runner"."""
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


class Tracker:
    def __init__(self, name: str, description: str = "", config_manager: Optional[ConfigManager] = None):
        self.name = name
        self.description = description
        self.log_directories: Set[str] = set()  # Set of log directory paths
        self.created_at = datetime.now()
        self.config_manager = config_manager or ConfigManager()
        # The keyring identity the tracked app encrypts its logs under. Empty
        # means guessed per file: see log_key_candidates().
        self.log_encryption_service = ""
        self.log_encryption_app_id = ""
        # The name this tracker is stored under, so a rename replaces that
        # entry rather than leaving the tracker filed under both names.
        self._stored_name: Optional[str] = None

    def to_metadata(self) -> Dict[str, Any]:
        """The fields stored in the encrypted cache for this tracker."""
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "log_directories": list(self.log_directories),  # Convert set to list for JSON serialization
            "log_encryption_service": self.log_encryption_service,
            "log_encryption_app_id": self.log_encryption_app_id,
        }

    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any], config_manager: ConfigManager) -> 'Tracker':
        """A tracker from to_metadata()'s fields; ones added since a record was stored default to empty."""
        tracker = cls(metadata["name"], metadata["description"], config_manager)
        tracker.created_at = datetime.fromisoformat(metadata["created_at"])
        tracker.log_directories = set(metadata.get("log_directories", []))
        tracker.log_encryption_service = metadata.get("log_encryption_service", "")
        tracker.log_encryption_app_id = metadata.get("log_encryption_app_id", "")
        return tracker

    def save_metadata(self) -> None:
        """Save tracker metadata to the encrypted cache"""
        self.config_manager.save_tracker_metadata(
            self.name, self.to_metadata(), previous_name=self._stored_name)
        self._stored_name = self.name
    
    def add_log_directory(self, directory: str) -> bool:
        """Add a log directory to the tracker"""
        if not os.path.exists(directory):
            raise ValueError(_("Directory does not exist: {0}").format(directory))
        
        if not os.path.isdir(directory):
            raise ValueError(_("Path is not a directory: {0}").format(directory))
        
        # Add directory to set
        self.log_directories.add(directory)
        self.save_metadata()
        return True
    
    def remove_log_directory(self, directory: str) -> None:
        """Remove a log directory from the tracker"""
        if directory in self.log_directories:
            self.log_directories.remove(directory)
            self.save_metadata()

    def set_log_directories(self, directories: Iterable[str]) -> None:
        """
        Replace the tracked directories with `directories`, adding and removing as needed.

        Every addition is validated before anything is changed, so a bad path leaves the
        tracker exactly as it was instead of half-updated. Metadata is written once.
        """
        directories = set(directories)
        for directory in directories - self.log_directories:
            if not os.path.exists(directory):
                raise ValueError(_("Directory does not exist: {0}").format(directory))
            if not os.path.isdir(directory):
                raise ValueError(_("Path is not a directory: {0}").format(directory))

        self.log_directories = directories
        self.save_metadata()

    def set_log_encryption(self, service_name: str, app_identifier: str) -> None:
        """Set the keyring identity for this tracker's encrypted logs; empty values are guessed.

        Not saved on its own: set_log_directories(), which follows in both the
        create and the edit path, writes the metadata once for everything.
        """
        self.log_encryption_service = service_name.strip()
        self.log_encryption_app_id = app_identifier.strip()

    def log_key_candidates(self, file_path: str) -> List[Tuple[str, str]]:
        """
        The (service_name, app_identifier) pairs to try for an encrypted log, in order.

        An app ID set on the tracker is the only one tried. Otherwise it is
        guessed, first from the log file's name and then from the tracker's
        name. A wrong guess costs a keyring read and nothing more: the reader
        never creates a passphrase, and a wrong key fails to decrypt.
        """
        service = self.log_encryption_service or AppInfo.LOG_ENCRYPTION_SERVICE
        if self.log_encryption_app_id:
            app_ids = [self.log_encryption_app_id]
        else:
            app_ids = [app_identifier_from_log_name(file_path),
                       app_identifier_from_tracker_name(self.name)]
        candidates = []
        for app_id in app_ids:
            if app_id and (service, app_id) not in candidates:
                candidates.append((service, app_id))
        return candidates

    def get_log_files(self) -> List[Dict[str, Any]]:
        """Get all log files in the tracked directories"""
        log_files = []
        logger.debug(f"Searching for log files in directories: {self.log_directories}")
        
        file_handler = FileHandler()
        
        for directory in self.log_directories:
            try:
                logger.debug(f"Scanning directory: {directory}")
                for root, _dirs, files in os.walk(directory):
                    logger.debug(f"Scanning subdirectory: {root}")
                    for file in files:
                        file_path = os.path.join(root, file)
                        
                        # Use FileHandler to validate the file
                        if FileHandler.is_log_file(file_path):
                            file_info = file_handler.get_file_info(file_path)
                            
                            if "error" not in file_info and file_info["is_file"]:
                                logger.debug(f"Found log file: {file_path}")
                                log_files.append({
                                    "path": file_path,
                                    "last_modified": file_info["last_modified"],
                                    "size": file_info["size"],
                                    "size_human": file_info["size_human"],
                                    "is_compressed": file_info["is_compressed"],
                                    "is_encrypted": file_info["is_encrypted"],
                                    "warnings": file_info.get("warnings", [])
                                })
            except Exception as e:
                logger.error(f"Error reading directory {directory}: {e}")
        
        logger.debug(f"Total log files found: {len(log_files)}")
        return log_files
    
    def get_log_directories(self) -> List[str]:
        """Get all log directories in the tracker"""
        return list(self.log_directories)
    
    def search_logs(self, query: str) -> List[Dict[str, Any]]:
        """Search through all log files for a specific query"""
        results = []
        for log_file in self.get_log_files():
            try:
                with open(log_file["path"], "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        if query.lower() in line.lower():
                            results.append({
                                "file": log_file["path"],
                                "line": line_num,
                                "content": line.strip()
                            })
            except Exception as e:
                logger.error(f"Error reading file {log_file['path']}: {e}")
        return results
    
    @classmethod
    def load(cls, name: str, config_manager: Optional[ConfigManager] = None) -> Optional['Tracker']:
        """Load a tracker from the encrypted cache"""
        config_manager = config_manager or ConfigManager()
        metadata = config_manager.get_tracker_metadata(name)
        
        if metadata is None:
            return None
        
        try:
            tracker = cls.from_metadata(metadata, config_manager)
            tracker._stored_name = name
            return tracker
        except Exception as e:
            logger.error(f"Error loading tracker {name}: {e}")
            return None
    
    @classmethod
    def list_trackers(cls, config_manager: Optional[ConfigManager] = None) -> List['Tracker']:
        """List all available trackers"""
        config_manager = config_manager or ConfigManager()
        
        trackers = []
        for name in config_manager.list_tracker_names():
            tracker = cls.load(name, config_manager)
            if tracker:
                trackers.append(tracker)
        return trackers 