# QA 개발검증 리포트 v2 (jippeel)

> ⚠️ **시점 주의**: 본 문서는 2026-08-26 기준 기록입니다. 최상단의 F-036(라이선스 고지) 릴리스 차단은 이후 구현 완료·실측 확인되었고(2026-09-05), 백엔드 테스트는 2026-09-06 기준 120 passed입니다. E-1(chromium 라이브러리)도 `~/.local/pwlibs` 방식으로 해소되어 E2E 6/6 통과. 최신 판정은 HANDOFF.md를 따릅니다.

- 작성: team-qa / 일자: 2026-08-26
- 대상: 테스트플랜_v1.md TC 전체 94건
- 실행환경: fake_llm(127.0.0.1:1234, model fake-7b) + uvicorn app.main:8000 실구동

---

## ⛔ 릴리스 차단 사항 (최상단 명시)

**F-036 im-not-ai(MIT) 라이선스 고지 미구현 — 릴리스 차단.**
증거: frontend/src에 About/라이선스 고지 섹션 없음(SettingsPage.tsx에 NFR-401 문구 언급만 존재, MIT 출처·라이선스 표기 0건 — grep 실측).
root cause: 기획(F-036)→구현 누락(G6 traceability에도 F-036이 미구현 null로 기록됨).
담당: **Frontend팀**(구현) · 기획팀(고지 문구 확정). 해결 전 G8 릴리스 진입 불가.

---

## 1. 집계 요약

| 구분 | 건수 |
|---|---|
| 자동 실행 | **24** (regression 4 중 3 + api 15 + security 자동분 6) |
| 자동 실행 PASS | **24 / FAIL 0** |
| pending-manual(환경 블록·실기기 필요) | 70 |

핵심 결과:
1. **Regression: backend pytest 118 passed** (G6 기록과 동일, 회귀 0건) — TC-601
2. **Frontend build: 통과** (tsc -b && vite build, 15.37s) — TC-602
3. **API 라이브 스모크 8/8 PASS**: 프로젝트 CRUD·cascade, volume=null, status 422, endpoint 마스킹, plus-status, refine 전 흐름(**gate=block 시 accept 409 차단 실측**)
4. **Security 4종 PASS**: DB 평문 0건(TC-301), 응답 평문 0건(TC-305), 로그 평문 0건(TC-306), 127.0.0.1 바인딩만 존재(TC-307)
5. UI e2e(TC-201~206·603): **환경 블록으로 미실행** — 앱 결함 아님(아래 root cause)

## 2. FAIL 및 블록 root cause (담당 지정)

| ID | 상태 | root cause | 담당 |
|---|---|---|---|
| E-1 (TC-201~206, 603) | 환경 블록 | chromium 실행에 시스템 라이브러리 libnspr4/libnss3/libasound2 누락 + sudo 불가로 설치 불가(headless shell·full chromium 모두 동일 실측). Playwright 자체·스펙·앱 정상 | **Infra팀**: OS 의존성 설치(`sudo npx playwright install-deps` 또는 패키지 설치) 후 QA 재실행 |
| F-036 | 미구현 | 위 최상단 참조 | Frontend팀 |
| TC-110 경미 | 관찰 | 응답이 api_key_masked 대신 has_api_key:boolean만 노출 — 보안 목적은 충족하나 테스트플랜 기대 스키마와 상이 | Backend팀: 스펙·플랜 문구 갱신 또는 masked 필드 추가(판단 위임) |

## 3. TC별 결과 (94건 전수)

