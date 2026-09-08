# 원고 보존 1단계 설계

## 승인·목표
사용자는 회차별 저장 큐, 버전 확인, 교체 전 복구본, 화면/작품 일치의 설계를 채팅에서 승인하고 구현 진행을 요청했다. 이 문서는 그 범위의 실행 계약이다. 장편 기억·집필 프롬프트·결말 모드는 이번 범위 밖이다.

## 대안과 선택
단순 debounce 패치는 서버 덮어쓰기를 막지 못한다. 전체 편집기 재작성은 범위가 크다. 기존 CodeMirror/React Query/FastAPI 구조에 공통 원고 저장 계약을 추가한다. 현재 회차 본문을 기준 원고로 유지하고 장면은 명시적으로 합치는 보조 원고다.

## 안전 경계
- 운영 jippeel.db 및 WAL/SHM, 인증 설정, 기존 서버에 테스트/마이그레이션을 실행하지 않는다. 테스트 앱 lifespan DATABASE_URL도 임시 경로로 고정한다.
- 현재 checkout에서 전용 feat/manuscript-preservation 브랜치로 작업한다. 기존 미커밋 문서와 .eval_tmp는 보존하고 stage/commit에 섞지 않는다. 새 worktree 생성 동의는 받지 않았으므로 만들지 않는다. merge/push/운영 적용은 별도다.
- 프로젝트 지정 ox-alpha-free가 runtime model lookup에 없으므로 구현/검토는 사용 가능한 openai-codex/gpt-5.5로 진행한다. 화면 재디자인 없이 기존 컴포넌트를 사용한다.
- 새 라이브러리와 유료 모델 호출을 추가하지 않는다. 기존 Windows Python venv와 Windows Node 의존성을 사용한다.
- 자동저장 성공, 로컬 복구본 저장, 네트워크 전송 시도는 다른 상태다. 강제 종료 직전·디스크 장애까지 무손실을 보증하지 않는다.

## 1. 서버 원고 변경 계약
- Chapter.revision은 정수, 초기 0. metadata 변경은 본문 revision을 올리지 않는다.
- PUT 및 POST 별칭 /chapters/{cid}/content는 {content_md, expected_revision}을 받는다. expected_revision은 필수이며 누락은 422. 오래된 클라이언트를 무검증 저장으로 허용하지 않는다. 최신 프론트와 백엔드는 함께 배포해야 한다.
- 현재 revision 불일치는 409. 응답 detail은 {code: "revision_conflict", message: 한국어 안내, current_revision: 정수}. 원고와 복구본을 변경하지 않는다.
- 동일 revision+동일 본문은 revision과 snapshot을 늘리지 않는 no-op이다. no-op도 조건부 UPDATE 또는 동등한 DB write-lock 검사로 expected_revision을 원자적으로 확인한다. 내용 변경은 pre-image 캡처→조건부 UPDATE(id AND revision)→그 revision의 snapshot 삽입→호출자 commit 순으로 같은 트랜잭션에서 수행할 수 있다. snapshot 기록 실패 시 본문 UPDATE도 전부 rollback한다. snapshot을 먼저 삽입하는 동등 구현도 원자성과 경합 시험으로 검증해야 한다. revision 경쟁/해당 unique 경쟁은 rollback 후 409로 처리하되 다른 무결성 오류를 무조건 충돌로 숨기지 않는다. 선행 SELECT 비교만으로 동시성을 보장했다고 하지 않는다.
- 모든 회차 본문 교체 경로(일반 저장/POST 별칭/윤문 수락/장면 합치기/복구)가 공통 서비스에 들어간다. 신규 회차 생성과 bootstrap 초기 데이터 삽입은 revision=0이다.
- ChapterDetail 및 회차 목록은 revision을 반환한다. 오류는 원고의 내용이나 존재하지 않는 타 작품 정보를 임의로 노출하지 않는다.

