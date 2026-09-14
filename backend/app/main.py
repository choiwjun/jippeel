"""FastAPI 엔트리 (사양 §2.2)."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.database import DATABASE_URL, SessionLocal, init_db
from app.routers import (ai_panel, characters, foreshadows, generation_runs,
                         improvement_rules, lorebook,
                         projects, quality, refine, scenes, system, volumes)
from app.routers.memories import router as memories_router  # pyright: ignore[reportMissingImports]
from app.services.auto_backup import AutoBackupConfig, start_scheduler
from app.services.fts import ensure_fts_index
from app.services.presets import seed_presets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sprint 1: create_all / Sprint 2: FTS5 로어북 인덱스 부트스트랩
    # (Alembic 경유 생성 시에도 초기 마이그레이션이 동일 구조를 보장)
    init_db()
    session = SessionLocal()
    try:
        ensure_fts_index(session)
        seed_presets(session)  # 기본 프롬프트 프리셋 — 비어 있을 때만
        session.commit()
    finally:
        session.close()

    # O02 — opt-in 자동 주기 백업(JIPPEEL_AUTOBACKUP_INTERVAL_MIN 설정 시에만)
    stop_autobackup = None
    autobackup_cfg = AutoBackupConfig.from_env()
    if autobackup_cfg.enabled:
        from app.database import _sqlite_file_from_url

        source_db = _sqlite_file_from_url(DATABASE_URL)
        if source_db is not None:
            stop_autobackup = start_scheduler(autobackup_cfg, source_db)

    yield

    if stop_autobackup is not None:
        stop_autobackup()


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
app.include_router(memories_router, prefix="/api/v1")
app.include_router(ai_panel.router, prefix="/api/v1")
app.include_router(generation_runs.router, prefix="/api/v1")
app.include_router(improvement_rules.router, prefix="/api/v1")
app.include_router(refine.router, prefix="/api/v1")
app.include_router(scenes.router, prefix="/api/v1")
app.include_router(foreshadows.router, prefix="/api/v1")
app.include_router(volumes.router, prefix="/api/v1")
app.include_router(quality.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------- 운영 모드 정적 서빙 (A-040, 기술설계 §4.2 변경 3) ----------
# frontend/dist가 있으면 uvicorn 단일 프로세스가 API + 프론트를 함께 서빙한다.
# dist는 프론트 빌드 산출물(npm run build)이며, dev 모드(vite :5173)에서는 미마운트로
# CORS 프록시 동작에 영향을 주지 않는다. 마운트는 API 라우터 등록 이후라 /api·/health 우선.
class _SPAStaticFiles(StaticFiles):
    """SPA fallback — BrowserRouter 클라이언트 경로(/settings, /projects/1/write 등)의
    직접 접근·새로고침이 파일에 대응되지 않아 404가 되므로 index.html로 돌린다.
    /api·/health 아래의 404는 API 계약이므로 JSON 404를 그대로 유지한다."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # Windows StaticFiles는 path를 os.sep(\)로 정규화해 전달한다 — 비교 전 /로 환원
            norm = path.replace("\\", "/")
            if exc.status_code == 404 and not norm.startswith(("api/", "health")):
                return await super().get_response("index.html", scope)
            raise


_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST_DIR.is_dir():
    app.mount("/", _SPAStaticFiles(directory=_DIST_DIR, html=True), name="frontend")
