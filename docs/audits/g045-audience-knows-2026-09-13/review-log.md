# G-045 독립 검토 기록 — foreshadow POST audience_knows 유실 수정

- 슬라이스: G-045 (선존 결함 최소 수정)
- 검토일: 2026-09-13
- 검토자: 독립 subagent 1건 (`subagent_explore`)
- 판정: **PASS**

## 검토자 확인 요약

- `ForeshadowCreate` 스키마의 모든 필드가 `Foreshadow()` 생성자에 매핑됨 — 추가 누락 없음.
- 다른 쓰기 경로 없음: PATCH는 `model_dump(exclude_unset=True)` + `setattr` 루프로 `audience_knows` 포함 전 필드 갱신.
- 응답은 commit+refresh된 영속 행을 직렬화 — 저장값과 응답값의 불일치 가능성 없음.
- 프론트 `audience_knows` 필드명·응답 직렬화 일치 — 생성 폼 체크박스가 이미 값을 전송 중이었으므로 실제 사용자 대상 데이터 유실이었음 확인.
- 회귀 테스트 단정이 영속성(commit 후 재조회 경로)을 실제로 검증.

## 지적 처리표

| # | 심각도 | 지적 | 처리 |
|---|--------|------|------|
| 1 | NOTE | fixture 목이 `audience_knows`를 이미 충실히 재현 — 실구현보다 관대해 e2e가 결함을 못 잡은 유형(mock drift) | **수용** — 이번에 fixture에 POST 라우트 + 실제 본문 검증(`posts[0].audience_knows is true`)을 추가해 drift 폭을 좁힘. 근본적 mock drift는 fixture 아키텍처의 알려진 한계 |
| 2 | NOTE | AI 후보 "등록" 버튼이 폼의 `audienceKnows` 체크박스 상태를 상속 — 후보별 독립 값이 아님 | **수용** — 선존 UX 의미 문제(버그 데이터 유실 아님). 별도 후보로 기록 |
| 3 | NOTE | `bootstrap.py`의 미사용 `Foreshadow` import | **수정** — 이번 슬라이스에서 제거(인접 위생) |

## 재검증

- focused: `test_foreshadow_disposition.py` + `test_foreshadows_canon.py` **24 passed**
- 전체 회귀: **677 passed / 1 skipped / violations 0 / warnings 0**
- 프론트: `foreshadow-disposition` fixture **8/8 passed**, tripwire no escapes, `tsc` exit 0

## 판정 근거

차단 결함 없음. 수정이 결함의 근본 원인(생성자 인자 누락)을 정확히 다루고, 회귀 테스트가 영속 저장·기본값·UI 왕복을 모두 고정. NOTE는 정보성·선존 관찰이며 1건은 함께 정리.
