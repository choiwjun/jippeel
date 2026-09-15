# 전체 작업 현황 — 완료·잔여·승인 대기

최종 대조: **2026-09-14(KST)**. 기존 링크 유지를 위해 파일명은 변경하지 않았다.

**현재 작업 상태의 단일 기준은 이 문서다.** `HANDOFF.md`는 진입점과 작업 이력,
`docs/DOCUMENT_STATUS.md`는 문서 인덱스다. 아래 보존된 9월 8일 원문과 과거 문서의
“다음 작업/미완료”는 현재 할 일 목록이 아니다.

## 1. 현재 결론과 판정 기준

**2026-09-14 전 엔진 감사 + 고도화:** "모든 엔진 조사분석" 지시로 백엔드 전 서비스·라우터를 감사했다. 수정 완료 8건 — ① 단일 생성도 `previous_chapter`·`auto_characters`·`include_memory`·`style_profile` 자동 주입(계획 경로와 대칭) ② `auto_characters` 관련성 선정(`first_volume` 미래 권 제외·이름/별칭 언급 점수) ③ 요약 잡 API(`summary-jobs` plan/run/retry) + MemoryPage 실행 UI — 결과는 draft만·승인 게이트 유지 ④ 규칙 패널 "이력 분석으로 제안 생성" 버튼 ⑤ 병렬 worker 계약 위반 1회 재집필(재위반 시 run 실패 유지) ⑥ canon 컨텍스트 캡(캐릭터 20·로어 30, 주연 우선+언급 순) ⑦ 자동 백업 기본 활성화(prod.sh `INTERVAL_MIN=30`·`KEEP=10`) ⑧ `canon.last_prompt_chars` 전역 제거·`select_context_memory` N+1 배치화·캐릭터 목록 `first_volume` 배지. 검증: backend **829P/1skip/violations 0**, frontend tsc/build 통과, 신규 테스트 8건(관련성 선정·별칭·canon 캡·요약 잡 API 5종·재집필 2종).

**감사 잔여(우선순위 순):** 캐릭터 라이프사이클 first-class 필드(퇴장/사망·권별 역할) → 권별 독립 조연 호출(현 단일 호출) → canon 결정적 사전검사(이름/시간/장소 모순 규칙으로 LLM 호출 절감) → 한국어 임베딩 로어 매칭(현 2-gram fallback) → 다중 프로세스 잡 락 → 인증/인가(LAN 공개 전 필수). 실제 provider·credential·실기기·운영 DB는 기존 G gate 유지.

**2026-09-14 다른 PC 접근 최소 범위:** A PC에서 `Jippeel실행.bat`을 실행하면
운영 서버가 LAN에 바인딩되고, 실행 창에 Windows 사설 IPv4별 B PC 접속 주소를
출력한다. `scripts/dev.sh`와 Vite 프록시도 WSL/Windows 혼합 환경에서 연결되도록
보완했다. B PC는 같은 네트워크에서 `http://<A-PC-IP>:8000`을 열어 A PC와 같은
SQLite DB를 본다. [사용법·방화벽·보안 한계](../runbooks/cross-pc-access.md)를
추가했으며, 로그인 없는 현재 앱의 인터넷 공개·클라우드 동기화·실시간 공동편집은
구현하지 않았다.

**2026-09-13 별도 Git 승인:** 사용자가 “핸드오프에 모두 남기고 커밋 푸시해”를 요청했다. [통합 인계·게시 경계](2026-09-13-commit-handoff.md)에 완료/증거/D01 제안·미선택/다음 순서를 기록한다. 초기 로컬·원격 main은 c1a92c4로 확인했으며, 아래 수용 당시 Git 미실행 기록을 이번 승인과 구분한다. D01 구현·운영/외부 실행 승인은 추가되지 않았다.

**2026-09-13 D01 수용:** 사용자가 전체 순차 진행과 추천안 자율 결정을 지시했다. Q1~Q7 추천 기본값(회차 목표만, option B 현재값+append-only 이력+최소 복원, purpose 함께 저장, 빈 저장≠삭제, 회차 삭제 cascade, 명시적 불러오기만 생성 반영, 명시 저장만)으로 [좁은 사양](../superpowers/plans/2026-09-13-d01-detailed-spec.md)을 확정하고 구현·격리 검증·독립 검토 2건 PASS_WITH_NOTES·지적 수정·재검증을 완료했다. [최종 수용](../audits/d01-goal-contract-2026-09-13/acceptance.md). backend focused 47P·전체 520P/skip1, frontend fixture 8+15+31P·tripwire 0, tsc exit0. 변경은 `choiwjun/d01-contract-analysis` worktree의 uncommitted 상태 — 게시는 별도 승인. 운영 DB·실제 provider·credential·실기기는 G gate 유지.

**2026-09-13 D03-1 수용:** D03의 첫 얇은 단위로 회차 집필 흐름 상태 기계를 수용했다. `Chapter.status`(원고 성숙도, plus-status 의존)와 독립된 `flow_stage`(planning→writing→revising→confirmed, revising→writing, confirmed→revising)와 append-only 전이 이벤트를 추가했다. `confirmed`는 집필 확정이며 연재/발행 완결이 아니다. CAS 409·불법 전이 422·BUSY 409, 이벤트는 전이 시점의 `goal_version`(nullable)·원고 revision을 앵커로 기록, 전이는 원고/snapshot/memo/목표/status 불변. migration `3d4e5f6a7b81`은 status·본문 유무로 backfill하고 downgrade는 전부 제거. [좁은 사양](../superpowers/plans/2026-09-13-d03-1-flow-stage-spec.md) · [수용](../audits/d03-1-flow-stage-2026-09-13/acceptance.md). backend focused 69P·전체 543P/skip1·violations 0, frontend fixture 6+8+15+31P·tripwire 0, tsc exit0. 독립 검토 2건(백엔드 PASS_WITH_NOTES·프론트 FAIL→지적 수정·재검증) 후 수용. 변경은 동일 worktree의 uncommitted 상태 — 게시는 별도 승인. D03 후속 단위(장면 재개·완결/연재 분리·이관)는 잔여.

**2026-09-13 D03-2 수용:** 회차 재개 계약(`GET /chapters/{cid}/resume`)을 수용했다. 순수 파생 읽기 — 마지막 전이 앵커 대비 목표/원고 드리프트, 미해결 감수(`RefineRun.accepted=false`) 수, sort_order 순 첫 빈 장면을 반환한다. 프론트는 에디터 헤더에 드리프트·감수·다음 장면 배지를 표시하고 모든 관련 mutation(전이·목표·원고·장면·윤문)에서 resume 캐시를 무효화한다. [좁은 사양](../superpowers/plans/2026-09-13-d03-2-resume-spec.md) · [수용](../audits/d03-2-resume-2026-09-13/acceptance.md). backend focused 74P·전체 558P/skip1·violations 0, frontend fixture 10+26+8+15P·tripwire 0, tsc exit0. 독립 검토 2건 PASS_WITH_NOTES — 검토에서 발견된 선존 회귀(preservation fixture의 `/flow`·`/resume`·`/goal` 미모킹, D01/D03-1 잠재 파손)를 mock 추가로 복구했다. uncommitted 유지, 게시 별도 승인. 잔여 D03 단위: 근거 연결·완결/연재 분리·이관.

**2026-09-13 D03-3 수용:** §6.3 "집필 확정(원문 상태)과 연재 완결(작품 상태)은 다른 수명주기"의 작품 측 대응물로 `projects.serial_state`(ongoing|hiatus|completed) + `serial_completed_at`을 수용했다. PATCH /projects/{pid}의 명시적 전이 — 회차 confirmed와 무연동, 양방향 불변을 테스트로 단정. 완결 진입·재진입마다 시각 갱신, 이탈 시 NULL, serial_state 없는 부분 PATCH는 보존, 명시적 null·사전 외 값 422. migration `4e5f6a7b8c92`는 ongoing/NULL backfill + `ck_project_serial_state` + downgrade 보존. 홈 카드에 select+휴재/완결 배지+완결 시각. [좁은 사양](../superpowers/plans/2026-09-13-d03-3-serial-state-spec.md) · [수용](../audits/d03-3-serial-state-2026-09-13/acceptance.md). backend focused 17P·전체 565P/skip1·violations 0, frontend fixture 6+10+8+26+15+31P·tripwire 0, tsc exit0. 독립 검토 2건 PASS_WITH_NOTES — 지적 14건 반영·1건 수용. uncommitted 유지, 게시 별도 승인. 잔여 D03 단위: 근거 연결·결말 영향·이관·완결 산출물.

**2026-09-13 D03-4 수용:** §6.2 근거 연결 — 저장된 회차 목표 항목(core_events·character_choices·cost) ↔ 원문 발췌(≤500자)의 수동 링크를 수용했다. 자동 판정·자동 발췌 없음. `chapter_goal_evidence_links`(migration `5f6a7b8c9d03`, head)는 생성 시점 `goal_version`·`goal_item_text`·`excerpt`를 앵커로 보존하고, GET은 파생 상태만 계산(manuscript_status intact|broken, goal_status unchanged|drifted|goal_deleted, current_goal_version). POST는 원문 존재·목표 항목 존재 검증 + BEGIN IMMEDIATE writer lock, BUSY→409. DELETE는 명시적·타 회차 소속 404, 회차 삭제 시 FK cascade. 프론트는 브리프 섹션 내 근거 연결 그룹(role=group)에서 저장본 항목 선택 + CodeMirror 선택 발췌 연결(POST 전 draft flush), 파생 배지·명시 삭제, 목표/원고/링크 모든 변경 경로에서 캐시 무효화. [좁은 사양](../superpowers/plans/2026-09-13-d03-4-evidence-links-spec.md) · [수용](../audits/d03-4-evidence-links-2026-09-13/acceptance.md). backend focused 22P·전체 576P/skip1·violations 0, frontend fixture 8+8+10+26+15+31+6P·tripwire 0, tsc exit0. 독립 검토 2건 PASS_WITH_NOTES — 지적 11건 중 5건 수정·6건 수용, 테스트 갭 보강. uncommitted 유지, 게시 별도 승인. 잔여 D03 단위: 결말 변경 영향·해결/의도적 미해결/외전 이관·완결 산출물.

