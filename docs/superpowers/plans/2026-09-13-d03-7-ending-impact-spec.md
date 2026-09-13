# D03-7 좁은 사양 — 결말 후보·변경 영향(ending impact)

날짜: 2026-09-13 / 부모: [전체 실행 계획](2026-09-13-project-wide-execution-plan.md) §6.2 · 근원: [관리 감사](../../audits/소설집필_관리_감사.md) §8.5-2 "결말 후보는 잠글 수 있지만 변경 가능하게 한다. 변경 시 영향을 받는 복선과 에피소드를 보여준다."

## 1. 배경

- D01이 회차 목표(`ending_intent` 필드 포함)를, D03-5가 복선 처분을 수용했으나 **작품 수준의 결말 후보**는 어디에도 없다.
- 작가가 결말을 바꾸면 이미 쓴 목표·열린 복선 중 무엇이 영향을 받는지 볼 수단이 없다 — 변경 시각 이전에 저장된 목표는 옛 결말 가정으로 쓰였을 수 있다.
- 본 슬라이스는 작품 수준 결말 후보의 저장·잠금·변경 기록과 **파생 영향 표시**만 추가한다. 자동 재검토·자동 판정 없음.

## 2. 데이터 계약

`projects`에 3개 컬럼 추가:

| 컬럼 | 타입 | 비고 |
|------|------|------|
| `ending_intent` | TEXT NULL | 작품 수준 결말 후보(회차 목표의 ending_intent와 별개) |
| `ending_locked` | BOOLEAN NOT NULL DEFAULT false | 잠금 — 실수로 바꾸지 않도록 하는 플래그 |
| `ending_updated_at` | DATETIME NULL | ending_intent **값이 실제로 바뀐** 마지막 시각 |

## 3. API 계약

### PATCH /projects/{pid} (기존 엔드포인트 확장)

`ProjectUpdate`에 `ending_intent: str | None`, `ending_locked: bool | None` 추가(생략 시 불변 — exclude_unset 의미론).

- `ending_intent` 키가 있고 **현재값과 다르면** → 저장 + `ending_updated_at=now`. 동일값이면 시각 갱신 없음.
- 명시적 `ending_intent: null`은 지우기 — 값이 있었으면 변경으로 간주해 시각 갱신.
- **`ending_locked=true` 상태에서** `ending_intent`가 실제로 바뀌는 요청이고 같은 요청에 `ending_locked:false`가 없으면 → **409** "결말이 잠겨 있습니다". (잠금은 실수 방지지 변경 금지가 아님 — 해제를 한 요청에 포함하면 허용.)
- 잠긴 상태에서 `ending_intent`가 **현재값과 동일**한 요청은 변경이 아니므로 허용.
- `ending_locked`만 있는 요청은 잠금 토글만 수행.

### GET /projects/{pid}/ending-impact → `EndingImpactOut`(파생·읽기 전용)

```jsonc
{
  "ending_intent": "주인공은 고향으로 돌아간다",
  "ending_locked": true,
  "ending_updated_at": "… | null",
  "open_foreshadows": [                      // status='설치' — 결말이 답해야 할 미해결 복선
    {"id": 3, "title": "검은 검"}
  ],
  "stale_goal_chapters": [                   // 목표 존재 && goal.updated_at < ending_updated_at
    {"chapter_id": 5, "title": "7화", "goal_version": 2}
    // 결말 변경 이전에 저장된 목표 — 옛 결말 가정으로 쓰였을 수 있음
  ],
  "finale_chapters": [                       // episode_purpose='series_finale' 목표를 가진 회차
    {"chapter_id": 9, "title": "최종화", "has_ending_intent": true}
  ]
}
```

- `ending_updated_at`이 NULL이면 `stale_goal_chapters`는 항상 [](비교 기준 없음).
- 전부 파생 사실 — 영향 "판정"·우선순위·자동 재작성 지시 없음.
- 404: 프로젝트 없음.

### ProjectOut

- `ending_intent: str | None`, `ending_locked: bool`, `ending_updated_at: datetime | None` 노출.

## 4. migration·가드

- migration `8c9d0e1f2636` (down_revision `7b8c9d0e1f25`): `batch_alter_table("projects")`로 3개 컬럼 — 기존 행은 NULL/false 보존, downgrade는 제거+행 보존. projects 재작성이므로 `PRAGMA foreign_keys=OFF/ON` 래핑(기존 패턴).
- `database.py`: `ALEMBIC_HEAD="8c9d0e1f2636"`, 스키마 가드에 3개 컬럼 확인 추가.

## 5. 프론트 계약

- PlanPage에 **결말 후보** 섹션 추가:
  - textarea + `저장` 버튼 → PATCH `{ending_intent}`(빈 값은 null로 전송).
  - 잠금 토글 → PATCH `{ending_locked}`.
  - 잠긴 상태면 textarea disabled + "잠김" 배지; 저장하려면 먼저 잠금 해제(프론트는 `{ending_locked:false, ending_intent}` 단일 PATCH로 해제+저장).
  - `ending_updated_at` 표시.
  - **변경 영향** 표시: 미해결 복선 제목, 오래된 목표 회차(제목+goal_version), 최종화 회차(ending_intent 유무).
- React Query: `['ending-impact', pid]`; 프로젝트 PATCH 성공 시 `['project', pid]` + `['ending-impact', pid]` 무효화.
- fixture: 포트 **15236**, `playwright.ending-impact.config.ts` + `e2e/ending-impact.spec.ts`.

## 6. 테스트

### backend (`test_ending_impact.py`)

- PATCH: ending_intent 설정→updated_at 기록 / 동일값 재전송→시각 불변 / 다른 값→시각 갱신 / 명시적 null 지우기 / 잠금 후 ending_intent 변경→409 / 잠금+해제 동시 PATCH→200 / 잠긴 상태 동일값 전송→200(비변경) / ending_locked만 토글 / ProjectOut 노출.
- impact: open 복선만 나열(회수·보류 제외), stale_goal_chapters(결말 변경 전후 목표 저장 대조), finale_chapters + has_ending_intent, ending_updated_at NULL이면 stale 빈 목록, 프로젝트 없음 404, 파생 읽기만(상태 불변).
- migration: populated upgrade 보존(NULL/false) + downgrade 컬럼 제거·프로젝트 행 보존.

### frontend fixture (`ending-impact.spec.ts`)

- 결말 후보 저장 → PATCH 본문 단정, updated_at 표시.
- 잠금 토글 → PATCH `{ending_locked:true}`, textarea disabled + 잠김 배지.
- 잠긴 상태 저장 → 단일 PATCH `{ending_locked:false, ending_intent}`.
- 영향 표시: 미해결 복선·오래된 목표 회차·최종화 회차 렌더.
- axe serious/critical 0.

## 7. 금지·범위 밖

- 결말 변경 시 목표·복선의 자동 재검토·자동 표시 금지(파생 사실 나열만).
- 회차 목표 ending_intent와 작품 결말 후보의 자동 동기화 없음.
- 운영 DB·실제 provider·credential·배포 없음.
