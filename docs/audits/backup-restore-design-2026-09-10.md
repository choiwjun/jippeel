# 백업·복원 설계

- 작성일: 2026-09-10
- 상태: **read-only 설계. 운영 DB와 기존 서비스에 접근하지 않음.**

## 현재 자산과 위험

- 기본 DB는 SQLite이며 WAL, `synchronous=NORMAL`, foreign keys, busy timeout을 사용한다.
- schema head는 Alembic `0a1b2c3d4e5f`로 검증된다.
- 원문은 `chapters`와 `chapter_snapshots`에 있고, chapter revision은 optimistic lock이다.
- API key는 DB에 암호문으로 저장되고, master key는 Windows keyring(DPAPI 우선) 또는 `~/.jippeel/api_key.key` fallback에 있다.
- DB와 master key를 같은 무보호 archive에 넣으면 암호화의 의미가 사라진다.

근거: `backend/app/database.py`, `backend/alembic/versions/0a1b2c3d4e5f_manuscript_preservation.py`, `backend/app/services/crypto.py`, `backend/app/services/manuscripts.py`.

## 백업 포맷

백업은 한 파일에 모든 비밀을 넣지 않고 다음 논리 자산으로 분리한다.

```text
backup-<timestamp>/
  manifest.json
  database.sqlite3
  database.sqlite3.sha256
  schema/alembic-head.txt
  metadata/project-export.json   # 선택적 비밀 제거 metadata
  key-handling.txt               # key ID/source만, key material 금지
```

`manifest.json`에는 format_version, created_at UTC, source DB identity, Alembic head, SQLite page/checkpoint 정보, file size, SHA-256, application commit, redaction policy를 기록한다. API key plaintext, Fernet key, keyring secret, provider response secret은 manifest/log/archive에 기록하지 않는다.

## 일관된 생성

운영 실행 중 임의로 `cp jippeel.db`를 하지 않는다. 승인된 구현은 다음 중 하나를 택해야 한다.

1. 서비스 write quiesce 후 SQLite backup API 또는 안전한 checkpoint와 copy
2. SQLite online backup API로 읽기 일관성 확보
3. WAL/SHM를 포함한 원자적 snapshot 방식

어떤 방식이든 `PRAGMA integrity_check`, source/backup checksum, Alembic head를 함께 기록한다. 이번 단계에서는 어느 방식도 운영 DB에 실행하지 않는다.

## 키 취급과 복원 경계

- Windows DPAPI/keyring 백업은 동일 사용자/기계의 credential 복구 또는 명시적 key escrow 없이는 다른 PC에서 API key를 복호화할 수 없다.
- fallback key file은 DB archive와 별도로 보관한다. 권한 0600 요구와 Windows ACL을 확인한다.
- 복원 대상 PC가 달라지면 먼저 key recovery plan을 승인한다. 새 key를 생성해 기존 ciphertext를 덮어쓰지 않는다.
- 키를 잃은 경우 복원된 원문과 metadata는 살릴 수 있지만 API endpoint secret은 복구 불가로 분리 보고한다.
- provider 호출은 복원 검증의 일부가 아니다. 테스트용 endpoint나 API key를 실제 provider에 전송하지 않는다.

## restore dry-run

1. 원본 backup checksum과 manifest를 검증한다.
2. 별도 임시 디렉터리의 새 SQLite 파일로 복원한다.
3. 파일을 read-only로 열어 SQLite `integrity_check`와 `foreign_key_check`를 수행한다.
4. Alembic version이 manifest와 `ALEMBIC_HEAD`에 맞는지 확인한다.
5. table/row count, project/chapter/revision/snapshot 관계, unique/index, content hash를 대조한다.
6. key material이 별도로 제공된 경우에만 암복호화 round-trip을 test vector로 확인한다. 실제 endpoint 호출은 하지 않는다.
7. 앱을 별도 temp DB와 전용 포트로 기동해 health, read-only 목록, snapshot 조회를 확인한다.
8. 실패 시 원본 backup과 운영 DB는 변경되지 않아야 한다.

## 실패 복구와 원자성

- 복원은 기존 DB 위에 in-place migration하지 않고 새 경로에 만든다.
- 모든 검증이 PASS한 뒤 서비스 중지/교체 승인 단계를 별도로 둔다.
- 교체 전 기존 DB, WAL, SHM, manifest를 보존한다.
- 교체 후 health/schema/revision smoke가 실패하면 즉시 이전 경로로 rollback한다.
- partial copy, checksum mismatch, wrong key, unsupported Alembic head, foreign-key failure는 각각 distinct error로 기록한다.
- 자동 삭제와 자동 key rotation은 첫 버전에 포함하지 않는다.

## acceptance evidence

- backup manifest + checksums
- source/backup `integrity_check`와 `foreign_key_check` 출력
- Alembic head와 migration list
- row count 및 chapter/revision/snapshot hash 비교표
- key source/ACL 확인 결과(키 값 제외)
- temp restore health/API 출력
- failure injection: checksum 변경, 파일 누락, wrong key, wrong schema head, disk-full simulation 결과
- rollback 전후 DB path와 hash

## 금지 범위

이번 문서는 설계만 남긴다. `jippeel.db` 백업·복원, 운영 서비스 중지, keyring export, 실제 API key 사용, 운영 migration은 실행하지 않았다.
