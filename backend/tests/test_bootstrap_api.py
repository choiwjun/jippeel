"""POST /api/v1/projects/bootstrap 통합 테스트 — LLM 클라이언트 모킹.

- 정상 경로: 고정 JSON 3회 응답 → 레코드 수·관계·키워드 검증
- 재시도 경로: 깨진 JSON → repair prompt 재시도 성공
- 폴백 경로: 전부 실패 → 규칙 기반 생성 + 502
- use_ai=false: LLM 호출 없이 템플릿 생성
"""
import asyncio
import json

import openai
import pytest
from sqlalchemy import select

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


GOOD_CHARACTERS = {
    "characters": [
        {"name": "강산협", "alias": "검귀", "role": "주연", "appearance": "검은 머리카락",
         "personality": "과묵하지만 1권 후반 도발에 흔들린다", "speech_style": "단문, 호칭은 이름만",
         "background": "멸문한 가문의 생존자. 파천탑 비전을 되찾는 것이 목표. "
                       "멸문의 밤 자신이 문을 열어둔 것이 비밀이다"},
        {"name": "서연화", "alias": "붉은 매화", "role": "조연", "appearance": "붉은 도포",
         "personality": "다혈질이나 약자 앞에서는 무른 모습을 숨긴다", "speech_style": "반말+독설",
         "background": "보물고 도령. 가문 부흥이 목표. 강산협의 비밀을 반쯤 짐작하고 있다"},
        {"name": "무허진인", "alias": "탑주", "role": "조연", "appearance": "백발",
         "personality": "신중하며 서서히 강산협을 후계로 밀어붙인다", "speech_style": "격식체",
         "background": "마탑 주인. 20년 전 멸문의 진상을 알고 있다"},
        {"name": "흑천교주", "alias": "가면", "role": "조연", "appearance": "검은 가면",
         "personality": "냉철하나 약속은 반드시 지킨다", "speech_style": "존댓말",
         "background": "흑천교 수장. 멸문을 명령한 건 정파연맹의 요청이었다는 것이 비밀"},
        {"name": "담영", "alias": "은침", "role": "조연", "appearance": "회색 두건",
         "personality": "장난스럽지만 정보에는 철저하다", "speech_style": "북방 사투리",
         "background": "그림자 조합 정보상. 흑천교와 거래 중 양다리를 걸치고 있다"},
        {"name": "백어린", "alias": "소협", "role": "단역", "appearance": "무명 도복",
         "personality": "소심하지만 검 앞에서는 달라진다", "speech_style": "존댓말",
         "background": "멸문 유생 1명. 강산협의 존재를 감지하고 찾아온다"},
    ],
}

