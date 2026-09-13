# 관리 데이터 무결성 후보 재현 보고서

- 일자: 2026-09-09
- 범위: `docs/handoffs/2026-09-08-remaining-work.md` §2~§3의 7개 후보
- 실행: 새 Windows TEMP SQLite + FastAPI `TestClient`
- 운영 DB/기존 서비스/점유 포트: 사용하지 않음
- 앱 소스: 수정하지 않음
- 재현 harness: `.eval_tmp/management_integrity_repro.py` (커밋 대상 아님)

## 실행 명령

```text
cd backend
.venv/Scripts/python.exe ../.eval_tmp/management_integrity_repro.py
```

실행은 exit 0으로 끝났고, TEMP DB cleanup도 완료됐다.

## 결과

| 후보 | 결과 | 관찰된 증상 | 영향 |
|---|---|---|---|
| 타 작품 장면 reorder | **재현** | A 회차 reorder 요청에 B 회차 scene ID를 넣어도 200. B scene의 `sort_order`가 1 → 9로 변경됨 | 타 작품 데이터 변조 |
| 타 작품 회차를 복선에 참조 | **재현** | 작품 A 복선이 작품 B 회차를 `planted_chapter_id`로 저장하고 201 반환 | 잘못된 cross-project 참조 |
| 관계가 있는 인물 삭제 | **재현** | DELETE가 500. 관계 행은 남아 있음 | 사용자가 예측할 수 없는 삭제 실패/관계 잔존 |
| 복선에 연결된 회차 삭제 | **재현** | DELETE가 500. 회차와 복선 참조가 모두 남아 있음 | 삭제 정책 부재 및 API 500 |
| 회차 없는 작품 reminder | **미재현** | 200, `latest_chapter: null`, `items: []` 반환 | 후보 종료 가능 |
| 작품별 FTS 검색 + limit | **재현** | 작품 B에 일치 항목이 있어도 `limit=1`에서 빈 배열 반환 | 다른 작품 hit가 limit을 소모 |
| `volume: null` 이동 | **재현** | `volume=1` 회차에 `volume: null`을 보내도 200 후 volume=1 유지 | 평면 회차로 이동 불가 |

## 현재 코드에서 확인한 최소 원인

1. `backend/app/routers/scenes.py`의 reorder 조회가 scene ID만 전역으로 조회하고 요청 회차 소속을 조건에 포함하지 않는다.
2. `backend/app/routers/foreshadows.py`의 `_validate_chapter_refs()`가 회차 존재만 확인하고 작품 소속을 확인하지 않는다.
3. `backend/app/routers/characters.py`의 캐릭터 삭제가 `relationships` 정리 또는 명시적 충돌 응답 없이 바로 삭제한다.
4. `backend/app/routers/projects.py`의 회차 삭제가 `Foreshadow` 참조 정책 없이 삭제를 시도한다. 현재 nullable FK 참조가 500으로 표면화된다.
5. `backend/app/routers/lorebook.py`의 FTS 검색은 전역 ID에 먼저 `limit`을 적용한 뒤 project filter를 적용한다.
6. `backend/app/routers/projects.py`의 reorder는 `item.volume is not None`일 때만 대입하므로 JSON `null`이 “미지정”과 구분되지 않는다.

## 첫 수정 범위 제안

이번 첫 수정은 **관리 CRUD의 cross-project 격리와 삭제/이동 계약**으로 제한한다.

- scenes reorder: 요청 회차 소속 검증 + 외부 ID 422 + 원자성 회귀 테스트
- foreshadow refs: planted/resolved 회차가 같은 project인지 검증 + 422 회귀 테스트
- character delete: 관계 삭제 또는 명시적 409 정책 중 하나를 결정하고 회귀 테스트
- chapter delete: foreshadow 참조의 보존/해제/삭제 정책을 결정하고 500 없는 계약과 회귀 테스트
- null volume: `null`을 명시적 평면 회차 이동으로 표현할 수 있는 API 계약과 회귀 테스트
- FTS limit: project scope를 먼저 적용한 뒤 limit하는 검색 계약과 회귀 테스트

`empty_project_reminder`는 현재 재현되지 않았으므로 이번 수정 범위에서 제외한다.

## 재현 증거 상세

TEMP DB 한 번의 실행에서 나온 핵심 관찰값이다. ID는 TEMP DB 내부 식별자이며 운영 데이터와 무관하다.

