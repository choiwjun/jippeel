# D03-4 좁은 사양 — 근거 연결 (목표 필드 ↔ 원문 발췌 링크)

- 상위: [전체 실행 계획 §6.2](2026-09-13-project-wide-execution-plan.md) — "근거 연결: 목표 필드(사건/선택/대가) ↔ 원문 범위의 링크 보존·파손 안내"
- 선행: D01(목표 버전·필드 구조), D03-1(전이 앵커), D03-2(파생 읽기 패턴) — 모두 수용 완료
- 상태: 구현용 확정 (추천안 자율 결정 권한에 따라)

## 1. 목적

"이 목표 항목은 원고의 이 부분에서 다뤄졌다"는 **수동 근거 링크**.
링크는 발췌문(excerpt) 기반 — offset 범위는 편집으로 조용히 깨지므로 쓰지 않는다.
읽기 시점에 파생 상태를 계산해 **파손 안내**를 제공한다. 자동 판정·자동 연결 없음(§6.3).

## 2. 데이터 — `chapter_goal_evidence_links`

| 컬럼 | 타입 | 의미 |
|------|------|------|
| `id` | PK | |
| `chapter_id` | INT FK chapters.id ON DELETE CASCADE | 소유 회차 (D01 고정 키) |
| `goal_version` | INT NOT NULL | 링크 생성 시점의 목표 버전 앵커 |
| `goal_field` | VARCHAR(40) NOT NULL | 연결 대상 목표 필드 — `core_events`/`character_choices`/`cost`만 허용(CHECK `ck_evidence_link_field`) |
| `item_index` | INT NULL | 목록 필드의 항목 인덱스(0-based). 스칼라 `cost`는 반드시 NULL |
| `goal_item_text` | VARCHAR(500) NOT NULL | 링크 시점 목표 항목 스냅샷 — 목표 변경 감지의 비교 기준 |
| `excerpt` | TEXT NOT NULL | 연결된 원문 발췌 (최대 500자) |
| `created_at` | DATETIME | |

- migration `5f6a7b8c9d03` (revises `4e5f6a7b8c92`). downgrade는 테이블 제거.

## 3. API

### `POST /chapters/{cid}/evidence-links` → `EvidenceLinkOut` (201)

body `{goal_field, item_index?, excerpt}`:
- 422: 사전 외 `goal_field`, 목록 필드에 `item_index` 누락/범위 밖, 스칼라에 `item_index` 제공, 빈 excerpt, excerpt가 현재 `content_md`에 없음(태어날 때부터 깨진 링크 금지)
- 409/422: 현재 목표 없음 또는 해당 항목 없음 → 링크할 대상이 없다
- 저장: `goal_version`=현재 목표 버전, `goal_item_text`=해당 항목 현재 텍스트

### `GET /chapters/{cid}/evidence-links` → `{links: [...]}`

각 링크에 파생 상태를 붙인다:

| 필드 | 값 |
|------|-----|
| `manuscript_status` | `intact` — 현재 `content_md`에 excerpt 포함 / `broken` — 없음 |
| `goal_status` | `unchanged` — 현재 목표 동일 위치 텍스트 일치 / `drifted` — 항목 변경·누락 / `goal_deleted` — 현재 목표 없음 |
| `current_goal_version` | 비교 기준 공개 |
| 나머지 | 저장 필드 그대로 |

- 404: 회차 없음. 쓰기 없는 파생 읽기.

### `DELETE /chapters/{cid}/evidence-links/{lid}` → 204

- 404: 링크 없음/다른 회차 소속.

## 4. 프론트 (thin UI)

AiPanel의 회차 목표 섹션 아래에 **근거 연결** 소절:

- 링크 목록: `"{goal_item_text 요약}" → "{excerpt 요약}"` + 상태 배지
  - `원문 파손`(manuscript_status=broken), `목표 변경됨`(goal_status=drifted), `목표 삭제됨`
- 링크 생성: 항목별 "선택 본문 연결" 버튼 — `editorStore.view`의 현재 selection 텍스트를 excerpt로 전송. 선택 없음/비어있음/다른 회차면 비활성 + 안내.
- 삭제 버튼 per 링크.
- 조회 키 `['evidence-links', chapterId]` — 원고 저장·목표 저장/삭제/복원·링크 변경 시 invalidate.

## 5. 테스트 matrix

| 축 | 케이스 |
|----|--------|
| 생성 | 목록 필드 각 인덱스·스칼라 cost 링크 → 201 + 앵커 저장 |
| 거절 | 사전 외 필드 422, 인덱스 누락/초과 422, 스칼라+인덱스 422, 빈/미존재 excerpt 422, 목표 없음 422 |
| 파생 | 원문 편집으로 excerpt 제거 → broken; 목표 항목 텍스트 변경(새 버전) → drifted; 목표 삭제 → goal_deleted; 둘 다 intact |
| 삭제 | 204, 타 회차 링크 404 |
| 보존 | 링크 생성/삭제가 목표 버전·원고 revision·snapshot을 바꾸지 않음 |
| 회차 삭제 | cascade로 링크 제거 |
| migration | head 도달, populated upgrade 후 링크 작성·조회, downgrade로 테이블 제거 + 프로젝트/회차 보존 |
| frontend | fixture: 링크 목록+상태 배지, 선택 연결 버튼 활성 조건, 생성·삭제 요청 본문, tripwire |

## 6. 경계

- 달성 자동 판정·자동 연결 금지 — 링크는 사용자의 명시적 주장이다.
- 목표 저장·원문 CAS·snapshot·flush·flow 계약 불변.
- 완결본 관리·이관(해결/의도적 미해결/외전)은 후속 단위.
- 운영 DB·실제 provider·credential·게시는 승인 경계 유지.
