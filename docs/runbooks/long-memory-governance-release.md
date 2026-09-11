# 장편 기억 거버넌스 운영 적용 준비 런북

- 상태: **준비만 완료 / 운영 실행 금지**
- 기준일: 2026-09-11
- 대상 migration head: `1b2c3d4e5f60`
- 범위: `MemoryEntry` 거버넌스 API/UI와 기존 provenance·revision·hash·stale 계약

## 1. 사전 조건

다음 조건이 모두 충족되기 전에는 운영 DB나 실제 provider에 접근하지 않는다.

- 명시적인 운영 적용 승인자와 승인 시각이 기록되어 있다.
- 운영 DB 백업 경로와 보존 기간이 확정되어 있다.
- DB 복원 담당자와 복원 완료 판정자가 분리되어 있다.
- 암호화 keyring/API key 복구 절차가 확인되어 있다.
- provider, model, 평가셋, 독립 평가자, 비용 hard cap이 확정되어 있다.
- 지정 Windows 장치와 test DB/key가 준비되어 있다.

## 2. 백업 및 manifest

운영 DB를 중지하거나 일관된 snapshot을 확보한 뒤 실행한다. 실제 경로·자격 증명은 문서나 로그에 남기지 않는다.

1. 원본 DB를 읽기 전용 상태로 전환한다.
2. 원본을 별도 저장소에 복사하고 파일 SHA-256을 기록한다.
3. 다음 manifest를 별도 보관한다.
   - 백업 파일 SHA-256, 크기, 생성 시각
   - Alembic `current`와 `heads`
   - 프로젝트·회차·memory row count
   - 백업 직전 `PRAGMA integrity_check`
   - 백업 직전 `PRAGMA foreign_key_check`
4. 복사본에서 integrity/foreign-key 검사를 다시 수행한다.
5. manifest와 복사본의 hash가 일치하지 않으면 즉시 중단한다.

## 3. migration 적용

승인된 변경 창에서만 실행한다.

```powershell
cd backend
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe heads
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
```

검증 항목:

- `current`가 `1b2c3d4e5f60`과 일치한다.
- 기존 프로젝트·회차·원고 row count가 migration 전후 보존된다.
- `memory_entries`의 project/chapter ownership, visibility constraint, source hash/revision 필드가 존재한다.
- 기존 원고 read/write, snapshot/restore, AI context stale 제외가 통과한다.
- 실패 시 앱을 재개하지 않고 백업 복원 절차로 전환한다.

운영 DB에서 downgrade를 즉흥적으로 실행하지 않는다. rollback은 검증된 백업 복원으로 수행하고, 복원 후 manifest와 smoke test를 다시 확인한다.

## 4. 운영 후 smoke test

실제 원고를 변경하지 않는 읽기 중심 확인부터 시작한다.

- `/health`
- 작품 목록과 회차 목록
- memory 목록의 project scope와 provenance 표시
- 승인 memory의 context 포함
- stale memory의 context 제외
- 다른 project memory/chapter ID 접근 거부
- memory가 연결된 회차 삭제 `409`
- UI에서 draft 추가·승인·폐기·취소 및 focus 이동

자동 요약, backfill, 실제 provider 호출은 이 런북의 smoke test에 포함하지 않는다.

## 5. 실제 모델 품질 평가 준비

실행 전 별도 평가 문서를 승인한다. 입력 양식은 `docs/audits/long-memory-evaluation-manifest.template.json`을 복사해 사용하며, 원본 원고·API key·secret은 manifest에 넣지 않는다.

- 승인된 사례 6개와 기대 결과/금지 결과를 고정한다.
- source owner와 provenance 판정 기준을 각 사례에 기록한다.
- provider/endpoint/model과 prompt block 길이 제한을 고정한다.
- 독립 평가자 2명을 배정한다.
- raw usage, latency, 오류, 비용 증거를 보관한다.
- 비용 hard cap은 USD 20으로 설정하며 초과 시 자동 중단한다.
- 현재 검증은 fake provider만 사용했으므로 품질 통과를 의미하지 않는다.

## 6. Windows 장치 QA 준비

지정 장치에서만 수행한다.

- 전용 port가 비어 있는지 확인하고 기존 프로세스를 종료하지 않는다.
- test DB와 test key만 사용한다.
- DPAPI/keyring 저장·복구, batch 실행, 브라우저 화면, 키보드 접근성, NVDA, 성능, restore race를 기록한다.
- 실패 시 운영 DB나 실제 keyring으로 우회하지 않는다.

현재 native Windows 자동화는 임시 SQLite와 fake provider를 사용한 통합 검증이며, 지정 실기기 sign-off가 아니다.

## 7. 현재 잔여 항목

- coverage 측정: 현재 venv에 `coverage`/`pytest-cov`가 없다. 새 의존성 추가는 별도 승인 범위다.
- 운영 migration/restore: 승인 전 미실행.
- 실제 provider 품질 평가: 평가셋·provider·독립 평가자 확정 전 미실행.
- 자동 요약/backfill: 별도 설계·승인 전 미실행.