- **scene reorder:** response `200`; 외부 scene의 `sort_order` `1.0 → 9.0`. 기대는 `422`와 외부 scene 보존이다. 코드 위치: `backend/app/routers/scenes.py:75-96`.
- **foreshadow cross-project:** 작품 A의 foreshadow에 작품 B chapter `id=3`을 저장하고 response `201`. 코드 위치: `backend/app/routers/foreshadows.py:201-205`.
- **character delete:** DELETE response `500` (`Internal Server Error`); 관계 `id=1`은 이후 GET에서 `200`으로 남았다. 코드 위치: `backend/app/routers/characters.py:95-99`.
- **chapter delete:** DELETE response `500`; 대상 chapter가 남고, foreshadow `id=2`와 `planted_chapter_id=4`도 남았다. 코드 위치: `backend/app/routers/projects.py:270-274` (`delete_chapter`), `backend/app/models.py:140-143` (`planted_chapter_id`/`resolved_chapter_id`의 `ForeignKey("chapters.id")`, `ondelete` 미지정).
- **empty reminder:** response `200`, `latest_chapter=null`, `items=[]`; 이번 후보는 종료한다. 코드 위치: `backend/app/routers/foreshadows.py`의 `foreshadow_reminder`.
- **project-scoped FTS:** 작품 B target lore `id=2`가 존재하지만 `limit=1` 검색 response `200`의 returned IDs는 `[]`. 코드 위치: `backend/app/routers/lorebook.py:61-80`.
- **null volume:** reorder response `200` 뒤 대상 chapter `volume`이 `1`로 유지됐다. 기대는 `null`. 코드 위치: `backend/app/routers/projects.py:278-307`.

현재 기준 커밋은 `fccade5`이며, 이 보고서는 해당 checkout에서 실행했다. 재현 명령은 위 실행 명령과 동일하다.

## 승인 및 구현 상태

6개 결함의 삭제 정책과 API 응답 코드가 승인되어 회귀 테스트 우선 작성 후 최소 구현을 완료했다. 아래 수정 및 재검증 결과를 참조한다.

## 수정 및 재검증 결과

승인된 정책(`cross-project=422`, 참조가 있는 삭제=`409`, FTS scope 선행, 명시적 `volume:null`)에 따라 최소 수정했다.

### 변경 파일

- `backend/app/routers/scenes.py` — reorder 조회에 `Scene.chapter_id == cid` 소속 조건 추가
- `backend/app/routers/foreshadows.py` — planted/resolved 회차의 project 소속 검증
- `backend/app/routers/characters.py` — 관계가 있는 캐릭터 삭제를 `409`로 거부하고 관계 보존
- `backend/app/routers/projects.py` — 복선 참조 회차 삭제를 `409`로 거부; `volume:null` 명시 여부 반영
- `backend/app/services/fts.py` / `backend/app/routers/lorebook.py` — FTS project scope를 적용한 뒤 limit
- `backend/tests/` — 6개 회귀 테스트 추가

### 검증

- 관련 API 테스트: **52 passed**
- 백엔드 전체 pytest: **275 passed**
- 수정 후 격리 관리 무결성 harness: **7개 후보 모두 `candidate_reproduced: false`**
  - 6개 수정 후보: 422/409 또는 올바른 scoped 결과/null 이동 확인
  - empty reminder: 기존부터 정상 200 유지
- 프론트 production build: **통과** (`tsc -b && vite build`)
- build 경고: 기존 `vite.config.ts` duplicate `build` key 1건

운영 DB·기존 서비스·운영 키는 사용하지 않았다.


## 후속 P1 수정 및 오케스트레이션 QA 상태

독립 리뷰에서 추가로 발견된 `category + limit` 결함을 수정했다. FTS 경로도 project/category 조건을 SQL에 포함한 뒤 `LIMIT`을 적용하며, LIKE fallback 경로의 기존 scope/limit 동작은 유지된다.

- category+limit 단일 회귀: **1 passed**
- lorebook 테스트: **12 passed**
- 백엔드 전체 safe runner: **276 passed**, 기존 anyio deprecation warning 1건
- 관리 무결성 격리 harness: **7개 후보 모두 `candidate_reproduced: false`**
- `fts.py`의 table alias/MATCH 문법 우려: 동일 native safe runner에서 실제 category+limit 회귀 및 전체 suite가 통과해 재현되지 않음

전역 Orca orchestration으로 구현·review·QA Task를 추적했다. 구현 Task는 완료됐고, clean 독립 review Task는 PASS했다. 이전 broad/FTS-only review의 BLOCKED/failed 기록은 워커 범위·환경 문제로 남겨 두되, clean review가 현재 review gate를 대체한다. 분리 QA Task의 backend/harness 결과와 부모의 frontend build 결과를 recovery provenance로 기록해 QA acceptance를 완료했다.

- clean review: lorebook **12 passed**, patch-scoped findings 없음
- backend QA: **276 passed**, 기존 anyio warning 1건
- harness QA: 7개 후보 모두 `candidate_reproduced: false`
- frontend QA: `npm run build` **exit 0**, 기존 duplicate `build` key warning 1건
