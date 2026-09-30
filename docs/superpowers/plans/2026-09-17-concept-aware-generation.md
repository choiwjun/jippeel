# 구조화된 작품 컨셉 구현 계획

> 사양: `docs/superpowers/specs/2026-09-17-concept-aware-generation.md`
> 조사: `docs/research/2026-09-17-novel-concept-taxonomy.md`

## 1. 도메인 계약과 migration

- [x] `StoryConcept` Pydantic 모델을 추가한다.
  - `summary`, `protagonist`, `inciting_incident`, `goal`, `opposition`, `stakes`, `hook`
  - 구성요소 최소 1개, unknown key 금지, 필드별 길이 제한
- [x] `Project.concept`를 nullable JSON으로 저장한다.
- [x] 기존 프로젝트에 임의 장르·톤·서사를 backfill하지 않는 Alembic migration을 추가한다.
- [x] 프로젝트 생성·수정·조회와 bootstrap 요청·응답에 같은 계약을 사용한다.

## 2. 생성 컨텍스트

- [x] 컨셉 객체를 bounded prompt block으로 변환한다.
- [x] 부트스트랩 발상 단계에서 AI가 구조화 컨셉을 제안하도록 JSON 계약을 확장한다.
- [x] 목차·캐릭터·권별 조연·관계/로어 단계에 같은 컨셉 블록을 전달한다.
- [x] 일반 회차·계획·병렬 생성·감수의 shared context에 같은 블록을 전달한다.
- [x] AI 실패/미사용 폴백과 생성 응답에서 컨셉을 보존한다.

## 3. UI

- [x] 재사용 가능한 접근성 컨셉 입력 컴포넌트를 만든다.
- [x] AI 부트스트랩과 수동 프로젝트 생성에 한 문장 전제와 선택적 구성요소 입력을 제공한다.
- [x] 홈 카드에 컨셉 요약을 표시하고 편집 대화상자를 제공한다.
- [x] 장르·테마·톤을 컨셉 선택 목록으로 혼합하지 않는다.

## 4. 검증

- [x] API·프롬프트·폴백·shared context 테스트를 추가한다.
- [x] migration upgrade/downgrade와 기존 프로젝트/참조 데이터 보존을 검증한다.
- [x] 격리 backend 전체 테스트, frontend build, Playwright UI를 실행한다.
- [x] 운영 DB migration·실제 provider 호출 없이 결과를 기록한다.
