# 작가 피드백 자가개선 — 설계 계획 (2026-09-14)

사용자 제시 방향을 현재 코드 기반에 맞춰 구체화한 계획이다.
**모델 재학습이 아니다** — 작품별로 "생성본 ↔ 작가 최종본"의 차이를 축적해
규칙을 제안하고, 작가가 승인한 규칙만 다음 생성의 컨텍스트에 주입한다.

## 0. 원칙 (불변 조건 — 모든 단위가 지킨다)

1. **원고·설정 몰래 변경 금지.** 개선 경로가 쓰는 것은 제안 레코드뿐.
   `chapters.content_md`·`projects.style_profile` 등은 기존 명시 경로만 쓴다.
2. **제안 → 작가 승인 → 적용** 순서. 자동 승인 없음.
   `MemoryEntry.visibility(draft|approved|retired)`와 `RefineRun.accepted`의
   기존 승인 패턴을 그대로 따른다.
3. **작품별 완전 분리.** 모든 신규 테이블은 `project_id` 스코프.
   컨텍스트 주입도 같은 project_id만 읽는다 — 타 작품 규칙이 새지 않는다.
4. **append-only 이력.** 생성 이력·피드백·규칙 변경은 수정하지 않고 새 행.
   삭제는 회차/프로젝트 cascade와 감사 보존 규칙을 따른다.
5. **결정론 먼저.** 분석 1차는 LLM 없는 결정론 계산(차이율·삭제 패턴·분량).
   LLM 제안은 그 위의 선택 단계이며 출력은 항상 draft.

## 1. 이미 있는 기반 (재구현 금지)

| 필요한 것 | 이미 있는 것 |
|---|---|
| 작가의 명시적 반영 경로 | AiPanel [끼워넣기]/[선택 교체]/[복사] — FR-406, 자동 삽입 없음 |
| 승인 플래그 패턴 | `RefineRun.accepted`, `MemoryEntry.visibility` |
| 컨텍스트 주입점 | `ai_context.build_context_bundle` — memory block·style_profile 삽입 구조 |
| 회차 revision 앵커 | `Chapter.revision` + CAS 409 (스냅샷 시점 고정 가능) |
| idempotent 비동기 작업 | `summary_jobs` — manifest 영속·idempotency_key·draft-only 결과 |
| 장기 기억 단층 | `MemoryEntry`(회차 요약) + `VolumeNote`(권 단위) |
| 호출 계량 | `ai_usage`(kind·model·문자 수) — 텍스트 자체는 미보존 |
| 실증된 필요성 | G02 파일럿 blind-04: 병렬 스티칭 결함을 review 레그가 포착 — "반복되는 AI 오류" 학습의 실제 사례 |

## 2. 없는 것 (이번 설계의 신규 범위)

- 생성 결과물(텍스트) 자체의 보존 — 지금은 문자 수만 남는다
- 작가의 처분 기록 — 끼워넣기/교체/폐기 중 무엇을 했는지
- 생성본 vs 최종 원고의 차이 분석
- 작품별 개선 규칙 저장소와 승인 절차
- 승인 규칙의 컨텍스트 주입

## 3. 단위 분할 (얇은 슬라이스, 각각 사양→RED→구현→회귀→독립 검토→수용)

### E1 `generation_runs` — 생성 이력 영속 (기반 테이블)

매번 생성 호출의 입력·출력을 보존하는 append-only 테이블.

```
id, project_id(FK cascade), chapter_id(FK SET NULL),
surface(generate|generate_parallel|review|parallel_plan|parallel_review),
preset_id, model, reasoning_effort,
input_sha256, output_sha256, output_text, output_chars,
wall_ms, ai_usage_id(FK, nullable),
status('pending'),           # E2가 갱신
chapter_revision_at_gen,     # 생성 시점 앵커
created_at
```

- 라우터가 아니라 서비스 계층에서 기록 — SSE 스트림 완결 시점에 확정.
- 스트림 중단/에러도 `status='provider_error'`로 보존(case-05의 RemoteProtocolError 같은 실측이 곧 데이터).
- 원문이 아니라 **참조**다 — 이 테이블을 지워도 원고·복원에 무관.

### E2 작가 처분 기록 — `generation_runs.outcome`

AiPanel의 세 버튼이 이미 유일한 반영 경로이므로, 클릭 시 outcome만 기록:

- `inserted` / `replaced` / `copied` / `discarded`(명시 닫기 또는 세션 만료)
- `outcome_at`, `chapter_revision_at_action` (CAS 앵커)
- 끼워넣기/교체 시 **실제 삽입된 텍스트** 보존(삽입 전후 커서 차이로 계산, 프론트가 전송)
- UI 변경 없이 기존 버튼에 계측만 추가 — FR-406 계약 불변

### E3 차이 분석 — 결정론 1차

런당·작품 누적으로 계산(LLM 없음):

- 삽입본 vs 현재 원고 해당 구간의 편집 거리·변경률(회차 저장 시점에 재계산)
- 자주 삭제되는 구간의 n-gram/패턴 집계(작품별)
- 회차별 생성물 길이 vs 최종 원고 길이 분포
- 표면별 accept/discard 비율(accepted 중 24h 내 대량 수정은 soft-reject 신호)

결과는 `project_feedback_signals` 같은 파생 읽기 또는 집계 테이블 — 재계산 가능하므로 캐시 성격.

### E4 `improvement_rules` — 작품별 규칙 저장소

```
id, project_id(FK cascade),
category(style|deletion|character_voice|pacing|length|recurring_error|canon_gap|arc),
rule_text,                     # 작가에게 보이는 한 줄 규칙
evidence_json,                 # 근거 generation_run ids·발췌·집계 수치
status('proposed'|'approved'|'rejected'|'retired'),
source('deterministic'|'llm_suggested'|'author_written'),
applied_count, superseded_by, created_at, decided_at
```

