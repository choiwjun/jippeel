"""TC-037 실측 스크립트 — db-info 경로 조회 → 3파일 복사 → 데이터 동일성 검증."""
import json
import shutil
import sqlite3
import urllib.request
from pathlib import Path

info = json.loads(urllib.request.urlopen("http://localhost:8000/api/v1/system/db-info").read())
DB = Path(info["path"])
print("db-info 경로:", DB, "| 존재:", info["exists"], f"| {info['size_bytes']:,} bytes")

BAK = DB.parent / "jippeel.qa-backup-test"
shutil.rmtree(BAK, ignore_errors=True)
BAK.mkdir()
copied = [f.name for f in (DB, Path(str(DB) + "-wal"), Path(str(DB) + "-shm")) if f.exists() and (shutil.copy2(f, BAK / f.name) or True)]
print("복사된 파일:", copied)

src = sqlite3.connect(DB)
dst = sqlite3.connect(BAK / DB.name)
tables = ["projects", "chapters", "characters", "lore_entries", "ai_endpoints", "prompt_presets"]
ok = all(
    src.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    == dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    for t in tables
)
print("복사본 데이터 동일성:", "PASS" if ok else "FAIL")
shutil.rmtree(BAK)
