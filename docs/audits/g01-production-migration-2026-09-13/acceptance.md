# G01 수용 — 실 DB migration 적용 + G03/G04 부분 실행

- 수용일: 2026-09-13
- 범위: G01 실 운영 DB migration(전 과정), G03 wrong-key/키 유실 검증(부분), G04 Windows 네이티브 전체 스위트(부분)
- 승인 근거: 사용자 전체 위임 “나대신 승인하고 남은거 다 작업해” — 로컬 실행 가능 범위에 한해 진행
- 상태: **수용(실행 완료 범위)**

## G01 — 실 DB migration ✅

대상: `C:\Users\wj941\Documents\jippeel\backend\jippeel.db`(664K, projects 2·chapters 20·ai_usage 1418행). `alembic_version` 없는 `create_all` 생성 DB, 스키마 정합은 `f9a1b2c3d4e5` 수준(preservation 이전).

절차(런북 순서):
1. **일관 백업** — sqlite backup API로 `real-backup-copy.db` 생성 + sha256 manifest(`backup-manifest.json`). `create_backup()`은 `alembic_version`을 요구해 수동 manifest 경로 사용.
2. **복원 검증** — 백업본 integrity_check ok + 14개 테이블 기준선 row counts 캡처(`verification.txt`).
3. **리허설** — 복사본에 `alembic stamp f9a1b2c3d4e5` → `upgrade head` 10개 migration 전부 완주(`rehearsal-upgrade-log.txt`). 마이그레이션본 데이터 보존 확인.
4. **실 적용** — 동일 절차를 실 DB에 적용(`real-upgrade-log.txt`).
5. **사후 검증** — `alembic_version=9d0e1f2a3747`(head), 14개 테이블 row counts 전부 기준선과 일치, `assert_manuscript_schema_current` 통과, 백엔드 smoke 정상.

ALTER 충돌 사전 대조: 각 migration의 ALTER 대상 컬럼이 실 DB에 부재함을 확인 후 적용(`foreshadows.audience_knows`는 선존, `6a7b8c9d0e14`는 `disposition`만 추가 — 충돌 없음).

## G03 — credential/key 검증(부분) ✅

- 두 키 파일(`~/.jippeel/api_key.key` Linux 측 / `C:\Users\wj941\.jippeel\` Windows 측)이 **상이함**을 확인 — 인스턴스별 키 분리 설계와 일치.
- 저장된 암호문 실데이터 부재(DB의 credential 슬롯 비어 있음) — 실제 credential 복호화 수용 대상 없음을 기록.
- temp 경로에서 실제 키로 생성한 암호문으로 **wrong-key 거부·키 유실 감지·복구 절차**를 검증(`g03-partial-key-verify.txt`).

미완료 잔여: 지정 테스트 credential/계정으로의 실제 로그아웃·복구 시연(계정 승인 필요).

## G04 — Windows 네이티브(부분) ✅

- Windows 11 네이티브 Python 3.14.4 + 실 리포 venv(`C:\Users\wj941\Documents\jippeel\backend\.venv`)로 격리 러너 `scripts/run_backend_pytest.py` 그대로 실행.
- 전체 스위트: 최종 **714 passed / 1 skipped / violations 0 / warnings 0**(`g04-partial-windows-native.txt`) — 초기 682P 이후 O05·신규 테스트 동기화 반영. 최초 1건 실패(`test_create_backup_write_failure`)는 Windows chmod가 디렉터리 생성을 차단하지 않는 근사 기법 — 플랫폼 조건화 후 통과.
- alembic 10개 migration도 Windows 네이티브에서 temp DB에 전부 완주.
- O05 변경분(database.py inspect 스코프·test_migrations 헬퍼·conftest `_db` 통합) 재동기화 후 최종 전체 스위트 **714 passed** 확인.

미완료 잔여: 원래 G04 수용 정의의 브라우저·NVDA·키보드·zoom·5만 자 입력/검색 성능 결과표 등 수동 실기기 영역(장치 창 승인 필요).

## 비수용(명시 제외)

- G02 실제 OAuth/provider 수용 — 실제 자원·예산(USD 20 cap)·평가자 승인 필요, 미실행.
- G03의 실제 credential 대상 시연, G04의 수동 실기기 시나리오 — 위 잔여 참조.
- 운영 DB 교체·rollback 실시연 — 백업본 보존되어 있으나 실 DB가 정상이므로 불필요로 판단.
