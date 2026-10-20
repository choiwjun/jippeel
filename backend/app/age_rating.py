"""작품 연령 등급 계약 — 전체연령/19금.

등급은 작품 단위 메타다. 부트스트랩 생성과 이후의 모든 회차 생성·감수가
같은 문구를 보도록 프롬프트 블록을 이 모듈 한 곳에서만 만든다.
등급을 올려도 완화되지 않는 금지선(미성년자 성적 묘사 등)은 adult 블록에
함께 싣는다 — 등급 상향이 금지선 해제로 읽히지 않게 하는 것이 계약이다.
"""
from typing import Final, Literal

AgeRating = Literal["all", "adult"]

AGE_RATINGS: Final[tuple[str, ...]] = ("all", "adult")
DEFAULT_AGE_RATING: Final[str] = "all"
AGE_RATING_LABELS: Final[dict[str, str]] = {
    "all": "전체연령",
    "adult": "19금(성인)",
}


def normalize_age_rating(value) -> str:
    """알 수 없는 값·None은 전체연령으로 떨어뜨린다(등급은 올라가지 않는다)."""
    if isinstance(value, str) and value.strip() in AGE_RATINGS:
        return value.strip()
    return DEFAULT_AGE_RATING


def age_rating_prompt_block(value) -> str:
    """등급을 수위 규칙으로 변환한다. 생성·감수가 같은 블록을 공유한다."""
    rating = normalize_age_rating(value)
    if rating == "adult":
        return (
            "[작품 연령 등급 — 19금(성인) 지정]\n"
            "성인 독자를 전제로 한다. 폭력·범죄·배신·성적 긴장 같은 수위 높은 소재를 "
            "피하지 말고 갈등·선택·대가로 작동시켜라. 자극을 목적 자체로 삼지 말고 "
            "인물의 선택과 그 결과가 남게 하라.\n"
            "등급과 무관하게 금지한다: 미성년자를 성적 대상으로 묘사하는 것, 실존 인물에 "
            "대한 성적·명예훼손 묘사, 범죄·자해의 실행을 돕는 구체적 수법 안내. "
            "연재 플랫폼의 성인 카테고리 규정과 작가의 명시 지시를 우선한다."
        )
    return (
        "[작품 연령 등급 — 전체연령]\n"
        "청소년이 읽을 수 있는 수위를 유지한다. 폭력·성적 묘사는 직접 서술을 피하고 "
        "정서와 긴장으로 처리하며, 욕설·약물·자해는 암시 수준으로 제한한다."
    )
