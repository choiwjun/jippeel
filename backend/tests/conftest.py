"""pytest fixtures — 임시 SQLite 파일 기반 통합 테스트 환경."""
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote


def _mark_temp_lifespan_db() -> None:
    url = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(url)
    if parsed.scheme == "sqlite" and parsed.path:
        try:
            db_path = Path(unquote(parsed.path[1:] if len(parsed.path) > 3 and parsed.path[0] == "/" and parsed.path[2] == ":" else parsed.path)).resolve()
            db_path.relative_to(Path(tempfile.gettempdir()).resolve())
        except ValueError:
            return
        os.environ["JIPPEEL_ALLOW_TEMP_CREATE_ALL"] = "1"


_mark_temp_lifespan_db()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine, get_db
from app.main import app
from app.services.presets_seed import ensure_builtin_presets


@pytest.fixture()
def client(tmp_path):
    """테스트마다 임시 디렉터리에 SQLite 파일 DB를 만들고 get_db를 교체한다."""
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    # lifespan이 프로덕션 DB에 하는 것과 동일한 시드를 테스트 DB에도 적용
    seed_session = TestingSessionLocal()
    try:
        ensure_builtin_presets(seed_session)
        seed_session.commit()
    finally:
        seed_session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
