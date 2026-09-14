"""G02 실제 provider 파일럿 러너 — 2026-09-14.

실제 승인 원고(운영 DB 복사본) 6사례를 실제 OAuth 브릿지(gpt-5.6-luna)로 실행.
결정론적 hard gate + raw SSE·usage·비용·DB 스냅샷 증거를 audit 디렉터리에 남긴다.
문학 rubric의 두 독립 평가자 blind 채점은 사람 영역 — 산출물은 blinded 형태로 보존.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:18701"
AUDIT = Path(__file__).resolve().parent
DB = "/tmp/jippeel-real-ui/pilot.db"

META_MARKERS = ["[감수]", "[수정본]", "```json", '"required_beats"', '"scene_count"', "closing_hook\":", "data:"]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def db_snapshot() -> str:
    """원고 보존 증거 — chapters.content_md/memo/revision 전부의 결정론적 해시.
    ai_usage 등 허용된 기록 테이블 변경은 스냅샷에서 제외한다."""
    con = sqlite3.connect(DB)
    rows = con.execute(
        "select id, content_md, memo, revision, status from chapters order by id").fetchall()
    con.close()
    return sha256(json.dumps(rows, ensure_ascii=False).encode())


def sse_post(path: str, payload: dict, timeout: float = 900.0):
    """SSE 엔드포인트 호출 — (events, raw_lines, wall_ms) 반환."""
    events: list[dict] = []
    raw: list[str] = []
    t0 = time.time()
    with httpx.stream("POST", BASE + path, json=payload,
                      headers={"Accept": "text/event-stream"}, timeout=timeout) as r:
        ev, data = "message", []
        for line in r.iter_lines():
            raw.append(line)
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
            elif line == "":
                if data:
                    events.append({"event": ev, "data": "".join(data)})
                ev, data = "message", []
        if data:
            events.append({"event": ev, "data": "".join(data)})
    return events, raw, int((time.time() - t0) * 1000)


def collect_text(events: list[dict], event_names=("message",)) -> str:
    out = []
    for e in events:
        if e["event"] in event_names:
            try:
                d = json.loads(e["data"])
                out.append(d.get("delta") or "")
            except json.JSONDecodeError:
                out.append(e["data"])
    return "".join(out)


def hard_gate(case: dict, draft: str, events: list[dict], scene_orders: list[int] | None):
    fails = []
    gold = case["gold"]
    for cue in gold["required_cues"]:
        if cue not in draft:
            fails.append(f"required cue missing: {cue}")
    for cue in gold["forbidden_cues"]:
        if cue in draft:
            fails.append(f"forbidden cue present: {cue}")
    for m in META_MARKERS:
        if m in draft and m not in ("[수정본]",):  # [수정본]은 review 이벤트만 — 본문에 있으면 leak
            fails.append(f"meta marker in draft: {m}")
    if scene_orders is not None and scene_orders != sorted(scene_orders):
        fails.append(f"scene order broken: {scene_orders}")
    if not draft.strip():
        fails.append("empty draft")
    if any(e["event"] in ("error", "parallel_error", "review_error") for e in events):
        fails.append("error event in stream")
    return fails


def main() -> int:
    cases = json.loads((AUDIT / "cases" / "cases.json").read_text(encoding="utf-8"))
    manifest_cases = []
    events_log = AUDIT / "provider-events.jsonl"
    outputs_dir = AUDIT / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    snap_before = db_snapshot()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ch1 = con.execute("select content_md, revision from chapters where id=1").fetchone()

    results = []
    total_wall = 0
    with events_log.open("a", encoding="utf-8") as elog:
        for case in cases:
            cid = case["case_id"]
            surface = case["surface"]
            req = case["request"]
            if req == "REAL_CHAPTER_1_DRAFT":
                payload = {"draft": ch1["content_md"], "reasoning_effort": "xhigh"}
            else:
                payload = req
            frozen = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
            input_hash = sha256(frozen)
            gold_frozen = json.dumps(case["gold"], ensure_ascii=False, sort_keys=True).encode()
            gold_hash = sha256(gold_frozen)

            path = {"generate": "/api/v1/ai/generate",
                    "generate-parallel": "/api/v1/ai/generate-parallel",
                    "review": "/api/v1/ai/review"}[surface]
            try:
                events, raw, wall_ms = sse_post(path, payload)
            except Exception as exc:
                results.append({"case_id": cid, "error": f"{type(exc).__name__}: {exc}",
                                "input_sha256": input_hash, "hard_gates": ["TRANSPORT_ERROR"]})
                continue
            total_wall += wall_ms
            for e in events:
                elog.write(json.dumps({"case_id": cid, "event": e["event"],
                                       "data": e["data"]}, ensure_ascii=False) + "\n")

            draft = collect_text(events, ("message",))
            review_txt = collect_text(events, ("review", "review_delta"))
            scene_orders = None
            if surface == "generate-parallel":
                orders = []
                for e in events:
                    if e["event"] == "worker_start":
                        try:
                            d = json.loads(e["data"])
                            orders.append(d.get("order", d.get("scene", {}).get("order")))
                        except json.JSONDecodeError:
                            pass
                scene_orders = [o for o in orders if isinstance(o, int)]

            gate_text = draft + "\n" + review_txt
            fails = hard_gate(case, gate_text, events, scene_orders)
            blind = f"blind-{cid.split('-')[-1]}"
            (outputs_dir / f"{blind}.txt").write_text(
                draft + ("\n\n=====REVIEW=====\n" + review_txt if review_txt else ""),
                encoding="utf-8")

            start_ev = next((e for e in events if e["event"] in ("start", "parallel_start")), None)
            start_meta = {}
            if start_ev:
                try:
                    start_meta = json.loads(start_ev["data"])
                except json.JSONDecodeError:
                    pass

            results.append({
                "case_id": cid, "surface": surface, "holdout": case["holdout"],
                "chapter_id": case["chapter_id"], "title": case["title"],
                "input_sha256": input_hash, "gold_contract_sha256": gold_hash,
                "model": start_meta.get("model"), "wall_ms": wall_ms,
                "draft_chars": len(draft), "review_chars": len(review_txt),
                "scene_orders": scene_orders,
                "injected_lore": start_meta.get("injected_lore"),
                "hard_gates": fails or ["PASS"],
                "blind_label": blind,
            })
            print(f"[{cid}] {surface} wall={wall_ms}ms draft={len(draft)}자 "
                  f"review={len(review_txt)}자 gates={fails or 'PASS'}", flush=True)

    snap_after = db_snapshot()
    usage_rows = [dict(r) for r in con.execute(
        "select kind, model, endpoint_name, prompt_chars, completion_chars, created_at "
        "from ai_usage order by id desc limit 20")]
    con.close()

    manifest = {
        "manifest_version": "2026-09-11", "status": "executed",
        "run_date": "2026-09-14", "provider": "ChatGPT OAuth (openai-oauth bridge)",
        "endpoint_name": "http://127.0.0.1:10531/v1", "model": "gpt-5.6-luna",
        "reasoning_effort": "xhigh (provider default; parallel workers medium)",
        "temperature": None, "max_tokens": None,
        "hard_cap_usd": 20, "actual_marginal_cost_usd": 0.0,
        "cost_basis": "ChatGPT OAuth subscription — 토큰당 과금 없음, marginal $0",
        "rubric_version": "ai-model-quality-evaluation-design-2026-09-10",
        "db_snapshot_before_sha256": snap_before,
        "db_snapshot_after_sha256": snap_after,
        "cases": manifest_cases or results,
    }
    (AUDIT / "evaluation-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "provider-usage.json").write_text(
        json.dumps({"ai_usage_rows": usage_rows, "total_wall_ms": total_wall},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "case-results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDIT / "blind-map.json").write_text(json.dumps(
        {r["case_id"]: r.get("blind_label") for r in results}, indent=2), encoding="utf-8")
    print(f"\nDB unchanged: {snap_before == snap_after} | total wall {total_wall/1000:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
