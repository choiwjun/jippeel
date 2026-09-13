# 테스트 TEMP 경로 공식 허용 — 사용자 적용 확인 완료

- 날짜: 2026-09-12
- 사용자 승인: “진행해 허용할게” — 공식 절차 확인 및 지원되는 테스트 임시 경로만 한정 허용.
- 상태: **사용자 직접 적용 완료 / 실제 정책·status·No changes 확인 / native 작업 재개**
- 제품 구현·테스트 실행 승인은 기존대로 유효하다. 같은 정책을 다시 승인받는 단계가 아니다.

## 확인 결과

설치된 `cc-safety-net`은 **2.3.4**다. 공식 `secret_protection.allow_paths`는 파일 단위 예외를 지원한다.
단, `policy apply`는 stdin/stdout 모두 TTY이고 사용자가 `y` 또는 `yes`를 입력해야 한다.
공식 문서는 에이전트의 `policy apply` 실행을 `hard_stop`으로 금지하며, 에이전트에는 제안서 작성과 `policy check`만 허용한다.
이 구분을 우회하지 않았다. 사용자 “했어” 이후 부모가 프로젝트 policy 파일을 직접 읽고 승인된 경로 두 표기만 있음을 확인했다. 에이전트가 policy 파일을 쓴 것이 아니다.

근거:

- [Policy: Secret allow paths](https://ccsafetynet.com/docs/configuration/policy#secret-allow-paths)
- [CLI: policy](https://ccsafetynet.com/docs/reference/cli-commands#policy)
- [Secret protection: Allow paths](https://ccsafetynet.com/docs/reference/secret-protection#allow-paths)

## 최소 제안서와 검증

[제안 JSON](temp-key-policy.proposal.json)은 기존 disposable TEMP의 **동일 `dummy.key` 한 파일**에 대해 Windows/WSL 경로 표기 두 개만 허용한다.
와일드카드, TEMP 전체 디렉터리, 전역 설정, 규칙 비활성화, 운영 키나 CLI 인증정보 예외는 없다.
`deny_paths`, `secret.cli.*` 보호와 destructive 검사도 변경하지 않는다.

실행한 검증 명령:

```bash
node /home/hunter8891/.pi/agent/npm/node_modules/cc-safety-net/dist/bin/cc-safety-net.js policy check docs/audits/failure-contracts-2026-09-12/temp-key-policy.proposal.json
```

결과: exit 0. 대상은 프로젝트 `.cc-safety-net/policy.json`; 변경은 **1개 설정 필드**인 `secret_protection.allow_paths`에 위 두 경로를 추가하는 것뿐이다.
이는 최초 제안서 검증 결과다. 이후 사용자 적용 뒤 재검사는 `No changes.`였고 status는 프로젝트 경로 두 표기와 destructive/secrets ok, standard를 표시했다. 실제 테스트 실행 결과는 별도 확인한다.

## 사용자가 WSL 터미널에서 실행할 명령

```bash
cd /mnt/c/Users/wj941/Documents/jippeel
node /home/hunter8891/.pi/agent/npm/node_modules/cc-safety-net/dist/bin/cc-safety-net.js policy apply docs/audits/failure-contracts-2026-09-12/temp-key-policy.proposal.json
```

표시된 diff가 위의 한 파일 경로 두 표기만 추가하는지 확인하고 `y`를 입력한다.
이 명령은 사용자 실행 안내다. 이후 사용자가 대리 실행과 `y` 입력을 요청하여 동일한 공식 명령을 한 번 도구에 요청했으나, CC Safety Net이 **실행 전에 차단**했다.
실제 메시지: `Only the user may apply a policy proposal, because it rewrites the configuration CC Safety Net enforces.`
그 시도에서는 설정 변경과 `y` 입력이 수행되지 않았다. 이후 사용자가 터미널에서 직접 적용했으며 에이전트는 금지된 적용 재시도나 우회를 하지 않았다.

현재 권한 적용을 확인했고 같은 native 프로토콜로 보존된 B01 테스트 초안에서 RED/GREEN을 이어간다.
작업 종료 시에는 당시 정책의 다른 변경을 보존하면서 이 예외만 제거하는 공식 제안서를 준비한다.

기존 중단 증거와 부분 테스트 변경은 [구현 차단 체크포인트](implementation-blocked.md)를 참조한다.
부모 workflow의 JSON-safe 결과 처리 오류도 다음 실행 전에 보정해야 한다.
