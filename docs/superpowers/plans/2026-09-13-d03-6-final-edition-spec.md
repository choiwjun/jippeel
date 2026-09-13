# D03-6 좁은 사양 — 완결본 관리(final edition)

날짜: 2026-09-13 / 부모: [전체 실행 계획](2026-09-13-project-wide-execution-plan.md) §6.2 "완결 분리: 집필 확정과 연재 완결 상태의 분리, **완결본 관리**" · 근원: [관리 감사](../../audits/소설집필_관리_감사.md) §8.2 "결말 설계와 실제 원고를 대조하는 완결 점검표 … 전체 퇴고 후 완결본 스냅샷 생성" · §8.7 "완결본 보존 및 재개 가능"

## 1. 배경

- D03-3이 `serial_state`(연재 수명주기)를, D03-1이 `flow_stage`(집필 확정)를, D03-5가 복선 처분을 각각 수용했다.
- 그러나 "완결본" 자체는 어디에도 보존되지 않는다 — 회차는 이후에도 수정·삭제될 수 있어, 완결 시점의 원고 전체를 나중에 대조·재개할 근거가 없다.
- 본 슬라이스는 두 가지만 추가한다:
  1. **완결 점검표** — 파생·읽기 전용. 결말 설계와 실제 상태의 대조용 사실 나열(자동 판정·달성 판정 없음).
  2. **완결본 스냅샷** — 명시적 생성. 그 시점의 전 회차 본문+매니페스트+점검표를 불변 보존(append-only).

## 2. 데이터 계약

### `project_final_editions` 테이블

| 컬럼 | 타입 | 비고 |
|------|------|------|
| id | PK | |
| project_id | FK→projects ON DELETE CASCADE, index, NOT NULL | |
| label | String(200) NULL | 작가 지정 이름(없으면 목록에서 "완결본 {id}" 표시) |
| created_at | datetime, default utcnow, index | |
| serial_state | String(20) NOT NULL | 캡처 시점의 작품 연재 상태(기록용) |
| chapter_count | Integer NOT NULL | 비정규화 요약 |
| total_chars | Integer NOT NULL | 비정규화 요약(content_md 길이) |
| manifest_json | JSON NOT NULL | 회차별 `{chapter_id,title,sort_order,revision,flow_stage,status,chars}` 목록(캡처 순서=sort_order) |
| content_md | Text NOT NULL | 조립 원고 전문 — `## {title}` 절로 이어붙인 단일 텍스트 |
| checklist_json | JSON NOT NULL | 캡처 시점의 완결 점검표(§3 GET과 동일 구조) — 동결본 |

- 불변(UPDATE 경로 없음). 삭제만 명시적 DELETE로 허용.
- 회차 삭제·수정과 무관하게 보존 — content_md에 실제 본문을 복사한다(참조가 아닌 스냅샷).

### 캡처 의미론

- `POST`는 **모든 회차**를 sort_order 순으로 캡처한다(flow_stage 무관 — 스냅샷은 현실 기록이지 확정 게이트가 아니다). 각 매니페스트 항목에 `flow_stage`를 남겨 미확정 회차 포함 여부를 후에 식별 가능하게 한다.
- 생성은 명시적 작가 행위. 자동 생성 없음.
- `serial_state='completed'`가 아니어도 생성 가능 — 게이트가 아니라 기록.

## 3. API 계약

### `POST /projects/{pid}/final-editions` → 201 `FinalEditionDetail`

- body: `{label?: str | null}` — `label`은 strip 후 최대 200자, 빈 문자열→NULL.
- `BEGIN IMMEDIATE`로 writer lock → 회차 조회 → 조립 → insert → commit. BUSY→409(기존 매핑 재사용).
- 응답은 detail(§하단) 전체.

### `GET /projects/{pid}/final-editions` → list `FinalEditionOut`

- 메타만(id, project_id, label, created_at, serial_state, chapter_count, total_chars). content·manifest·checklist 미포함. created_at 내림차순.

### `GET /projects/{pid}/final-editions/{eid}` → `FinalEditionDetail`

- `FinalEditionOut` + `manifest`(list) + `content_md` + `checklist`.
- 타 프로젝트 소속이면 404(교차 프로젝트 은닉, 기존 패턴).

### `DELETE /projects/{pid}/final-editions/{eid}` → 204

- 명시적 삭제만. 없거나 타 프로젝트면 404. BUSY→409.

### `GET /projects/{pid}/completion-checklist` → `CompletionChecklist`(파생·읽기 전용)

