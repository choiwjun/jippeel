"""summary-jobs API 계약 — plan은 멱등, run은 주입 provider로 draft만 쓴다."""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import MemoryEntry, SummaryJob
from app.routers import summary_jobs as summary_jobs_router
from tests.conftest import _db


def _project_with_chapters(client, bodies):
    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ids = []
    for i, body in enumerate(bodies, start=1):
        chapter = client.post(
            f"/api/v1/projects/{pid}/chapters",
            json={"title": f"{i}화", "sort_order": i},
        ).json()
        client.put(
            f"/api/v1/chapters/{chapter['id']}/content",
            json={"content_md": body, "expected_revision": 0},
        )
        ids.append(chapter["id"])
    return pid, ids


@pytest.fixture()
def fake_provider(monkeypatch):
    monkeypatch.setattr(
        summary_jobs_router.gpt_oauth, "get_provider",
        lambda: SimpleNamespace(name="ChatGPT OAuth", default_model="gpt-test"),
    )
    calls: list[int] = []

    def _provider(job):
        calls.append(job.id)
        return f"요약 결과 {job.id}"

    monkeypatch.setattr(
        summary_jobs_router, "make_gpt_summary_provider", lambda: _provider,
    )
    return calls


def test_plan_is_idempotent_and_skips_empty(client, fake_provider):
    pid, _ids = _project_with_chapters(client, ["본문 A", "   "])

    first = client.post(f"/api/v1/projects/{pid}/summary-jobs/plan", json={})
    assert first.status_code == 200
    # 빈 회차도 skipped_empty provenance 행으로 영속된다
    assert first.json()["summary"]["created"] == 2

    second = client.post(f"/api/v1/projects/{pid}/summary-jobs/plan", json={})
    assert second.json()["summary"]["created"] == 0
    assert second.json()["summary"]["duplicates"] == 2

    jobs = client.get(f"/api/v1/projects/{pid}/summary-jobs").json()
    statuses = sorted(j["status"] for j in jobs)
    assert statuses == ["planned", "skipped_empty"]


def test_plan_404_for_missing_project(client, fake_provider):
    resp = client.post("/api/v1/projects/999999/summary-jobs/plan", json={})
    assert resp.status_code == 404


def test_run_writes_draft_memory_only(client, fake_provider):
    pid, _ids = _project_with_chapters(client, ["본문 A"])
    client.post(f"/api/v1/projects/{pid}/summary-jobs/plan", json={})

    run = client.post(f"/api/v1/projects/{pid}/summary-jobs/run")
    assert run.status_code == 200
    processed = run.json()["processed"]
    assert len(processed) == 1
    assert processed[0]["status"] == "draft_saved"

    db = _db(client)
    entries = db.scalars(
        select(MemoryEntry).where(MemoryEntry.project_id == pid)
    ).all()
    assert len(entries) == 1
    assert entries[0].visibility == "draft"
    assert entries[0].body.startswith("요약 결과")


def test_run_isolates_provider_error_per_job(client, monkeypatch):
    pid, _ids = _project_with_chapters(client, ["본문 A", "본문 B"])
    monkeypatch.setattr(
        summary_jobs_router.gpt_oauth, "get_provider",
        lambda: SimpleNamespace(name="ChatGPT OAuth", default_model="gpt-test"),
    )
    client.post(f"/api/v1/projects/{pid}/summary-jobs/plan", json={})

    calls = {"n": 0}

    def _flaky(job):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("provider down")
        return "성공 요약"

    monkeypatch.setattr(
        summary_jobs_router, "make_gpt_summary_provider", lambda: _flaky,
    )
    run = client.post(f"/api/v1/projects/{pid}/summary-jobs/run")
    statuses = {j["id"]: j["status"] for j in run.json()["processed"]}
    assert sorted(statuses.values()) == ["draft_saved", "provider_error"]

    failed_id = next(jid for jid, s in statuses.items() if s == "provider_error")
    retry = client.post(f"/api/v1/summary-jobs/{failed_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "planned"


def test_retry_rejects_non_provider_error(client, fake_provider):
    pid, _ids = _project_with_chapters(client, ["본문 A"])
    client.post(f"/api/v1/projects/{pid}/summary-jobs/plan", json={})
    client.post(f"/api/v1/projects/{pid}/summary-jobs/run")

    job = client.get(f"/api/v1/projects/{pid}/summary-jobs").json()[0]
    resp = client.post(f"/api/v1/summary-jobs/{job['id']}/retry")
    assert resp.status_code == 409
