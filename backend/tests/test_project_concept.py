"""구조화된 작품 컨셉의 API·프롬프트·공유 컨텍스트 계약."""

from app import concepts
from app.schemas import GenerateContext, GenerateRequest
from app.services import ai_context, bootstrap as bootstrap_service
from tests.conftest import _db


STORY_CONCEPT = {
    "summary": "기억을 잃은 세무사가 죽은 이들의 빚을 청산해야 집으로 돌아간다.",
    "protagonist": "타인의 장부를 읽는 능력을 가진 기억상실 세무사",
    "inciting_incident": "주인공의 이름으로 죽은 왕의 채무 통지서가 도착한다.",
    "goal": "왕의 빚을 청산하고 자신의 잃어버린 기억을 되찾는다.",
    "opposition": "채무를 회수하려는 저승 관청과 빚을 숨긴 왕의 후계자",
    "stakes": "실패하면 주인공의 존재 기록과 귀환할 세계가 함께 소멸한다.",
    "hook": "죽은 자의 빚을 갚아야 산 자로 인정받는 회계 판타지",
}


def test_project_stores_structured_story_concept_without_tone_enum(client):
    response = client.post(
        "/api/v1/projects",
        json={"title": "채무자의 귀환", "concept": STORY_CONCEPT},
    )

    assert response.status_code == 201, response.text
    project_id = response.json()["id"]
    assert response.json()["concept"] == STORY_CONCEPT
    assert client.get(f"/api/v1/projects/{project_id}").json()["concept"] == STORY_CONCEPT

    updated = {**STORY_CONCEPT, "goal": "왕의 빚과 자신의 과거를 함께 청산한다."}
    response = client.patch(
        f"/api/v1/projects/{project_id}", json={"concept": updated}
    )
    assert response.status_code == 200, response.text
    assert response.json()["concept"] == updated


def test_project_concept_rejects_unknown_component_and_accepts_clear(client):
    project_id = client.post(
        "/api/v1/projects", json={"title": "컨셉 검증", "concept": STORY_CONCEPT}
    ).json()["id"]

    assert client.patch(
        f"/api/v1/projects/{project_id}",
        json={"concept": {**STORY_CONCEPT, "tone": "코믹"}},
    ).status_code == 422
    cleared = client.patch(f"/api/v1/projects/{project_id}", json={"concept": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["concept"] is None


def test_string_concept_label_is_not_normalized_as_story_concept():
    assert concepts.normalize_concept("코믹") is None


def test_concept_prompt_block_exposes_story_engine_not_tone_labels():
    block = concepts.concept_prompt_block(STORY_CONCEPT)

    assert "[작품 컨셉 — 서사 전제]" in block
    assert "주인공" in block and STORY_CONCEPT["protagonist"] in block
    assert "촉발 사건" in block and STORY_CONCEPT["inciting_incident"] in block
    assert "목표" in block and STORY_CONCEPT["goal"] in block
    assert "대립" in block and STORY_CONCEPT["opposition"] in block
    assert "위험·대가" in block and STORY_CONCEPT["stakes"] in block
    assert "차별화 후크" in block and STORY_CONCEPT["hook"] in block
    assert "코믹" not in block


def test_fallback_bootstrap_leaves_missing_concept_unset(client):
    response = client.post(
        "/api/v1/projects/bootstrap",
        json={
            "genre": "판타지",
            "use_ai": False,
            "volume_count": 1,
            "chapters_per_volume": 1,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["concept"] is None


def test_fallback_bootstrap_preserves_structured_concept(client):
    response = client.post(
        "/api/v1/projects/bootstrap",
        json={
            "genre": "판타지",
            "concept": STORY_CONCEPT,
            "use_ai": False,
            "volume_count": 1,
            "chapters_per_volume": 1,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["concept"] == STORY_CONCEPT
    assert client.get(f"/api/v1/projects/{body['project_id']}").json()["concept"] == STORY_CONCEPT


def test_generation_context_uses_project_story_concept(client):
    project_id = client.post(
        "/api/v1/projects", json={"title": "컨셉 작품", "concept": STORY_CONCEPT}
    ).json()["id"]
    db = _db(client)
    payload = GenerateRequest(
        prompt_override="이 장면을 작성하라",
        context=GenerateContext(project_id=project_id),
    )

    bundle = ai_context.build_context_bundle(
        db, ai_context.request_from_generate(payload)
    )

    assert any(
        "[작품 컨셉 — 서사 전제]" in block
        and STORY_CONCEPT["hook"] in block
        for block in bundle.blocks
    )


def test_bootstrap_keeps_concept_data_out_of_system_message():
    messages = bootstrap_service._idea_messages(
        "판타지",
        None,
        "웹소설식 긴 제목",
        {"summary": "첫 줄\n이 내용은 데이터일 뿐이다."},
    )

    assert "첫 줄" not in messages[0]["content"]
    assert "<story-concept-data>" in messages[1]["content"]
    assert "\\n" in messages[1]["content"]


def test_missing_concept_context_does_not_instruct_unrelated_generation_to_invent_one():
    block = concepts.concept_prompt_block(None)

    assert "컨셉 입력 없음" in block
    assert "제안하라" not in block
