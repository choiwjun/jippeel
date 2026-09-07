"""Manuscript preservation API regressions.

These tests lock the approved revision/snapshot contract from
``docs/superpowers/specs/2026-09-07-manuscript-preservation.md``.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services import humanize


def _project(client, title="safe"):
    return client.post("/api/v1/projects", json={"title": title}).json()


def _chapter(client, project_id, title="one"):
    return client.post(f"/api/v1/projects/{project_id}/chapters", json={"title": title}).json()


def _put(client, chapter_id, content_md, expected_revision):
    return client.put(
        f"/api/v1/chapters/{chapter_id}/content",
        json={"content_md": content_md, "expected_revision": expected_revision},
    )


def _post(client, chapter_id, content_md, expected_revision):
    return client.post(
        f"/api/v1/chapters/{chapter_id}/content",
        json={"content_md": content_md, "expected_revision": expected_revision},
    )


def test_stale_write_preserves_manuscript_and_history(client):
    project = client.post('/api/v1/projects', json={'title': 'safe'}).json()
    chapter = client.post(f"/api/v1/projects/{project['id']}/chapters", json={'title': 'one'}).json()
    cid = chapter['id']
    first = client.put(f'/api/v1/chapters/{cid}/content', json={'content_md': 'newest', 'expected_revision': 0})
    assert first.status_code == 200
    assert first.json()['revision'] == 1
    stale = client.put(f'/api/v1/chapters/{cid}/content', json={'content_md': 'old', 'expected_revision': 0})
    assert stale.status_code == 409
    assert client.get(f'/api/v1/chapters/{cid}').json()['content_md'] == 'newest'
    snapshots = client.get(f'/api/v1/chapters/{cid}/snapshots').json()
    assert len(snapshots) == 1
    old = client.get(f"/api/v1/chapters/{cid}/snapshots/{snapshots[0]['id']}").json()
    assert old['content_md'] == ''


def test_revision_is_returned_and_required_on_content_routes(client):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]

    created = client.get(f"/api/v1/chapters/{cid}").json()
    listed = client.get(f"/api/v1/projects/{pid}/chapters").json()[0]
    assert created["revision"] == 0
    assert listed["revision"] == 0

    assert client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "missing"}).status_code == 422
    assert client.post(f"/api/v1/chapters/{cid}/content", json={"content_md": "missing"}).status_code == 422


def test_post_alias_noop_and_conflict_shape(client):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]

    first = _post(client, cid, "same", 0)
    assert first.status_code == 200
    assert first.json()["revision"] == 1

    noop = _put(client, cid, "same", 1)
    assert noop.status_code == 200
    assert noop.json()["revision"] == 1
    assert client.get(f"/api/v1/chapters/{cid}/snapshots").json()[0]["revision"] == 0
    assert len(client.get(f"/api/v1/chapters/{cid}/snapshots").json()) == 1

    stale_same_payload = _put(client, cid, "same", 0)
    assert stale_same_payload.status_code == 409
    assert stale_same_payload.json()["detail"] == {
        "code": "revision_conflict",
        "message": "원고가 다른 곳에서 먼저 저장되었습니다. 최신 원고를 확인한 뒤 다시 시도하세요.",
        "current_revision": 1,
    }


def test_concurrent_same_revision_write_has_one_winner(client):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]

    def save(text):
        return _put(client, cid, text, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["winner-a", "winner-b"]))

    statuses = sorted(resp.status_code for resp in results)
    assert statuses == [200, 409]
    winner = next(resp.json()["content_md"] for resp in results if resp.status_code == 200)
    loser = next(resp for resp in results if resp.status_code == 409)
    assert loser.json()["detail"]["current_revision"] == 1
    current = client.get(f"/api/v1/chapters/{cid}").json()
    assert current["content_md"] == winner
    assert current["revision"] == 1
    assert len(client.get(f"/api/v1/chapters/{cid}/snapshots").json()) == 1


def test_snapshot_restore_is_same_chapter_only_and_reversible(client):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    other_cid = _chapter(client, pid, title="two")["id"]

    assert _put(client, cid, "first", 0).json()["revision"] == 1
    assert _put(client, cid, "second", 1).json()["revision"] == 2
    first_snapshot = client.get(f"/api/v1/chapters/{cid}/snapshots").json()[-1]

    rejected = client.post(
        f"/api/v1/chapters/{other_cid}/restore",
        json={"snapshot_id": first_snapshot["id"], "expected_revision": 0},
    )
    assert rejected.status_code == 422

    restored = client.post(
        f"/api/v1/chapters/{cid}/restore",
        json={"snapshot_id": first_snapshot["id"], "expected_revision": 2},
    )
    assert restored.status_code == 200
    assert restored.json()["content_md"] == ""
    assert restored.json()["revision"] == 3

    restore_snapshot = client.get(f"/api/v1/chapters/{cid}/snapshots").json()[0]
    undo = client.post(
        f"/api/v1/chapters/{cid}/restore",
        json={"snapshot_id": restore_snapshot["id"], "expected_revision": 3},
    )
    assert undo.status_code == 200
    assert undo.json()["content_md"] == "second"
    assert undo.json()["revision"] == 4


def test_scene_merge_requires_revision_and_preserves_on_empty_or_stale(client):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    _put(client, cid, "manual", 0)

    missing = client.put(f"/api/v1/chapters/{cid}/content_from_scenes", json={})
    assert missing.status_code == 422

    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "blank", "content_md": "   "})
    empty = client.put(
        f"/api/v1/chapters/{cid}/content_from_scenes",
        json={"expected_revision": 1},
    )
    assert empty.status_code == 422
    assert client.get(f"/api/v1/chapters/{cid}").json()["content_md"] == "manual"

    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "one", "sort_order": 0, "content_md": "scene a"})
    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "two", "sort_order": 1, "content_md": "scene b"})
    stale = client.put(
        f"/api/v1/chapters/{cid}/content_from_scenes",
        json={"expected_revision": 0},
    )
    assert stale.status_code == 409
    merged = client.put(
        f"/api/v1/chapters/{cid}/content_from_scenes",
        json={"expected_revision": 1},
    )
    assert merged.status_code == 200
    assert merged.json()["content_md"] == "scene a\n\nscene b"
    assert merged.json()["revision"] == 2


@pytest.fixture()
def mock_humanize(monkeypatch):
    def fake_run_pipeline(content_md, force_route=None):
        return {
            "route_hint": force_route or "standard",
            "changed_ratio": 0.01,
            "gate": "pass",
            "status": "ok",
            "spans": [],
            "report": {"metrics": {}, "gates": {}},
            "refined": "refined text",
            "work_dir": "unused",
        }

    monkeypatch.setattr(humanize, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(humanize, "cleanup_workdir", lambda work_dir: None)


def test_refine_accept_uses_captured_base_revision_and_blocks_stale(client, mock_humanize):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    _put(client, cid, "base text", 0)

    run = client.post("/api/v1/refine", json={"chapter_id": cid, "expected_revision": 1}).json()
    assert client.get(f"/api/v1/refine/runs/{run['run_id']}").json()["base_revision"] == 1

    _put(client, cid, "newer human edit", 1)
    stale_accept = client.post(f"/api/v1/refine/runs/{run['run_id']}/accept")
    assert stale_accept.status_code == 409
    assert stale_accept.json()["detail"]["code"] == "revision_conflict"
    after = client.get(f"/api/v1/chapters/{cid}").json()
    assert after["content_md"] == "newer human edit"
    assert after["revision"] == 2
    assert client.get(f"/api/v1/refine/runs/{run['run_id']}").json()["accepted"] is False


def test_refine_accept_returns_chapter_detail(client, mock_humanize):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    _put(client, cid, "base text", 0)

    run = client.post("/api/v1/refine", json={"chapter_id": cid, "expected_revision": 1}).json()
    accepted = client.post(f"/api/v1/refine/runs/{run['run_id']}/accept")
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["id"] == cid
    assert body["content_md"] == "refined text"
    assert body["revision"] == 2
    assert client.get(f"/api/v1/refine/runs/{run['run_id']}").json()["accepted"] is True


def test_refine_requires_expected_revision_and_stale_skips_pipeline(client, monkeypatch):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    _put(client, cid, "base text", 0)
    _put(client, cid, "newer text", 1)

    calls = {"count": 0}

    def fail_if_called(content_md, force_route=None):
        calls["count"] += 1
        raise AssertionError("pipeline should not run for stale refine")

    monkeypatch.setattr(humanize, "run_pipeline", fail_if_called)

    missing = client.post("/api/v1/refine", json={"chapter_id": cid})
    assert missing.status_code == 422

    stale = client.post("/api/v1/refine", json={"chapter_id": cid, "expected_revision": 1})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "revision_conflict"
    assert stale.json()["detail"]["current_revision"] == 2
    assert calls["count"] == 0


def test_snapshot_failure_rolls_back_manuscript_update(tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app.database import Base, create_db_engine
    from app.models import Chapter, Project
    from app.services import manuscripts

    engine = create_db_engine(f"sqlite:///{(tmp_path / 'rollback.db').as_posix()}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db = SessionLocal()
    try:
        project = Project(title="rollback")
        db.add(project)
        db.flush()
        chapter = Chapter(project_id=project.id, title="one", content_md="old", revision=0)
        db.add(chapter)
        db.commit()
        cid = chapter.id

        original_flush = db.flush

        def fail_after_update(*args, **kwargs):
            if db.new:
                raise RuntimeError("snapshot insert failed")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db, "flush", fail_after_update)
        with pytest.raises(RuntimeError, match="snapshot insert failed"):
            manuscripts.replace_manuscript(db, cid, "new", 0, reason="autosave")
        db.rollback()
    finally:
        db.close()

    verify = SessionLocal()
    try:
        persisted = verify.get(Chapter, cid)
        assert persisted.content_md == "old"
        assert persisted.revision == 0
        assert manuscripts.list_snapshots(verify, cid) == []
    finally:
        verify.close()
        engine.dispose()



def test_delete_chapter_cascades_snapshots(client):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    _put(client, cid, "first", 0)
    snapshots = client.get(f"/api/v1/chapters/{cid}/snapshots").json()
    assert len(snapshots) == 1

    assert client.delete(f"/api/v1/chapters/{cid}").status_code == 204
    assert client.get(f"/api/v1/chapters/{cid}").status_code == 404
    assert client.get(f"/api/v1/chapters/{cid}/snapshots/{snapshots[0]['id']}").status_code == 404



def test_noop_racing_changing_writer_reports_fresh_revision(tmp_path):
    from sqlalchemy.orm import sessionmaker

    from app.database import Base, create_db_engine
    from app.models import Chapter, Project
    from app.services import manuscripts

    engine = create_db_engine(f"sqlite:///{(tmp_path / 'noop-race.db').as_posix()}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    setup = SessionLocal()
    try:
        project = Project(title="race")
        setup.add(project)
        setup.flush()
        chapter = Chapter(project_id=project.id, title="one", content_md="same", revision=1)
        setup.add(chapter)
        setup.commit()
        cid = chapter.id
    finally:
        setup.close()

    stale_noop = SessionLocal()
    winner = SessionLocal()
    try:
        cached = stale_noop.get(Chapter, cid)
        assert cached.revision == 1
        assert cached.content_md == "same"

        changed = manuscripts.replace_manuscript(winner, cid, "newest", 1, reason="autosave")
        winner.commit()
        assert changed.revision == 2

        with pytest.raises(manuscripts.RevisionConflict) as exc_info:
            manuscripts.replace_manuscript(stale_noop, cid, "same", 1, reason="autosave")
        assert exc_info.value.current_revision == 2
        stale_noop.rollback()
    finally:
        stale_noop.close()
        winner.close()

    verify = SessionLocal()
    try:
        current = verify.get(Chapter, cid)
        assert current.content_md == "newest"
        assert current.revision == 2
        snapshots = manuscripts.list_snapshots(verify, cid)
        assert [(s.revision, s.content_md, s.reason) for s in snapshots] == [(1, "same", "autosave")]
    finally:
        verify.close()
        engine.dispose()


def test_duplicate_snapshot_integrity_rollback_reports_real_current_revision(tmp_path):
    from sqlalchemy.orm import sessionmaker

    from app.database import Base, create_db_engine
    from app.models import Chapter, ChapterSnapshot, Project
    from app.services import manuscripts

    engine = create_db_engine(f"sqlite:///{(tmp_path / 'snapshot-dupe.db').as_posix()}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db = SessionLocal()
    try:
        project = Project(title="dupe")
        db.add(project)
        db.flush()
        chapter = Chapter(project_id=project.id, title="one", content_md="old", revision=0)
        db.add(chapter)
        db.flush()
        db.add(ChapterSnapshot(
            chapter_id=chapter.id,
            revision=0,
            content_md="pre-existing duplicate",
            reason="autosave",
        ))
        db.commit()
        cid = chapter.id

        with pytest.raises(manuscripts.RevisionConflict) as exc_info:
            manuscripts.replace_manuscript(db, cid, "new", 0, reason="autosave")
        assert exc_info.value.current_revision == 0
        db.rollback()
    finally:
        db.close()

    verify = SessionLocal()
    try:
        current = verify.get(Chapter, cid)
        assert current.content_md == "old"
        assert current.revision == 0
        snapshots = manuscripts.list_snapshots(verify, cid)
        assert [(s.revision, s.content_md, s.reason) for s in snapshots] == [
            (0, "pre-existing duplicate", "autosave")
        ]
    finally:
        verify.close()
        engine.dispose()


def test_restore_requires_revision_stale_conflicts_and_keeps_reason(client):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    assert _put(client, cid, "first", 0).json()["revision"] == 1
    assert _put(client, cid, "second", 1).json()["revision"] == 2
    snapshots = client.get(f"/api/v1/chapters/{cid}/snapshots").json()
    snapshot_id = snapshots[-1]["id"]

    missing = client.post(f"/api/v1/chapters/{cid}/restore", json={"snapshot_id": snapshot_id})
    assert missing.status_code == 422

    stale = client.post(
        f"/api/v1/chapters/{cid}/restore",
        json={"snapshot_id": snapshot_id, "expected_revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_revision"] == 2
    assert client.get(f"/api/v1/chapters/{cid}").json()["content_md"] == "second"

    restored = client.post(
        f"/api/v1/chapters/{cid}/restore",
        json={"snapshot_id": snapshot_id, "expected_revision": 2},
    )
    assert restored.status_code == 200
    assert restored.json()["revision"] == 3
    reasons = [s["reason"] for s in client.get(f"/api/v1/chapters/{cid}/snapshots").json()]
    assert reasons[0] == "restore"
    assert "autosave" in reasons


def test_snapshot_reason_values_for_refine_and_scene_merge(client, mock_humanize):
    pid = _project(client)["id"]
    cid = _chapter(client, pid)["id"]
    _put(client, cid, "base text", 0)

    run = client.post("/api/v1/refine", json={"chapter_id": cid, "expected_revision": 1}).json()
    accepted = client.post(f"/api/v1/refine/runs/{run['run_id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["revision"] == 2

    client.post(f"/api/v1/chapters/{cid}/scenes", json={"title": "one", "sort_order": 0, "content_md": "scene body"})
    merged = client.put(
        f"/api/v1/chapters/{cid}/content_from_scenes",
        json={"expected_revision": 2},
    )
    assert merged.status_code == 200

    reasons = [s["reason"] for s in client.get(f"/api/v1/chapters/{cid}/snapshots").json()]
    assert reasons[:3] == ["scene_merge", "refine", "autosave"]
