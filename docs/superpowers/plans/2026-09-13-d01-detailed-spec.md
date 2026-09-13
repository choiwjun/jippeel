# D01 회차 목표 영속화 — 상세 사양 (좁은 범위)

- 작성일: 2026-09-13
- 상태: **상세 사양 — 구현 착수 기준**. [D01 상세 계약 제안서](2026-09-13-d01-detailed-contract-proposal.md)와 [질문·근거](2026-09-13-d01-contract-questions.md)의 미결정 질문을 소유자 위임 결정으로 확정한다.
- 결정 권한: 사용자가 "결정사항 묻지 말고 추천 방향대로 결정 후 진행"하라고 명시 승인. 아래 결정은 제안서의 권장 기본값을 그대로 채택한다.
- 기준 소스: 현재 HEAD `c2e4f6a` (worktree `choiwjun/d01-contract-analysis`).

## 1. 소유자 위임 결정 (Q1~Q7)

| # | 질문 | **확정 결정** | 근거 |
| --- | --- | --- | --- |
| Q1 | 작품 공통 목표 | **이번 범위 제외 — 회차 목표만** | 제안 기본값. 작품 레벨 목표는 D03 흐름 설계에서 별도 판단 |
| Q2 | A vs B | **B — 현재값 저장 + append-only 변경 이력 + 목록·복원 최소 API/UI** | 제안 권장안. D03의 목표↔원문 근거 연결에 과거 목표 내용이 필요 |
| Q3 | `episode_purpose` 영속화 | **함께 저장·복원** | 회차 directive를 목표와 같은 생애로 보존. 검증 규칙·`purpose_directive` 문구 불변 |
| Q4 | 전 필드 빈 값 의미 | **명시적 삭제 동작만 목표 제거**. 전 필드 빈 값 저장은 "빈 목표" 저장(비우기≠삭제). 삭제는 확인 후 DELETE. B이므로 이력은 보존 | 제안 기본값 |
| Q5 | 회차 삭제 시 목표·이력 | **회차 생애와 동일 — cascade 삭제** | 제안 기본값. 회차 삭제 자체는 기존 409 정책(복선·기억 참조) 그대로. D03 근거 참조 도입 시 재확인 |
| Q6 | 생성 시 저장본 사용 모드 | **기본 = 현재 입력값(메모리 폼). "저장본 불러오기"는 폼에 명시적 적재하는 버튼**으로 구현 — 서버가 요청 브리프를 몰래 교체하지 않음. 불러온 저장본 버전을 UI 배지로 표시(출처) | 제안 기본값의 가장 얇은 형태. 생성 요청 동결·flush 계약 변경 없음 |
| Q7 | 자동저장 | **명시적 저장 버튼만** | 제안 기본값. 큐·충돌·이탈 보존 명세 없이 자동저장 도입하지 않음 |

## 2. 데이터 모델

### 2.1 `chapter_goals` (회차당 현재 목표 1행)

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| id | Integer | PK |
| chapter_id | Integer | `FK chapters.id ON DELETE CASCADE`, **UNIQUE**, index, NOT NULL |
| goal_json | JSON | NOT NULL — §3의 정규화된 목표 payload |
| episode_purpose | String(20) | NOT NULL, 기본 `"serial"`, CHECK IN ('serial','volume_end','series_finale') |
| goal_version | Integer | NOT NULL, ≥1, 회차 내 단조 증가 |
| base_manuscript_revision | Integer | NULL — 저장 당시 작가가 본 원고 revision |
| created_at / updated_at | DateTime | 기존 TimestampMixin 패턴 |

### 2.2 `chapter_goal_revisions` (append-only 이력)

| 컬럼 | 타입 | 제약 |
| --- | --- | --- |
| id | Integer | PK |
| chapter_id | Integer | `FK chapters.id ON DELETE CASCADE`, index, NOT NULL |
| goal_version | Integer | NOT NULL — `UNIQUE(chapter_id, goal_version)` |
| goal_json | JSON | NOT NULL |
| episode_purpose | String(20) | NOT NULL, 같은 CHECK |
| base_manuscript_revision | Integer | NULL |
| restored_from | Integer | NULL — 복원으로 생성된 버전이면 원본 goal_version |
| created_at | DateTime | NOT NULL (이력은 created만) |

- 목표 저장·복원·삭제는 `Chapter.revision`을 증가시키지 않고 `ChapterSnapshot`을 만들지 않는다.
- `goal_version` 단조성 기준: `max(chapter_goals.goal_version, max(chapter_goal_revisions.goal_version)) + 1`. 현재값 삭제 후 재생성해도 이력 버전과 충돌하지 않는다.
- ORM 관계: `Chapter.goal`(uselist=False, delete-orphan), `Chapter.goal_revisions`(delete-orphan) — 프로젝트 삭제 cascade와 정합.

