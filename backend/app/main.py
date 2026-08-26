"""FastAPI 엔트리 (사양 §2.2)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal, init_db
from app.routers import ai_panel, characters, lorebook, projects, refine
from app.services.fts import ensure_fts_index
from app.services.presets_seed import ensure_builtin_presets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sprint 1: create_all / Sprint 2: FTS5 로어북 인덱스 부트스트랩
    # (Alembic 경유 생성 시에도 초기 마이그레이션이 동일 구조를 보장)
    init_db()
    session = SessionLocal()
    try:
        ensure_fts_index(session)
        ensure_builtin_presets(session)  # 빌트인 프롬프트 프리셋 멱등 시드(FR-403)
        session.commit()
    finally:
        session.close()
    yield


app = FastAPI(title="jippeel-dashboard API", version="0.1.0", lifespan=lifespan)

# 프론트 dev 서버(Vite, http://localhost:5173) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/v1")
app.include_router(characters.router, prefix="/api/v1")
app.include_router(lorebook.router, prefix="/api/v1")
app.include_router(ai_panel.router, prefix="/api/v1")
app.include_router(refine.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
