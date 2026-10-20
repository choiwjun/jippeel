"""작품 연령 등급(전체연령/19금) 계약 테스트.

등급은 생성 입력이자 이후 모든 생성·감수가 공유하는 수위 규칙이다.
- 기본값은 전체연령이며, 등급 상향은 명시적 입력만으로 일어난다
- 부트스트랩 프롬프트와 공유 AI 컨텍스트가 같은 블록을 본다
- adult 블록은 등급과 무관한 금지선을 함께 싣는다
"""
from app.age_rating import age_rating_prompt_block, normalize_age_rating
from app.schemas import GenerateContext, GenerateRequest
from app.services.ai_context import build_context_bundle, request_from_generate
from tests.conftest import _db
from tests.test_bootstrap_api import (  # noqa: F401 — fixture 재사용
    _good_outline,
    enqueue_success,
    fake_llm,
)


# ---- 등급 정규화 (등급은 올라가지 않는다) ----

def test_unknown_age_rating_falls_back_to_all():
    assert normalize_age_rating("adult") == "adult"
    assert normalize_age_rating("all") == "all"
    for value in (None, "", "19", "ADULT", "r19", 19, {"v": "adult"}):
        assert normalize_age_rating(value) == "all"


def test_adult_block_carries_hard_limits():
    block = age_rating_prompt_block("adult")
    assert "19금(성인) 지정" in block
    # 등급 상향이 금지선 해제로 읽히지 않아야 한다
    assert "미성년자를 성적 대상으로 묘사하는 것" in block
    assert "등급과 무관하게 금지한다" in block

    safe = age_rating_prompt_block("all")
    assert "전체연령" in safe and "19금" not in safe


# ---- 프로젝트 API ----

def test_project_defaults_to_all_rating(client):
    body = client.post("/api/v1/projects", json={"title": "기본 등급"}).json()
    assert body["age_rating"] == "all"


def test_project_rating_round_trip_and_null_rejected(client):
    pid = client.post("/api/v1/projects",
                      json={"title": "성인작", "age_rating": "adult"}).json()["id"]
    assert client.get(f"/api/v1/projects/{pid}").json()["age_rating"] == "adult"

    # 생략은 불변
    patched = client.patch(f"/api/v1/projects/{pid}", json={"genre": "로맨스판타지"}).json()
    assert patched["age_rating"] == "adult" and patched["genre"] == "로맨스판타지"

    # 하향도 명시적으로 가능
    assert client.patch(f"/api/v1/projects/{pid}",
                        json={"age_rating": "all"}).json()["age_rating"] == "all"

    # NOT NULL 컬럼 — 명시적 null·미지 값은 422
    assert client.patch(f"/api/v1/projects/{pid}", json={"age_rating": None}).status_code == 422
    assert client.patch(f"/api/v1/projects/{pid}", json={"age_rating": "r19"}).status_code == 422
    assert client.post("/api/v1/projects",
                       json={"title": "x", "age_rating": "19금"}).status_code == 422


# ---- 공유 AI 컨텍스트 ----

def _bundle_blocks(client, pid):
    payload = GenerateRequest(
        prompt_override="이어 써줘",
        context=GenerateContext(project_id=pid),
    )
    return "\n".join(build_context_bundle(_db(client), request_from_generate(payload)).blocks)


def test_rating_block_is_injected_into_shared_context(client):
    pid = client.post("/api/v1/projects",
                      json={"title": "성인작", "age_rating": "adult"}).json()["id"]
    blocks = _bundle_blocks(client, pid)
    assert "[작품 연령 등급 — 19금(성인) 지정]" in blocks
    assert "미성년자를 성적 대상으로 묘사하는 것" in blocks


def test_all_rating_project_gets_safe_block(client):
    pid = client.post("/api/v1/projects", json={"title": "전체연령작"}).json()["id"]
    blocks = _bundle_blocks(client, pid)
    assert "[작품 연령 등급 — 전체연령]" in blocks
    assert "19금" not in blocks


# ---- 부트스트랩 ----

def test_bootstrap_adult_rating_is_persisted_and_in_every_prompt(client, fake_llm):
    enqueue_success(fake_llm, outline=_good_outline(1, 2))

    response = client.post("/api/v1/projects/bootstrap", json={
        "genre": "로맨스판타지",
        "age_rating": "adult",
        "volume_count": 1,
        "chapters_per_volume": 2,
    })

    assert response.status_code == 200, response.text
    pid = response.json()["project_id"]
    project = client.get(f"/api/v1/projects/{pid}").json()
    assert project["age_rating"] == "adult"
    assert project["genre"] == "로맨스판타지"

    assert len(fake_llm["calls"]) == 4
    systems = [
        msg["content"]
        for call in fake_llm["calls"]
        for msg in call["messages"]
        if msg["role"] == "system"
    ]
    assert len(systems) == 4
    assert all("19금(성인) 지정" in content for content in systems)
    assert all("미성년자를 성적 대상으로 묘사하는 것" in content for content in systems)


def test_bootstrap_without_rating_stays_all(client, fake_llm):
    enqueue_success(fake_llm, outline=_good_outline(1, 2))

    response = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지",
        "volume_count": 1,
        "chapters_per_volume": 2,
    })

    assert response.status_code == 200, response.text
    pid = response.json()["project_id"]
    assert client.get(f"/api/v1/projects/{pid}").json()["age_rating"] == "all"
    systems = [
        msg["content"]
        for call in fake_llm["calls"]
        for msg in call["messages"]
        if msg["role"] == "system"
    ]
    assert systems and all("[작품 연령 등급 — 전체연령]" in c for c in systems)
    assert not any("19금" in c for c in systems)


def test_bootstrap_fallback_keeps_rating(client):
    """use_ai=false 폴백 경로도 등급을 보존한다."""
    response = client.post("/api/v1/projects/bootstrap", json={
        "genre": "로맨스판타지",
        "age_rating": "adult",
        "use_ai": False,
        "volume_count": 1,
        "chapters_per_volume": 2,
    })
    assert response.status_code == 200, response.text
    pid = response.json()["project_id"]
    assert client.get(f"/api/v1/projects/{pid}").json()["age_rating"] == "adult"