GOOD_RELLORE = {
    "relationships": [
        {"from": "강산협", "to": "서연화", "label": "동문-감시자", "note": "전우로 시작해 1권 후반 서연화가 강산협의 비밀을 알아채고 따돌림당한다. 2권 화해 분기"},
        {"from": "강산협", "to": "무허진인", "label": "제자-스승", "note": "비전을 전수받지만 진상 일부를 숨긴다. 후반 거짓이 드러나 결별 위기"},
        {"from": "강산협", "to": "흑천교주", "label": "사냥감-사냥꾼", "note": "교주는 강산협을 흑천교로 끌으려 하고, 강산협은 증오와 이해 사이에서 흔들린다"},
        {"from": "강산협", "to": "담영", "label": "고객-정보상", "note": "거래 관계로 시작, 후반 담영이 쌍방 거래 사실을 흑천교에 팔며 배신"},
        {"from": "강산협", "to": "백어린", "label": "피보호자-보호자", "note": "멸문 유생임을 알고 숨겨준다. 그녀의 존재가 강산협의 비밀을 흔드는 열쇠"},
        {"from": "서연화", "to": "담영", "label": "거래처-첩자", "note": "서로 이용하며 강산협 정보를 사고판다. 1권 끝 서로를 속였다는 걸 깨닫는다"},
        {"from": "무허진인", "to": "흑천교주", "label": "휴전-비밀동약", "note": "20년 전 멸문 밤의 당사자들. 서로의 약점을 쥐고 휴전 중이다"},
        {"from": "흑천교주", "to": "백어린", "label": "추격자-도주자", "note": "교주는 유생 생환 명단의 마지막 한 명인 그녀를 추적한다"},
        {"from": "강산협", "to": "없는이름", "label": "유령", "note": "무효 쌍 — 저장되면 안 된다"},
    ],
    "lore_entries": [
        {"category": "용어", "title": "천강검기", "content": "하늘 기운을 끌어 쓰는 검술. 정파연맹 최상위 검가만 전수받는다. "
         "멸문된 백령검가가 원전이었다는 사실은 1권 3화에서 드러난다", "keywords": ["천강검기", "검기"]},
        {"category": "장소", "title": "파천탑", "content": "무허진인이 다스리는 아홉 층 탑. 1화 강산협이 입장하는 관문. "
         "최상층 봉인고에 멸문의 증거가 잠들어 있다", "keywords": ["파천탑", "탑"]},
        {"category": "세력", "title": "흑천교", "content": "공식적으로 마도 종파로 지정됐으나 실제로는 정파연맹의 더러운 일을 대행한다. "
         "교주는 이 모순을 알고 연맹을 협박할 단서를 모은다", "keywords": ["흑천교", "교주"]},
        {"category": "용어", "title": "내단법", "content": None},
        {"category": "장소", "title": "낙하협곡", "content": "백령검가 폐허가 잠긴 협곡. 1권 5화 최종 결전지다", "keywords": ["낙하협곡", "협곡"]},
        {"category": "세력", "title": "정파연맹", "content": "정통 연합의 상층부. 20년 전 멸문 명령의 배후다", "keywords": ["정파연맹", "연맹"]},
        {"category": "기타", "title": "대가의 법칙", "content": "모든 힘엔 대가가 따른다. 강산협의 검읽기도 매번 기억의 고통을 대가로 치른다",
         "keywords": ["대가"]},
        {"category": "기타", "title": "예언의 조각", "content": "흩어진 예언. 백어린이 그 마지막 조각이다", "keywords": ["예언"]},
        {"category": "용어", "title": "검식(檢識)", "content": "검의 기억을 읽는 흑천교 금술. 강산협의 재능과 흑천교주의 야망을 잇는 접점이다",
         "keywords": ["검식"]},
        {"category": "장소", "title": "회명루", "content": "목진백이 정보를 거래하는 누각. 2화 배경이며 담영과 서연화의 거래도 이곳에서 벌어진다",
         "keywords": ["회명루"]},
        {"category": "세력", "title": "그림자 조합", "content": "담영이 속한 정보 조합. 정파연맹과 흑천교 양쪽에 팔아넘기는 이중 계약이 1권 후반 폭탄이 된다",
         "keywords": ["그림자 조합", "조합"]},
        {"category": "기타", "title": "멸문의 밤", "content": "20년 전 백령검가가 하루아침에 지워진 사건. 강산협의 비밀과 교주의 죄책, 무허진인의 침묵이 모두 이 밤에서 나온다",
         "keywords": ["멸문", "백령검가"]},
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


def enqueue_success(holder, idea=GOOD_IDEA, outline=None,
                    characters=GOOD_CHARACTERS, rellore=GOOD_RELLORE,
                    supporting=None):
    queue = [
        json.dumps(idea, ensure_ascii=False),
        json.dumps(outline if outline is not None else _good_outline(), ensure_ascii=False),
        json.dumps(characters, ensure_ascii=False),
    ]
    if supporting is not None:
        queue.append(json.dumps(supporting, ensure_ascii=False))
    queue.append(json.dumps(rellore, ensure_ascii=False))
    holder["queue"] = queue


from tests.conftest import _db


def test_bootstrap_transport_timeout_does_not_trigger_json_repair(monkeypatch):
    """SDK transport timeout은 JSON 형식 오류가 아니므로 repair하지 않는다."""
    calls = 0

    async def raise_timeout(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise openai.APITimeoutError(request=None)

    monkeypatch.setattr(bootstrap_service.llm, "complete_chat", raise_timeout)

    with pytest.raises(bootstrap_service.BootstrapAIError, match="AI provider 시간 초과"):
        asyncio.run(bootstrap_service._call_json(
            object(), "test-model", [{"role": "user", "content": "{}"}]))

    assert calls == 1


def test_bootstrap_repair_transport_timeout_is_not_reported_as_json_failure(monkeypatch):
    """repair 요청의 SDK timeout도 JSON 오류로 재분류하지 않는다."""
    calls = 0

    async def malformed_then_timeout(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return "not json"
        raise openai.APITimeoutError(request=None)

    monkeypatch.setattr(bootstrap_service.llm, "complete_chat", malformed_then_timeout)

    with pytest.raises(bootstrap_service.BootstrapAIError, match="AI provider 시간 초과"):
        asyncio.run(bootstrap_service._call_json(
            object(), "test-model", [{"role": "user", "content": "{}"}]))

    assert calls == 2


def test_bootstrap_supporting_transport_timeout_skips_only_one_volume(
        client, fake_llm, default_endpoint):
    """권별 transport timeout은 repair하지 않고 다음 권·최종 단계로 진행한다."""
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(3, 3), ensure_ascii=False),
        json.dumps(GOOD_CHARACTERS, ensure_ascii=False),
        openai.APITimeoutError(request=None),
        json.dumps({"characters": [{"name": "이권인", "role": "조연"}]}),
        json.dumps({"characters": [{"name": "삼권인", "role": "단역"}]}),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]

    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 3, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["used_ai"] is True and body["fallback"] is False
    assert body["character_count"] == 8
    assert len(fake_llm["calls"]) == 7


def test_bootstrap_supporting_cast_per_volume(client, fake_llm, default_endpoint):
    """각 권이 독립 호출되고 응답 인물의 first_volume은 요청 권으로 고정된다."""
    supporting = [
        {"characters": [
            {"name": "목진백", "role": "조연", "first_volume": 99,
             "appearance": "흰 수염", "personality": "느긋함", "speech_style": "느린 말투",
             "background": "1권 정보원"},
        ]},
        {"characters": [
            {"name": "설무영", "role": "단역", "first_volume": 1,
             "appearance": "백의", "personality": "냉담", "speech_style": "반말",
             "background": "2권 조력자"},
        ]},
        {"characters": [
            {"name": "하오문주", "role": "조연", "first_volume": 1,
             "appearance": "거구", "personality": "호탕", "speech_style": "호쾌한 반말",
             "background": "3권 조력자"},
        ]},
    ]
    enqueue_success(fake_llm, outline=_good_outline(3, 3))
    fake_llm["queue"][3:3] = [json.dumps(item, ensure_ascii=False) for item in supporting]
    # 권별 호출은 서로 다른 권 앵커와 first_volume을 전달해야 한다.
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 3, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(fake_llm["calls"]) == 7
    assert body["character_count"] == 9
    db = _db(client)
    chars = db.scalars(select(Character).where(
        Character.project_id == body["project_id"])).all()
    by_name = {c.name: c for c in chars}
    assert [by_name[name].card_json["data"]["first_volume"]
            for name in ("목진백", "설무영", "하오문주")] == [1, 2, 3]
    supporting_prompts = [call["messages"][-1]["content"] for call in fake_llm["calls"][3:6]]
    assert all(f"first_volume은 반드시 {volume}" in prompt
               for volume, prompt in enumerate(supporting_prompts, 1))
    assert all(f"대상 권: {volume}권" in prompt
               for volume, prompt in enumerate(supporting_prompts, 1))
    assert by_name["강산협"].role == "주연"


def test_bootstrap_two_volumes_skips_supporting_call(
        client, fake_llm, default_endpoint):
    """2권 이하면 기존 비용 경계에 따라 권별 조연 호출을 하지 않는다."""
    enqueue_success(fake_llm)
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    assert len(fake_llm["calls"]) == 4


def test_bootstrap_supporting_failure_isolated_to_one_volume(
        client, fake_llm, default_endpoint):
    """한 권 조연 호출 실패는 다른 권과 핵심 캐스트를 막지 않는다."""
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(3, 3), ensure_ascii=False),
        json.dumps(GOOD_CHARACTERS, ensure_ascii=False),
        "not json at all", "still not json",  # 1권 실패 및 repair
        json.dumps({"characters": [{"name": "이권인", "role": "조연"}]}),
        json.dumps({"characters": [{"name": "삼권인", "role": "단역"}]}),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 3, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["character_count"] == 8
    assert len(fake_llm["calls"]) == 8


def test_bootstrap_short_cast_triggers_supplement_call(
        client, fake_llm, default_endpoint):
    """인원 부족 시 전체 재생성이 아니라 부족분만 보충하는 호출을 한다."""
    short_cast = {"characters": GOOD_CHARACTERS["characters"][:4]}
    supplement = {"characters": [
        {"name": "남궁세가주", "role": "조연", "appearance": "중년의 위엄",
         "personality": "온화하나 계산적", "speech_style": "존댓말",
         "background": "남궁세가 수장. 멸문 당시 침묵한 대가를 갚으려 한다"},
        {"name": "혈랑", "role": "단역", "appearance": "흉터투성이",
         "personality": "광폭", "speech_style": "거친 반말",
         "background": "백어린을 추적하는 흑천교 추격조"},
    ]}
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(), ensure_ascii=False),
        json.dumps(short_cast, ensure_ascii=False),
        json.dumps(supplement, ensure_ascii=False),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["used_ai"] is True and body["fallback"] is False
    assert len(fake_llm["calls"]) == 5
    assert body["character_count"] == 6

    # 보충 호출은 기존 인물을 assistant 메시지로 보존하고 부족 인원만 요청한다
    retry_msgs = fake_llm["calls"][3]["messages"]
    assistant = next(m for m in retry_msgs if m["role"] == "assistant")
    for name in ("강산협", "서연화", "무허진인", "흑천교주"):
        assert name in assistant["content"]
    assert "4명" in retry_msgs[-1]["content"]
    assert "2명" in retry_msgs[-1]["content"]

    # 기존 인물 + 보충 인물이 모두 저장된다
    db = _db(client)
    chars = db.scalars(select(Character).where(
        Character.project_id == body["project_id"])).all()
    assert {c.name for c in chars} == {
        "강산협", "서연화", "무허진인", "흑천교주", "남궁세가주", "혈랑"}


