# 백업·복원 dry-run 결과

- 실행일: 2026-09-10
- 범위: 임시 SQLite만 사용한 backup/restore 검증
- 운영 DB·기존 서비스·keyring·실제 API key는 사용하지 않음

## 실행

1. `/tmp/jippeel-backup-source.db`를 Alembic head `0a1b2c3d4e5f`까지 생성
2. 임시 project/chapter 한 건을 넣고 WAL checkpoint 수행
3. Python `sqlite3.Connection.backup()`으로 `/tmp/jippeel-backup-copy.db` 생성
4. 복원본에서 integrity, foreign key, Alembic head, 논리 row를 확인

## 결과

```json
{
  "integrity_check": "ok",
  "foreign_key_errors": [],
  "alembic_head": "0a1b2c3d4e5f",
  "counts": {"projects": 1, "chapters": 1, "chapter_snapshots": 0},
  "restored_row": ["dry-run 회차", "백업 복원 검증 원문", 0]
}
```

원본/복원 SQLite 파일의 raw SHA-256은 각각 `3ab1245a...a10`과 `4e5dd8a9...a64`로 달랐다. SQLite backup은 파일 페이지/WAL 배치가 달라질 수 있으므로 raw file hash를 동일성 기준으로 쓰지 않는다. 실제 acceptance에서는 manifest에 각 파일 hash를 기록하고, schema head·row count·정본 content hash·revision·integrity 결과를 논리 기준으로 비교한다.

## 미검증 범위

- 운영 DB backup 또는 restore
- Windows DPAPI/keyring 복구
- 암호화된 API key 복호화
- 서비스 중지/교체/rollback
- 실제 provider 호출
