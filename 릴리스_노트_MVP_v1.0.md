# 릴리스 노트 — jippeel 웹소설 AI 집필 대시보드 MVP v1.0

- **일자**: 2026-08-26
- **게이트**: G0~G8 전체 통과 (규약 v1 준수, trace-gate 판정)
- **품질 증거**: backend pytest 118 passed / frontend build 통과 / API 라이브 스모크 8/8 / security 자동 4종 PASS (QA_개발검증_리포트_v2.md)

## 포함 기능
M1 에디터(마크다운·자동저장·글자수 3종 카운트) / M2 캐릭터 / M3 로어북(FTS5 검색) /
M4 AI 패널(모델 무관 OpenAI 호환, SSE 스트리밍) / M5 윤문(im-not-ai 연동, 변경률 게이트 30/50%) /
S7 설정(api_key DPAPI+Fernet 암호화, 라이선스 고지)

## Known Issues / 보류
1. UI e2e·a11y 자동 스캔: chromium 시스템 라이브러리 부재로 미실행(Infra팀 install-deps 후 재실행 필요)
2. 실기기 항목 보류: Windows keyring(DPAPI) 실측(TC-302), NVDA 스크린리더(TC-503~505), 노벨피아 글자수 실측(C8 — 현재 추정식 \p{L}\p{N} 적용)
3. 백로그: F-011 카드 JSON 편집, F-016 참조 회차, F-030 임계값 UI, F-034 자동 백업
4. 경미: TC-110 응답 스키마(has_api_key) 플랜과 상이

## 라이선스 준수
LICENSES.md 참조 — im-not-ai(MIT) 고지 포함, 19개 패키지 그룹 실측 확인.
