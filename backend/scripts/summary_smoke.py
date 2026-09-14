"""D04 실제 provider smoke — 합성 DB + 로컬 OAuth 브릿지 1회 호출.

실행 환경: 브릿지가 JIPPEEL_GPT_OAUTH_BASE_URL(기본 http://127.0.0.1:10531/v1)로
기동 중이어야 한다. 이 스크립트는 운영 DB를 건드리지 않는다 — 전용 임시
sqlite 파일에 프로젝트·회차·job을 만들고, provider만 실제 브릿지다.

    backend/.venv/bin/python scripts/summary_smoke.py [--keep-db PATH]

결과물: job 상태(draft_saved 기대), MemoryEntry draft 본문, provenance.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from sqlalchemy.orm import sessionmaker

# 앱 임포트 전에 DB URL을 합성 경로로 고정한다 — 운영 DB 오염 방지.
_TMPDIR = Path(tempfile.mkdtemp(prefix="summary-smoke-"))
_DEFAULT_DB = _TMPDIR / "smoke.db"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-db", default=None,
                        help="합성 DB를 지정 경로에 보존(기본은 임시 디렉터리)")
    args = parser.parse_args()

    import os
    db_path = Path(args.keep_db) if args.keep_db else _DEFAULT_DB
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    from app.database import create_db_engine
    from app.models import Base, Chapter, MemoryEntry, Project, SummaryJob
    from app.services.summary_provider import (
        SUMMARY_PROMPT_VERSION as ADAPTER_PROMPT_VERSION,
        make_gpt_summary_provider,
    )
    from app.services.summary_worker import (
        plan_summary_jobs,
        run_pending_summary_jobs,
    )
    from sqlalchemy import select

    engine = create_db_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False,
                               expire_on_commit=False)

    chapter_body = (
        "카엘은 폐역 입구에서 발소리를 멈췄다. 안쪽에서 금속이 스치는 소리가 "
        "났다. 그는 허리춤의 단도를 만지며 숨을 골랐다.\n\n"
        "\"누구야.\" 어둠 속에서 목소리가 먼저 물었다. 소녀였다. 손에는 녹슨 "
        "열쇠가 쥐어져 있었다.\n\n"
        "카엘은 대답 대신 등 뒤의 추격자 발소리에 귀를 기울였다. 셋. 아니 넷. "
        "\"여기서 나가려면 그 열쇠가 필요해.\" 소녀가 열쇠를 들어 올렸다. "
        "\"대신 나도 데려가.\"\n\n"
        "그는 망설이지 않았다. \"이름이 뭐야.\" \"리아.\" \"좋아, 리아. "
        "따라와.\" 두 사람은 환기구로 기어들어갔고, 폐역 문이 부서지는 "
        "소리가 등 뒤에서 울렸다."
    )

    with TestSession() as db:
        project = Project(title="smoke 대상 작품", genre="판타지")
        db.add(project)
        db.flush()
        chapter = Chapter(project_id=project.id, title="smoke 1화",
                          sort_order=1, content_md=chapter_body)
        db.add(chapter)
        db.commit()
        pid, cid = project.id, chapter.id
        revision = chapter.revision

        created, duplicates = plan_summary_jobs(
            db,
            project_id=pid,
            chapter_ids=[cid],
            prompt_version=ADAPTER_PROMPT_VERSION,
            provider_identity="gpt-oauth-bridge",
            model_snapshot="smoke",
            request_options={"purpose": "d04-smoke"},
        )
        print(json.dumps({
            "planned": [{"id": j.id, "status": j.status,
                         "idempotency_key": j.idempotency_key}
                        for j in created],
            "duplicates": len(duplicates),
        }, ensure_ascii=False))

        provider = make_gpt_summary_provider(session_factory=TestSession)
        processed = run_pending_summary_jobs(db, provider, project_id=pid)

        job = db.get(SummaryJob, processed[0].id)
        entry = db.scalar(
            select(MemoryEntry).where(MemoryEntry.id == job.memory_entry_id)
        ) if job.memory_entry_id else None
        print(json.dumps({
            "job_status": job.status,
            "job_error": job.error,
            "attempt_count": job.attempt_count,
            "memory_entry_id": job.memory_entry_id,
            "entry_visibility": entry.visibility if entry else None,
            "entry_kind": entry.kind if entry else None,
            "entry_provenance": entry.provenance_json if entry else None,
            "entry_body": entry.body if entry else None,
            "source_revision": revision,
            "db_path": str(db_path),
        }, ensure_ascii=False, indent=2))
        return 0 if job.status == "draft_saved" else 1


if __name__ == "__main__":
    sys.exit(main())
