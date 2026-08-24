"""
Unit tests for ThemeManager's markup helpers: convert_ansi_to_html, which renders
ANSI-colored log output in the log viewer and in search results, and styled_span,
which builds the spans the viewer's own messages are wrapped in. Pure string
processing, no live QApplication needed.
"""

import pytest

from src.utils.theme_manager import ThemeManager

pytestmark = pytest.mark.unit


def test_plain_text_without_ansi_codes_is_returned_unchanged():
    text = "line one\nline two"
    assert ThemeManager.convert_ansi_to_html(text) == text


def test_foreground_color_code_wraps_text_in_colored_span():
    result = ThemeManager.convert_ansi_to_html("\x1b[31mred text\x1b[0m")
    assert result == '<span style="color: #cd3131">red text</span>'


def test_bold_code_wraps_text_in_bold_span():
    result = ThemeManager.convert_ansi_to_html("\x1b[1mbold text\x1b[0m")
    assert result == '<span style="font-weight: bold">bold text</span>'


def test_background_color_code_wraps_text_in_background_span():
    result = ThemeManager.convert_ansi_to_html("\x1b[41mbg text\x1b[0m")
    assert result == '<span style="background-color: #cd3131">bg text</span>'


def test_multiline_text_joins_lines_with_br():
    result = ThemeManager.convert_ansi_to_html("plain line\n\x1b[31mred line\x1b[0m")
    assert result == 'plain line<br><span style="color: #cd3131">red line</span>'


def test_text_after_reset_code_has_no_styling():
    result = ThemeManager.convert_ansi_to_html("\x1b[31mred\x1b[0m plain")
    assert result == '<span style="color: #cd3131">red</span> plain'


def test_styled_span_without_styles_returns_text_unwrapped():
    """No styles means no markup - the viewer shouldn't get an empty span."""
    assert ThemeManager.styled_span("hello") == "hello"


@pytest.mark.parametrize("kwargs, expected", [
    pytest.param({"color": "#ff0000"},
                 '<span style="color: #ff0000">hi</span>', id="color"),
    pytest.param({"background_color": "#000000"},
                 '<span style="background-color: #000000">hi</span>', id="background"),
    pytest.param({"bold": True},
                 '<span style="font-weight: bold">hi</span>', id="bold"),
])
def test_styled_span_applies_each_style(kwargs, expected):
    assert ThemeManager.styled_span("hi", **kwargs) == expected


def test_styled_span_combines_styles_in_a_stable_order():
    """Order is fixed so rendered output stays comparable between runs."""
    assert ThemeManager.styled_span("hi", color="#fff", bold=True, background_color="#000") == \
        '<span style="color: #fff; background-color: #000; font-weight: bold">hi</span>'


@pytest.mark.parametrize("falsy", ["", None])
def test_styled_span_treats_a_falsy_color_as_no_style(falsy):
    assert ThemeManager.styled_span("hi", color=falsy) == "hi"


def test_styled_span_wraps_empty_text():
    assert ThemeManager.styled_span("", color="#fff") == '<span style="color: #fff"></span>'
