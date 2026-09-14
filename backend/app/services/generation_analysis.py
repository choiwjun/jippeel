"""결정론 생성 분석 (작가 피드백 자가개선 E3) — LLM 없는 통계·diff 서비스.

생성 산출물(output_text)과 작가가 실제 반영한 텍스트(landed_text)를
difflib으로 비교해 편집거리·삭제 표현·분량 분포·surface별 수용률을 산출한다.
분석 결과는 E5 제안 job의 입력 신호이며 원고·설정을 변경하지 않는다.
"""
from __future__ import annotations

import difflib
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Chapter, GenerationRun

# 원고성 텍스트 채널만 diff 대상 — plan은 계약 JSON, review는 감수 의견이다.
_TEXT_CHANNELS = {"draft", "refined", "worker"}
_ACCEPTED = {"inserted", "replaced"}
# 삭제 표현 추출의 최소/최대 조각 길이 — 1글자 조각은 신호가 아니고
# 과장 조각(사실상 전체 재작성)은 표현 단위가 아니다.
_MIN_SPAN = 2
_MAX_SPAN = 120
_TOP_DELETED = 20


def _edit_ratio(a: str, b: str) -> float:
    """0~1 유사도 — 1.0이면 작가가 한 글자도 고치지 않았다."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _deleted_spans(source: str, landed: str) -> list[str]:
    """output→landed diff에서 delete/replace 구간의 원문 조각을 추출한다."""
    sm = difflib.SequenceMatcher(None, source, landed, autojunk=False)
    spans: list[str] = []
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag not in ("delete", "replace"):
            continue
        frag = source[i1:i2].strip()
        if _MIN_SPAN <= len(frag) <= _MAX_SPAN:
            spans.append(frag)
    return spans


def analyze_project_generations(db: Session, project_id: int) -> dict:
    """프로젝트의 전체 생성 이력을 결정론적으로 집계한다."""
    runs = db.scalars(
        select(GenerationRun)
        .where(GenerationRun.project_id == project_id)
        .options(selectinload(GenerationRun.outputs))
        .order_by(GenerationRun.id.asc())
    ).all()

    surfaces: dict[str, dict] = {}
    edit_entries: list[dict] = []
    deleted_counter: Counter[str] = Counter()
    deleted_evidence: dict[str, set[int]] = {}
    lengths: dict[str, list[int]] = {}
    total_outputs = 0

    # landed_text가 현재 원고에 남아 있는지 보는 잔존 검사용 — 회차당 한 번 조회
    chapter_cache: dict[int, str] = {}

    def _chapter_text(chapter_id: int | None) -> str | None:
        if chapter_id is None:
            return None
        if chapter_id not in chapter_cache:
            chapter = db.get(Chapter, chapter_id)
            chapter_cache[chapter_id] = chapter.content_md or "" if chapter else ""
        return chapter_cache[chapter_id]

    for run in runs:
        surf = surfaces.setdefault(run.surface, {
            "runs": 0, "outputs": 0,
            "outcome_counts": {"pending": 0, "inserted": 0, "replaced": 0,
                               "copied": 0, "discarded": 0},
            "wall_ms_total": 0,
        })
        surf["runs"] += 1
        surf["wall_ms_total"] += run.wall_ms or 0
        for output in run.outputs:
            total_outputs += 1
            surf["outputs"] += 1
            surf["outcome_counts"][output.outcome] = (
                surf["outcome_counts"].get(output.outcome, 0) + 1)
            lengths.setdefault(output.channel, []).append(output.output_chars)

            if output.channel not in _TEXT_CHANNELS:
                continue
            if output.landed_text is None:
                continue
            ratio = _edit_ratio(output.output_text, output.landed_text)
            current = _chapter_text(run.chapter_id)
            edit_entries.append({
                "output_id": output.id,
                "chapter_id": run.chapter_id,
                "channel": output.channel,
                "surface": run.surface,
                "ratio": round(ratio, 4),
                "output_chars": output.output_chars,
                "landed_chars": len(output.landed_text),
                "landed_still_present": (
                    None if current is None
                    else output.landed_text in current),
            })
            for span in _deleted_spans(output.output_text, output.landed_text):
                deleted_counter[span] += 1
                deleted_evidence.setdefault(span, set()).add(output.id)

    surface_stats = []
    for name, agg in surfaces.items():
        decided = sum(agg["outcome_counts"][k] for k in
                      ("inserted", "replaced", "copied", "discarded"))
        accepted = (agg["outcome_counts"]["inserted"]
                    + agg["outcome_counts"]["replaced"])
        surface_stats.append({
            "surface": name,
            "runs": agg["runs"],
            "outputs": agg["outputs"],
            "outcome_counts": agg["outcome_counts"],
            "accept_rate": (round(accepted / decided, 4)
                            if decided else None),
            "avg_wall_ms": (round(agg["wall_ms_total"] / agg["runs"], 1)
                            if agg["runs"] else 0),
        })

    deleted = [
        {"text": text, "count": count,
         "output_ids": sorted(deleted_evidence[text])[:10]}
        for text, count in deleted_counter.most_common(_TOP_DELETED)
    ]

    length_stats = [
        {"channel": channel, "count": len(vals),
         "avg_chars": round(sum(vals) / len(vals), 1),
         "min_chars": min(vals), "max_chars": max(vals)}
        for channel, vals in sorted(lengths.items())
    ]

    ratios = [e["ratio"] for e in edit_entries]
    return {
        "project_id": project_id,
        "total_runs": len(runs),
        "total_outputs": total_outputs,
        "surfaces": surface_stats,
        "edit_distances": edit_entries,
        "avg_edit_ratio": (round(sum(ratios) / len(ratios), 4)
                           if ratios else None),
        "deleted_expressions": deleted,
        "length_distribution": length_stats,
    }
