"""글자 수 계산 유틸.

사양 S2: 에디터 우측에 공백 포함/제외 글자 수 표시.
word_count_cache에는 **공백 제외** 글자 수를 저장한다.
"""
import re

_WS_RE = re.compile(r"\s+")


def count_chars_excluding_whitespace(text) -> int:
    """공백(유니코드 whitespace 전체)을 제외한 글자 수."""
    if not text:
        return 0
    return len(_WS_RE.sub("", text))


def count_chars_including_whitespace(text) -> int:
    """공백 포함 글자 수 (표시용)."""
    return len(text or "")
