"""
Unit tests for src.utils.utils.Utils - pure string/text helpers with no I/O.
Expected values below were verified by running the actual implementation directly,
since pytest itself wasn't installed in the sandbox this suite was first written in.
"""

import pytest

from src.utils.utils import Utils

pytestmark = pytest.mark.unit


def test_split_basic():
    assert Utils.split("a,b,c") == ["a", "b", "c"]


def test_split_empty_string():
    assert Utils.split("") == []


def test_split_no_delimiter():
    assert Utils.split("single") == ["single"]


def test_split_respects_escaped_delimiter():
    assert Utils.split("a\\,b,c") == ["a,b", "c"]


def test_string_distance_classic_example():
    assert Utils.string_distance("kitten", "sitting") == 3


def test_string_distance_identical_strings():
    assert Utils.string_distance("abc", "abc") == 0


def test_longest_common_substring():
    assert Utils.longest_common_substring("abcdef", "zabcx") == "abc"


def test_sort_dictionary_orders_by_key():
    assert Utils.sort_dictionary({"b": 2, "a": 1, "c": 3}) == {"a": 1, "b": 2, "c": 3}


def test_contains_emoji():
    assert Utils.contains_emoji("hello \U0001F600") is True
    assert Utils.contains_emoji("hello") is False


def test_clean_emoji_replaces_with_marker():
    assert Utils.clean_emoji("hi \U0001F600 there") == "hi [emoji] there"
