# 독립 검토 — 2026-10-05

검토자: 현재 도구의 읽기 전용 `independent_bug_review` subagent. 같은 worktree의 writer는 작성자 한 명으로 유지했다. 검토자는 코드·테스트만 읽었으며 파일 변경, 테스트 실행, DB/provider/Git 작업은 수행하지 않았다.

## 지적과 반영

| 경로 | 지적 | 최종 반영 |
| --- | --- | --- |
| 전체 내보내기 | dirty draft의 revision을 새 GET으로 바꾸면 다른 작성자의 저장을 덮어쓸 수 있음 | dirty/in-flight/recovery 작업본의 기준을 유지하며 원래 expected_revision으로 저장. 실제 revision 비교를 하는 합성 API의 동시 저장 회귀 추가 |
| 회차·전체 내보내기 | coordinator의 synthetic detail을 직접 사용하면 제목·권·순서 유실 | 상세 메타데이터에 저장된 본문/revision만 병합. 파일명·제목·권·서사 순서 검증 |
| 아크·권 기억 선택 | chapter_id 없는 rollup은 숫자 sort만으로 미래 기억 주입 | 출처 그래프의 마지막 회차를 canonical 순서로 비교. 생성 rollup의 legacy 숫자 lower bound를 출처 기준으로 대체. 수동 기억의 명시 범위 보존 |
| 요약 worker | 오래된 identity map의 승인 상태로 provider를 호출할 수 있음 | 호출 전 새 graph를 읽고 그 graph에서 원천 존재·종류·승인·freshness 검증. 외부 retire/delete의 arc/volume 미호출 회귀 4개 |
| 실제 요약 어댑터 | helper 인자 변경이 Session 호출부와 불일치 | 기존 Session 인자 계약 유지, 선택적 graph 전달. 실제 arc/volume 어댑터와 fake transport 통합 테스트 2개 |
| 전체 내보내기 | 오래된 GET이 새 autosave ACK 뒤 도착하면 revision이 되돌아감 | clean 작업본도 서버 revision이 현재 revision 이상인 경우에만 갱신. 오래된 GET을 지연시키는 browser 회귀 |

## 최종 읽기 검토 결론

**수용 가능.** 앞선 6개 지적이 모두 반영됐고, 추가로 수정이 필요한 구체적 결함은 발견하지 못했다. 어댑터 호출 계약, 내보내기의 메타데이터·revision 보존, 출처 freshness 및 canonical 순서의 호출 전후 검사와 해당 회귀 시나리오를 확인했다.

실행 검증의 결과와 한계는 작성자의 [최종 수용 기록](acceptance.md)을 기준으로 한다.
