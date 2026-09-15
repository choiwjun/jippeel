# 📋 프로젝트 핸드오프 — 웹소설 AI 집필·관리 대시보드 구축

## 현재 작업 기준 — 2026-09-14

**전 엔진 감사 + 고도화(2026-09-14):** "모든 엔진 조사분석" 지시로 백엔드 전 서비스·라우터를 감사하고 8개 항목을 수정했다. 검증: backend **829P/1skip/70subtests/violations 0** + frontend tsc/build 통과.

- **단일 생성 컨텍스트 대칭:** `/ai/generate`도 계획 경로와 동일하게 `previous_chapter`·`auto_characters`·`include_memory` 자동 주입 + `style_profile` 기본값 on. 직전 회차·인물·장편 기억이 수동 선택 없이 들어간다.
- **캐릭터 관련성 선정:** `auto_characters`가 `first_volume > 현재 권`인 미등장 인물을 제외하고, 본문·메모·프롬프트의 이름/별칭(`aliases` 컬럼+card_json) 언급 점수로 상한까지 채운다. 30명+ 장편 캐스트에서 현재 권 관련 인물이 우선된다.
- **요약 잡 API + UI:** `GET/POST /projects/{pid}/summary-jobs`(+`/plan`·`/run?limit=N`·`/{jid}/retry`) 신규 라우터. MemoryPage에 계획/실행 버튼·잡 상태 표·provider_error 재시도. 실행은 draft 메모리만 쓰고 작가 승인 게이트 유지.
- **규칙 제안 버튼:** 규칙 패널 "이력 분석으로 제안 생성"이 `POST /improvement-rules/propose`를 호출 — 제안은 proposed 상태로만 생성.
- **병렬 장면 재집필:** worker 출력의 계약 위반(마커 누출·빈 장면·분량 초과)은 transport 재시도와 별개로 **1회 재집필** 프롬프트로 회복. 재집필도 위반하면 run 실패 유지(오염 원고 미조립).
- **canon 컨텍스트 캡:** 캐릭터 20명·로어 30건 상한, 주연 우선 + 본문 언급 관련성 순. 장편 후반 프롬프트 폭증 방지.
- **자동 백업 활성화:** `prod.sh`에 `JIPPEEL_AUTOBACKUP_INTERVAL_MIN=30`·`KEEP=10` 기본값 + WSLENV 전파. `Jippeel실행.bat`은 prod.sh 위임이라 별도 수정 불필요.
- **경미 수정:** `canon.py`의 모듈 전역 `last_prompt_chars` 제거(동시 요청 경쟁 → `counts["prompt_chars"]` 반환으로 대체), `select_context_memory`의 N+1 `db.get(Chapter)` → 단건 배치 쿼리, 캐릭터 목록에 `first_volume` 배지 노출.
- **선행 슬라이스(같은 감사에서 완료):** planner ValidationError 1회 재시도 + `planner_debug` 원문 보존(3개 표면), 병렬 감수 `[수정본]` 출력+refined 채널 분리, 레퍼런스 스타일 분석(`style_analysis.py` 결정적 지표+LLM 합성→style_profile 초안), 권별 조연 확장(3권+ 작품에 권당 2~3명, `first_volume` 부여, 관계망 포함, 실패 시 핵심 캐스트 폴백).
- **남은 후속:** 캐릭터 라이프사이클(퇴장/사망·권별 역할 변화) first-class 필드화, 권별 독립 캐스트 호출(현재 단일 호출), canon 결정적 사전검사(이름/장소/시간 모순 규칙), 한국어 임베딩 기반 로어 매칭(현재 2-gram fallback), 다중 프로세스 잡 락, 인증/인가(로그인 없는 단일 사용자 앱 — LAN 공개 시 필수), 실제 provider/실기기 게이트.

## 이전 작업 기준 — 2026-09-13

**2026-09-14 다른 PC 접근 최소 범위:** A PC의 운영 서버가 LAN에 바인딩되도록
`scripts/prod.sh`에 `JIPPEEL_HOST`/`JIPPEEL_PORT` 설정과 Windows 사설 IPv4 주소
출력을 추가하고, `scripts/dev.sh`·`frontend/vite.config.ts`에는 WSL/Windows 개발
서버 연결 설정을 반영했다. `Jippeel실행.bat` 실행 후 표시된 `http://<A-PC-IP>:8000`을 B PC에서
열면 같은 SQLite DB를 함께 본다. 로그인 없는 현재 앱은 인터넷에 공개하지 않으며,
같은 LAN 사용법과 방화벽·한계는 [다른 PC에서 작품 확인하기](docs/runbooks/cross-pc-access.md)에
기록했다. 자동 클라우드 동기화·공동편집·인터넷 공개는 이번 범위에 포함하지 않는다.

**새 순차 진행 승인:** M01~M05 기억 화면 → B03 품질 지표 → 회차 목표/완결·재개/summary worker → 추가 검증 → 실제 자원 수용 순서로 진행한다. M01~M05와 B03은 수용 완료했고 [승인·실행 계약](docs/superpowers/plans/2026-09-12-remaining-sequence.md)을 따른다. 완료된 P1/C13은 재개하지 않고 실제 자원은 필수 환경·예산·접근 승인 확보 전 사용하지 않는다.

**진행 중(2026-09-14):** `choiwjun/d01-contract-analysis` worktree에서 D01·D03 전 단위·D04-1·V01~V04·G-045 수용 완료. 사용자 전체 위임으로 **G01 실 DB migration(완료)·G03·G04 자동화 가능 영역(네이티브 스위트+실기동 프로브+실제 브라우저 10/10)·U01~U04·O01~O03·O05·O06·V03·D04 provider 어댑터** 실행. 전체 backend **726P/1skip/70subtests/violations 0/warnings 0**, Windows 네이티브 통과. 09-14 추가: **V04 실물 대조 완료**, **SPA fallback 실제 결함 수정**(딥링크 404→index.html, API 404는 JSON 유지), **실행 스크립트 경로 정정**, Documents checkout `git pull`+dist 리빌드 완료. **09-14 최종 게이트:** **G02 실제 provider 파일럿 완료** — 실제 `openai-oauth` 브릿지(gpt-5.6-luna) 경유 6-case 실 호출 전부 완결, SSE 2,803건·usage·latency 기록, DB 해시 동일, marginal $0. **G03 OAuth 로그아웃·복구 시연 완료** — stop→credential 제거→기동 거부→복원→실 호출 성공 전 주기. **G04 NVDA 최종 사인오프 완료** — 실제 NVDA가 실제 운영 앱을 음성 발화(랜드마크·제목·버튼·콤보박스 롤/값/상태, Tab 순환 발화). **G02 독립 AI blind 평가 A/B 2회도 완료** — hard-block 없음·축별 lower median 3 이상·최대 점수 차이 1점. 수용 증거: `docs/audits/g02-pilot-2026-09-14/`·`g03-oauth-logout-2026-09-14/`·`g04-real-browser-2026-09-14/`. 작가 accept/reject와, 프로젝트 정책상 인간 평가자를 반드시 요구하는 경우의 별도 인간 세션만 남긴다. AI 평가는 인간을 사칭하지 않고 대행 평가로 기록했다. **09-14 후속:** 작가 피드백 자가개선([설계](docs/specs/2026-09-14-author-feedback-improvement.md)) **E1+E2 수용 완료** — `generation_runs`/`generation_outputs` append-only(migration `ae1f2b3c4d58`, head 갱신), 3개 surface SSE 기록 + additive `generation_saved` 이벤트, outcome 상태 기계(`POST /generation-outputs/{id}/outcome`, 종결 재전이 409), 프론트 명시 액션(끼워넣기/교체/복사) 계측. 전체 backend **738P/1skip/violations 0** + frontend tsc/build 통과. [수용](docs/audits/e1-generation-runs-2026-09-14/acceptance.md). 잔여: E3 diff 분석→E4 improvement_rules→E5 제안 job→E6 승인 규칙 주입→E7 UI. **09-14 병렬 세션 통합:** Documents checkout의 병렬 Codex 세션 작업(브릿지 재시도·원클릭 다음 회차 생성·LAN 접속·독립 blind 평가)을 `fa9ba01`로 보존 커밋 후 병합했다.

**09-14 대량 슬라이스 — 계획→승인→집필 + 자가개선 전 단계 + 계층 기억:**
- **P1~P4 계획-우선 집필:** `POST /ai/plan`(계획만 생성·`channel="plan"` 보존), `ParallelGenerateRequest.approved_plan` 주입 시 planner 스킵, `POST /projects/{pid}/assistant/plan-next`(회차 선택+계획), `assistant/generate-next`는 draft-only(`applied:false`)로 정합, `POST /generation-outputs/{id}/apply`가 `expected_revision` CAS로만 원고 반영. 프론트는 계획 카드(수락하고 집필/다시 생성/폐기) + BootstrapDialog 계획→초안→적용 흐름. 기존 원고 자동 덮어쓰기 없음.
- **E3 결정론 diff 분석:** LLM 없이 삽입본↔최종본 편집거리·삭제 패턴·분량·surface별 accept율 (`generation_analysis`).
- **E4/E6/E7 규칙 생명주기:** `improvement_rules`(migration `c04b5d6e7f81`, 8 카테고리, proposed→approved/rejected/retired, 승인 후 불변), `approved`만 `[작가 승인 규칙]` 블록으로 컨텍스트 주입+`applied_rules_json` provenance, 규칙 패널·생성 이력·명시 폐기(discarded) UI.
- **E5 제안 job:** 임계 신호가 `proposed` 초안만 기록(draft-only·idempotent·근거 링크).
- **D04:** 실제 GPT OAuth 브릿지 smoke(`summary_smoke.py`, draft_saved·자동 승인 없음) + [운영 runbook](docs/runbooks/summary-backfill-operations.md) + [수용](docs/audits/d04-2-summary-smoke-2026-09-14/acceptance.md).
- **D02/500화 1차 슬라이스:** 아크 요약 — `summary_jobs.kind='arc'`+`source_ids_json`(migration `d1e2f3a4b5c6`), 승인된 회차 요약 10화 묶음→`arc_summary` draft, `arc-v1` 프롬프트, stale/idempotent 유지. [설계](docs/specs/2026-09-14-hierarchical-memory-500ep.md).
- **검증:** 전체 backend 786P→(보완 후)**792P/1skip/violations 0** + frontend tsc/build 통과.
- **09-14 사용자 검토 보완(`0c44677`):** ① 일반 AI 패널도 plan-first 기본화 — 주 버튼이 [🗺 계획 만들기](자동 전체 분석)이고 [바로 생성]은 명시적 우회. ② 어시스턴트 컨텍스트에 `auto_characters`+`include_relationships` 자동 주입 추가 — 인물 카드·관계가 수동 선택 없이 들어간다. ③ `apply`의 `expected_revision` 필수화(생략 시 422) — CAS가 계약상 강제. ④ 단일 `/ai/generate`도 `approved_plan` 계약 주입 지원. ⑤ orphan `test_assistant_flow.py`(구 자동저장 계약)를 draft-only 계약으로 이식·추적 파일화. 전체 **792P/1skip/violations 0**.

**09-14 제품 후속 슬라이스 — D02 2차 + D04 잔여:**
- **D02 권 기억:** `summary_jobs.kind='volume'` + `memory_entries.kind='volume_memory'`(migration `e2f3a4b5c6d7`). `plan_volume_summary_jobs`가 승인된 아크 요약을 `volume_size`(기본 5≈50화)로 묶고, `_process_volume_job`이 동일한 stale/idempotent 패턴으로 `volume_memory` draft를 만든다. provider는 `volume-v1` 프롬프트.
- **D02 커버리지 선택:** `select_context_memory`가 승인된 arc가 덮는 회차 요약·승인된 volume이 덮는 아크(와 그 아래 회차 요약)를 컨텍스트에서 제외 — 같은 구간은 가장 압축된 승인본 하나만 들어간다. draft 상위 층은 하위를 덮지 않는다.
- **D02 인지 도메인:** 작가/독자/인물별 인지 상태·사건/관계 영향 추적의 [도메인 설계](docs/specs/2026-09-14-cognitive-state-domain.md) 완료(knowledge_states·event_impacts·P1~P4 단계). 구현은 별도 슬라이스.
- **D04 잔여:** [평가 manifest](docs/specs/2026-09-14-summary-eval-manifest.md)(공통 M1~M6 + 종류별 S/A/V 항목 + JSONL 기록 형식), MemoryPage 승인 UI 통합(자동 생성 배지·출처 필터·arc/volume 라벨·정제된 provenance 표시), `scripts/summary_backfill.py` 운영 스크립트(alembic head 검증·브릿지 pre-flight·--limit 비용 상한).
- **운영 실행 검증:** 실제 운영 DB(`backend/jippeel.db`, 백업 `jippeel.db.bak-2026-09-14-pre-volume`)를 `d1e2f3a4b5c6`→`e2f3a4b5c6d7`로 마이그레이션 후 backfill 계획 실행 — 300회차 전부 `skipped_empty`(본문 없음, provider 호출 0건), 재실행 시 전량 duplicate로 멱등 확인. 실제 요약 생성은 본문이 쌓인 뒤 `--run --limit`으로 진행.
- **검증:** 전체 backend **800P/1skip/violations 0** + frontend tsc/build 통과.

**완료·미완료·다음 작업·승인 대기는 [전체 작업 현황](docs/handoffs/2026-09-08-remaining-work.md) 한 곳에서 관리한다.**
기존 9월 8일 인계를 9월 13일 결과까지 대조했고, 완료·잔여·검증·운영 승인·선택 확장을 분리했다.
문서 탐색은 [문서 상태 인덱스](docs/DOCUMENT_STATUS.md)를 사용한다.

### 최종 인계·커밋·푸시 명시 승인 — 2026-09-13

- 사용자 요청 **“핸드오프에 모두 남기고 커밋 푸시해”**에 따라 누적 프로젝트 변경·정식 문서·선별 증거 305개를 검토했다. 코드·게시 보안 **2PASS/차단0** 후 결과 문서 보강만 더해 `main`에 게시한다. [통합 인계·검증·미결정·보존 경계](docs/handoffs/2026-09-13-commit-handoff.md)에 모두 모았다.
- D01의 핵심 해결책은 **목표 영구 저장·재진입 복원**, 추가 추천은 **이력 보존·조회·복원**이다. “어떤게 문제야?/해결방안이야?”는 설명 확인이며 선택·개발 승인이 아니다. D01은 조사만 완료했다.
- 아래 과거 기록의 “Git 미승인/미실행”은 당시 사실이다. 이번 Git 승인이 이를 대체하지만 운영 DB/provider/credential/장치/migration·배포 gate는 유지한다. 초기 로컬/원격 `main`은 모두 `c1a92c4`로 확인했다.
- `.eval_tmp`·에이전트 작업폴더·`.coverage`·과거 미추적 원시 자료는 보존하되 일괄 게시하지 않는다. 실제 커밋은 통합 인계 파일의 Git 이력에서, 원격 반영은 `HEAD`와 원격 `main` 대조로 확인한다.

