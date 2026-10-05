"""Author-facing evidence views; no inference, writes or generation context changes."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, ChapterGoal, Character, EventImpact, Foreshadow, Relationship
from app.services.chapter_order import chapter_ordering, neighbor_condition
from app.services.long_memory import content_sha256, load_memory_freshness


def chapter_refs(db: Session, pid: int):
    rows = db.execute(select(Chapter.id, Chapter.title, Chapter.volume, Chapter.sort_order,
                             Chapter.revision).where(Chapter.project_id == pid)
                      .order_by(*chapter_ordering())).all()
    return {r.id: {"id": r.id, "title": r.title, "position": i + 1, "revision": r.revision}
            for i, r in enumerate(rows)}


def relations(db: Session, pid: int, chapter: Chapter, refs: dict) -> list[dict]:
    names = dict(db.execute(select(Character.id, Character.name).where(Character.project_id == pid)).all())
    rows = db.scalars(select(Relationship).where(Relationship.from_character_id.in_(names),
                                               Relationship.to_character_id.in_(names))
                      .order_by(Relationship.id)).all()
    items = [{"id": f"relation-{r.id}", "kind": "relation", "label": r.label or "관계",
              "from_name": names[r.from_character_id], "to_name": names[r.to_character_id],
              "excerpt": (r.note or "")[:1000], "basis": "시점 정보 없음 · 현재 작가 설정",
              "source": None} for r in rows]
    # Approval/retirement is append-only. A retired successor must hide its earlier
    # approved snapshot as well; querying approved rows alone would revive it.
    provenance = db.scalars(select(EventImpact.provenance_json).where(EventImpact.project_id == pid)).all()
    superseded = {p["supersedes_id"] for p in provenance if isinstance(p, dict)
                  and isinstance(p.get("supersedes_id"), int) and not isinstance(p.get("supersedes_id"), bool)}
    events = db.scalars(select(EventImpact).join(Chapter, Chapter.id == EventImpact.chapter_id)
                        .where(EventImpact.project_id == pid, Chapter.project_id == pid,
                               EventImpact.visibility == "approved",
                               (Chapter.id == chapter.id) | neighbor_condition(chapter, previous=True))
                        .order_by(*chapter_ordering(), EventImpact.id)).all()
    source_ids = {e.chapter_id for e in events if e.id not in superseded and e.source_sha256}
    # Multiple events can reference the same long manuscript: read and hash it once.
    sources = {r.id: (content_sha256(r.content_md), r.revision) for r in db.execute(
        select(Chapter.id, Chapter.content_md, Chapter.revision)
        .where(Chapter.project_id == pid, Chapter.id.in_(source_ids))
    ).all()} if source_ids else {}
    for event in events:
        # Approval alone does not establish provenance. Legacy/manual events without a hash
        # are left in their management screen, not presented as verified historical changes.
        source = sources.get(event.chapter_id)
        if (event.id in superseded or event.chapter_id not in refs or source is None
                or source[0] != event.source_sha256):
            continue
        for i, delta in enumerate(event.relationship_deltas_json or []):
            if not isinstance(delta, dict):
                continue
            pair = delta.get("pair")
            if not isinstance(pair, list) or len(pair) != 2:
                continue
            if all(isinstance(v, int) and not isinstance(v, bool) and v > 0 and v in names for v in pair):
                pair_names = [names[v] for v in pair]
            elif all(isinstance(v, str) and v.strip() for v in pair):
                pair_names = [v.strip() for v in pair]
            else:
                continue
            before = delta.get("from") if isinstance(delta.get("from"), str) else "미기록"
            after = delta.get("to") if isinstance(delta.get("to"), str) else "미기록"
            note = delta.get("note") if isinstance(delta.get("note"), str) else ""
            items.append({"id": f"event-{event.id}-{i}", "kind": "relationship_change",
                          "label": event.label, "from_name": pair_names[0][:255], "to_name": pair_names[1][:255],
                          "excerpt": f"{before[:400]} → {after[:400]}\n{note[:200]}",
                          "basis": "작가 승인 변화 기록 · 현재 원문 해시 일치",
                          "source": {**refs[event.chapter_id], "revision": source[1]}})
    return items


def foreshadows(db: Session, pid: int, chapter: Chapter, refs: dict) -> list[dict]:
    rows = db.scalars(select(Foreshadow).where(Foreshadow.project_id == pid).order_by(Foreshadow.id)).all()
    cutoff = refs[chapter.id]["position"]
    def ref(cid):
        source = refs.get(cid)
        return {**source, "future": source["position"] > cutoff} if source else None
    return [{"id": f"foreshadow-{r.id}", "kind": "foreshadow", "label": r.title,
             "excerpt": (r.content or "")[:1000], "basis": "작가 등록 기록",
             "registered_status": r.status, "disposition": r.disposition,
             "planted": ref(r.planted_chapter_id), "resolved": ref(r.resolved_chapter_id),
             "planned": ref(r.planned_resolution_chapter_id),
             "source": ref(r.planted_chapter_id)} for r in sorted(
                 rows, key=lambda r: (refs.get(r.planted_chapter_id, {}).get("position", float("inf")), r.id))]


def review_key(kind: str, row) -> str:
    # SQLite may reuse a deleted INTEGER PRIMARY KEY. Preserve each row's creation
    # identity so an old decision cannot become the history of a newly created target.
    generation = content_sha256(f"{row.project_id if kind == 'memory' else row.chapter_id}:{row.id}:{row.created_at.isoformat()}")[:24]
    return f"{kind}-{row.id}-{generation}"


def reviews(db: Session, pid: int, refs: dict) -> list[dict]:
    freshness = load_memory_freshness(db, pid)
    # Conservative project-wide fingerprint includes full text and recursive provenance.
    # Unrelated source changes may require a reload; no changed source can be silently adopted.
    graph_token = content_sha256(json.dumps({
        "memories": [{k: getattr(m, k) for k in (
            "id", "chapter_id", "kind", "body", "visibility", "source_revision",
            "source_sha256", "provenance_json", "effective_from_sort_order", "effective_to_sort_order"
        )} for m in sorted(freshness.entries.values(), key=lambda m: m.id)],
        "chapters": [{"id": c.id, "revision": c.revision, "hash": content_sha256(c.content_md),
                      "title": c.title, "volume": c.volume, "sort_order": c.sort_order}
                     for c in sorted(freshness.chapters.values(), key=lambda c: c.id)],
    }, ensure_ascii=False, sort_keys=True))
    kind_labels = {"summary": "회차 요약", "beat": "전개", "decision": "선택", "fact": "설정",
                   "timeline": "시간 순서", "relationship_note": "관계 메모",
                   "arc_summary": "아크 요약", "volume_memory": "권 기억"}
    items = []
    for memory in sorted(freshness.entries.values(), key=lambda r: r.id):
        if memory.visibility == "retired" or not freshness.is_stale(memory):
            continue
        chapter = freshness.chapters.get(memory.chapter_id)
        if memory.chapter_id is not None and chapter is None:
            reason = "근거 회차 누락"
        elif chapter is not None and (memory.source_revision != chapter.revision
                                     or memory.source_sha256 != content_sha256(chapter.content_md)):
            reason = "근거 원고 버전·내용 변경"
        else:
            reason = "연결 근거 불일치 · 하위 기억의 변경·승인·출처 확인 필요"
        items.append({"id": f"memory-{memory.id}", "review_key": review_key("memory", memory), "kind": "stale_memory",
                      "label": f"{kind_labels.get(memory.kind, '기억')} #{memory.id}", "excerpt": (memory.body or "")[:1000],
                      "basis": reason, "visibility": memory.visibility, "review_text": memory.body,
                      "source_revision": memory.source_revision,
                      "source": {**refs[memory.chapter_id], "revision": chapter.revision}
                      if chapter is not None and memory.chapter_id in refs else None})
    goals = db.execute(select(ChapterGoal, Chapter.revision).join(Chapter, Chapter.id == ChapterGoal.chapter_id)
                       .where(Chapter.project_id == pid, ChapterGoal.base_manuscript_revision.is_not(None),
                              ChapterGoal.base_manuscript_revision != Chapter.revision)
                       .order_by(*chapter_ordering())).all()
    for goal, revision in goals:
        if goal.chapter_id not in refs:
            continue
        payload = goal.goal_json or {}
        events = payload.get("core_events") or []
        excerpt = "\n".join(str(v) for v in events)[:1000] if isinstance(events, list) else ""
        labels = {"emotion_goal": "감정 목표", "core_events": "핵심 사건", "character_choices": "인물 선택",
                  "cost": "대가", "prohibitions": "금지 사항", "next_hook": "다음 회차 연결",
                  "ending_intent": "결말 의도", "scene_type": "장면 유형", "target_chars_novelpia": "목표 글자 수"}
        review_text = "\n".join(f"{labels.get(key, key)}: " + (" / ".join(map(str, value)) if isinstance(value, list) else str(value))
                                for key, value in payload.items() if value is not None)
        review_text += f"\n회차 용도: { {'serial': '연재', 'volume_end': '권말', 'series_finale': '최종화'}.get(goal.episode_purpose, goal.episode_purpose)}"
        items.append({"id": f"goal-{goal.id}", "review_key": review_key("goal", goal), "kind": "goal_drift", "label": f"회차 목표 v{goal.goal_version}",
                      "excerpt": excerpt, "basis": "목표 기준 원고와 현재 저장 버전이 다름",
                      "review_text": review_text,
                      "goal_fingerprint": content_sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
                      "source_revision": goal.base_manuscript_revision,
                      "source": {**refs[goal.chapter_id], "revision": revision}})
    for item in items:
        item["evidence_token"] = content_sha256(graph_token + json.dumps(item, ensure_ascii=False, sort_keys=True))
    return items
