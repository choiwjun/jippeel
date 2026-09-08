# AI-context 최종 문서 확인

소스 기준: `cd7fc1f3360b6e42d49ab75398b94732ed057649`. 문서 단계에서 앱/테스트 코드는 수정하지 않았다.

- **shower:** 별도 세션이 최종 검증·runbook·lessons·새 인계 블록의 제공된 본문만 읽었다. [blind report](ai-context-final-doc-coldread.md)에 확정된 차단 문제는 없었다. 인계는 일부 블록만 제공했기 때문에 이전 기록 부재 가능성을 제기했다. 부모는 실제 HANDOFF에 이전 본문이 보존됨을 확인했다. 사전 환경 확인, 읽기 전용 포트 확인, 이동 포인터와 보존 사본 경로 구분, `holding` 정의, 해결된 지적 제목을 보완했다.
- **실행 확인:** runbook에 실은 환경 복원형 PowerShell backend 절차를 새 TEMP DB로 native 실행해 269 passed를 확인했다. [출력](ai-context-final-runbook-backend.txt). 별도 읽기 전용 사전 확인도 성공했다. [출력](ai-context-final-runbook-preflight.txt). 단위 테스트 우회는 실제 통합과 분리했다.
- **mandela:** 평가 대상은 실제 앱, 생성 데이터는 합성 fixture, 로거는 별도 가짜 제공자, 판정은 요청/화면/API/DB 대조다. 과거의 identity 주입·reload에 의한 상태 제거·메타데이터끼리의 대조는 잘못된 평가 경계였다. 최종 증거는 자연스러운 동일 runtime의 남은 이전 상태, 실제 제공자 메시지, 저장 본문에서 독립 계산한 hash를 사용한다. 별도 검토자와 부모가 재실행했다. 이것을 외부 모델/문학 품질 평가로 일반화하지 않았다.
- **ssotize 읽기 전용 점검:** 현재 완료 상태의 기준은 [최종 검증](ai-context-final-validation.md)이다. runbook/lessons/HANDOFF는 이를 참조한다. progress는 진행 이력임을 명시했고 착수 당시 단계와 현재 결론을 구분했다. Task/review/snapshot의 과거 수치·상태·hash는 당시 근거이며 광범위한 정리나 삭제를 하지 않았다.
- **factchk 범위:** 운영·성능·모델 품질에 대한 외부 사실/신규성 주장은 추가하지 않았다. 검증 수치는 native 명령의 실제 종료 코드와 출력, 제공자 원시 메시지, API/DB/화면 증거를 기준으로 확인했다. 외부 웹 조사로 이 로컬 실행 증거를 대체하지 않았다.
- **re0:** 새 문서에서는 현재 계약·재실행·제한을 분리하고 중간 초안 상태를 제거했다. 역사적 보고서는 그대로 보존했다.
- **링크:** 최종 검증/runbook/lessons의 상대 링크 29개 대상 존재를 확인했다. 결과는 `.eval_tmp/ai-context-final-parent/document-links.json`에 보존했다.
- **detool 생략:** 도구 중립적 이식성을 주장하지 않는 native Windows 운영 안내이므로 정확한 명령·포트·경로를 유지했다.
