# 인지·상태 도메인 설계 (D02 잔여 — 작가/독자/인물별 인지와 사건·관계 영향 추적)

2026-09-14 · 상태: 설계 문서. 구현 슬라이스는 아래 "단계"에 따라 별도 착수.

## 문제

현재 장편 기억(MemoryEntry)과 복선은 "작품 전체가 아는 사실" 하나의 시야만
갖는다. 실제 집필에서 필요한 것은 주체별 시야다:

- **독자 시야** — 독자에게 공개된 사실만. 100화에 공개될 반전을 30화 집필
  컨텍스트에 넣으면 AI가 힌트를 새게 한다.
- **인물 시야** — 인물 A가 아는 것만. A가 모르는 음모를 A의 대사·내면이
  암시하면 몰입이 깨진다. 반대로 "독자는 알지만 인물은 모름"은 서스펜스의
  재료다.
- **작가 시야** — 작가의 설계 노트(의도·미공개 설정). 생성에 참고하되
  독자/인물 시야와 섞이면 안 된다.

또한 사건이 남긴 파장(관계 변화·복선 진행·인물 상태)을 회차 단위로 추적하지
않으면 500화에서 "이 사건 이후 A와 B가 왜 틀어졌지"를 복원할 수 없다.

## 용어·모델 제안

### 인지 상태 (knowledge state)

| 개념 | 필드 |
|---|---|
| 주체 | `subject_type` ∈ `author` / `reader` / `character` — `character`일 때만 `character_id` |
| 대상 | `target_kind` ∈ `fact` / `foreshadow` / `lore` / `event` — `target_id`로 기존 행을 가리킨다 |
| 상태 | `status` ∈ `unaware` / `aware` / `false_belief` / `forgotten` — `false_belief`는 "잘못 알고 있음"(반전·기만 서술용) |
| 공개 지점 | `revealed_chapter_id` + `effective_from_sort_order` — 언제부터 그 상태인가 |
| provenance | 수동 입력 또는 파생 job(`generated_by`), 근거 발췌 링크(D03-4 evidence 재사용) |

기본값 규칙: 기록이 없으면 `author=aware`(작가는 전부 앎),
`reader=unaware`, `character`는 "해당 인물이 관련된 사실만 aware"로
추정한다 — 추정은 명시 기록이 덮어쓴다.

### 사건 영향 (event impact)

회차 안 "사건"을 엔티티로 올린다(장면 비트와 별개 — 사건은 관계·복선·인물
상태에 델타를 남기는 단위):

| 필드 | 의미 |
|---|---|
| `chapter_id`, `label` | 사건 발생 지점·이름 |
| `character_deltas_json` | `[{character_id, delta: "부상/각성/관계전락…", note}]` |
| `relationship_deltas_json` | `[{character_pair, from→to, note}]` — 관계 카드의 변화 |
| `foreshadow_deltas_json` | `[{foreshadow_id, 진전: 진행/회수/실패}]` |
| `state_after` | 이 사건 직후 인물·복선 스냅샷 요약 (요약 본문 아님) |

### 조회 계약

`knowledge_visible(subject, target, at_sort_order)` — 그 시점에 그 주체가
그 사실을 아는가. 컨텍스트 주입 시 `pov_character_id`가 지정되면
`character` 시야로 필터된 기억·복선만 넣는다(현재 복선의
`audience_knows`는 reader 시야의 1필드 특수형 — 일반화가 이 도메인).

## 생성·승인 원칙 (기존 거버넌스 재사용)

- 파생은 `generated_by` provenance가 있는 **draft만** — 승인은 작가.
- 승인 전에는 어떤 컨텍스트 블록에도 들어가지 않는다 (select 게이트 재사용).
- 상태 전이는 append-only — `unaware→aware` 등 전이 자체가 이력이며,
  덮어쓰기 대신 새 행 + `effective_from` 경계.
- 회차 원문이 바뀌면 파생 행은 stale — `source_sha256` 패턴 재사용.

## 단계 (구현 슬라이스 제안)

| 단계 | 범위 | 선행 조건 |
|---|---|---|
| P1 스키마 | `knowledge_states`·`event_impacts` 테이블 + 수동 입력 UI | 이 문서 승인 |
| P2 파생 job | 회차 → 사건/인지 후보 draft 추출 (summary worker 패턴 재사용) | P1 + E6 규칙 주입 경험 |
| P3 컨텍스트 | POV 시야 필터를 `build_context_bundle`에 연결 | P2 축적 + POV 선택 UI |
| P4 추적 뷰 | 인물별 "지금 무엇을 아는가"·사건 영향 타임라인 | P2 |

P1만으로도 작가가 수동으로 인지 상태를 기록할 수 있고, P2의 파생은
그 위에 올라가는 가속이다. E-시리즈와 마찬가지로 파생→작가 승인→적용의
궤적을 따른다.

## 비목표

- 독자 반응 데이터(플랫폼 댓글·선작률) 수집 — 외부 연동, 별도 범위.
- 실시간 인지 추론(매 토큰마다 시야 계산) — 생성 시점 스냅샷 필터로 충분.
- 과거 시점 재작성(회고 씬)의 시야 역행 — P3 이후 과제로 남긴다.
