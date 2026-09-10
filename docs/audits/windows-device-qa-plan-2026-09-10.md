# Windows 실기기 QA 계획

- 작성일: 2026-09-10
- 상태: **계획만 작성. Windows 장치와 운영 서비스는 조작하지 않음.**

## 전제와 안전 범위

현재 세션은 WSL/Linux 작업 환경이다. 실제 Windows 장치, 사용자 profile, DPAPI/keyring, 기존 포트의 서비스 상태를 이 세션에서 주장하지 않는다.

실기기 QA는 사용자가 지정한 장치와 시간에만 수행한다.

- 기존 `:8000`, `:5173` 서비스는 종료하지 않는다.
- 테스트용 DB와 테스트용 key만 사용한다.
- 원본 `jippeel.db`와 사용자 keyring을 백업 없이 건드리지 않는다.
- 실제 provider/API key 호출은 하지 않는다.
- 모든 결과는 캡처, 명령, OS/Python/Node 버전, 포트, commit SHA와 함께 기록한다.

기존 기준: `QA_수동검증_가이드.md`, `Jippeel실행.bat`, `scripts/prod.sh`, `scripts/dev.sh`.

## 사전 조건

- Windows 버전/장치 이름/사용자 profile과 테스트 승인
- WSL 배포판과 mount path가 `Jippeel실행.bat`의 경로와 일치
- `backend\.venv\Scripts\python.exe`, Node/npm, frontend dependencies, Alembic DB 준비
- 테스트용 temp DB와 별도 `JIPPEEL_KEY_FILE` 또는 테스트 keyring
- 사용 가능한 test ports; 기존 8000/5173 점유 현황 캡처
- 브라우저, PowerShell, NVDA(접근성 범위인 경우) 준비

## 테스트 매트릭스

| ID | 범위 | 절차 | PASS 기준 | 증거 |
|---|---|---|---|---|
| WIN-01 | batch/path/encoding | `Jippeel실행.bat`을 먼저 읽기 전용 점검하고 지정 경로에서 실행 | 한글 OneDrive 경로를 깨뜨리지 않고 로그가 생성됨 | batch output, path, commit |
| WIN-02 | backend startup | temp DB + 전용 port로 `uvicorn` 기동, `/health` 확인 | schema gate 통과, health 200, 기존 포트 무변경 | command, port list, health |
| WIN-03 | frontend build/serve | Windows `npm run build`, dist serve | `tsc`/Vite exit 0, assets 로드, Unicode 경로 정상 | build log, browser screenshot |
| WIN-04 | DPAPI/keyring | 테스트 key encrypt/decrypt와 temp SQLite byte scan | plaintext 미노출, round-trip 성공, DPAPI/keyring 경로 확인 | PowerShell output, DB hash |
| WIN-05 | Unicode/line endings | 한글 작품·회차·본문·파일 경로 저장/재조회 | UTF-8 본문, 제목, JSON, log가 동일 | before/after hashes, API response |
| WIN-06 | port coexistence | 기존 점유 포트가 있을 때 start script 실행 | 기존 서비스 종료/덮어쓰기 없이 명확히 실패 또는 다른 test port 사용 | `netstat`/`ss`, logs |
| WIN-07 | manuscript preservation | temp DB에서 content save, stale revision, restore snapshot | 409 stale, snapshot 생성, 복원 후 revision/hash 일치 | API output, DB inspection |
| WIN-08 | performance | 50k-char editor typing와 lore search를 가이드대로 3회 측정 | 기존 기준(<100ms typing, <1s search)을 기록하고 worst case 판정 | DevTools trace, timings |
| WIN-09 | accessibility | NVDA checklist, keyboard/zoom 125% | 조작 불가·정보 누락 0, focus/alert/stream semantics 기록 | screen recording, checklist |
| WIN-10 | rollback | 테스트 프로세스/임시 파일 정리 | 기존 서비스·DB·keyring 불변, test process/ports 0 | before/after process and port list |

`WIN-04`, `WIN-07`은 운영 DB나 실제 API key를 사용하지 않는다. `WIN-08`, `WIN-09`는 기존 가이드의 수동 측정 항목을 대체하지 않고 evidence를 보강한다.

## 실행 순서

1. 장치/경로/포트/commit과 기존 process snapshot을 저장한다.
2. 테스트용 DB/key/포트로 WIN-01~07을 수행한다.
3. build와 browser surface를 확인한다.
4. 성능·접근성 측정을 별도로 수행한다.
5. 종료 전 process/port/파일 diff를 재수집한다.
6. 실패한 항목은 PASS로 낮추지 말고 blocker/재현 명령/rollback 상태를 기록한다.

## 결과물

- `windows-qa-<date>.md`: 각 TC, 측정값, 판정, blocker
- 명령 로그와 환경 버전
- 화면/접근성/성능 evidence
- temp DB/key의 생성·삭제 기록(키 값 제외)
- before/after process, port, file hash
- rollback 확인

## 정적 사전 점검 결과

WSL에서 `bash -n scripts/prod.sh scripts/dev.sh`를 먼저 실행했다. 두 스크립트가 CRLF였기 때문에 Bash가 line 25 부근에서 실패했다. WSL에서 `Jippeel실행.bat`이 이 스크립트를 호출하므로 실행 경로의 실제 결함으로 판정했다. 두 `.sh` 파일의 줄바꿈을 LF로 정규화한 뒤 같은 명령이 통과했고, batch 파일·frontend package·backend requirements 존재도 확인했다. 실제 Windows 장치에서의 실행/DPAPI/브라우저/NVDA 검증은 아직 하지 않았다.

## 현재 blocker

Windows 장치 지정, 테스트 시간, 사용 가능한 별도 port, 실제 test DB/keyring이 아직 없다. 이 정보 없이 실기기 QA를 실행하거나 `Jippeel실행.bat`을 더블클릭하지 않는다.
