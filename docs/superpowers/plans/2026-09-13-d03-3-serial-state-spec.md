# D03-3 좁은 사양 — 완결 분리 (연재 상태 serial_state)

- 상위: [전체 실행 계획 §6.2](2026-09-13-project-wide-execution-plan.md) — "완결 분리: 집필 확정과 연재 완결 상태의 분리, 완결본 관리", §6.3 — "집필 확정(원문 상태)과 연재 완결(작품 상태)은 서로 다른 수명주기"
- 선행: D03-1(flow_stage, confirmed=집필 확정) 수용 완료
- 상태: 구현용 확정 (추천안 자율 결정 권한에 따라)

## 1. 목적

회차의 `confirmed`(집필 확정 — 원고 수준)와 독립적으로, **작품의 연재 상태**를 관리하는
작품 수준 필드. 전부 confirmed여도 연재 완결이 아니고, 완결이어도 회차 재개는 가능하다.

## 2. 계약

### 데이터

- `projects.serial_state` TEXT NOT NULL DEFAULT `'ongoing'`
  - 값: `'ongoing'`(연재중) | `'hiatus'`(휴재) | `'completed'`(완결)
  - CHECK constraint `ck_project_serial_state`
- `projects.serial_completed_at` DATETIME NULL — `'completed'` 진입 시각, 다른 상태로 나가면 NULL (ORM `created_at` 패턴과 동일하게 DateTime)

### API

- `PATCH /projects/{pid}` 의 `ProjectUpdate`에 `serial_state` 추가(기존 필드와 동일하게 부분 수정).
- `ProjectOut`에 `serial_state` + `serial_completed_at` 추가(목록·상세 동일).
- 전이 규칙: 상태 기계 아님 — 관리 라벨이므로 모든 전이 허용(자유 전환). `completed` 진입/재진입마다 `serial_completed_at`을 현재 시각으로 설정하고, 다른 상태로 바뀌면 NULL로 지운다.
- 잘못된 값 → 422(Pydantic Literal + DB check 이중 방어).

### migration

- 새 revision `4e5f6a7b8c92`, parent `3d4e5f6a7b81` → 새 head.
- `projects` 테이블 리빌드(컬럼 추가 + check) — `chapters` 등 자식 FK 때문에 SQLite
  `PRAGMA foreign_keys=OFF`를 섹션 전체에 적용하는 기존 패턴(b3c4/3d4e)을 따른다.
- backfill: 기존 행 전부 `ongoing`(server_default로 처리), `serial_completed_at` NULL.
- downgrade: 두 컬럼과 check 제거, 데이터 보존.

### 스키마 가드

- `database.py` `ALEMBIC_HEAD = "4e5f6a7b8c92"`, 컬럼 2개 + constraint 검사 추가.

## 3. 불변조건

- 회차 `flow_stage`·`status`와 완전 독립 — 어떤 쪽도 다른 쪽을 변경·검증하지 않는다.
- `serial_state='completed'`는 "완결본 동결"을 의미하지 않는다 — 원고 편집·전이는 계속 가능
  (완결본 관리의 동결/버전 개념은 후속 단위).
- 기존 ProjectUpdate 필드 동작 불변.

## 4. 프론트 (thin UI)

HomePage 프로젝트 카드:
- `serial_state` 배지 표시(연재중은 표시 생략 — 카드 잡음 최소화; 휴재/완결만 배지).
- 카드에 상태 선택 select(연재중/휴재/완결) — PATCH /projects/{pid}.
- 완결 카드에는 `완결 {date}` 표시(serial_completed_at 있을 때).

## 5. 테스트 matrix

| 축 | 케이스 |
|----|--------|
| 기본값 | 생성 시 ongoing·completed_at NULL |
| 전이 | ongoing→hiatus→ongoing→completed→ongoing, completed_at set/clear |
| 독립 | serial_state 변경이 회차 flow_stage·status·revision 불변 / 회차 confirmed가 serial_state를 바꾸지 않음 |
| 검증 | bogus 값 422, PATCH 부분 수정 시 다른 필드 불변 |
| migration | backfill ongoing, downgrade 컬럼 제거·데이터 보존, check 강제 |
| frontend | fixture: 배지 표시·전환 PATCH·tripwire |

## 6. 경계

- 완결본 동결/버전 스냅샷·근거 연결·이관은 후속 D03 단위.
- 운영 DB·실제 provider·credential·게시는 승인 경계 유지.