- `proposed`는 제안일 뿐 — 생성에 아무 영향 없음.
- `approved`만 주입 대상. `retired`는 승인 이력 보존(감사).
- 작가 직접 작성(`author_written`) 허용 — 분석 없이도 규칙 추가 가능.

### E5 규칙 제안 작업 — `summary_jobs` 확장 또는 분리 job

- 결정론 신호(E3)가 임계 도달 시 proposed 규칙 생성(예: "삽입본의 '~것이다' 종결이 매번 삭제됨 (7/9회)")
- LLM 제안은 별도 job: N개 run의 (생성본, 최종본) diff를 묶어 규칙 초안 제안 → `proposed`로만 기록
- 기존 worker 생명주기·idempotency·draft-only·provider_error 재시도 규칙 재사용
- **60k 상한·prompt_version 계약 그대로** — 고정 OAuth 계약 변경 없음

### E6 컨텍스트 주입 — 승인 규칙만

`build_context_bundle`에 선택 블록 추가:

```
[작가 승인 규칙 — 이 작품 전용]
- (approved 규칙, 승인 순서대로, 상한 N건·총 M자)
```

- `include_rules: bool = True` 요청 플래그 — 호출자가 끌 수 있음
- 규칙 블록은 번들에 **그대로 표시** — 작가가 보내는 프롬프트에 뭐가 들어가는지 투명
- `applied_count` 갱신으로 규칙의 실사용 추적

### E7 UI — 규칙 패널 + 생성 이력

- 프로젝트 설정(또는 신규 탭)에 **개선 규칙 목록**: proposed 카드에 근거 링크(어떤 run의 어떤 diff에서 나왔는지), [승인][거절] 버튼
- approved 목록: 적용 횟수·[폐기] — 폐기는 retired로 이력 보존
- 회차 에디터에 생성 이력 접이식(이 회차에서 생성된 run·처분·현재 diff 상태)
- 모두 기존 패턴 재사용: list→PATCH, 캐시 무효화, uiScale 대응

## 4. 500화+ 장기 기억 계층 (별도 트랙, 기존 구조 위에)

현재: `MemoryEntry`(회차 요약, draft→approved) + `VolumeNote` + `summary_jobs`.

추가할 계층:

| 계층 | 저장소 | 생산 |
|---|---|---|
| 회차 요약 | MemoryEntry(kind='summary') | 기존 summary_jobs (D04-1) |
| 아크 요약(10~20화) | MemoryEntry kind='arc_summary' 추가 또는 별도 tier 필드 | 회차 요약 N개 묶음을 요약하는 job(승인 규칙 동일) |
| 권 장기 기억 | 기존 VolumeNote 확장 | 권 완결 시점 집계 |
| 작가 승인 규칙 | improvement_rules | E4/E5 |
| 오래된 기억 압축 | visibility='retired' 전이 + superseded 링크 | 주기 job — 삭제 아닌 은퇴 |

컨텍스트 선택(`select_context_memory`)은 최근 회차 요약 → 현재 아크 → 권 →
승인 규칙 순으로 예산 내 탑재 — 기존 선별 로직에 계층 가중치만 추가.

## 5. 데이터 흐름 (전체 그림)

```
생성 요청 ──► build_context_bundle(…, include_rules) ──► provider
              ▲                                         │
   approved improvement_rules만                   SSE 출력
              │                                         ▼
        E4 테이블 ◄── proposed ◄── E5 분석 job ◄── E1 generation_runs
              ▲                                        │
         작가 승인/거절                          E2 처분 + E3 diff 집계
              │                                        ▲
        E7 규칙 패널                          AiPanel 끼워넣기/교체/폐기
```

## 6. 검증·안전 계획

- 각 단위: focused tests + 전체 회귀 + 독립 검토 2건 (기존 수용 절차 동일)
- 불변 테스트: 규칙 승인 없이 생성 컨텍스트가 바이트 단위로 동일함을 단정
- 격리: 프로젝트 A 규칙이 프로젝트 B 번들에 절대 등장하지 않음을 테스트로 단정
- CAS: 규칙 결정·폐기는 상태 전이 CAS(이미 decided면 409)
- 실 provider 필요 구간은 E5의 LLM 제안뿐 — 브릿지 생존 확인 후 USD cap 준수

## 7. 착수 순서 제안

1. **E1+E2** 먼저 — 데이터가 없으면 이후 전부 공허. 생성 이력+처분이 쌓이기 시작해야 분석 재료가 생긴다.
2. **E4+E7** — 규칙 저장소와 승인 UI. `author_written` 규칙만으로도 즉시 유용(작가가 직접 "이 작품은 ~하게" 규칙 등록 → 다음 생성에 적용).
3. **E6** — 승인 규칙 주입. E4+E7 완료 후 얇게.
4. **E3+E5** — 축적 데이터로 결정론 신호 → 제안. LLM 제안은 마지막.
5. 장기 기억 계층은 E1~E7과 독립 — 요약 job이 이미 있으므로 병렬 가능.

E1~E3이 쌓이면 G02 파일럿의 blind-04 같은 스티칭 결함이 자동으로
"recurring_error" 신호로 집계된다 — 파일럿이 이 기능의 첫 실증 데이터다.

## 8. 명시적 비범위

- 모델 재학습·파인튜닝·워터마크 관련 어떤 것도 하지 않음
- 승인 없는 규칙 자동 적용 금지
- 타 작품 데이터의 교차 사용 금지(개인화는 작품 단위가 최대)
- 플랫폼 자동 발행·O04 provider 확장과 무관