- [게시 검토·원시 근거](docs/audits/publication-2026-09-13/manifest.json)를 보존했다. 기존 provider 일반 오류 메시지 전달의 낮은 위험도 A1은 통합 인계·원장에 후속 참고로 남겼고, 새 회귀나 실제 유출로 단정하지 않았다. 인코딩/`python` 명령 실패와 제한된 재개, CRLF-aware 공백검사 exit0도 인계에 기록했다.

### 순차 진행 종료 정리 — D01·D03·D04-1·V01·V02·V04 전부 수용 — 2026-09-13

- 사용자의 "모든 작업을 완료까지 진행·결정사항은 추천대로 자율 결정" 지시에 따라 승인된 순서(M01~M05/B03 수용 후 D01 → D03 → D04 → V01/V02/V04)를 끝까지 실행했다. 각 단위는 좁은 사양 → RED → 구현 → 집중+전체 회귀 → 독립 검토 2건 → 지적 반영 → 재검증 → 수용 문서의 동일 절차를 거쳤다.
- **수용 완료:** D01(회차 목표 영속화·이력·복원), D03-1~D03-7(흐름 상태 기계·재개 파생·연재 상태 분리·근거 링크·이관 구분·완결본 스냅샷·결말 변경 영향), D04-1(`summary_jobs`+fake worker·idempotency·draft-only), V01(`PW_COVERAGE=1` V8 수집→fs 경로 키 union 병합, 11 스위트 128P 측정값 lines 83.27%), V02(복원 실패 주입 9종 코드 15P), V04(AST 전용 외부 metrics 버전 검증기 20P), G-045(복선 POST `audience_knows` 유실 1행 수정·독립 검토 PASS).
- **최종 검증 수치:** backend 677P/1skip(기존 외부 metrics 미설치 분기)/violations 0 · frontend fixture 11 스위트 128P(+G-045 왕복 1건)/tripwire no escapes 전부 · tsc exit0.
- **G 게이트 잔여(승인 없이 실행 금지):** G02 실제 OAuth/provider 수용·품질 파일럿 → G01 기존 DB migration·운영 적용 → G03 credential·key 복구/wrong-key 복원 → G04 지정 Windows 실기기 수용. D04 잔여(실제 provider 어댑터·비용 cap·평가 manifest·승인 UI·운영 절차)는 G01/G02/G03과 결합돼 있다.
- **U(선택·축소 구현) 잔여:** U01 캐릭터 card_json 자유 확장 UI, U02 로어 참조 회차 표시, U03 윤문 명령 프리셋, U04 시니어 확대 모드(G04 판단 연계). V03은 배포 구성 필요 시에만.
- **O(우선순위 밖) 잔여:** O01~O06(카드 import·자동 백업·연재 캘린더·provider 확장·정리·규정 재확인). 선존 결함 G-045(`create_foreshadow`의 `audience_knows` 미저장 — 실제 데이터 유실)는 1행 수정·재현/회귀/독립 검토로 [수용 완료](docs/audits/g045-audience-knows-2026-09-13/acceptance.md).
- 모든 변경은 `choiwjun/d01-contract-analysis` worktree의 **uncommitted** 상태다. 9월 13일 Git 게시 승인은 그 이전 작업에 대한 것이며 이후 변경에는 자동 적용되지 않는다 — 커밋·푸시·운영 적용은 별도 승인 대기.

### 전체 위임 실행 — G01 완료·G03/G04 부분·U01~U04·O01~O03·O05·V03 — 2026-09-13

- 사용자의 "나대신 승인하고 남은거 다 작업해" 위임으로 로컬 실행 가능 게이트·선택 항목을 전부 실행했다. 승인으로 해결되지 않는 실제 자원 요건(계정·예산·지정 장치 창)은 부분 실행+잔여 기록으로 처리했다.
- **G01 완료:** 실 운영 DB(`C:\Users\wj941\Documents\jippeel\backend\jippeel.db`)를 백업→복원 검증→리허설→실 적용으로 head `9d0e1f2a3747`까지 migration. 14개 테이블 데이터 보존·schema assert 통과. 증거·절차는 [수용](docs/audits/g01-production-migration-2026-09-13/acceptance.md).
- **G03 부분:** 인스턴스별 키 분리 확인·wrong-key 거부·키 유실 감지·복구 절차 temp 검증. 저장 암호문 실데이터 부재 — 실 credential 시연 잔여(계정 승인).
- **G04 부분:** Windows 네이티브 전체 스위트 714P/violations 0/warnings 0+alembic 완주. 브라우저·NVDA·성능표 등 수동 실기기 영역 잔여.
- **U01~U04:** card_json 편집 UI·로어 참조 회차(`GET /lore/{lid}/referencing-chapters`+접이식)·윤문 프리셋(선존 충족으로 종결)·시니어 확대(`uiScale`+에디터 typography compartment — fontFamily/lineHeight 선존 갭 실제 적용). fixture 5+4+3.
- **O01~O03:** ST 카드 PNG+novelWriter import(16P)·opt-in 자동 백업 `JIPPEEL_AUTOBACKUP_INTERVAL_MIN`(11P)·`GET /projects/{pid}/writing-activity`(5P). O04(provider 확장)·O06(규정 재확인)·플랫폼 직접 발행은 정책상 미채택.
- **O05:** ResourceWarning 19건 근본 수정 — `assert_manuscript_schema_current`의 `inspect(bind)` transient Inspector가 lifespan마다 연결을 유지 → `with bind.connect()` 스코프로 교체. 테스트 측 `_inspect` 헬퍼·엔진/제너레이터 폐기 정리·진단 probe 전부 제거. **warnings 0**.
- **V03:** `scripts/sqlite_multiprocess_check.py` — 앱 pragma 그대로 spawn 다중 프로세스 동시 쓰기 2회 PASS(무손실·integrity ok·WAL).
- **최종 검증:** Linux 전체 **714 passed/1 skipped/70 subtests/violations 0/warnings 0** · Windows 네이티브 스위트 통과 · 신규 fixture 12/12. 상세는 [수용](docs/audits/uo-options-v03-2026-09-13/acceptance.md).
- **잔여(실제 자원 승인 필요):** G02 실제 OAuth/provider·품질 파일럿(USD 20 cap), G03 실 credential 로그아웃/복구 시연, G04 수동 실기기 시나리오, O04/O06, 운영 교체·rollback 실시연.

### 2026-09-14 후속 — V04 실물 대조·G04 실제 브라우저·SPA fallback 수정·실행 스크립트 정정

