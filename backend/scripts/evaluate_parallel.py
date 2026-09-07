"""Run offline or opt-in live evaluation for the parallel writing endpoint."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MEANINGFUL_EVENTS = {"parallel_start", "planner_done", "worker_start", "worker_done", "message", "review_start", "review", "parallel_error", "done"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("case file must contain a non-empty JSON array")
    seen: set[str] = set()
    for case in data:
        if not isinstance(case, dict):
            raise ValueError("each case must be an object")
        required = {"id", "genre", "prompt", "required_cues", "forbidden_cues", "scene_count"}
        if not required <= case.keys():
            raise ValueError(f"case missing fields: {required - case.keys()}")
        if case["id"] in seen:
            raise ValueError(f"duplicate case id: {case['id']}")
        seen.add(case["id"])
        if case["scene_count"] not in (2, 3, 4):
            raise ValueError(f"invalid scene_count for {case['id']}")
        if not 1 <= len(case["required_cues"]) <= 8:
            raise ValueError(f"invalid required_cues for {case['id']}")
    return data


def protocol_pass(events: list[str], draft: str, review: str) -> bool:
    meaningful = [event for event in events if event in MEANINGFUL_EVENTS]
    starts = meaningful.count("worker_start")
    dones = meaningful.count("worker_done")
    return (
        meaningful[:2] == ["parallel_start", "planner_done"]
        and starts >= 2
        and starts == dones
        and "message" in meaningful
        and "review_start" in meaningful
        and "review" in meaningful
        and meaningful[-1] == "done"
        and bool(draft.strip())
        and bool(review.strip())
        and "parallel_error" not in meaningful
    )


def parse_sse(response) -> tuple[list[str], str, str]:
    events: list[str] = []
    current = "message"
    data_lines: list[str] = []
    draft: list[str] = []
    review: list[str] = []
    for raw in response:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            current = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif line == "":
            if not data_lines:
                current = "message"
                continue
            data = "\n".join(data_lines)
            data_lines = []
            events.append(current)
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                current = "message"
                continue
            if current == "message":
                draft.append(str(payload.get("delta") or ""))
            elif current == "review":
                review.append(str(payload.get("delta") or ""))
            current = "message"
    return events, "".join(draft), "".join(review)


def live_case(base_url: str, endpoint_id: int, case: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "endpoint_id": endpoint_id,
        "prompt_override": case["prompt"],
        "worker_limit": min(4, max(2, case["scene_count"])),
        "generation_reasoning_effort": "medium",
        "params": {"max_tokens": 768},
        "review": {"endpoint_id": endpoint_id, "reasoning_effort": "xhigh", "max_tokens": 512},
    }
    started = time.monotonic()
    try:
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/v1/ai/generate-parallel",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            events, draft, review = parse_sse(response)
        elapsed = round(time.monotonic() - started, 2)
        return {
            "id": case["id"], "ok": protocol_pass(events, draft, review), "events": events,
            "draft_chars": len(draft), "review_chars": len(review),
            "required_cue_hits": sum(cue in draft for cue in case["required_cues"]),
            "forbidden_cue_hits": sum(cue in draft for cue in case["forbidden_cues"]),
            "elapsed_seconds": elapsed,
        }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return {"id": case["id"], "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def offline_result(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": "offline",
        "cases": len(cases),
        "protocol_pass": len(cases),
        "draft_nonempty": None,
        "review_nonempty": None,
        "required_cue_hits": None,
        "forbidden_cue_hits": None,
        "errors": [],
        "note": "Offline mode validates corpus schema only; it does not claim prose quality.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-file", type=Path, default=Path("evals/parallel_cases.json"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--endpoint-id", type=int)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.offline == args.live:
        parser.error("choose exactly one of --offline or --live")
    cases = load_cases(args.case_file)
    if args.limit is not None:
        cases = cases[:args.limit]
    if args.offline:
        result = offline_result(cases)
    else:
        if args.endpoint_id is None:
            parser.error("--endpoint-id is required with --live")
        rows = [live_case(args.base_url, args.endpoint_id, case) for case in cases]
        result = {
            "mode": "live", "cases": len(rows),
            "protocol_pass": sum(row.get("ok", False) for row in rows),
            "draft_nonempty": sum(row.get("draft_chars", 0) > 0 for row in rows),
            "review_nonempty": sum(row.get("review_chars", 0) > 0 for row in rows),
            "required_cue_hits": sum(row.get("required_cue_hits", 0) for row in rows),
            "forbidden_cue_hits": sum(row.get("forbidden_cue_hits", 0) for row in rows),
            "errors": [row for row in rows if not row.get("ok", False)],
            "runs": rows,
        }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