**2026-09-13 D03-5 수용:** §6.2 이관 구분 — 닫힌 복선(status=회수·보류)의 처분 라벨 `foreshadows.disposition`(resolved/intentional_unresolved/side_story/NULL)을 수용했다. 자동 추론 없음·작가 명시 지정만. 불변조건 status='설치' ⇒ disposition IS NULL은 POST·PATCH 적용 결과로 422 강제, 해제는 명시적 null만. GET disposition 필터(status_filter와 AND), migration `6a7b8c9d0e14`(head)는 populated 보존·downgrade 제거. 프론트는 행 배지 + per-row 처분 select(설치 시 disabled), 설치 복귀 시 단일 PATCH로 명시 해제 포함. [좁은 사양](../superpowers/plans/2026-09-13-d03-5-foreshadow-disposition-spec.md) · [수용](../audits/d03-5-foreshadow-disposition-2026-09-13/acceptance.md). backend focused 36P·전체 587P/skip1·violations 0, frontend fixture 7+8+10+26+15+31+6+8P·tripwire 0, tsc exit0. 독립 검토 2건 PASS_WITH_NOTES — 지적 13건 중 5건 수정·8건 수용. 범위 밖 선존 결함 발견: `create_foreshadow`가 `audience_knows`를 받지만 저장하지 않음(G-045) — 별도 슬라이스 후보로 기록. uncommitted 유지, 게시 별도 승인. 잔여 D03 단위: 결말 변경 영향·완결본 관리.

**2026-09-13 D03-6 수용:** §6.2 완결 분리 잔여분 + 감사 §8.2 완결 점검표·완결본 스냅샷을 수용했다. `project_final_editions`(migration `7b8c9d0e1f25`, head)는 명시적 POST의 불변 스냅샷 — 전 회차 조립 원고(content_md, sort_order+id 순)·매니페스트·동결 점검표·캡처 시점 serial_state. UPDATE 경로 없음·삭제만 명시적. `GET /projects/{pid}/completion-checklist`는 파생 읽기 — 회차 단계별 집계, 복선 open 목록+처분 4버킷, 미수용 윤문, 파손 근거 링크, ending_intent 없는 최종화 목표. 자동 완결 판정 없음. 프론트 `/projects/:pid/completion` 페이지 + 홈 카드 링크. [좁은 사양](../superpowers/plans/2026-09-13-d03-6-final-edition-spec.md) · [수용](../audits/d03-6-final-edition-2026-09-13/acceptance.md). backend focused 31P·전체 605P/skip1·violations 0, frontend fixture 6+8+10+26+15+31+6+8+7P·tripwire 0, tsc exit0. 독립 검토 2건 PASS_WITH_NOTES — 지적 19건 중 9건 수정·10건 수용. uncommitted 유지, 게시 별도 승인. 잔여 D03 단위: 결말 변경 영향.

**2026-09-13 D03-7 수용:** §8.5 결말 변경 영향 — 작품 수준 `projects.ending_intent`·`ending_locked`·`ending_updated_at`(migration `8c9d0e1f2636`, head)을 수용했다. PATCH는 명시 지우기·`""`→null 정규화·실제 변경 시에만 시각 갱신·잠긴 결말은 동일 요청의 `ending_locked:false` 필요·명시적 `ending_locked:null`은 422. `GET /projects/{pid}/ending-impact`는 파생 읽기 — 미해결 복선·잠재적 오래된 목표 회차·최종화 목표의 결말 보유 여부. 자동 전파·자동 완결 판정 없음. PlanPage 결말 후보 섹션(저장·잠금 토글·영향 3목록). [좁은 사양](../superpowers/plans/2026-09-13-d03-7-ending-impact-spec.md) · [수용](../audits/d03-7-ending-impact-2026-09-13/acceptance.md). backend focused 33P·전체 618P/skip1·violations 0, frontend fixture 6P·tripwire 0(기존 9종 전부 green), tsc exit0. 독립 검토 2건 PASS_WITH_NOTES — 지적 9건 반영·재검증. **D03 전 단위 수용 완료** — 다음은 D04 fake worker. uncommitted 유지, 게시 별도 승인.

**2026-09-13 D04-1 수용:** D04 첫 얇은 단위 — `summary_jobs` manifest 영속(migration `9d0e1f2a3747`, head, idempotency_key UNIQUE) + fake worker 생명주기를 수용했다. 설계 §5 선택지 1(별도 테이블+unique) 채택. 서비스 계층만 — HTTP·프론트·자동 호출 없음, provider는 주입 fake callable만. 상태 기계 planned→running→draft_saved|skipped_empty|stale_source|provider_error|rejected|duplicate_skipped, running 복구(attempt_count 보존), provider_error만 명시 재시도, 호출 전후 source 재검증, 결과는 MemoryEntry draft append-only(provenance 7키). chapter 삭제 시 job SET NULL 보존. [좁은 사양](../superpowers/plans/2026-09-13-d04-1-summary-worker-spec.md) · [수용](../audits/d04-1-summary-worker-2026-09-13/acceptance.md). backend focused 41P·전체 641P/skip1·violations 0. 독립 검토 2건(backend·contract/design) PASS_WITH_NOTES — MED 5건·테스트 갭 반영·재검증. uncommitted 유지. 잔여 D04: 실제 provider 어댑터·비용 cap·평가 manifest·승인 UI·운영 절차 — §9 체크리스트·G01/G02/G03 승인 필요. 다음은 V01/V02/V04 검증 보강.

**2026-09-13 V02 수용:** 복원 실패 시나리오 보강을 수용했다. `backend/app/services/restore_verify.py` — stdlib만·합성 TEMP 경계의 `create_backup`+`verify_backup_dir`(읽기 전용, `query_only`). 9개 실패 코드 계약(manifest 결손·무효/파일 누락/checksum/비-SQLite/schema head 불일치/integrity/FK 위반/대상 쓰기 실패), 다중 실패 수집, 잘못된 manifest·경로 탈출 이름은 `MANIFEST_INVALID`, 비-jippeel 원본·쓰기 실패 코드 분리. [사양](../superpowers/plans/2026-09-13-v02-restore-failure-injection.md) · [수용](../audits/v02-restore-verify-2026-09-13/acceptance.md). backend focused 15P·전체 656P/skip1·violations 0. 독립 검토 PASS_WITH_NOTES — MED 5·LOW 3 수정, NOTE 4 수용. 실제 운영 DB·복원 실행·wrong-key는 G01/G03 범위로 유지. uncommitted 유지. 잔여: V01(실행 중)·V04.

**2026-09-13 V04 수용(검증 도구 범위):** 외부 im-not-ai metrics 버전 동기화의 검증 절차를 코드로 고정했다. `backend/app/services/metrics_version.py` — 대상 파일을 실행하지 않고 AST로 `compute_all_v2(text, genre)` 시그니처(genre 키워드 바인딩 가능·필수 위치 인자 ≤2·비-async)와 `CHANGE_RATE_WARN/ABORT` 상수를 `humanize.WARN_RATIO/BLOCK_RATIO` 라이브 값과 비교한다. 파일 부재·파싱 불가·비-리터럴 상수는 예외 없이 보고(fail-closed). [사양](../superpowers/plans/2026-09-13-v04-external-metrics-version-spec.md) · [수용](../audits/v04-metrics-version-2026-09-13/acceptance.md). backend focused 20P·전체 676P/skip1·violations 0. 독립 검토 PASS_WITH_NOTES — MED 2건 수정(1건 부분 반증 후 방어 확장). 실물 metrics_v2.py는 호스트 미설치 확인 — 실제 상수 비교는 스킬 설치 승인 후 `verify_metrics_module(실물경로)` 1회 실행으로 완료하며 이번 수용으로 주장하지 않음. uncommitted 유지. 잔여: V01(검토 진행).

**2026-09-13 V01 수용:** 프론트 source-mapped coverage 계측을 수용했다. `PW_COVERAGE=1` opt-in만 — 미설정 시 순수 passthrough. `e2e/coverage-test.ts` V8 수집 + 기존 scoped 래퍼(memory·quality) 공유, `coverage-report.mjs`가 소스맵 경유 **실제 fs 경로 키 union 병합**(검토 BLOCKER: 포트별 분리 병합을 수정), `.ts/.tsx/.css` 필터·정렬·per-file 예외 격리, html+text+json 산출. `run-coverage.sh` 11개 fixture config 순차·실패 전파. [사양](../superpowers/plans/2026-09-13-v01-frontend-coverage-spec.md) · [수용](../audits/v01-frontend-coverage-2026-09-13/acceptance.md). 11 스위트 **128P·tripwire 0**·57 소스 파일 측정값 lines 83.27%·branches 83.28%·functions 60.92% — 측정 기록이며 임계 주장 아님. 독립 검토 2건(①PASS_WITH_NOTES ②FAIL→수정·재검증). uncommitted 유지. **V01/V02/V04 검증 보강 전부 완료** — 다음은 최종 정리·G/U/O 잔여 보고.

**2026-09-13 G-045 수용:** D03-5 검토에서 발견된 선존 결함 — `POST /projects/{pid}/foreshadows`가 `audience_knows`를 받았지만 `Foreshadow()` 생성자에 전달하지 않아 항상 False로 저장(프론트 생성 폼 체크박스가 이미 전송 중 — 실제 데이터 유실). 생성자 인자 1행 추가로 수정. [수용](../audits/g045-audience-knows-2026-09-13/acceptance.md). RED 재현 후 수정, focused 24P·전체 677P/skip1·violations 0, fixture POST 목+UI 왕복 테스트 추가 8/8·tsc exit0. 독립 검토 PASS — 다른 쓰기 경로·필드 유실 없음 확인. uncommitted 유지.

