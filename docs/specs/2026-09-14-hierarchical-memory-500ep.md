# 500화+ 계층 기억 — 설계 (D02 연계)

2026-09-14 · 상태: 1차 슬라이스 구현 완료 (회차 요약 → 아크 요약), 권 기억·압축은 후속.

## 목표

500화 이상 가는 연재에서 모든 회차 요약을 매번 컨텍스트에 넣을 수 없다.
층을 나눠 — 최근엔 구체적으로, 오래된 건 압축해서 — 제한된 컨텍스트 안에서
장기 일관성을 유지한다.

## 계층

| 층 | kind | 원천 | 생성 |
|----|------|------|------|
| 회차 요약 | `summary` | `chapter.content_md` | `summary_jobs(kind='summary')` |
| 아크 요약 | `arc_summary` | 승인된 `summary` 10~20화 묶음 | `summary_jobs(kind='arc')` |
| 권 기억 | (후속) `volume_memory` | 승인된 `arc_summary` 묶음 | 후속 슬라이스 |
| 작가 규칙 | `improvement_rules` | E3 분석·작가 작성 | E4/E5 (구현됨) |

공통 원칙:
- 생성 결과는 전부 `visibility='draft'`로 append — 승인 없이 컨텍스트에 들어가지 않는다.
- `select_context_memory`는 `approved`만 선택하므로 승인 게이트가 무료로 보장된다.
- 상위 층의 원천은 하위 층의 **승인본뿐** — draft 아크가 권 기억에 섞이지 않는다.

## 아크 요약 슬라이스 (구현됨)

- `plan_arc_summary_jobs` — 승인된 회차 요약을 `arc_size`(기본 10)로 묶어
  `kind='arc'` job 생성. 마지막 부분 아크는 `min_arc_sources`(기본 3) 미만이면 생략.
- idempotency key에 원천 entry id 집합+본문 해시 포함 → 같은 원천이면 job 재사용,
  원천이 바뀌면(승인 취소·재승인으로 다른 본문) 새 job.
- `_process_arc_job` — 처리 시점에 원천이 전부 존재·승인 상태인지 재검증
  (회차 요약과 같은 stale_source 패턴). provider 호출 후에도 재검증.
- 결과 `MemoryEntry(kind='arc_summary', chapter_id=None, visibility='draft',
  effective_from_sort_order=<아크 끝 sort>)`. chapter_id=None이므로 `is_stale`의
  원문 해시 비교를 타지 않고, effective_from 게이트로 아크 이후 회차에만
  컨텍스트 진입한다.
- provider 어댑터는 `ARC_PROMPT_VERSION='arc-v1'` 템플릿 — 회차 나열이 아닌
  구간 흐름 요약. 동일 `MAX_SOURCE_CHARS` 상한.

## 컨텍스트 예산 전략 (후속)

현재 `select_context_memory`는 승인본 전체를 나열한다. 500화에서는:
- 아크 요약이 회차 요약을 대표 — 같은 구간의 회차 요약이 승인된 아크 요약으로
  덮인 경우 개별 회차 요약은 컨텍스트에서 제외하는 **커버리지 선택**이 필요.
- 우선순위 제안: 이전 회차 원문 > 승인 규칙 > 현재 아크의 회차 요약 >
  과거 아크 요약 > 권 기억 > 로어/복선.

## 권 기억·압축 (후속)

- `kind='volume'` job: 승인된 `arc_summary` 묶음 → `volume_memory` entry.
- 오래된 기억 자동 retired: 상위 층이 승인되면 하위 층의 retired는 작가
  액션으로만 — 자동 전이는 하지 않는다(append-only 원칙).
- 장기 이슈: 10화/50화 주기의 `long_arc` 카테고리 규칙(E5 제안 job과 연계).

## 비용·운영

- 계획(manifest)은 provider-free — 실제 호출은 승인 게이트 뒤 worker만.
- 아크 job도 `provider_error`만 명시 retry — stale_source는 재계획 대상.
- 회차 삭제 시 chapter-anchored 요약은 `SET NULL`로 보존되되 `is_stale`가
  컨텍스트에서 제외 — 아크 요약은 chapter_id=None이라 남지만 provenance의
  `arc_source_entry_ids`로 원천 추적 가능.
