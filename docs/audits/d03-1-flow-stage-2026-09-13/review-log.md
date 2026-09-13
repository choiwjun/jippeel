# D03-1 독립 검토 기록

두 건의 fresh-context 독립 검토(백엔드 / 프론트엔드)를 병렬 수행했다. 검토자는 테스트를 직접 실행할 수 없는 read-only 환경이었으므로, 실행 근거는 본 디렉터리의 캡처 로그가 담당한다.

## 검토 1 — 백엔드 (verdict: PASS_WITH_NOTES)

계약 핵심 전부 정상 확인: 전이 표 정확, 에러 우선순위(404→409→422), guarded UPDATE CAS, 전이+이벤트 단일 커밋, SQLITE_BUSY→409, 마이그레이션 pragma 패턴(alembic 1.18.5 소스 대조), backfill 매핑, downgrade 정리, 스키마 가드.

### 지적 및 조치

| # | 지적 | 조치 |
|---|------|------|
| 1 | `flow_events`의 `delete-orphan`이 spec §3 위반(append-only 표면 약화) | `cascade="all"`로 수정 (models.py:90) |
| 2 | 앵커(goal_version/revision)가 writer lock 전에 읽혀 stale 가능 | guarded UPDATE 이후로 읽기 재배치 (projects.py:645-664) |
| 3 | migration `PRAGMA foreign_keys=ON`(finally)이 트랜잭션 내 no-op — 주석이 오해 소지 | 기존 `b3c4d5e6f7a8` 패턴과 동일한 quirk — 유지, 수용 문서에 한계로 기록 |
| 4 | `TRIM(content_md)`이 ASCII 공백만 처리 — `\n`만 있는 초고는 writing으로 매핑 | 알려진 한계로 수용 문서에 기록(공백-only 본문은 드묾) |
| 5 | 모델에 `server_default` 없어 create_all DB와 drift | `server_default="planning"` 추가 (models.py:64-66) |
| 6 | `IntegrityError→409`가 비-CAS 무결성 오류도 flow_stage_conflict로 포장 | 기존 goal-write 패턴과 일치 — 유지 |
| 7 | 전이가 `updated_at`을 갱신(onupdate) | 금지 목록 외 — 수용 문서에 명시 |

### 테스트 갭 → 추가됨

- 목표 저장→삭제→전이 시 `goal_version NULL` — `test_transition_after_goal_deleted_anchors_null`
- 보존 테스트에 snapshot 개수 불변 assertion 추가 (PUT 교체 1회 후 비교)
- stale expected + illegal to_stage → 409 우선순위 — `test_stale_expected_and_illegal_to_stage_returns_409_first`
- populated downgrade — `test_populated_downgrade_from_head_removes_flow_keeps_data`
- migrated DB의 `ck_chapter_flow_stage` 강제 검증 — backfill 테스트 말미에 추가

## 검토 2 — 프론트엔드 (verdict: FAIL → 수정 후 재검증)

### 차단 지적 (반증됨 + 예방적 수정)

- `Badge`의 `aria-label`이 `aria-prohibited-attr` serious 위반이라는 정적 분석 지적(확신도 85-90%). **실제 axe 실행은 위반 0**(frontend-chapter-flow.txt — 6 passed, a11y 테스트 포함). 다만 일반 `<span>`의 aria-label이 AT에서 무시될 수 있다는 근본 지적은 타당 → `role="status"` 부여로 명명 가능 role 확보 + 전이 시 polite announce 개선. 수정 후 6 passed 재확인.

### 비차단 지적 및 조치

| # | 지적 | 조치 |
|---|------|------|
| 1 | fixture `FlowEvent`에 `created_at` 누락 | 추가 |
| 2 | fixture가 필수 필드 누락에 409 대신 422를 반환해야 함 | 필드 존재 검사 추가(422) — 실제 UI 경로에서는 도달 불가 |
| 3 | `/flow/events` mock이 미사용 dead mock | 유지 — 계약 형상 고정 목적 |
| 4 | `FLOW_TRANSITIONS` 수동 미러 — drift 위험 | 유지 — 백엔드가 422로 최종 방어; 한계로 기록 |
| 5 | 쿼리 실패 시 컨트롤이 조용히 사라짐 | thin slice 범위 — 유지 |
| 6 | `package-lock.json` stale(`@axe-core/playwright` 미포함) | 기존 dirty 상태로 선존 — 본 슬라이스 범위 밖, 수용 문서에 기록 |
| 7 | 선존 버그: `patchMeta`가 `['chapter', id]` 캐시 미갱신 | 본 변경 무관 — 수용 문서에 별도 후속으로 기록 |

### 검증된 항목

CAS 읽기 시점(stale closure 없음), 쿼리 키 일관성, 409 처리, controlled select, 앵커 표기, 타입 계약 필드 일치, tripwire 커버리지, 기존 status select/SaveIndicator/D01 비침해.

## 최종 상태

- 재실행: backend focused `69 passed`, backend regression `543 passed / 1 skipped / violations []`,
  chapter-flow fixture `6 passed`, chapter-goal 회귀 `8 passed`, tsc `TSC_EXIT=0`.
- 두 검토 모두 차단 결함 없음 확인 후 수정·재검증 완료.