def test_bootstrap_supplement_dedupes_names_returned_again(
        client, fake_llm, default_endpoint):
    """보충 응답이 기존 이름을 반복해도 중복 저장하지 않는다."""
    short_cast = {"characters": GOOD_CHARACTERS["characters"][:4]}
    supplement = {"characters": [
        dict(GOOD_CHARACTERS["characters"][0]),  # 기존 이름 반복 — 버려야 함
        {"name": "혈랑", "role": "단역"},
    ]}
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(), ensure_ascii=False),
        json.dumps(short_cast, ensure_ascii=False),
        json.dumps(supplement, ensure_ascii=False),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    assert resp.json()["character_count"] == 5


def test_bootstrap_supplement_failure_keeps_partial_cast(
        client, fake_llm, default_endpoint):
    """보충 호출 실패는 전체 폴백이 아니라 기존 캐스트 유지로 끝난다."""
    short_cast = {"characters": GOOD_CHARACTERS["characters"][:4]}
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(), ensure_ascii=False),
        json.dumps(short_cast, ensure_ascii=False),
        "not json", "still not json",  # 보충 호출 + repair 모두 실패
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["used_ai"] is True and body["fallback"] is False
    assert body["character_count"] == 4
    assert len(fake_llm["calls"]) == 6


def test_bootstrap_stage_events_cover_retry_and_supporting_cast(fake_llm):
    """on_stage가 characters-retry·권별 조연 단계를 started/done으로 남긴다."""
    short_cast = {"characters": GOOD_CHARACTERS["characters"][:4]}
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(3, 3), ensure_ascii=False),
        json.dumps(short_cast, ensure_ascii=False),
        json.dumps({"characters": [{"name": "보충인물", "role": "조연"}]},
                   ensure_ascii=False),
        json.dumps({"characters": [{"name": "일권인", "role": "조연"}]}),
        json.dumps({"characters": [{"name": "이권인", "role": "조연"}]}),
        json.dumps({"characters": [{"name": "삼권인", "role": "단역"}]}),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    events = []

    async def on_stage(stage, status, label):
        events.append((stage, status))

    client_obj = bootstrap_service.llm.make_client("http://localhost", None)
    structure = asyncio.run(bootstrap_service.generate_structure(
        "무협", None, "웹소설식 긴 제목", 3, 3, client_obj, "test-model",
        on_stage=on_stage))

    assert [e for e in events if e[1] == "started"] == [
        ("idea", "started"), ("outline", "started"), ("characters", "started"),
        ("characters-retry", "started"),
        ("supporting-cast-volume-1", "started"),
        ("supporting-cast-volume-2", "started"),
        ("supporting-cast-volume-3", "started"),
        ("relations-lore", "started"),
    ]
    for stage in ("characters", "characters-retry", "relations-lore",
                  "supporting-cast-volume-1", "supporting-cast-volume-2",
                  "supporting-cast-volume-3"):
        assert (stage, "done") in events
    merged_names = {c["name"] for c in structure["characters"]}
    assert "보충인물" in merged_names and len(merged_names) == 5


