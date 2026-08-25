"""POST /api/v1/projects/bootstrap 통합 테스트 — LLM 클라이언트 모킹.

- 정상 경로: 고정 JSON 3회 응답 → 레코드 수·관계·키워드 검증
- 재시도 경로: 깨진 JSON → repair prompt 재시도 성공
- 폴백 경로: 전부 실패 → 규칙 기반 생성 + 502
- use_ai=false: LLM 호출 없이 템플릿 생성
"""
import json

import pytest
from sqlalchemy import select

from app.database import get_db
from app.models import Chapter, Character, LoreEntry, Project, Relationship
from app.routers import projects as projects_router
from app.services import bootstrap as bootstrap_service


GOOD_IDEA = {
    "titles": ["전지적 독자 시점의 나", "회귀자는 검이 된다", "마검사의 두 번째 삶",
               "별을 삼키는 자", "그 안개 속에서"],
    "logline": "소설 속 세계에 빨려 들어간 편집자가 살아남기 위해 원작을 바꾼다.",
    "theme": "운명과 선택",
}


def _good_outline(volume_count=2, cpv=3):
    volumes = []
    for v in range(1, volume_count + 1):
        chapters = []
        for i in range(1, cpv + 1):
            chapters.append({
                "order": i,
                "title": f"{v}권 {i}화. 각성의 서막 {v}-{i}",
                "synopsis": f"{v}-{i} 첫 문단. 주인공은 새로운 적수와 조우한다.\n"
                            f"{v}-{i} 둘째 문단. 위기를 틈타 숨겨둔 힘이 깨어난다.",
                "key_event": f"결정적 전환 {v}-{i}",
            })
        volumes.append({"volume": v, "title": f"{v}권. 균열의 시작", "chapters": chapters})
    return {"volumes": volumes}


GOOD_WORLD = {
    "characters": [
        {"name": "강산협", "alias": "검귀", "role": "주연", "appearance": "검은 머리카락",
         "personality": "과묵함", "speech_style": "단문", "background": "멸문한 가문의 생존자"},
        {"name": "서연화", "alias": "붉은 매화", "role": "조연", "appearance": "붉은 도포",
         "personality": "다혈질", "speech_style": "반말", "background": "보물고 도령"},
        {"name": "무허진인", "alias": "탑주", "role": "조연", "appearance": "백발",
         "personality": "신중함", "speech_style": "격식체", "background": "마탑 주인"},
        {"name": "흑천교주", "alias": "가면", "role": "조연", "appearance": "검은 가면",
         "personality": "냉철함", "speech_style": "존댓말", "background": "흑천교 수장"},
    ],
    "relationships": [
        {"from": "강산협", "to": "서연화", "label": "동료", "note": "전우"},
        {"from": "강산협", "to": "무허진인", "label": "제자-스승", "note": "비전 전수"},
        {"from": "강산협", "to": "없는이름", "label": "유령", "note": "무효 쌍"},
    ],
    "lore_entries": [
        {"category": "용어", "title": "천강검기", "content": "하늘 기운을 끌어 쓰는 검술",
         "keywords": ["천강검기", "검기"]},
        {"category": "장소", "title": "파천탑", "content": "아홉 층 탑", "keywords": ["파천탑"]},
        {"category": "세력", "title": "흑천교", "content": "마도 종파", "keywords": ["흑천교"]},
        {"category": "용어", "title": "내단법", "content": None},
        {"category": "장소", "title": "낙하협곡", "content": "깊은 협곡", "keywords": []},
        {"category": "세력", "title": "정파연맹", "content": "정통 연합", "keywords": ["연맹"]},
        {"category": "기타", "title": "대가의 법칙", "content": "모든 힘엔 대가가 따른다",
         "keywords": ["대가"]},
        {"category": "기타", "title": "예언의 조각", "content": "흩어진 예언", "keywords": ["예언"]},
    ],
}


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class FakeCompletions:
    """큐에 담긴 응답을 순서대로 반환하는 비(非)스트리밍 fake."""

    def __init__(self, holder):
        self._holder = holder

    async def create(self, **kwargs):
        self._holder["calls"].append(kwargs)
        queue = self._holder["queue"]
        if not queue:
            raise AssertionError("LLM 호출 과다 — 큐가 비었음")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Response(item)


class _ChatNS:
    def __init__(self, completions):
        self.completions = completions


@pytest.fixture()
def fake_llm(monkeypatch):
    holder = {"queue": [], "calls": []}

    class FakeAsyncOpenAI:
        def __init__(self, base_url=None, api_key=None, timeout=None):
            self.base_url = base_url
            self.chat = _ChatNS(FakeCompletions(holder))

    monkeypatch.setattr(
        bootstrap_service.llm, "make_client",
        lambda base_url, api_key_encrypted: FakeAsyncOpenAI(base_url=base_url))
    return holder


