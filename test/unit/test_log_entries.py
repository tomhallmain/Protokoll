"""
Unit tests for src.internal.log_entries - entry boundary detection and search-match
grouping. Pure functions, so these cover the heuristic's edge cases directly rather
than through the log viewer.

Expected values below were verified by running the actual implementation, since the
suite can't be executed in the sandbox this was written in.
"""

import re

import pytest

from src.internal.log_entries import (
    DEFAULT_MAX_ENTRY_LINES,
    count_matches,
    find_matches,
    is_entry_start,
    one_entry_per_line,
    render_entry,
    split_into_entries,
)

pytestmark = pytest.mark.unit


TRACEBACK_LOG = (
    "2026-08-24 10:00:01 INFO Starting up\n"
    "2026-08-24 10:00:02 ERROR Failed to connect\n"
    "Traceback (most recent call last):\n"
    '  File "app.py", line 12, in <module>\n'
    "    connect()\n"
    "ConnectionError: refused\n"
    "2026-08-24 10:00:03 INFO Retrying\n"
)


def plain(content, needle, **kwargs):
    """find_matches in plain-text mode, which is how the search bar defaults."""
    return find_matches(content, None, needle.lower(), **kwargs)


def rendered_text(blocks):
    return "\n".join(text for block in blocks for entry in block for _, text, _ in entry)


# --- entry start detection -------------------------------------------------

@pytest.mark.parametrize("timestamp", [
    "2026-08-24 10:00:01",
    "2026-08-24T10:00:01",
    "2026-08-24 10:00:01.123",
    "2026-08-24 10:00:01,123",
])
def test_timestamp_variants_start_an_entry(timestamp):
    assert is_entry_start(f"{timestamp} something happened")


def test_date_without_a_time_does_not_start_an_entry():
    """The timestamp rule requires a time component; a bare date is too weak a signal."""
    assert not is_entry_start("2026-08-24 something happened")


def test_leading_level_starts_an_entry_without_a_timestamp():
    assert is_entry_start("INFO boot ok")
    assert is_entry_start("myapp.module ERROR something failed")


@pytest.mark.parametrize("line", [
    "  File \"app.py\", line 12, in <module>",   # indented traceback frame
    "\tat Foo.bar(Foo.java:9)",                  # tab-indented stack frame
    "   2026-08-24 10:00:01 indented timestamp",
])
def test_indented_lines_are_continuations(line):
    """Leading whitespace is the strongest continuation signal there is."""
    assert not is_entry_start(line)


@pytest.mark.parametrize("line", [
    "TERRORS everywhere",        # level token inside a longer word
    "INFORMATIONAL notice",
    "ConnectionError: refused",  # the tail of a traceback, not a new entry
])
def test_level_lookalikes_do_not_start_an_entry(line):
    assert not is_entry_start(line)


def test_level_buried_late_in_a_line_does_not_start_an_entry():
    """Bounded prefix: a level word deep inside a long message isn't a header."""
    assert not is_entry_start("x" * 90 + " ERROR mentioned in passing")
    assert is_entry_start("x" * 40 + " ERROR still near the front")


# --- splitting -------------------------------------------------------------

def test_traceback_lines_group_under_their_header():
    entries = split_into_entries(TRACEBACK_LOG.split("\n"))
    assert entries == [(0, 0), (1, 5), (6, 7)]


def test_content_before_the_first_entry_becomes_an_implicit_entry():
    lines = ["=== MyApp v1.2 ===", "built from deadbeef", "2026-08-24 10:00:01 INFO up"]
    assert split_into_entries(lines) == [(0, 1), (2, 2)]


def test_entry_start_on_the_last_line_closes_at_end_of_file():
    assert split_into_entries(["prose", "2026-08-24 10:00:01 ERROR last"]) == [(0, 0), (1, 1)]


def test_every_line_its_own_entry_when_all_lines_are_starts():
    lines = [f"2026-08-24 10:00:0{i} ERROR e{i}" for i in range(5)]
    assert split_into_entries(lines) == one_entry_per_line(lines)


def test_file_with_no_recognizable_entries_falls_back_to_per_line():
    lines = [f"just some prose on line {i}" for i in range(10)]
    assert split_into_entries(lines) == one_entry_per_line(lines)


def test_oversized_leading_block_disables_grouping():
    """A giant implicit leading entry means the heuristic doesn't understand this
    file at all - one entry per line beats one unreadable block."""
    lines = ["just prose"] * 10 + ["2026-08-24 10:00:01 ERROR late"]
    assert split_into_entries(lines, max_entry_lines=5) == one_entry_per_line(lines)
    assert split_into_entries(lines, max_entry_lines=200) == [(0, 9), (10, 10)]


def test_empty_input_produces_no_entries():
    assert split_into_entries([]) == []


# --- rendering and truncation ----------------------------------------------

def test_render_entry_numbers_lines_absolutely_and_flags_only_the_match():
    lines = ["2026-08-24 10:00:02 ERROR boom", "  frame one", "  frame two"]
    assert render_entry(lines, (0, 2), {2}) == [
        (1, "2026-08-24 10:00:02 ERROR boom", False),
        (2, "  frame one", False),
        (3, "  frame two", True),
    ]


