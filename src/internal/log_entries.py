"""
Log entry parsing and search-match grouping.

A "logical entry" is one logger call, which may span several physical lines: an
exception with a traceback, a formatted multi-line message, or an embedded newline in
a logged value. A search term found anywhere inside an entry should return the whole
entry, not the isolated line it landed on.

Protokoll reads logs produced by arbitrary apps and languages, so entry boundaries are
heuristic rather than a parse of one known format.

Everything here is pure: lines in, tuples out. No Qt, no config lookups and no file
access, so the search core is usable and testable without the UI.
"""

import re

# Levels recognized both when detecting entry starts and when stripping a leading
# level prefix for "limit to line start" matching. Kept as one list so the two can't
# drift apart.
LOG_LEVELS = "INFO|ERROR|WARNING|DEBUG|TRACE"

# Primary entry-start signal: a leading timestamp, covering the common variants
# (date/time separated by a space or 'T', optional fractional seconds).
ENTRY_START_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}([.,]\d+)?"
)

# Fallback for producers whose format has no leading timestamp. Deliberately stricter
# than LOG_LEVEL_PATTERN below: the level token must sit in a bounded prefix of a line
# that does not start with whitespace, so an indented traceback frame, or a level word
# buried late in a long message, is not mistaken for the start of a new entry.
ENTRY_START_LEVEL_PATTERN = re.compile(
    rf"^(?!\s).{{0,80}}?\b({LOG_LEVELS})\b", re.IGNORECASE
)

# Strips a leading timestamp/level prefix so "limit to line start" can anchor the
# search at the start of the message itself. Intentionally permissive - it only has to
# find the prefix on a line already known to be worth testing.
LOG_LEVEL_PATTERN = re.compile(rf"^.*?({LOG_LEVELS})\W*", re.IGNORECASE)

# Cap on how many physical lines of a single entry get rendered, so one deep stack
# trace can't flood the results view.
DEFAULT_MAX_ENTRY_LINES = 200


def is_entry_start(line):
    """Whether this physical line begins a new logical entry."""
    return bool(ENTRY_START_TIMESTAMP_PATTERN.match(line)
                or ENTRY_START_LEVEL_PATTERN.match(line))


def split_into_entries(lines, max_entry_lines=DEFAULT_MAX_ENTRY_LINES):
    """
    Group physical lines into logical entries, as inclusive 0-based (start, end) index
    pairs covering every line in order. Indices rather than entry text keep this
    composable with the index-based grouping below.

    Content before the first recognized entry start (a startup banner, say) becomes an
    implicit leading entry so nothing is dropped. If that leading entry alone exceeds
    max_entry_lines the heuristic is not recognizing this file's format at all - a plain
    text file picked up by extension, for instance - so grouping is abandoned in favour
    of one entry per line, rather than collapsing the file into a single unreadable block.
    """
    starts = [i for i, line in enumerate(lines) if is_entry_start(line)]
    if not starts or starts[0] > max_entry_lines:
        return one_entry_per_line(lines)

    boundaries = starts if starts[0] == 0 else [0] + starts
    return [
        (start, (boundaries[i + 1] - 1) if i + 1 < len(boundaries) else len(lines) - 1)
        for i, start in enumerate(boundaries)
    ]


def one_entry_per_line(lines):
    """Entry bounds for the ungrouped path, where each physical line stands alone."""
    return [(i, i) for i in range(len(lines))]


def line_matches(line, search_re, search_text_lower, use_regex=False,
                 limit_to_line_start=False):
    """Whether one physical line satisfies the search, honouring the search modifiers."""
    if limit_to_line_start:
        search_in = LOG_LEVEL_PATTERN.sub("", line, count=1)
        if use_regex:
            return search_re.match(search_in) is not None
        return search_in.lower().startswith(search_text_lower)
    if use_regex:
        return bool(search_re.search(line))
    return search_text_lower in line.lower()


def render_entry(lines, bounds, matched_lines, max_entry_lines=DEFAULT_MAX_ENTRY_LINES):
    """
    Render one entry as a list of (line_num, line_content, is_match) physical lines,
    line_num being 1-based. is_match stays true only for the lines that actually
    matched, so the rest of the entry can be drawn plainer. Lines past max_entry_lines
    are replaced by a truncation marker, which carries a line_num of None.
    """
    start, end = bounds
    last = min(end, start + max(1, max_entry_lines) - 1)
    rendered = [
        (idx + 1, lines[idx].rstrip('\n'), idx in matched_lines)
        for idx in range(start, last + 1)
    ]
    truncated = end - last
    if truncated > 0:
        rendered.append((None, f"... {truncated} more lines truncated ...", False))
    return rendered


def group_matches(lines, matched_lines, multiline=True, context_before=0,
                  context_after=0, max_entry_lines=DEFAULT_MAX_ENTRY_LINES):
    """
    Turn a set of matched line indices into blocks of entries, each entry a list of
    (line_num, line_content, is_match) physical lines.

    A match anywhere inside an entry returns the whole entry. context_before/after count
    entries on either side of a matching one; overlapping or adjacent context windows
    merge into a single contiguous block. With multiline off every entry holds a single
    line, which reproduces the ungrouped per-line behaviour through the same code.
    """
    if not matched_lines:
        return []

    entries = (split_into_entries(lines, max_entry_lines) if multiline
               else one_entry_per_line(lines))

    entry_of = [0] * len(lines)
    for entry_idx, (start, end) in enumerate(entries):
        for idx in range(start, end + 1):
            entry_of[idx] = entry_idx
    matched_entries = sorted({entry_of[idx] for idx in matched_lines})

    ranges = []
    for entry_idx in matched_entries:
        start = max(0, entry_idx - context_before)
        end = min(len(entries) - 1, entry_idx + context_after)
        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
        else:
            ranges.append((start, end))

    return [
        [render_entry(lines, entries[entry_idx], matched_lines, max_entry_lines)
         for entry_idx in range(start, end + 1)]
        for start, end in ranges
    ]


def find_matches(content, search_re, search_text_lower, use_regex=False,
                 limit_to_line_start=False, multiline=True, context_before=0,
                 context_after=0, max_entry_lines=DEFAULT_MAX_ENTRY_LINES):
    """Search one file's content and return the grouped match blocks."""
    lines = content.split('\n')
    matched_lines = {
        i for i, line in enumerate(lines)
        if line_matches(line, search_re, search_text_lower, use_regex, limit_to_line_start)
    }
    return group_matches(lines, matched_lines, multiline, context_before,
                         context_after, max_entry_lines)


def count_matches(blocks):
    """One entry containing any matching line counts as one match."""
    return sum(
        1 for block in blocks for entry in block
        if any(is_match for _, _, is_match in entry)
    )