**2026-09-13 게이트 실행 — G01 수용·G03/G04 부분:** 사용자 전체 위임(“나대신 승인하고 남은거 다 작업해”)으로 로컬 실행 가능 게이트를 실행했다. **G01 완료** — 실 운영 DB(`C:\Users\wj941\Documents\jippeel\backend\jippeel.db`, create_all 생성·alembic_version 없음, 스키마 정합 `f9a1b2c3d4e5`)를 일관 백업(sha256 manifest)→복원 검증→리허설→실 적용으로 `9d0e1f2a3747`(head)까지 10개 migration 적용, 14개 테이블 row counts 전부 보존·`assert_manuscript_schema_current` 통과. **G03 부분** — 두 인스턴스 키 파일 상이 확인·저장 암호문 실데이터 부재 기록·실제 키 기반 wrong-key 거부/키 유실 감지/복구 temp 검증. **G04 부분** — Windows 네이티브 전체 스위트 714P/violations 0/warnings 0, alembic 10개 네이티브 완주; 수동 실기기 영역(브라우저·NVDA·성능표)은 잔여. [수용](../audits/g01-production-migration-2026-09-13/acceptance.md).

**2026-09-13 U/O/V03 실행:** **U01** card_json 편집 UI(merge-patch 재사용, fixture 5/5)·**U02** `GET /lore/{lid}/referencing-chapters`+상세 접이식 목록(backend 17P·fixture 4/4)·**U03** 프리셋은 선존 충족으로 종결(중복층 추가하지 않음)·**U04** `uiScale` 3단 영속+CodeMirror typography compartment(fontFamily/lineHeight 선존 갭 실제 적용, fixture 3/3). **O01** ST 카드 PNG import/export+novelWriter ZIP import(16P)·**O02** `JIPPEEL_AUTOBACKUP_INTERVAL_MIN` opt-in 자동 백업+프루닝(11P)·**O03** `GET /projects/{pid}/writing-activity`(5P). **O05** ResourceWarning 19건 근본 수정 — `inspect(bind)` transient Inspector 연결 유지를 `with bind.connect()` 스코프로 교체, 테스트 측 엔진/제너레이터 폐기 정리, 진단 probe 전부 제거 → **warnings 0**. **V03** `scripts/sqlite_multiprocess_check.py` 다중 프로세스 동시 쓰기 2회 PASS(무손실·integrity ok·WAL). Linux 전체 **714P/1skip/70subtests/violations 0/warnings 0**. [수용](../audits/uo-options-v03-2026-09-13/acceptance.md).

**2026-09-13 심야 후속 실행(“남은작업모두진행해”):** **G03** 실 `get_cipher()` 폴백 키 왕복·실 Windows 키 cross-decrypt 거부 확인(`g03-real-crypto-path.txt`). **G04** Windows 네이티브 uvicorn 실기동 프로브 — 실 DB 복사본 기동 3.79s·54,300자 저장 43ms·CAS 409·snapshot/resume 정상(`g04-windows-realdevice-probe.txt`). **O06** 플랫폼 규정 재확인 — `규정추적_2026-09-13.md`(변화 없음, 공모전 AI 금지 유지). **D04** 실제 provider 어댑터 `summary_provider.py` 구현·7P — 실 호출은 G02 게이트 유지(`openai-oauth` 미설치, 대화형 로그인 필요). 전체 **721P/1skip/warnings 0**. [수용](../audits/uo-options-v03-2026-09-13/acceptance.md).

**2026-09-14 후속 실행(잔여 목록 전달):** **V04 실물 대조 완료** — 실제 `metrics_v2.py`가 Windows 측 `C:\Users\wj941\.agents\im-not-ai\...\metrics_v2.py`에 설치돼 있음을 확인, `verify_metrics_module` 실물 실행으로 계약 전 항목 일치(`ok:true`, [증거](../audits/v04-metrics-version-2026-09-13/real-file-verification.txt)). **G04 실제 브라우저 검증** — mock 없이 실제 dist 빌드 + 실제 uvicorn + 실 DB 복사본 + Playwright Chromium으로 10/10 PASS: 랜딩·API 왕복(실 데이터)·키보드 Tab·에디터 마운트·uiScale 실 DOM 적용(16→20.8px)·**5만 자 실제 입력→자동저장 왕복(+50,027자 실증)**·/settings 렌더·콘솔 오류 0 ([수용](../audits/g04-real-browser-2026-09-14/acceptance.md)). **실제 결함 발견·수정** — SPA fallback 부재: 운영 모드에서 `/settings` 등 클라이언트 라우트 직접 접근·새로고침이 JSON 404였음 → `_SPAStaticFiles` 추가, `/api`·`/health` 404는 JSON 유지(`test_spa_fallback.py` 5P). **실행 스크립트 정정** — `Jippeel실행.bat`·`prod.sh`·`dev.sh`의 폐기 OneDrive 경로→실 경로, Linux `bin/python`→실제 Windows venv `Scripts/python.exe`로 수정(커밋 `701ea52`, Documents checkout은 `git pull`로 반영·frontend dist 리빌드 완료). 전체 **726P/1skip/violations 0**. 잔여 수동 영역: NVDA 실측·G02 OAuth 로그인·G03 계정 시연.

**2026-09-14 병렬 Windows 세션(ZCode) 기록:** Documents checkout에서 병행 세션이 같은 게이트를 독립 실행 — 최소 provider smoke(SSE 완결·error 0)·bridge stop/restart 복구·**NVDA 2026.1.1 설치**·Home/Editor/Settings/AI 패널 UIA 접근성 트리 수동 확인 PASS_WITH_NOTES. 실제 발화·키보드 순환은 그 세션 도구로 포착 불가로 기록했으나 본 세션의 `nvda-speech-evidence.txt`가 그 갭을 메웠다. 상세 [실행 기록](../audits/g02-g03-g04-user-actions-2026-09-14/acceptance.md).

**2026-09-14 최종 게이트 실행(“이거 너가 진행해”):** **G02 실제 provider 파일럿 실행 완료** — 사용자 Codex의 실제 `openai-oauth` 브릿지를 기동(ChatGPT OAuth, 모델 `gpt-5.6-luna`, xhigh)하고 실제 앱 엔드포인트(실 uvicorn :18701·실 DB 복사본) 경유로 6-case 실 호출 전부 완결. raw SSE 2,803건·ai_usage 행·latency 기록, DB snapshot 해시 before==after, OAuth 구독 경로라 marginal $0(USD 20 cap 대비). 게이트 플래그 4건 분석 결과 실 제품 결함 없음 — `[감수]` 2건은 review 정규 헤더를 스캔한 게이트 오탐, `서도윤` 1건은 gold cue 과엄격(본문에 `도윤` 10회), `parallel_error` 1건은 브릿지 일시 끊김(draft 3,262자는 완성). **1차 평가(agent-first-pass, 보조 의견) 완료** — hard gate 6/6 PASS(실 본문 대조), rubric 축별 median 5/5/4/5/5, blind-04 병렬 스티칭 결함은 review 레그가 자체 식별(파이프라인 감수 표면 실증), blind-06은 실제 원고 오류 정확 포착+수정본 적용 검증 [1차 평가](../audits/g02-pilot-2026-09-14/acceptance-report.md). 잔여는 지정 평가자 2인의 blind 채점·작가 accept뿐이며 평가 대상·gold 해시는 동결됨 [수용](../audits/g02-pilot-2026-09-14/acceptance.md). **G03 OAuth 로그아웃·복구 시연 완료** — `openai-oauth stop`→포트 종료, `$CODEX_HOME/auth.json`+`~/.codex/auth.json` 제거→브릿지 기동 거부(무인증 상태에서 provider 호출 불가), 백업 복원→실 호출 "복구 완료" 성공. 임시 credential 사본 시연 후 전량 파기 [수용](../audits/g03-oauth-logout-2026-09-14/acceptance.md). **G04 NVDA 실증** — 실제 NVDA 프로세스(DEBUG 로깅)가 실제 운영 앱(Windows uvicorn :8000·실 DB·Chrome)을 탐색하며 실제 음성 발화 기록 — 랜드마크·제목 수준·링크·버튼 롤이 1:1로 발화되고 Tab 포커스 순환마다 발화(`nvda-speech-evidence.txt`). 2차 전용 창 패스로 무중단 순환(Chrome UI→문서→배너→보조 랜드마크→컨트롤) 확보 + 연재 상태 콤보상자의 레이블·롤·값·상태·설명 완전 발화 확인 — 지정 장치 대화형 사인오프만 잔여.

**2026-09-14 대량 슬라이스 — 계획→승인→집필 + E1~E7 + 계층 기억:** 사용자 전체 위임("이 모든걸 다 작업했으면좋겠어")으로 핵심 기능 개발을 완료했다. **계획-우선 집필** — `POST /ai/plan`(계획만·channel=plan 보존), `approved_plan` 주입 시 planner 스킵(단일·병렬·assistant 3 surface 공통), `assistant/plan-next`+`generate-next`(draft-only·`applied:false`), `POST /generation-outputs/{id}/apply`가 필수 `expected_revision` CAS로만 원고 승격. 프론트는 AI 패널 주 버튼이 [🗺 계획 만들기](자동 전체 분석: 설정·인물·로어·복선·이전 회차·문체·회차 목표 + `auto_characters`·관계 자동 주입) → 계획 카드 → [수락하고 집필]. BootstrapDialog도 계획→초안→명시 적용. **E3~E7** — 결정론 diff 분석·`improvement_rules` 생명주기·proposed-only 제안 job·approved 규칙 주입·규칙/이력/폐기 UI. **D04** — 실제 OAuth 브릿지 smoke 완료([수용](../audits/d04-2-summary-smoke-2026-09-14/acceptance.md)·[runbook](../runbooks/summary-backfill-operations.md)). **D02 1차** — 아크 요약 슬라이스(migration `d1e2f3a4b5c6`, [설계](../specs/2026-09-14-hierarchical-memory-500ep.md)). 사용자 검토 보완으로 일반 패널 plan-first 기본화·인물 자동 주입·apply CAS 필수화 반영(`0c44677`). orphan `test_assistant_flow.py`를 draft-only 계약으로 이식. 전체 **792P/1skip/violations 0**·프론트 tsc/build 통과. 커밋 `21920ed`·`0c44677` origin/main 반영, 운영 DB head `d1e2f3a4b5c6`. **잔여는 개발이 아니라 사용자 수용** — blind-01~06 accept/reject·실기동 확인·선택적 인간 평가 2인. 장기 로드맵: D02 권 기억·커버리지 선택·인지 상태 도메인.