## 3. 목표 payload (저장 검증 — 생성 검증과 분리)

- `goal_json`은 `EpisodeBrief`와 동일한 9개 필드 구조: `emotion_goal, core_events, character_choices, cost, prohibitions, next_hook, ending_intent, scene_type, target_chars_novelpia`.
- **부분·빈 저장 허용**: 모든 필드 optional. 서버 정규화 = 문자열 trim 후 빈 문자열→null, 배열 항목 trim 후 빈 항목 제거. 배열은 정규화 결과 그대로 저장(빈 배열 허용).
- **보호 상한은 생성 계약과 동일**: 문자열·배열 항목 500자, `core_events`≤3, `character_choices`≤4, `prohibitions`≤10, `scene_type`은 5값 Literals, `target_chars_novelpia` 1000~10000. 위반은 422.
- 저장된 부분 목표가 자동으로 유효 생성 브리프가 되지 않는다 — 생성 경로는 기존 `parseEpisodeBrief`/`validate_context_contract` 그대로.

## 4. API 계약 (`app/routers/projects.py` 회차 섹션에 추가)

| 메서드·경로 | 요청 | 응답 | 실패 |
| --- | --- | --- | --- |
| `GET /chapters/{cid}/goal` | — | `200 ChapterGoalOut{chapter_id, project_id, goal: ChapterGoalVersion\|null, current_chapter_revision, history_count}` | 404 chapter |
| `PUT /chapters/{cid}/goal` | `ChapterGoalWrite{project_id?, goal: ChapterGoalPayload, episode_purpose?, expected_goal_version: int\|null, base_manuscript_revision?: int}` | `200 ChapterGoalOut` (새 goal_version) | 404 chapter / 409 CAS / 422 payload·소속 |
| `DELETE /chapters/{cid}/goal` | — | `204` — 현재값 row만 삭제, 이력 보존 | 404 chapter / 404 goal |
| `GET /chapters/{cid}/goal/history` | — | `200 list[ChapterGoalRevisionOut]` goal_version 내림차순 | 404 chapter |
| `POST /chapters/{cid}/goal/restore` | `{goal_version, expected_goal_version: int\|null, base_manuscript_revision?: int}` | `200 ChapterGoalOut` — 해당 이력 payload+purpose를 **새 버전**으로 기록(`restored_from` 설정) | 404 chapter / 404 이력 / 409 CAS |

### CAS 규칙

- `expected_goal_version=null` → "현재 목표 없음" 기대: 현재 row 존재 시 409 `{code:"goal_version_conflict", current_goal_version}`.
- `expected_goal_version=N` → 현재 row가 없거나 `goal_version != N`이면 409 + 현재 버전 반환.
- 생성 경로는 `UNIQUE(chapter_id)` IntegrityError→409, 갱신 경로는 `UPDATE ... WHERE id=? AND goal_version=?` rowcount 검사→409. 이력 INSERT의 `UNIQUE(chapter_id, goal_version)` 위반도 409. SQLITE_BUSY → 409 안내(기존 패턴).
- 복원도 동일 CAS(현재 버전 기대치 필요). 복원 시 `base_manuscript_revision`은 요청값, 없으면 현재 `Chapter.revision`.
- `project_id`가 요청에 오면 실제 회차 소속과 대조해 불일치 시 422 (기존 `_resolve_project` 패턴).
- 저장 `base_manuscript_revision` 미지정 시 현재 `Chapter.revision` 기록. 목표 저장이 원문을 잠그거나 갱신하지 않는다.

## 5. 프론트 계약

- **query key**: `['chapter-goal', chapterId]` — `['chapter', chapterId]`(원문)와 분리. 목표 저장·복원·삭제 후 이 키만 invalidate.
- **폼 소유**: `episodeBrief`는 현재 회차의 작업 폼 유지. store에 회차별 작업본 `_briefByChapter` + dirty 표시 `_briefDirty` 추가 — 회차 전환 시 이전 회차 입력을 map에 보관하고 새 회차 작업본(없으면 저장본, 없으면 빈 값)으로 전환한다. 저장본 hydrate는 dirty가 아닐 때만(늦은 응답이 다른 회차 폼을 덮지 않음 — M01/M02 경계).
- **UI (기존 브리프 폼 확장만)**: 섹션 헤더에 저장 상태(`저장본 vN · 기준 rM` / `미저장` / `저장본 vN · 원고 rX로 변경됨` stale 안내) + 버튼 `[불러오기]`(저장본→폼, 목표 없으면 비활성) / `[목표 저장]` / `[이력]` / `[삭제]`(확인 후). 409·실패 시 입력 유지 + toast.
- **이력 dialog**: 버전 목록(v, 시각, 기준 revision, 감정 목표 첫 줄) + `[이 버전으로 복원]`(확인 후 POST restore → 새 버전 기록 → 폼 갱신).
- **생성 연계**: `context.brief`는 현재 폼에서만 구성(기존 `parseEpisodeBrief`·동결·flush 그대로). 저장본을 쓰려면 불러오기로 폼에 적재한다(§1 Q6).
- purpose 동기화: 목표 저장 시 현재 directive `episodePurpose`를 함께 저장하고, hydrate·복원 시 저장된 purpose를 해당 회차 directive에 되돌린다(검증·문구 변경 없음).

