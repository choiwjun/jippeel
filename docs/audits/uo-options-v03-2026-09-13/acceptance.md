# U01~U04·O01~O03·O05·V03 수용 — 선택 UI·확장·정리·부하 검증

- 수용일: 2026-09-13
- 승인 근거: 사용자 전체 위임 “나대신 승인하고 남은거 다 작업해”
- 상태: **수용** (uncommitted)

## U01 — 캐릭터 card_json 자유 확장 UI ✅

`CharactersPage`에 `CardJsonSection` 추가 — 기존 `PATCH /characters/{id}/card_json`(merge-patch) 재사용. JSON 편집·검증·저장, 관계 UI·fixture 패턴 보존. fixture `characters-card-json` 5/5, tsc exit0.

## U02 — 로어 참조 회차 표시 ✅

- backend: `GET /api/v1/lore/{lid}/referencing-chapters` — 기존 `score_entries` 매칭 로직 재사용, 프로젝트 스코핑·sort_order 정렬. 집중 **17 passed**.
- frontend: 로어 상세 Sheet에 접이식 `ReferencingChaptersSection`(토글 버튼 패턴). fixture `lore-referencing` 4/4.

## U03 — 윤문 명령 프리셋 — 이미 충족으로 기록 ✅

조사 결과 기능 코어가 선존: `prompt_presets` CRUD + Settings UI + AiPanel 프리셋 선택기 → `preset_id` 왕복. humanize 경로는 고정 OAuth 계약상 `force_route` 3종만 존재해 추가 프리셋층은 중복이며 임의 shell 실행 UI는 금지 정책. **중복 구현하지 않고 "이미 충족"으로 종결.**

## U04 — 시니어 확대 모드 ✅

- `settingsStore.uiScale`(normal/large=115%/xlarge=130%) 영속, main.tsx 초기화 시 documentElement에 적용, index.css 스케일 규칙, Settings UI 라디오.
- 에디터 typography compartment 추가 — 선존 갭이던 `fontFamily`/`lineHeight` 설정을 실제 CodeMirror에 동적 적용(기존 하드코딩 제거).
- fixture `ui-scale` 3/3(기본값·즉시 적용·리로드 영속·리셋), preservation 회귀 26/26, tsc exit0.

## O01 — SillyTavern 카드 PNG + novelWriter import ✅

사양: `docs/specs/2026-09-13-o01-card-png-novelwriter-import.md`.
- `services/card_png.py` — ST V2 카드 PNG export(tEXt 청크)/import, `characters.card_json` 저장.
- `services/novelwriter_import.py` — novelWriter ZIP/nwx 파싱 → 순서 보장 회차 생성. type/layout은 자식 요소·속성 양식 모두 허용, malformed/비지원 입력 안전 거부.
- RFC 5987 `filename*=utf-8''` 다운로드 파일명(한글 이름 latin-1 오류 수정), `python-multipart>=0.0.9` requirements 추가.
- 집중 **16 passed**.

## O02 — 자동 주기 백업 ✅

사양: `docs/specs/2026-09-13-o02-auto-backup.md`.
- `services/auto_backup.py` — `JIPPEEL_AUTOBACKUP_INTERVAL_MIN` 미설정 시 스케줄러 미기동(opt-in). 기존 `create_backup()` 계약 재사용, 타임스탬프 디렉터리(충돌 시 suffix)·보존 개수 프루닝·shutdown 시 정상 종료.
- `main.py` lifespan 연결 — 비활성 시 기동 영향 없음. 백업 DB 파일명 `database.sqlite3`.
- 집중 **11 passed**.

## O03 — 집필 활동 캘린더 ✅

사양: `docs/specs/2026-09-13-o03-writing-activity.md`.
- `GET /api/v1/projects/{pid}/writing-activity?days=N` — `updated_at` 일자 그룹핑, 윈도우 경계 밖 제외, 프로젝트 스코핑. 멀티 작품 합계는 기존 프로젝트 목록이 제공하므로 얇은 슬라이스는 캘린더 엔드포인트.
- 집중 **5 passed**.

## O05 — ResourceWarning 정리 ✅

전체 스위트의 **19건 ResourceWarning(미폐쇄 sqlite3 연결) 근본 원인을 수정**했다.