def test_bootstrap_duplicate_names_count_as_short_cast(
        client, fake_llm, default_endpoint):
    """1차 응답의 중복 이름은 인원 수에 넣지 않고 보충 호출을 발동한다."""
    dup_cast = {"characters": GOOD_CHARACTERS["characters"][:4]
                + [GOOD_CHARACTERS["characters"][0]]}  # 5항목이나 고유 4명
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(), ensure_ascii=False),
        json.dumps(dup_cast, ensure_ascii=False),
        json.dumps({"characters": [{"name": "보충인물", "role": "조연"}]}),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    assert len(fake_llm["calls"]) == 5  # 보충 호출 발동
    assert resp.json()["character_count"] == 5


def test_bootstrap_supplement_failure_emits_failed_stage(fake_llm):
    """보충 호출 실패는 characters-retry failed 이벤트로 끝난다."""
    short_cast = {"characters": GOOD_CHARACTERS["characters"][:4]}
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(), ensure_ascii=False),
        json.dumps(short_cast, ensure_ascii=False),
        "not json", "still not json",
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    events = []

    async def on_stage(stage, status, label):
        events.append((stage, status))

    client_obj = bootstrap_service.llm.make_client("http://localhost", None)
    structure = asyncio.run(bootstrap_service.generate_structure(
        "무협", None, "웹소설식 긴 제목", 2, 3, client_obj, "test-model",
        on_stage=on_stage))

    assert ("characters-retry", "started") in events
    assert ("characters-retry", "failed") in events
    assert ("relations-lore", "done") in events  # 이후 단계는 계속 진행
    assert len(structure["characters"]) == 4
    assert len(fake_llm["calls"]) == 6


