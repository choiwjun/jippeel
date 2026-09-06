"""윤문 라우터 (사양 §5 M5, Sprint 3).

im-not-ai 파이프라인 래퍼(app/services/humanize.py)로 회차 본문을 윤문하고,
변경률 게이트(FR-505: 30% 경고 / 50% 차단)를 백엔드에서 강제한다.
수락 시에만 회차 본문을 교체하며, 자동 덮어쓰기는 없다(FR-504).
"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, RefineRun
from app.schemas import (
    RefineRequest,
    RefineResult,
    RefineRunOut,
    SimpleOk,
    SpanOut,
)
from app.services import humanize
from app.services.wordcount import count_novelpia_chars

router = APIRouter()


def _get_chapter_or_404(cid: int, db: Session) -> Chapter:
    chapter = db.get(Chapter, cid)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


def _get_run_or_404(run_id: int, db: Session) -> RefineRun:
    run = db.get(RefineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="refine run not found")
    return run


@router.post("/refine", response_model=RefineResult)
def refine_chapter(payload: RefineRequest, db: Session = Depends(get_db)):
    """FR-501~505 — 회차 본문 윤문 실행 → 진단 span + 최종본 + 게이트 판정."""
    chapter = _get_chapter_or_404(payload.chapter_id, db)
    if not chapter.content_md.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="본문이 비어 있어 윤문할 수 없습니다.")

    try:
        result = humanize.run_pipeline(chapter.content_md, payload.force_route)
    except humanize.HumanizeNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=str(exc)) from exc
    except humanize.HumanizeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"윤문 파이프라인 실패: {exc}") from exc

    run = RefineRun(
        chapter_id=chapter.id,
        route_hint=result["route_hint"],
        changed_ratio=result["changed_ratio"],
        report_json={
            "gate": result["gate"],
            "status": result["status"],
            "spans": result["spans"],
            "metrics": result["report"]["metrics"],
            "gates_raw": result["report"]["gates"],
            "original_text": chapter.content_md,  # 수락 시점 원문 보존(감사용)
        },
        result_text=None if result["status"] == "blocked" else result["refined"],
        accepted=False,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    humanize.cleanup_workdir(result["work_dir"])

    return RefineResult(
        run_id=run.id,
        route_hint=result["route_hint"],
        spans=[SpanOut(**s) for s in result["spans"]],
        original=chapter.content_md,
        refined=result["refined"] if result["status"] != "blocked" else "",
        changed_ratio=result["changed_ratio"],
        gate=result["gate"],          # pass | warn | block
        status=result["status"],      # FR-505 — block 시 status=blocked
    )


@router.get("/refine/runs/{run_id}", response_model=RefineRunOut)
def get_refine_run(run_id: int, db: Session = Depends(get_db)):
    """리포트 재조회."""
    return _get_run_or_404(run_id, db)


@router.post("/refine/runs/{run_id}/accept", response_model=SimpleOk)
def accept_refine_run(run_id: int, db: Session = Depends(get_db)):
    """FR-504 — 수락 → 대상 회차 본문 교체(자동저장 흐름과 동일하게 word_count_cache 갱신)."""
    run = _get_run_or_404(run_id, db)
    if run.accepted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="이미 처리된 실행입니다.")
    if (run.report_json or {}).get("rejected"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="거절된 실행은 수락할 수 없습니다. 다시 윤문을 실행하세요.")
    if not run.result_text:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="차단되었거나 결과가 없는 실행은 수락할 수 없습니다.")

    chapter = _get_chapter_or_404(run.chapter_id, db)
    # 자동저장 흐름 유지 — PUT content와 동일한 필드 갱신
    chapter.content_md = run.result_text
    chapter.word_count_cache = count_novelpia_chars(run.result_text)
    run.accepted = True
    db.commit()
    return SimpleOk()


@router.post("/refine/runs/{run_id}/reject", response_model=SimpleOk)
def reject_refine_run(run_id: int, db: Session = Depends(get_db)):
    """FR-504 — 거절 → 기록만 남김(본문 무변경)."""
    run = _get_run_or_404(run_id, db)
    if run.accepted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="이미 수락된 실행은 거절할 수 없습니다.")
    report = dict(run.report_json or {})
    report["rejected"] = True
    run.report_json = json.loads(json.dumps(report, ensure_ascii=False))  # JSON 변경 감지 보장
    db.commit()
    return SimpleOk()