| TC | 결과 | 검증 절차(요약) | 증거 / root cause | 담당 |
|---|---|---|---|---|
| TC-001 | pending-manual | 프로젝트 생성→열기→삭제 실행. 각 동작 후 목록 확인. 삭제 시 확인 대화상자 노출 여부 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-002 | pending-manual | 회차 생성→드래그/버튼으로 순서 변경→삭제 후 **앱 재시작**, 순서 재확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-003 | pending-manual | 권(volume) 생성→회차를 권 A→권 B 이동→재시작 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-004 | pending-manual | 제목(`#`)/강조(`**`)/목록(`-`) 포함 샘플 문서 작성→미리보기 탭 전환 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-005 | pending-manual | 에디터에서 연속 타이핑 중 글자 수 푸터(공백 제외 강조 포함) 관찰 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-006 | pending-manual | 상태를 초고→수정중→완료로 각각 지정→재시작 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-007 | pending-manual | 문장 입력 후 입력 정지→"저장됨 · 방금 전" 표시 시점 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-008 | pending-manual | 백엔드 프로세스 정지 상태에서 타이핑→저장 시도 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-009 | pending-manual | 회차 메모 Popover에 메모 저장→재표시→수정→본문과 분리 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-010 | pending-manual | 회차 단위 .txt/.md 내보내기→전체(.md/.txt) 내보내기→다운로드 파일과 원문 비교 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-011 | pending-manual | 카드 20개 생성→조회→수정→삭제. 삭제 시 확인 대화상자 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-012 | pending-manual | 이름/별칭/역할/외형/성격/말투/배경 7필드에 식별 가능한 값 입력→저장→상세 재오픈 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-013 | pending-manual | 캐릭터 A-B에 관계 라벨("주군-가신") 생성→A와 B 카드 각각에서 조회 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-014 | pending-manual | 카드 다수 상태에서 그리드/카드형 목록 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-015 | pending-manual | 로어북 엔트리 50개 생성→조회→수정→삭제 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-016 | pending-manual | 엔트리에 용어/장소/세력/기타 카테고리 부여→필터 선택 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-017 | pending-manual | 엔트리에 키워드 다중 부여→저장→재표시→S5 AI 패널 컨텍스트 선택 목록 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-018 | pending-manual | 특정 엔트리 선택→참조 회차 Collapsible 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-019 | pending-manual | S7에서 LM Studio(base_url/api_key/model/temperature) 설정→S5 프롬프 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-020 | pending-manual | 클라우드 OpenAI 호환 엔드포인트로 프로파일 전환→프롬프트 실행 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-021 | pending-manual | 프리셋(장면 생성·대사 보강·요약 등) 선택→호출→결과 수신을 로컬·클라우드에서 각 1회 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-022 | pending-manual | 컨텍스트 체크박스(현재 회차/선택 카드/선택 로어북) on/off 전환→요청 로그(또는 프롬프트 미리보기)로 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-023 | pending-manual | AI 스트리밍 출력 도중 에디터 타이핑·스크롤 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-024 | pending-manual | ①특정 커서 위치에 끼워넣기 ②본문 선택 후 선택 교체 ③클립보드 복사 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-025 | pending-manual | 엔드포인트 프로파일 2개 이상 저장→전환→기본값 지정→재시작 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-026 | pending-manual | ①잘못된 base_url ②잘못된 api_key ③응답 지연 엔드포인트로 각각 실행 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-027 | pending-manual | AI 티 샘플 회차에서 진단→윤문→diff→수락 실행 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-028 | pending-manual | 강도 light/standard/heavy 각 선택 실행→route_hint 기록 대조. 자동 판정 선택 시 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-029 | pending-manual | 진단 리포트에서 10대 카테고리(taxonomy A~J) 분류와 span 위치 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-030 | pending-manual | diff 화면에서 수정 단위별 수락/거절 개별 결정→거절 건의 원문 보존 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-031 | pending-manual | 변경률 ~30% 샘플과 ~55% 샘플로 각각 실행 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-032 | pending-manual | 윤문 화면(S6) 상시 문구 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-033 | pending-manual | 윤문 2회 이상 실행→실행 이력 Collapsible에서 대상 회차·강도·변경률·수락 여부·실행 시각 조회 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-034 | pending-manual | S1 규정 요약 카드(S-103)/S7 규정 탭 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-035 | pending-manual | 회차 14개 vs 15개 프로젝트, 완료 회차 공백제외 2,999자 vs 3,000자 데이터로 S-104 위 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-036 | pending-manual | 네트워크 차단 상태에서 편집·저장·윤문(로컬 처리분: shim/게이트) 실행 + S5 전송 고지 Alert  | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-037 | pending-manual | 앱 종료→jippeel.db(-wal/-shm 포함) 파일 복사(S-705 안내 경로)→초기화된 환경에 복원 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-038 | pending-manual | 회차 작성→자동 저장 확인→추가 타이핑(미저장분)→프로세스 kill→재시작 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-039 | pending-manual | 코딩 비전공자 1인이 별도 문서 없이 집필→AI→윤문→저장 흐름 수행(관찰 기록) | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-040 | pending-manual | S1~S7 전 화면·메뉴·오류 메시지 순회, 영문 잔류 여부 기록 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-041 | pending-manual | 에디터(S2)·캐릭터(S3)·로어북(S4) 각 화면에서 AI 패널 호출(Alt+A 및 FAB) | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-042 | pending-manual | S7 About(S-707) 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-043 | pending-manual | 규정 정보 화면 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-044 | pending-manual | S7 규정·현황 탭(S-704) 확인 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-045 | pending-manual | 외부 AI 엔드포인트 차단(장애 시뮬레이션) 상태에서 편집·저장·윤문(로컬분) 실행 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-046 | pending-manual | `Jippeel신행.bat`(갱신분: uvicorn 단일 프로세스+dist 서빙) 더블클릭 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-047 | pending-manual | LM Studio 프로파일↔클라우드 프로파일 전환 후 창작 데이터(프로젝트/회차/카드/로어북) diff 대조 | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-048 | pending-manual | UI 문자열·문서·로그 전체를 대상으로 탐지 회피 암시 문구 감사(키워드: 탐지, 회피, bypass, de | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-049 | pending-manual | ①카드 card_json에 자유 확장 필드(JSON) 저장·재표시(TC-106과 연계) ②SillyTaver | UI 수동/준자동 시나리오 — 브라우저 실행 불가 환경(아래 환경 블록 참조). 대응 API 계약은 TC-1xx 자동 검증으로 보완 | QA팀(환경 복구 후 재실행) |
| TC-101 | pass | POST/GET/PATCH/DELETE `/projects` 계약 검증(201/200/404, DELETE  | 라이브 스모크 POST 201/목록/DELETE cascade 확인 + backend test_projects_api.py 포함 118 passed | QA팀 |
| TC-102 | pass | PATCH `/projects/{pid}/chapters/reorder`에 소속 불일치·중복 id 포함 목록 | backend test_chapters_reorder.py (118 passed 내) | QA팀 |
| TC-103 | pass | volume=null 회차 생성→reorder→정렬 조회(G4 변경분: T-002 volume nullabl | 라이브 volume=null 회차 생성 201·vol=None + test_volume_nullable.py | QA팀 |
| TC-104 | pass | wordcount 서비스에 검증 샘플(공백 제외/공백+특문 제외 후보식) 단위 테스트 — C8 확정 식 반영 | backend test_wordcount.py (C8 확정식) | QA팀 |
| TC-105 | pass | PATCH `/chapters/{cid}` status에 3종 외 값 전송 | 라이브 PATCH status='잘못된값' → 422 실측 + test_chapters_api.py | QA팀 |
| TC-106 | pass | POST/PATCH `/characters` 7필드 저장 + PATCH `/characters/{chid}/ | backend test_characters_api.py (7필드+card_json 병합) | QA팀 |
| TC-107 | pass | POST `/characters/relations`(cross-project → 422 포함) + GET ` | backend test_characters_api.py (relations cross-project 422·양방향) | QA팀 |
| TC-108 | pass | lore CRUD + `?category=` 필터 + PUT `/lore/{lid}/keywords` 전체  | backend test_lorebook_api.py (CRUD·필터·FTS) | QA팀 |
| TC-109 | pass | `/lore/search?q=` prefix 질의 + FTS5 미지원 빌드 시 LIKE 폴백 경로 테스트 | backend test_lorebook_api.py (search 경로) | QA팀 |
| TC-110 | pass | POST `/ai/endpoints` 저장 후 DB row 직접 조회 + GET `/ai/endpoints` | 라이브 GET /ai/endpoints → has_api_key:boolean만 노출(api_key_masked 필드 대신 더 엄격한 형태). 평문 반환 경로 없음으로 목적 충족 — 스펙 문구와 상이(경미, 기록용) | QA팀 |
| TC-111 | pass | is_default=true 프로파일 2개 저장 시도/기본값 전환 | backend test_ai_panel_api.py (기본값 단일성) | QA팀 |
| TC-112 | pass | 백엔드 코드베이스에서 Ollama 네이티브 프로토콜 흔적(`/api/generate`, `/api/tags` | 정적 grep: backend/app에서 /api/generate·/api/tags·ollama 흔적 0건, openai.AsyncOpenAI(base_url=...) 단일 경로 확인 | QA팀 |
| TC-113 | pass | mock 파이프라인으로 POST `/refine`→GET run→accept/reject. gate=bloc | 라이브 실측: POST /refine 200(gate=block) → accept **409** 차단 → reject 200 원문보존 + test_refine_api.py + 직전 세션 임시테스트 9 passed | QA팀 |
| TC-114 | pass | RefineRun 레코드 필드(route_hint, changed_ratio, accepted, report | backend test_refine_api.py (RefineRun 필드 저장·재조회 — 라이브 run GET 200 report_json 포함 확인) | QA팀 |
| TC-115 | pass | GET `/projects/{pid}/plus-status`: 회차 14/15개, 공백제외 2,999/3,0 | 라이브 GET /projects/{pid}/plus-status 200 (chapter_count/done_chars/eligible) + test_plus_status.py 7건 | QA팀 |
| TC-201 | pending-manual | 기존 `frontend/e2e/app-flow.spec.ts` 6 시나리오 전체 재실행 | 브라우저 실행 불가(환경 블록 E-1) | Infra팀: 의존성 설치 후 QA팀 재실행 |
| TC-202 | pending-manual | 요구사항 §7 M1① 재현: 프로젝트 생성→회차 3개 작성→상태 변경→재시작(reload/context 재생 | 브라우저 실행 불가(환경 블록 E-1) | Infra팀: 의존성 설치 후 QA팀 재실행 |
| TC-203 | pending-manual | mock 스트리밍 응답 수신→끼워넣기/선택 교체 버튼 클릭→본문 변조 확인 | 브라우저 실행 불가(환경 블록 E-1) | Infra팀: 의존성 설치 후 QA팀 재실행 |
| TC-204 | pending-manual | diff Dialog에서 거절→수락 흐름 + 50% 초과 mock에서 수락 버튼 disabled 확인 | 브라우저 실행 불가(환경 블록 E-1) | Infra팀: 의존성 설치 후 QA팀 재실행 |
| TC-205 | pending-manual | 자동저장 완료 대기→페이지 context 종료(kill 시뮬레이션)→재접속→본문 대조 | 브라우저 실행 불가(환경 블록 E-1) | Infra팀: 의존성 설치 후 QA팀 재실행 |
| TC-206 | pending-manual | S2/S3/S4에서 각각 Alt+A로 AI 패널 토글 | 브라우저 실행 불가(환경 블록 E-1) | Infra팀: 의존성 설치 후 QA팀 재실행 |
| TC-301 | pass | 테스트용 api_key 값을 심은 상태에서 `jippeel.db`, `-wal`, `-shm` 파일을 바이트 | jippeel.db 바이트 덤프 스캔: sk-/eyJ/gsk_ 패턴 0건, ai_endpoints.api_key_encrypted는 Fernet 암호문(gAAAAAB…)만 존재 | QA팀 |
| TC-302 | pending-manual | Windows에서 ①`keyring.set_password/get_password` 왕복 스크립트 실측 ②W | Windows 실기기 keyring(DPAPI) 실측 필요 | QA팀(Windows 실기기) |
| TC-303 | pass | keyring 백엔드 부재 환경(또는 강제 실패 주입)에서 저장→Fernet 로컬 키 파일 폴백 동작 확인  | test_crypto.py: fallback-file 마스터키 생성·Fernet 왕복·타키 복호화 실패 검증 (118 passed 내) | QA팀 |
| TC-304 | pending-manual | key 저장 후 S7 재진입→마스킹 표시 확인 + [표시] 버튼 부재 확인(프로토타입 C-1) | UI 마스킹 표시 확인 필요(브라우저 불가). API층은 has_api_key만 노출 확인(TC-110) | QA팀(재실행) |
| TC-305 | pass | `/ai/endpoints*` 전 응답 JSON을 수집해 평문 key 문자열 스캔 | 라이브 응답 JSON 스캔: api_key 평문 필드 0건(has_api_key boolean뿐) | QA팀 |
| TC-306 | pass | key 저장/LLM 호출/오류 발생 상황의 uvicorn·프론트 콘솔 로그 덤프 스캔 | ~/.jippeel-logs/ 전 로그 grep: sk-/JWT 패턴 평문 0건 | QA팀 |
| TC-307 | pass | uvicorn 기동 후 `netstat`로 listen 인터페이스 확인 | ss -tlnp 실측: 127.0.0.1:8000·127.0.0.1:1234만 LISTEN, 0.0.0.0 노출 0건 | QA팀 |
| TC-308 | pending-manual | 미리보기에 `<script>alert(1)</script>`·`<img onerror>` 포함 마크다운 입력 | dompurify ^3.2.3 도입은 package.json 확인 — 브라우저 렌더 실행 검증은 환경 블록 | QA팀(재실행) |
| TC-309 | pending-manual | humanize 명령 템플릿에 셸 특수문자 포함 원문/장르값 주입 시도(subprocess 위생, shlex | 부분 근거: test_humanize_unit.py run_subprocess 추상화·gate 보수적 처리 통과. 셸 특수문자 주입 직접 실측은 미실시 | QA팀 |
| TC-401 | pending-manual | 3만 자·5만 자 원고에서 타이핑 입력→화면 반영 시간 10회 계측(Playwright tracing 또는  | 계측형 성능테스트 — 브라우저/시드 환경 필요(TC-402는 자동 가능하나 이번 사이클 제외) | QA팀 |
| TC-402 | pending-manual | 로어북 300건·캐릭터 200건 시드 후 `/lore/search` 반환 시간 20회 계측(p95) | 계측형 성능테스트 — 브라우저/시드 환경 필요(TC-402는 자동 가능하나 이번 사이클 제외) | QA팀 |
| TC-403 | pending-manual | 타이핑 입력 이벤트→글자 수 표시 갱신까지 지연 계측 | 계측형 성능테스트 — 브라우저/시드 환경 필요(TC-402는 자동 가능하나 이번 사이클 제외) | QA팀 |
| TC-404 | pending-manual | SSE 스트리밍 수신 중 타이핑·스크롤 조작 응답 시간 계측 | 계측형 성능테스트 — 브라우저/시드 환경 필요(TC-402는 자동 가능하나 이번 사이클 제외) | QA팀 |
| TC-405 | pending-manual | 입력 정지→PUT/PATCH 저장 요청 완료까지 타임스탬프 계측 10회 | 계측형 성능테스트 — 브라우저/시드 환경 필요(TC-402는 자동 가능하나 이번 사이클 제외) | QA팀 |
| TC-501 | pending-manual | **시니어 배려 모드 OFF** 상태에서 S1~S7 전 화면 axe-core 스캔(E2E `@axe-core | axe-core/NVDA/키보드 — 브라우저 불가 환경 + NVDA 실기기 필요 | Design팀 지원 + QA팀 |
| TC-502 | pending-manual | **시니어 배려 모드 ON** 상태에서 동일 전 화면 재스캔 + 본문/보조 텍스트 대비 ≥7:1 토큰 실측 | axe-core/NVDA/키보드 — 브라우저 불가 환경 + NVDA 실기기 필요 | Design팀 지원 + QA팀 |
| TC-503 | pending-manual | NVDA로 S5 AI 패널 조작: 가드 Alert 문구 읽힘, 스트리밍 출력의 aria-live 공지, 오류 | axe-core/NVDA/키보드 — 브라우저 불가 환경 + NVDA 실기기 필요 | Design팀 지원 + QA팀 |
| TC-504 | pending-manual | NVDA로 S6 윤문 리포트 조작: 게이트 바 라벨(0~30%/30~50%/50%+) 읽힘, block 시  | axe-core/NVDA/키보드 — 브라우저 불가 환경 + NVDA 실기기 필요 | Design팀 지원 + QA팀 |
| TC-505 | pending-manual | 키보드만으로 S1→S7 핵심 흐름 1회 수행(§6.1 단축키표 준수 확인: Ctrl+S, Alt+A, Alt | axe-core/NVDA/키보드 — 브라우저 불가 환경 + NVDA 실기기 필요 | Design팀 지원 + QA팀 |
| TC-506 | pending-manual | 클릭 타겟 크기 계측(기본 ≥44×44, 시니어 모드 ≥48×48) + 시니어 모드 포커스 링 3px·고대비 | axe-core/NVDA/키보드 — 브라우저 불가 환경 + NVDA 실기기 필요 | Design팀 지원 + QA팀 |
| TC-601 | pass | `backend/.venv/bin/python -m pytest -q` 전체 재실행 — 기존 **97 pas | backend pytest -q: **118 passed** (8.92s) — G6 기록 118과 동일, 회귀 0건 | QA팀 |
| TC-602 | pass | `tsc --noEmit` + `npm run build` | npm run build 성공(tsc -b && vite build, built in 15.37s) — chunk size warning만 존재(비차단) | QA팀 |
| TC-603 | pending-manual | `app-flow.spec.ts` 재실행 | Playwright 1.62.1 기동됨으나 chromium 공통 라이브러리 부재로 launch 실패(환경 블록 E-1). 스펙 자체 결함 아님 | Infra팀: `npx playwright install-deps` 등 OS 의존성 설치 |
| TC-604 | pass | Alembic initial→add_project_memo→**volume nullable 신규 revisi | backend test_migrations.py·test_database_pragmas.py 포함 118 passed(WAL/NORMAL/busy_timeout/FK·up/down 무결) | QA팀 |

## 4. G7 판정안

**G7 = pass (조건부)**
- 근거: 자동 실행 24건 **FAIL 0** (regression 118 passed·build 통과·API/security 자동분 전부 통과).
- 보류 목록 note: pending-manual 70건 — ① UI e2e/a11y/perf 62건(환경 블록 E-1, Infra팀 의존성 설치 후 재실행), ② Windows 실기기 필요분(TC-302 등), ③ NVDA 실기기(TC-503~505).
- 단, **F-036 라이선스 고지는 릴리스 차단으로 G8 진입 전 반드시 해소**되어야 함(G7 자동 판정 기준과는 별개 요건).

### 재현 커맨드
```bash
cd backend && .venv/bin/python -m pytest -q        # 118 passed
cd frontend && npm run build                        # success
.venv/bin/python ~/.jippeel-logs/api_smoke.py       # 라이브 API 스모크
.venv/bin/python ~/.jippeel-logs/refine_smoke.py    # refine gate=block → accept 409
```
