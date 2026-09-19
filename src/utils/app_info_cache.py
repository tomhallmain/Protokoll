import json
import os
import shutil
import threading
from typing import Any, Dict, List, Optional

from .encryptor import decrypt_data_from_file, encrypt_data_to_file
from .globals import AppInfo
from .logging_setup import get_logger

logger = get_logger('utils.app_info_cache')


class AppInfoCache:
    """This app's state that is encrypted at rest.

    Holds what says which applications are tracked and where their logs are --
    tracker definitions, the custom log directory list, and the last-used
    tracker and log file. Window geometry and search toggles stay in the plain
    config file, since they say nothing about the tracked apps.

    The whole cache is one encrypted blob, so a change means re-encrypting all
    of it. Keys come from the key store shared with the other applications
    under AppInfo.SERVICE_NAME. Callers batch their changes and call store()
    once rather than storing per edit: every store re-encrypts everything, and
    the first one in a process also checks the keypair, which costs PBKDF2 at a
    million iterations.
    """

    CACHE_FILENAME = "app_info_cache.enc"
    JSON_FILENAME = "app_info_cache.json"
    INFO_KEY = "info"
    TRACKERS_KEY = "trackers"
    NUM_BACKUPS = 4

    _instances: Dict[str, 'AppInfoCache'] = {}
    _instances_lock = threading.Lock()

    @classmethod
    def for_directory(cls, directory: str) -> 'AppInfoCache':
        """The instance for *directory*, creating it on first use.

        Shared per directory because each instance keeps the whole cache in
        memory and writes all of it: two instances over one file would each
        overwrite the other's changes.
        """
        key = os.path.normcase(os.path.abspath(directory))
        with cls._instances_lock:
            if key not in cls._instances:
                cls._instances[key] = cls(directory)
            return cls._instances[key]

    @classmethod
    def clear_instances(cls) -> None:
        """Drop the per-directory instances, so the next use reloads from disk."""
        with cls._instances_lock:
            cls._instances.clear()

    def __init__(self, directory: str):
        self._lock = threading.RLock()
        self._cache: Dict[str, Any] = {AppInfoCache.INFO_KEY: {}, AppInfoCache.TRACKERS_KEY: {}}
        self._dirty = False
        #: Set when a cache file existed but could not be read. store() refuses
        #: while it is set, so an unreadable cache is never overwritten by the
        #: empty one this instance would otherwise hold.
        self.load_error: Optional[str] = None
        self._directory = directory
        self._cache_loc = os.path.join(directory, AppInfoCache.CACHE_FILENAME)
        self._json_loc = os.path.join(directory, AppInfoCache.JSON_FILENAME)
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def store(self) -> bool:
        """Write the cache out.

        Returns True when it was encrypted, False when encryption failed and it
        was written as plain JSON, which load() picks up first and migrates on
        the next run. Raises when neither worked, and when the cache on disk
        could not be read at startup.
        """
        with self._lock:
            if self.load_error:
                raise Exception(
                    f"Refusing to overwrite the cache at {self._cache_loc}, which could "
                    f"not be read at startup: {self.load_error}"
                )

            try:
                cache_data = json.dumps(self._cache).encode('utf-8')
            except Exception as e:
                raise Exception(f"Error compiling application cache: {e}")

            try:
                encrypt_data_to_file(
                    cache_data,
                    AppInfo.SERVICE_NAME,
                    AppInfo.APP_IDENTIFIER,
                    self._cache_loc,
                )
                self._dirty = False
                self._discard_json_fallback()
                return True
            except Exception as e:
                logger.error(f"Error encrypting cache: {e}")

            try:
                with open(self._json_loc, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f)
                try:
                    # Owner-only: this is the content the encrypted cache exists
                    # to protect. No-op on Windows, where the user profile
                    # already restricts access.
                    os.chmod(self._json_loc, 0o600)
                except OSError:
                    pass
                logger.warning(f"Stored the application cache unencrypted at {self._json_loc}")
                self._dirty = False
                return False
            except Exception as e:
                raise Exception(f"Error storing application cache: {e}")

    def _discard_json_fallback(self) -> None:
        """Remove a plaintext fallback once the encrypted cache holds the values.

        load() reads the fallback first, so one left behind would replace newer
        values with whatever it happened to hold when encryption last failed.
        """
        if not os.path.exists(self._json_loc):
            return
        try:
            os.remove(self._json_loc)
        except OSError as e:
            logger.error(f"Could not remove the plaintext cache at {self._json_loc}: {e}")

    def store_if_dirty(self) -> None:
        """Write the cache out when something has changed since the last write."""
        with self._lock:
            if self._dirty:
                self.store()

    def _try_load_cache_from_file(self, path: str) -> Dict[str, Any]:
        """Decrypt and parse one cache file. Raises on failure."""
        decrypted = decrypt_data_from_file(
            path,
            AppInfo.SERVICE_NAME,
            AppInfo.APP_IDENTIFIER,
        )
        return json.loads(decrypted.decode('utf-8'))

    def load(self) -> None:
        with self._lock:
            self.load_error = None

            if os.path.exists(self._json_loc):
                logger.info("Detected JSON-format application cache, will attempt migration to encrypted store")
                try:
                    with open(self._json_loc, "r", encoding="utf-8") as f:
                        self._cache = json.load(f)
                except Exception as e:
                    self.load_error = f"{self._json_loc}: {e}"
                    logger.error(f"Failed to load cache from {self._json_loc}: {e}")
                    return
                try:
                    if self.store():
                        logger.info(f"Migrated application cache from {self._json_loc} to encrypted store")
                    else:
                        logger.warning("Encrypted store of application cache failed; keeping JSON cache file")
                except Exception as e:
                    logger.error(f"Failed to store migrated application cache: {e}")
                return

            cache_paths = [self._cache_loc] + self._get_backup_paths()
            existing = [path for path in cache_paths if os.path.exists(path)]
            if not existing:
                logger.info(f"No cache file found at {self._cache_loc}, creating new cache")
                return

            for path in existing:
                try:
                    self._cache = self._try_load_cache_from_file(path)
                except Exception as e:
                    logger.error(f"Failed to load cache from {path}: {e}")
                    continue
                if path == self._cache_loc:
                    message = f"Loaded cache from {self._cache_loc}"
                    rotated_count = self._rotate_backups()
                    if rotated_count > 0:
                        message += f", rotated {rotated_count} backups"
                    logger.info(message)
                else:
                    logger.warning(f"Loaded cache from backup: {path}")
                return

            self.load_error = f"Failed to load cache from all locations: {existing}"
            logger.error(self.load_error)

    def matches_stored(self) -> bool:
        """Whether the encrypted file on disk decrypts back to what is held here.

        Used before deleting the plaintext a migration read from: a write that
        cannot be read back is indistinguishable from no write at all.
        """
        with self._lock:
            try:
                return self._try_load_cache_from_file(self._cache_loc) == self._cache
            except Exception as e:
                logger.error(f"Could not read back the cache at {self._cache_loc}: {e}")
                return False

    def export_as_json(self, json_path: str = None) -> str:
        """Write the cache out unencrypted, for inspection or backup."""
        if json_path is None:
            json_path = self._json_loc
        with self._lock:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        return json_path

    # ------------------------------------------------------------------
    # Values
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if AppInfoCache.INFO_KEY not in self._cache:
                self._cache[AppInfoCache.INFO_KEY] = {}
            self._cache[AppInfoCache.INFO_KEY][key] = value
            self._dirty = True

    def get(self, key: str, default_val: Any = None) -> Any:
        with self._lock:
            info = self._cache.get(AppInfoCache.INFO_KEY, {})
            return info.get(key, default_val)

    def _get_trackers(self) -> Dict[str, Any]:
        """Tracker metadata by name. Must be called from within a locked context."""
        if AppInfoCache.TRACKERS_KEY not in self._cache:
            self._cache[AppInfoCache.TRACKERS_KEY] = {}
        return self._cache[AppInfoCache.TRACKERS_KEY]

    def get_tracker(self, name: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            metadata = self._get_trackers().get(name)
            return dict(metadata) if metadata is not None else None

    def set_tracker(self, name: str, metadata: Dict[str, Any]) -> None:
        with self._lock:
            self._get_trackers()[name] = dict(metadata)
            self._dirty = True

    def remove_tracker(self, name: str) -> None:
        with self._lock:
            if self._get_trackers().pop(name, None) is not None:
                self._dirty = True

    def tracker_names(self) -> List[str]:
        with self._lock:
            return list(self._get_trackers())

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------

    def _get_backup_paths(self) -> List[str]:
        """Backup file paths, newest first."""
        backup_paths = []
        for i in range(1, AppInfoCache.NUM_BACKUPS + 1):
            index = "" if i == 1 else f"{i}"
            backup_paths.append(f"{self._cache_loc}.bak{index}")
        return backup_paths

    def _rotate_backups(self) -> int:
        """Shift each backup one position older and copy the cache to the newest."""
        backup_paths = self._get_backup_paths()
        rotated_count = 0

        if os.path.exists(backup_paths[-1]):
            os.remove(backup_paths[-1])

        for i in range(len(backup_paths) - 1, 0, -1):
            if os.path.exists(backup_paths[i - 1]):
                shutil.copy2(backup_paths[i - 1], backup_paths[i])
                rotated_count += 1

        shutil.copy2(self._cache_loc, backup_paths[0])

        return rotated_count