- **V04 완료:** 실물 `metrics_v2.py`가 Windows 측 `C:\Users\wj941\.agents\im-not-ai\skills\humanize-korean\references\`에 설치돼 있음을 확인(Linux `~/.agents`가 아니라 Windows 측이었음). `verify_metrics_module` 실물 실행으로 `compute_all_v2` 시그니처·`CHANGE_RATE_WARN=0.3`/`ABORT=0.5`·warn≤abort 전 항목 일치 — [증거](docs/audits/v04-metrics-version-2026-09-13/real-file-verification.txt).
- **G04 실제 브라우저 검증 10/10:** mock 없이 실제 `npm run build` dist + 실제 uvicorn + 실 DB 복사본 + Playwright Chromium. 실 API 왕복(프로젝트 2·챕터 10 실데이터)·키보드 Tab 포커스 이동·uiScale 영속+실 DOM 적용(16→20.8px, `data-ui-scale=xlarge`)·**에디터 5만 자 실제 입력 경로(insertText 932ms)→자동저장 PUT→API 재조회로 +50,027자 실증**·콘솔 오류 0. 증거·스크린샷: [수용](docs/audits/g04-real-browser-2026-09-14/acceptance.md).
- **실제 결함 발견·수정 — SPA fallback 부재:** 운영 모드(A-040 uvicorn 단일 서빙)에서 `/settings`·`/projects/1/write` 직접 접근·새로고침이 JSON `{"detail":"Not Found"}`였다. `StaticFiles(html=True)`는 디렉터리 인덱스만 처리. `_SPAStaticFiles` 추가 — 비-API 404→index.html fallback, `/api`·`/health` 404는 JSON 유지. `test_spa_fallback.py` 5P·전체 726P 회귀 통과.
- **실행 스크립트 정정(`701ea52`):** `Jippeel실행.bat`·`scripts/prod.sh`·`scripts/dev.sh`의 폐기된 `OneDrive/바탕 화면/WJproject/jippeel` 경로→`Documents/jippeel` 실 경로, `.venv/bin/python`(존재하지 않음)→실제 Windows venv `Scripts/python.exe`로 수정. `dev.sh`의 빌드 경로도 실제 frontend로 교체.
- **배포:** `c9168ec`·`a593e7f`·`701ea52` 전부 `origin/main` 반영. `C:\Users\wj941\Documents\jippeel` 로컬 checkout은 `git pull`로 `701ea52` 도달, `frontend/dist` 리빌드 완료 — `Jippeel실행.bat`이 실제로 동작 가능한 상태.
- **잔여(사용자 행동 필요):** G02 `npx openai-oauth login` 브릿지 설치·대화형 로그인, G03 브릿지 소유 OAuth 로그아웃·지정 계정 credential 시연, G04 NVDA 스크린리더 실측(지정 Windows 장치).

### D01 목표 저장 조사 완료·이력 요구 결정 대기 — 2026-09-13

- 읽기 전용으로 EpisodeBrief/단일 메모리 store/Chapter.memo/원고 revision과 현재 요청 동결을 대조했다. 목표 영속 모델·과거 내용/버전 연결은 미구현이며 소스·schema·실제 자원을 건드리지 않았다.
- [요구 선택·근거](docs/superpowers/plans/2026-09-13-d01-contract-questions.md): 최신 목표만 저장(A) 또는 과거 목표도 조회·복원(B). 장기 근거 연결을 위해 B를 권장하지만 아직 승인되지 않았다.
- 선택 후 상세 저장/복원/purpose/생성 연계 계약을 명시하고 승인 후 개발한다. D03/D04는 후속, 완료된 B03은 재개하지 않는다.

### B03 품질 지표 최소 보정 최종 수용 — 2026-09-13

- 두 계수 결함을 보정하고 문체 참고점수·빈 원고/글자/essay/이력 설명, 선택적 대화상자 접근성 이름을 반영했다. 가중치/API/purpose/기존 이력·외부 adapter는 유지했다.
- 공식 격리 backend **482P/기존 skip1/70subtests**, 서로 다른 frontend **77P**, fullaxe3회 violations/incomplete0, app/helper TS·build 및 제품3개 변경범위 line/branch80% 이상을 확인했다. [최종 수용·검증·실패 이력](docs/audits/quality-b03-2026-09-12/acceptance.md).
- fresh 독립 검토의 제품 지적은0이었다. 자동 formatter 이후 보조 파일 실행 증거 E1은 부모의 exact-current5P/helperTS0로 보강하고 retained 검토2건 **PASS·새 지적0**으로 종결했다. 처음 BLOCKED·ENOMEM·504·axe/계측 실패를 고쳐 쓰지 않았다.
- [선별 사본·원본 경로 manifest](docs/audits/quality-b03-2026-09-12/accepted-evidence/manifest.json): 원래218+retry25 artifact와 현재16source/protected hashes 확인. stage/commit/push·운영 자원 사용 없음. 다음은 승인된 순서의 **D01/D03/D04 요구·저장/상태/job 계약·기획**이며 상세 미결정은 구현 전 승인받는다.

### M01~M05 최종 수용 완료 — 2026-09-12

- 기억 화면 5건을 새 backend 421P/기존 skip1·frontend 72P, TS/helper TS/build·변경범위 coverage 검증과 fresh 독립 검토 2건 PASS 후 수용했다.
- [수용 기록·근거·복구 한계](docs/audits/memory-m01-m05-2026-09-12/acceptance.md)를 보존했다. 원래 /tmp 소실, worker timeout과 결과 직렬화/측정 오류는 별도 이력이며 완료된 검증을 반복하거나 실패 기록을 소급 PASS로 바꾸지 않았다.
- 검토 종료 후 제품·테스트·보호 대상 hash 불변을 확인했다. 상태 문서만 갱신하며 stage/commit/push·운영 적용은 없다. 전체 프론트 V01과 실기기 수용은 별도다.
- 당시 다음 단계였던 B03도 위 기록으로 수용 완료했다. 완료한 P1/C13/M01~M05/B03을 다시 열지 않는다.

### 실행 규칙 정정 — 2026-09-12

사용자가 “prime-agent는 사용하지 않는 agent”라고 명시했다. `AGENTS.md`의 prime-agent 강제 경로와
전용 라우팅은 과거 기록으로 전환했다. 현재 Pi 도구로 진행하며 prime-agent 설치/예외 승인을
다시 요구하지 않는다. 앱의 고정 OAuth 계약, 운영/외부 접근·배포·Git 변경 승인 경계는 변경하지 않았다.

### B01/B02/B04 최종 수용 완료 — 2026-09-12

- canon 실패 응답 계약, bootstrap 슬롯·metadata 정합성, 테스트 전역 격리 보강을 수용했다. **419 passed / 기존 외부 비교 1 skipped / 70 subtests / 19 warnings**, 독립 재검토 2건 PASS.
- 공식 실행은 `backend/scripts/run_backend_pytest.py`를 사용한다. [실행 가이드](docs/runbooks/isolated-backend-tests.md), [최종 수용·원시 증거](docs/audits/failure-contracts-2026-09-12/b04-review-fixes.md)를 보존했다.
- 검토 후 제품·테스트 소스 및 보존 대상 hash 불변을 확인했다. stage/commit/push·운영 적용 없음. B04 종료 당시 실행 중인 worker/reviewer 없음.
- 옛 `.coverage` 미복구·당시 credential 영향 미확정은 역사적 한계다. 유지 승인된 a8db… 생성본은 보존했다. LSP는 inconclusive이며 실제 provider/지정 기기 재검증은 하지 않았다.
- 원장의 **C13 완료 / V04 외부 비교 미검증**으로 반영했다. M01~M05, B03, D/V/G/U/O는 별도 범위이며 자동 착수하지 않는다. 아래 사고 당시 상태를 현재 blocker로 다시 올리지 않는다.

### 사고 당시 이력 — B01/B02 구현·401개 통과, 수용 차단 (이후 위 기록으로 종결)

- 실제 helper/direct fake에서 canon 오류 응답과 bootstrap 권/회차 정규화 문제를 재현했다.
- [재현·원본 증거](docs/audits/failure-contracts-2026-09-12/reproduction.md)와
  [최소 수정 계획](docs/superpowers/plans/2026-09-12-failure-contracts.md)을 프로젝트에 보존했다.
- **사용자 승인 완료**: 유효 번호 보존·중복 첫 유효 항목 유지·빈 슬롯 템플릿 보충 기준으로 수정→회귀→독립 검토를 진행한다.
- B01 구조 전체 검증·기존 1회 repair와 B02 슬롯·metadata 선택 정합성을 구현했다. 새 회귀 84건 포함 전체 **401 passed**이나 **격리·보존 gate가 실패하여 완료가 아니다**.
- 사용자의 한정 허용 정책 적용은 확인됐다. 별개로 WSL 셸 환경변수가 Windows Python에 전달되지 않아 기존 `.coverage`가 갱신되고 테스트 키 경로도 미적용된 문제가 확인됐다.
- DB는 runner가 Windows 내부에서 TEMP로 설정했다. 그러나 crypto는 keyring을 먼저 호출하므로 기본 키 저장소 접근 가능성을 배제할 수 없다. 실제 키 내용·저장소 상태는 조회하지 않았으며 부수 효과는 미확정이다.
- 원래 `.coverage`의 정확한 사본을 알려진 범위에서 찾지 못했다. [격리 실패·증거·처리 제안](docs/audits/failure-contracts-2026-09-12/validation-isolation-incident.md)에 따라 생성물 처리 결정과 테스트 전역 격리 보정 후 재검증해야 한다.
- workflow `c3560081-9458-4464-b041-1e41518a0244`는 `blocked-before-review`로 종료했다. **실행 중인 worker 없음 / 독립 검토 미착수**. 이전 부모 JSON 직렬화 오류는 이번 흐름에서 재발하지 않았다.
- 실행·잔여 상태는 전체 작업 원장의 B01/B02에서 관리한다.

- 승인된 기억 P1 네 건은 완료. 원래 P2 다섯 건은 별도 잔여이며, canon/bootstrap은 후속 C13에서 종결했다.
- 원고 보존·공통 맥락·관리 무결성·Vite/AnyIO·임시 백업/복원·memory rollback을 다시 미완료로 올리지 않는다.
- 실제 provider/운영 DB/credential/지정 Windows QA는 별도 승인 대기다. 문서 정리는 실행 승인이 아니다.
- **후속 승인:** 사용자가 현재 `.coverage` 생성본 유지와 테스트 격리 보강·재검증에 “진행해”로 승인했다. [계획 §8](docs/superpowers/plans/2026-09-12-failure-contracts.md)에 따라 보안 사전검토→단일 테스트 writer→안전한 회귀→fresh 독립 검토를 재개한다. 기존 원본 복원·실제 키 저장소 조회/수정은 하지 않는다.
  운영 DB·실제 provider·새 migration 파일·배포·commit/stage/push는 계속 제외한다. credential 무접근을 확인했다고 주장하지 않는다.

## 아래는 작업 당시 이력 — 현재 실행 목록 아님

아래에 반복되는 “최신/다음 작업/남은 게이트”와 예전 테스트 수치는 **각 기록 당시 상태**다.
현재 판정은 위 전체 작업 현황의 ID 및 종결·이관표가 우선하며, 옛 승인이나 명령을 재사용하지 않는다.

## 2026-09-11 기준 기록

### 승인된 장편 기억 P1 네 건 보정 — 2026-09-11 추가

- 사용자 승인 범위: draft 폐기 오전송, POST pending 입력 보호, memory PATCH 경쟁,
  chapter DELETE/기억 생성 경쟁만 수정했다. 이번에 한해 unavailable prime-agent 대신
  native Pi 단일 writer·로컬 pytest/Playwright를 사용하도록 승인받았다.
- 확인 state에 id/target visibility를 함께 보관하며 동작별 안내를 표시한다.
  POST 중 제출 폼의 모든 입력과 제출을 잠그고, 실패하면 입력을 보존한다.
- PATCH visibility+양쪽 nullable 범위 CAS 실패는 409; 기존 invalid transition/range는 422.
  빈 PATCH는 무쓰기, 같은 값 재요청은 현재 상태에서 200. stale 경합은 자동 재시도하지 않는다.
- chapter DELETE는 SQLite writer lock을 참조 조회 전에 확보한다. 이미 committed memory는
  409로 보존한다. DELETE가 먼저 이기면 pending POST는 busy/FK 409, 이후 생성은 404다.
  deliberate whole-project cascade, provenance/schema/원고 revision 정책은 변경하지 않았다.
- 검증: RED backend 6 실패·frontend 3 실패 → 최종 전체 backend **317 passed**,
  targeted **64 passed**, memory Playwright/axe **6 passed**, frontend TS/Vite build 통과.
  branch 포함 coverage: memories **93%**, projects **85%**, long_memory **93%**, 합산 **90%**.
  frontend source-mapped coverage %는 계측 부재로 미측정이다.
- 이번 full suite에서 과거 im-not-ai 외부 script 실패는 재현되지 않았다. 관련 파일을 수정하거나
  실패를 제외하지 않았다. 증거: `/tmp/jippeel-memory-p1.Ge5TLu/{red-backend,red-full-frontend,coverage-final-backend,full-final-backend,final-frontend,final-build}.txt`.
- baseline 대비 승인된 파일만 변경했다. 기존 OAuth 등 dirty 변경, untracked artifacts,
  backend/.coverage는 보존했다. commit/stage/push, 운영 DB/provider/keyring/migration은 실행하지 않았다.
- 독립 review 완료(2026-09-12): 무결성/security PASS, UI PASS with notes. UI의 상태 assertion이
  버튼 텍스트와 혼동되는 지적은 부모가 상태 span 및 폐기 후 action 부재 검사로 보강했고,
  `parent-reviewed-frontend.txt`에서 memory Playwright/axe **6 passed**를 재확인했다.
- 최초 worker는 최종 보고 중 30분 timeout으로 종료됐으나 diff/검증 로그를 보존하고 동일 Pi
  recovery workflow `2c5a47a8-9c26-4766-8b62-2b1981a198ac`로 보고·독립 검토를 완료했다.
  재구현·외부 실행 방식 전환 없이 복구했다. 승인된 P1 네 건은 완료했으며,
  P2 다섯 건과 기존 운영 적용 게이트는 이번 완료 범위가 아니다.

### 저장소

- 브랜치: `main`
- 로컬/원격: `HEAD=c1a92c4`, `origin/main=c1a92c4` (커밋·push 금지 상태에서 working tree 직접 수정 중)
- 장편 기억 거버넌스 구현, native integration fixture 보강, stale bound 보정, MVP v0.5 기획 반영을 추적 커밋했다.
- 미추적 감사·평가 산출물은 보존 중이며, 일괄 삭제·stage하지 않는다.

### 완료된 작업

1. Git pull 충돌 해결 및 원격 `main` 동기화
2. Starlette/AnyIO/HTTPX 호환성 정리
   - `anyio>=4.14,<4.15`
   - `httpx2>=2.0.0`
3. WSL 실행 스크립트 CRLF 결함 수정
   - `scripts/prod.sh`, `scripts/dev.sh`를 LF로 정규화
   - `bash -n` 통과
4. 임시 SQLite 백업·복원 dry-run
   - integrity check 통과
   - foreign key 오류 0
   - Alembic head 및 논리 row 복원 확인
5. 장편 기억 최소 수직 슬라이스
   - `MemoryEntry` 모델 및 migration `1b2c3d4e5f60`
   - provenance/revision/hash/time-scope stale 판정
   - 승인된 기억만 AI context에 자동 주입
   - `include_memory=false`, `include_draft_memory` 옵션
   - `included_memory_entry_ids` metadata 기록
6. 임시 DB migration rollback/re-upgrade 검증
   - `1b2c3d4e5f60 → 0a1b2c3d4e5f → 1b2c3d4e5f60`
7. 장편 기억 거버넌스 API/UI 후속 구현
   - project-scoped 생성/목록/필터, provenance/stale 표시, draft 승인·폐기
   - 다른 작품 memory/chapter 격리, 연결 회차 삭제 409 보존 게이트
   - 임시 SQLite backend 292 passed, frontend build, memory Playwright/axe E2E 통과
   - pytest-cov 기준 핵심 모듈 coverage 80% 이상 확인
   - stale 필터가 500건 이후 항목도 limit까지 찾도록 내부 batch scan 보정
8. 격리 integration fixture·E2E 보강
   - native Windows Python fixture가 cross-project invalid foreshadow negative case를 실제 SQLite에 구성
   - parallel-writing E2E가 임시 backend에 자체 fake endpoint를 등록해 독립 실행 가능
   - 실제 provider/운영 DB/keyring 없이 AI-context 3개, manuscript-preservation 1개, 기본 a11y/app-flow/parallel/memory 11개 E2E 통과
9. MVP v0.6 기획 반영
   - `대시보드_MVP_사양.md`에 고정 GPT OAuth provider 및 M6 장편 기억 override 반영
   - 상세 제품 사양: `docs/superpowers/specs/2026-09-11-long-memory-governance.md`
10. 고정 GPT OAuth provider 전환(오프라인 계약)

- `gpt_oauth.py`가 localhost bridge, 고정 모델(`gpt-5.6-luna`), 기본 `xhigh`를 검증
- 집필·감수·병렬·부트스트랩·canon·복선 제안은 `AiEndpoint` row를 읽지 않음
- S5/S7에서 endpoint/API key/base URL 입력과 모델 선택을 제거하고 bridge 상태만 안내
- legacy `ai_endpoints` CRUD/models route는 migration 호환용 hidden route로만 보존

### 당시 검증 증거 — P1 최종 수용 전 기록

아래 외부 script 9건 실패는 이후 전체 317 passed 실행에서 재현되지 않았다.
현재 검증 근거·범위는 [전체 현황 §9](docs/handoffs/2026-09-08-remaining-work.md#9-검증-수치의-최신성과-근거)를 따른다.

- OAuth 변경 전 기준선: backend **292 passed** (임시 SQLite runner)
- OAuth 변경 후 변경 범위 회귀: backend **108 passed** (gpt_oauth·long_memory·memories·AI·bootstrap·canon·legacy compatibility 선택집합)
- 전체 suite 재실행 결과 **294 passed, 9 failed, 1 skipped**; 9건은 현재 환경에 없는
  `~/.agents/im-not-ai/scripts/{prepare_monolith_input.py,verify_gates.py}` 의존 실패로,
  제품 변경과 분리했다. fixed provider/memory 선택집합은 아래 108 passed로 확인했다.
- pytest-cov 변경범위 coverage 재수집: memories router 80%, schemas 98%, long_memory 92%, summary_jobs 85%
  (827 statements 중 53 misses, 합산 line **93.59%**, 표시 94%; branch 전체 **91%**)
- 프론트: `cd frontend && npm run build` 성공(TS + Vite)
- 장편 기억 Playwright/axe E2E: **1 passed**
- native Windows isolated AI-context integration: **3 passed**
- native Windows isolated manuscript-preservation integration: **1 passed**
- native Windows isolated default E2E: **11 passed** (a11y, app-flow, memory, parallel-writing)
- AI-context/preservation fixture 직접 실행: 각각 `seeded` / `passed`
- 실제 OAuth/provider·운영 DB·keyring·지정 Windows 실기기 QA에는 접근하지 않았다. fake bridge만 사용했다.
- 독립 reviewer가 확인한 이전 P1/P2 지적(교차 project PATCH, chapter 삭제 cascade, 500건 bound 정렬)은 각각 project-bound PATCH/422, chapter 삭제 409, stale batch scan으로 보정했고 회귀 테스트를 통과했다.
- reviewer 재실행은 기존 Luna provider cold-start로 결과를 받지 못했으나, 글로벌
  `~/.pi/agent/settings.json`에서 서브에이전트 기본을 `openai-codex/gpt-6-astra`,
  reviewer fallback을 `openai-codex/gpt-5.6-sol`로 라우팅했고 smoke test를 통과했다.

### 당시 남은 작업과 실행 게이트 — 현재 목록은 전체 현황 참조

다음 항목들은 작성 당시 기록이다. 특히 완료된 임시 검증과 실제 운영 검증을 합쳐 재개하지 않는다.

#### 1. 운영 DB migration — 실행 전 승인 필요

현재 기존 `jippeel.db`는 새 Alembic head보다 뒤처져 있다. 따라서 일반 환경에서 앱을 시작하기 전에 다음 순서를 따라야 한다.

1. 운영/기존 DB 백업을 먼저 만든다.
2. 백업 manifest, logical integrity, restore 결과를 확인한다.
3. 별도 승인 후 `backend/.venv/bin/alembic upgrade head`를 실행한다.
4. 앱 시작과 기존 원고 read/write 회귀를 확인한다.

이번 작업에서는 기존 DB를 migration하지 않았다.

#### 2. 장편 기억 후속 범위의 후속 게이트

- 자동 요약·backfill의 provider-free deterministic planner는 구현·검증했다. `summary_jobs` schema/worker/provider 호출은 별도 승인 후 진행
- Astra 결정 기록: `docs/decisions/2026-09-11-astra-long-memory-release.md`
- 운영 DB migration 후 기존 데이터 negative corpus 검증
- 실제 모델 품질 평가와 prompt block 길이·우선순위는 provider/비용 상한 확정 후 진행

#### 3. 백업·복원 운영 준비

- OAuth bridge credential 복구·로그아웃/rollback 절차 확인 필요(이번 작업에서는 credential에 접근하지 않음)
- 임시 DB failure injection 추가
- 실제 restore rollback runbook 작성 완료: `docs/runbooks/long-memory-governance-release.md`
- 운영 DB/암호화 keyring에는 승인 전 접근하지 않음

#### 4. 실제 모델 품질 평가

- 실제 승인 사례 6개와 source owner 확정
- 고정 `ChatGPT OAuth` / `gpt-5.6-luna`의 availability·정책·비용을 확인하고 별도 승인
- 독립 평가자 2명 배정
- raw usage와 비용 증거 확보
- USD 20 hard cap 내에서 별도 승인 후 실행
- 위 조건이 없으면 provider 호출과 비용 발생을 하지 않음

#### 5. Windows 실기기 QA

- 정적 사전 점검은 통과했다.
- Windows 11 x64 지정 장치, 전용 port, test DB/key, QA 시간 창이 필요하다.
- DPAPI/keyring, batch 실행, 브라우저, NVDA, 성능, 복원 시나리오를 장치에서 수동 검증한다.

### 주요 산출물

- `docs/audits/ai-model-quality-evaluation-design-2026-09-10.md`
- `docs/audits/long-memory-design-2026-09-10.md`
- `docs/audits/backup-restore-design-2026-09-10.md`
- `docs/audits/backup-restore-dry-run-2026-09-10.md`
- `docs/audits/windows-device-qa-plan-2026-09-10.md`
- `docs/runbooks/long-memory-governance-release.md`
- `docs/audits/long-memory-evaluation-manifest.template.json`
- `docs/superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md`
- `대시보드_MVP_사양.md` v0.6
- `기술설계_GPT_OAuth_브릿지_v1.md`
- `docs/superpowers/specs/2026-09-11-long-memory-governance.md`
- `docs/decisions/2026-09-11-astra-long-memory-release.md`
- `backend/requirements-dev.txt`
- `backend/app/services/summary_jobs.py`
- `backend/tests/test_summary_jobs.py`
- `docs/audits/anyio-starlette-httpx-compatibility-2026-09-10.md`
- `docs/superpowers/plans/2026-09-10-long-memory.md`

### 최근 커밋

- `b1e77ce test: harden native integration fixtures`
- `0c17e5a feat: add long-memory governance`
- `68887bc docs: refresh project handoff status`
- `6a27ec8 docs: record memory migration rollback evidence`

---

## 최신 검증 업데이트 — memory migration rollback dry-run (2026-09-10)

- 임시 SQLite에서 `1b2c3d4e5f60 → 0a1b2c3d4e5f → 1b2c3d4e5f60` rollback/re-upgrade를 확인했다.
- downgrade 후 `memory_entries` 부재, re-upgrade 후 head와 table 복원을 확인했다.
- 운영 DB migration은 여전히 실행하지 않았다.

## 최신 진행 업데이트 — 장편 기억 context 연결 완료 (2026-09-10)

- `GenerateContext.include_memory`(기본 true)와 `include_draft_memory`(기본 false)를 추가했다.
- generate/canon 공통 `build_context_bundle`이 승인·최신·현재 시간축 기억만 prompt block으로 넣는다.
- `included_memory_entry_ids`를 metadata에 기록하고, 요청에서 memory 주입을 끌 수 있다.
- 백엔드 전체 **280 passed**, 프론트 production build 성공.

### 남은 게이트

1. 운영 DB는 백업 후 `alembic upgrade head`를 별도 승인·실행해야 한다. 현재 작업에서는 실행하지 않았다.
2. 자동 요약/backfill과 memory 관리 UI는 별도 범위다.
3. 실제 모델 평가와 Windows 실기기 QA는 외부 입력/장치가 필요하다.

## 최신 진행 업데이트 — 장편 기억 최소 수직 슬라이스 구현 (2026-09-10)

- `MemoryEntry` provenance/revision/time-scope 모델과 `long_memory` 선택 서비스를 추가했다.
- Alembic migration `1b2c3d4e5f60`을 추가하고 임시 DB head upgrade를 검증했다.
- 신규 장편 기억 테스트 2개와 전체 backend **279 passed**를 확인했다.
- 아직 prompt 자동 주입, UI, 자동 요약/backfill, 운영 migration은 실행하지 않았다.

### 다음 게이트

1. memory context를 generate/canon prompt에 연결할 contract와 payload 회귀를 별도 확정한다.
2. 운영 migration 전 backfill·rollback·negative corpus를 검증한다.
3. 실제 모델·Windows·운영 DB 작업은 기존 승인 조건을 따른다.

## 최신 진행 업데이트 — 안전한 dry-run과 Windows 정적 점검 완료 (2026-09-10)

- 백업 dry-run 결과: [`docs/audits/backup-restore-dry-run-2026-09-10.md`](docs/audits/backup-restore-dry-run-2026-09-10.md)
- 임시 SQLite를 Alembic head까지 생성하고 backup API로 복원했다. `integrity_check=ok`, foreign key 오류 0, head `0a1b2c3d4e5f`, 논리 row 복원 PASS.
- Windows 정적 점검에서 CRLF shell script 문제를 재현했다. `scripts/prod.sh`, `scripts/dev.sh`를 LF로 정규화했고 `bash -n`이 통과했다.
- 실제 운영 DB·keyring·Windows 장치·provider는 사용하지 않았다.

### 다음 게이트

1. 장편 기억은 schema/migration 구현 승인을 별도로 확정한다.
2. 백업·복원은 key recovery plan과 temp restore failure injection을 추가 검증한다.
3. Windows는 지정 장치에서 DPAPI·브라우저·NVDA·성능을 수동 실행한다.
4. 실제 모델 평가는 사례·provider·가격·평가자를 확정한 뒤 실행한다.

## 최신 진행 업데이트 — 남은 작업의 안전한 설계 완료 (2026-09-10)

- 장편 기억: `docs/audits/long-memory-design-2026-09-10.md`
- 백업·복원: `docs/audits/backup-restore-design-2026-09-10.md`
- Windows 실기기 QA: `docs/audits/windows-device-qa-plan-2026-09-10.md`
- 세 문서는 read-only 설계다. 운영 DB·실제 모델·Windows 장치·배포는 건드리지 않았다.
- 실제 모델 평가 실행은 실제 사례 6개, provider/model 가격, 평가자와 별도 실행 승인이 준비될 때까지 보류한다.

### 남은 실행 게이트

1. 장편 기억은 schema 후보·migration·negative corpus를 별도 승인한다.
2. 백업·복원은 temp DB dry-run과 key recovery plan을 먼저 승인한다.
3. Windows QA는 장치·포트·테스트 key/DB를 지정한 뒤 수동 실행한다.
4. 실제 모델 평가는 비용 cap과 raw usage evidence를 확보한 뒤 실행한다.

## 최신 진행 업데이트 — 실제 모델 품질 평가 설계 완료 (2026-09-10)

- 설계 보고서: [`docs/audits/ai-model-quality-evaluation-design-2026-09-10.md`](docs/audits/ai-model-quality-evaluation-design-2026-09-10.md)
- 실제 승인 원고 6개 파일럿, hard contract gate와 blind 문학 rubric을 분리했다.
- USD 20 hard cap, provider usage 기반 비용 기록, 임시 DB/전용 포트만 사용하도록 정했다.
- 실제 provider 호출·비용 발생·운영 DB 접근은 하지 않았다.

### 다음 게이트

1. 실제 사례 6개의 ID와 source owner를 manifest에 확정한다.
2. provider/endpoint/model/가격표와 두 독립 평가자를 확정한다.
3. 위 증거가 준비된 뒤에만 파일럿 실행을 승인한다.

## 최신 진행 업데이트 — AnyIO/Starlette 호환성 조사 완료 (2026-09-10)

- 조사 보고서: [`docs/audits/anyio-starlette-httpx-compatibility-2026-09-10.md`](docs/audits/anyio-starlette-httpx-compatibility-2026-09-10.md)
- 직접 원인은 Starlette 1.6.0의 `httpx` fallback과 AnyIO 4.15.1의 `BlockingPortal` alias deprecation이었다.
- `backend/requirements.txt`에 `anyio>=4.14,<4.15`, `httpx2>=2.0.0`을 추가했다.
- 최종 requirements 격리 설치 + deprecation strict 전체 백엔드 회귀: **277 passed**. 프론트 빌드: **exit 0**.
- 운영 반영·배포·운영 DB 접근·실제 모델 호출은 하지 않았다.

### 다음 작업

1. 실제 모델 품질 평가의 평가셋·채점 기준·비용 상한·provider를 확정한다.
2. 승인된 기준으로 read-only 평가 설계와 acceptance evidence를 작성한다.
3. 외부 API 호출과 비용 발생은 별도 승인 전까지 금지한다.

## 최신 인계 — 관리 무결성·Vite 경고 정리 및 후속 계획 (2026-09-09)

### 현재 진행사항

- 관리 무결성 결함 6개, 회차가 0개인 작품의 복선 reminder 500 결함, lorebook `category + limit` FTS 결함을 TDD로 수정했다.
- `frontend/vite.config.ts`의 중복 `build` 키를 제거했다. 유효한 `react-vendor/editor/markdown` 청크 설정은 유지했다.
- 운영 반영·배포·운영 DB 접근·실제 모델 호출은 하지 않았다.
- 미추적 `.eval_tmp/`, `.omo/`, 원시 감사자료는 커밋하지 않았다.

### 수정 범위

- `backend/app/routers/scenes.py`: 다른 회차 scene reorder 거부(`422`), 외부 scene 보존
- `backend/app/routers/foreshadows.py`: 다른 작품 회차 planted/resolved 참조 거부(`422`); 회차 0개 reminder에 `latest_chapter: null` 반환
- `backend/app/routers/characters.py`: 관계가 있는 character 삭제 거부(`409`), 관계 보존
- `backend/app/routers/projects.py`: 복선 참조 chapter 삭제 거부(`409`); reorder에서 명시적 `volume: null` 처리
- `backend/app/services/fts.py`, `backend/app/routers/lorebook.py`: project/category scope 후 FTS `LIMIT`; LIKE fallback scope 유지
- `frontend/vite.config.ts`: dead duplicate `build` 블록 제거

### 검증·배포 결과

- 관련 backend 테스트: **54 passed**
- 백엔드 전체 safe runner: **277 passed**
- 격리 관리 무결성 harness: 7개 후보 모두 `candidate_reproduced: false`
- 프론트 `npm run build`: **exit 0**, 중복 `build` 경고 없음; `react-vendor/editor/markdown` 청크 생성
- 독립 Vite review: **PASS**, `git diff --check` 통과
- AnyIO/Starlette deprecation warning 1건은 `backend/.venv/.../starlette/testclient.py:53`의 설치 의존성 코드에서 발생한다. 억지 suppression이나 무승인 의존성 업그레이드는 하지 않았다.
- 로컬 `HEAD`와 `origin/main`: **946f61b** 일치
- 최신 커밋: `946f61b fix: remove duplicate vite build configuration`

### Orca 상태

- Vite 구현 Task `task_2efa6ab75780`: **DONE**
- Vite 독립 review Task `task_b3ccf82d0105`: **PASS**
- 후속 조사 Run `run_171c0158883a`의 경고 조사 `task_15a248da6002`와 장기 과제 분해 `task_ea805d74d020`: `Reconnecting` 정체로 **BLOCKED** 처리했다. 동일 프롬프트는 재시도하지 않는다.
- 해당 후속 조사에서는 소스·문서·커밋·push 변경이 없었다.

### 진행해야 할 사항

1. **AnyIO 경고 호환성 조사**: 격리 환경에서 FastAPI/Starlette/AnyIO/httpx 호환 버전을 확인한다. 경고 숨김보다 업그레이드·고정·보류를 비교하고, 승인 전 의존성 파일은 수정하지 않는다.
2. **실제 모델 품질 평가**: 먼저 평가셋·채점 기준·비용 상한·provider를 확정한다. 사용자의 명시 승인 전에는 외부 API 호출과 비용 발생을 하지 않는다.
3. **장편 기억**: chapter/context bundle, canon·revision·stale 판정의 저장 경계와 회귀 테스트를 설계한 뒤 별도 승인을 받는다.
4. **백업·복원**: 백업 포맷, 암호화 키 취급, restore dry-run, 무결성 검증, 실패 복구 절차를 설계한다. 운영 DB에는 접근하지 않는다.
5. **Windows 실기기 QA**: 사용자가 지정한 Windows 장치에서 포트·파일 경로·인코딩·실행 패키징·복원 시나리오를 검증한다.
6. 각 항목은 독립 Task로 분리하고, 구현 전 read-only 조사와 acceptance evidence를 먼저 확정한다. 실제 변경은 별도 승인 후 진행한다.

### 운영 제약

- 운영 반영·배포·운영 DB 접근·실제 모델 호출은 별도 승인 없이는 진행하지 않는다.
- `.eval_tmp/`, `.omo/`, 원시 감사자료는 커밋하지 않는다.
- 새 검증은 기존 서비스를 종료하지 않고 임시 DB와 전용 포트를 사용한다.

## 최신 인계 — 남은 작업과 main 공유 (2026-09-08)

- 현재 작업·게시 대상은 **main**이다. 검증된 기존 변경을 fast-forward로 통합했으며 이번 인계에서 앱 소스는 수정하지 않았다.
- 사용자 승인 범위는 남은 작업 문서화·main 커밋·push다. 후속 기능 구현·실제 AI 호출/비용·운영 DB 접근·배포 승인은 포함하지 않는다.
- 이 섹션 작성 당시에는 [남은 작업 인계](docs/handoffs/2026-09-08-remaining-work.md)를 기준으로 관리 무결성 후보의 격리 재현과 수정 범위를 확정하는 단계였다. 현재 상태와 다음 게이트는 위의 최신 인계를 기준으로 한다.
- 원고 보존과 AI 맥락 일관성은 완료 상태다. 아래 과거의 feature 브랜치/미push 기록은 검증 당시 이력이다. 이번 공유 대상은 main이며 운영 미배포 상태는 유지한다.
- 임시 DB·원시 로그·기존 미추적 자료는 일괄 커밋하지 않는다. push 성공 여부는 원격 main ref와 로컬 HEAD 일치로 확인한다.

## AI 맥락 일관성 검증 당시 인계 — 2026-09-08

- 승인된 AI 맥락 작업은 구현·독립 Spec/Standards 검토·최종 검증을 마쳤다. **운영 미배포**다.
- 소스 커밋: `cd7fc1f3360b6e42d49ab75398b94732ed057649` (`feat/ai-context-consistency`). merge/push/운영 마이그레이션은 하지 않았다.
- 현재 상태·검증 수치·제한은 [최종 검증](docs/audits/ai-context-final-validation.md)이 기준이다. [사용·재검증](docs/runbooks/ai-context-consistency.md), [다음 작업의 검증 규칙](docs/audits/ai-context-lessons.md)을 따른다.
- 남은 범위: 실제 모델/문학 품질, 장편 기억, 운영 배포는 별도 작업이다. 기존 dirty/untracked 자료를 보존했다. 새 검증은 기존 서비스를 종료하지 않고 새 임시 DB와 전용 포트에서 한다.
- 아래 기존 인계 기록은 보존한다. 그 안의 AI 맥락 진행 중 문구는 당시 이력이며, 다른 작업의 완료를 뜻하지 않는다.

---

> **이전 단계 인계**: [원고 보존 1단계 구현·검증 결과](#원고-보존-1단계--구현독립-검증-완료-운영-미적용). 현재 AI 맥락 작업 상태는 위의 최신 인계와 최종 검증 링크를 따른다. 아래 초기 단계 기록은 당시 이력이다.
> **최초 작성일**: 2026-08-24 (세션: 01a033b5-b61c-71cd-b3db-427e9d370bcd)
> **작성 목적**: 지금까지의 조사·검증·결정 사항을 다음 세션/작업자가 이어갈 수 있도록 핸드오프화

---

> **아카이브 구간 안내:** 아래 `## 1` 이후의 초기 요구사항·Sprint·LM Studio/다중
> endpoint 기록은 작성 당시의 historical log다. 현재 구현과 다음 작업의 기준은 문서
> 상단의 최신 인계, `docs/DOCUMENT_STATUS.md`, `대시보드_MVP_사양.md` v0.6 및
> `기술설계_GPT_OAuth_브릿지_v1.md`이며, 과거 API key/endpoint·실 provider 실측은
> 현재 release evidence가 아니다.

