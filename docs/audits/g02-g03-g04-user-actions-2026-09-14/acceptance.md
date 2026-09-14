# G02·G03·G04 사용자 행동 후속 실행 기록

- 실행일: 2026-09-14
- 범위: 실제 OAuth provider 최소 smoke, 브릿지 재기동 복구, NVDA 실행 및 접근성 트리 수동 확인
- 격리: TEMP SQLite, 전용 앱 포트 `18701`, OAuth bridge `127.0.0.1:10531`
- 운영 DB·원고·소스는 변경하지 않았고, credential/token 내용은 읽거나 기록하지 않았다.

## G02 — 실제 provider 최소 smoke

- `npx openai-oauth login` 실행 시 기존 OAuth 자격 파일이 존재해 덮어쓰기 여부를 물었고, 기존 자격 보존을 위해 `N`을 선택했다.
- 기존 OAuth 상태를 재사용해 bridge를 기동했다.
- TEMP DB 기반 실제 앱 `/api/v1/ai/generate`에 1회 요청했다.
- 결과: HTTP `200`, SSE `start=1`, `message=3`, `done=1`, delta 19자, error event 0.
- `max_tokens=128`, inline review 없이 최소 smoke만 실행했다.
- 판정: **최소 실제 provider smoke PASS**.
- 6-case 품질 파일럿·블라인드 평가자·USD 20 hard cap을 포함한 전체 G02 수용은 별도다.

## G03 — bridge credential 재기동 복구

- `npx openai-oauth stop` 후 동일한 기존 OAuth 상태로 bridge를 재기동했다.
- `/v1/models` HTTP `200`, 모델 6개, 고정 모델 `gpt-5.6-luna` 노출을 확인했다.
- 판정: **bridge 프로세스 재기동·credential 재사용 PASS**.
- CLI에 계정 자체 OAuth 로그아웃 명령은 없었다. 브릿지 소유 로그아웃과 지정 계정 credential 시연은 미완료다.
- bridge 동작 중 기존 로컬 auth 상태가 갱신될 수 있으나 secret 내용은 확인하지 않았다.

## G04 — NVDA 수동 확인

- `winget search --id NVAccess.NVDA --exact`로 공식 `NVAccess.NVDA` 패키지를 확인하고, `winget install`로 NVDA 2026.1.1을 설치했다. 실행 파일은 `C:\Program Files\NVDA\nvda.exe`다.
- 실제 NVDA 프로세스를 기동한 상태에서 Windows Chrome으로 TEMP DB 기반 실제 Jippeel(dist+uvicorn)에 접속했다. 운영 DB·소스·원고는 사용하지 않았다.
- Home에서 프로젝트 제목·장르·회차 수·글자 수와 `열기` 링크가 UIA 접근성 트리에 노출됐다(S1).
- Editor에서 회차 제목·원고 상태·집필 흐름 단계·재개 정보·저장 시각·편집/미리보기 탭·원고 편집 영역·글자/공백 제외 수·AI 상태가 노출됐다(S2).
- Settings에서 GPT OAuth·윤문·테마·규정·고급 탭과 다크/라이트, 폰트, 행간, 시니어 확대(보통/115%/130%) 라디오 컨트롤이 노출됐다.
- AI 패널을 실제로 열고 닫아 대화상자 제목, 자동 반영 방지 경고, OAuth 전송 경고, 고정 모델, 프롬프트/생성 옵션, 체크박스, 생성·끼워넣기·선택 교체·복사·닫기 컨트롤이 노출됨을 확인했다(S5).
- 접근성 트리 확인은 NVDA 프로세스가 실행 중인 지정 Windows 환경에서 수행했다. 이 도구 환경에서는 NVDA 음성 출력 자체를 녹음·텍스트화할 수 없고, NVDA 메뉴/포커스 이동의 직접 검증도 안정적으로 지원되지 않아 **실제 발화 문장·키보드 순환까지 PASS로 단정하지 않는다**.
- 판정: **NVDA 설치·기동 및 UIA 접근성 노출 수동 확인 PASS_WITH_NOTES**. 실제 음성 발화와 NVDA 키보드 포커스 순환은 사용자가 NVDA가 활성화된 장치에서 한 번 더 확인해야 한다.

## 정리

- 임시 앱 서버와 OAuth bridge는 실행 후 종료했다.
- 생성한 TEMP DB·임시 디렉터리는 제거했다.
- NVDA는 수동 확인 후 종료했고, 전용 앱 포트 `18702`는 더 이상 listen하지 않는다.