def test_bootstrap_full_cast_skips_supplement_call(fake_llm):
    """인원이 충분하면 보충 호출·characters-retry 단계가 없다."""
    fake_llm["queue"] = [
        json.dumps(GOOD_IDEA, ensure_ascii=False),
        json.dumps(_good_outline(), ensure_ascii=False),
        json.dumps(GOOD_CHARACTERS, ensure_ascii=False),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    events = []

    async def on_stage(stage, status, label):
        events.append((stage, status))

    client_obj = bootstrap_service.llm.make_client("http://localhost", None)
    asyncio.run(bootstrap_service.generate_structure(
        "무협", None, "웹소설식 긴 제목", 2, 3, client_obj, "test-model",
        on_stage=on_stage))

    assert len(fake_llm["calls"]) == 4
    assert all(stage != "characters-retry" for stage, _ in events)


def test_bootstrap_prompts_capture_adaptive_story_and_character_design(fake_llm):
    idea = bootstrap_service._idea_messages(
        "무협", "몰락한 세가를 재건하는 회귀자", "웹소설식 긴 제목")
    outline = bootstrap_service._outline_messages(
        "무협", {"titles": ["세가의 회귀자"], "logline": "세가를 재건한다", "theme": "대가"}, 2, 3)
    characters = bootstrap_service._characters_messages(
        "무협", {"titles": ["세가의 회귀자"], "logline": "세가를 재건한다", "theme": "대가",
                  "protagonist_name": "강진우"}, "1권 개요")
    relations_lore = bootstrap_service._relations_lore_messages(
        "무협", {"titles": ["세가의 회귀자"], "logline": "세가를 재건한다", "theme": "대가"},
        "1권 개요", ["강진우", "서연"])

    all_text = "\n".join(
        str(message["content"])
        for messages in (idea, outline, characters, relations_lore)
        for message in messages
    )
    for keyword in (
        "독자 약속", "결핍", "전문성", "반복 가능한 에피소드",
        "목표·장애물·선택·결과", "상태 변화", "키워드 목록",
    ):
        assert keyword in all_text
    character_text = "\n".join(str(message["content"]) for message in characters)
    assert "라이벌 또는 스승" in character_text
    assert "대가" in character_text
    assert "관계와 조직" in character_text


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
    assert body["character_count"] == 6
    assert body["lore_count"] == 12
    assert body["chapter_count"] == 6
    assert body["volume_count"] == 2
    assert body["used_ai"] is True and body["fallback"] is False

    # LLM 4회 호출 확인(제목·목차·캐릭터·관계/로어)
    assert len(fake_llm["calls"]) == 4
    assert all(c["model"] == "gpt-5.6-luna" for c in fake_llm["calls"])

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
    assert len(chars) == 6
    by_name = {c.name: c for c in chars}
    card = by_name["강산협"].card_json
    assert card["spec"] == "chara_card_v2"
    assert card["data"]["name"] == "강산협"
    assert by_name["강산협"].aliases == ["검귀"]

    # 관계: 유효한 쌍만 저장(없는 이름 무효 처리)
    rels = db.scalars(select(Relationship)).all()
    assert len(rels) == 8
    ids = {c.id for c in chars}
    assert all(r.from_character_id in ids and r.to_character_id in ids for r in rels)

    # 로어북: keywords 보존 + 미지정 시 title 자동 보완
    lore = db.scalars(select(LoreEntry).where(
        LoreEntry.project_id == project.id)).all()
    assert len(lore) == 12
    kw = {l.title: l.keywords for l in lore}
    assert kw["천강검기"] == ["천강검기", "검기"]
    assert kw["내단법"] == ["내단법"]  # keywords 누락 → title로 보완
    assert kw["낙하협곡"] == ["낙하협곡", "협곡"]
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


def test_bootstrap_uses_bounded_reasoning_budget(client, fake_llm, default_endpoint):
    """대형 구조 JSON은 provider의 xhigh 기본값을 그대로 물려받지 않는다.

    xhigh 추론을 제목·목차·캐릭터·세계관에 연속 적용하면 부트스트랩 전체가
    수분 이상 지연되어 AI 결과 대신 템플릿 폴백으로 끝날 수 있다.
    """
    enqueue_success(fake_llm, outline=_good_outline(volume_count=1, cpv=1))

    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지", "volume_count": 1, "chapters_per_volume": 1})

    assert resp.status_code == 200, resp.text
    assert resp.json()["used_ai"] is True
    assert {call["reasoning_effort"] for call in fake_llm["calls"]} == {"high"}


def test_generate_structure_preserves_explicit_reasoning_effort(fake_llm):
    """서비스 함수의 명시적 reasoning 계약은 라우터의 전용 override와 분리한다."""
    enqueue_success(fake_llm, outline=_good_outline(volume_count=1, cpv=1))

    client_obj = bootstrap_service.llm.make_client("http://localhost", None)
    asyncio.run(bootstrap_service.generate_structure(
        "판타지", None, "웹소설식 긴 제목", 1, 1,
        client_obj, "test-model", reasoning_effort="medium"))

    assert {call["reasoning_effort"] for call in fake_llm["calls"]} == {"medium"}


def test_bootstrap_broken_json_repaired_once(client, fake_llm, default_endpoint):
    # ①제목 단계만 깨짐 → repair 재시도로 성공 (총 4회 호출)
    broken = "네, 요청하신 결과입니다:\n{ titles: [누락된 따옴표], "
    enqueue_success(fake_llm)
    fake_llm["queue"].insert(0, broken)
    resp = client.post("/api/v1/projects/bootstrap", json={"genre": "로맨스"})
    assert resp.status_code == 200
    assert len(fake_llm["calls"]) == 5  # 실패 1 + 재시도 1 + 나머지 단계 3

    # repair 프롬프트에 이전 출력이 assistant로 포함되는지 확인
    retry_msgs = fake_llm["calls"][1]["messages"]
    assert any(m["role"] == "assistant" and "누락된 따옴표" in m["content"]
               for m in retry_msgs)


def test_bootstrap_total_failure_falls_back_with_502(client, fake_llm, default_endpoint):
    fake_llm["queue"] = ["이것은 JSON이 아닌 일반 텍스트"] * 8  # 4단계 × (본+재시도)
    resp = client.post("/api/v1/projects/bootstrap", json={"genre": "판타지"})
    assert resp.status_code == 502
    body = resp.json()
    assert "폴백" in body["detail"]
    assert body["fallback"] is True and body["used_ai"] is False

    # 그래도 템플릿으로라도 전체 구조가 저장된다
    assert body["chapter_count"] == 10  # 기본값 1권 10화
    assert body["character_count"] >= 4
    assert 12 <= body["lore_count"] <= 18

    db = _db(client)
    project = db.get(Project, body["project_id"])
    assert project.title.startswith("[판타지]")
    assert len(db.scalars(select(Chapter).where(
        Chapter.project_id == project.id)).all()) == 10
    assert len(db.scalars(select(Character).where(
        Character.project_id == project.id)).all()) == 4
    assert len(db.scalars(select(Relationship)).all()) == 3
    assert len(db.scalars(select(LoreEntry).where(
        LoreEntry.project_id == project.id)).all()) == 12


def test_bootstrap_stream_hides_unexpected_exception_details(client, monkeypatch):
    async def fail(*_args, **_kwargs):
        raise RuntimeError("provider secret should not reach the client")

    monkeypatch.setattr(bootstrap_service, "generate_structure", fail)
    response = client.post("/api/v1/projects/bootstrap/stream", json={
        "genre": "판타zia",
        "use_ai": True,
    })

    assert response.status_code == 200
    assert "provider secret should not reach the client" not in response.text
    assert "작품 생성 중 서버 오류가 발생했습니다." in response.text


def test_bootstrap_new_project_chapters_start_with_empty_manuscripts(
    client, fake_llm
):
    response = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지", "premise": "새 작품", "use_ai": False,
    })
    assert response.status_code == 200, response.text
    project_id = response.json()["project_id"]
    db = _db(client)
    chapters = db.scalars(
        select(Chapter).where(Chapter.project_id == project_id)
    ).all()
    assert chapters
    assert all(chapter.content_md == "" for chapter in chapters)
    assert all(chapter.revision == 0 for chapter in chapters)