## 1. 프로젝트 개요

- **목표**: 소설(웹소설) 작성을 위한 오픈소스 도구 조합 + "하나의 대시보드"로 통합
- **최종 사용자**: 한국 웹소설 작가 (노벨피아·문피아 병행 연재 전략 채택)
- **핵심 요구**:
  - 시나리오(시놉시스/플롯) 관리
  - 캐릭터 관리 (캐릭터 카드 · 관계)
  - 세계관(월드빌딩) 관리
  - 장면/챕터(회차) 관리
  - AI 집필 보조 (모델 무관 방식)
- **현재 단계**: 리서치 완료 → 대시보드 설계 협의 → 제작 전

---

## 2. 핵심 결정 사항 (확정)

| 항목 | 결정 | 비고 |
| ------ | ------ | ------ |
| 플랫폼 전략 | **노벨피아 + 문피아 병행 연재** | 무료 연재는 병행, 유료 전환은 단일 선택(독점 조항 확인 필요) |
| AI 연결 | **Ollama 불사용** → 모델 무관(OpenAI 호환 API) 대시보드 설계 | LM Studio / KoboldCpp / 클라우드(GPT·Grok·Claude) 어느 것이든 연결 가능 |
| 대시보드 구성 | 원고/회차 에디터 + 캐릭터 관리 + 세계관(로어북) + AI 패널 | FastAPI + 경량 웹 프론트 (MVP 먼저) |
| AI 사용 방침 | 인간이 검수하는 보조용 (AI 티 제거 윤문 포함) | 플랫폼 규정 준수 방향 (공모전 AI 전면 금지 등) |
| 후속 스킬 | im-not-ai(Humanize KR) 설치 검토 중 | MIT, 한국어 AI 티 제거 윤문 — 설치 대기 |

