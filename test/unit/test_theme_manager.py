"""
Unit tests for ThemeManager.convert_ansi_to_html - renders ANSI-colored log output
in the log viewer and in search results. Pure string processing, no live
QApplication needed.
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
