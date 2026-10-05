"""2026-10-05 bug audit: real API/context/worker regressions, synthetic DB only."""
import pytest
from sqlalchemy import delete, update

from app.models import Chapter, MemoryEntry
from app.schemas import GenerateContext, GenerateRequest
from app.services.ai_context import build_context_bundle, request_from_generate
from app.services.long_memory import create_memory_entry, select_context_memory
from app.services.summary_worker import (
    plan_arc_summary_jobs, plan_volume_summary_jobs, run_pending_summary_jobs,
)
from tests.conftest import _db


def _project(client):
    return client.post("/api/v1/projects", json={"title": "audit project"}).json()["id"]


def _chapter(client, pid, title, *, volume=1, sort_order=1, body="source"):
    chapter = client.post(f"/api/v1/projects/{pid}/chapters", json={
        "title": title, "volume": volume, "sort_order": sort_order,
    }).json()
    if body:
        response = client.put(f"/api/v1/chapters/{chapter['id']}/content", json={
            "content_md": body, "expected_revision": 0,
        })
        assert response.status_code == 200, response.text
        chapter = response.json()
    return chapter


@pytest.mark.parametrize("target,field", [
    ("project", "title"), ("chapter", "title"), ("chapter", "status"),
    ("chapter", "sort_order"), ("character", "name"),
    ("character", "lifecycle_status"), ("scene", "title"),
    ("scene", "content_md"), ("scene", "sort_order"),
])
def test_not_null_patch_is_rejected_and_preserves_values(client, target, field):
    pid = _project(client)
    chapter = _chapter(client, pid, "chapter")
    character = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "character"}).json()
    scene = client.post(f"/api/v1/chapters/{chapter['id']}/scenes", json={
        "title": "scene", "content_md": "scene body", "sort_order": 1,
    }).json()
    paths = {
        "project": f"/projects/{pid}", "chapter": f"/chapters/{chapter['id']}",
        "character": f"/characters/{character['id']}", "scene": f"/scenes/{scene['id']}",
    }
    path = "/api/v1" + paths[target]
    before = client.get(path).json()
    response = client.patch(path, json={field: None})
    assert response.status_code == 422, response.text
    assert client.get(path).json()[field] == before[field]


def test_nullable_patch_still_clears_volume_memo_and_lifecycle_reference(client):
    pid = _project(client)
    chapter = _chapter(client, pid, "chapter")
    client.patch(f"/api/v1/chapters/{chapter['id']}", json={"memo": "memo"})
    response = client.patch(f"/api/v1/chapters/{chapter['id']}", json={"volume": None, "memo": None})
    assert response.status_code == 200
    assert response.json()["volume"] is None and response.json()["memo"] is None
    character = client.post(f"/api/v1/projects/{pid}/characters", json={
        "name": "character", "lifecycle_chapter_id": chapter["id"],
    }).json()
    response = client.patch(f"/api/v1/characters/{character['id']}", json={"lifecycle_chapter_id": None})
    assert response.status_code == 200 and response.json()["lifecycle_chapter_id"] is None


@pytest.mark.parametrize("lifecycle", ["departed", "deceased"])
def test_lifecycle_chapter_delete_conflict_then_reference_clear(client, lifecycle):
    pid = _project(client)
    chapter = _chapter(client, pid, "source", body="preserved manuscript")
    character = client.post(f"/api/v1/projects/{pid}/characters", json={
        "name": "character", "lifecycle_status": lifecycle, "lifecycle_chapter_id": chapter["id"],
    }).json()
    response = client.delete(f"/api/v1/chapters/{chapter['id']}")
    assert response.status_code == 409, response.text
    assert "캐릭터" in response.json()["detail"]
    assert client.get(f"/api/v1/chapters/{chapter['id']}").json()["content_md"] == "preserved manuscript"
    assert client.get(f"/api/v1/characters/{character['id']}").json()["lifecycle_chapter_id"] == chapter["id"]
    client.patch(f"/api/v1/characters/{character['id']}", json={"lifecycle_chapter_id": None})
    assert client.delete(f"/api/v1/chapters/{chapter['id']}").status_code == 204


