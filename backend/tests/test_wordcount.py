"""글자 수 계산(공백 제외) 단위 테스트."""
import pytest

from app.services.wordcount import (
    count_chars_excluding_whitespace,
    count_chars_including_whitespace,
)


def test_empty_string():
    assert count_chars_excluding_whitespace("") == 0


def test_none_returns_zero():
    assert count_chars_excluding_whitespace(None) == 0


def test_korean_no_spaces():
    assert count_chars_excluding_whitespace("가나다라") == 4


def test_korean_with_spaces_and_newlines():
    # 첫문장입니다.(7) + 둘째문장.(5) = 12
    assert count_chars_excluding_whitespace("첫 문장입니다.\n\n둘째 문장.") == 12


def test_mixed_korean_english_punct():
    text = "그는 말했다: \"Hello, world!\" 그리고 웃었다."
    expected = len([c for c in text if not c.isspace()])
    assert count_chars_excluding_whitespace(text) == expected


def test_only_whitespace_is_zero():
    assert count_chars_excluding_whitespace(" \t\n\u3000") == 0


def test_fullwidth_space_is_whitespace():
    assert count_chars_excluding_whitespace("아\u3000아") == 2


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a", 1),
        ("a b", 2),
        ("  ", 0),
        ("한글 English 혼용 123", 14),
    ],
)
def test_parametrized(text, expected):
    assert count_chars_excluding_whitespace(text) == expected
    assert count_chars_including_whitespace("a b\nc") == 5
