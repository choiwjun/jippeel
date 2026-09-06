"""로어북 자동 주입 서비스 — 백로그 P1 (부록06: goink·NarraLume 개념 차용, 코드 비복사).

본문/프롬프트 텍스트에 실제로 등장한 로어 항목만 골라 프롬프트 컨텍스트에 넣는다.
  - 매칭은 title·keywords의 부분 일치. 로어 항목은 고유명사(용어·장소·세력)가
    대부분이라 한국어 형태소 분석 없이도 정확 부분 매칭으로 충분히 동작한다
  - 점수 = (제목 출현 횟수 × 3) + (키워드 출현 횟수 × 2), 상위 limit개 선정
  - 길이 1짜리 용어는 과잉 매치 위험이 있어 제외

임베딩 기반 시맨틱 검색(sqlite-vec + ONNX 등)은 후속 업그레이드 경로(부록06 §4).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LoreEntry

_TITLE_WEIGHT = 3
_KEYWORD_WEIGHT = 2
_MIN_TERM_LEN = 2


def _occurrences(text: str, term: str) -> int:
    """대소문자 무시 비겹침 출현 횟수."""
    return text.casefold().count(term.casefold())


def score_entries(entries: list[LoreEntry], text: str) -> list[tuple[LoreEntry, int]]:
    """텍스트와 관련된 항목만 점수와 함께 반환(점수 내림차순, 동점은 id 오름차순)."""
    scored: list[tuple[LoreEntry, int]] = []
    for entry in entries:
        score = 0
        title = (entry.title or "").strip()
        if len(title) >= _MIN_TERM_LEN:
            score += _TITLE_WEIGHT * _occurrences(text, title)
        for kw in entry.keywords or []:
            if not isinstance(kw, str):
                continue
            kw = kw.strip()
            if len(kw) >= _MIN_TERM_LEN:
                score += _KEYWORD_WEIGHT * _occurrences(text, kw)
        if score > 0:
            scored.append((entry, score))
    scored.sort(key=lambda pair: (-pair[1], pair[0].id))
    return scored


def select_lore_for_text(db: Session, project_id: int, text: str,
                         limit: int = 6) -> list[LoreEntry]:
    """프로젝트 로어북에서 텍스트에 언급된 항목 상위 limit개를 선정한다."""
    text = text or ""
    if not text.strip():
        return []
    entries = db.scalars(
        select(LoreEntry).where(LoreEntry.project_id == project_id)
    ).all()
    scored = score_entries(entries, text)
    return [entry for entry, _score in scored[:max(limit, 0)]]
