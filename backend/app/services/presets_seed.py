"""빌트인 프롬프트 프리셋 시드 (FR-403 보강 / 부록06: oh-story-claudecode 방법론 차용).

웹소설 집필에 바로 쓸 수 있는 프리셋 6종을 이름 기준 멱등 시드한다.
- 이미 같은 name이 있으면 건너뛴다(사용자가 수정·삭제해도 재시작 시 복원 —
  SettingsPage 안내 문구 "빌트인 프리셋은 백엔드 시드에서 관리"와 일치).
- 프리셋 내용은 oh-story-claudecode의 지식베이스(장 종결 후크·감정 곡선·
  대화 잠재의식·去AI味 지침)를 한국 웹소설 맥락으로 재해석한 것으로,
  원문 코드·문장을 복사하지 않았다(MIT 라이선스, 부록06 §3).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PromptPreset

BUILTIN_PRESETS: list[dict] = [
    {
        "name": "이어쓰기",
        "template_text": (
            "앞 본문의 시점·문체·시제를 그대로 유지한 채, 마지막 장면에서 "
            "자연스럽게 이어지도록 이어 쓴다. 앞 내용을 요약해 반복하지 말고, "
            "새로운 사건·대사·행동으로 전개하라. 등장인물의 말투는 설정을 따른다."
        ),
        "context_flags": ["chapter", "characters", "lore"],
    },
    {
        "name": "장 끝 후크",
        "template_text": (
            "본문의 마지막 2~3문장을 다음 화가 궁금해지는 후크로 다듬어라. "
            "반전 암시·미해결 질문·위기 직전 정지 중 이 장면에 가장 알맞은 "
            "방식 하나를 택하고, 후크 이전의 흐름과 설정은 유지한다."
        ),
        "context_flags": ["chapter"],
    },
    {
        "name": "감정 기복 설계",
        "template_text": (
            "한 화 안에서 독자 감정이 최소 3번 오르내리도록 장면을 재배치·보강하라. "
            "고조 직후에는 완충 장면을 두고, 각 전환마다 인물의 구체적 행동과 "
            "반응으로 감정을 드러내라. 설명 대신 장면으로 보여라. 출력은 수정된 본문 전체."
        ),
        "context_flags": ["chapter"],
    },
    {
        "name": "대화 잠재의식",
        "template_text": (
            "대사들이 '말하는 것'과 '진심'이 어긋나도록 다듬어라. 갈등 중인 인물은 "
            "부정·회피·농담으로 본심을 감추고, 행동 묘사가 말과 반대되는 순간을 "
            "최소 한 군데 넣어라. 설명문을 붙이지 말고 본문만 출력하라."
        ),
        "context_flags": ["chapter", "characters"],
    },
    {
        "name": "장면 확장",
        "template_text": (
            "현재 장면을 오감 디테일(소리·냄새·온도·촉감·시각)로 확장하되 줄거리 "
            "진행은 늦추지 마라. 분위기와 인물 심리를 강화하는 디테일만 남기고, "
            "장식적 수식은 과하게 넣지 마라."
        ),
        "context_flags": ["chapter"],
    },
    {
        "name": "AI 티 제거 스타일",
        "template_text": (
            "다음 규칙으로 본문을 다듬어라. ① '~하게 된다', '~것이었다' 같은 서술형 "
            "반복을 줄인다. ② 같은 어미가 연속으로 오지 않게 한다. ③ 막연한 형용사·부사를 "
            "구체적 행동으로 바꾼다. ④ 문단 첫머리 패턴을 다양화한다. ⑤ 의성어·과장 표현은 "
            "남발하지 않는다. 줄거리와 사실 관계는 변경하지 마라."
        ),
        "context_flags": ["chapter"],
    },
]


def ensure_builtin_presets(db: Session) -> int:
    """누락된 빌트인 프리셋만 추가한다. 반환값은 새로 추가한 개수."""
    existing = set(
        db.scalars(select(PromptPreset.name)).all()
    )
    added = 0
    for spec in BUILTIN_PRESETS:
        if spec["name"] in existing:
            continue
        db.add(PromptPreset(**spec))
        added += 1
    if added:
        db.flush()
    return added