**후속 순차 진행 승인:** 사용자가 M01~M05 → B03 → 회차 목표/완결·재개/summary worker → V01/V02/V04 → 실제 자원 수용의 순서를 승인했다. M01~M05와 B03은 회귀·독립 검토·부모 수용을 완료했으며 다음은 D01/D03/D04 상세 계약·기획이다. [실행·승인 기록](../superpowers/plans/2026-09-12-remaining-sequence.md)을 따르며, 실제 자원은 대상·예산·계정·백업·장치와 실행 허가가 갖춰지기 전 접근하지 않는다.

- 기본 집필·관리 기능, 원고 보존, 공통 AI 맥락, 관리 무결성 보정, 수동 장편 기억 기반과
  **승인된 기억 P1 네 건은 완료**다. 같은 범위를 처음부터 다시 구현하지 않는다.
- 남은 일은 **실제 결함/후보, 미구현 제품 범위, 검증만 남은 범위, 운영·외부 승인 대기,
  선택적 확장**으로 분리한다. 프로젝트 전체나 장편 로드맵 전체를 완료로 표시하지 않는다.
- **B01/B02 실패 계약과 B04 테스트 격리 보강은 최종 수용 완료**다. 새 격리 실행 **419 passed / 외부 비교 1 skipped / 70 subtests / 19 warnings**, 독립 재검토 2건 PASS, 검토 후 소스·보존 대상 hash 불변을 확인했다.
  [최종 수용·원시 근거](../audits/failure-contracts-2026-09-12/b04-review-fixes.md)를 프로젝트에 보존했다. 실행 중인 worker/reviewer는 없다.
  최초 401개 실행의 [격리·보존 사고](../audits/failure-contracts-2026-09-12/validation-isolation-incident.md)는 소급 PASS로 바꾸지 않는다. 사용자 승인에 따라 재생성 `.coverage` a8db…를 유지했고, 옛 d6ad… 원본 미복구·당시 credential 부수 효과 미확정은 그대로 남긴다.
  당시 실제 provider/운영 DB/새 migration 파일/배포/commit/stage/push는 범위 밖이었다. Git만 위의 9월 13일 새 승인으로 분리했다.
- `main`, HEAD `c1a92c45fe8c16b4ee140a31fe97683ab588ed07`은 B03 수용과 D01 조사까지 불변이었다.
  9월 13일 게시 사전점검에서 원격 main도 같은 SHA임을 확인했다. 누적 프로젝트 변경은 명시 목록으로 게시하고 미추적 로컬 자료는 별도 보존한다.
- **완료**는 적힌 구현·검증 범위의 완료이며 운영 적용·문학 품질 보증이 아니다.
  **후보**는 정적 근거가 있지만 이번에 새 실행 재현하지 않은 항목이다.
  **승인 대기**는 지금 실행해도 된다는 뜻이 아니다.
- **2026-09-12 사용자 정정:** prime-agent는 사용하지 않는 도구다. `AGENTS.md`의 강제 경로를 폐기하고
  현재 Pi 도구로 진행한다. 예전 P1 한정 예외를 확대 승인받을 필요가 없으며, 이 도구 때문에 작업을 막지 않는다.
  첫 안정화 범위 B01/B02는 재현을 마쳤고 [최소 수정 계획](../superpowers/plans/2026-09-12-failure-contracts.md)을 작성했다.
  기획 중복에서 첫 유효 항목을 유지하는 기준과 수정→회귀→독립 검토는 사용자 승인을 받았다. 운영/외부 승인 gate는 유지한다.

## 2. 완료 — 재작업 목록에서 제외

| ID | 작업 | 완료된 범위·근거 | 분리해서 남기는 것 |
| --- | --- | --- | --- |
| C01 | 기본 MVP 집필·관리 | 작품/권/회차, 마크다운 편집·미리보기, 상태·메모·글자 수, txt/md 내보내기, 인물·관계·로어 관리, AI/윤문 패널, 설정·라이선스 고지. [MVP 사양](../../대시보드_MVP_사양.md), [기존 QA](../../QA_개발검증_리포트_v3.md) | 축소 구현 UI는 U01~U04; 비개발자 실기기 수용은 G04 |
| C02 | 기존 집필 보조 고도화 | 기획/목차·인물 생성, 권 개요·문체 프로파일, 장면 CRUD/조립/AI, 복선 CRUD·reminder·제안, 자동 로어 주입, canon/품질 진단·이력, 감수·병렬 집필 기능. `HANDOFF.md` 고도화 이력 및 현재 소스 | 진단 B01/B02/B03 종결, 영속 작업 흐름 D01~D03, 실제 품질 G02 |
| C03 | 원고 보존 1단계 | revision 충돌, 회차별 저장 큐, 전환/늦은 응답 방어, 복구 draft, snapshot·복원, 윤문/장면 반영 안전성. [독립 최종 검증](../audits/preservation-final-validation.md) | 운영 적용 G01; 모든 삭제의 휴지통 기능까지 구현했다는 뜻은 아님 |
| C04 | 공통 AI 맥락 일관성 | 단일/병렬/감수/canon 소속·revision·본문 opt-out·관계·목적·회수 허용, 미래 계획 구분, 요청 snapshot/출처 격리. 최종화에 일반 연재 훅 점수를 강제하지 않음. [최종 검증](../audits/ai-context-final-validation.md) | M01은 **MemoryPage** 문제로, 완료된 AI 패널 맥락 수정을 다시 여는 것이 아님 |
| C05 | 관리 CRUD·검색 무결성 | 타 회차 scene reorder/타 작품 복선 참조 거부, 관계 있는 인물·복선 참조 회차 삭제 409, 회차 0개 reminder, FTS project/category scope 후 limit, 명시적 `volume:null`. `HANDOFF.md` 9월 9일 결과: 관련 54/전체 277 passed | 9월 8일의 관리 후보 재현 작업은 종료. 별도 B01/B02도 C13에서 종결 |
| C06 | 환경·빌드 정리 | Vite 중복 build 제거, AnyIO/Starlette/HTTPX 호환성 고정, 실행 shell LF 정규화. [호환성 보고](../audits/anyio-starlette-httpx-compatibility-2026-09-10.md), Windows 계획의 정적 점검 결과 | ResourceWarning 등 선택적 정리 O05; 지정 장치 QA G04 |
| C07 | 장편 기억 기반·수동 거버넌스 | MemoryEntry/migration, provenance/revision/hash/적용 시점, 승인·stale 주입 경계, generate/canon 연결, API/UI·필터·500건 이후 stale 탐색. [구현 기록](../superpowers/plans/2026-09-11-long-memory-followup.md) | UI·안내 M01~M05도 수용 완료. 더 넓은 인지 모델 D02, 운영 G01은 별도 |
| C08 | 승인된 장편 기억 P1 네 건 | 초안 폐기 오전송, POST pending 입력 보호, PATCH CAS 경쟁, chapter 삭제/기억 생성 경쟁 수정. 독립 무결성 PASS·UI PASS with notes 및 assertion 보강 완료. [최종 기록](../superpowers/plans/2026-09-11-long-memory-followup.md) | 원래 P2 다섯 건도 아래 M01~M05로 수용 완료. 테스트 assertion 지적과 worker timeout은 해결됨 |
| C09 | 고정 GPT OAuth 전환 | localhost bridge / `gpt-5.6-luna` / 기본 `xhigh`, 신규 AI 경로에서 endpoint 선택 제거, S5/S7 상태 안내, legacy 호환 경로 보존. [설계](../../기술설계_GPT_OAuth_브릿지_v1.md) | 오프라인/fake 계약 완료일 뿐 실제 로그인·provider 수용 G02/G03 미실시 |
| C10 | 자동 요약의 provider-free planner | 명시 chapter allowlist, deterministic manifest, provider 없는 계획·경계 테스트. [설계·완료 경계](../superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md) | 실제 summary job 저장/worker/draft 생성·운영 backfill D04 미구현 |
| C11 | 백업·복원·migration 임시 검증 | 원고 보존 검증의 **선택 11개 테이블 합성 데이터 full-row 백업 비교**, [9월 10일 임시 SQLite 복원](../audits/backup-restore-dry-run-2026-09-10.md), 기존 데이터 포함 migration 회귀, memory downgrade/re-upgrade, [운영 런북](../runbooks/long-memory-governance-release.md) 작성 완료 | 새 failure injection V02, 실제 DB/credential/교체·rollback G01/G03. 임시 검증 자체를 다시 할 일로 올리지 않음 |
| C12 | 평가·QA 준비와 자동화 | [실모델 평가 설계](../audits/ai-model-quality-evaluation-design-2026-09-10.md), [Windows QA 계획](../audits/windows-device-qa-plan-2026-09-10.md), 브라우저 fixture/axe·임시 실제 API/SQLite/fake-provider 통합 검증 완료 | 전체 실기기·실모델 수용이 아님. V01~V03 및 G02/G04만 잔여 |
| C13 | B01/B02 실패 계약·B04 테스트 격리 | canon 전체 구조 검증·1회 repair, bootstrap exact 슬롯·metadata 정합성, native pre-import 테스트 격리·공식 runner. 419P/외부 skip1, 독립 검토 2건 PASS·부모 수용. [최종 근거](../audits/failure-contracts-2026-09-12/b04-review-fixes.md) | 외부 metrics 비교 V04, 실제 provider/credential/운영 G gate. 과거 사고의 한계는 보존 |

## 3. 실패 계약 종결·미수정 후보

### 3.1 장편 기억 P2 다섯 건 — M01~M05 수용 완료

사용자 후속 승인 범위를 구현·회귀·독립 검토 2건 PASS 후 부모가 수용했다. [최종 수용·근거·한계](../audits/memory-m01-m05-2026-09-12/acceptance.md). 기존 P1/C13과 별도 수용이며 운영 적용을 뜻하지 않는다.

| ID | 작업 | 완료 조건 | 상태 |
| --- | --- | --- | --- |
| M01 | 작품 직접 전환 시 MemoryPage 입력·필터·pending callback 소속 분리 | A→B→A의 늦은 응답도 현재 폼·toast·focus를 건드리지 않고 원래 작품만 갱신 | **수용 완료** |
| M02 | 원문 변경 후 memory cache stale 표시 갱신 | 저장/복원 revision 성공 갱신, editor unmount 이후 save acknowledgement와 통지 예외 보존 | **수용 완료** |
| M03 | project/chapter/memory 조회 오류 표시 | 실패/loading/빈 목록 구분, 키보드 재시도·입력 보존 | **수용 완료** |
| M04 | 승인·폐기 확인 취소/완료 후 focus 복귀 | 호출 버튼 또는 사라진 버튼의 목록 fallback, 다른 화면 초점 보존 | **수용 완료** |
| M05 | 연결 회차 삭제 409 안내 수정 | retired memory도 provenance 때문에 삭제를 막는 정확한 안내·데이터 보존 | **수용 완료** |

