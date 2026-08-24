"""
Policy for handing large log content to a viewer.

Reading a log and deciding how much of it to show are separate problems from drawing
it. This module owns the second: how big is "too big", when to stream content in
chunks instead of one go, and where to cut a single enormous line. The thresholds live
here as named constants rather than as literals buried in a widget method.

Pure: content in, decisions and slices out. No Qt.
"""

# Above this, content is streamed or truncated rather than appended in one call.
LARGE_CONTENT_BYTES = 1_000_000

# A large file with at least this many lines is streamed; below it, the content is
# treated as one enormous line (minified JSON and the like) and cut instead.
MULTILINE_THRESHOLD = 100

# Lines per streamed chunk.
CHUNK_LINES = 500

# How much of a single enormous line is worth showing.
MAX_LONG_LINE_CHARS = 10_000

# Strategies returned by choose_render_strategy.
RENDER_SINGLE = "single"
RENDER_CHUNKED = "chunked"
RENDER_LONG_LINE = "long_line"


def count_lines(content):
    """Line count for content that may or may not end in a newline."""
    return content.count('\n') + 1


def choose_render_strategy(content):
    """
    Pick how content should reach the viewer.

    RENDER_SINGLE for anything of reasonable size, RENDER_CHUNKED for a large file with
    real line structure, and RENDER_LONG_LINE for a large file that is essentially one
    unbroken line, where streaming by lines would not help.
    """
    if len(content) <= LARGE_CONTENT_BYTES:
        return RENDER_SINGLE
    if count_lines(content) > MULTILINE_THRESHOLD:
        return RENDER_CHUNKED
    return RENDER_LONG_LINE


def iter_chunks(content, chunk_lines=CHUNK_LINES):
    """Yield content back as line-aligned chunks, in order, losing nothing."""
    lines = content.split('\n')
    for i in range(0, len(lines), chunk_lines):
        yield '\n'.join(lines[i:i + chunk_lines])


def truncate_long_line(content, max_chars=MAX_LONG_LINE_CHARS):
    """
    Return (text, original_length): text cut to max_chars, and the original length when
    a cut actually happened, or None when the content already fit.
    """
    if len(content) > max_chars:
        return content[:max_chars], len(content)
    return content, None