## 6. 회귀 검증 케이스 (합성 TEMP DB · fake provider · fixture-only)

### 6.1 backend (`tests/test_chapter_goals.py` + `test_migrations.py` 추가분)

1. 목표 없음 → GET 200 `goal:null, history_count:0`; 없는 회차 404.
2. 저장 → 재조회 동일 payload·`goal_version`·`episode_purpose`·`base_manuscript_revision`.
3. 부분 입력·공백 정규화(빈 항목 제거·""→null)·빈 payload 저장 허용.
4. 상한 위반 422(501자 항목, core_events 4개, prohibitions 11개, scene_type 이탈, target 999).
5. 두 작품·두 회차 분리 — 교차 저장은 chapter 경로라 소속 검증은 `project_id` 불일치 422 케이스.
6. CAS: `expected=null`인데 존재 → 409; `expected` 불일치 → 409 + 현재 버전; 갱신 성공 시 버전+1·이력 row 추가.
7. 삭제: DELETE → GET `goal:null`이나 이력 유지(`history_count`>0); 재생성은 이력 max+1 버전; `Chapter.memo`·`content_md`·`revision`·snapshot·기억·복선 불변.
8. 복원: 존재하지 않는 이력 404; CAS 409; 성공 시 새 버전 + `restored_from` + purpose 복원.
9. 원문 저장/복원(`replace_manuscript` 경로) 후 목표·이력 불변 + `current_chapter_revision` 차이로 stale 판별 가능.
10. 회차 삭제(기존 조건 충족 시) → 목표·이력 cascade; 회차 삭제 409 정책(복선·기억 참조) 불변.
11. 경쟁: 독립 세션 2개로 동시 갱신 → 한쪽 409, 실패층 변경 없음(기존 `test_memory_concurrency` 패턴).
12. 생성 연계: 저장된 목표와 무관하게 요청 `context.brief`가 브리프 블록으로 1회 주입(기존 fake_llm 검증 재사용). 저장이 생성 요청을 바꾸지 않음.
13. migration: TEMP DB upgrade→`chapter_goals`/`chapter_goal_revisions` 생성, downgrade→제거, head 재upgrade 멱등, 기존 chapter/memory 행 보존.

### 6.2 frontend fixture (신규 spec + 전용 playwright config)

- 저장 버튼 → PUT 호출 본문(정규화된 payload, `expected_goal_version`, purpose) 확인 → 성공 시 `저장본 vN` 배지.
- 재진입: 저장된 목표 fixture → 패널 열면 폼이 저장본으로 채워짐.
- 회차 전환: A 회차 미저장 입력 → B 전환 후 복귀 → A 입력 보존(회차별 작업본).
- 늦은 응답 격리: A 회차 저장 응답이 B 회차 폼·query cache를 바꾸지 않음.
- 409 → toast + 입력 유지 + 저장본 갱신 안 refetch로 폼 덮지 않음.
- 이력 목록·복원: POST restore 본문 확인 → 새 버전 배지.
- 삭제: 확인 → DELETE → `저장본 없음` 상태.
- axe serious/critical 0.

## 7. 보존·금지 (제안서 §9/§11 그대로)

- 원문 revision/CAS·snapshot·flush·요청 동결·실패 처리·purpose 의미·문구 불변.
- `Chapter.memo` 덮어쓰기 금지, 목표 달성 자동 판정 금지, endpoint·모델 선택 UI 재도입 금지.
- 운영 DB migration 실행·commit/push·실제 provider·credential 접근은 별도 게이트.

## 8. 수용 증거

- RED 로그 → 최종 runner 로그(exit 0 + 위반 0 + subprocess 0) → fixture spec 로그 → manifest → 수용 문서 → 원장 갱신.
- `--isolation-coverage`는 고정 5개 모듈만 계측하므로 projects 라우터 변경분만 수치로 남기고, 새 서비스/스키마 라인은 국소 수치로 확대 해석하지 않는다.