```jsonc
{
  "serial_state": "completed",
  "serial_completed_at": "… | null",
  "chapters": {
    "total": 12,
    "by_stage": {"planning": 0, "writing": 1, "revising": 2, "confirmed": 9},
    "unconfirmed": 3                     // flow_stage != 'confirmed'
  },
  "foreshadows": {
    "total": 5,
    "open": [{"id": 3, "title": "검은 검", "status": "설치"}],   // status='설치'만, 미회수=점검 대상
    "by_disposition": {"resolved": 2, "intentional_unresolved": 1, "side_story": 0, "closed_unclassified": 1}
    // closed_unclassified = status 회수|보류 && disposition IS NULL
  },
  "pending_refine_runs": 4,              // accepted=false인 RefineRun 수(프로젝트 전체)
  "broken_evidence_links": 1,            // excerpt가 현재 원문에 없는 근거 링크 수
  "finale_goals_missing_ending": [{"chapter_id": 7, "title": "최종화"}]
  // 목표 존재 + episode_purpose='series_finale' + ending_intent 비어 있음
}
```

- 전부 파생 사실. "완결 가능/불가" 판정·점수 없음 — 작가가 읽고 판단한다.
- 404: 프로젝트 없음.

## 4. migration·가드

- migration `7b8c9d0e1f25` (down_revision `6a7b8c9d0e14`): `project_final_editions` 신규 테이블 + `ix_…_project_id`, `ix_…_created_at`. 신규 테이블이므로 FK pragma 래핑 불필요.
- `database.py`: `ALEMBIC_HEAD="7b8c9d0e1f25"`, 스키마 가드에 테이블 존재 확인 추가.
- 테스트: upgrade→행 insert→downgrade→테이블 제거·프로젝트 행 보존(기존 populated 패턴).

## 5. 프론트 계약

- 신규 페이지 `/projects/:pid/completion` — `CompletionPage`.
  - **완결 점검표** 섹션: 위 JSON의 각 수치를 카드/배지로 표시(열린 복선·미확정 회차·미수용 감수·파손 링크·ending_intent 없는 최종화 목표는 제목 나열).
  - **완결본** 섹션: label 입력(선택)+`완결본 생성` 버튼 → POST; 목록(라벨·시각·회차 수·총 글자 수·연재 상태 배지); 행 클릭 시 상세(매니페스트 표 + 원고 전문 pre); `삭제` 버튼 → DELETE.
- HomePage 카드: 집필 링크 옆에 `완결 관리` Link 추가.
- React Query: `['final-editions', pid]`, `['completion-checklist', pid]`; 생성·삭제 성공 시 두 키 무효화.
- fixture: 포트 **15235**, `playwright.final-edition.config.ts` + `e2e/final-edition.spec.ts`.

## 6. 테스트

### backend (`test_final_editions.py`)

- POST: 라벨 있음/없음(→NULL), 다중 회차 조립 순서(sort_order), manifest 필드·content_md 조립 형식, chapter_count·total_chars 정확성, checklist_json 동결(생성 후 원고 바꿔도 detail의 checklist는 캡처 시점 값), serial_state 기록, 프로젝트 없음 404, 빈 프로젝트(회차 0)도 생성 가능.
- GET list: 메타만(content_md 키 부재), 최신순, 타 프로젝트 격리.
- GET detail: 전체 필드, 타 프로젝트 404, 없음 404.
- DELETE: 성공 204→list에서 소실, 없음 404, 타 프로젝트 404.
- checklist: by_stage 집계, open 복선만 나열(회수·보류 제외), by_disposition 4버킷 정확성(설치+disposition 불가이므로 설치는 open에만), pending_refine_runs, broken_evidence_links(원문 바꿔 파손 유도), finale 목표 ending_intent 없음 탐지(부분 목표 저장), 프로젝트 없음 404.
- migration: populated upgrade 보존 + downgrade 후 프로젝트 잔존·테이블 제거.

### frontend fixture (`final-edition.spec.ts`)

- 점검표 수치·배지 렌더(열린 복선 제목 표시).
- 완결본 생성 → 목록 반영(label 미지정 시 "완결본 {id}").
- 상세 펼침 — 매니페스트·원고 전문 표시.
- 삭제 → 목록 제거.
- serial_state 배지 표시.
- axe serious/critical 0.

## 7. 금지·범위 밖

- 자동 완결 판정·자동 스냅샷 생성 금지.
- 완결본의 복원(restore-to-chapters)은 범위 밖 — 읽기 전용 보존만.
- 결말 후보(project ending) 저장·변경 영향 표시는 다음 슬라이스(D03-7).
- 운영 DB·실제 provider·credential·배포 없음.
