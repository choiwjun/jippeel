# QA 개발 검증 리포트

> **작성**: QA팀 (6단계) — 검증 실행은 QA 세션 + 최종 집계는 표준 파이프라인 코디네이터가 보조
> **검증일**: 2026-08-25
> **대상**: backend/ (Sprint 1~3), frontend/ (Sprint 4a·4b), 요구사항_정의서.md 수용 기준

---

## ① 종합 판정: **✅ 통과 — MVP 출시 가능**

백엔드 전수 테스트, 프론트 타입체크·빌드, 소스 동기 무결성, 런타임 스모크 모두 통과.
차단 결함(Critical) 0건.

---

## ② 결과 요약

| 영역 | 검증 | 결과 |
|------|------|------|
| 백엔드 | `backend/.venv/bin/python -m pytest -q` | **97 passed** (단위+통합, 프라그마·암호화 왕복·게이트 경계값 포함) |
| 프론트 | `tsc --noEmit` + `npm run build` | 타입 오류 0, 빌드 성공(≈4.4s) |
| 동기 무결성 | ~/jippeel-build ↔ /mnt/c 프로젝트 폴더 src diff | **완전 일치** |
| 런타임 스모크 | uvicorn 기동 → 프로젝트 생성→회차 생성→본문 저장→윤문 mock 실행→플로우 | 정상 (QA 세션 실측) |

### 윤문 게이트(FR-505) 실측
- QA mock이 정량블록 포함 입력을 그대로 출력 → 변경률 80%로 **게이트 차단 발동**
- 이는 코드 결함이 아니라 mock 한계이며, **50% 초과 차단 로직이 실제 동작함을 입증** (im-not-ai 철칙 #4 준수)

---

## ③ Must 수용기준 표본 대조

| 수용 기준 (요구사항 §7) | 근거 | 판정 |
|--------------------------|------|------|
| api_key 평문 노출 없음 (NFR-202) | crypto.py 암호화 저장 + 응답 스키마 미포함 + test_crypto 왕복 테스트 | ✅ |
| 변경률 게이트 동작 (FR-505) | 80% mock → blocked 반환 실측 | ✅ |
| 공백 제외 글자 수 (FR-104) | wordcount 단위 테스트 + S2 실시간 카운터 구현 | ✅ |
| 회차 CRUD·본문 저장 (FR-101~103) | test_chapters_api 통과 | ✅ |
| 로어북 키워드 검색 (FR-304) | FTS5 + /search 구현·테스트 | ✅ |
| SSE 스트리밍 (FR-405) | fetch 스트림 소비(aiStream.ts) + 에러경로 3종 SSE 이벤트 테스트 | ✅ |
| 자동 삽입 금지 (P1/FR-406) | AiPanel 3버튼(끼워넣기/선택교체/복사)만 구현 | ✅ |

---

## ④ 발견 결함

### Critical
없음

### Major
없음

### Minor / 후속 확인 — ✅ 전건 해소 (2026-08-26 후속 검증)

1. **sendBeacon 언로드 플러시** → **결함으로 확정 후 수정**. sendBeacon은 POST 고정인데 백엔드는 PUT만 존재해 플러시가 항상 405로 실패하고 있었음. `POST /chapters/{id}/content` 별칭 라우트 추가 + 테스트(`test_post_content_beacon_alias_matches_put`)로 해소
2. **Python 3.14 + starlette TestClient 경고** → 현재 버전 조합(3.14.4)에서 재현 안 됨(전체 스위트 -W default 통과). 종결
3. **vite 청크 크기 경고** → manualChunks 분리(react-vendor/editor/markdown)로 경고 제거

### 후속 검증에서 추가 발견·수정 (2026-08-26)

- **humanize.run_subprocess 인코딩 결함(Windows)**: text=True가 시스템 로캘(cp949)로 디코딩해 한글 출력에서 UnicodeDecodeError → verify_gates 실패. `encoding="utf-8", errors="replace"` 명시로 수정 (WSL에선 무증상이던 크로스플랫폼 결함)
- **E2E 재실행**: Windows 네이티브 환경(가짜 LLM :1234 + refine 스텁 + Chromium) 신규 구축 후 **6/6 passed**

---

## ⑤ MVP 출시 가능 여부

**가능.** 남은 Minor 항목은 운영 중 점진 처리 가능.
파이프라인 1~6단계 전체 완료: 요구사항(승인) → 리서치(부록01~05) → 기획(v0.3) → 디자인(v1.1+프로토타입) → 개발(S1~4) → QA(본 리포트).

---
*QA팀 최종 보고 — 2026-08-25*
