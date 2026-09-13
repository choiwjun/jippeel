# V02 좁은 사양 — 복원 검증기 + 실패 주입 테스트

- 작성일: 2026-09-13
- 슬라이스: V02(복원 실패 시나리오 보강) — 원장 "manifest 불일치·파일 누락·잘못된 schema·disk-full 등 미수행 failure injection"
- 근거: [백업·복원 설계](../../audits/backup-restore-design-2026-09-10.md)의 restore dry-run 절차 §1–§5·실패 복구 단락, [dry-run 결과](../../audits/backup-restore-dry-run-2026-09-10.md)의 미검증 범위
- 경계: **합성·임시 경로만**. 운영 DB·keyring·credential·실제 provider 접근 없음. wrong-key 검증은 G03 범위로 분리 유지.

## 1. 목표·비목표

### 목표
- dry-run 절차를 코드로 고정한 복원 검증기 `verify_backup_dir()` — 각 검사가 **서로 다른 실패 코드**를 반환.
- 백업 생성기 `create_backup()` — sqlite3 backup API + manifest 기록(dry-run이 증명한 절차의 코드화).
- 합성 failure-injection 테스트: manifest 불일치·누락, 파일 누락, checksum 변경, 손상 파일, 잘못된 schema head, FK 위반, 쓰기 불가 대상(disk-full 근사).

### 비목표
- 실제 백업 스케줄링·운영 DB 접근·서비스 교체/rollback 자동화
- key 복호화·wrong-key 검증(G03), provider 호출
- HTTP 엔드포인트·프론트 UI

## 2. 백업 포맷 (설계 문서와 동일)

```text
backup-*/
  manifest.json       # format_version, created_at, source_path, alembic_head,
                      # files: [{name, size_bytes, sha256}]
  database.sqlite3    # sqlite3 backup API로 만든 일관 사본
```

- manifest에는 시크릿·키 물질을 기록하지 않는다.

## 3. 서비스 계약 — `app/services/restore_verify.py`

```python
class RestoreErrorCode(StrEnum):
    MANIFEST_MISSING = "manifest_missing"
    MANIFEST_INVALID = "manifest_invalid"
    FILE_MISSING = "file_missing"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    NOT_SQLITE = "not_sqlite"
    INTEGRITY_FAILED = "integrity_failed"
    FOREIGN_KEY_FAILED = "foreign_key_failed"
    SCHEMA_HEAD_MISMATCH = "schema_head_mismatch"
    BACKUP_WRITE_FAILED = "backup_write_failed"

def create_backup(source_db: Path, dest_dir: Path) -> Path
def verify_backup_dir(backup_dir: Path, *, expected_alembic_head: str | None = None
                     ) -> VerifyReport  # dataclass {ok: bool, failures: list[Failure]}
```

### create_backup
1. `sqlite3.Connection.backup()`으로 `database.sqlite3` 생성 — WAL 일관 사본.
2. 대상 쓰기 실패(권한·disk-full·경로 부재) → `RestoreVerifyError(BACKUP_WRITE_FAILED)`.
3. manifest 기록 — 파일 sha256·크기·alembic head(원본의 `alembic_version` 조회)를 포함.
4. 원본이 SQLite가 아니거나 읽기 불가 → `RestoreVerifyError(NOT_SQLITE)`.

### verify_backup_dir — 검사 순서와 실패 코드
1. `manifest.json` 없음 → MANIFEST_MISSING; 파싱 불가·필수 필드 누락 → MANIFEST_INVALID.
2. manifest 선언 파일이 디스크에 없음 → FILE_MISSING (파일별).
3. 파일 sha256 불일치 → CHECKSUM_MISMATCH (파일별).
4. DB 파일이 SQLite가 아님 → NOT_SQLITE.
5. `PRAGMA integrity_check` != 'ok' → INTEGRITY_FAILED.
6. `PRAGMA foreign_key_check` 행 존재 → FOREIGN_KEY_FAILED.
7. `alembic_version` ≠ manifest.alembic_head → SCHEMA_HEAD_MISMATCH;
   `expected_alembic_head` 전달 시 둘 다 맞아야 함.
- 실패는 모두 수집해 반환(첫 실패에서 멈추지 않음). DB를 열 수 없으면(4번) 이후 DB 검사는 건너뛴다.
- 검증은 읽기 전용 — 백업·원본을 변경하지 않는다.

## 4. 검증 — `backend/tests/test_restore_verify.py`
- 합성 TEMP SQLite만. fixture: 프로젝트·회차 행 + `alembic_version` 테이블을 가진 소스 DB.
- happy path: create_backup → verify ok, manifest 해시 일치.
- 주입: manifest 삭제/손상/필드 누락, db 파일 삭제, db 파일 1바이트 변경(해시 불일치), 비-SQLite 파일, integrity 손상(페이지 훼손), FK orphan 행, alembic head 불일치(manifest/기대값 각각), dest 쓰기 불가.
- 각 주입이 **정확한 실패 코드**를 반환하는지, 복수 실패가 함께 보고되는지, 검증이 백업 파일을 변경하지 않는지(해시 재확인) 단정.
- `run_backend_pytest.py` 전체 회귀.
