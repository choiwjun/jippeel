"""AI 사용량 기록 — 고도화 G-060.

문자량 기반 집계(토큰 수는 엔드포인트별 편차가 커서 집계 신뢰가 낮다).
자체 세션을 열어 호출부의 DB 세션과 독립적으로 기록한다.
"""
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import AiUsage


def record(kind: str, model: str | None, endpoint_name: str | None,
           prompt_chars: int, completion_chars: int) -> None:
    """사용량 1건 기록. 기록 실패가 본 기능을 막지 않는다(best-effort)."""
    try:
        session = SessionLocal()
        try:
            session.add(AiUsage(
                kind=kind, model=model, endpoint_name=endpoint_name,
                prompt_chars=max(prompt_chars, 0),
                completion_chars=max(completion_chars, 0),
            ))
            session.commit()
        finally:
            session.close()
    except Exception:  # noqa: BLE001 — 사용량 기록은 본 기능을 절대 막지 않는다
        pass


def summary(limit_days: int = 30) -> list[dict]:
    """kind+model 그룹 집계 — 최근 limit_days일."""
    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=limit_days)
    session = SessionLocal()
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
        session.close()
