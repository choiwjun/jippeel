"""기본 제공 프롬프트 프리셋 시드 — AI 패널 첫 화면이 비어 보이지 않도록 한다.

앱 기동(lifespan)에서 프리셋 테이블이 비어 있을 때만 1회 삽입한다.
사용자가 수정·삭제해도 다시 채우지 않는다(사용자 데이터 존중).
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PromptPreset

BUILTIN_PRESETS: list[dict] = [
    {
        "name": "이어쓰기",
        "template_text": (
            "직전 내용에 자연스럽게 이어지는 다음 장면을 웹소설 문체로 집필하라.\n"
            "문단은 2~3문장으로 짧게 유지하고, 대사와 심리 묘사를 섞어 리듬감을 살리며,\n"
            "마지막 문장은 다음 화로 넘어가고 싶게 만드는 훅으로 끝낸다."
        ),
        "context_flags": ["chapter"],
    },
    {
        "name": "새 장면 만들기",
        "template_text": (
            "캐릭터와 세계관 설정을 지켜 지금 장소·상황에서 벌어지는 새로운 장면을 집필하라.\n"
            "등장인물의 말투는 각 캐릭터 설정을 따르고, 장면의 목적(갈등·발전·복선)을 분명히 한다."
        ),
        "context_flags": ["characters", "lore"],
    },
    {
        "name": "대사 다듬기",
        "template_text": (
            "본문의 대사가 캐릭터마다 구분되도록 말투를 다듬고, 설명하듯 긴 서술은 대사로 바꿔라.\n"
            "사건의 순서와 내용은 바꾸지 마라."
        ),
        "context_flags": ["chapter", "characters"],
    },
    {
        "name": "묘사 살리기",
        "template_text": (
            "밋밋한 서술을 보이는 것·소리·냄새·촉감 등 오감 묘사로 보강하라.\n"
            "문장은 짧게 유지하고 과한 수식어는 쓰지 마라. 흐름과 사건은 유지한다."
        ),
        "context_flags": ["chapter"],
    },
    {
        "name": "내용 요약",
        "template_text": (
            "본문을 3문장으로 요약하고, 다음 화 예고에 쓸 한 줄 훅을 덧붙여라."
        ),
        "context_flags": ["chapter"],
    },
    {
        "name": "다음 화 훅으로 마무리",
        "template_text": (
            "본문을 이번 화의 결말로 마무리하되, 독자가 다음 화를 클릭하게 만드는\n"
            "반전·위기·질문 중 하나의 훅으로 끝내라."
        ),
        "context_flags": ["chapter"],
    },
]


def seed_presets(session: Session) -> None:
    """프리셋이 하나도 없을 때만 기본 프리셋을 채운다(멱등)."""
    count = session.scalar(select(func.count()).select_from(PromptPreset))
    if count:
        return
    for item in BUILTIN_PRESETS:
        session.add(PromptPreset(**item))
    session.commit()