- **근본 원인(앱 코드):** `assert_manuscript_schema_current()`의 `inspect(bind)` — SQLAlchemy transient `Inspector`가 첫 introspection 시 체크아웃한 연결을 `close()` 없이 유지. TestClient lifespan마다 `init_db` 호출 → 테스트당 1연결 누수. `with bind.connect() as conn: inspect(conn)` 스코프로 수정 — 검사 로직 전체(chapters·refine_runs·snapshots·goals·flow_events·projects serial/ending·evidence·foreshadow·final_editions·summary_jobs·alembic head)를 동일 `with` 안에 보존.
- **테스트 측:** `test_migrations.py`의 13개 `inspect(engine)` → `_inspect()` 헬퍼(연결 레지스트리 폐기); conftest `_dispose_app_engine` autouse; `_db` 제너레이터 미폐쇄 수정(`_db_gens` 레지스트리)·인라인 `next()` 사용처 `closing()` 래핑.
- 진단용 leak probe(세션 훅·연결 트레이스)는 근본 원인 수정 후 **전부 제거** — 최종 잔여물 없음.
- 결과: **714 passed / 1 skipped / warnings 0**(이전 19 warnings).

부산물: 격리 러너의 `/tmp/jippeel-isolated-*` 누적(~99MB×131)으로 tmpfs 포화 사례 발견 — 정리로 3.2GB 회수, 반복 실행 시 모니터링 필요.

## V03 — 다중 프로세스 SQLite 부하 ✅

`scripts/sqlite_multiprocess_check.py` — 앱과 동일 pragma(WAL·synchronous=NORMAL·busy_timeout=5000·FK)로 spawn 컨텍스트 다중 OS 프로세스가 같은 DB 파일에 `BEGIN IMMEDIATE` 쓰기 반복.

- 8 workers × 50: rows=400, integrity=ok, journal=wal — PASS
- 16 workers × 100: rows=1600, busy_retries=0(5s busy_timeout이 경합 흡수), max_commit 10.9ms — PASS

주장 범위: 같은 파일에 대한 다중 프로세스 동시 쓰기가 손실·손상 없이 완료됨. 실제 HTTP 다중 프로세스 배포 구성 검증은 배포 형태 확정 시 별도.

## 최종 검증 수치

- Linux 전체: **714 passed / 1 skipped / 70 subtests / warnings 0 / violations 0**
- Windows 네이티브: **714 passed / 1 skipped / violations 0 / warnings 0**(89.67s)
- 프론트 fixture 신규: card-json 5 + lore-referencing 4 + ui-scale 3 = 12/12, 기존 스위트 회귀 유지

## 후속 실행 — 2026-09-13 심야(사용자 "남은작업모두진행해" 위임)

- **G03 실 crypto 경로 시연:** `get_cipher()` 실 폴백 파일 키(0600) 왕복·Windows 실 키로 cross-decrypt → `ValueError` wrong-key 거부·무관 키 거부·복구 경로(키 파일 보존) 확인. 증거: `g03-real-crypto-path.txt`. 잔여는 브릿지 소유 OAuth 로그아웃뿐.
- **G04 Windows 실기동 프로브:** 최신 코드를 Windows 네이티브 uvicorn으로 기동 — 실 DB 복사본(head) 대상 boot 3.79s·프로젝트/회차 읽기·**54,300자 본문 PUT 43ms**·CAS 두 번째 저장 67ms·snapshot/resume 파생 정상·옛 revision 409 거부. 증거: `g04-windows-realdevice-probe.txt` + `g04_windows_probe.py`. 잔여는 브라우저 조작·NVDA·키보드·zoom 등 대화형 실기기 수용.
- **O06 규정 재확인 완료:** `규정추적_2026-09-13.md` — 노벨피아 순수창작/이벤트 AI 금지·약관 시행 8-13 확인, 문피아 AI 신규 공지 없음(공모전 금지 유지), 조아라 명문 규정 부재 지속. 게시 전 재확인 원칙 유지.
- **D04 실제 provider 어댑터 구현:** `services/summary_provider.py` — `make_gpt_summary_provider()`가 job→메시지 조립→고정 OAuth 브릿지 `complete_chat`(xhigh)·`MAX_SOURCE_CHARS`=60k 상한·prompt_version 불일치 fail-fast. `test_summary_provider.py` 7P — fake transport로 메시지 조립·버전 거부·에러→provider_error·worker 수명주기 통합 검증. **실제 브릿지 호출 자체는 G02 게이트 유지** — 브릿지 미설치(`npx openai-oauth` 대화형 로그인 필요)를 확인.
- 최종 전체 회귀: **721 passed / 1 skipped / 70 subtests / warnings 0 / violations 0**.

## 비수용(명시 제외)

- G02 실제 OAuth/provider 수용 — `openai-oauth` 브릿지 미설치, 대화형 ChatGPT 로그인이 사용자 행동 필요. 어댑터는 준비됐으며 브릿지 기동 후 smoke 1회로 완료 가능.
- O04 신규 provider/모델 선택지·임베딩 — 고정 OAuth 계약상 우선하지 않음(정책 유지).
- 플랫폼 직접 발행 연동(O03 후반부) — O06 재확인상 이벤트/공모전 AI 금지 기조 유지로 보류 정당성 확인.
