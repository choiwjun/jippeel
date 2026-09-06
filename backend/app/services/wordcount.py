"""글자 수 계산 유틸.

사양 S2: 에디터에 공백 포함/제외 글자 수 표시.
word_count_cache에는 **노벨피아 모드**(공백·문장부호·특수문자 제외, 문자·숫자만)
글자 수를 저장한다 — 프론트 wordCount.ts의 countNovelpia와 동일 기준(부록06)이며,
PLUS 전환 판정(G4 Q3)도 이 값으로 계산해 화면 표시와 서버 판정이 어긋나지 않게 한다.
노벨피아의 정확한 제외 문자집합은 비공개이므로 최종 확정은 실측 검증이 필요하다.
"""
import re
import unicodedata

_WS_RE = re.compile(r"\s+")


def count_chars_excluding_whitespace(text) -> int:
    """공백(유니코드 whitespace 전체)을 제외한 글자 수 (표시용)."""
    if not text:
        return 0
    return len(_WS_RE.sub("", text))


def count_chars_including_whitespace(text) -> int:
    """공백 포함 글자 수 (표시용)."""
    return len(text or "")


def count_novelpia_chars(text) -> int:
    """노벨피아 모드 글자 수 — 문자(Unicode category L*)·숫자(N*)만 계수.

    프론트 countNovelpia(/[^\p{L}\p{N}]/gu 제외)와 동일한 집계다.
    """
    if not text:
        return 0
    return sum(1 for ch in text if unicodedata.category(ch)[0] in ("L", "N"))