## 2. 복구본과 복구
- ChapterSnapshot: id, chapter_id(FK), revision, content_md, reason(autosave/refine/scene_merge/restore), created_at. (chapter_id, revision) unique. 저장 변경 전의 원문을 기록한다. 자동 삭제/보관 수 상한은 이번에 넣지 않는다.
- GET /chapters/{cid}/snapshots는 최신순 메타데이터 목록, GET /chapters/{cid}/snapshots/{sid}는 해당 회차의 원문 포함 상세.
- POST /chapters/{cid}/restore {snapshot_id, expected_revision}: 같은 회차 snapshot만 허용하고 공통 서비스로 복원한다. 현재 원문도 먼저 보관하므로 복구를 다시 되돌릴 수 있다. 응답 ChapterDetail.
- 최소 UI: 기존 에디터에 복구본 목록→원문 확인→명시적 복구. 자동 적용 금지. 현재 unsaved draft는 서버 반영을 마친 다음 복구하거나 충돌/오류로 중단한다.
- 삭제 휴지통, 장면별 revision, 자동 백업 스케줄러는 제외한다. 회차 삭제 시 관련 snapshot cascade 정책을 명시하고 테스트한다. snapshot은 DB 백업을 대체하지 않는다.

## 3. 윤문·장면 합치기
- 윤문 시작 전 편집기 저장을 완료한다. POST /refine도 expected_revision을 필수로 받으며, 서버 버전 불일치는 pipeline을 실행하기 전에 409로 거부한다. RefineRun.base_revision(nullable legacy)는 입력 원문을 캡처한 순간의 revision이다. input_content_md와 base_revision을 pipeline 이전에 함께 캡처해 실행 입력·report·응답에 동일하게 사용한다. pipeline 이후 다시 읽은 원문을 base로 잘못 기록하지 않는다.
- 수락 API는 run.base_revision으로 공통 저장을 호출한다. 결과가 만들어진 후 원문이 바뀌었으면 409, accepted=false, 원문 보존. legacy base_revision=null인 기록은 재실행 안내와 함께 수락 차단한다. 응답은 ChapterDetail로 통일한다.
- 장면 조립 PUT은 {expected_revision} 필수. 장면이 없거나 합친 본문이 비어 있으면 422로 현재 원고를 보존한다. 같은 회차 장면만 sort_order,id 순으로 합친다. 조립 전에 현재 draft 저장을 완료하고 현재 본문이 교체됨을 확인받는다.
- 장면 관리 열기 버튼은 닫힌 Dialog 바깥에 둬 실제 접근 가능하게 한다. 그 밖의 unrelated CRUD는 변경하지 않는다.