---

## 3. 진행 현황 (2026-08-24 세션 기준)

**✅ 완료된 리서치**

1. 오픈소스 소설 작성 도구 조사 (도구·AI 생성·스킬 전체) — `부록01`
2. 웹소설 시장·수익 검증 (사실 확인) — `부록02`
3. 플랫폼 AI 규정 + 신인 시작 비교 (문피아·노벨피아·조아라) — `부록03`
4. im-not-ai(Humanize KR) 스킬 평가 — `부록04`
5. 병행 연재 규정·사례 — `리서치_병행연재_규정_사례.md`
6. 병행 연재 최적 장르 추천 — `추천_병행연재_최적장르.md`
   - (genre-fit-researcher는 파싱 지연으로 삭제, 확보 데이터로 결론 도출)

**⏳ 대기 중 (사용자 결정 필요)**

1. **표준 파이프라인 진행** (AGENTS.md §0 순서):
   - [x] 1단계 요구사항 분석 ✅ `요구사항_정의서.md` (2026-08-25, FR 60개·NFR·수용 기준) — **✅ 사용자 승인 완료**
   - [x] 2단계 리서치 ✅ 부록01~04 + 규정·장르 / **+2차 정밀분석 완료**: `부록05_오픈소스_최적조합.md` (2026-08-25) — GitHub·npm·PyPI 실측 기반 9개 레이어 비교, 최종 조합 확정(Vue3+Vite·CodeMirror6·FastAPI+SQLAlchemy2.x·SQLite WAL·자체 ST카드 파서·openai SDK·jsdiff·Naive UI·Pinia), 라이선스 리스크 정리(CodeMirror 아카이브·PrimeVue 배제·AGPL 오염 금지), 사양 v0.2 반영 항목 8건 도출
   - [x] 2단계 리서치 ✅ 부록01~04 + 규정·장르 (파이프라인 선행 수행분, 보완 리서치는 필요 시)
   - [x] 3단계 기획 ✅ `대시보드_MVP_사양.md` **v0.2** (2026-08-25) — React 전환(사용자 결정: shadcn/ui+Tailwind·Zustand), 요구사항 FR/NFR 역참조, 부록05 반영 8건, §6 UI 가이드라인 React 기준 재작성 — **승인 대기**
   - [x] 4단계 디자인 (MiniMax M3) ✅ `디자인_화면설계서_v1.md` **v1.1** — QA 정합성 검증 통과
   - [x] 기획 QA 게이트: `QA_기획정합성_리포트.md`(조건부 통과) → 사양 v0.3·요구사항 개정·설계서 v1.1 수정 → `QA_기획정합성_리포트_v2.md` **✅ 최종 통과(개발 착수 가능)** — 회귀 R-1~R-3 정정 완료
   - [x] 디자인 프로토타입 ✅ `프로토타입/index.html` (MiniMax M3, 자기완결 HTML) — **사용자 승인 완료(2026-08-25)**
   - [x] 5단계 개발 진행 중 — Sprint 1 ✅ (FastAPI 스캐폴딩 + DB 모델 + 프로젝트/회차 CRUD, 26 테스트)
   - [x] 5단계 개발 진행 중 — Sprint 2 ✅ (캐릭터 카드 API + 로어북 API(FTS5 검색) + 회차 bulk reorder + Alembic 도입, 54 테스트 전부 통과)
   - [x] 5단계 개발 진행 중 — Sprint 3 ✅ **백엔드 완료** (AI 엔드포인트 관리+api_key 암호화(DPAPI→Fernet 폴백)·SSE 스트리밍 프록시·im-not-ai 윤문 연동(변경률 게이트 30% 경고/50% 차단 강제)·수락/거절 플로우, **97 테스트 통과**)
   - [x] 5단계 개발 — **프론트 완료(Sprint 4a·4b, npm run build 통과)**:
     - 4a: Vite+React+TS 스캐폴딩, 테마 토큰(다크 기본), Zustand 4스토어+TanStack Query, 3분할 셸, S1 홈·S2 에디터(CodeMirror6+미리보기+공백제외 카운트+자동저장)
     - 4b: S5 AI 패널(SSE 스트림 소비+끼워넣기/선택교체/복사), S6 윤문 리포트(A~J diff+게이트 게이지), S3 캐릭터, S4 로어북 검색, S7 설정(api_key 마스킹), 내보내기(.txt/.md)
     - 빌드 방식: ~/jippeel-build(ext4)에서 작업→rsync로 프로젝트 폴더 동기(/mnt/c 속도 문제 우회)
   - ⏭️ 다음: 6단계 QA — 백엔드 pytest 전수 + 프론트 빌드/E2E 점검 + 런타임 실측(sendBeacon 프록시 등)
   - [x] 6단계 QA ✅ `QA_개발검증_리포트.md` (2026-08-25) — **✅ 통과, MVP 출시 가능** (백엔드 97 테스트·프론트 빌드·런타임 스모크·Must 수용기준 대조 전부 통과, Critical 0건)

**✅ 외부 도구 흡수 적용 (2026-08-26, "필요한 모든걸 흡수해서 적용해")**

- 대상: NarraLume(Apache-2.0)·goink(**AGPL — 코드 비복사, 개념만**)·oh-story-claudecode(MIT) → 상세 분석은 `부록06_외부도구_흡수_분석.md`
- **로어북 자동 주입 v1 구현** (백로그 P1 달성): `services/injection.py` — 본문·지시문에 언급된 로어(title/keywords 점수 매칭) 상위 K개를 `/ai/generate`에 자동 주입. `context.auto_lore`·`auto_lore_limit` 파라미터, SSE start 이벤트 `injected_lore` 공개. P1 원칙 유지(원고 자동 삽입 아님)
- **빌트인 프롬프트 프리셋 6종 시드**: `services/presets_seed.py`(이름 기준 멱등) — 이어쓰기/장 끝 후크/감정 기복 설계/대화 잠재의식/장면 확장/AI 티 제거 스타일 (oh-story 방법론 한국형 재해석)
- 프론트 S5: "로어 자동 주입" 체크박스 + 주입된 로어 배지 표시 + 전송 고지 문구 보강 (aiPanelStore/aiStream/AiPanel)
- QA Minor #3 해소: vite manualChunks(react-vendor/editor/markdown) 분리 — 빌드 경고 제거
- 검증: 백엔드 **117 passed**(신규 12 포함) / 프론트 `npm run build` 통과(TS 0 오류·청크 경고 0)
- 환경 정비: requirements.txt 누락 의존성 명시(openai·sse-starlette·cryptography), im-not-ai Windows 클론(`~/.agents/im-not-ai`)으로 네이티브 pytest 전수 가능
- 후속 로드맵(부록06 §2): 임베딩 시맨틱 검색 v2(sqlite-vec+한국어 ONNX), canon 충돌 게이트(NarraLume), Run Center, 복선 관리, 독자 인지 추적

**✅ 잔여 과업 소화 (2026-08-26 2차 — "남은작업진행해")**

- **QA Minor 3건 전건 해소**: ① sendBeacon 언로드 플러시가 POST라 PUT-only 백엔드에서 405 → `POST /chapters/{id}/content` 별칭 추가(실제 결함이었음) ② Py3.14 starlette 경고 재현 안 됨·종결 ③ vite 청크 분리 완료
- **크로스플랫폼 결함 수정**: `humanize.run_subprocess`에 encoding="utf-8" 명시 — Windows cp949에서 verify_gates 크래시하던 버그(WSL 무증상)
- **E2E 6/6 passed**: Windows 네이티브 환경 신규 구축(`scripts/fake_llm_server.py` 가짜 LLM :1234 + `scripts/e2e_refine_stub.py` 윤문 스텁 + venv python3.exe 심) 후 전 시나리오 통과. S1~S7 종단 + 정리 블록 포함
- **플랫폼 규정 추적** ✅: `규정추적_2026-08.md` — 핵심 변화는 AI 기본법(2026-01-22) 생성물 표시 의무 + Claude 텍스트 워터마크(2026-08~). 노벨피아 약관 개정(08-06) 세부 확인은 다음 주기. 문피아 공모전 AI 금지 재확인, 조아라 무규정 유지
- **노벨피아 PLUS 체크리스트** ✅: `노벨피아_PLUS_전환_체크리스트.md` — 조건 확정(15화+편당 공백제외 3,000자+정산정보), jippeel 워크플로 매핑, PLUS 진행률 표시 기능 아이디어 백로그 등재
- 검증: 백엔드 **118 passed** (beacon 별칭 테스트 추가)

**🎉 표준 파이프라인 6단계 + 흡수 적용 + 잔여 과업 완료 — 남은 것: 실사용 피드백 / P2 백로그(SillyTavern 카드 연동, 임베딩 로어 검색 v2)**

**✅ 신규 기능: 작품 부트스트랩 (2026-08-25, "제목·목차·캐릭터 자동화" 요청)**

- POST /api/v1/projects/bootstrap — 장르+프리미스(선택) 한 줄로 제목 후보 5·로그라인·권/회차 목차(시놉시스)·캐릭터 4~6+관계·로어북 8~12를 LLM 3콜로 생성해 단일 트랜잭션 저장(JSON 파싱 실패 시 재시도→규칙 기반 폴백)
- S1 홈 '✨ AI로 작품 자동 생성' 마법사(Dialog: 장르/프리미스/권·회차 수 → 진단 단계 표시 → 결과 요약 → 프로젝트 열기)
- 백엔드 테스트 104→105 통과, 실호출 스모크 성공(프로젝트+5화+캐릭터4+관계3+로어북8 생성)
- ⚠️ 생성 품질은 연결된 LLM 품질에 종속 — 현재 :1234는 fake 모델이라 템플릿 수준 출력. 실사용 시 실제 모델(LM Studio 실 weights 또는 클라우드 키) 필요

**✅ E2E 안정화 (2026-08-25) — 6/6 passed × 2회 연속**

- 수정 1: S5 레이스 버그 — endpoints 로딩 중 클릭 시 토스트 조기반환 + 쿼리 settle 재마운트가 스트림 abort → 스트림 생명주기를 zustand로 승격, 첫 엔드포인트 자동 선택
- 수정 2: 윤문 환경변수 누락 — IM_NOT_AI_DIAGNOSE_CMD/REFINE_CMD 스텁(cp) 설정, scripts/dev.sh에도 반영
- 수정 3: S6 spans=[]일 때 비교 뷰 미렌더 → 성공 시 항상 원문/수정본 비교 영역 렌더
- 서버 운영: tmux 세션(jippeel-be/jippeel-fe) 권장 — bash 도구 타임아웃이 프로세스 그룹째 정리함

**✅ 자동화 보강 (2026-08-25, 사용자 요청 "수동 작업 최소화")**

- 원클릭 실행: `Jippeel실행.bat` (Windows 더블클릭 → WSL에서 백엔드+프론트 기동+브라우저 오픈) / `scripts/dev.sh`
- LM Studio(:1234) 자동 감지·엔드포인트 사전 등록
- UI E2E 자동화: `frontend/e2e/app-flow.spec.ts` — Playwright 6 시나리오(프로젝트 생성→집필→AI 스트리밍→P1 자동삽입 금지→윤문 게이트→api_key 마스킹) **6/6 passed × 2회 연속**, 스크린샷 자동 저장
- 실행법: `cd frontend && npx playwright test` (Chromium 라이브러리는 `~/.local/pwlibs` + LD_LIBRARY_PATH 방식, sudo 불필요)
- 참고: 빌드·E2E는 ~/jippeel-build(ext4)에서 수행 후 rsync 동기 — /mnt/c 속도 문제 우회

**✅ 추가 완료 (2026-08-25)**

- im-not-ai(Humanize KR) 스킬 설치 완료: `~/.agents/im-not-ai` 클론 → `~/.agents/skills/{humanize-korean,humanize,humanize-redo}` 심링크
- 실측 검증 완료: AI 티 샘플 윤문 파이프라인(standard 경로) 정상 동작 — 진단→윤문→final.md 생성 확인
- 작업별 모델 라우팅 규칙 확정: `AGENTS.md` 참조 (프론트=MiniMax M3 / 백엔드·QA·리서치·요구사항=ox-alpha)

**✅ Sprint 2 백엔드 완료 (2026-08-25, 사양 v0.3 기준)**

- `backend/app/routers/characters.py` — 캐릭터 CRUD + 관계(Relationship) 생성/목록/삭제 + `card_json` 병합 PATCH(`/characters/{id}/card_json`, RFC 7386 유사) (FR-201~205)
- `backend/app/routers/lorebook.py` — 로어 항목 CRUD + 카테고리 필터 + keywords[] 관리(PUT `/lore/{id}/keywords`) + FTS5 키워드 검색 GET `/projects/{pid}/lore/search?q=` (FR-301~305)
  - FTS5는 선택 적용(`app/services/fts.py`): unicode61 토크나이저 한계 보완 위해 쿼리를 `"term"*` 접두어 질의로 변환, 미지원 빌드·문법 오류 시 LIKE 폴백. CRUD에서 인덱스 동기화.
