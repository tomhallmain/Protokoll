"""
Worker threads for reading and searching logs off the GUI thread.

A compressed log is decompressed in full to reach its end, an encrypted one is
decrypted in full, and a search reads every file whole, so none of these can
run on the GUI thread without freezing it. Each worker does the file work and
emits one result signal; only the slot receiving it, on the GUI thread, touches
widgets. Every result carries the generation the request was made under, so
the window can drop results that a newer request has made stale.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from ..internal.log_search import search_files
from ..utils.file_handler import FileHandler
from ..utils.logging_setup import get_logger

logger = get_logger('ui.log_workers')


@dataclass
class LoadResult:
    file_path: str
    #: Validation outcome; when False, reason says why and nothing was read.
    is_valid: bool
    reason: str
    file_info: Dict[str, Any]
    success: bool = False
    content: str = ""
    read_info: Dict[str, Any] = field(default_factory=dict)


class _LogWorker(QThread):
    """A worker with a cancel flag. Not parented: MainWindow keeps the reference."""

    def __init__(self, generation: int):
        super().__init__()
        self.generation = generation
        #: Set by MainWindow once this worker's result signal has reached it.
        self.delivered = False
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()


class LogLoadThread(_LogWorker):
    """Validate a log file and read the end of it for viewing."""
    loaded = pyqtSignal(int, object)  # generation, LoadResult

    def __init__(self, generation: int, file_path: str, max_bytes: int,
                 key_candidates: Sequence[Tuple[str, str]]):
        super().__init__(generation)
        self.file_path = file_path
        self.max_bytes = max_bytes
        self.key_candidates = list(key_candidates)

    def run(self):
        # Records cannot be skipped in a StreamingLogCipher file, so a load is
        # not interrupted part way; a cancelled one finishes and is dropped.
        file_handler = FileHandler()
        try:
            is_valid, reason, file_info = file_handler.validate_file_for_viewing(self.file_path)
            result = LoadResult(self.file_path, is_valid, reason, file_info)
            if is_valid:
                result.success, result.content, result.read_info = file_handler.read_tail_safe(
                    self.file_path, self.max_bytes,
                    key_candidates=self.key_candidates, file_info=file_info)
        except Exception as e:
            logger.error(f"Loading {self.file_path} failed: {e}", exc_info=True)
            result = LoadResult(self.file_path, True, "", {}, success=False,
                                read_info={"error": str(e)})
        self.loaded.emit(self.generation, result)


class LogSearchThread(_LogWorker):
    """Search a set of log files; the file list is gathered on this thread too."""
    searched = pyqtSignal(int, object)  # generation, log_search.SearchOutcome
    failed = pyqtSignal(int, str)       # generation, error message

    def __init__(self, generation: int, list_file_paths: Callable[[], List[str]],
                 find_matches: Callable[[str], list],
                 key_candidates: Callable[[str], Sequence[Tuple[str, str]]],
                 search_text: str, all_files: bool):
        super().__init__(generation)
        self.list_file_paths = list_file_paths
        self.find_matches = find_matches
        self.key_candidates = key_candidates
        # Carried for the window to describe the outcome with.
        self.search_text = search_text
        self.all_files = all_files

    def run(self):
        try:
            outcome = search_files(
                self.list_file_paths(), FileHandler(), self.find_matches,
                key_candidates=self.key_candidates, should_cancel=self.is_cancelled)
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            self.failed.emit(self.generation, str(e))
            return
        self.searched.emit(self.generation, outcome)
