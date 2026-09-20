import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.app_info_cache import AppInfoCache
from ..utils.encryptor import KEY_STORE_DIR_ENV_VAR
from ..utils.logging_setup import get_logger

logger = get_logger('utils.config_manager')

class ConfigManager:
    """Settings for the app, split across two files.

    ``config.json`` holds the window geometry, the theme and the search
    toggles, in the clear. Anything naming a tracked application or its log
    paths goes to the encrypted AppInfoCache: the tracker definitions, the
    custom log directory list, and the keys in CACHE_KEYS / CACHE_KEY_PREFIXES
    below. get() and set() route by key, so callers use one interface.

    Cache writes are held until flush_cache(), because a store re-encrypts the
    whole cache and set() is called on every toggle and log file selection.
    Tracker edits are the exception and store immediately.
    """

    #: Keys held in the encrypted cache rather than config.json.
    CACHE_KEYS = frozenset({"recent_trackers", "last_tracker"})
    CACHE_KEY_PREFIXES = ("last_log_file_",)
    CUSTOM_LOG_DIRS_KEY = "custom_log_directories"

    LEGACY_TRACKERS_DIRNAME = "trackers"
    LEGACY_CUSTOM_LOG_DIRS_FILENAME = "custom_log_dirs.json"

    def __init__(self):
        self.app_name = "Protokoll"
        self.config_dir = Path(os.path.expanduser("~")) / ".protokoll"
        self.config_file = self.config_dir / "config.json"
        # The key store's override moves this app's whole directory, so the
        # cache and the keys that open it stay together.
        self.cache_dir = Path(os.environ.get(KEY_STORE_DIR_ENV_VAR) or self.config_dir)

        # Create necessary directories
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Default configuration
        self.default_config = {
            "window": {
                "width": 1024,
                "height": 768,
                "x": None,
                "y": None
            },
            "theme": "light",
            "log_viewer": {
                "font_size": 12,
                "font_family": "Consolas",
                "line_wrap": True,
                # How much of a log file's end the viewer loads. Everything
                # before it stays on disk, so opening a huge file costs the same
                # as opening a small one.
                "max_load_bytes": 2 * 1024 * 1024
            },
            "search": {
                "show_line_numbers": True,
                "use_regex": False,
                "limit_to_line_start": False,
                "all_files": False,
                "context_before": 0,
                "context_after": 0,
                "multiline_entries": True,
                "max_entry_lines": 200
            }
        }

        self.config = self.load_config()
        self.app_info_cache = AppInfoCache.for_directory(str(self.cache_dir))
        self._migrate_plaintext_state()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default if not exists"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with default config to ensure all keys exist
                    return {**self.default_config, **config}
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return self.default_config.copy()
        return self.default_config.copy()

    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    @classmethod
    def _is_cache_key(cls, key: str) -> bool:
        return key in cls.CACHE_KEYS or key.startswith(cls.CACHE_KEY_PREFIXES)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        if self._is_cache_key(key):
            return self.app_info_cache.get(key, default)

        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        if self._is_cache_key(key):
            self.app_info_cache.set(key, value)
            return

        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()

    def flush_cache(self) -> None:
        """Write out pending cache changes, at a point where a pause is acceptable."""
        try:
            self.app_info_cache.store_if_dirty()
        except Exception as e:
            logger.error(f"Error storing application cache: {e}")

    def add_recent_tracker(self, tracker_name: str) -> None:
        """Add a tracker to recent trackers list"""
        recent = self.get('recent_trackers', [])
        if tracker_name in recent:
            recent.remove(tracker_name)
        recent.insert(0, tracker_name)
        recent = recent[:10]  # Keep only 10 most recent
        self.set('recent_trackers', recent)

    # ------------------------------------------------------------------
    # Tracker metadata
    # ------------------------------------------------------------------

    def get_tracker_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        return self.app_info_cache.get_tracker(name)

    def save_tracker_metadata(
        self,
        name: str,
        metadata: Dict[str, Any],
        previous_name: Optional[str] = None,
    ) -> None:
        """Store one tracker's metadata, dropping *previous_name* on a rename."""
        if previous_name and previous_name != name:
            self.app_info_cache.remove_tracker(previous_name)
        self.app_info_cache.set_tracker(name, metadata)
        self.app_info_cache.store()

    def remove_tracker(self, name: str) -> None:
        self.app_info_cache.remove_tracker(name)
        self.app_info_cache.store()

    def list_tracker_names(self) -> List[str]:
        return self.app_info_cache.tracker_names()

    # ------------------------------------------------------------------
    # Custom log directories
    # ------------------------------------------------------------------

    def get_custom_log_directories(self) -> List[str]:
        return list(self.app_info_cache.get(self.CUSTOM_LOG_DIRS_KEY, []))

    def set_custom_log_directories(self, directories: List[str]) -> None:
        self.app_info_cache.set(self.CUSTOM_LOG_DIRS_KEY, list(directories))
        self.app_info_cache.store()

    # ------------------------------------------------------------------
    # Migration off the plaintext files
    # ------------------------------------------------------------------

    def _migrate_plaintext_state(self) -> None:
        """Move state written before the cache was encrypted into it.

        The plaintext is deleted only once the encrypted cache has been written
        and read back matching, so an install that cannot encrypt keeps working
        from the files it has and retries on the next run.
        """
        if self.app_info_cache.load_error:
            return

        legacy_trackers = self._read_legacy_tracker_metadata()
        legacy_custom_dirs = self._read_legacy_custom_log_directories()
        legacy_config_keys = {
            key: value for key, value in self.config.items() if self._is_cache_key(key)
        }
        if not (legacy_trackers or legacy_custom_dirs is not None or legacy_config_keys):
            return

        # Values already in the cache win: they are the ones the app has been
        # using, and a plaintext file left behind by a failed migration is as
        # old as that failure.
        for name, metadata in legacy_trackers.items():
            if self.app_info_cache.get_tracker(name) is None:
                self.app_info_cache.set_tracker(name, metadata)
        if legacy_custom_dirs is not None and self.app_info_cache.get(self.CUSTOM_LOG_DIRS_KEY) is None:
            self.app_info_cache.set(self.CUSTOM_LOG_DIRS_KEY, legacy_custom_dirs)
        for key, value in legacy_config_keys.items():
            if self.app_info_cache.get(key) is None:
                self.app_info_cache.set(key, value)

        try:
            encrypted = self.app_info_cache.store()
        except Exception as e:
            logger.error(f"Could not store the migrated cache, keeping the plaintext files: {e}")
            return
        if not encrypted or not self.app_info_cache.matches_stored():
            logger.warning("Migrated cache was not written encrypted; keeping the plaintext files")
            return

        self._delete_legacy_tracker_metadata()
        if legacy_custom_dirs is not None:
            self._delete_file(self.config_dir / self.LEGACY_CUSTOM_LOG_DIRS_FILENAME)
        if legacy_config_keys:
            for key in legacy_config_keys:
                self.config.pop(key, None)
            self.save_config()
        logger.info("Migrated tracker and log directory state into the encrypted cache")

    def _legacy_trackers_dir(self) -> Path:
        return self.config_dir / self.LEGACY_TRACKERS_DIRNAME

    def _read_legacy_tracker_metadata(self) -> Dict[str, Dict[str, Any]]:
        trackers_dir = self._legacy_trackers_dir()
        if not trackers_dir.is_dir():
            return {}

        trackers = {}
        for tracker_dir in trackers_dir.iterdir():
            metadata_file = tracker_dir / "metadata.json"
            if not metadata_file.is_file():
                continue
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.error(f"Error reading tracker metadata {metadata_file}: {e}")
                continue
            trackers[metadata.get("name", tracker_dir.name)] = metadata
        return trackers

    def _delete_legacy_tracker_metadata(self) -> None:
        trackers_dir = self._legacy_trackers_dir()
        if not trackers_dir.is_dir():
            return
        for tracker_dir in trackers_dir.iterdir():
            self._delete_file(tracker_dir / "metadata.json")
            self._remove_empty_dir(tracker_dir)
        self._remove_empty_dir(trackers_dir)

    def _read_legacy_custom_log_directories(self) -> Optional[List[str]]:
        legacy_file = self.config_dir / self.LEGACY_CUSTOM_LOG_DIRS_FILENAME
        if not legacy_file.is_file():
            return None
        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading custom log directories {legacy_file}: {e}")
            return None

    @staticmethod
    def _delete_file(path: Path) -> None:
        try:
            path.unlink()
        except OSError as e:
            logger.error(f"Could not delete {path}: {e}")

    @staticmethod
    def _remove_empty_dir(path: Path) -> None:
        try:
            path.rmdir()
        except OSError:
            pass  # not empty, or already gone