- `PATCH /api/v1/projects/{pid}/chapters/reorder` — 순서/권 bulk 변경(원자성 보장: 소속 아님·중복 id 시 422, 부분 적용 없음)
- **Alembic 도입**: `backend/alembic.ini`(script_location=%(here)s 고정) + `alembic/env.py`(DATABASE_URL 환경변수 우선, render_as_batch) + 초기 마이그레이션(전체 스키마 + FTS 인덱스 부트스트랩). `tests/test_migrations.py`로 upgrade head/downgrade base/idempotency 검증.
- 게이트: `.venv/bin/python -m pytest -q` → **54 passed**(Sprint 1 26개 포함). requirements.txt에 alembic>=1.13 추가.
- 잔여(다음 스프린트): AI 프록시(routers/ai_panel.py), 윤문 연동(routers/refine.py), 프론트엔드.

---

## 4. 다음 액션 (우선순위)

- [x] 1. 병행 연재 규정·사례 리서치 완료 (무료 병행 가능 / 유료 독점 제약 확인)
- [x] 2. 병행 유리 장르 최종 추천 완료 (남성향 판타지·무협 + 회귀·빙의)
- [x] 3. im-not-ai 스킬 설치 완료 (2026-08-25, 실측 검증 포함)
- [x] 4. 대시보드 MVP 제작 시작: **사양 문서 확정 완료(2026-08-25) → `대시보드_MVP_사양.md`**
      - 기술 스택 확정: FastAPI + SQLAlchemy + SQLite / Vite+React(TS) / CodeMirror 6 / shadcn/ui+Tailwind / Zustand
      - 4단계 디자인 ✅ `디자인_화면설계서_v1.md` (2026-08-25, MiniMax M3 작성) — §0 핵심UX 8원칙, §1 3분할 ASCII 레이아웃, §2 S1~S7 와이어프레임·shadcn 매핑·FR 역참조, §3 인터랙션 플로우 3개(집필/윤문/캐릭터), §4 HSL 토큰·세리프, §5 Zustand 4스토어, §6 단축키·a11y, §7 개발팀 구현 노트. **승인 대기**
      - 다음: ① 본 설계서 검토·승인 → ② 5단계 개발팀(FastAPI 스캐폴딩 + 프론트 1차 스프린트) → ③ 6단계 QA
      - 원고/회차 에디터 (마크다운)
      - 캐릭터 카드 관리
      - 세계관/로어북 관리
      - AI 패널 (OpenAI 호환 엔드포인트 설정 UI — 모델 무관)
      - 윤문 모듈 (im-not-ai 연동 예정)
      - (나중 단계) SillyTavern / novelWriter API 연동
- [x] 5. 로어북 자동 주입 — ✅ 완료(2026-08-26, 부록06 참조). 임베딩 v2는 백로그로 보류
- [x] 6. 문피아·노벨피아·조아라 AI 규정 최신 공지 추적 — ✅ `규정추적_2026-08.md` (다음 주기: 노벨피아 08-06 약관 개정문 확인)
- [x] 7. 노벨피아 PLUS 전환 체크리스트 작성 — ✅ `노벨피아_PLUS_전환_체크리스트.md`
- [x] 8. E2E 정식 재실행 — ✅ Windows 네이티브 환경 구축 후 **6/6 passed**(2026-08-26)

---

## 5. 중요 리스크 & 유의사항

- **AI 규정**: 문피아 = 일반 연재 본문·표지까지 AI 금지 / 노벨피아 = 공모전 금지, 일반 연재는 순수 창작 원칙 / 조아라 = 규정 미확인
- **AI 표시 의무**: 2026년 현재 3사 모두 명시적 표시 의무 없음 (단, 정책 수시 변경 — 연재 시작 전 최신 공지 필수)
- **수익 기대**: "AI로 돈 버는 시대"는 과장 — 창작자 평균 연수입 1,953만원, 연 4,000만원 이상 13.5%
- **탐지 리스크**: AI 초안 그대로 게시 시 독자에게 들키면 별점 테러·연재 중단 (문피아 AI 전면 금지는 규정 위반 소지)
- **병행 시 독점 조항**: 노벨피아 PLUS 비독점/독점, 문피아 매니지·유료화 시 독점 조건 — 유료 전환 전 반드시 확인

---

## 6. 부록 목록

| 파일 | 내용 |
| ------ | ------ |
| `부록01_오픈소스_리서치.md` | 소설 작성 도구·AI 생성 도구·스킬 전체 조사 결과 |
| `부록02_시장_검증.md` | 웹소설 시장 사실 확인 (수익 구조·트렌드·수치) |
| `부록03_플랫폼_정책.md` | 문피아·노벨피아·조아라 AI 규정 + 신인 시작 유리한 곳 비교 |
| `부록04_im-not-ai_평가.md` | Humanize KR 스킬 상세 평가 |
| `부록06_외부도구_흡수_분석.md` | NarraLume·goink·oh-story 흡수 분석 — 채택/보류/거부 판정, 라이선스 준수, 임베딩 v2 설계 메모 (2026-08-26) |
| `추천_병행연재_최적장르.md` | 병행 연재 최적 장르 추천 (확정) |
| `진행중_리서치.md` | 병행 연재 조사 현황 |
| `리서치_병행연재_규정_사례.md` | 병행 연재 규정·사례 상세 (리서처 원문) |
| `디자인_화면설계서_v1.md` | 4단계 디자인 산출물 — S1~S7 와이어프레임·컴포넌트·테마 토큰·Zustand 경계·개발 노트 (2026-08-25) |
| `프로토타입/index.html` | **4단계 디자인 정적 프로토타입** — S2/S5/S6/S7 4개 화면, 단일 HTML, 외부 의존 없음, HSL 테마 토큰·한글 세리프·FR 주석·jsdom 검증 완료 (95.8 KB) |

---
*최종 갱신: 2026-08-25 — 디자인 단계(4) 산출물(설계서 v1.1 + 정적 HTML 프로토타입) 작성 완료, 다음 단계는 디자인 승인 + 개발(5) 착수*

## 7. 디자인 프로토타입 (2026-08-25)

**✅ 정적 HTML 프로토타입 작성 완료** — `프로토타입/index.html` (95.8 KB, 단일 파일, 외부 의존 없음, 더블클릭으로 열림)

### 사양

- **기준 문서**: `디자인_화면설계서_v1.md` v1.1 + v1.2 갱신 반영
- **기술**: 단일 HTML — `<style>` 내장 CSS (HSL 테마 토큰 §4.1), 바닐라 JS (외부 라이브러리 0)
- **테마**: 저채도 다크 기본 + 라이트 전환 (◐ 버튼), 한글 세리프 시스템 스택 (Noto Serif KR, 본명조, Source Han Serif)
- **글꼴**: `font-family: 'Noto Serif KR', '본명조', 'Source Han Serif', 'Source Serif Pro', 'Pretendard', Georgia, serif`
- **반응형**: 데스크톱 우선 (≥1280px), 미니멀 폴백

### 포함 화면 (상단 탭 전환)

1. **S2 회차 에디터** — 3분할(좌 회차 트리 / 중 CodeMirror 자리 + 미리보기 탭 / 우 패널), 상단바(프로젝트 셀렉터·저장 상태 FR-106), 하단 상태바(글자 수 공백제외 카운트 JS 실제 계산 FR-104)
2. **S5 AI 패널** — 🛡 P1 Alert(FR-406) + ☁ NFR-201 전송 고지, 프롬프트 프리셋, 더미 스트리밍 결과(`✨ 생성 시작` 클릭 시 실제 토큰처럼 흘러나옴), [↪ 끼워넣기][⤳ 선택 교체][⧉ 복사] (P1·FR-406)
3. **S6 윤문 리포트** — 변경률 게이지(30% 경고선/50% 차단선 시각화), taxonomy ID A~J 색상 범례, 병렬 diff 뷰(원문/수정본, 삭제선/추가색), 진단 span 마크, [✓ 수락][✗ 거절] + 50% 초과 더미 케이스(수락 비활성·재실행/폐기만 C-2)
4. **S7 설정** — 6개 탭(AI/윤문/테마/규정·현황/백업/고급), AI 탭에 api_key 마스킹만 노출([표시] 버튼 완전 삭제 C-1), 규정·현황 탭에 NFR-404 Alert

### UX 원칙 적용 (설계서 §0)

- **P1** AI 자동 삽입 금지 (S5 상단 ShieldCheck Alert + S5 액션 3종) ✓
- **P2** 글자 수(공백 제외) 항상 노출 (S2 푸터, mono·굽게) ✓
- **P3** 저장 상태 "저장됨 · 방금 전" (FR-106, 디바운스 1.5s 시뮬레이션) ✓
- **P4** 윤문 30/50% 게이트 (게이지 색 + 임계선, block 시 수락 비활성 + 재실행/폐기) ✓
- **P5** 그리드+드로어 (S3·S4 미포함, 백엔드 후속 화면) — 본 프로토타입은 S2/S5/S6/S7 4개 화면
- **P6** AI 패널 전역 호출 (Alt+A 단축키 + 우측 상단 FAB + 우측 패널 토글) ✓
- **P7** 저채도 다크/라이트 + 세리프 본문 (HSL 토큰, 다크 기본) ✓
- **P8** 이모지·애니메이션 절제 (Alert/FAB에 ShieldCheck·CloudUpload 1개씩만) ✓

### 검증 완료

- ✓ HTML 파싱 (BeautifulSoup) — 4개 화면 모두 존재, alert 9개, diff 7개, diag-mark 8개
- ✓ JS 동작 (jsdom) — 탭 전환, 테마 토글, 글자 수 카운트 (테스트: "가나다 abc def" → 총 11자, 공백제외 9자), 우측 패널 토글, S7 탭 전환, 변경률 게이지 27.4% / pass
- ✓ 외부 의존 0 (`<link href>`, `<script src>`, `@import`, `url()` 모두 없음)
- ✓ FR/NFR 번호 HTML 주석 — 각 화면·컴포넌트에 FR-101~602 / NFR-201·202·204·301·302·303·401·403·404 표기

### 사용법

- **Windows 탐색기**에서 `프로토타입/index.html` 더블클릭 (Edge/Chrome 권장)
- **WSL**에서 `wslview 프로토타입/index.html` 또는 파일 탐색기에서 열기
- **단축키**: `Alt+A` AI 패널, `Alt+R` 윤문, `Esc` 패널 닫기
- **테마 전환**: 상단 ◐ 버튼 (다크 ↔ 라이트)
- **윤문 데모**: S6 탭 → [🔄 다시 실행] 버튼으로 12.4% / 27.4% / 41.0% / 62.1% / 73.5% 중 랜덤 게이트 시연

### 후속 작업

- [ ] 5단계 개발팀(ox-alpha-free)에 본 프로토타입 + 설계서 핸드오프 → `App.tsx` 셸 + 3분할 레이아웃 + 토큰 부트스트랩부터 착수
- [ ] 6단계 QA — 본 프로토타입을 시각 회귀 테스트 기준선으로 활용 (Chromatic 등)

---

## 게이트 파이프라인 완주 (2026-08-26 추가)

G0~G8 전체 통과(규약 v1). gates.json/traceability.json이 최신 상태 원본.
요구사항 R-054 → 기능 F-036 → 화면 S-053 → API A-040 → DB T-008 → 테스트 TC-094 추적 완결.
릴리스 노트: 릴리스_노트_MVP_v1.0.md. 다음 세션은 Known Issues와 백로그부터.

---

## GPT OAuth 초기 조사 기록 — 현재 설계로 대체됨 (2026-09-05 historical)

> 아래 기록은 endpoint 등록과 실제 provider 실측을 전제로 한 과거 메모다. 현재 구현의
> canonical 기준은 `기술설계_GPT_OAuth_브릿지_v1.md`이며, 실제 OAuth 수용은 아직 승인 대기다.

**과거 조사 결론(현재는 superseded)**

- 당시에는 OAuth bridge를 일반 endpoint로 등록하고 실 provider를 호출하는 방안을 기록했다.
- 현재 구현은 endpoint 등록·모델 변경·OAuth token 재사용을 전제로 하지 않는다.
- 실제 OAuth/ChatGPT 구독 호환성, 비용, 계정 정책은 검증하지 않았으며 승인된 수용 게이트로 남아 있다.
- 현재의 고정 provider 계약은 `기술설계_GPT_OAuth_브릿지_v1.md`와 이 문서 상단의 상태를 기준으로 한다.

---

## UI/UX 1단계 개선 + 삭제 버그 수정 (2026-09-06 추가)

**버그 수정: 프로젝트 삭제 FK 오류** — 관계(relationships)가 있는 프로젝트 삭제 시 500
(SQLAlchemy cascade가 Relationship을 못 닿음). delete 라우트에서 관계 행 선삭제 처리,
회귀 테스트 추가 → **pytest 119 passed**

**UI 1단계 개선 (사용자 혼란 제거 — 진단: 개발 잔재 노출이 핵심 원인)**

- 내부 용어 전면 제거: UI 노출 문자열에서 Sprint 4b / FR-xxx / NFR-xxx / (S7) / F-036 / 부록04·06 / 결정사항_G4 삭제 (개발 주석은 유지)
- 사이드바 맥락화: 회차 트리는 에디터(/write)에서만, 캐릭터·로어북은 전환 네비만, 홈의 미구현 필터 스텁 삭제, "⚙ 설정 (S7)"→"⚙ 설정"
- 상태바(회차·글자수·저장·AI)는 에디터에서만 표시
- 기본 프롬프트 프리셋 6종 시드(이어쓰기·새 장면·대사 다듬기·묘사 살리기·내용 요약·다음 화 훅) — `app/services/presets.py`, 빈 테이블에서만 삽입(멱등)
- E2E 자기완결화: FakeLM 엔드포인트를 beforeAll에서 등록→S5 명시 선택→afterAll 정리(기본 엔드포인트가 실모델이어도 독립 실행), 스트림 즉완 레이스는 or() 로케이터로 완화 → **E2E 6/6 passed**

**UI 2단계 개선 (2026-09-06 완료) — pytest 120 passed·E2E 6/6**

- 설정 카드 한글화(서버 주소/기본 모델/온도/추론 강도/API 키) + **reasoning_effort UI 선택 추가**
- 버그 수정: 설정 저장 시 temperature 빈 값이 0.7로 강제되던 문제(null 보존) — OAuth 엔드포인트 저장 시 다시 깨지던 원인
- AI 패널: 엔드포인트 온도 미설정이면 슬라이더 대신 "온도 미지원" 표시 + 요청에 temperature 미전송, 선택 프리셋 지시 내용 미리보기
- 홈 카드: 회차 수·누적 글자 수 표시(백엔드 /projects 목록에 chapter_count·total_chars 집계 추가)
- 전체 변경분 커밋 완료(4개 단위): 4df245b 문서·인프라 / cd14119 백엔드 / 828d9d2 프론트 / 6f3d561 세션 문서
- 참고: movestudio dev_server(:8000 충돌) — 두 프로젝트 동시 구동 시 포트 충돌 있음