## 4. 클라이언트 저장 모델
- 편집 draft/저장 상태/서버 revision/요청 중 원문은 (project_id, chapter_id) 별로 소유한다. 라우트 변경은 기존 draft를 saved로 초기화하지 않는다.
- 각 회차 저장 요청은 최대 하나만 진행한다. 입력 때 로컬 edit sequence를 증가시키며 저장 중 입력도 dirty다. 성공 응답은 보낸 sequence까지만 인정하고 새 입력이 있으면 최신 버전으로 다음 요청을 보낸다.
- 기본 debounce 1500ms 유지. Ctrl+S 및 화면 작업 전 flush는 최신 입력이 서버에 반영되거나 명확한 오류가 날 때까지 처리한다. 컴포넌트 unmount와 무관하게 저장 큐가 유지된다.
- 성공 시 detail/list 캐시를 해당 회차의 응답으로 갱신한다. editor 및 preview는 unsaved draft를 우선 사용하고 캐시 refetch가 최신 입력을 덮지 않는다. 회차별 word count/상태 표시를 유지한다.
- 작품 이동 시 선택 회차의 소속을 확인하고 잘못된 선택을 초기화한다. 이전 회차 데이터가 새 URL에서 표시되지 않게 응답 project_id도 검사한다.
- 로컬 복구본은 원고+base revision+project/chapter id+edit sequence를 browser storage에 보관한다(키 접두사 jippeel:manuscript-draft:v1:). 모든 사용자 입력에서 debounce/flush 예약 전에 최신 draft 기록을 시도한다. 저장 성공/유실 응답 확인이 같은 sent sequence에 해당할 때만 그 draft를 clean으로 표시하거나 삭제한다. 성공 응답 뒤 더 새 입력이 있으면 새 서버 base revision과 최신 draft를 유지해 기록하며 지우지 않는다. storage 오류/용량 초과로 편집기를 멈추거나 서버 저장을 막지 않으며 복구 보장 범위 밖임을 표시한다. 복구본을 서버 저장됨으로 표시하지 않는다.
- 재접속 시 현재 서버 원고를 조회한다. base revision이 같으면 draft를 복구해 저장할 수 있다. 다르면 로컬/서버 원고를 보존한 채 비교와 복사 안내를 제공하고 자동 덮어쓰기는 금지한다.
- lib/api.ts의 ApiError는 HTTP status, 한국어 message, 서버 detail 객체(code/current_revision 포함)를 보존한다. 409/네트워크 오류는 draft를 남기고 한국어로 알린다. 단순 최신 revision으로 바꿔 강제 재시도하지 않는다. 응답 유실 시 GET으로 저장 결과를 확인하고 content_md === sentText인 경우에만 서버 revision을 조정한다. 다르면 dirty/conflict와 로컬 본문을 유지한다.
- pagehide keepalive는 best effort이며 주 보존 수단으로 삼지 않는다. pending 큐와 경합하는 버전 미지정 요청을 보내지 않는다. 저장되지 않은 상태의 정상 이탈에는 beforeunload 경고를 사용한다. 큰 원고나 네트워크 차단의 복구는 browser storage 기록 범위로 제한한다.

## 5. 테스트·마이그레이션·적용
1. 기존 201개 backend 테스트 baseline을 임시 lifespan DB로 실행: 201 passed, 1 기존 경고.
2. API: version 필수·정상 저장·stale 409·같은 revision 동시 요청 중 한 개만 성공·no-op·snapshot 원문·복구 소속·복구 후 되돌림·빈 장면 합치기·stale/legacy 윤문·POST 별칭·삭제 cascade.
3. 프론트: 1500ms 전 회차 전환, 응답 지연 중 추가 입력, 연속 Ctrl+S, 회차/작품 이동, 저장 후 preview/reopen, refetch 중 입력, 409/네트워크 실패, reload 복구, storage 실패, 윤문 중 수정, 장면 합치기 후 복구.
4. 브라우저 fixture 테스트와 임시 backend 통합 테스트를 구분한다. 마지막 검증은 전용 포트에서 새 앱/임시 DB로 실제 PUT·refine stub·snapshot restore를 수행한다. 실제 LLM 품질 테스트가 아니다.
5. Alembic: 새 DB, 기존 head에 모든 관련 데이터가 있는 DB의 upgrade와 보존, 과거 nullable-volume 변경을 포함한 데이터 있는 구버전 upgrade를 시험한다. 기존 migrations의 데이터 FK 문제는 재현 테스트를 먼저 쓰고 필요한 최소 변경만 한다.
6. 운영 DB 자동 upgrade/stamp 금지. 일반 시작은 create_all/seed/FTS 작업 전에 schema/Alembic guard로 chapters.revision, chapter_snapshots, refine_runs.base_revision, 필수 unique/index 및 올바른 Alembic head를 확인한다. 불일치 시 어떤 테이블도 추가하지 말고 명확한 upgrade 안내로 실패한다. 빈 운영 DB도 명시적 alembic upgrade로 준비한다. create_all 허용은 명시적으로 지정한 임시 테스트 초기화에만 한정한다. 운영 적용 전 백업·복제 DB upgrade·검증·동시 서비스 중지·백엔드/프론트 동시 교체 절차를 문서화한다.
7. 별도 reviewer가 실제 diff와 관련 테스트를 확인한다. 기술적 보존 시험을 소설 품질 상승의 증거로 주장하지 않는다.