### 3.2 실패·진단 계약 — 종결 기록과 남은 후보

| ID | 작업 | 현재 근거·이미 끝난 부분과의 구분 | 판정·다음 행동 |
| --- | --- | --- | --- |
| B01 | canon 잘못된 `issues` 응답 계약 | 구조 전체 거부·기존 1회 repair·실패 성공이력 미생성. 새 격리 전체 suite 및 독립 검토 통과 | **수용 완료 — C13**, 재작업하지 않음 |
| B02 | bootstrap 권별 슬롯·metadata 정합성 | 첫 유효 항목 선택·빈 슬롯 보충, 목차/title index/VolumeNote 정합성. 신규 회귀 32건 포함 새 전체 suite 통과 | **수용 완료 — C13**. 기존 작품 재번호 부여·스키마 변경 없음 |
| B03 | 로컬 품질 지표의 의미·계수 정확성 | tilde 없는 약한 어미·긴 닫힌 인용 계수 보정, 문체 참고점수/빈 원고/essay/이력 안내, 선택적 dialog 이름. 가중치/API/기존 이력 유지 | **수용 완료(2026-09-13)**. [최종 수용·증거](../audits/quality-b03-2026-09-12/acceptance.md). backend482P/기존 skip1·frontend77P·국소 coverage 충족, 독립 검토 E1 종결2PASS. 실제 작품 평가는 G02 |

**B04 — 테스트 격리 보강 수용 완료(C13):** Windows 내부 fresh TEMP와 import 전 guard/fake-keyring, 실제 Fernet 의미 유지, 공식 `backend/scripts/run_backend_pytest.py`를 제공했다. 첫 독립 검토의 Windows 파일명 비교·실행 가이드 지적을 보정하고 재검토 2건 PASS를 확인했다. 보호 범위는 writable-open/알려진 민감 읽기 등 명시된 검사이며 일반 OS sandbox가 아니다.

[최종 수용](../audits/failure-contracts-2026-09-12/b04-review-fixes.md), [지원 실행 가이드](../runbooks/isolated-backend-tests.md), [승인 계획](../superpowers/plans/2026-09-12-failure-contracts.md)을 따른다. 기존 401개 assertion 실행의 보존 실패·credential 부수 효과 미확정, 옛 `.coverage` 미복구는 [사고 기록](../audits/failure-contracts-2026-09-12/validation-isolation-incident.md)에 남긴다. 사용자가 유지 승인한 a8db… 생성본은 새 실행 동안 보존했다. 실제 키 저장소 조사·정책 변경·Git 반영은 수행하지 않았다.
B03은 [집필·관리 감사](../audits/소설집필_관리_감사.md)의 후보를 새 공식 격리 runner로 재현·수정·수용했다. [원래 RED·로그](../audits/quality-b03-2026-09-12/manifest.json)와 [수용 사본 manifest](../audits/quality-b03-2026-09-12/accepted-evidence/manifest.json)를 구분한다. 504·axe·formatter 계측·ENOMEM 실패 원문은 유지하고 최종 현재 파일 검증으로 해결했다. 실제 외부 metrics/provider는 실행하지 않았다.

### 게시 전 보안 참고 A1 — 낮음·별도 후속 범위

2026-09-13 게시 검토 2건은 PASS/차단0이다. 다만 `backend/app/routers/ai_panel.py:280`의 **기존** 일반 provider 오류 메시지 전달에 upstream 민감 정보가 로컬 화면으로 반영될 가능성이 있다는 LOW 참고를 남겼다. 새 회귀·실제 유출은 관측하지 않았으며 수용된 C13/B03을 재개하지 않는다. 고정 일반 메시지·정제 진단·fake sentinel 회귀의 별도 후속 범위를 검토할 수 있다. [검토 원문·범위](../audits/publication-2026-09-13/security-review.md.txt). 현재 사용자 승인은 인계·Git 게시이며 이 참고의 구현은 하지 않았다.

## 4. 미구현 제품 범위 — 구현된 기반과 분리

| ID | 작업 | 이미 있는 것 | 실제 남은 범위·착수 조건 |
| --- | --- | --- | --- |
| D01 | 영속 회차 브리프/목표 | EpisodeBrief 입력·요청 전달, Chapter.memo, 회차 목적 지시 | **수용 완료(2026-09-13)** — 회차당 현재 목표 + append-only 이력 + 목록·복원, purpose 영속, CAS 409, 명시 불러오기만 생성 반영. [수용](../audits/d01-goal-contract-2026-09-13/acceptance.md). 게시·운영 적용은 별도 승인 |
| D02 | 인지·상태를 구분하는 장편 기억 확장 | 근거·적용 시점·승인/stale, 미래 복선 구분, 복선의 audience_knows, **아크 요약 슬라이스(2026-09-14)** — `summary_jobs.kind='arc'`·`arc_summary` MemoryEntry·`arc-v1`(migration `d1e2f3a4b5c6`), **권 기억 + 커버리지 선택(2026-09-14)** — `kind='volume'`·`volume_memory`·`volume-v1`·승인 상위층의 하위 요약 커버리지 제외(migration `e2f3a4b5c6d7`) [설계](../specs/2026-09-14-hierarchical-memory-500ep.md) | **인지·상태 구현 슬라이스 완료(2026-09-14)** — `knowledge_states`·`event_impacts` migration `f1a2b3c4d5e6`, 캐릭터 lifecycle migration `g2a3b4c5d6e7`; 수동 CRUD와 append-only 전이, draft-only cognitive derive, 승인 aware 기준 fail-closed POV, generate/canon 공통 `pov_character_id`, Cognitive UI를 구현했다. 설계 P1~P4의 이 슬라이스 범위는 완료이며 운영 적용·실제 provider는 별도 gate |
| D03 | 기획→집필→퇴고→완결·재개 흐름 | 권 개요·인물 설정·장면·감수·원고 이력, 최종화 목적 | **D03-1 수용(2026-09-13)** — flow_stage 상태 기계·전이 이벤트 앵커 [수용](../audits/d03-1-flow-stage-2026-09-13/acceptance.md). **D03-2 수용(2026-09-13)** — 재개 계약(드리프트·미해결 감수·다음 장면) [수용](../audits/d03-2-resume-2026-09-13/acceptance.md). **D03-3 수용(2026-09-13)** — projects.serial_state 연재 수명주기 분리 [수용](../audits/d03-3-serial-state-2026-09-13/acceptance.md). **D03-4 수용(2026-09-13)** — 목표 항목↔원문 발췌 근거 링크·파생 파손/드리프트 안내 [수용](../audits/d03-4-evidence-links-2026-09-13/acceptance.md). **D03-5 수용(2026-09-13)** — 복선 disposition(해결/의도적 미해결/외전 이관) 구분 표시 [수용](../audits/d03-5-foreshadow-disposition-2026-09-13/acceptance.md). **D03-6 수용(2026-09-13)** — 완결 점검표 + 완결본 불변 스냅샷 [수용](../audits/d03-6-final-edition-2026-09-13/acceptance.md). **D03-7 수용(2026-09-13)** — 작품 결말 후보·잠금·파생 영향 표시 [수용](../audits/d03-7-ending-impact-2026-09-13/acceptance.md). **D03 전 단위 수용 완료** |
| D04 | 실제 자동 요약·backfill | C10의 provider-free manifest planner | **D04-1 수용(2026-09-13)** — summary_jobs 영속 + fake worker 생명주기(계획 중복 차단·복구·재시도·draft append) [수용](../audits/d04-1-summary-worker-2026-09-13/acceptance.md). **실제 provider 어댑터 `summary_provider.py` 구현·7P**. **실제 브릿지 smoke 완료(2026-09-14)** — `scripts/summary_smoke.py`가 합성 TEMP DB + 실제 OAuth 브릿지로 draft_saved까지 검증, 자동 승인 없음 [수용](../audits/d04-2-summary-smoke-2026-09-14/acceptance.md) · [운영 runbook](../runbooks/summary-backfill-operations.md). **평가 manifest·승인 UI 통합·운영 도구 완료(2026-09-14)** — [평가 manifest](../specs/2026-09-14-summary-eval-manifest.md)(전 종류 체크리스트+JSONL 기록 형식), MemoryPage에 자동 생성 배지·출처 필터·arc/volume kind 라벨, `scripts/summary_backfill.py` 운영 스크립트. 운영 DB 계획 실행 완료 — 300회차 전부 `skipped_empty`(본문 없음, provider 호출 0건), 재실행 시 전량 duplicate로 멱등 확인. 잔여: 본문 작성 후 실제 backfill 실행 + draft 검토·승인(작가) |
| E | 작가 피드백 자가개선 | style_profile·장편 기억·회차 목표·품질 진단·RefineRun accepted·MemoryEntry draft/approved | [전체 설계](../specs/2026-09-14-author-feedback-improvement.md)·[E1 사양](../specs/2026-09-14-e1-generation-runs-spec.md). **E1~E7 전부 구현(2026-09-14)** — E1+E2 수용 [수용](../audits/e1-generation-runs-2026-09-14/acceptance.md); E3 결정론 diff 분석(`generation_analysis` — 편집거리·삭제 표현·분량·surface accept율), E4 `improvement_rules`(migration `c04b5d6e7f81`, 8 카테고리·승인 후 불변), E5 제안 job(proposed만·idempotent), E6 approved 규칙만 컨텍스트 주입+`applied_rules_json`, E7 규칙 패널·생성 이력·명시 폐기 UI. HANDOFF §09-14 대량 슬라이스 참조 |

근거: [원래 집필 로드맵 §8.4–8.5](../audits/소설집필_관리_감사.md),
[자동 요약 설계](../superpowers/plans/2026-09-11-long-memory-auto-summary-backfill.md), 현재 모델·store.
로드맵이 있다는 사실을 상세 설계/구현 승인으로 바꾸지 않는다.

