# 실제 모델 품질 평가 설계

- 작성일: 2026-09-10
- 상태: **설계만 완료. 실제 provider 호출·비용 발생 없음.**
- 목적: 결정론적 fake-provider 검증을 실제 모델 품질 검증으로 확장하기 위한 승인 단위와 acceptance evidence 정의

## 1. 평가 경계

이번 평가는 synthetic writing-case 전체 회귀가 아니다. 사용자가 승인한 실제 게시 원고 또는 실제 게시 예정 회차에서만 사례를 고른다. 사례 원문·설정·브리프·금지사항은 실행 전에 동결하고 SHA-256을 기록한다.

평가 대상은 현재 코드가 제공하는 실제 표면으로 한정한다.

| 표면 | 평가 내용 |
|---|---|
| `POST /api/v1/ai/generate` | 저장 회차 맥락, 브리프, 문체, 인물 관계, 목적과 훅을 반영한 단일 생성 |
| `POST /api/v1/ai/generate-parallel` | planner 계약, 장면별 worker 결과, 순서 조립, 병렬 감수의 실제 품질 |
| `POST /api/v1/ai/review` 또는 생성 인라인 review | 초안 근거의 감수와 수정본 분리, 지적의 정확성 |
| `POST /api/v1/canon-check` | 캐릭터·로어·복선과의 모순 후보 탐지. 자동 수정 품질과 혼동하지 않음 |

현재 로컬 규칙 기반 `/api/v1/chapters/{cid}/quality`는 LLM 품질의 정답으로 사용하지 않는다. 이는 별도 규칙 진단이며 문학적 완성도 평가가 아니다.

근거: `backend/app/routers/ai_panel.py`, `backend/app/routers/quality.py`, `backend/app/schemas.py`.

## 2. 파일럿 사례 구성

파일럿은 **실제 승인 사례 6개**로 시작한다. 사례 수는 일반화된 문학 품질 보증이 아니라 비용 제한형 진단용이다.

- 단일 생성 3개
- 병렬 생성 2개
- review 또는 canon 1개
- 가능한 경우 `serial`, `volume_end`, `series_finale` 목적을 나눠 포함한다. 실제 자료가 없는 목적은 만들지 않고 `unavailable`로 기록한다.
- 회차별로 다음 입력을 함께 동결한다: project/chapter/revision, 본문 포함 여부, episode purpose, brief, style profile, selected characters/lore, approved foreshadow IDs, previous chapter 옵션.
- 6개 중 최소 2개는 평가 설계에 사용하지 않은 **holdout**으로 남긴다. holdout은 rubric과 prompt를 확정한 뒤 처음 공개한다.

각 사례 manifest에는 다음을 기록한다.

```json
{
  "case_id": "real-case-01",
  "source_kind": "approved_real_chapter",
  "source_ref": "private-local-reference",
  "project_id": 0,
  "chapter_id": 0,
  "revision": 0,
  "episode_purpose": "serial",
  "input_sha256": "...",
  "gold_contract_sha256": "...",
  "holdout": true
}
```

실제 원고와 API key는 Git에 넣지 않는다. `source_ref`는 로컬 별도 보관 경로만 가리킨다.

## 3. provider와 비용 상한

provider를 자동 선택하지 않는다. 실행 manifest에 `provider`, `endpoint_name`, `model`, `reasoning_effort`, `temperature`, `max_tokens`를 고정한다. 비교 실험이 아니므로 파일럿에서는 한 provider/model만 사용한다.

비용 정책:

