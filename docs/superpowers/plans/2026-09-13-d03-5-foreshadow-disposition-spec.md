# D03-5 좁은 사양 — 복선 이관 구분(disposition)

날짜: 2026-09-13 / 부모: [전체 실행 계획](2026-09-13-project-wide-execution-plan.md) §6.2 "이관: 해결 / 의도적 미해결 / 외전 이관의 구분 표시"

## 1. 배경

- `Foreshadow.status`는 `설치|회수|보류`(모델 `ck_foreshadow_status`, 고도화 G-020).
- 설치=미해결, 회수=해결됨, 보류=유예 — 그러나 **왜** 닫혔는지(본편에서 해결 / 의도적으로 미해결로 남김 / 외전으로 이관)는 표현되지 않는다.
- 본 슬라이스는 그 구분 라벨 `disposition`만 추가한다. 자동 판정 없음 — 작가가 명시적으로 지정한다.

## 2. 데이터 계약

`foreshadows.disposition` — `TEXT NULL`, CHECK `disposition IN ('resolved','intentional_unresolved','side_story')`, 제약명 `ck_foreshadow_disposition`.

| 값 | 의미 |
|----|------|
| `resolved` | 본편에서 해결됨 |
| `intentional_unresolved` | 의도적 미해결(열린 결말 등) |
| `side_story` | 외전 이관 — 본편에서 더 회수하지 않고 외전으로 넘김 |
| NULL | 미분류 |

**불변조건**: `status='설치'`이면 `disposition IS NULL`. (설치=아직 회수 안 된 복선에 처분 라벨은 모순.)

- disposition은 `status='회수'`·`'보류'`에서만 설정 가능. 어느 status에 둘지는 작가 판단(외전 이관을 회수로 보든 보류로 보든).
- disposition은 status와 별개 수명주기가 아니라 닫힘 상태의 수식어다.

## 3. API 계약

### POST /projects/{pid}/foreshadows
- `ForeshadowCreate.disposition: Literal[...] | None = None`.
- `status='설치'` + disposition non-null → **422**.
- 허용되면 그대로 저장.

### PATCH /foreshadows/{fid}
- `ForeshadowUpdate.disposition` — `exclude_unset` 의미론 유지: 필드 생략=불변, 명시적 `null`=해제, 값=설정.
- 패치 적용 후의 (status, disposition) 결과가 `status='설치'` + disposition non-null이면 **422** — 아무 필드도 쓰지 않는다.
- 즉 `status:'설치'`로 되돌리려면 같은 요청에 `disposition:null`을 함께 보내거나 먼저 해제해야 한다(자동 해제 없음 — 명시적).
- 사전 외 disposition 값 → 422(Literal).

### GET /projects/{pid}/foreshadows
- `disposition` 쿼리 파라미터(선택) — 사전 외 값 422, 지정 시 해당 disposition만.
- 기존 `status_filter`와 AND 조합.

### ForeshadowOut
- `disposition: str | None` 노출.

## 4. migration·가드

- migration `6a7b8c9d0e14` (down_revision `5f6a7b8c9d03`): `batch_alter_table("foreshadows")`로 `disposition` 컬럼 + `ck_foreshadow_disposition` 추가. 테이블 재작성이므로 `PRAGMA foreign_keys=OFF/ON`으로 감싼다(기존 chapters 패턴). populated upgrade는 기존 행 보존(disposition NULL), downgrade는 제거.
- `database.py`: `ALEMBIC_HEAD="6a7b8c9d0e14"`, 스키마 가드에 `disposition` 컬럼 + 제약명 확인 추가.

## 5. 프론트 계약

- `Foreshadow.disposition?: 'resolved'|'intentional_unresolved'|'side_story'|null` (ForeshadowsPage 로컬 타입 확장).
- 목록 행: status 옆에 disposition 배지 — `해결` / `의도적 미해결` / `외전 이관`.
- 행의 disposition select(미분류/해결/의도적 미해결/외전 이관): `status='설치'`이면 disabled. 변경 시 PATCH `{disposition}` 또는 `{disposition:null}`.
- status select로 `'설치'`를 고르고 그 행에 disposition이 있으면, 한 번의 PATCH로 `{status:'설치', disposition:null}`을 보낸다(클릭 한 번 UX 유지 + 불변조건 충족).
- 성공 시 `['foreshadows', pid]` 무효화(기존 패턴), 실패 시 toast.

## 6. 테스트

### 백엔드(합성 TEMP DB)
- 생성: 설치+disposition→422, 회수+resolved→201·Out에 노출, disposition 생략→NULL.
- PATCH: 보류 행에 disposition 설정→200, 설치 행에 disposition→422, disposition 있는 행을 status:'설치'로만→422·원래값 보존, `{status:'설치',disposition:null}`→200·둘 다 적용, `disposition:null` 단독→해제, 사전 외 값→422.
- 목록 disposition 필터 + 잘못된 값 422.
- migration: populated upgrade 행 보존·컬럼·제약 존재·위반 INSERT 거부, downgrade 컬럼·제거.
- 보존: 기존 foreshadow API 테스트 회귀.

### 프론트 fixture(포트 15234)
- disposition 배지 렌더링(각 값 + 미분류 비표시).
- disposition select → PATCH 본문 계약(`{disposition:'side_story'}` / `{disposition:null}`).
- status='설치' 행의 disposition select disabled.
- disposition 있는 행을 설치로 변경 → 단일 PATCH `{status:'설치',disposition:null}`.
- 목록 필터 버튼/쿼리는 기존 status 필터 유지(회귀).
- axe serious/critical 위반 0.

## 7. 범위 밖

- disposition 자동 추론·AI 판정(금지, §6.3).
- 외전 작품과의 실제 링크/이동(외전 이관은 라벨만).
- reminder·AI 컨텍스트 주입 로직 변경 없음(설치만 미회수로 주입되는 기존 동작 유지).
- 운영 DB migration·배포·커밋 — 별도 승인.