과거 감사의 “브리프에만 있는 로어 검색 누락”은 D02의 검색 입력·회수 범위에서,
“짧은 장면도 완료 처리/앞 장면 결과 없는 병렬 집필”은 D03의 분량·사건 이행·순차/병렬 조건에서
재확인한다. 새 실행 재현 없이 해결됐다고 닫거나 확정 결함으로 늘려 세지 않는다.

## 5. 검증·계측만 남음 — 기존 구현 재작업 아님

| ID | 작업 | 완료된 근거 | 미실시 범위 |
| --- | --- | --- | --- |
| V01 | 프론트 source-mapped coverage | TS/Vite build, Memory E2E/axe 통과 | **수용 완료(2026-09-13)** — `PW_COVERAGE=1` opt-in V8 수집→Istanbul union 병합 [수용](../audits/v01-frontend-coverage-2026-09-13/acceptance.md). 11 스위트 128P·tripwire 0·57 소스 파일 측정값: lines 83.27%·branches 83.28%·functions 60.92%. 측정 기록이며 임계 목표 주장 아님 |
| V02 | 복원 실패 시나리오 보강 | C11의 합성 데이터 백업/복원·migration 검증 완료 | **수용 완료(2026-09-13)** — manifest 무효·파일 누락·잘못된 schema·disk-full·integrity·FK failure injection 15P [수용](../audits/v02-restore-verify-2026-09-13/acceptance.md). wrong-key는 G03 범위 유지. 실제 운영 DB 복원 실행은 G01/G03 |
| V03 | 추가 환경/부하 범위 | 실제 독립 SQLite 세션을 이용한 CAS·잠금 경합 검증 완료 | **다중 프로세스 검증 완료(2026-09-13)** — `sqlite_multiprocess_check.py` 8×50·16×100 동시 쓰기 무손실·integrity ok·WAL [수용](../audits/uo-options-v03-2026-09-13/acceptance.md). 실제 HTTP 다중 프로세스 배포 구성 검증은 배포 형태 확정 시 별도 |
| V04 | 외부 im-not-ai metrics 버전 동기화 | 내부 경계 회귀 유지. 부모가 기존 미설치 skip 1건을 분리해 허용 | **완료(2026-09-14)** — AST 전용 `verify_metrics_module` 20P + 실물 `C:\Users\wj941\.agents\im-not-ai\...\metrics_v2.py` 대조 전 항목 일치(`ok:true`, [증거](../audits/v04-metrics-version-2026-09-13/real-file-verification.txt)) [수용](../audits/v04-metrics-version-2026-09-13/acceptance.md) |

## 6. 운영·외부·장치 승인 대기 — 지금 자동 실행하지 않음

| ID | 승인 단위 | 준비 완료 | 필요한 입력/실행과 완료 증거 |
| --- | --- | --- | --- |
| G01 | 기존 DB migration·운영 적용 | migration 코드·임시 검증·운영 런북 | **실행 완료(2026-09-13)** — 실 DB를 `f9a1b2c3d4e5` 수준에서 head `9d0e1f2a3747`로 10개 migration 적용, 백업→복원 검증→리허설→실 적용→데이터 보존 검증 전 과정 수행 [수용](../audits/g01-production-migration-2026-09-13/acceptance.md) |
| G02 | 실제 OAuth/provider 수용·문학 품질 파일럿 | 고정 provider fake 계약·평가 설계 | **실행 완료(2026-09-14)** — 실제 `openai-oauth` 브릿지(ChatGPT OAuth, `gpt-5.6-luna`) 경유 6-case 실 호출 전부 완결(generate×3·parallel×2·review×1), raw SSE 2,803건·usage·latency 기록, DB snapshot 해시 동일, marginal $0(cap $20) [수용](../audits/g02-pilot-2026-09-14/acceptance.md). 독립 AI evaluator A/B blind 2회도 완료: hard-block 없음·축별 lower median 3 이상·최대 점수 차이 1점 [상세](../audits/g02-pilot-2026-09-14/independent-blind-evaluation-2026-09-14.md). 인간 평가자 대체 여부와 작가 accept는 별도 정책/사용자 판단 |
| G03 | credential·key 복구/로그아웃 | bridge credential 소유 경계와 키 분리 설계 | **실행 완료(2026-09-14)** — 실 crypto 경로(`g03-real-crypto-path.txt`) + **브릿지 소유 로그아웃·복구 전 주기 실증**: `openai-oauth stop`→포트 종료, 양 auth.json 제거→브릿지 기동 거부("No auth file found"), 복원→실 호출 성공("복구 완료"). 임시 credential 사본 시연 후 전량 파기 [수용](../audits/g03-oauth-logout-2026-09-14/acceptance.md). 서버 측 세션 폐기·완전 재로그인은 bridge 미지원 계정 소유자 선택으로 비차단 분리 |
| G04 | 지정 Windows 실기기 수용 | Windows native 임시 DB 자동화와 WSL 실행 경로 정적 점검 | **최종 수용 완료(2026-09-14)** — 네이티브 전체 스위트 714P·alembic 완주·실기동 프로브(boot 3.79s·54,300자 PUT 43ms·CAS 409·snapshot/resume 정상) + **실제 브라우저 검증 10/10**(mock 없음) + **NVDA 실제 음성 발화·포커스 순환 실증**(`nvda-speech-evidence.txt` — 랜드마크·제목 수준·링크·버튼·콤보박스 롤/값/상태 발화, 전용 창 Tab 순환 발화) + 병렬 세션의 NVDA 2026.1.1 설치·4개 화면 UIA 트리 확인 [최종 수용](../audits/g04-real-browser-2026-09-14/acceptance.md)·[병렬 기록](../audits/g02-g03-g04-user-actions-2026-09-14/acceptance.md) |

운영 DB, 실제 OAuth/provider, keyring, 지정 장치에 이번 정리로 새 승인이 생기지 않는다.
실행 순서는 [운영 런북](../runbooks/long-memory-governance-release.md)과 각 승인서에서 확정한다.

## 7. 축소 구현 UI·선택 백로그·제외 정책

### 기존 사양의 축소 구현 — 없던 일로 지우거나 출시 결함으로 단정하지 않음

| ID | 항목 | 상태·다음 판단 |
| --- | --- | --- |
| U01 | 캐릭터 card_json 자유 확장 UI (F-011) | **구현 완료(2026-09-13)** — `CardJsonSection`(merge-patch 재사용), fixture 5/5 [수용](../audits/uo-options-v03-2026-09-13/acceptance.md) |
| U02 | 로어 참조 회차 표시 (F-016, 선택 기능) | **구현 완료(2026-09-13)** — `GET /lore/{lid}/referencing-chapters`+접이식 목록, backend 17P·fixture 4/4 [수용](../audits/uo-options-v03-2026-09-13/acceptance.md) |
| U03 | 윤문 명령 프리셋 UI | **이미 충족(2026-09-13)** — prompt_presets CRUD+Settings UI+AiPanel `preset_id` 왕복 선존, 중복층 미추가 |
| U04 | 시니어 전용 확대 모드 | **구현 완료(2026-09-13)** — `uiScale` 3단 영속+에디터 typography compartment, fixture 3/3 [수용](../audits/uo-options-v03-2026-09-13/acceptance.md) |

### 현재 우선순위 밖의 선택 확장

- O01: ~~SillyTavern 카드 PNG import/export, novelWriter import~~ — **구현 완료(2026-09-13)** 16P [수용](../audits/uo-options-v03-2026-09-13/acceptance.md).
- O02: ~~자동 주기 백업~~ — **구현 완료(2026-09-13)** `JIPPEEL_AUTOBACKUP_INTERVAL_MIN` opt-in 11P. 클라우드 동기화·Git 버전 관리·추가 삭제 복구 UI는 미채택 잔여.
- O03: ~~연재 캘린더~~ — **구현 완료(2026-09-13)** `GET /projects/{pid}/writing-activity` 5P(멀티 작품 합계는 기존 목록 제공). 플랫폼 직접 발행 연동은 정책 확인 전 보류 유지.
- O04: 새 provider/모델 선택지, KoboldCpp native, 임베딩 검색·병렬 작업자 수 확대. 현재 고정 OAuth 계약에서는 우선하지 않음.
- O05: ~~비차단 ResourceWarning~~ — **정리 완료(2026-09-13)** `inspect(bind)` 연결 유지 근본 수정, warnings 19→0.
- O06: ~~플랫폼 규정 재확인~~ — **실행 완료(2026-09-13)** `규정추적_2026-09-13.md`(AI 정책 변화 없음 확인). 게시·배포 판단 시점에 다시 최신화.

**되살리지 않을 것:** 신규 endpoint/API key/base URL·모델 선택 UI는 의도적으로 제거했다.
legacy `ai_endpoints`/hidden routes는 보존·migration 호환용이지 재도입 할 일이 아니다.
AI 자동 삽입·무검수 자동 승인·탐지 회피 기능도 추가하지 않는다.

## 8. 후속 순서 — 사용자 순차 진행 승인 반영

### 2026-09-14 D02 인지·상태 슬라이스 구현 기록

- `KnowledgeState`와 `EventImpact`를 모델·schema·migration·router에 추가했다. 수동 입력은 승인 상태로 저장하고 derive 결과는 `draft`로만 저장한다.
- 상태 수정·폐기는 원본 행을 바꾸거나 지우지 않고 successor/retired transition을 append한다. 최신 상태는 시점 경계를 적용한 뒤 `(effective_from_sort_order, id)` 기준으로 선택한다.
- `build_context_bundle`는 POV 캐릭터의 프로젝트 소속을 검증하고, 승인된 `aware` 대상만 허용하는 fail-closed 정책으로 fact/lore/foreshadow/event 컨텍스트를 제한한다. 명시적으로 승인한 foreshadow도 POV 인지 게이트를 우회하지 않는다. generate와 canon 모두 `pov_character_id`를 전달한다.
- `derive-cognitive`는 고정 GPT OAuth bridge adapter를 사용하며 설정 오류는 503, provider/연결 오류는 502로 반환한다. adapter는 동기 worker 계약을 유지하면서 sync/async client close를 보장한다.
- `CognitivePage`와 AI 패널·CanonDialog POV 선택 UI는 명시적 label/id 및 ARIA 상태를 사용한다. 작가 시야(null)가 기본값이다.
- 회귀 근거: cognitive suite 34 passed. 전체 backend와 frontend 최종 수치는 아래 검증 게이트에서 재실행한다.