- 파일럿 hard cap: **USD 20**
- 80% 도달 시 다음 사례를 시작하지 않고 중간 결과를 보존한다.
- provider 응답의 실제 token usage와 승인된 가격표로 비용을 계산한다. `ai_usage`의 문자 수는 비용 산정의 대체값으로 사용하지 않는다.
- 현재 `backend/app/services/llm.py`는 stream delta/최종 문자열만 반환하고 provider usage를 보존하지 않는다. 따라서 실제 평가 runner는 raw provider response를 별도로 캡처하거나 provider billing export를 받아야 한다. 이 증거를 확보하지 못하면 실행을 중단한다.
- provider가 usage 또는 가격을 노출하지 않으면 실행을 중단하고 추정 비용만 보고한다.
- 자동 retry는 금지한다. 전송 오류 1건도 원시 응답·비용 상태를 보존한 뒤 수동 재승인한다.
- 로컬 provider는 금전 비용이 0이어도 wall time, prompt/completion chars, model, endpoint를 기록한다.

실제 호출 전 preflight에서 예상 비용이 hard cap을 넘으면 사례 수나 출력 상한을 줄여 다시 승인한다. cap을 초과하는 우회 호출은 하지 않는다.

## 4. 정답과 채점

### 4.1 독립적인 gold contract

각 사례의 gold contract는 모델 출력에서 추출하지 않고, 평가 전에 작가/기획자가 승인한 원본에서 만든다.

- 반드시 보존할 canon 사실과 시간축
- 인물의 현재 목표·선택·대가
- 필수 사건/beat
- 금지된 새 사실과 금지 표현
- episode purpose, ending intent 또는 next hook
- 문체 profile에서 관찰 가능한 규칙

### 4.2 hard gates

아래 하나라도 실패하면 해당 사례는 문학 점수와 무관하게 **BLOCK**이다.

1. 다른 작품·회차·revision의 사실을 사용한다.
2. gold contract의 금지사항을 위반한다.
3. 핵심 canon, 시간축, 인물 관계를 반대로 만든다.
4. required beat, choice, cost 또는 ending intent를 누락한다.
5. planner/worker 장면 순서가 깨지거나 다른 장면 내용을 대신 쓴다.
6. `[감수]`, JSON, 장면 계약 등 사용자에게 보이면 안 되는 메타 출력이 본문에 섞인다.
7. 실제 요청과 다른 provider 입력, 저장 본문, revision이 사용된다.
8. 평가 전후의 임시 DB snapshot에서 허용되지 않은 원고 변경이 발생한다.

hard gate는 gold contract와 원시 provider payload를 대조하는 결정론적 검사 및 사람의 사실 대조로 판정한다. 생성 모델이나 같은 provider의 자기평가만으로 pass시키지 않는다.

### 4.3 문학 품질 rubric

출력은 provider/model 이름을 가린 뒤 두 명의 독립 평가자가 1–5점으로 채점한다.

| 축 | 1점 | 3점 | 5점 |
|---|---|---|---|
| 인과·구조 | 사건 연결이 끊김 | 핵심 흐름은 이해됨 | 장면 목적과 전환이 선명함 |
| 인물·목소리 | 동기/말투 붕괴 | 대체로 일관됨 | 선택과 대사가 인물에 필연적임 |
| 리듬·문장 | 장황/단조/메타 | 읽히지만 군더더기 존재 | 장면 유형에 맞고 긴장 유지 |
| 사건·대가 | 목표/대가가 추상적 | 일부 행동화 | 선택과 대가가 행동으로 확인됨 |
| 연재 목적 | 훅/권말 의도 실패 | 부분 달성 | 목적과 다음 압력이 정확함 |

평가자는 모델명, provider, 생성 순서, 다른 평가자의 점수를 보지 않는다. 사례별 자유 코멘트에는 반드시 원문 위치와 근거를 남긴다. 평균 하나로 합쳐 품질을 보증하지 않고 축별 median, 점수 차이, hard gate 결과, author accept/reject를 함께 보고한다.

최종 파일럿 acceptance는 다음 모두를 요구한다.

- 6개 사례 모두 hard gate PASS
- 각 사례의 작가 accept
- 어떤 문학 축도 median 3 미만이 아님
- 두 평가자의 축별 점수 차이가 2점을 넘는 사례는 adjudication 완료
- provider usage/cost, raw SSE, 입력 hash, DB before/after snapshot이 모두 존재

