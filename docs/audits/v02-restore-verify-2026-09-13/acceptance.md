# V02 수용 — 복원 실패 시나리오 보강

- 수용일: 2026-09-13
- 사양: [V02 실패 주입 사양](../../superpowers/plans/2026-09-13-v02-restore-failure-injection.md)
- 상태: **수용** (uncommitted)

## 수용 범위

`backend/app/services/restore_verify.py` — 합성 백업 생성(`create_backup`)과 읽기 전용 검증(`verify_backup_dir`). stdlib만 사용, TEMP 경계 내 동작, 기존 C11 임시 복원 검증의 **실패 주입 보강**이며 실제 운영 DB·복원 실행과 무관하다.

실패 분류 계약(9 코드):

| 코드 | 발생 조건 |
|------|-----------|
| `MANIFEST_MISSING` | manifest.json 부재 |
| `MANIFEST_INVALID` | 파싱 불가·필수키 결손·files 형식 위반·항목 name/sha256 결손·경로 탈출 이름 |
| `FILE_MISSING` | 선언 파일 부재 또는 읽기 불가 |
| `CHECKSUM_MISMATCH` | 선언 sha256 불일치 |
| `NOT_SQLITE` | 원본/대상이 SQLite가 아니거나 alembic_version 없음 |
| `SCHEMA_HEAD_MISMATCH` | alembic_version이 기대·manifest head와 불일치 |
| `INTEGRITY_FAILED` | SQLite 손상(integrity_check 비-ok·probe 실패) |
| `FK_VIOLATION` | `PRAGMA foreign_key_check` 위반 행 존재 |
| `BACKUP_WRITE_FAILED` | 대상 디렉터리 생성·대상 DB 쓰기 실패 |

## 검증 근거

- focused: `tests/test_restore_verify.py` **15 passed** — 성공 경로 + 실패 9종 + 다중 실패 수집 + 읽기 전용 보존 + malformed manifest 5 variant + 경로 탈출 거부 + 비-jippeel 원본 거부
- 전체 회귀: **656 passed / 1 skipped** — skip은 외부 metrics 비교(V04 잔여)로 분리 유지
- 격리: violations 0 · subprocess 0 · fake_keyring 7 (전체 회귀 집계)
- RED 증거: `red-log.txt` (구현 전 실패 확인)
- 독립 검토: PASS_WITH_NOTES — MED 5·LOW 3 수정, NOTE 4 명시 수용 ([review-log.md](review-log.md))

## 비수용(명시 제외)

- 운영 DB·실제 백업 대상·실제 credential — G01/G03 승인 게이트.
- wrong-key 복원 검증 — G03 범위(모듈 docstring 명시).
- 복원 실행·교체·롤백 절차 — 본 슬라이스는 검증기만.
- WAL-mode 임시 side-file — fixture delete-mode 환경 제약으로 미재현, `query_only` 보호는 유지.

## 잔여

- 실제 DB 대상 복원 절차 검증은 G01/G03 승인 후 별도 슬라이스.
- `format_version` 값 검증은 향후 백업 포맷 버전 도입 시.
