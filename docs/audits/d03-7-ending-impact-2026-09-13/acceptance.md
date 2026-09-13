# D03-7 수용 문서 — 결말 변경 영향

- 슬라이스: **D03-7** (D03 마지막 단위)
- 사양: `docs/superpowers/plans/2026-09-13-d03-7-ending-impact-spec.md`
- 근원 요구: 관리 감사 §8.5 — "결말 후보는 잠글 수 있지만 변경 가능하게 한다. 변경 시 영향을 받는 복선과 에피소드를 보여준다."
- 상태: **수용 완료** (2026-09-13)
- 커밋 여부: **uncommitted** (`manifest.json`의 `committed: false`)

## 계약 요약

- `Project.ending_intent` (TEXT NULL), `ending_locked` (BOOL NOT NULL default false), `ending_updated_at` (DATETIME NULL)
- `PATCH /projects/{pid}`: `ending_intent` 설정·명시적 지우기, `""` → null 정규화, 실제 변경 시에만 `ending_updated_at` 갱신, 동일 값 재저장 시 timestamp 유지
- 잠긴 결말 변경은 동일 요청에 `ending_locked: false`가 있어야 허용 (단일 PATCH로 해제+저장)
- `ending_locked: null` 명시 → 422 (DB 500 방지)
- `GET /projects/{pid}/ending-impact`: 파생·읽기 전용 — 미해결 복선(`status='설치'`), `ending_updated_at` 기준 잠재적 오래된 목표 회차, `series_finale` 목표 회차 + 각각의 ending_intent 보유 여부
- 자동 전파 없음 (작품 결말 → 회차 목표), 자동 완결·복선 판정 없음
- 프론트: PlanPage 결말 후보 섹션 — textarea·저장·잠금 토글·잠김 배지·영향 목록 3종, `['project',pid]`+`['ending-impact',pid]` 무효화, 프로젝트/서버값 변경 시 draft 리셋, 로딩 중 컨트롤 비활성

## 검증 결과 (검토 후 최종)

| 항목 | 결과 |
|------|------|
| backend focused (ending_impact + migrations + serial_state) | 27→**33 passed** |
| backend 전체 회귀 | **618 passed, 1 skipped**, 위반 0 |
| frontend ending-impact fixture | **6 passed**, tripwire no escapes |
| TypeScript | `TSC_EXIT=0` |
| 독립 검토 | backend·frontend 모두 **PASS_WITH_NOTES**, 지적 9건 반영·재검증 통과 |

기존 fixture 전종 회귀 green 유지 (chapter-goal 8, chapter-flow 10, preservation 26, ai-context 15, memory 31, serial-state 6, evidence-links 8, foreshadow-disposition 7, final-edition 6).

## 격리

- backend: 합성 TEMP SQLite만 사용, 운영 DB 접근 없음
- frontend: 전용 포트 15236 fixture 라우트만 사용, API tripwire 이탈 0
- 외부: 실제 provider·credential·유료 자원·배포 없음. migration은 로컬 구현·테스트만 (운영 적용은 별도 승인 경계)

## 범위 밖 / 명시 미결

- 운영 DB migration 적용, 배포, 실제 provider 연동 — 별도 승인 필요
- 결말 변경 시 회차 목표 자동 갱신·알림 — 의도적 비자동화 (파생 표시만)
- 선존 결함 G-045 (`create_foreshadow`가 `audience_knows`를 받지만 미영속) — 본 슬라이스 범위 밖, 원장에 기록 유지