이 조건은 파일럿의 go/no-go 기준이지 장편 문학 품질의 일반 보증이나 통계적 유의성 주장이 아니다.

## 5. 실행과 증거 보존

운영 DB와 기존 서비스는 건드리지 않는다. 임시 DB, 전용 포트, 별도 provider endpoint 또는 dry-run endpoint를 사용한다.

보존할 산출물:

- `evaluation-manifest.json`: 사례·입력 hash·provider·모델·설정·rubric 버전
- `provider-events.jsonl`: secret redaction 후 원시 SSE/응답 이벤트
- `scores-blinded.jsonl`: blind label별 hard gate·rubric 점수·근거
- `blind-map.json`: 평가 종료 후에만 공개하는 label↔output map
- `cost-summary.json`: provider usage, 가격표 버전, 사례별 누적 비용
- `db-snapshot-before.sha256`, `db-snapshot-after.sha256`
- `acceptance-report.md`: 실패 사례, adjudication, author decision, 최종 go/no-go

실제 평가 전 검증 순서:

1. 사례 manifest와 gold contract를 별도 검토한다.
2. provider/model/가격표와 USD 20 cap을 확인한다.
3. 요청 payload와 실제 provider `payload.messages`를 대조한다.
4. 사례별 raw output을 blind label로 저장한다.
5. hard gate를 먼저 수행하고, 통과한 출력만 문학 rubric으로 보낸다.
6. 두 평가자의 blind score를 adjudicate한다.
7. 비용·snapshot·이력·원고 보존을 확인하고 go/no-go를 작성한다.

## 6. leakage audit (Mandela)

| 패턴 | 위험 | 독립성 보정 |
|---|---|---|
| Shared hallucination | 같은 LLM이 생성과 채점을 모두 수행 | 결정론적 contract 검사 + 두 사람의 blind 평가. LLM judge는 보조 의견으로만 보관 |
| Tautology | rubric이 출력에서 사후 추출된 항목을 다시 채점 | gold contract와 rubric을 출력 전에 freeze |
| Verifier = designer | 구현자가 만든 사례와 rubric만 평가 | holdout 2개와 독립 평가자 사용 |
| Shared-pool bias | gold를 만든 작가가 모든 품질 점수를 혼자 부여 | 작가는 canon/accept만, 독립 평가자는 blind literary score 담당 |
| Frame injection | prompt가 기대 답/평가 가설을 직접 노출 | 모델 입력에는 실제 집필 계약만 넣고 gold label·점수 기준은 넣지 않음 |
| Demand characteristics | 평가자가 provider/model을 알아 점수에 영향 | blind labels, random output order, provider 정보 비공개 |

따라서 이 설계의 외부 ground truth는 모델 자신이 아니라 **평가 전에 동결된 실제 원고/작가 승인 canon과 blind human review**다. 실제 모델 호출 전에는 이 독립성 조건을 변경하지 않는다.

## 7. 현재 결정과 미결정

결정:

- synthetic 전체 회귀 대신 실제 승인 원고 6개 파일럿
- hard contract와 문학 rubric 분리
- USD 20 hard cap, provider usage 기반 비용 기록
- 운영 DB/서비스 미접근, no-call 설계 단계 유지

미결정:

- 실제 사례 6개의 ID와 source owner
- provider/endpoint/model 및 가격표
- 두 독립 평가자의 배정
- 파일럿 실행 승인 시점

## 출처와 코드 근거

- 생성/감수 API: `backend/app/routers/ai_panel.py`
- 생성 요청 계약: `backend/app/schemas.py` (`GenerateContext`, `EpisodeBrief`, `ParallelGenerateRequest`, `ReviewRequest`)
- canon 검사: `backend/app/routers/quality.py`
- 사용량 기록: `backend/app/services/usage.py`, `backend/app/models.py` (`AiUsage`)
- 기존 검증 한계: `docs/audits/ai-context-final-validation.md`
- 재사용 가능한 검증 규칙: `docs/audits/ai-context-lessons.md`