@pytest.mark.parametrize("volumes,sorts", [
    ([1, 1, 2], [1, 2, 1]), ([1, 1, 1], [1, 1, 1]), ([1, 2, None], [9, 1, 0]),
])
def test_ai_neighbors_match_volume_sort_and_id_order(client, volumes, sorts):
    pid = _project(client)
    chapters = [_chapter(client, pid, f"chapter-{i}", volume=volume, sort_order=sort,
                         body=f"MANUSCRIPT_{i}") for i, (volume, sort) in enumerate(zip(volumes, sorts))]
    listing = client.get(f"/api/v1/projects/{pid}/chapters").json()
    assert [c["id"] for c in listing] == [c["id"] for c in chapters]
    db = _db(client)
    for i, chapter in enumerate(chapters):
        bundle = build_context_bundle(db, request_from_generate(GenerateRequest(
            prompt_override="continue", context=GenerateContext(
                project_id=pid, chapter_id=chapter["id"], previous_chapter=True,
                auto_outline=True, include_memory=False,
            ),
        )))
        previous = [b for b in bundle.blocks if b.startswith("[직전 회차")]
        if i == 0:
            assert previous == []
        else:
            assert len(previous) == 1 and f"MANUSCRIPT_{i - 1}" in previous[0]
        assert bundle.metadata["outline"].get("next_chapter_id") == (
            chapters[i + 1]["id"] if i + 1 < len(chapters) else None
        )


def _hierarchy(client, *, include_volume=True, positions=None):
    pid = _project(client)
    positions = positions or [(1, n) for n in range(1, 6)]
    chapters = [_chapter(client, pid, f"source-{n}", volume=volume, sort_order=sort)
                for n, (volume, sort) in enumerate(positions)]
    db = _db(client)
    summaries = []
    for chapter in chapters[:4]:
        summaries.append(create_memory_entry(db, project_id=pid, chapter_id=chapter["id"],
            source_revision=chapter["revision"], source_text=chapter["content_md"], kind="summary",
            body=f"summary-{chapter['id']}", visibility="approved"))
    db.commit()
    plan_arc_summary_jobs(db, project_id=pid, arc_size=2, min_arc_sources=2,
        prompt_version="audit-arc", provider_identity="fake", model_snapshot="fake", request_options={})
    jobs = run_pending_summary_jobs(db, lambda job: f"arc-{job.id}")
    arcs = [db.get(MemoryEntry, job.memory_entry_id) for job in jobs]
    assert len(arcs) == 2
    for arc in arcs:
        assert client.patch(f"/api/v1/projects/{pid}/memories/{arc.id}", json={"visibility": "approved"}).status_code == 200
    volume = None
    if include_volume:
        db.expire_all()
        plan_volume_summary_jobs(db, project_id=pid, volume_size=2, min_volume_sources=2,
            prompt_version="audit-volume", provider_identity="fake", model_snapshot="fake", request_options={})
        jobs = run_pending_summary_jobs(db, lambda job: f"volume-{job.id}")
        volume = db.get(MemoryEntry, jobs[0].memory_entry_id)
        assert client.patch(f"/api/v1/projects/{pid}/memories/{volume.id}", json={"visibility": "approved"}).status_code == 200
    db.expire_all()
    return pid, chapters, summaries, arcs, volume, db


@pytest.mark.parametrize("change", ["manuscript", "retire", "missing", "malformed"])
def test_staleness_propagates_to_arc_volume_list_and_context(client, change):
    pid, chapters, summaries, arcs, volume, db = _hierarchy(client)
    assert [e.id for e in select_context_memory(db, pid, chapters[-1]["id"])] == [volume.id]
    if change == "manuscript":
        response = client.put(f"/api/v1/chapters/{chapters[0]['id']}/content", json={
            "content_md": "corrected source", "expected_revision": chapters[0]["revision"],
        })
        assert response.status_code == 200
    elif change == "retire":
        assert client.patch(f"/api/v1/projects/{pid}/memories/{summaries[0].id}", json={"visibility": "retired"}).status_code == 200
    elif change == "missing":
        db.delete(summaries[0]); db.commit()
    else:
        arcs[0].provenance_json = {"arc_source_entry_ids": ["invalid-id"]}
        db.commit()
    db.expire_all()
    rows = client.get(f"/api/v1/projects/{pid}/memories").json()
    by_id = {row["id"]: row for row in rows}
    assert by_id[arcs[0].id]["stale"] is True
    assert by_id[volume.id]["stale"] is True
    assert by_id[arcs[1].id]["stale"] is False
    selected = [e.id for e in select_context_memory(db, pid, chapters[-1]["id"])]
    assert arcs[0].id not in selected and volume.id not in selected
    assert arcs[1].id in selected and summaries[1].id in selected
    stale_rows = client.get(f"/api/v1/projects/{pid}/memories?stale=true").json()
    assert {arcs[0].id, volume.id} <= {row["id"] for row in stale_rows}