---

## 출시 재판정 사이클 + 로어북 자동 주입 (2026-09-06 추가)

**✅ 요구사항_분석.md 지적사항 전수 검증·수정 완료** — 7건 중 5건 사실(수정), 1건 환경 한정(WSL에서 pytest 정상), 1건 선행 구현됨(reasoning_effort UI). 상세 판정은 세션 보고 참조.

**발견·수정된 핵심 결함 (F-Q3-1, P0)**

- 이탈 저장 플러시가 React 언마운트 클린업에만 존재 → **탭 닫기·새로고침에서 변경분 유실**
- 수정: `pagehide` 이벤트 병행 + sendBeacon(POST, 계약 불일치) → **keepalive fetch PUT** 전환
- E2E TC-038 시나리오로 자동 검증됨

**글자 수 기준 통일 (F-Q3-3)**

- word_count_cache를 노벨피아 모드(공백·문장부호·특수문자 제외, 문자·숫자만)로 통일 — 푸터·위젯·PLUS 판정 동일 기준(부록06)
- 기존 데이터 캐시는 다음 저장 시 갱신됨(즉시 재계산 필요 시 PUT content 재호출)

**로어북 자동 주입 (백로그 P1 → 구현)**

- `POST /ai/generate`에 `context.auto_lore` — 본문에 로어 제목·키워드(2글자+) 등장 시 자동 포함(상한 12건, 명시 선택과 중복 제외)
- AI 패널에 "세계관 자동 포함" 체크박스(기본 ON, 회차 있을 때만 활성)

**검증 결과**

- backend pytest **122 passed** / frontend build 통과(청크 분할: 908KB→4개) / **E2E 8/8 × 2회 연속**
- 신규 E2E: TC-038(이탈 플러시 보존)·TC-308(미리보기 XSS 차단 — script 미실행·onerror 제거)
- TC-037 백업 실측 **PASS**: db-info → 3파일 복사 → 데이터 동일성 (스크립트: scripts/backup_verify.py)
- 게이트 갱신: gates.json G6/G7/G8·traceability R-043 implemented(Q5 방식) — QA_개발검증_리포트_v3.md 참조

**잔여 pending-manual**: NVDA(TC-503~505)·시니어 모드·성능 계측(TC-401~405)·Windows keyring(TC-302) — 실기기 필요. a11y 자동 스캔(TC-501 자동화분)은 도입 완료 — axe-core critical·serious 0건.

---

## 집필 프롬프트 고도화 + a11y 자동화 + 원격 병합 (2026-09-06 후반)

**✅ 원격 병렬 커밋(baf4527) 리베이스 통합** — 8/26 병렬 세션의 로어 자동 주입 구현(injection.py 점수 기반·SSE start 주입 공개·limit/project_id)을 채택해 내 구현과 통합. humanize utf-8 고정(Windows cp949 수정)·requirements 핀·conftest 시드도 흡수. 통합 후 **137 passed·E2E 9/9**.

**✅ 집필 프롬프트 고도화(백로그)** — ① /ai/generate에 웹소설 문체 system 프롬프트 기본 적용 ② `context.previous_chapter` 옵션: 직전 회차 끝부분 2,000자 자동 주입(이어쓰기 맥락) — AI 패널 체크박스에서 제어.

**✅ a11y 자동 스캔 도입(TC-501 자동화분)** — @axe-core/playwright로 전 화면 스캔 E2E 추가(e2e/a11y.spec.ts), critical·serious 0건 달성. 수정: progressbar 접근명, destructive/status-draft 색 대비 보정, **Tailwind 색상 `<alpha-value>` 전환**(기존 /투명도 클래스 무작동 버그 수정). baseline 리포트는 e2e/a11y/baseline.json.

**✅ 청크 재분할** — 908KB 단일 → react 162/editor 475/markdown 130/앱 144/data 47KB, 전 청크 500KB 미만(경고 소멸).

**✅ 릴리스 노트 v1.1** 갱신(릴리스_노트_MVP_v1.0.md 하단). 잔여: NVDA·시니어 모드·성능 계측·Windows keyring 실기기 항목, 자동 백업·복원, SillyTavern 연동, UI 3단계.

---

## 완성도 고도화 v1 (1~4단계) — 2026-09-06 최종

> 사양: `고도화_사양_완성도_v1.md` (G-001~G-032). 목표: "이 화 단위 보조" → "장편 연재 서사 일관성 + 회차 품질 루프"

**P1 — 맥락 주입 고도화**

- G-001 목차 자동 주입: `GenerateContext.auto_outline` — 현재 회차 memo(부트스트랩 시놉시스·핵심 사건) + 다음 회차 전개 방향(600자)을 `[이번 회차 목표(목차)]`·`[다음 회차 예고]` 블록으로 주입. SSE start `injected_outline` 공개. AI 패널 "목차 자동 포함" 체크박스(기본 ON)
- G-002 부트스트랩 이름 일관성: 콜 1(idea)에서 `protagonist_name` 확정 → 콜 2(목차, "다른 이름 금지")·콜 3(캐릭터, "주연 name 강제") 전달. 프로젝트 memo에도 보관. 3콜 이름 교차 불일치 해소

**P2 — 장면(Scene) 구조화**

- `scenes` 테이블(Alembic e8f0a1b2c3d4) + CRUD·reorder(422 원자성) — `routers/scenes.py`
- G-012: `GenerateContext.scene_id` — `[현재 장면]` 블록으로 장면 단위 집필. AI 패널 "현재 장면" 셀렉트 + 장면 관리 Dialog(`SceneManager.tsx`)

**P3 — 복선 + canon 게이트**

- `foreshadows` 테이블(같은 마이그레이션) + CRUD·상태(설치|회수|보류) — `routers/foreshadows.py`, `pages/ForeshadowsPage.tsx`(사이드바 "🧵 복선")
- G-022: `GenerateContext.auto_foreshadow` — 미회수(설치) 복선 상위 5개 `[미회수 복선]` 블록 주입 + SSE 투명성 + 패널 체크박스(기본 ON)
- G-023 canon 검사: `POST /canon-check` — 회차 본문+캐릭터+로어+미회수 복선을 LLM 1콜(JSON, repair 재시도)로 모순 후보 반환. `services/canon.py`. 응답만 반환(원고 자동 수정 없음)

**P4 — 회차 품질 진단(로컬 규칙 기반, LLM 불필요)**

- `services/quality.py` — 대사 비율·초단문 리듬·어미 반복·접속사 남발·문단 첫머리 다양성·후크(끝 300자)·노벨피아 글자 수 → 0~100점 + 한국어 제안 + 제안 프리셋(장 끝 후크·AI 티 제거·이어쓰기)
- `GET /chapters/{id}/quality` + 에디터 FAB "품질 진단" Dialog(제안 프리셋 클릭 → AI 패널 프리셋 선택, 자동 실행 없음)

**결함 수정(발견 즉시)**: 프로젝트 삭제 시 foreshadows FK 오류(Relationship 사례 동일) — `Project.foreshadows` cascade 추가 + 회귀 테스트

**검증**: backend pytest **155 passed** / frontend `npm run build` 통과 / **E2E 8/8**·a11y axe 1/1(critical·serious 0) / 실호출 스모크: 목차·복선·장면 주입 SSE 확인 + gpt-5.6-luna(OAuth) 실모델 스트리밍·canon-check 200 OK

**잔여(백로그)**: canon-check 결과 이력 저장, 임베딩 로어 검색 v2, 장면 → 회차 본문 조립(G-013), 복선 키워드 기반 자동 등록, 품질 지표 metrics_v2(im-not-ai) 정량 엔진 연동, 시니어 모드·성능 계측(기존 잔여)

---

## 고도화 v2 (잔여 소화 + 품질 도약) — 2026-09-06 후반

> 커밋 18c6181(고도화 v1) 이어서. 사양 문서: `고도화_사양_완성도_v1.md` + 본 섹션

**1. 뒷마무리**

- G-041 canon 이력: `canon_runs` 테이블 — POST /canon-check가 run_id 반환, `GET /canon-check/runs?chapter_id=` 재조회
- G-041 품질 이력: `quality_checks` 테이블 — GET /quality 시 본문 해시가 바뀐 경우만 기록, `GET /chapters/{id}/quality/history` 추이
- G-042 후크 자동 점검: 회차 상태 '완료' 전환 시 품질 진단(기록 없이) → 후크 없으면 토스트 경고(차단 없음)
- G-013 장면→본문 조립: `PUT /chapters/{cid}/content_from_scenes` + 장면 관리 Dialog "⤓ 본문으로 합치기"(명시 클릭 전용)
- G-046 복선 자동 추출: `POST /projects/{pid}/foreshadows/suggest` — 회차 본문에서 떡밥 후보 LLM 추출(기존 복선 제외) → 복선 페이지 후보 카드에서 선택 등록(자동 등록 없음)

**2. 기존 잔여**

- 커밋 2건 완료(18c6181 고도화 v1 / 본 세션 v2). canon-check UI ✅(에디터 FAB "모순 검사" Dialog — 모순 목록+severity+이력)
- NVDA·시니어 모드·성능 계측·Windows keyring: 실기기 수동 항목(변동 없음). 임베딩 v2: 여전히 백로그

**3. 품질 도약**

- G-045 독자 인지 추적: `foreshadows.audience_knows` — 복선 페이지 토글("독자 인지"). canon 검사가 "독자가 이미 아는 사실을 처음 밝히는 것처럼 쓴 케이스"도 지적
- G-050 권 개요 레이어: `volume_notes` 테이블(개요·감정 곡선·고봉 노트) + "📐 기획" 페이지 + auto_outline 시 권 개요 자동 주입
- G-051 canon 검사 확장: 직전 회차 끝부분(1,000자) + 시간축·위치·독자 인지 검사 지침을 프롬프트에 명시
- G-040 문체 프로파일: `projects.style_profile` + 기획 페이지 편집(1.5초 디바운스 저장) + AI 패널 "문체 프로파일 적용" 체크 → system 프롬프트 결합

**4. 기술 부채**

- G-060 AI 사용량: `ai_usage` 테이블(문자량 기반 — 토큰 집계 신뢰 낮음) — generate/canon/bootstrap/foreshadow_suggest 자동 기록, S7 AI 탭 상단 "AI 사용량(최근 30일)" 카드, `GET /ai/usage`
- dev.sh: :8000 점유 중 /health 실패 시 movestudio 충돌 경고 추가. rsync 동기화 절차는 기존 문서 유지

**운영 DB 마이그레이션 주의**: dev DB는 create_all이 테이블을 먼저 만들어 alembic과 어긋난 케이스 발생 → 컬럼 수동 추가(foreshadows.audience_knows, projects.style_profile) 후 `alembic stamp f9a1b2c3d4e5` 처리. 신규 환경은 `alembic upgrade head` 한 번이면 됨

**결함 수정(발견 즉시)**: 프로젝트 삭제 시 canon_runs·quality_checks FK 캐스케이드 누락(3번째 동일 패턴) — Chapter 관계 cascade 추가 + 회귀 테스트

**검증**: backend pytest **165 passed** / frontend build 통과 / **E2E 9/9**(app-flow 8 + a11y 1) / 실호출 스모크: 권 개요·문체 프로파일·품질 이력(해시 dedup)·canon(gpt-5.6-luna, run_id)·떡밥 추출·장면 조립·usage 집계·삭제 회귀 전부 200/204

**✅ 부트스트랩 권 개요 동시 생성 + 복선 본문 매칭 (G-050 확장·G-047, 커밋 26855d2)**: ① 부트스트랩 콜 2가 권 개요·감정 곡선·고봉을 함께 생성해 volume_notes 저장(폴백 포함, 결과 Dialog에 안내) ② `GET /projects/{pid}/foreshadows/match` — 본문에 언급된 복선 배지를 AI 패널에 표시(로어 주입과 동일 매칭 방식). 백로그 2건 제거. 검증: pytest 168 / E2E 9/9 / 실호출 스모크

**✅ 고도화 v3 (커밋 3960300, 2026-09-06): 시맨틱 로어 v2·metrics_v2·복선 리마인드·수동 QA 가이드**

- G-070 시맨틱 로어 v2: `services/semantic.py`(문자 2-gram 코사인, 제로디펜던시) — 부록06 §4 하이브리드 설계의 근사 구현. `auto_lore_semantic` 플래그(AI 패널 체크박스)로 형태소 변형·대명사 지칭 보완. ONNX 임베딩 교체 지점: `semantic.semantic_score` 인터페이스만 유지하면 됨
- G-071 metrics_v2 연동: 품질 진단에 im-not-ai 정량 엔진 병합 — "선택 적용" 패턴(스킬 `~/.agents/im-not-ai` 있으면 metrics.v2 병합+risk_band 표시, 없으면 폴백). IM_NOT_AI_METRICS_DIR 환경변수로 경로 오버라이드
- G-048 복선 회수 리마인드: `GET /foreshadows/reminder?window=5` — 설치 복선의 마지막 언급 회차 전수 스캔 → 최근 window화 미언급/무언급 = stale. 복선 페이지 상단 리마인드 카드
- `QA_수동검증_가이드.md` 신설 — TC-302(DPAPI PowerShell 원라이너)·TC-401~405(성능 계측 절차)·TC-503~505(NVDA 체크리스트)·시니어 모드 판정 자료. 실기기에서 표 채우기만 하면 pending-manual 전량 소화
- 검증: pytest **171 passed** / build / E2E 9/9 / 실호출 스모크(reminder stale 판정·v2 risk_band 병합) 통과

**다음 백로그 후보**: ONNX 임베딩 교체(semantic_score 인터페이스 — 모델 파일 다운로드 필요), 실기기 수동 QA 실행(가이드 준비 완료 — 사용자 실행)

---

## 감수 패스 — 생성 직후 자동 감수·수정본 (2026-09-06 추가)

**✅ 감수 패스(G-0xx 후보) 구현 완료** — `/ai/generate`에 `review` 옵션 추가. 초안 스트림이 정상 종료되면 **같은 SSE 스트림에서** 감수 1콜을 이어 실행한다(별도 요청 없음).