def test_long_entry_is_truncated_with_a_marker():
    lines = ["2026-08-24 10:00:02 ERROR boom"] + [f"  frame {i}" for i in range(10)]
    entry = render_entry(lines, (0, 10), {0}, max_entry_lines=3)

    assert [text for _, text, _ in entry[:3]] == [
        "2026-08-24 10:00:02 ERROR boom", "  frame 0", "  frame 1"]
    line_num, text, is_match = entry[-1]
    assert line_num is None, "the truncation marker is not a real line, so it has no number"
    assert "8 more lines truncated" in text
    assert is_match is False


@pytest.mark.parametrize("cap", [0, -5])
def test_degenerate_line_cap_still_renders_one_line(cap):
    """A nonsensical max_entry_lines must not render an entry as a marker and nothing else."""
    entry = render_entry(["ERROR a", "b", "c"], (0, 2), {0}, max_entry_lines=cap)
    assert entry[0] == (1, "ERROR a", True)
    assert entry[-1][0] is None


def test_entry_shorter_than_the_cap_has_no_marker():
    entry = render_entry(["ERROR a", "b"], (0, 1), {0}, max_entry_lines=DEFAULT_MAX_ENTRY_LINES)
    assert all(line_num is not None for line_num, _, _ in entry)


# --- grouping matches ------------------------------------------------------

def test_match_on_a_continuation_line_returns_the_whole_entry():
    text = rendered_text(plain(TRACEBACK_LOG, "ConnectionError"))

    assert "ERROR Failed to connect" in text
    assert "Traceback (most recent call last):" in text
    assert "Starting up" not in text
    assert "Retrying" not in text


def test_several_matching_lines_in_one_entry_count_once():
    assert count_matches(plain(TRACEBACK_LOG, "connect")) == 1


def test_multiline_disabled_returns_only_the_matching_line():
    text = rendered_text(plain(TRACEBACK_LOG, "ConnectionError", multiline=False))

    assert "ConnectionError: refused" in text
    assert "ERROR Failed to connect" not in text


def test_context_counts_entries_not_physical_lines():
    """One entry of context pulls in a whole neighbour, however many lines it spans."""
    text = rendered_text(plain(TRACEBACK_LOG, "ConnectionError", context_before=1, context_after=1))

    assert "Starting up" in text
    assert "Retrying" in text


def test_adjacent_matches_merge_into_one_block():
    content = "".join(f"2026-08-24 10:00:0{i} ERROR e{i}\n" for i in range(5))
    assert len(plain(content, "ERROR")) == 1


def test_distant_matches_stay_in_separate_blocks():
    content = ("2026-08-24 10:00:00 ERROR hit\n"
               + "".join(f"2026-08-24 10:00:0{i} INFO pad\n" for i in range(1, 5))
               + "2026-08-24 10:00:09 ERROR hit\n")
    assert len(plain(content, "hit")) == 2


@pytest.mark.parametrize("kwargs", [
    {"context_before": 999},
    {"context_after": 999},
    {"context_before": 999, "context_after": 999},
])
def test_context_larger_than_the_file_clips_instead_of_wrapping(kwargs):
    content = "".join(f"2026-08-24 10:00:0{i} ERROR e{i}\n" for i in range(5))
    text = rendered_text(plain(content, "e2", **kwargs))

    assert "e2" in text
    assert "e9" not in text


# --- search modifiers ------------------------------------------------------

def test_regex_mode_matches_anywhere_in_the_line():
    content = ("2026-08-24 10:00:01 INFO code 200 ok\n"
               "2026-08-24 10:00:02 WARNING code 404 missing\n")
    blocks = find_matches(content, re.compile(r"code (4|5)\d\d", re.IGNORECASE), None,
                          use_regex=True)

    assert "404" in rendered_text(blocks)
    assert "200" not in rendered_text(blocks)


def test_limit_to_line_start_anchors_after_the_level_prefix():
    content = ("2024-01-01 ERROR database connection lost\n"
               "2024-01-01 ERROR something failed in database\n")
    text = rendered_text(find_matches(content, None, "database", limit_to_line_start=True))

    assert "database connection lost" in text
    assert "something failed in database" not in text


# --- odd input -------------------------------------------------------------

@pytest.mark.parametrize("content", ["", "\n", "\n\n\n"])
def test_empty_content_yields_no_matches(content):
    assert plain(content, "anything") == []


def test_no_match_yields_no_blocks():
    assert plain(TRACEBACK_LOG, "nonexistent-term") == []


def test_file_without_a_trailing_newline_is_still_searchable():
    assert "ERROR boom" in rendered_text(plain("2026-08-24 10:00:01 ERROR boom", "boom"))


def test_crlf_line_endings_do_not_break_grouping():
    """read_file_safe reads in binary, so \\r can survive into the content it hands over."""
    content = "2026-08-24 10:00:01 ERROR boom\r\n  frame one\r\n"
    text = rendered_text(plain(content, "boom"))

    assert "ERROR boom" in text
    assert "frame one" in text


def test_unicode_and_ansi_content_passes_through_untouched():
    """The viewer converts ANSI to HTML downstream, so escapes must survive the search."""
    content = "2026-08-24 10:00:01 ERROR \x1b[31mошибка\x1b[0m\n"
    text = rendered_text(plain(content, "ошибка"))

    assert "ошибка" in text
    assert "\x1b[31m" in text


def test_very_long_single_line_is_returned_whole():
    content = "2026-08-24 10:00:01 ERROR " + ("x" * 50_000) + " needle\n"
    assert "needle" in rendered_text(plain(content, "needle"))