def test_bootstrap_use_ai_false_skips_llm(client, fake_llm):
    # 엔드포인트 없음 + make_client가 호출되면 즉시 실패하도록 모킹됨
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "판타지", "premise": "용을 키우는 병원", "use_ai": False})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["used_ai"] is False and body["fallback"] is True
    assert body["chapter_count"] == 10
    assert fake_llm["calls"] == []  # LLM 호출 없음


def test_bootstrap_rejects_invalid_oauth_bridge_configuration(client, fake_llm, monkeypatch):
    monkeypatch.setenv("JIPPEEL_GPT_OAUTH_BASE_URL", "https://example.invalid/v1")

    resp = client.post("/api/v1/projects/bootstrap", json={"genre": "판타지"})

    assert resp.status_code == 503
    assert "localhost" in resp.json()["detail"]
    assert fake_llm["calls"] == []


def test_bootstrap_request_validation(client):
    # genre 필수
    r = client.post("/api/v1/projects/bootstrap", json={})
    assert r.status_code == 422
    # 음수 권수 거부
    r = client.post("/api/v1/projects/bootstrap",
                    json={"genre": "x", "volume_count": 0})
    assert r.status_code == 422


def test_bootstrap_llm_waits_past_legacy_timeout_without_cutting_call(monkeypatch):
    """생성 응답이 늦어도 애플리케이션 timeout으로 provider 호출을 끊지 않는다."""
    async def returns_late(*_args, **_kwargs):
        await asyncio.sleep(0.03)
        return json.dumps(GOOD_IDEA, ensure_ascii=False)

    monkeypatch.setattr(bootstrap_service, "BOOTSTRAP_CALL_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(bootstrap_service.llm, "complete_chat", returns_late)

    result = asyncio.run(bootstrap_service._call_json(
        object(), "test-model", [{"role": "user", "content": "test"}]))

    assert result == GOOD_IDEA

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
        json.dumps(GOOD_CHARACTERS, ensure_ascii=False),
        json.dumps(GOOD_RELLORE, ensure_ascii=False),
    ]
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["used_ai"] is True and body["fallback"] is False
    assert body["title"] == GOOD_IDEA["titles"][0]
    assert len(raw_str_llm["calls"]) == 4


