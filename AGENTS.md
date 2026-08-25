# AGENTS.md — 작업별 에이전트·모델 라우팅 규칙

> 이 프로젝트(웹소설 AI 집필 대시보드)에서 작업을 시작하기 전 아래 라우팅 규칙을 따른다.
> 모든 CLI 작업은 `prime-agent`(v0.8+)를 통해 실행하며, 기본 provider는 `opencode-go`이다.

---

## 0. 표준 파이프라인 (팀·단계 순서)

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
*최종 갱신: 2026-08-25*
