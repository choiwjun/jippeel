"""D04 운영 실행 — 실제 DB 대상 요약 backfill (계획 + worker 실행).

두 단계로 나뉜다:

  1. 계획(기본) — provider-free·멱등. chapter 본문이 있는 회차를 대상으로
     summary → arc → volume 순으로 job을 만든다. 같은 idempotency_key의
     job은 재사용되므로 반복 실행해도 중복되지 않는다. DB는 읽기+job
     append만 한다.

  2. 실행(--run) — 실제 provider 호출. 1 job = 1 호출이므로 --limit으로
     비용을 통제한다. 결과는 전부 MemoryEntry draft — 자동 승인 없음.
     브릿지(JIPPEEL_GPT_OAUTH_BASE_URL)가 살아 있어야 하며, credential은
     브릿지 소유다.

예:

    # 계획만 (안전, provider 호출 없음)
    ./.venv/bin/python scripts/summary_backfill.py \\
        --db /path/to/jippeel.db --project-id 1

    # 계획 + worker 실행, 비용 상한 5 job
    ./.venv/bin/python scripts/summary_backfill.py \\
        --db /path/to/jippeel.db --project-id 1 --run --limit 5

    # 특정 회차만
    ./.venv/bin/python scripts/summary_backfill.py \\
        --db /path/to/jippeel.db --project-id 1 --chapters 3,4,5 --run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True,
                        help="운영 SQLite 파일 경로 (alembic head 일치 필수)")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--chapters", default="all",
                        help="'all'(기본, 본문 있는 회차 전부) 또는 쉼표 구분 회차 id")
    parser.add_argument("--arc-size", type=int, default=10)
    parser.add_argument("--min-arc-sources", type=int, default=3)
    parser.add_argument("--volume-size", type=int, default=5)
    parser.add_argument("--min-volume-sources", type=int, default=2)
    parser.add_argument("--run", action="store_true",
                        help="worker 실행 — 실제 provider 호출 발생")
    parser.add_argument("--limit", type=int, default=5,
                        help="--run 시 한 번에 처리할 최대 job 수 (비용 상한)")
    parser.add_argument("--no-volume", action="store_true",
                        help="volume 단계 건너뛰기")
    parser.add_argument("--no-arc", action="store_true",
                        help="arc 단계 건너뛰기")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    db_path = Path(args.db)
    if not db_path.is_file():
        print(json.dumps({"error": f"db not found: {db_path}"},
                         ensure_ascii=False))
        return 2

    # 앱 임포트 전에 DB URL 고정 — 기본 ./jippeel.db로 새는 것을 막는다.
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.resolve()}"

    from sqlalchemy import select, text

    from app.database import ALEMBIC_HEAD, SessionLocal
    from app.models import Chapter

    with SessionLocal() as db:
        try:
            version = db.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception:
            version = None
        if version != ALEMBIC_HEAD:
            print(json.dumps({
                "error": "alembic head mismatch",
                "db_version": version,
                "expected": ALEMBIC_HEAD,
                "hint": "먼저 마이그레이션을 적용하세요 (백업 후 alembic upgrade head)",
            }, ensure_ascii=False))
            return 2

        if args.chapters == "all":
            chapter_ids = [
                cid for cid, in db.execute(
                    select(Chapter.id)
                    .where(Chapter.project_id == args.project_id)
                    .order_by(Chapter.sort_order)
                ).all()
            ]
        else:
            chapter_ids = [int(x) for x in args.chapters.split(",") if x.strip()]

        from app.services.summary_provider import (
            ARC_PROMPT_VERSION,
            SUMMARY_PROMPT_VERSION,
            VOLUME_PROMPT_VERSION,
        )
        from app.services.summary_worker import (
            plan_arc_summary_jobs,
            plan_summary_jobs,
            plan_volume_summary_jobs,
        )
        from app.services.gpt_oauth import get_provider

        resolved = get_provider()
        report: dict = {"db": str(db_path), "project_id": args.project_id,
                        "alembic_head": version, "plan": {}}

        created, dup = plan_summary_jobs(
            db, project_id=args.project_id, chapter_ids=chapter_ids,
            prompt_version=SUMMARY_PROMPT_VERSION,
            provider_identity=resolved.name,
            model_snapshot=resolved.default_model,
            request_options={"purpose": "backfill"},
        )
        report["plan"]["summary"] = {"created": len(created),
                                     "duplicates": len(dup)}

        if not args.no_arc:
            created, dup = plan_arc_summary_jobs(
                db, project_id=args.project_id,
                arc_size=args.arc_size, min_arc_sources=args.min_arc_sources,
                prompt_version=ARC_PROMPT_VERSION,
                provider_identity=resolved.name,
                model_snapshot=resolved.default_model,
                request_options={"purpose": "backfill"},
            )
            report["plan"]["arc"] = {"created": len(created),
                                     "duplicates": len(dup)}

        if not args.no_volume:
            created, dup = plan_volume_summary_jobs(
                db, project_id=args.project_id,
                volume_size=args.volume_size,
                min_volume_sources=args.min_volume_sources,
                prompt_version=VOLUME_PROMPT_VERSION,
                provider_identity=resolved.name,
                model_snapshot=resolved.default_model,
                request_options={"purpose": "backfill"},
            )
            report["plan"]["volume"] = {"created": len(created),
                                        "duplicates": len(dup)}

        if not args.run:
            report["ran"] = False
            report["hint"] = "worker 실행은 --run --limit N"
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        # 실제 provider 호출 전 브릿지 생존 확인 — 없으면 전부 provider_error가
        # 되므로 빠르게 중단한다.
        base = resolved.base_url.rstrip("/")
        try:
            with urllib.request.urlopen(f"{base}/models", timeout=3) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"bridge /models -> {resp.status}")
        except Exception as exc:
            report["error"] = f"bridge unreachable: {exc}"
            report["hint"] = "브릿지 기동 후 재실행 — job은 planned로 남는다"
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 2

        from app.services.summary_provider import make_gpt_summary_provider
        from app.services.summary_worker import run_pending_summary_jobs

        provider = make_gpt_summary_provider(session_factory=SessionLocal)
        processed = run_pending_summary_jobs(
            db, provider, project_id=args.project_id, limit=args.limit
        )
        report["ran"] = True
        report["processed"] = [
            {"id": j.id, "kind": j.kind, "status": j.status,
             "error": j.error, "memory_entry_id": j.memory_entry_id}
            for j in processed
        ]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        failed = [j for j in processed
                  if j.status in ("provider_error", "rejected")]
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
