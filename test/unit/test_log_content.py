"""
Unit tests for src.internal.log_content - the policy deciding how large log content
reaches a viewer. Pure functions, so the thresholds are exercised directly rather than
through the log viewer.
"""

import pytest

from src.internal.log_content import (
    CHUNK_LINES,
    LARGE_CONTENT_BYTES,
    MAX_LONG_LINE_CHARS,
    MULTILINE_THRESHOLD,
    RENDER_CHUNKED,
    RENDER_LONG_LINE,
    RENDER_SINGLE,
    choose_render_strategy,
    count_lines,
    iter_chunks,
    truncate_long_line,
)

pytestmark = pytest.mark.unit


# --- strategy selection ----------------------------------------------------

def test_small_content_is_appended_in_one_go():
    assert choose_render_strategy("hello\nworld\n") == RENDER_SINGLE


def test_empty_content_is_appended_in_one_go():
    assert choose_render_strategy("") == RENDER_SINGLE


def test_content_exactly_at_the_size_threshold_is_not_large():
    """The threshold is exclusive: only content past it gets special handling."""
    assert choose_render_strategy("a" * LARGE_CONTENT_BYTES) == RENDER_SINGLE


def test_large_multiline_content_is_chunked():
    content = "a" * LARGE_CONTENT_BYTES + "\n" * (MULTILINE_THRESHOLD + 1)
    assert choose_render_strategy(content) == RENDER_CHUNKED


def test_large_content_without_line_structure_is_treated_as_one_long_line():
    assert choose_render_strategy("a" * (LARGE_CONTENT_BYTES + 1)) == RENDER_LONG_LINE


def test_large_content_at_the_line_threshold_is_still_a_long_line():
    """MULTILINE_THRESHOLD lines is not yet 'multi-line enough' to stream."""
    content = "a" * LARGE_CONTENT_BYTES + "\n" * (MULTILINE_THRESHOLD - 1)
    assert choose_render_strategy(content) == RENDER_LONG_LINE


# --- chunking --------------------------------------------------------------

@pytest.mark.parametrize("content", [
    pytest.param("", id="empty"),
    pytest.param("solo", id="single-line"),
    pytest.param("a\nb\n", id="trailing-newline"),
    pytest.param("\n".join(f"line {i}" for i in range(1234)), id="spans-several-chunks"),
    pytest.param("\n".join(str(i) for i in range(CHUNK_LINES)), id="exact-chunk-multiple"),
])
def test_chunks_rejoin_into_the_original_content(content):
    """Chunking is a view onto the content, so it must lose nothing and reorder nothing."""
    assert "\n".join(iter_chunks(content)) == content


def test_chunks_do_not_exceed_the_chunk_size():
    content = "\n".join(f"line {i}" for i in range(1234))
    assert all(count_lines(chunk) <= CHUNK_LINES for chunk in iter_chunks(content))


def test_chunk_count_covers_every_line():
    content = "\n".join(f"line {i}" for i in range(1234))
    assert len(list(iter_chunks(content))) == 3


def test_empty_content_still_yields_one_chunk():
    """split('\\n') never returns an empty list, so the caller always gets something."""
    assert list(iter_chunks("")) == [""]


# --- long-line truncation --------------------------------------------------

def test_long_line_is_cut_and_reports_its_original_length():
    text, original_length = truncate_long_line("a" * 20_000)

    assert len(text) == MAX_LONG_LINE_CHARS
    assert original_length == 20_000


def test_content_within_the_limit_is_returned_untouched():
    text, original_length = truncate_long_line("short")

    assert text == "short"
    assert original_length is None, "no cut happened, so there's no original length to report"


def test_content_exactly_at_the_limit_is_not_cut():
    text, original_length = truncate_long_line("a" * MAX_LONG_LINE_CHARS)

    assert text == "a" * MAX_LONG_LINE_CHARS
    assert original_length is None


def test_custom_limit_is_honoured():
    assert truncate_long_line("abcdef", max_chars=3) == ("abc", 6)


# --- line counting ---------------------------------------------------------

@pytest.mark.parametrize("content, expected", [
    ("", 1),
    ("one line", 1),
    ("a\nb\nc", 3),
    ("a\nb\n", 3),
])
def test_count_lines(content, expected):
    assert count_lines(content) == expected
