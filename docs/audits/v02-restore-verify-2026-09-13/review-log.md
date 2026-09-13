# V02 독립 검토 기록 — 복원 실패 시나리오 보강

- 슬라이스: V02 (backend service layer only)
- 검토일: 2026-09-13
- 검토자: 독립 subagent 1건 (백엔드·계약 설계). 프론트 산출물 없음 — UI 변경 없는 서비스 계층.
- 판정: **PASS_WITH_NOTES**

## 검토자 확인 요약

- 설계 수용 항목 전부 구현·녹색: checksum 변경·파일 누락·잘못된 schema head·disk-full 근사·integrity·FK 위반·다중 실패 수집·읽기 전용 검증.
- 9개 `RestoreErrorCode` 계약 문자열 일치, 검사 순서·조기 반환·`query_only` 적용·scope 경계(stdlib만, TEMP, no keyring/network/subprocess/provider/endpoint) 준수 확인.
- wrong-key는 G03 위임으로 문서화됨 — 범위 일치.

## 지적 처리표

| # | 심각도 | 지적 | 처리 |
|---|--------|------|------|
| 1 | MED | malformed manifest 비정상 종료 (UnicodeDecodeError·스칼라 JSON·`files:null`·name 누락/비문자열) | **수정** — `UnicodeDecodeError` 추가 포착, manifest dict/files list/항목 타입 전수 검증 → `MANIFEST_INVALID`. 테스트 5 variant 추가 |
| 2 | MED | `files` 비-list 시 0개 검사 + `ok=True` 위음성·sha256 누락 항목의 CHECKSUM_MISMATCH 오분류 | **수정** — 비-list·항목 결손을 `MANIFEST_INVALID` 조기 반환으로 분류 |
| 3 | MED | manifest `name` 경로 탈출 (`..`/절대경로) — TEMP 경계 밖 읽기 oracle | **수정** — `rel.is_absolute() · ".." in parts · rel.name != name` 거부 → `MANIFEST_INVALID`. 회귀 테스트 추가 |
| 4 | MED | dest 쓰기 실패(disk-full·권한·열기) `NOT_SQLITE` 오분류 — spec `BACKUP_WRITE_FAILED` 계약 위반 | **수정** — `SQLITE_FULL·IOERR·CANTOPEN·READONLY` → `BACKUP_WRITE_FAILED`, 그 외 `NOT_SQLITE` |
| 5 | MED | chmod 기반 쓰기 실패 주입 비이식성(root 우회·Windows 무효) | **수정** — 결정적 경로 추가: 대상 상위가 존재하는 파일 → `FileExistsError` → `BACKUP_WRITE_FAILED`. chmod 경로는 보조로 유지 |
| 6 | MED | 테스트 갭 — 비-jippeel source(no alembic_version)·malformed manifest·선언 파일 읽기 불가 | **수정** — `test_create_backup_rejects_non_jippeel_source` + malformed 5 variant + OSError → `FILE_MISSING` 매핑 추가 |
| 7 | LOW | 검증 probe 실패 시 conn 미해제 | **수정** — except에서 `conn.close()` |
| 8 | LOW | missing-source 테스트가 code 미단정 | **수정** — `.code == NOT_SQLITE` 단정 추가 |
| 9 | LOW | `PRAGMA integrity_check` 2회 실행 | **수정** — probe 결과 재사용 |
| 10 | NOTE | WAL mode 임시 -shm/-wal 파일 (실제 jippeel.db는 WAL) | **수용** — fixture는 delete-mode; `query_only`로 내용 보호 유지. `immutable=1` URI는 격리 가드가 URI 연결을 거부해 사용 불가 — 제약 기록 |
| 11 | NOTE | 미검증 manifest 필드(size_bytes·format_version·미선언 추가 파일) | **수용** — sha256이 size를 포함, format_version은 향후 버전 게이트에서 사용, 추가 파일 무시는 의도된 범위 |
| 12 | NOTE | 원장 V02 행 미갱신·감사 인덱스 | **수정** — 수용 시 원장·인덱스 갱신 (이 문서와 동일 커밋 범위) |
| 13 | NOTE | create_backup 부분 실패 시 manifest 없는 잔여 디렉터리 → MANIFEST_MISSING | **수용** — 일관된 보고 동작, 문서화 |

## 재검증

- focused: `tests/test_restore_verify.py` **15 passed**
- 전체 회귀: **656 passed / 1 skipped / violations 0** (외부 metrics skip은 V04 잔여로 분리 유지)
- 증거: `backend-focused.txt`·`backend-full.txt`·`source-hashes.txt` 갱신

## 판정 근거

차단 결함 없음. MED 5건·LOW 3건 전부 수정 후 재검증 녹색. NOTE 4건은 범위·제약 근거와 함께 명시 수용.