def test_bootstrap_protagonist_name_enforced_across_calls(client, fake_llm, default_endpoint):
    """고도화 G-002 — 콜 1에서 확정한 주인공 이름이 콜 2(목차)·콜 3(캐릭터)에
    강제 전달되는지 검증한다(이름 교차 불일치 해소)."""
    idea = dict(GOOD_IDEA, protagonist_name="강산협")
    enqueue_success(fake_llm, idea=idea)
    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "무협", "volume_count": 2, "chapters_per_volume": 3})
    assert resp.status_code == 200, resp.text

    calls = fake_llm["calls"]
    assert len(calls) == 4
    outline_user = calls[1]["messages"][-1]["content"]
    characters_user = calls[2]["messages"][-1]["content"]
    idea_user = calls[0]["messages"][-1]["content"]
    # 콜 1에서 protagonist_name을 요구
    assert "protagonist_name" in idea_user
    # 콜 2·3에 강제 규칙 전달
    assert "강산협" in outline_user and "다른 이름 금지" in outline_user
    assert "반드시 \"강산협\"" in characters_user

    # 프로젝트 memo에 주인공 이름 보관
    body = resp.json()
    db = _db(client)
    project = db.get(Project, body["project_id"])
    memo = json.loads(project.memo)["bootstrap"]
    assert memo["protagonist_name"] == "강산협"


