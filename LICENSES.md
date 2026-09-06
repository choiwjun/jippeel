# LICENSES.md — 오픈소스 라이선스 고지 (F-036)

jippeel은 아래 오픈소스 소프트웨어를 사용합니다.
본 문서는 앱 설정(설정 > 규정·현황 > 라이선스 및 출처)에 표시되는 내용의 정본입니다.

검증 기준일: 2026-08-26
- Frontend: `frontend/package.json` 및 설치된 `node_modules/*/package.json`의 license 필드 실측
- Backend: `backend/requirements.txt` 직접 의존성 및 `.venv` dist-info METADATA / LICENSE 파일 실측

---

## im-not-ai (Humanize KR) 스킬

| 항목 | 내용 |
|---|---|
| 용도 | 한글 AI 윤문 오케스트레이션 (윤문 기능, NFR-401 · im-not-ai 4대 철칙) |
| 라이선스 | **MIT** |
| 출처 | <https://github.com/epoko77-ai/im-not-ai> (imnotai.kr) |
| 평가 문서 | `부록04_im-not-ai_평가.md` |

MIT License 전문: <https://opensource.org/licenses/MIT>

---

## 주요 의존성 라이선스 요약

### Frontend (`frontend/package.json` 기준)

| 패키지 | 버전 계열 | 라이선스 |
|---|---|---|
| react / react-dom | ^18.3.1 | MIT |
| react-router-dom | ^6.28.1 | MIT |
| @tanstack/react-query | ^5.62.11 | MIT |
| zustand | ^5.0.2 | MIT |
| @codemirror/state, /language, /view, /lang-markdown | ^6.x | MIT |
| markdown-it | ^14.1.0 | MIT |
| diff (jsdiff) | ^7.0.0 | BSD-3-Clause |
| dompurify | ^3.2.3 | MPL-2.0 OR Apache-2.0 |
| Vite (dev) | ^5.4.11 | MIT |
| TypeScript (dev) | ^5.6.3 | Apache-2.0 |
| Tailwind CSS (dev) | ^3.4.17 | MIT |

기타 dev 도구(@vitejs/plugin-react, postcss, autoprefixer)는 모두 MIT로 확인됨.

### Backend (`backend/requirements.txt` 직접 의존성 기준)

| 패키지 | 버전 (설치 실측) | 라이선스 |
|---|---|---|
| fastapi | 0.141.1 | MIT |
| sqlalchemy | 2.0.52 | MIT |
| alembic | 1.19.1 | MIT |
| pydantic / pydantic-settings | 2.13.4 / 2.15.0 | MIT |
| uvicorn[standard] | 0.52.4 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| pytest (dev/test) | 9.1.1 | MIT |
| cryptography (전이 의존성) | 50.0.0 | Apache-2.0 OR BSD-3-Clause (dual — LICENSE.APACHE / LICENSE.BSD 선택 적용) |

---

## 라이선스 전문 링크

- MIT: <https://opensource.org/licenses/MIT>
- BSD-3-Clause: <https://opensource.org/license/bsd-3-clause>
- Apache-2.0: <https://www.apache.org/licenses/LICENSE-2.0>
- MPL-2.0: <https://www.mozilla.org/en-US/MPL/2.0/>
- BSD-2-Clause: <https://opensource.org/license/bsd-2-clause>

> 각 패키지의 정확한 라이선스 조건은 해당 패키지 배포본에 동봉된 LICENSE 파일이 정본입니다.
> 본 목록은 확신할 수 없는 항목을 제외하고 실측으로 확인된 것만 기재했습니다.

---

*작성: team-frontend / F-036 릴리스 차단 해소용 (QA_개발검증_리포트_v2.md 참조). traceability.json 병합은 Master가 수행.*
