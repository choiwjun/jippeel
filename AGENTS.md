# AGENTS.md — 현재 작업 규칙

## 현재 실행 환경 — 2026-09-12 사용자 정정

- **prime-agent는 사용하지 않는다.** 설치·실행·별도 예외 승인을 작업의 선행 조건으로 요구하지 않는다.
- 현재 Pi 세션의 도구로 작업한다. 필요한 위임은 Pi의 사용 가능한 subagent와 현재 설정을 사용한다.
- 아래 prime-agent 전용 provider/model 플래그와 세션 명령은 과거 기록이며 현재 라우팅을 강제하지 않는다.
  사용자가 지정하지 않은 모델·provider를 설치하거나 전역 설정을 바꾸지 않는다.
- 작업 상태는 [전체 작업 현황](docs/handoffs/2026-09-08-remaining-work.md), 문서 탐색은
  [문서 상태 인덱스](docs/DOCUMENT_STATUS.md), 승인·실행 이력은 [HANDOFF.md](HANDOFF.md)를 확인한다.
- 요구사항 → 조사 → 기획 → 필요한 디자인 → 개발 → QA 순서와 단계 산출물·승인 원칙은 유지한다.
  이미 승인·완료된 범위를 다시 열지 않으며, 버그 수정은 재현 → 최소 수정 → 회귀 검증·독립 검토로 진행한다.
- 같은 worktree에는 writer 한 명만 둔다. 기존 dirty 변경·미추적 자료를 보존한다.
- 테스트는 합성 TEMP DB·fake provider·전용 포트로 격리한다. 운영 DB·실제 provider/비용·credential·
  지정 실기기·migration/배포 및 commit/stage/push는 별도 승인 경계를 유지한다.
- 이 변경은 개발 도구 선택에 관한 정정이다. 앱의 고정 GPT OAuth provider 계약을 바꾸지 않는다.

## 과거 라우팅 기록 — 사용 중지

다음은 2026-08-25 당시 기록이다. prime-agent 관련 명령·기본 모델·실행 방식은 현재 지시가 아니며,
이 기록 때문에 작업을 중단하거나 prime-agent 사용 승인을 다시 요청하지 않는다.

---

## 0. 표준 파이프라인 (과거 팀·모델 배정)

작업은 반드시 아래 순서로 진행한다. 각 단계의 산출물은 프로젝트 폴더의 md 파일로 남기고, 승인 후 다음 단계로 넘어간다.

| 순서 | 팀 | 담당 모델 | 산출물 |
|------|-----|-----------|--------|
| 1. **요구사항 분석** | 요구사항팀 | `ox-alpha-free` | 요구사항 목록, 범위 정의 |
| 2. **리서치** | 리서치팀 | `ox-alpha-free` | 조사·검증 보고서 (부록 시리즈) |
| 3. **기획** | 기획팀 | `ox-alpha-free` | 사양 문서 (`대시보드_MVP_사양.md`) |
| 4. **디자인** | 디자인팀 | MiniMax M3 | 와이어프레임·UI 컴포넌트 시안 |
| 5. **개발** | 개발팀 | `ox-alpha-free` | FastAPI 백엔드 + 프론트 구현 |
| 6. **QA** | QA팀 | `ox-alpha-free` | 테스트 코드, 검증 리포트 |

---

## 1. 모델 라우팅 매트릭스

| 작업 유형 | 모델 | 실행 명령 |
|-----------|------|-----------|
| **프론트엔드 디자인** (UI/UX, 화면 구성, 스타일링, 컴포넌트 시안) | MiniMax M3 (`minimax` 프로바이더) | `prime-agent --provider minimax --model MiniMaxAI/MiniMax-M3 "<작업 지시>"` |
| **백엔드** (FastAPI, DB, API 설계·구현) | `ox-alpha-free` | `prime-agent "<작업 지시>"` |
| **QA** (테스트 코드, 검증, 버그 재현) | `ox-alpha-free` | `prime-agent "<작업 지시>"` |
| **리서치** (조사, 사실 확인, 비교 분석) | `ox-alpha-free` | `prime-agent "<작업 지시>"` |
| **요구사항 정리** (사양 문서화, 핸드오프, 회의 정리) | `ox-alpha-free` | `prime-agent "<작업 지시>"` |

- `ox-alpha-free`는 prime-agent의 **기본 모델**이므로 별도 플래그 없이 실행하면 된다.
- 프론트엔드 디자인은 `~/.prime/agent/extensions/minimax/index.ts`로 등록된 **확장 프로바이더**(`--provider minimax`)를 사용한다.
- ⚠️ 주의: opencode-go 쪽의 `minimax-m3` 모델(`--model minimax-m3`)은 API 키가 없어 인증 오류가 난다. 반드시 위 명령처럼 `minimax` 프로바이더를 지정할 것.

## 2. 실행 예시

```bash
# 프론트엔드: 원고/회차 에디터 UI 디자인
prime-agent --provider minimax --model MiniMaxAI/MiniMax-M3 "회차 에디터 화면 컴포넌트 설계해줘"

# 백엔드: 캐릭터 관리 API 구현
prime-agent "캐릭터 카드 CRUD API를 FastAPI로 구현해줘"

# 리서치: 플랫폼 규정 추적
prime-agent "문피아·노벨피아 AI 규정 최신 공지 확인해줘"

# QA: API 테스트
prime-agent "캐릭터 API 통합 테스트 작성하고 실행해줘"
```

## 3. 세션 운영 규칙

1. **세션 분리**: 프론트엔드(minimax)와 백엔드(ox-alpha) 작업은 별도 세션으로 진행한다. 필요 시 `-c`(continue)/`-r`(resume)로 각 세션을 이어간다.
2. **결과물 공유**: 한쪽 세션의 산출물(설계, API 스펙 등)은 프로젝트 폴더의 md 파일로 저장해 다른 세션이 읽을 수 있게 한다.
3. **핸드오프**: 작업 전환 시 `HANDOFF.md`를 최신 상태로 갱신한다.
4. **장기 자동화**: 반복 작업이나 게이트 검증이 필요하면 `--autonomous` 옵션 활용:
   ```bash
   prime-agent --provider minimax --model MiniMaxAI/MiniMax-M3 --autonomous --autonomous-gate "npm run build" "<지시>"
   ```

---
과거 라우팅 작성: 2026-08-25 / prime-agent 사용 중지 및 현재 규칙 정정: 2026-09-12
