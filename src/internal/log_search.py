"""
Running a search over a set of log files: reading each one, matching it, and
recording the ones that could not be searched and why.

Matching itself is log_entries' job; this module only drives it file by file.
No Qt, so it runs on a worker thread and is testable without the UI.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Sequence, Tuple

from ..utils.translations import _

#: Why a file was skipped: it failed validation (binary, unreadable, missing),
#: or it passed validation and then could not be read (too large to search,
#: undecryptable, bad encoding).
SKIP_VALIDATION = "validation"
SKIP_READ = "read"


@dataclass
class SearchOutcome:
    #: (file_path, blocks) for each file with at least one match, in search order.
    file_results: List[Tuple[str, list]] = field(default_factory=list)
    #: (file_path, SKIP_VALIDATION or SKIP_READ, reason) for each file not searched.
    skipped_files: List[Tuple[str, str, str]] = field(default_factory=list)
    #: Files attempted, skipped ones included.
    files_searched: int = 0
    #: True when should_cancel() stopped the run before every file was tried.
    cancelled: bool = False


def search_files(file_paths: Sequence[str], file_handler, find_matches: Callable[[str], list],
                 key_candidates: Callable[[str], Sequence[Tuple[str, str]]] = lambda _path: (),
                 should_cancel: Callable[[], bool] = lambda: False) -> SearchOutcome:
    """
    Search each file in *file_paths* with *find_matches* (content -> blocks).

    *key_candidates* gives the keys to try for an encrypted file.
    *should_cancel* is checked before each file.
    """
    outcome = SearchOutcome()
    for file_path in file_paths:
        if should_cancel():
            outcome.cancelled = True
            break
        outcome.files_searched += 1

        is_valid, reason, file_info = file_handler.validate_file_for_viewing(file_path)
        if not is_valid:
            outcome.skipped_files.append((file_path, SKIP_VALIDATION, reason))
            continue
        success, content, read_info = file_handler.read_file_safe(
            file_path, key_candidates=key_candidates(file_path), file_info=file_info)
        if not success:
            outcome.skipped_files.append(
                (file_path, SKIP_READ, read_info.get("error", _("Unknown error"))))
            continue

        blocks = find_matches(content)
        if blocks:
            outcome.file_results.append((file_path, blocks))
    return outcome
