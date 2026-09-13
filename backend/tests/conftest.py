"""pytest fixtures — 임시 SQLite 파일 기반 통합 테스트 환경."""
from tests.isolation_guard import require_isolation

# Must execute before importing pytest, SQLAlchemy or any app module.
require_isolation()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine, get_db
from app.database import engine as app_engine
from app.main import app
from app.services.presets_seed import ensure_builtin_presets


@pytest.fixture(autouse=True)
def _dispose_app_engine():
    """lifespan의 모듈 수준 엔진 풀 연결이 GC까지 남아 ResourceWarning을 내지 않게 한다."""
    yield
    app_engine.dispose()


_db_gens = []


@pytest.fixture(autouse=True)
def _close_db_gens():
    """_db()가 연 제너레이터를 매 테스트 종료 시 닫아 세션/연결 누수를 막는다."""
    _db_gens.clear()
    yield
    for gen in _db_gens:
        gen.close()
    _db_gens.clear()


def _db(client):
    """get_db dependency override 제너레이터를 열어 세션을 반환한다. 폐기는 _close_db_gens가 담당."""
    from app.database import get_db
    gen = client.app.dependency_overrides[get_db]()
    _db_gens.append(gen)
    return next(gen)


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
