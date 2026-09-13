# 수동 검증 가이드 — Windows 실기기 (TC-302·401~405·503~505·시니어 모드)

> **2026-09-12 상태 정정: 아래는 역사적 체크리스트이며 현재 실행 지침이 아니다.**
> API key 설정 UI는 제거됐고, 기본 DB/port·revision 없는 저장 명령을 그대로 실행하지 않는다.
> 현재 잔여는 [전체 현황 G04](docs/handoffs/2026-09-08-remaining-work.md), 실행 준비는
> [Windows QA 계획](docs/audits/windows-device-qa-plan-2026-09-10.md)을 따른다.
> 기존 자동화/axe 통과와 지정 장치의 NVDA·성능·DPAPI 수용은 구분한다.

---

> **작성일**: 2026-09-06 | **대상**: WSL에서 자동화할 수 없는 실기기 항목만 모음
> **선행**: `Jippeel실행.bat` 더블클릭으로 앱 구동 상태 (백엔드 :8000 / 프론트 :5173)
> 각 항목을 끝낼 때마다 아래 표에 결과를 기록하고, 실패 시 캡처와 함께 이슈화한다.

## 1. TC-302 — api_key 암호화(Windows DPAPI) 실측

**목적**: Windows 네이티브 환경에서 keyring(DPAPI) 암호화가 동작하고 저장 파일에 평문이 없는지 확인.

```powershell
# PowerShell에서 (backend 폴더 기준)
cd backend
.venv\Scripts\python -c "from app.services.crypto import get_cipher; c = get_cipher(); print(type(c).__name__); e = c.encrypt('테스트키123'); print('평문 노출:', '테스트키123'.encode() in e); print('복호화 일치:', c.decrypt(e) == '테스트키123')"
```

**판정**:
- 출력에 `DPAPI` 또는 `Keyring` 계열 클래스명 + `평문 노출: False` + `복호화 일치: True` → **PASS**
- WSL에서의 Fernet 폴백과 다른 암호화 백엔드가 나오는지 확인 (DPAPI 우선 규칙 — 사양 §8.2)

추가 실측: S7 설정에서 api_key 등록 후 SQLite 덤프에서 평문 검색:
```powershell
.venv\Scripts\python -c "import pathlib; blob = pathlib.Path('jippeel.db').read_bytes(); print('평문 노출:', '테스트키123'.encode() in blob)"
```

## 2. TC-401~405 — 성능 계측

**목적**: NFR-101 (3~5만 자 원고 타이핑 반영 <100ms), NFR-103 (검색 <1s) 실측.

### 2-1. 원고 대량 데이터 준비
```powershell
# 5만 자 테스트 회차 생성 (PowerShell)
$text = ("「비켜라.」`n`n칼끝이 목을 겨눴다. 순간, 그의 손목이 꺾였다.`n`n") * 1500
$json = @{ content_md = $text } | ConvertTo-Json
# 프로젝트 1의 회차 ID를 확인 후 (GET http://localhost:8000/api/v1/projects/1/chapters)
# Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chapters/{회차ID}/content" -Method Put -Body $json -ContentType "application/json"
```

### 2-2. 타이핑 지연 측정 (수동 — DevTools Performance)
1. 해당 회차 에디터 열기 (편집 탭)
2. F12 → Performance 탭 → 녹화 시작
3. 문장 중간에 10자 정도 타이핑 → 녹화 중지
4. 가장 느린 입력 이벤트의 처리 시간 확인 → **100ms 미만이면 PASS**
5. 반복 3회, 최악값 기록

### 2-3. 로어북 검색 시간
- S4 로어북에서 검색어 입력 → Network 탭의 `/lore/search` 응답 시간 확인 → **1초 미만 PASS** (수백 건 기준 — 로어 300건 이상일 때)

**기록 형식**:
| 항목 | 측정값 | 기준 | 판정 |
|------|--------|------|------|
| 타이핑 반영(5만 자) | ms | <100ms | |
| 로어 검색 | ms | <1s | |

## 3. TC-503~505 — NVDA 스크린리더 점검

**준비**: NVDA 설치(https://www.nvaccess.org) → Ctrl+Alt+N 시작.

**체크리스트** (읽히는 내용을 기록):
- [ ] S1 홈 — 프로젝트 카드가 "제목 + 회차 수 + 글자 수"로 읽힘
- [ ] S2 에디터 — 글자 수 푸터가 갱신 시 읽히지 않음(aria-live 최소화 확인), 저장 상태("저장됨")는 polite로 읽힘
- [ ] S5 AI 패널 — 전송 고지 Alert 먼저 읽힘, 스트리밍 중 출력이 매 토큰마다 읽히지 않음(aria-live 정책 확인)
- [ ] S6 윤문 리포트 — 변경률 게이트 상태(pass/warn/block)가 텍스트로 읽힘
- [ ] 대비 색만으로 상태를 구분하지 않는지(텍스트 병기) — StatusBadge 확인
- [ ] Esc로 Dialog/Sheet 닫기 동작 + 초점 복귀

**판정**: 치명적(조작 불가·정보 누락) 항목 0건이면 PASS.

## 4. 시니어 모드 검증 (현재 미구현 — 결정 필요)

⚠️ 시니어 모드는 아직 구현 항목이 아니다(TC-505 후보). 실기기에서 아래를 확인해
**구현 필요성을 판정**하는 자료로 쓴다:
- [ ] 기본 폰트 크기(16px)에서 60대 사용자가 읽기 불편한지
- [ ] 확대(브라우저 zoom 125%) 시 레이아웃 붕괴 여부 — 3분할 셸·FAB 겹침 확인
- [ ] 버튼 히트 영역이 충분한지(44px 권장) — FAB·회차 트리·설정 토글

붕괴가 있으면 이슈화(우선순위: 중) → "글자 크기 확대 토큰(S7 테마 탭)" 후보.

## 5. 결과 기록

| TC | 결과 | 비고 |
|----|------|------|
| TC-302 keyring DPAPI | | |
| TC-401~405 성능 | | |
| TC-503~505 NVDA | | |
| 시니어 모드 판정 자료 | | |

완료 후 이 파일의 표를 채우고 `QA_개발검증_리포트_v3.md`에 반영하면, pending-manual 항목이 전부 소화된다.