def test_arc_plan_excludes_stale_approved_source(client):
    pid = _project(client)
    chapters = [_chapter(client, pid, str(n), sort_order=n) for n in (1, 2)]
    db = _db(client)
    for chapter in chapters:
        create_memory_entry(db, project_id=pid, chapter_id=chapter["id"],
            source_revision=chapter["revision"], source_text=chapter["content_md"], kind="summary",
            body="approved summary", visibility="approved")
    db.commit()
    client.put(f"/api/v1/chapters/{chapters[0]['id']}/content", json={"content_md": "changed", "expected_revision": 1})
    db.expire_all()
    created, _ = plan_arc_summary_jobs(db, project_id=pid, arc_size=2, min_arc_sources=2,
        prompt_version="audit", provider_identity="fake", model_snapshot="fake", request_options={})
    assert created == []


def test_arc_worker_rejects_source_changed_during_provider_call(client):
    pid = _project(client)
    chapters = [_chapter(client, pid, str(n), sort_order=n) for n in (1, 2)]
    db = _db(client)
    for chapter in chapters:
        create_memory_entry(db, project_id=pid, chapter_id=chapter["id"],
            source_revision=chapter["revision"], source_text=chapter["content_md"], kind="summary",
            body="approved summary", visibility="approved")
    db.commit()
    plan_arc_summary_jobs(db, project_id=pid, arc_size=2, min_arc_sources=2,
        prompt_version="audit", provider_identity="fake", model_snapshot="fake", request_options={})
    def provider(job):
        response = client.put(f"/api/v1/chapters/{chapters[0]['id']}/content", json={"content_md": "changed", "expected_revision": 1})
        assert response.status_code == 200
        return "obsolete result"
    jobs = run_pending_summary_jobs(db, provider)
    assert jobs[0].status == "stale_source"
    assert jobs[0].memory_entry_id is None


@pytest.mark.parametrize("first_volume,next_volume", [(1, 2), (2, None)])
def test_rollup_future_gates_and_planners_follow_canonical_order(client, first_volume, next_volume):
    pid, chapters, summaries, arcs, volume, db = _hierarchy(client, positions=[
        (first_volume, 98), (first_volume, 99), (next_volume, 1), (next_volume, 2),
        (first_volume, 100),
    ])
    # Repeated sort values across volumes cannot regroup sources or leak future facts.
    assert arcs[0].provenance_json["arc_source_entry_ids"] == [s.id for s in summaries[:2]]
    assert arcs[1].provenance_json["arc_source_entry_ids"] == [s.id for s in summaries[2:]]
    assert volume.provenance_json["volume_source_entry_ids"] == [a.id for a in arcs]
    assert [e.id for e in select_context_memory(db, pid, chapters[-1]["id"])] == [arcs[0].id]
    later = _chapter(client, pid, "after rollup", volume=next_volume, sort_order=3)
    assert [e.id for e in select_context_memory(db, pid, later["id"])] == [volume.id]


@pytest.mark.parametrize("kind", ["arc", "volume"])
@pytest.mark.parametrize("change", ["retire", "delete"])
def test_rollup_worker_refreshes_cached_sources_before_provider(client, kind, change):
    if kind == "volume":
        pid, _chapters, _summaries, sources, _volume, db = _hierarchy(client, include_volume=False)
        plan_volume_summary_jobs(db, project_id=pid, volume_size=2, min_volume_sources=2,
            prompt_version="audit-volume", provider_identity="fake", model_snapshot="fake", request_options={})
    else:
        pid = _project(client)
        chapters = [_chapter(client, pid, str(n), sort_order=n) for n in (1, 2)]
        db = _db(client)
        sources = [create_memory_entry(db, project_id=pid, chapter_id=c["id"],
            source_revision=c["revision"], source_text=c["content_md"], kind="summary",
            body="approved summary", visibility="approved") for c in chapters]
        db.commit()
        plan_arc_summary_jobs(db, project_id=pid, arc_size=2, min_arc_sources=2,
            prompt_version="audit-arc", provider_identity="fake", model_snapshot="fake", request_options={})
    cached = sources[0]
    external = _db(client)
    if change == "retire":
        external.execute(update(MemoryEntry).where(MemoryEntry.id == cached.id).values(visibility="retired"))
    else:
        external.execute(delete(MemoryEntry).where(MemoryEntry.id == cached.id))
    external.commit()
    assert db.get(MemoryEntry, cached.id) is cached and cached.visibility == "approved"
    calls = []
    jobs = run_pending_summary_jobs(db, lambda job: calls.append(job.id) or "must not generate", limit=1)
    assert len(jobs) == 1 and jobs[0].status == "stale_source"
    assert jobs[0].memory_entry_id is None and calls == []
