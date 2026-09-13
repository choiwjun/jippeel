# `oh-story-claudecode` 통합 검토

> 검토일: 2026-09-07
> 대상: https://github.com/zenstory-ai/oh-story-claudecode
> 확인 기준: 원격 저장소 HEAD `5de060f9a47e7c4781c81edb320436b772e2955e` (`release: 0.7.9`, 2026-08-30)

## 결론

**전체 패키지를 jippeel에 그대로 추가하는 것은 보류한다.**

다만 `story-long-write`의 장편 집필 절차와 `story-review`의 구조·인물·일관성 점검 방법론은 **한국어·문피아/노벨피아 기준으로 개조한 선택형 보조 스킬**로 가져올 가치가 있다. jippeel의 FastAPI/SQLite 기능을 대체하거나 직접 연결하는 패키지는 아니다.

## 확인된 내용

| 항목 | 확인 결과 | 출처 |
|---|---|---|
| 범위 | 13개 스킬, 7개 custom agent, setup/hook 배포 체계 | 외부 `README.md`, `skills/story-setup/SKILL.md` |
| 핵심 기능 | 장편·단편 집필, 대중소설 분석·스캔, 리뷰, 파일 기반 추적, 표지, 브라우저 CDP | 외부 `README.md`, `skills/*/SKILL.md` |
| 언어·플랫폼 | 프롬프트와 rubric이 중국어 중심이며 番茄·起点·知乎·晋江 기준 포함 | 외부 `README.md`, `skills/story-review/SKILL.md`, `skills/story-long-scan/SKILL.md` |
| 저장 구조 | `正文/`, `大纲/`, `设定/`, `追踪/` Markdown 파일 구조 | 외부 `skills/story-long-write/SKILL.md` |
| 라이선스 | MIT. 복사·수정 시 저작권/라이선스 고지 유지 필요 | 외부 `LICENSE` |
| 패키지 의존성 | `package.json`의 개발 의존성은 Playwright. `browser-cdp`는 별도 `agent-browser` 설치를 요구 | 외부 `package.json`, `skills/browser-cdp/SKILL.md` |

## jippeel과의 중복·충돌

1. **집필 기능 중복**: jippeel은 `backend/app/routers/ai_panel.py`, `backend/app/services/canon.py`, `backend/app/services/quality.py`, `frontend/src/components/panels/AiPanel.tsx`에 회차 생성, 컨텍스트 주입, 감수, canon 검사, 품질 진단을 이미 구현했다. **판단**: 외부 `story-long-write`를 그대로 넣는 것만으로 생성 품질이 자동 향상된다는 근거는 없다.
2. **저장 원본 충돌 위험**: 외부 `skills/story-long-write/SKILL.md`는 `正文/`·`大纲/`·`设定/`·`追踪/` 아래 Markdown 파일을 사용하고, jippeel은 `backend/app/database.py`와 웹 대시보드를 중심으로 한다. **판단**: 양쪽을 동시에 권위 원본으로 쓰면 내용과 상태가 갈라질 수 있다.
3. **언어·플랫폼 적용 위험**: 외부 스킬의 프롬프트와 rubric에는 중국어 및 番茄·起点·知乎·晋江 기준이 있다. **판단**: 이를 한국어 프로젝트에 그대로 적용하면 문체와 목표 플랫폼 기준이 어긋날 수 있다.
4. **운영 설정 충돌 위험**: 외부 `skills/story-setup/SKILL.md`는 `AGENTS.md`, `.agents/`, `.claude/`, `.codex/` 등의 agents/hooks/skills를 프로젝트에 배포한다. 현재 jippeel의 자체 `AGENTS.md`와 별도 FastAPI 실행 구조를 고려하면, **판단**: 전체 setup을 바로 실행할 경우 설정 충돌과 관리 부담이 생길 수 있다.

## 가져올 가치가 있는 부분

- 장편의 대강·권별 개요·세부 개요·추적 상태를 연결하는 집필 절차
- 구조·인물·문체·설정·플랫폼 관점의 다중 리뷰 rubric
- 작성 전 reference gate와 작성 후 결정적 점검 개념
- 작가 습관과 작품별 상태를 분리하는 방식

이 부분은 외부 파일 구조를 그대로 도입하기보다, jippeel의 `Project`, `Chapter`, `Scene`, `Foreshadow`, `style_profile`과 현재 AI 패널에 맞춰 프롬프트·점검 항목으로 변환하는 것이 적합하다.

## 도입하지 않을 범위

- `browser-cdp`: 기존 로그인 세션 재사용과 auth token 추출 기능이 있어 제품 기본 기능으로 넣지 않는다. 외부 저장소도 첫 Chrome 시작 시 기존 Chrome을 종료할 수 있다고 명시한다 (`skills/browser-cdp/SKILL.md`).
- `story-long-scan`/`story-short-scan`: 플랫폼별 수집기와 브라우저 상태 의존성이 있어 jippeel의 핵심 생성 경로에 넣지 않는다.
- `story-deslop`: 외부 스킬은 자연스러운 문장 윤문으로 설명되지만, jippeel은 `대시보드_MVP_사양.md`의 영구 제외 원칙에 따라 AI 탐지 회피 기능을 넣지 않는다. 따라서 전체 skill을 그대로 통합하지 않고, 필요한 문체 개선은 기존 품질/윤문 흐름에서 처리한다.
- `story-setup`과 전체 hooks/agents 배포: 현재 프로젝트 설정을 덮거나 두 개의 작업 원본을 만들 수 있으므로 바로 실행하지 않는다.

## 권장 최소안

1. 외부 저장소 전체를 jippeel 런타임이나 백엔드에 복사하지 않는다.
2. 필요할 때만 `story-long-write`·`story-review`의 방법론을 읽어 한국어 프로젝트용 보조 프롬프트로 재작성한다.
3. 작품 데이터의 권위 원본은 계속 jippeel SQLite로 유지한다.
4. 적용 전 대표적인 한국어 샘플로 기존 생성 결과와 비교 평가한다. 샘플 수와 평가 기준은 실제 대상 장르·플랫폼을 정한 뒤 별도로 결정한다.
5. MIT `LICENSE` 고지를 유지한다.

**최종 판단: `선택적 방법론 흡수 권장 / 전체 패키지 직접 추가는 비권장`.**

## 출처

- 저장소: <https://github.com/zenstory-ai/oh-story-claudecode>
- README: <https://github.com/zenstory-ai/oh-story-claudecode/blob/5de060f9a47e7c4781c81edb320436b772e2955e/README.md>
- 라이선스: <https://github.com/zenstory-ai/oh-story-claudecode/blob/5de060f9a47e7c4781c81edb320436b772e2955e/LICENSE>
- 집필 스킬: <https://github.com/zenstory-ai/oh-story-claudecode/blob/5de060f9a47e7c4781c81edb320436b772e2955e/skills/story-long-write/SKILL.md>
- 리뷰 스킬: <https://github.com/zenstory-ai/oh-story-claudecode/blob/5de060f9a47e7c4781c81edb320436b772e2955e/skills/story-review/SKILL.md>
- 브라우저 CDP 스킬: <https://github.com/zenstory-ai/oh-story-claudecode/blob/5de060f9a47e7c4781c81edb320436b772e2955e/skills/browser-cdp/SKILL.md>
- jippeel AI 생성 경로: `backend/app/routers/ai_panel.py`, `backend/app/services/canon.py`, `backend/app/services/quality.py`
- jippeel 범위·제외 원칙: `대시보드_MVP_사양.md` §7~§8