def test_bootstrap_outline_anchors_are_carried_to_character_and_lore_calls(
        client, fake_llm, default_endpoint):
    """콜 2 목차의 장소·사건명이 콜 3·4의 정본 컨텍스트로 전달된다."""
    outline = {
        "volumes": [{
            "volume": 1,
            "title": "폐선의 시작",
            "chapters": [{
                "order": 1,
                "title": "첫 사냥의 준비",
                "synopsis": (
                    "서도윤은 은하역 폐선로의 환기구를 조사하며 "
                    "청람 게이트의 개방 흔적을 찾는다."),
                "key_event": "은하역 폐선로 선점 계획 확정",
            }],
        }],
    }
    enqueue_success(fake_llm, outline=outline)

    resp = client.post("/api/v1/projects/bootstrap", json={
        "genre": "현대판타지", "volume_count": 1, "chapters_per_volume": 1})
    assert resp.status_code == 200, resp.text

    calls = fake_llm["calls"]
    characters_user = calls[2]["messages"][-1]["content"]
    rellore_user = calls[3]["messages"][-1]["content"]
    for prompt in (characters_user, rellore_user):
        assert "은하역 폐선로" in prompt
        assert "청람 게이트" in prompt
        assert "목차가 정본" in prompt


def test_bootstrap_outline_anchor_summary_has_a_hard_size_cap():
    """대형 목차도 후속 LLM 콜용 앵커 블록이 고정 상한을 넘지 않는다."""
    chapters = [
        bootstrap_service.OutlineChapter(
            volume=1, order=index + 1, sort_order=float(index),
            title=f"회차 {index + 1}",
            synopsis="은하역 폐선로 " + ("설명 " * 500),
            key_event="핵심 사건 " + ("사건 " * 200),
        )
        for index in range(400)
    ]

    summary = bootstrap_service._outline_anchor_summary(chapters, {1: "대형 권"})

    assert len(summary) <= bootstrap_service.OUTLINE_ANCHOR_MAX_CHARS
    assert "목차 앵커 생략" in summary


def test_stage_timeout_is_disabled_for_generation_stages():
    """생성 stage는 provider가 끝날 때까지 기다리고 애플리케이션 timeout을 쓰지 않는다."""
    from app.services.bootstrap import (_stage_timeout,
                                        BOOTSTRAP_CALL_TIMEOUT_SECONDS,
                                        BOOTSTRAP_OUTLINE_TIMEOUT_SECONDS)
    assert _stage_timeout("outline") is None
    assert _stage_timeout("idea") is None
    assert _stage_timeout("characters") is None
    assert BOOTSTRAP_CALL_TIMEOUT_SECONDS is None
    assert BOOTSTRAP_OUTLINE_TIMEOUT_SECONDS is None
