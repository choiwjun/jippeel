"""Synthetic bug reproductions. Run with backend/.venv/Scripts/python.exe -I -B.

Installs the repository's guard before any third-party or application imports.
No production DB, HTTP server, provider, key store, or subprocess is used.
"""
import json
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from tests.isolation_guard import install, require_isolation

install([])
state = require_isolation()
os.environ["JIPPEEL_LAN_AUTH"] = "0"
os.environ["JIPPEEL_AUTOBACKUP_INTERVAL_MIN"] = "0"
logging.disable(logging.CRITICAL)

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app.database import Base, create_db_engine, get_db, engine as app_engine
from app.main import app
from app.models import Chapter
from app.schemas import GenerateContext, GenerateRequest
from app.services.ai_context import build_context_bundle, request_from_generate
from app.services.long_memory import create_memory_entry, select_context_memory
from app.services.summary_worker import plan_arc_summary_jobs, run_pending_summary_jobs

probe_engine = create_db_engine("sqlite:///" + (state.root / "probe.db").as_posix())
Base.metadata.create_all(probe_engine)
Session = sessionmaker(bind=probe_engine, autoflush=False, expire_on_commit=False)

def override_db():
    with Session() as db:
        yield db

app.dependency_overrides[get_db] = override_db
results = []

with TestClient(app, raise_server_exceptions=False) as client:
    def create_project(title):
        response = client.post("/api/v1/projects", json={"title": title})
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def create_chapter(pid, title, volume=1, sort_order=1):
        response = client.post(f"/api/v1/projects/{pid}/chapters", json={
            "title": title, "volume": volume, "sort_order": sort_order,
        })
        assert response.status_code == 201, response.text
        return response.json()["id"]

    pid = create_project("lifecycle-probe")
    cid = create_chapter(pid, "departure-source")
    character = client.post(f"/api/v1/projects/{pid}/characters", json={
        "name": "synthetic-character", "lifecycle_status": "departed", "lifecycle_chapter_id": cid,
    })
    assert character.status_code == 201, character.text
    deletion = client.delete(f"/api/v1/chapters/{cid}")
    assert deletion.status_code == 500, deletion.text
    assert client.get(f"/api/v1/chapters/{cid}").status_code == 200
    results.append({"case": "lifecycle_chapter_delete", "actual_status": deletion.status_code,
                    "response": deletion.json(), "chapter_preserved": True})

    deletion = client.delete(f"/api/v1/projects/{pid}")
    results.append({"case": "lifecycle_project_delete", "actual_status": deletion.status_code,
                    "project_exists_after": client.get(f"/api/v1/projects/{pid}").status_code == 200})

    pid = create_project("nullable-probe")
    cid = create_chapter(pid, "null-target")
    chid = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "null-target"}).json()["id"]
    sid = client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "null-target"}).json()["id"]
    for path, body in [
        (f"/projects/{pid}", {"title": None}),
        (f"/chapters/{cid}", {"title": None}),
        (f"/chapters/{cid}", {"status": None}),
        (f"/characters/{chid}", {"name": None}),
        (f"/characters/{chid}", {"lifecycle_status": None}),
        (f"/scenes/{sid}", {"content_md": None}),
    ]:
        response = client.patch("/api/v1" + path, json=body)
        assert response.status_code == 500, (path, body, response.text)
        results.append({"case": "null_patch", "path": path, "body": body, "actual_status": response.status_code})

    pid = create_project("volume-order-probe")
    c1 = create_chapter(pid, "volume-1-first", volume=1, sort_order=1)
    c2 = create_chapter(pid, "volume-1-last", volume=1, sort_order=2)
    c3 = create_chapter(pid, "volume-2-first", volume=2, sort_order=1)
    for cid, body in [(c1, "FIRST_VOLUME_OPENING"), (c2, "EXPECTED_PREVIOUS_END"), (c3, "CURRENT_VOLUME_OPENING")]:
        response = client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": body, "expected_revision": 0})
        assert response.status_code == 200, response.text
    listing = client.get(f"/api/v1/projects/{pid}/chapters").json()
    assert [c["id"] for c in listing] == [c1, c2, c3]
    with Session() as db:
        request = GenerateRequest(prompt_override="synthetic-request", context=GenerateContext(
            project_id=pid, chapter_id=c3, previous_chapter=True, auto_outline=True, include_memory=False,
        ))
        bundle = build_context_bundle(db, request_from_generate(request))
    related_blocks = [b for b in bundle.blocks if b.startswith("[직전 회차") or b.startswith("[다음 회차")]
    assert not any("EXPECTED_PREVIOUS_END" in b for b in related_blocks)
    assert bundle.metadata["outline"]["next_chapter_id"] == c2
    results.append({"case": "ai_volume_order", "ui_order": [c["id"] for c in listing],
                    "target_id": c3, "expected_previous_id": c2, "actual_related_blocks": related_blocks,
                    "actual_next_id": bundle.metadata["outline"]["next_chapter_id"]})

    pid = create_project("hierarchical-stale-probe")
    source_ids = [create_chapter(pid, f"memory-source-{n}", sort_order=n) for n in (1, 2)]
    target_id = create_chapter(pid, "memory-target", sort_order=3)
    for cid in source_ids:
        response = client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "OLD_SOURCE_FACT", "expected_revision": 0})
        assert response.status_code == 200, response.text
    with Session() as db:
        summary_ids = []
        for cid in source_ids:
            ch = db.get(Chapter, cid)
            entry = create_memory_entry(db, project_id=pid, chapter_id=cid,
                source_revision=ch.revision, source_text=ch.content_md, kind="summary",
                body="OLD_APPROVED_SUMMARY", visibility="approved")
            summary_ids.append(entry.id)
        db.commit()
        created, duplicates = plan_arc_summary_jobs(db, project_id=pid, arc_size=2, min_arc_sources=2,
            prompt_version="audit-arc-v1", provider_identity="fake-provider", model_snapshot="fake-model",
            request_options={})
        assert len(created) == 1 and not duplicates
        processed = run_pending_summary_jobs(db, lambda job: "ARC_OLD_FACT")
        assert processed[0].status == "draft_saved"
        arc_id = processed[0].memory_entry_id
    approved = client.patch(f"/api/v1/projects/{pid}/memories/{arc_id}", json={"visibility": "approved"})
    assert approved.status_code == 200, approved.text
    changed = client.put(f"/api/v1/chapters/{source_ids[0]}/content", json={
        "content_md": "NEW_CORRECTED_SOURCE_FACT", "expected_revision": 1,
    })
    assert changed.status_code == 200, changed.text
    memories = client.get(f"/api/v1/projects/{pid}/memories").json()
    by_id = {row["id"]: row for row in memories}
    assert by_id[summary_ids[0]]["stale"] is True
    assert by_id[arc_id]["stale"] is False
    with Session() as db:
        included = select_context_memory(db, pid, target_id)
    assert arc_id in [entry.id for entry in included]
    results.append({"case": "arc_stale_source", "changed_chapter_id": source_ids[0],
                    "source_summary_stale": by_id[summary_ids[0]]["stale"],
                    "arc_summary_stale": by_id[arc_id]["stale"],
                    "included_memory": [{"id": entry.id, "kind": entry.kind, "body": entry.body} for entry in included],
                    "fake_provider_calls": 1})

app.dependency_overrides.clear()
probe_engine.dispose()
app_engine.dispose()
print(json.dumps({"results": results, "isolation": {
    "violations": state.violations, "subprocess_attempts": state.subprocess_attempts,
    "internal_ipc_count": state.internal_ipc_count,
}}, ensure_ascii=True), flush=True)
