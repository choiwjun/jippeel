"""E5 — 결정론 신호 → proposed 규칙 초안 생성 job.

E3 분석 결과만 사용한다(LLM 없음). 절대 자동 승인하지 않는다 —
status는 항상 "proposed"이고 적용 여부는 작가 승인 게이트가 결정한다.

멱등성: 동일 (project_id, category, rule_text) 규칙이 어떤 상태로든 이미
존재하면 건너뛴다. rejected·retired 규칙까지 재제안하지 않는 것이
작가 결정 존중 원칙이다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ImprovementRule
from app.services.generation_analysis import analyze_project_generations

# 임계값 — 신호가 약하면 제안하지 않는다(작가 주의력은 유한한 자원).
_DELETED_MIN_COUNT = 3        # 같은 표현이 3회 이상 삭제됐을 때
_DELETED_MIN_OUTPUTS = 2      # 서로 다른 산출물 2개 이상에서
_LOW_ACCEPT_MIN_DECIDED = 4   # 처분 결정 4건 이상일 때만 수용률 신뢰
_LOW_ACCEPT_RATE = 0.4        # 수용률 40% 미만
_SHRUNK_MIN_SAMPLES = 3       # landed가 기록된 draft 3건 이상
_SHRUNK_RATIO = 0.7           # landed/output 평균 0.7 미만 → 초안이 김
_MAX_DELETED_PROPOSALS = 5    # 한 실행의 삭제-표현 제안 상한(빈도순)


def _propose_candidate(
    db: Session, project_id: int, *, category: str, rule_text: str,
    rationale: str, evidence: list[dict], existing: set[tuple[str, str]],
    created: list[ImprovementRule],
) -> None:
    key = (category, rule_text)
    if key in existing:
        return
    now = datetime.now(timezone.utc)
    rule = ImprovementRule(
        project_id=project_id,
        category=category,
        rule_text=rule_text,
        status="proposed",
        source="system_proposal",
        evidence_json=evidence,
        rationale=rationale,
        status_events_json=[{"from": None, "to": "proposed",
                             "at": now.isoformat()}],
    )
    db.add(rule)
    created.append(rule)
    existing.add(key)


def propose_rules_for_project(db: Session, project_id: int) -> dict:
    """프로젝트의 결정론 신호를 평가해 proposed 규칙 초안만 만든다.

    Returns:
        {"created": [ImprovementRule], "skipped_existing": int,
         "signals": int} — 신호 수·중복 건너뜀·생성 규칙.
    """
    analysis = analyze_project_generations(db, project_id)
    existing = {
        (r.category, r.rule_text)
        for r in db.scalars(
            select(ImprovementRule)
            .where(ImprovementRule.project_id == project_id)
        ).all()
    }
    created: list[ImprovementRule] = []
    signals = 0
    skipped_existing = 0

    def _maybe(category, rule_text, rationale, evidence):
        nonlocal signals, skipped_existing
        signals += 1
        before = len(created)
        _propose_candidate(
            db, project_id, category=category, rule_text=rule_text,
            rationale=rationale, evidence=evidence, existing=existing,
            created=created)
        if len(created) == before:
            skipped_existing += 1

    # 신호 1 — 반복 삭제 표현: 작가가 계속 지우는 표현은 생성 금지 규칙 후보
    for d in analysis["deleted_expressions"][:_MAX_DELETED_PROPOSALS]:
        if (d["count"] >= _DELETED_MIN_COUNT
                and len(d["output_ids"]) >= _DELETED_MIN_OUTPUTS):
            _maybe(
                "deleted_expression",
                f"다음 표현은 생성하지 마라: \"{d['text']}\"",
                f"이 표현이 초안→반영 비교에서 {d['count']}회 삭제됐다"
                f"(산출물 {len(d['output_ids'])}건).",
                [{"kind": "generation_output", "id": oid}
                 for oid in d["output_ids"]],
            )

    # 신호 2 — 낮은 surface 수용률: 절반 가까운 초안이 폐기되면 방향 재검토
    for s in analysis["surfaces"]:
        decided = sum(v for k, v in s["outcome_counts"].items()
                      if k != "pending")
        if (decided >= _LOW_ACCEPT_MIN_DECIDED
                and s["accept_rate"] is not None
                and s["accept_rate"] < _LOW_ACCEPT_RATE):
            _maybe(
                "recurring_error",
                f"'{s['surface']}' 경로 초안 수용률이 낮다"
                f"({int(s['accept_rate'] * 100)}%) — 집필 전 계획 검토와 "
                "작가 의도 확인을 강화하라.",
                f"처분 결정 {decided}건 중 수용 "
                f"{s['outcome_counts']['inserted'] + s['outcome_counts']['replaced']}건.",
                [{"kind": "note", "text": f"surface={s['surface']} "
                                          f"decided={decided}"}],
            )

    # 신호 3 — 초안 과장: 작가가 반영할 때 크게 줄이는 패턴
    drafts = [e for e in analysis["edit_distances"] if e["channel"] == "draft"]
    if len(drafts) >= _SHRUNK_MIN_SAMPLES:
        ratios = [
            e["landed_chars"] / e["output_chars"]
            for e in drafts if e["output_chars"] > 0
        ]
        if ratios and mean(ratios) < _SHRUNK_RATIO:
            _maybe(
                "length",
                "생성 초안이 작가 선호보다 길다 — 같은 사건을 더 적은 "
                "분량으로 쓰고 수식 묘사를 줄여라.",
                f"반영본/초안 분량 비율 평균 {mean(ratios):.2f}"
                f"({len(ratios)}건 표본).",
                [{"kind": "generation_output", "id": e["output_id"]}
                 for e in drafts[:10]],
            )

    db.commit()
    for rule in created:
        db.refresh(rule)
    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "signals": signals,
    }
