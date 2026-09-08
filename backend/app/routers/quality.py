"""canon 충돌 검사 + 회차 품질 진단 라우터 — 고도화 G-023·G-031·이력(G-041)."""
import hashlib

import openai
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CanonRun, Chapter, QualityCheck
from app.schemas import (CanonCheckRequest, CanonCheckResponse, CanonRunOut,
                         ChapterQualityOut, EpisodePurpose, QualityCheckOut)
from app.services import ai_context
from app.services import canon as canon_service
from app.services import llm, quality as quality_service
from app.services import usage as usage_service
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
    결과는 canon_runs에 이력으로 저장되며 GET /canon-check/runs로 재조회한다.
    """
    chapter = _get_chapter_or_404(payload.chapter_id, db)
    bundle = ai_context.build_context_bundle(db, ai_context.request_from_canon(payload, chapter))
    messages_context = canon_service.build_messages(db, chapter, payload=payload, bundle=bundle)
    try:
        endpoint, model = resolve_endpoint(db)
    except NoEndpointError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)
    prompt_chars = 0
    try:
        issues, counts, used_model = await canon_service.run_canon_check(
            db, chapter, client, model,
            temperature=endpoint.temperature,
            reasoning_effort=endpoint.reasoning_effort,
            payload=payload,
            bundle=bundle,
            messages_context=messages_context)
        prompt_chars = canon_service.last_prompt_chars
    except openai.APIError as exc:
        raise HTTPException(status_code=502,
                            detail=canon_service.friendly_api_error(exc)) from exc
    except ValueError as exc:  # JSON 재시도 후 파싱 실패
        raise HTTPException(status_code=502,
                            detail=f"canon 검사 실패: {type(exc).__name__}") from exc

    run = CanonRun(chapter_id=chapter.id, model=used_model,
                   issues_json=issues, context_json=counts)
    db.add(run)
    db.commit()
    db.refresh(run)
    usage_service.record(kind="canon", model=used_model, endpoint_name=endpoint.name,
                         prompt_chars=prompt_chars,
                         completion_chars=sum(len(i["quote"]) + len(i["reason"]) for i in issues))

    return CanonCheckResponse(
        run_id=run.id, chapter_id=chapter.id, model=used_model, issues=issues,
        checked_context=counts)


@router.get("/canon-check/runs", response_model=list[CanonRunOut])
def canon_runs(chapter_id: int = Query(...), db: Session = Depends(get_db)):
    """canon 검사 이력 재조회(G-041) — 최신순."""
    rows = db.scalars(
        select(CanonRun).where(CanonRun.chapter_id == chapter_id)
        .order_by(CanonRun.created_at.desc(), CanonRun.id.desc()).limit(50)
    ).all()
    return list(rows)


@router.get("/chapters/{cid}/quality", response_model=ChapterQualityOut)
def chapter_quality(
    cid: int,
    record: bool = True,
    episode_purpose: EpisodePurpose = "serial",
    db: Session = Depends(get_db),
):
    """규칙 기반 회차 품질 진단 — LLM 호출 없이 로컬 계산(G-030·G-031).

    record=true(기본)이면 quality_checks에 이력을 기록하되, 본문 해시가
    직전 기록과 같으면 스킵한다(점수 추이는 본문이 바뀔 때만 갱신).
    """
    chapter = _get_chapter_or_404(cid, db)
    text = chapter.content_md or ""
    result = quality_service.analyze_chapter(text, episode_purpose=episode_purpose)

    recorded = False
    if record:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        same_hash_rows = db.scalars(
            select(QualityCheck).where(
                QualityCheck.chapter_id == cid,
                QualityCheck.content_hash == content_hash,
            )
        ).all()
        has_same_purpose = any(
            ((row.metrics_json or {}).get("episode_purpose") or "serial") == episode_purpose
            for row in same_hash_rows
        )
        if not has_same_purpose:
            db.add(QualityCheck(
                chapter_id=cid, score=result["score"], content_hash=content_hash,
                metrics_json=result["metrics"], suggestions_json=result["suggestions"],
                presets_json=result["suggested_preset_names"]))
            db.commit()
            recorded = True
    return ChapterQualityOut(chapter_id=chapter.id, recorded=recorded, **result)


@router.get("/chapters/{cid}/quality/history", response_model=list[QualityCheckOut])
def chapter_quality_history(cid: int, db: Session = Depends(get_db)):
    """품질 점수 추이 — 최신순 최대 100건."""
    _get_chapter_or_404(cid, db)
    rows = db.scalars(
        select(QualityCheck).where(QualityCheck.chapter_id == cid)
        .order_by(QualityCheck.created_at.desc(), QualityCheck.id.desc()).limit(100)
    ).all()
    return list(rows)