@pytest.fixture()
def default_endpoint(client):
    resp = client.post("/api/v1/ai/endpoints", json={
        "name": "기본", "base_url": "http://localhost:1234/v1",
        "api_key": "secret", "default_model": "test-model", "is_default": True})
    assert resp.status_code == 201, resp.text
    return resp.json()


def enqueue_success(holder, idea=GOOD_IDEA, outline=None, world=GOOD_WORLD):
    holder["queue"] = [
        json.dumps(idea, ensure_ascii=False),
        json.dumps(outline if outline is not None else _good_outline(), ensure_ascii=False),
        json.dumps(world, ensure_ascii=False),
    ]


def _db(client):
    return next(iter(client.app.dependency_overrides[get_db]()))


def test_bootstrap_success_creates_full_structure(client, fake_llm, default_endpoint):
    enqueue_success(fake_llm)
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # 응답 스키마·요약
    assert body["project_id"] > 0
    assert body["title"] == GOOD_IDEA["titles"][0]
    assert body["logline"].startswith("소설 속")
    assert body["character_count"] == 4
    assert body["lore_count"] == 8
    assert body["chapter_count"] == 6
    assert body["volume_count"] == 2
    assert body["used_ai"] is True and body["fallback"] is False

    # LLM 3회 호출 확인
    assert len(fake_llm["calls"]) == 3
    assert all(c["model"] == "test-model" for c in fake_llm["calls"])

    db = _db(client)
    project = db.get(Project, body["project_id"])
    # 제목 1번째 + 나머지 후보 memo 보관
    assert project.title == GOOD_IDEA["titles"][0]
    memo = json.loads(project.memo)["bootstrap"]
    assert memo["title_candidates"] == GOOD_IDEA["titles"][1:]
    assert memo["theme"] == "운명과 선택"

    # 회차: 권·sort_order·상태·시놉시스(memo)
    chapters = db.scalars(select(Chapter).where(
        Chapter.project_id == project.id).order_by(Chapter.sort_order)).all()
    assert len(chapters) == 6
    assert [c.sort_order for c in chapters] == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    assert all(c.status == "초고" for c in chapters)
    assert chapters[0].memo.startswith("1-1 첫 문단.")
    assert "[핵심 사건]" in chapters[0].memo
    assert chapters[3].volume == 2

    # 캐릭터: card_json 형태
    chars = db.scalars(select(Character).where(
        Character.project_id == project.id)).all()
    assert len(chars) == 4
    by_name = {c.name: c for c in chars}
    card = by_name["강산협"].card_json
    assert card["spec"] == "chara_card_v2"
    assert card["data"]["name"] == "강산협"
    assert by_name["강산협"].aliases == ["검귀"]

    # 관계: 유효한 쌍만 저장(없는 이름 무효 처리)
    rels = db.scalars(select(Relationship)).all()
    assert len(rels) == 2
    ids = {c.id for c in chars}
    assert all(r.from_character_id in ids and r.to_character_id in ids for r in rels)

    # 로어북: keywords 보존 + 미지정 시 title 자동 보완
    lore = db.scalars(select(LoreEntry).where(
        LoreEntry.project_id == project.id)).all()
    assert len(lore) == 8
    kw = {l.title: l.keywords for l in lore}
    assert kw["천강검기"] == ["천강검기", "검기"]
    assert kw["내단법"] == ["내단법"]  # keywords 누락 → title로 보완
    assert kw["낙하협곡"] == ["낙하협곡"]  # 빈 배열 → title로 보완
    assert {l.category for l in lore} <= {"용어", "장소", "세력", "기타"}


def test_bootstrap_defaults_single_volume_10_chapters(client, fake_llm, default_endpoint):
    idea = dict(GOOD_IDEA)
    enqueue_success(fake_llm, idea=idea,
                    outline=_good_outline(volume_count=1, cpv=10))
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "현대판타지", "premise": "퇴근길에 마왕을 만났다"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["volume_count"] == 1 and body["chapter_count"] == 10
    db = _db(client)
    n = len(db.scalars(select(Chapter).where(
        Chapter.project_id == body["project_id"])).all())
    assert n == 10


def test_bootstrap_broken_json_repaired_once(client, fake_llm, default_endpoint):
    # ①제목 단계만 깨짐 → repair 재시도로 성공 (총 4회 호출)
    broken = "네, 요청하신 결과입니다:\n{ titles: [누락된 따옴표], "
    enqueue_success(fake_llm)
    fake_llm["queue"].insert(0, broken)
    resp = client.post("/api/v1/projects/bootstrap", json={"genre": "로맨스"})
    assert resp.status_code == 200
    assert len(fake_llm["calls"]) == 4  # 실패 1 + 재시도 1 + 나머지 단계 2

    # repair 프롬프트에 이전 출력이 assistant로 포함되는지 확인
    retry_msgs = fake_llm["calls"][1]["messages"]
    assert any(m["role"] == "assistant" and "누락된 따옴표" in m["content"]
               for m in retry_msgs)


