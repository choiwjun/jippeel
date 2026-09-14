"""AI 사용량 기록 — 고도화 G-060.

문자량 기반 집계(토큰 수는 엔드포인트별 편차가 커서 집계 신뢰가 낮다).
자체 세션을 열어 호출부의 DB 세션과 독립적으로 기록한다.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AiUsage


def record(kind: str, model: str | None, endpoint_name: str | None,
           prompt_chars: int, completion_chars: int,
           db: "Session | None" = None) -> int | None:
    """사용량 1건 기록. 기록 실패가 본 기능을 막지 않는다(best-effort).

    신규 행 id를 반환한다 — E1 generation_runs가 ai_usage_id로 연결한다.
    실패 시 None. db 전달 시 그 세션을 사용(호출 세션과 같은 DB에 쓰기 위함),
    생략 시 자체 SessionLocal을 연다.
    """
    try:
        session = db if db is not None else SessionLocal()
        try:
            usage = AiUsage(
                kind=kind, model=model, endpoint_name=endpoint_name,
                prompt_chars=max(prompt_chars, 0),
                completion_chars=max(completion_chars, 0),
            )
            session.add(usage)
            session.commit()
            return usage.id
        finally:
            if db is None:
                session.close()
    except Exception:  # noqa: BLE001 — 사용량 기록은 본 기능을 절대 막지 않는다
        return None


def summary(limit_days: int = 30, db: "Session | None" = None) -> list[dict]:
    """kind+model 그룹 집계 — 최근 limit_days일. db 전달 시 그 세션 사용."""
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=limit_days)
    session = db if db is not None else SessionLocal()
    try:
        rows = session.execute(
            select(
                AiUsage.kind,
                AiUsage.model,
                func.count(AiUsage.id),
                func.sum(AiUsage.prompt_chars),
                func.sum(AiUsage.completion_chars),
                func.max(AiUsage.created_at),
            ).where(AiUsage.created_at >= since)
            .group_by(AiUsage.kind, AiUsage.model)
            .order_by(func.max(AiUsage.created_at).desc())
        ).all()
        return [
            {"kind": kind, "model": model, "calls": calls,
             "prompt_chars": int(p or 0), "completion_chars": int(c or 0),
             "last_at": last}
            for kind, model, calls, p, c, last in rows
        ]
    finally:
        if db is None:
            session.close()
