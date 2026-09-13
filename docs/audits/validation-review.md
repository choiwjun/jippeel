# 검증·품질 측정 감사

- 현재 Windows 프로젝트 venv에서 `pytest -q`: 201 passed, 1 warning (10.91s). DATABASE_URL은 임시 DB로 분리했다.
- Windows Node에서 TypeScript 및 Vite 빌드 성공. `vite.config.ts:11,38`의 중복 build 키 경고: 뒤 설정이 앞 설정을 덮어쓴다.
- WSL Node 빌드는 Linux Rollup 바이너리 부재로 실패. Windows용 node_modules와 런타임 혼용 문제이며 앱 기능 회귀와 구분한다. 의존성 변경 안 함.
- 품질 함수 실측: 빈 문자열 65점, `"가나다라" 마바사!` 100점(문자·숫자 7자). 후크는 느낌표만으로 참이 된다. 점수를 소설 완성도나 재미의 근거로 사용할 수 없다.
- `quality.py`의 WEAK_ENDINGS 문자열은 `~`를 포함하며 text.count로 검색한다. 자연스러운 `일 뿐이다`는 카운트 0. `이었다`는 `였다`와 중복 집계될 수도 있다. 장르 기준은 외부 근거를 검증하지 않았으므로 관례라는 주장을 승인하지 않는다.
- `backend/scripts/evaluate_parallel.py`: offline_result는 corpus 스키마만 검사하며 protocol_pass=len(cases)를 반환한다. 본문 품질을 주장하지 않는다는 명시적 caveat는 좋은 점이나 필드명은 schema_valid_cases로 바꾸는 편이 정확하다.
- live_case의 ok는 SSE 프로토콜에만 의존하며 required/forbidden cue 위반은 합격에 반영되지 않는다. 프로토콜 테스트는 유용하지만 서사 품질 평가와 분리해야 한다.
- 독립 평가 권고: 작가가 고정한 비공개 설정·사건 정답, 장르별 블라인드 A/B(단일/병렬/감수), 장편 1/20/50/100화 시점 모순율, 실제 수정량·채택률·비용 측정. 같은 모델의 감수 의견은 독립 정답이 아니다.

원시 증거: pytest.txt, quality-probes.txt, build-wsl.txt, build-windows.txt.

## 독립 재검토·보고서 품질 검사

- 상위 감사자가 관리 API·데이터 포함 Alembic·집필 함수 probe를 같은 프로젝트 환경에서 다시 실행했다. `verified-*.txt`가 재실행 출력이다. 모두 원 보고의 실패 양상을 확인했다. probe 프로세스 exit 0은 버그가 없다는 뜻이 아니라 예외/응답을 정상 수집했다는 뜻이다.
- 별도 fresh reader가 종합 보고서를 cold-read했다. 재현/위험 표시, 대상 시점·소스 해시, 승인 범위, 저장 시험 조건을 명확히 하라는 5건을 반영했다.
- SSOT 읽기 전용 점검: HANDOFF의 175 passed·옛 완료/다음 단계는 과거 기록이며 현재 기준은 pytest.txt의 201 passed이다. 검색 용어는 `passed`/`검증`과 `시맨틱`/`2-gram`으로 교차 확인했다. 의미 검색·대명사 보완이라는 역사적 표현보다 semantic.py의 문자 2-gram 구현을 근거로 삼았다. 기존 문서 정리는 승인 범위 밖이라 수정하지 않았다.
- 외부 정책·장르 통계·시장성 주장은 재검증하지 않아 결론에서 제외했다. 품질 점수의 유효성은 mandela 기준으로 프로토콜·규칙 적합성과 독립 작품 평가를 분리했다.
- portability/도구 중립성을 주장하는 산출물이 아니므로 detool은 생략했다. re0 정리로 시간순 작업 기록 대신 현재 결함·조치·완료 기준으로 종합 보고서를 구성했다.