실행 순서는 [9월 12일 순차 승인 기록](../superpowers/plans/2026-09-12-remaining-sequence.md)을 따른다. 아래는 기존 의존성 참고이며, 실제 자원에 대한 대상/비용/접근 승인은 별도로 충족해야 한다.

1. **안정화 종결:** B01/B02/B04는 C13, M01~M05와 B03도 수용 완료다. 완료된 범위를 다시 열지 않는다.
2. **다음 승인 묶음:** D01 → D03 → D04의 상세 요구·저장/상태/job 계약·기획부터 진행한다. 로드맵을 상세 구현 승인으로 대신하지 않으며 기존 planner를 재구현하지 않는다. D02는 이 묶음의 자동 추가 범위가 아니다.
3. **검증 보강:** 그 다음 V01/V02/V04. V03은 배포 구성에 필요할 경우만 채택한다.
4. **실제 자원 수용:** G02 → G01 → G03 → G04 순서로 환경·예산·접근 허가 등 개별 gate를 충족한 뒤만 실행한다.
5. U/O 항목은 핵심 안정화와 실제 작가 사용 결과 뒤에 선택한다.

## 9. 검증 수치의 최신성과 근거

| 증거 층 | 가장 최근 확인한 결과 | 해석 한계 |
| --- | --- | --- |
| 전체 backend — 최신(2026-09-15 D02 source-hash 회귀 보강 후) | **872 passed / 1 skipped / violations 0** | 지정 isolated runner; `subprocess_attempts=0`, `internal_ipc_count=507`, `fake_keyring_calls=8`. 실제 provider/운영 DB 아님 |
| 전체 backend — Windows 네이티브 | **714 passed / 1 skipped / violations 0 / warnings 0** | Windows 11 네이티브 Python 3.14.4 + 격리 러너 그대로. 수동 실기기 수용(G04 잔여)과 구분 |
| V03 다중 프로세스 부하 | 8×50·16×100 동시 쓰기 **rows 무손실·integrity ok·journal wal** | `scripts/sqlite_multiprocess_check.py` — 실제 HTTP 다중 프로세스 배포 구성 아님 |
| 전체 backend — B03 최종 | **482 passed / 1 skipped / 70 subtests / 19 warnings** | native isolated runner, exit0·guard 위반0·실제 subprocess 시도0. 기존 외부 metrics skip(V04) 유지 |
| B03 frontend·접근성 | **quality5 + memory31 + preservation26 + AI15 = 77 passed**, app/helper TS·build PASS | 전용 fixture-only/no escapes. quality fullaxe3회 violations/incomplete 0, 지정 실기기 아님 |
| B03 변경범위 coverage | quality **19/20·10/10**, QualityDialog **278/284·42/48**, Dialog **41/41·14/14** (line·branch) | Python L34는 미계측 실행행으로 미충족 유지. source/map 일치·raw merge/Istanbul 독립 재구성. 전체 V01 아님 |
| B03 독립 검토·보존 | 제품 지적0, E1 현재 보조 파일 증거 종결 **2 PASS** | 218원래+25retry artifacts·16source/protected hashes, 초기 BLOCKED/ENOMEM과 최신 helper hash 구분 |
| M01~M05 당시 전체 backend | **421 passed / 1 skipped / 70 subtests / 19 warnings** | 당시 수용 결과이며 B03의 482개와 합산하지 않음 |
| B01/B02/B04 coverage | bootstrap line **96.19%** / branch **81.52%**, canon **87.10% / 83.33%**, guard **93.44% / 91.67%** | 3모듈만 계측. 전체 backend/프론트 coverage 아님 |
| B04 독립 재검토·보존 | 코드 **PASS**, 격리·보존 **PASS** → 부모 수용 | read-only 검토. 37개 app 소스 및 승인된 coverage 보존; LSP **clean 0 / inconclusive 5** |
| M01~M05 frontend | **Memory 31 / preservation 26 / AI fixture 15 = 72 passed**, TS/helper TS/build PASS, axe serious/critical 0 | fixture-only positive no escapes. 지정 Windows 실기기 수용 아님 |
| M01~M05 변경범위 coverage | Memory line **60/60**, branch **33/33**; drafts **2/2**, branch N/A; queryClient **11/11, 5/5**; App N/A; projects literal **1 → 실행문장 1** | source-mapped 국소 계측. N/A≠100%, raw Python L299 미계측. 전체 V01 미완료 |
| M01~M05 독립 검토·보존 | 상태/접근성 **PASS**, 격리/계측 **PASS**, 부모 수용 | 356 artifact·29 source·5 protected hash 직접 확인. LSP diagnostics0 / clean1 / inconclusive4 |
| P1 당시 전체 backend | **317 passed** | 역사적 P1 수용 로그. 최신 전체 결과는 위의 482개 |
| P1 관련 backend + coverage | **64 passed** | 전체 317과 합산하지 않음 |
| P1 당시 Memory Playwright/axe | **6 passed**, assertion 보강 후 부모 재통과 | 다른 모든 UI의 현재 재실행 결과는 아님 |
| TypeScript/Vite build | **최신 PASS** — `npx tsc --noEmit`, `npm run build` (Vite 5.4.21) | 지정 Windows 기기 수용과 다름 |
| 핵심 3모듈 branch 포함 coverage | memories **93%**, projects **85%**, long_memory **93%**, 합산 **90%** | 전체 저장소/프론트 coverage 아님; 예전 4모듈 93.59%와 분모가 다름 |
| 독립 검토 | 무결성/security **PASS**, UI **PASS with notes** → assertion 보강 | 정적 검토. reviewer가 테스트를 독립 실행했다고 주장하지 않음 |

최신 D02 게이트: backend **872 passed / 1 skipped**, isolation violations 0; frontend tsc/build PASS; Alembic current `f1a2b3c4d5e6`, head `g2a3b4c5d6e7`. 독립 검토 후 nested delta project validation, historical transition 차단, malformed derive 응답 502, canon client close, assistant POV 전달을 보강했고, 원문 변경 시 source hash가 달라져 기존 파생 행을 stale 이력으로 보존하는 회귀를 확인했다.

저장소 내 최신 근거: [B03 최종 수용](../audits/quality-b03-2026-09-12/acceptance.md), [B03 최종 사본 manifest](../audits/quality-b03-2026-09-12/accepted-evidence/post-write-manifest.json).
M01~M05 수용 당시: [최종 수용](../audits/memory-m01-m05-2026-09-12/acceptance.md), [사본 manifest](../audits/memory-m01-m05-2026-09-12/accepted-evidence/post-write-manifest.json).
B04 수용 당시 근거: [B01/B02/B04 최종 수용](../audits/failure-contracts-2026-09-12/b04-review-fixes.md), [필수 실행·검토 증거 manifest](../audits/failure-contracts-2026-09-12/accepted-evidence/manifest.json).
기존 P1/UI 수치는 당시 [P1 수정·최종 수용 기록](../superpowers/plans/2026-09-11-long-memory-followup.md)이며 B04에서 UI/build를 재실행하지 않았다.
로컬 근거(원격 checkout에 자동 제공되지 않음):

- 최종 수용: `/home/hunter8891/.pi/agent/sessions/--mnt-c-Users-wj941-Documents-jippeel--/subagent-artifacts/outputs/2c5a47a8-9c26-4766-8b62-2b1981a198ac/parent-acceptance.md`
- 최초 기억 검토: 같은 sessions 하위 `subagent-artifacts/outputs/a3b64221-53bb-476a-b99d-533595151ec7/reviews/parent-synthesis.md`
- 실행 로그: `/tmp/jippeel-memory-p1.Ge5TLu/{full-final-backend,coverage-final-backend,final-build,parent-reviewed-frontend}.txt`

예전 **108 passed / 294 passed·9 failed·1 skipped**는 당시 기록으로 보존한다.
P1 당시 im-not-ai 외부 script 실패는 최종 실행에서 재현되지 않았다. B04에서는 mocked executor 테스트의 파일 존재 전제만 owned TEMP의 fail-if-executed sentinel로 충족했으며 실제 호스트 스크립트는 실행하지 않았다. 외부 metrics 소스 비교 1건(V04)은 미검증이다. 영구 환경 해결이나 실제 외부 호환성 PASS로 확대하지 않는다.

## 10. 옛 목록의 종결·이관표

| 옛 항목 | 현재 판정 |
| --- | --- |
| 9월 8일 §2 “다음 작업: 관리 후보 재현” / 우선순위 1 | C05 완료 — 재개하지 않음 |
| 9월 8일 우선순위 2 “canon/기획 생성 실패 계약” | B01/B02/B04 **C13 수용 완료** — 419P/기존 외부 skip1, 독립 검토 2건 PASS. 과거 사고의 한계는 보존 |
| 9월 8일 우선순위 3 “독립 평가 설계” | 설계 C12 완료 / 실제 평가 G02 대기 |
| 9월 8일 우선순위 4 “장편 기억” | 기반·수동 UI C07/C08 및 M01~M05 보정 완료 / D02 확장 / D04 자동화 / G01 운영 분리 |
| 9월 8일 우선순위 5 “영속 목표·완결” | D01/D03 미구현 유지 |
| 9월 8일 우선순위 6 “백업·복원” | 임시 검증·런북 C11 완료 / V02 실패 보강 / G01/G03 실제 실행 대기 |
| 9월 8일 우선순위 7 “Windows QA” | 계획·정적 점검 C06/C12 완료 / G04 지정 장치 수용 대기 |
| Vite/AnyIO 경고, memory prompt 연결/UI, 임시 rollback | C06/C07/C11 완료 — 과거 HANDOFF에서 다시 가져오지 않음 |
| MVP §7의 로어 자동 주입·장면·연속성 검사 “백로그” | 기본 기능 C02 완료. 더 넓은 품질·시간축 요구만 B/D/G로 분리 |
| QA v3의 axe “전부 pending” | 자동화한 범위 C12 완료 / M04 및 G04 수동 영역만 구분 |
| 원래 P2 5건과 새 테스트 assertion 지적 | M01~M05 수용 완료. assertion은 C08에서 해결 |
| prime-agent 부재 / worker timeout | P1 timeout은 복구 완료. 이후 사용자가 prime-agent 미사용을 명시해 강제 경로도 폐기했다. 현재 Pi 도구를 사용하며 prime-agent 승인 대기는 종료 |