- **백엔드** (`routers/ai_panel.py`·`schemas.py`):
  - `GenerateReviewOptions` — endpoint_id(미지정 시 생성 엔드포인트 재사용)·model·reasoning_effort(미지정 시 감수 엔드포인트 설정값)·max_tokens
  - 감수 system 프롬프트(감수자 페르소나, `[감수]` 3~7개 지적 + `[수정본]` 수정 원고 전문 형식 강제)
  - `_split_review_stream()` 상태 기계 — 스트림을 `[수정본]` 마커 기준으로 review/refined 이벤트로 분리. 마커가 청크 경계에서 잘려도 말미 버퍼로 처리
  - SSE 이벤트: `review_start`(모델·엔드포인트·추론강도) / `review`(지적) / `refined`(수정본) / `review_error`. start 이벤트에 `review_enabled` 공개
  - 감수만 실패해도 초안은 이미 수신 완료 → `review_error` 통보 후 스트림 정상 종료. 사용량 기록 kind=`review` 추가
- **프론트** (AiPanel·aiStream·aiPanelStore):
  - "감수 패스" 섹션 — 자동 감수 체크박스 + 감수 추론 강도 선택(엔드포인트 설정값/low~xhigh)
  - 결과 영역 **초안 / 감수 의견 / 수정본 3탭** — 감수 시작 시 감수 탭, 수정본 시작 시 수정본 탭 자동 전환. 감수 의견 탭은 본문 반영(끼워넣기·선택 교체) 비활성, 복사만 허용(P1 원칙 유지). 헤더에 감수 모델 정보 표시
- **결함 수정(발견 즉시)**: 엔드포인트 **생성 시 `reasoning_effort`가 저장되지 않던 버그**(PATCH만 반영됨) — create 라우트에 추가
- **검증**: backend pytest **175 passed**(신규 4: 마커 청크 경계 분할·추론 강도 오버라이드·감수 실패 시 초안 보존·review 미사용 시 회귀 없음) / frontend `npm run build` 통과(TS 0 오류)

**다음 백로그 후보**: 감수 결과 채택 시 본문 반영 플로우 UX 개선, ONNX 임베딩 교체(semantic_score 인터페이스 — 모델 파일 다운로드 필요), 실기기 수동 QA 실행(가이드 준비 완료 — 사용자 실행)

## 집필 시작→완결 능력 감사 보강

- 현재 진단과 고도화 순서: [소설 집필·관리 감사 §8](docs/audits/소설집필_관리_감사.md#8-핵심-목표-재평가-시작부터-완결까지).
- 이번 확인은 소스 정적 검토와 기존 감사의 소스 해시 대조다. 새 테스트 실행·실모델 품질 평가·운영 데이터 변경·코드 수정은 하지 않았다.
- 다음 승인 단위와 검증 조건은 위 감사 문서를 따른다. 과거의 기능 완료 기록을 현재 정상 동작 또는 장편 품질의 보증으로 읽지 않는다.

## 원고 보존 1단계 — 구현·독립 검증 완료, 운영 미적용

- 승인 범위: 회차별 저장 큐·버전 확인·교체 전 복구본·화면/작품 일치. 서사 기억·기획·완결 지원은 후속 범위다.
- 로컬 브랜치 `feat/manuscript-preservation`, 최종 기능 수정 `42fad7c`. 병합·push·운영 DB 마이그레이션·서비스 교체는 하지 않았다.
- [설계](docs/superpowers/specs/2026-09-07-manuscript-preservation.md) · [구현 계획](docs/superpowers/plans/2026-09-07-manuscript-preservation.md) · [현재 결과와 이력](docs/audits/preservation-progress.md).
- 독립 검토: Standards PASS, 최종 Spec PASS(필수 미해결 지적 0건). 선택적 중복 코드 개선 제안은 후속 정리 대상으로 남겼다.
- 독립 검증: 백엔드222개, 모의 API 브라우저 보존17개, 실제 임시 백엔드 브라우저 시나리오1개, 프론트 빌드 통과. [최종 검증 기록](docs/audits/preservation-final-validation.md).
- 저장·응답 지연·회차/작품 전환·오래된 윤문 수락 차단·장면 합치기·복원을 검증했다. 복구 조회 실패/중복 선택은 모의 API 브라우저 검증이며, 실제 통합의 별도 실패 시나리오로 확대하지는 않았다.
- 미해결 복구본이 있으면 로컬/서버 원고를 선택하기 전까지 편집이 잠긴다. 서버 조회 실패 시 복구본을 보존하고 재시도를 안내한다.
- 운영 적용은 별도 승인 후 [백업·복제 DB 검증·동시 배포 절차](docs/runbooks/manuscript-preservation.md)를 따른다. 모든 본문 교체와 윤문 시작에 `expected_revision`이 필수이며, 원고 snapshot은 DB 백업을 대체하지 않는다.
- 이번 시험은 임시 DB·전용 포트·외부 처리 stub만 사용했다. 실제 원고·API 키 복원·실제 AI 품질 또는 장편 완결 품질을 검증한 결과가 아니다.

## AI 집필 맥락 정리 — 범위 승인, 설계·구현 계획 작성 중

- 사용자 요청: 원고 보존 다음 단계로 AI 집필 맥락 정리를 진행한다. 운영 배포 승인은 아니다.
- [진행 기록](docs/audits/ai-context-progress.md) · [맥락 전달 조사](docs/audits/ai-context-flow-research.md) · [집필/검사 지침 조사](docs/audits/ai-context-directives-research.md).
- 정적 조사만 완료했다. 공통 맥락 조립·현재 회차 연결·소속 검증·관계 전달·일반화/권말/최종화·이번 화 복선 회수 허용을 최소 범위로 제안한다.
- 제안 범위와 단계적 접근 설명 후 사용자가 “작업진행해”로 진행을 승인했다. `feat/ai-context-consistency`(base70ec67e)에서 상세 계약·구현 계획을 작성하고 작업별 검토를 거쳐 구현한다. 임시 DB backend222개와 native frontend build 기준선을 재확인했다. 운영 데이터·서비스 접근 및 운영 적용은 하지 않았다.
- 원고 보존 1단계는 완료 상태를 유지한다. 시점별 기억·영속 회차 목표·전체 완결 관리 기능은 후속 범위다.

- AI-context 최신 진행: 사양/계획 독립 사전 검토 PASS. T1(공통 맥락·소속 검증·문체/관계 전달) 구현 착수. 작업별 검토 후 T2–T4로 진행하며 원고 보존 완료 상태와 운영 미적용은 유지한다.

- AI-context 후속: T1 Spec/Quality PASS와 부모 backend247 PASS 후 `da49ff3` 커밋. T2 목적/복선 지침 구현 중이다. 프론트 T3와 실제 브라우저 통합 T4는 아직 미착수이며 배포하지 않았다.

- AI-context 최신: T2 Spec/Quality PASS와 부모 backend269 PASS 후 `46b1ec2` 커밋. T3 화면의 요청 소유권/공유 선택 연결 구현 중. 실제 HTTP/browser/provider 통합 T4 및 최종 전체 검토는 남아 있으며 운영 미적용이다.

- AI-context 최신: T3 UI fixture/독립재검토/build PASS 후 `03bad73` 커밋. T4 실제 격리 API·SQLite·가짜제공자·브라우저 통합 QA를 시작했다. 아직 전체 완료/운영 반영이 아니며 최종 브랜치 검토도 남아 있다.

## GPT 초안 + Gemini(agy) 교차 감수 — 2026-09-14

- 요청: "소설 생성시 gpt초안 gemini감수 로직" — 생성은 고정 GPT OAuth 브릿지 유지, 감수만 Antigravity CLI(`agy`, Gemini OAuth 계정)로 라우팅.
- 신설 `backend/app/services/agy_review.py`: `JIPPEEL_REVIEW_PROVIDER=agy`일 때 활성. `agy -p`를 `--output-format stream-json --sandbox`로 실행해 `agent_response`의 `text_delta`를 `llm.stream_chat`과 같은 델타 스트림으로 변환. `JIPPEEL_AGY_MODEL`(기본 `gemini-3.8-flash-high`)·`JIPPEEL_AGY_BIN`·`JIPPEEL_AGY_TIMEOUT_S` 지원. 백엔드가 Windows 프로세스이면 `wsl.exe` 경유 + 프롬프트 stdin 전달(argv 길이 제한 회피).
- 라우팅: `/ai/generate` 인라인 감수, `/ai/generate-parallel` 감수(재시도 루프 포함), 독립 `/ai/review` — 3곳 전부 `_review_backend`/`_review_stream` 디스패치. SSE `review_start`/`parallel_start`의 provider가 `antigravity-agy`로 보고되고 usage도 동일 endpoint로 기록. agy 경로에서는 요청의 `review.model`(GPT 모델명)을 무시하고 `JIPPEEL_AGY_MODEL`만 사용.
- `scripts/prod.sh`: 기동 시 `JIPPEEL_REVIEW_PROVIDER=agy`·`JIPPEEL_AGY_MODEL=gemini-3.8-flash-high` 기본 주입(환경변수로 해제 가능 — `JIPPEEL_REVIEW_PROVIDER=` 로 끄면 기존 브릿지 감수로 복귀).
- credential 경계 유지: 앱 코드·요청에 비밀 없음. Gemini credential은 `~/.gemini`(agy OAuth) 소유, GPT는 기존 브릿지 소유.
- 검증: 백엔드 **808P/1skip/violations 0** (신규 8 — 파서·라우팅·실패 시 초안 보존). subprocess 경로는 격리 가드상 테스트 불가 → WSL에서 실제 `agy` 수동 스모크로 스트리밍 확인(1회 호출).
- 실증 완료: WSLENV 미전달로 첫 배포에서 agy 미적용이 확인돼 `prod.sh`에 `WSLENV=JIPPEEL_REVIEW_PROVIDER:JIPPEEL_AGY_MODEL` 추가(9009392). 재기동 후 `/ai/review` 실호출로 `provider=antigravity-agy, model=gemini-3.8-flash-high`, `[감수]`+`[수정본]` 스트리밍·이력 저장(run 10) 확인.

## 병렬 planner ValidationError 복원력 — 2026-09-14

- 증상: "병렬 집필 실패: ValidationError" — SSE `parallel_error` 이벤트 내부 실패라 HTTP는 200. planner LLM이 스키마 밖 JSON(필수 필드 누락·scene 수/order 위반)을 반환한 것.
- 수정(`ai_panel.py`): `/ai/generate-parallel`에서 planner 응답이 `parse_parallel_plan` 검증에 실패하면 1회 재시도. 실패 원문·검증 에러는 `planner_debug.parse_error{detail,raw}`로 run manifest에 보존, `parallel_error` 이벤트에 예외 타입+메시지 포함. `/ai/plan`·assistant plan-next에도 동일 1회 재시도 적용(이 두 경로는 실패 원문을 `plan` 채널 출력으로 이미 보존).
- 승인된 계획(payload.approved_plan) 경로는 planner 미호출이라 무영향. 검증은 약화하지 않음.
- 테스트: `test_assistant_flow.py` 신규 2건 — 첫 실패 후 재시도 성공, 2회 연속 실패 시 run이 `provider_error`+planner_debug 보존. 전체 회귀 **810P/1skip/violations 0**.

## 병렬 감수 수정본 활성화 — 2026-09-14 (후속)

- 사용자 지적: 병렬 집필에서 초안·감수 의견 후 수정본이 안 나옴 — `PARALLEL_REVIEW_SYSTEM_PROMPT`가 의도적으로 "[수정본] 출력 금지"였던 설계상 제한.
- 수정: 병렬 감수도 단일 생성과 동일하게 `[감수]` 지적 + `[수정본]` 전체 수정 원고를 출력. 스트림은 기존 `_split_review_stream()`로 분리해 `review`/`refined` SSE 이벤트·저장 채널(review+refined)로 흘린다. 프론트는 refined 탭/핸들러를 이미 지원해 프론트 변경 없음.
- 테스트: `test_parallel_review_emits_refined_after_marker` 신규 — 마커 포함 감수가 refined 이벤트와 저장 채널로 분리됨을 검증. 전체 회귀 **811P/1skip**.

## 레퍼런스 스타일 분석 — 2026-09-14

- 사용자 요청: 인기작 구조·문체·캐릭터 구조 수집 학습 → 페르소나 개선. 외부 인기작 크롤링은 저작권·플랫폼 약관상 불가 — 작가가 직접 붙여넣은 레퍼런스 텍스트만 분석하는 방식으로 구현.
- 신설 `backend/app/services/style_analysis.py`: 순수 Python 결정적 지표(문장 길이 평균/중앙/p90·단문-장문 비율·대화 단락 비율·종결/연결 어미 비율·시점 힌트·단락당 문장 수·상위 어미) + LLM이 지표·원문 샘플을 해석해 문체 프로파일 초안(지시문 목록) 합성.
- `POST /projects/{pid}/style-analysis` (projects.py): 텍스트(200~20000자) → `{metrics, profile_draft}` 반환만 — 저장 없음. 작가가 검토·수정 후 PATCH style_profile로 적용.
- 프론트 PlanPage: 문체 프로파일 아래 "레퍼런스 스타일 분석" 섹션 — 텍스트 입력 → 지표 배지 + 초안 편집 → "문체 프로파일에 적용" → 이후 생성 컨텍스트에 주입(기존 style_profile 경로 그대로).
- 검증: `test_style_analysis.py` 신규 5건(지표·메시지 형태·엔드포인트·미저장·길이 검증), 전체 회귀 **816P/1skip**, 프론트 빌드 PASS.

## 캐릭터 생성 엔진 고도화 — 권별 조연 확장 — 2026-09-14

- 사용자 지적: 10권/300화 장편인데 캐릭터가 4명뿐이고 이름도 유형 라벨("차가운 검객")이었다. `d8c5793`에서 실명 강제+5명 미만 재시도를 넣었으나, 장편에선 핵심 캐스트만으론 부족.
- 확장(`bootstrap.py`): `volume_count >= 3`이면 캐릭터 호출 뒤 `_supporting_cast_messages`로 권별 조연·단역 생성 호출을 추가(권당 2~3명 요청). 각 조연은 `first_volume`(첫 등장 권)을 들고, 핵심 캐스트와 이름 중복 불가. 호출 실패 시 핵심 캐스트만으로 진행.
- `_coerce_supporting_cast`: 이름 중복 제거, `first_volume` int 변환·범위 밖은 1권으로 보정, role은 조연/단역으로 제한, 권당 최대 3명.
- 관계망: 조연 이름을 합쳐 콜 4(관계+세계관) 프롬프트에 전달 — 조연도 관계망에 연결될 수 있음. 관계 저장 검증도 합성 캐스트 기준.
- `OutlineCharacter.first_volume` 필드 추가, `_character_card_json`의 `data.first_volume`에 보존 — 캐릭터 카드에서 첫 등장 권 확인 가능(UI 노출은 후속 과제).
- 테스트 신규 3건: 권별 조연 생성+중복 제거+first_volume 보정, 2권 이하는 호출 생략(4회 유지), 조연 호출 실패 시 핵심 캐스트로 완료. `volume_count=4` 기존 테스트는 큐 5개·호출 수 5로 갱신.
- 전체 회귀 **819P/1skip/violations 0**. 백엔드 재기동 적용.
