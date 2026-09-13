"""O03 — 집필 활동 캘린더 엔드포인트 테스트."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine, get_db
from app.main import app
from app.services.presets_seed import ensure_builtin_presets


@pytest.fixture()
def client_db(tmp_path):
    """conftest의 client와 동일한 격리 DB이되 세션 팩토리를 함께 노출한다."""
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    seed = TestingSessionLocal()
    try:
        ensure_builtin_presets(seed)
        seed.commit()
    finally:
        seed.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, TestingSessionLocal
    app.dependency_overrides.clear()
    engine.dispose()


def _create_project(client, title="활동 테스트") -> int:
    res = client.post("/api/v1/projects", json={"title": title})
    assert res.status_code == 201
    return res.json()["id"]


def _mk_chapter(client, pid: int, title: str, sort: float = 0.0) -> int:
    res = client.post(
        f"/api/v1/projects/{pid}/chapters",
        json={"title": title, "sort_order": sort},
    )
    assert res.status_code == 201
    return res.json()["id"]


def _set_updated(session_factory, cid: int, when: datetime) -> None:
    from app.models import Chapter

    db = session_factory()
    try:
        ch = db.get(Chapter, cid)
        ch.updated_at = when
        db.commit()
    finally:
        db.close()


class TestWritingActivity:
    def test_buckets_group_by_updated_date(self, client_db):
        client, session_factory = client_db
        pid = _create_project(client)
        today = datetime.now(timezone.utc).replace(hour=10, minute=0)
        yesterday = today - timedelta(days=1)
        c1 = _mk_chapter(client, pid, "1화", 1.0)
        c2 = _mk_chapter(client, pid, "2화", 2.0)
        c3 = _mk_chapter(client, pid, "3화", 3.0)
        _set_updated(session_factory, c1, today)
        _set_updated(session_factory, c2, today.replace(hour=20))
        _set_updated(session_factory, c3, yesterday)

        res = client.get(f"/api/v1/projects/{pid}/writing-activity?days=7")
        assert res.status_code == 200
        body = res.json()
        assert body["project_id"] == pid
        buckets = {b["date"]: b for b in body["buckets"]}
        assert len(buckets) == 2
        today_key = today.date().isoformat()
        assert buckets[today_key]["chapters"] == 2
        assert body["totals"]["active_days"] == 2
        assert body["totals"]["chapters"] == 3

    def test_empty_project(self, client):
        pid = _create_project(client)
        res = client.get(f"/api/v1/projects/{pid}/writing-activity")
        assert res.status_code == 200
        body = res.json()
        assert body["buckets"] == []
        assert body["totals"] == {"active_days": 0, "chapters": 0, "chars": 0}

    def test_days_bounds(self, client):
        pid = _create_project(client)
        assert (
            client.get(f"/api/v1/projects/{pid}/writing-activity?days=0").status_code
            == 422
        )
        assert (
            client.get(
                f"/api/v1/projects/{pid}/writing-activity?days=366"
            ).status_code
            == 422
        )
        assert (
            client.get(f"/api/v1/projects/{pid}/writing-activity?days=365").status_code
            == 200
        )

    def test_old_activity_outside_window(self, client_db):
        client, session_factory = client_db
        pid = _create_project(client)
        cid = _mk_chapter(client, pid, "오래된 화")
        _set_updated(
            session_factory, cid, datetime.now(timezone.utc) - timedelta(days=100)
        )
        res = client.get(f"/api/v1/projects/{pid}/writing-activity?days=30")
        assert res.json()["buckets"] == []
        res = client.get(f"/api/v1/projects/{pid}/writing-activity?days=120")
        assert len(res.json()["buckets"]) == 1

    def test_project_isolation_and_404(self, client):
        pid = _create_project(client)
        other = _create_project(client)
        _mk_chapter(client, other, "타작품")
        res = client.get(f"/api/v1/projects/{pid}/writing-activity")
        assert res.json()["totals"]["chapters"] == 0
        assert (
            client.get("/api/v1/projects/999999/writing-activity").status_code == 404
        )
