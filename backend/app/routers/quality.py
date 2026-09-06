"""canon 충돌 검사 + 회차 품질 진단 라우터 — 고도화 G-023·G-031."""
import openai
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter
from app.schemas import (CanonCheckRequest, CanonCheckResponse,
                         ChapterQualityOut)
from app.services import canon as canon_service
from app.services import llm, quality as quality_service
from app.services.bootstrap import NoEndpointError, resolve_endpoint

router = APIRouter()


def _get_chapter_or_404(cid: int, db: Session) -> Chapter:
    chapter = db.get(Chapter, cid)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


@router.post("/canon-check", response_model=CanonCheckResponse)
async def canon_check(payload: CanonCheckRequest, db: Session = Depends(get_db)):
    """회차 본문이 캐릭터·세계관·복선 설정과 모순되는지 LLM으로 검사한다(G-023).

    원고를 자동 수정하지 않는다 — 모순 후보 목록을 작가 판단에 제공할 뿐.
    """
    chapter = _get_chapter_or_404(payload.chapter_id, db)
    try:
        endpoint, model = resolve_endpoint(db)
    except NoEndpointError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)
    try:
        issues, counts, used_model = await canon_service.run_canon_check(
            db, chapter, client, model,
            temperature=endpoint.temperature,
            reasoning_effort=endpoint.reasoning_effort)
    except openai.APIError as exc:
        raise HTTPException(status_code=502,
                            detail=canon_service.friendly_api_error(exc)) from exc
    except (ValueError, Exception) as exc:  # noqa: BLE001 — JSON 재시도 실패 포함
        raise HTTPException(status_code=502,
                            detail=f"canon 검사 실패: {type(exc).__name__}") from exc

    return CanonCheckResponse(
        chapter_id=chapter.id, model=used_model, issues=issues,
        checked_context=counts)


@router.get("/chapters/{cid}/quality", response_model=ChapterQualityOut)
def chapter_quality(cid: int, db: Session = Depends(get_db)):
    """규칙 기반 회차 품질 진단 — LLM 호출 없이 로컬 계산(G-030·G-031)."""
    chapter = _get_chapter_or_404(cid, db)
    result = quality_service.analyze_chapter(chapter.content_md or "")
    return ChapterQualityOut(chapter_id=chapter.id, **result)