def test_bootstrap_total_failure_falls_back_with_502(client, fake_llm, default_endpoint):
    fake_llm["queue"] = ["이것은 JSON이 아닌 일반 텍스트"] * 6  # 3단계 × (본+재시도)
    resp = client.post("/api/v1/projects/bootstrap", json={"genre": "판타지"})
    assert resp.status_code == 502
    body = resp.json()
    assert "폴백" in body["detail"]
    assert body["fallback"] is True and body["used_ai"] is False

    # 그래도 템플릿으로라도 전체 구조가 저장된다
    assert body["chapter_count"] == 10  # 기본값 1권 10화
    assert body["character_count"] >= 4
    assert 8 <= body["lore_count"] <= 12

    db = _db(client)
    project = db.get(Project, body["project_id"])
    assert project.title.startswith("[판타지]")
    assert len(db.scalars(select(Chapter).where(
        Chapter.project_id == project.id)).all()) == 10
    assert len(db.scalars(select(Character).where(
        Character.project_id == project.id)).all()) == 4
    assert len(db.scalars(select(Relationship)).all()) == 3
    assert len(db.scalars(select(LoreEntry).where(
        LoreEntry.project_id == project.id)).all()) == 8


def test_bootstrap_use_ai_false_skips_llm(client, fake_llm):
    # 엔드포인트 없음 + make_client가 호출되면 즉시 실패하도록 모킹됨
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지", "premise": "용을 키우는 병원", "use_ai": False})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["used_ai"] is False and body["fallback"] is True
    assert body["chapter_count"] == 10
    assert fake_llm["calls"] == []  # LLM 호출 없음


def test_bootstrap_use_ai_without_endpoint_returns_400(client, fake_llm):
    resp = client.post("/api/v1/projects/bootstrap", json={"genre": "판타지"})
    assert resp.status_code == 400
    assert "엔드포인트" in resp.json()["detail"]


def test_bootstrap_request_validation(client):
    # genre 필수
    r = client.post("/api/v1/projects/bootstrap", json={})
    assert r.status_code == 422
    # 음수 권수 거부
    r = client.post("/api/v1/projects/bootstrap",
                    json={"genre": "x", "volume_count": 0})
    assert r.status_code == 422

# --------------------------------------------------------------------------
# 회귀: 실제 llm.complete_chat 시그니처를 그대로 통과하는 bootstrap 경로
#
# LM Studio 등 일부 호환 서버는 stream 파라미터와 무관하게 SSE(text/event-stream)
# 로 응답하고, openai SDK 3.x는 이 경우 예외 대신 "원문 str"을 반환한다.
# 과거 complete_chat이 response.choices에 접근해 AttributeError → 500이 발생했다.
# complete_chat의 반환 계약("항상 str")을 모킹 없이 실제 함수로 검증한다.
# --------------------------------------------------------------------------

class _RawStrCompletions:
    """create()가 openai SDK처럼 원문 str을 반환하는 fake (SSE 본문)."""

    def __init__(self, holder):
        self._holder = holder

    async def create(self, **kwargs):
        self._holder["calls"].append(kwargs)
        queue = self._holder["queue"]
        assert queue, "LLM 호출 과다 — 큐가 비었음"
        content = queue.pop(0)
        # SDK가 str을 돌려주는 상황을 재현: 완성된 SSE 본문 문자열을 그대로 반환
        body = "".join([f'data: {{"choices": [{{"delta": {{"content": {json.dumps(content)}}}}}]}}\n\n',
                        "data: [DONE]\n\n"])
        return body


class _RawStrChatNS:
    def __init__(self, completions):
        self.completions = completions


class _RawStrAsyncOpenAI:
    """make_client가 반환하는 것과 동일한 인터페이스의 fake 클라이언트."""

    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.chat = _RawStrChatNS(_RawStrCompletions(_RAW_STR_HOLDER))


_RAW_STR_HOLDER = {"queue": [], "calls": []}


@pytest.fixture()
def raw_str_llm(monkeypatch):
    """make_client만 교체한다 — complete_chat은 실제 구현을 그대로 사용."""
    _RAW_STR_HOLDER["queue"] = []
    _RAW_STR_HOLDER["calls"] = []
    monkeypatch.setattr(
        bootstrap_service.llm, "make_client",
        lambda base_url, api_key_encrypted: _RawStrAsyncOpenAI(base_url=base_url))
    return _RAW_STR_HOLDER


def test_bootstrap_survives_sdk_str_response(client, raw_str_llm, default_endpoint):
    """SDK가 SSE 원문 str을 반환해도 500 없이 AI 생성에 성공한다(회귀)."""
    raw_str_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(), ensure_ascii=False),
        json.dumps(GOOD_WORLD, ensure_ascii=False),
    ]
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["used_ai"] is True and body["fallback"] is False
    assert body["title"] == GOOD_IDEA["titles"][0]
    assert len(raw_str_llm["calls"]) == 3

