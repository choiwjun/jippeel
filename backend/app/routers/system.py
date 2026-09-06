"""시스템 정보 라우터 — A-039 백업 안내(Q5 결정안: 파일 단위 수동 복사)용 DB 위치 제공.

S7 고급 탭에서 백업·복원 가이드와 함께 표시할 DB 파일 경로를 반환한다.
REST 백업 엔드포인트는 만들지 않기로 한 결정(기술설계 A-039 — WAL 핫카피
정합 리스크 회피)을 유지하며, 경로 안내만 서버에서 제공한다.
"""
from pathlib import Path

from fastapi import APIRouter

from app.database import engine

router = APIRouter()


@router.get("/system/db-info")
def db_info() -> dict:
    """SQLite 데이터베이스 파일 경로·크기·동반 파일(-wal/-shm) 경로 반환."""
    raw = engine.url.database or "jippeel.db"
    path = Path(raw).resolve()
    companions = [str(path.with_name(path.name + ext)) for ext in ("-wal", "-shm")]
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "companion_files": companions,
    }