상태 변경 시 해당 ID의 **완료 범위·남은 범위·근거·승인 조건**을 여기서 갱신한다.
사양·runbook은 동작/절차를 정의하고 작업 상태는 이 문서를 링크한다.
수치가 없는 제품 확장/수동 QA를 섞은 “전체 완료율”은 계산하지 않는다.

---

## 보존된 2026-09-08 인계 원문 — 현재 실행 목록 아님

아래는 당시 승인·소스·후보를 보존한 이력이다. 당시 commit/push 승인은 이번 정리에 재사용하지 않는다.
완료/잔여 판단은 위의 종결·이관표와 현재 작업표가 우선한다.

## 1. 현재 상태와 이번 요청의 경계

- 작업·게시 대상: **main**. 기존 검증 브랜치의 변경을 fast-forward로 main에 통합했다. 새 기능 브랜치는 만들지 않는다.
- 기능 검증 기준: 소스 `cd7fc1f3360b6e42d49ab75398b94732ed057649`, 문서 `92c9cda995d10ef565b0af631cf5038206a63a3e`.
- 원고 보존 1단계와 AI 맥락 일관성은 구현·독립 검토가 끝났다. 다시 미완료 작업으로 열지 않는다. [보존 결과](../audits/preservation-final-validation.md), [AI 맥락 결과](../audits/ai-context-final-validation.md).
- 최근 검증은 backend269 / UI·SPA15 / 보존17 / 가짜 제공자 실제 통합3 및 build PASS다. 각 검증 층의 수치는 합산하지 않는다. 새 기능이나 실모델 품질 전체의 통과를 뜻하지 않는다.
- **이번 승인은 남은 작업 문서화·main 커밋·push까지다.** 아래 기능 구현, 실제 모델 호출/비용, 운영 DB 접근·마이그레이션·배포는 별도 승인 대상이다. Git push를 운영 배포로 간주하지 않는다.

## 2. 다음 한 작업

**관리 데이터 무결성 후보를 현재 버전의 격리 API에서 재현하고, 첫 수정 범위를 확정한다.**

AI 요청에서 잘못된 소속을 거부하는 기능이 완성됐어도, CRUD가 잘못된 참조를 저장하거나 삭제/검색에서 실패하는 문제까지 해결됐다는 뜻은 아니다. 아래 후보는 과거 감사와 현재 정적 검토에 근거한다. **이번 인계 작업에서 새 실행 재현을 하지 않았으므로 현재 재현 확정 결함으로 단정하지 않는다.**

첫 산출물은 후보별 재현 결과/실패 테스트, 영향 데이터, 최소 수정안이다. 실제 운영 데이터 대신 새 합성 TEMP DB를 사용한다. 재현된 항목만 구현 계획으로 올린다.

## 3. 우선순위와 완료 조건

| 순서 | 작업 | 최소 완료 조건 | 현재 상태 |
| --- | --- | --- | --- |
| 1 | 관리 CRUD·조회 무결성 | 타 작품 장면 reorder 및 복선 회차 참조 거부; 관계가 있는 인물 삭제 및 복선에 연결된 회차 삭제 정책; 회차 없는 작품 reminder; 작품별 FTS 제한 순서; `volume:null` 이동을 각각 재현하고 회귀 테스트로 검증 | 과거 재현/현재 정적 후보, 새 재현 필요 |
| 2 | 모순 응답·기획 생성의 실패 계약 | 기존 JSON 파싱 실패 처리는 유지하고, 파싱 가능한 잘못된 `issues` 스키마가 실제 모순 0건으로 처리되지 않게 구분. 부트스트랩 결과의 권별 회차 수·순서·중복·폴백을 검증 | 후속 후보, 현재 버전 재현부터 |
| 3 | 문학 품질의 독립 평가 설계 | 작가가 미리 고정한 설정·사건 정답, 블라인드 비교, 모델/분량/예산 통제, 채택률·수정량·모순율·시간/비용 기록. 합격 기준을 실행 전에 승인 | 실제 모델·문학 품질 미검증 |
| 4 | 회차 시점별 작품 기억 | 근거 원고/revision/적용 시점/승인 여부를 가진 사실·변경 후보. 작가/독자/인물 인지를 구분하고 과거 수정 영향 표시. 1/20/50/100화 고정 사례로 과거·미래 혼입 검사 | 설계·구현 별도 승인 필요 |
| 5 | 영속 회차 목표·기획·퇴고·완결 연결 | 브리프 재진입 복원; 목표·사건·선택·대가를 원고 근거와 연결; 해결/의도적 미해결/외전 이관을 구분; 최종본 보존 | 후속 범위. 현재 세션 설정은 영속 목표 관리가 아님 |
| 6 | 완전 백업·복원과 운영 적용 준비 | 일관된 DB 백업을 별도 환경에 복원하고 원고 외 설정/관계/복선/장면/이력, 필요한 키 복원까지 검사. 구버전 복제 DB upgrade, rollback 및 프론트/백엔드 동시 적용 계획 확보 | 운영 DB·실제 키 복원·배포 미실행. 별도 승인 필요 |
| 7 | 실제 Windows 기기 QA | 접근성/NVDA/키보드/시니어 모드, 대용량 편집·검색 성능, 암호화·복원 동작을 합의된 환경에서 측정하고 결과표 작성 | 기존 수동 QA 항목 재검토 필요 |

3번의 평가 기준·샘플 설계는 초기에 준비하되 실모델 호출은 별도 승인 후 한다. 4→5는 의존 순서다. 6번은 출시 전 필수 조건이지 지금 운영 환경을 만져도 된다는 뜻이 아니다.

### 관리·실패 계약 후보의 코드 진입점

- 장면 reorder: `backend/app/routers/scenes.py`
- 복선 참조/reminder: `backend/app/routers/foreshadows.py`
- 관계 있는 인물 삭제: `backend/app/routers/characters.py`, `backend/app/models.py`
- 작품별 FTS 검색: `backend/app/routers/lorebook.py`의 검색 구현
- 명시적 권 미지정 이동: `backend/app/routers/projects.py`, `backend/app/schemas.py`
- canon 응답 검증: `backend/app/services/canon.py`
- 생성 계획 보충/검증: `backend/app/services/bootstrap.py`

정적 의심이 실제로 재현되지 않으면 해당 후보를 닫거나 검증 범위를 좁힌다. 오래된 감사의 행 번호나 당시 테스트 수치를 현재 결과로 재사용하지 않는다.

## 4. 완료된 부분을 다시 깨뜨리지 않을 기준

- [AI 맥락 검증 규칙](../audits/ai-context-lessons.md), [원고 보존 규칙](../audits/preservation-lessons.md)을 먼저 읽는다.
- 본문 opt-out과 회차 식별은 별개다. 생성/모순 검사/품질의 관계 대상 정책도 다르다.
- 실제 제공자 메시지와 저장 본문에서 독립 계산한 hash를 확인한다. 동일 모델의 자기 감수를 정답으로 쓰지 않는다.
- 페이지 새로고침이나 테스트의 ID 주입으로 stale-state를 지우지 않는다. 동일 SPA runtime과 남은 이전 editor/draft 상태에서 전환을 검사한다.
- 첫 await 전 snapshot, 이후 토큰·출처 확인, 회차별 저장 큐·revision·복구 잠금·명시적 반영을 유지한다.
- 검증 환경은 [AI 재실행 안내](../runbooks/ai-context-consistency.md)를 따른다. Windows native, 새 TEMP DB, import 전 환경 설정, 실제 통합은 Alembic head/우회 제거가 기준이다.

## 5. 작업 공간·공유 주의사항

- `.eval_tmp/`, 과거 감사 원시 로그·프로브·미추적 문서는 이번 인계 커밋에 일괄 추가하지 않는다. DB/WAL/SHM·키·실제 원고를 push하지 않는다.
- 일부 과거 감사와 원시 증거는 로컬에만 있다. 이 문서는 해당 미추적 문서가 없어도 남은 범위를 파악하도록 요약했다. 원격 checkout에서는 커밋된 테스트와 runbook으로 새 격리 증거를 만든다.
- [기존 수동 QA 가이드](../../QA_수동검증_가이드.md)는 항목 목록 참고용이다. 과거 기본 포트/DB 직접 접근/구형 API 명령을 그대로 실행하지 않는다. 현재 `expected_revision` 계약과 별도 테스트 환경에 맞게 개정하고 승인받은 뒤 사용한다.
- 기존 서비스나 점유 포트를 종료하지 않는다. 운영 DB/키 복원은 문서화 승인과 구분한다.
- 저장소의 main과 원격 main이 다른 경우 force push하지 않는다. 원격 변경을 확인하고 중단·재조정한다.

## 6. 낮은 우선순위·지금 늘리지 않을 것

- 비차단 Vite 중복 `build` 키 경고, anyio deprecation, 호환 helper 중복은 별도 작은 정리 작업으로 다룬다. 과거 검토 snapshot을 공백 정리 때문에 일괄 바꾸지 않는다.
- 프리셋·모델 선택지·병렬 작업자 수·외부 연동·외형 화면을 먼저 늘리지 않는다. 임베딩 도입은 시간축·근거·승인 흐름의 대체재가 아니다.

## 7. 다음 담당자의 시작 체크리스트

1. `git status --short`, 현재 `main`/원격 ref와 기능 기준 커밋을 확인한다. 기존 미추적 자료를 삭제하거나 일괄 stage하지 않는다.
2. 완료 보고서와 lessons를 읽고 완료 범위를 재개하지 않는다.
3. 2절의 관리 무결성 후보를 새 임시 환경에서 재현하는 범위부터 제안한다.
4. 재현/수정 계획 승인 → 회귀 테스트 → 최소 구현 → 독립 검토 → 실제 경계 재검증 순서를 따른다.
5. 실제 모델/운영 배포가 필요해지면 데이터·비용·백업/복원·중단 조건을 따로 승인받는다.
