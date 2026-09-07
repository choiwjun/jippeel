"""POST /ai/generate — SSE 스트리밍 테스트 (openai 클라이언트 모킹, FR-405·408)."""
import json

import httpx
import openai
import pytest
from sqlalchemy import select

from app.database import get_db
from app.models import AiEndpoint
from app.routers import ai_panel


# ---------- fake openai client ----------
class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, chunks=None, exc=None):
        self._chunks = chunks or []
        self._exc = exc

    async def create(self, **kwargs):
        if self._exc is not None:
            raise self._exc
        async def _gen():
            for c in self._chunks:
                yield c
        return _gen()


class _ChatNS:
    def __init__(self, completions):
        self.completions = completions


DEFAULT_CHUNKS = ["안녕", "하세요", "반갑습니다"]


class FakeAsyncOpenAI:
    """openai.AsyncOpenAI와 동일한 호출 표면만 흉내낸다.

    exc/chunks는 외부에서 전달받은 공유 spec에 저장한다 — 라우터가
    make_client를 호출하기 전에 설정한 에러 경로도 이후 생성되는
    클라이언트 인스턴스에 그대로 적용된다.
    """

    def __init__(self, base_url=None, api_key=None, timeout=None, spec=None):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.last_kwargs = None
        self._spec = spec if spec is not None else {"chunks": None, "exc": None}
        self._refresh()

    def _refresh(self):
        if self._spec["exc"] is not None:
            self.chat = _ChatNS(_Completions(exc=self._spec["exc"]))
        else:
            _set_stream(self, self._spec["chunks"] or DEFAULT_CHUNKS)

    def set_chunks(self, chunks):
        self._spec["chunks"] = chunks
        self._spec["exc"] = None
        self._refresh()

    def set_exc(self, exc):
        self._spec["exc"] = exc
        self._refresh()


def _set_stream(client, chunks):
    async def create(**kwargs):
        client.last_kwargs = kwargs
        async def _gen():
            for c in chunks:
                yield _Chunk(c)
        return _gen()
    client.chat = _ChatNS(_Completions())
    client.chat.completions.create = create


@pytest.fixture()
def fake_llm(monkeypatch):
    spec = {"chunks": list(DEFAULT_CHUNKS), "exc": None}
    holder = {"client": None}

    def _make_client(base_url, api_key_encrypted):
        c = FakeAsyncOpenAI(base_url=base_url, api_key="decrypted", spec=spec)
        holder["client"] = c
        return c

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    # 라우터가 make_client를 부르기 전(set_exc 사전 설정)에도
    # fake_llm["client"]가 유효하도록 대표 인스턴스를 미리 만들어 둔다.
    # POST 시 라우터가 새 인스턴스로 교체하지만 spec을 공유하므로
    # 설정·last_kwargs 확인 모두 유지된다.
    holder["client"] = _make_client("http://localhost:1234/v1", "sk-local")
    return holder


@pytest.fixture()
def endpoint_with_preset(client):
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://localhost:1234/v1",
        "api_key": "secret", "default_model": "m-1"}).json()
    preset = client.post("/api/v1/ai/presets", json={
        "name": "요약", "template_text": "요약해줘",
        "context_flags": ["chapter"]}).json()
    project = client.post("/api/v1/projects", json={"title": "p"}).json()
    chapter = client.post(f"/api/v1/projects/{project['id']}/chapters", json={}).json()
    client.put(f"/api/v1/chapters/{chapter['id']}/content",
               json={"content_md": "제1장 본문"})
    return {"endpoint_id": ep["id"], "preset_id": preset["id"],
            "chapter_id": chapter["id"]}


def _parse_sse(text):
    events = []
    # sse-starlette는 CRLF(\r\n)로 전송한다 — 파싱 전 정규화
    text = text.replace("\r\n", "\n")
    for block in text.split("\n\n"):
        ev, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                ev = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = line.split(":", 1)[1].strip()
        if ev:
            events.append((ev, data))
    return events


def test_generate_streams_deltas(client, fake_llm, endpoint_with_preset):
    payload = {
        "endpoint_id": endpoint_with_preset["endpoint_id"],
        "preset_id": endpoint_with_preset["preset_id"],
        "context": {"chapter_id": endpoint_with_preset["chapter_id"]},
        "params": {"temperature": 0.5},
    }
    resp = client.post("/api/v1/ai/generate", json=payload)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert kinds[0] == "start"
    assert kinds[-1] == "done"

    deltas = "".join(json.loads(d)["delta"] for e, d in events if e == "message")
    assert deltas == "안녕하세요반갑습니다"

    # 프롬프트에 컨텍스트(회차 본문)와 지시가 포함되었는지 + 스트리밍 파라미터 확인
    sent = fake_llm["client"].last_kwargs
    assert sent["stream"] is True
    assert sent["model"] == "m-1"
    assert abs(sent["temperature"] - 0.5) < 1e-9
    user_msg = sent["messages"][-1]["content"]
    assert "제1장 본문" in user_msg and "요약해줘" in user_msg
    # 모킹 클라이언트가 복호화된 키로 만들어졌는지(base_url 전달) 확인
    assert fake_llm["client"].base_url == "http://localhost:1234/v1"


def test_generate_timeout_error_becomes_sse_error_event(client, fake_llm, endpoint_with_preset):
    request = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")
    fake_llm["client"].set_exc(openai.APITimeoutError(request=request))

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint_with_preset["endpoint_id"],
        "prompt_override": "요약해줘"})
    events = _parse_sse(resp.text)
    errors = [(e, d) for e, d in events if e == "error"]
    assert len(errors) == 1
    detail = json.loads(errors[0][1])["detail"]
    assert "시간 초과" in detail  # FR-408 사용자 안내


def test_generate_connection_error_sse(client, fake_llm, endpoint_with_preset):
    request = httpx.Request("POST", "http://x/v1")
    fake_llm["client"].set_exc(
        openai.APIConnectionError(message="연결 실패", request=request))

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint_with_preset["endpoint_id"],
        "prompt_override": "요약해줘"})
    errors = [(e, d) for e, d in _parse_sse(resp.text) if e == "error"]
    assert "연결할 수 없습니다" in json.loads(errors[0][1])["detail"]


def test_generate_auth_error_sse(client, fake_llm, endpoint_with_preset):
    request = httpx.Request("POST", "http://x/v1")
    response = httpx.Response(401, request=request)
    fake_llm["client"].set_exc(openai.AuthenticationError(
        message="bad key", response=response, body=None))

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": endpoint_with_preset["endpoint_id"],
        "prompt_override": "요약해줘"})
    errors = [(e, d) for e, d in _parse_sse(resp.text) if e == "error"]
    assert "인증 실패" in json.loads(errors[0][1])["detail"]


def test_generate_model_resolution(client, fake_llm, endpoint_with_preset):
    # params.model이 default_model보다 우선, 둘 다 없으면 400
    payload = {"endpoint_id": endpoint_with_preset["endpoint_id"],
               "prompt_override": "hi", "params": {"model": "override-m"}}
    client.post("/api/v1/ai/generate", json=payload)
    assert fake_llm["client"].last_kwargs["model"] == "override-m"

    from app.database import get_db
    db = next(iter(client.app.dependency_overrides[get_db]()))
    row = db.scalars(select(AiEndpoint)).one()
    row.default_model = None
    db.commit()
    payload2 = {"endpoint_id": endpoint_with_preset["endpoint_id"],
                "prompt_override": "hi"}
    r = client.post("/api/v1/ai/generate", json=payload2)
    assert r.status_code == 400



def test_auto_lore_injects_matched_entries_only(client, fake_llm):
    """auto_lore=True — 본문 키워드와 일치한 로어만 자동 포함(백로그 P1)."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    pid = client.post("/api/v1/projects", json={"title": "p"}).json()["id"]
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()
    client.put(f"/api/v1/chapters/{ch['id']}/content", json={
        "content_md": "검은 강가의 마을에서 이야기가 시작된다. 흑요 검이 빛난다."})
    client.post(f"/api/v1/projects/{pid}/lore", json={
        "category": "용어", "title": "흑요 검", "keywords": ["흑요 검"], "content": "검의 설정"})
    client.post(f"/api/v1/projects/{pid}/lore", json={
        "category": "장소", "title": "무한의 탑", "keywords": ["무한의 탑"], "content": "탑의 설정"})

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch["id"], "auto_lore": True}})
    assert resp.status_code == 200

    messages = fake_llm["client"].last_kwargs["messages"]
    user_text = messages[-1]["content"]
    assert "[세계관(자동): 흑요 검]" in user_text
    assert "무한의 탑" not in user_text

    # auto_lore=False면 자동 포함 없음
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch["id"], "auto_lore": False}})
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "[세계관: 흑요 검]" not in user_text


def test_system_prompt_prepended(client, fake_llm):
    """집필 기본 system 프롬프트가 user 메시지 앞에 붙는다(백로그: 프롬프트 고도화)."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘"})
    assert resp.status_code == 200
    messages = fake_llm["client"].last_kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "현역 한국 웹소설 작가" in messages[0]["content"]
    assert messages[-1]["role"] == "user"


def test_previous_chapter_tail_injected(client, fake_llm):
    """previous_chapter=True — 직전 회차 끝부분이 컨텍스트로 주입된다(이어쓰기 맥락)."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    pid = client.post("/api/v1/projects", json={"title": "p"}).json()["id"]
    ch1 = client.post(f"/api/v1/projects/{pid}/chapters",
                      json={"title": "1화", "sort_order": 0}).json()
    ch2 = client.post(f"/api/v1/projects/{pid}/chapters",
                      json={"title": "2화", "sort_order": 1}).json()
    client.put(f"/api/v1/chapters/{ch1['id']}/content", json={
        "content_md": "첫 화 도입부. " * 20 + "마지막 문장은 문이 열리는 순간이었다."})

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch2["id"], "previous_chapter": True}})
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "[직전 회차: 1화 끝부분]" in user_text
    assert "문이 열리는 순간이었다." in user_text  # 끝부분 위주 주입

    # 플래그 끄면 주입 없음
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"chapter_id": ch2["id"], "previous_chapter": False}})
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "[직전 회차:" not in user_text


def test_review_pass_streams_review_and_refined(client, fake_llm):
    """감수 패스 — 초안 스트림 종료 후 같은 SSE에서 review/refined가 이어진다.

    마커 '[수정본]'이 청크 경계('[수정' | '본]...')에서 잘리는 케이스도 함께 검증.
    """
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m",
        "reasoning_effort": "high"}).json()
    fake_llm["client"].set_chunks([
        "[감수]\n- 서두 전개가 급하다\n",
        "[수정", "본]\n수정된 원고 전문",
    ])

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "review": {}})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert kinds[-1] == "done"

    # start에 review_enabled 공개
    start = json.loads(dict(events)["start"])
    assert start["review_enabled"] is True

    review_start = [(e, d) for e, d in events if e == "review_start"]
    assert len(review_start) == 1
    info = json.loads(review_start[0][1])
    assert info["model"] == "m"
    assert info["endpoint"] == "e"
    assert info["reasoning_effort"] == "high"

    review = "".join(json.loads(d)["delta"] for e, d in events if e == "review")
    assert review == "[감수]\n- 서두 전개가 급하다"  # 마커 직전 개행은 전환 시 제거된다
    refined = "".join(json.loads(d)["delta"] for e, d in events if e == "refined")
    assert refined == "수정된 원고 전문"

    # 초안 delta는 그대로 message 이벤트로 유지된다
    draft = "".join(json.loads(d)["delta"] for e, d in events if e == "message")
    assert draft == "[감수]\n- 서두 전개가 급하다\n[수정본]\n수정된 원고 전문"

    # 감수 호출 프롬프트 — system 프롬프트 + 초안 원고 전달
    sent = fake_llm["client"].last_kwargs
    assert sent["messages"][0]["role"] == "system"
    assert "감수자" in sent["messages"][0]["content"]
    assert "[초안 원고]" in sent["messages"][-1]["content"]
    assert draft in sent["messages"][-1]["content"]
    assert sent["reasoning_effort"] == "high"


def test_review_pass_explicit_effort_overrides(client, fake_llm):
    """review.reasoning_effort가 엔드포인트 설정값보다 우선한다."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    fake_llm["client"].set_chunks(["본문", "[수정본]", "고침"])
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "review": {"reasoning_effort": "medium"}})
    assert resp.status_code == 200
    assert fake_llm["client"].last_kwargs["reasoning_effort"] == "medium"


def test_review_pass_failure_keeps_draft(client, fake_llm, monkeypatch):
    """감수 1콜 실패 — review_error 이벤트 후 스트림은 done으로 정상 종료, 초안 보존."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    ep2 = client.post("/api/v1/ai/endpoints", json={
        "name": "감수용", "base_url": "http://reviewer/v1",
        "default_model": "rv"}).json()

    # 감수 전용 엔드포인트로 만들어지는 클라이언트만 실패시킨다
    base_make = ai_panel.llm.make_client

    def _make(base_url, api_key_encrypted):
        c = base_make(base_url, api_key_encrypted)
        if "reviewer" in base_url:
            c.set_exc(openai.APITimeoutError(request=httpx.Request(
                "POST", "http://reviewer/v1/chat/completions")))
        return c

    monkeypatch.setattr(ai_panel.llm, "make_client", _make)

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "review": {"endpoint_id": ep2["id"]}})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]
    assert kinds[-1] == "done"

    draft = "".join(json.loads(d)["delta"] for e, d in events if e == "message")
    assert draft == "안녕하세요반갑습니다"  # 초안은 정상 수신
    errors = [(e, d) for e, d in events if e == "review_error"]
    assert len(errors) == 1
    assert "시간 초과" in json.loads(errors[0][1])["detail"]
    assert not [e for e, _ in events if e == "error"]  # 본 스트림 error는 아님


def test_review_absent_no_review_events(client, fake_llm):
    """review 필드가 없으면 기존 동작 유지 — review 이벤트 계열이 전혀 나오지 않는다."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘"})
    kinds = [e for e, _ in _parse_sse(resp.text)]
    assert kinds[0] == "start"
    assert kinds[-1] == "done"
    assert not any(k.startswith("review") or k == "refined" for k in kinds)


# ---------- 회차 브리프 (한국어 회차 품질 수직 슬라이스) ----------
BRIEF_LABEL = "[이번 화 브리프 — 생성 계약]"


def _valid_brief() -> dict:
    return {
        "emotion_goal": "굴욕을 뒤집는 통쾌함",
        "core_events": ["파문 통보", "흑요검의 첫 반응"],
        "character_choices": ["주인공은 복귀 대신 독자 노선을 택한다"],
        "cost": "세가 복귀 가능성을 포기한다",
        "prohibitions": ["흑요검의 정체를 완전히 밝히지 않는다"],
        "next_hook": "검집이 열리려는 순간 뒤에서 손목을 붙잡힌다",
        "scene_type": "대립",
        "target_chars_novelpia": 3000,
    }


def test_generate_with_brief_injects_contract_block(client, fake_llm):
    """context.brief 전송 시 브리프가 한국어 경계 블록으로 user 메시지에 주입된다."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "context": {"brief": _valid_brief()}})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[0][0] == "start"
    assert events[-1][0] == "done"

    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert BRIEF_LABEL in user_text
    assert "굴욕을 뒤집는 통쾌함" in user_text            # emotion_goal
    assert "파문 통보" in user_text                      # core_events
    assert "주인공은 복귀 대신 독자 노선을 택한다" in user_text  # character_choices
    assert "세가 복귀 가능성을 포기한다" in user_text      # cost
    assert "흑요검의 정체를 완전히 밝히지 않는다" in user_text  # prohibitions
    assert "검집이 열리려는 순간 뒤에서 손목을 붙잡힌다" in user_text  # next_hook
    assert "대립" in user_text                           # scene_type
    assert "3000" in user_text                           # target_chars_novelpia


def test_generate_without_brief_omits_brief_block(client, fake_llm):
    """brief 미전송 시 기존 요청과 동일 — 브리프 라벨 블록이 없다."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘"})
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert BRIEF_LABEL not in user_text


def test_brief_contract_validation_rejects_invalid(client, fake_llm):
    """빈 emotion_goal / core_events 4개 초과 — Pydantic 제한 위반은 422."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    base = {"endpoint_id": ep["id"], "prompt_override": "이어서 써줘"}

    bad_goal = _valid_brief() | {"emotion_goal": ""}
    resp = client.post("/api/v1/ai/generate",
                       json={**base, "context": {"brief": bad_goal}})
    assert resp.status_code == 422

    bad_events = _valid_brief() | {"core_events": ["a", "b", "c", "d"]}
    resp = client.post("/api/v1/ai/generate",
                       json={**base, "context": {"brief": bad_events}})
    assert resp.status_code == 422


def test_brief_array_items_strip_and_limits(client, fake_llm):
    """배열 항목 검증 — 공백 항목·빈 항목·501자 항목은 422, 공백은 제거해 주입."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    base = {"endpoint_id": ep["id"], "prompt_override": "이어서 써줘"}

    def post_brief(brief: dict):
        return client.post("/api/v1/ai/generate",
                           json={**base, "context": {"brief": brief}})

    # 공백만 있는 항목 — strip 후 빈 값이므로 422
    assert post_brief(_valid_brief() | {"core_events": ["   "]}).status_code == 422
    # 배열 중간의 빈 항목 — 422
    assert post_brief(_valid_brief() | {"prohibitions": ["정체를 숨긴다", ""]}).status_code == 422
    # 501자 항목 — 422
    assert post_brief(_valid_brief() | {"core_events": ["가" * 501]}).status_code == 422
    # 문자열 필드도 동일 — 공백만 있는 cost, 501자 next_hook
    assert post_brief(_valid_brief() | {"cost": "  \t "}).status_code == 422
    assert post_brief(_valid_brief() | {"next_hook": "나" * 501}).status_code == 422

    # 공백 제거는 검증으로 수행 — trim된 값이 프롬프트 블록에 주입된다
    resp = post_brief(_valid_brief() | {"core_events": ["  파문 통보  "],
                                        "emotion_goal": " 통쾌함 "})
    assert resp.status_code == 200
    user_text = fake_llm["client"].last_kwargs["messages"][-1]["content"]
    assert "파문 통보" in user_text
    assert "  파문 통보  " not in user_text
    assert "감정 목표: 통쾌함" in user_text


def test_review_stream_tail_flushed_without_refined_marker(client, fake_llm):
    """[수정본] 마커 없이 감수 스트림이 끝나도 carry에 남은 마지막 구간이 review로 방출된다."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    fake_llm["client"].set_chunks([
        "[감수]\n- 서두 전개가 급하",
        "다\n- 결말 훅이 약하다",
    ])

    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘",
        "review": {}})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)

    review = "".join(json.loads(d)["delta"] for e, d in events if e == "review")
    assert review == "[감수]\n- 서두 전개가 급하다\n- 결말 훅이 약하다"
    assert not [e for e, _ in events if e == "refined"]  # 마커가 없으므로 수정본 없음


# ---------- 적응형 한국어 생성·감수 프롬프트 계약 ----------
def test_novel_system_prompt_adaptive_korean_contract(client, fake_llm):
    """생성 system 프롬프트 — 브리프 우선·장면 유형 리듬 지침, 구형 절대 수치 규칙 제거."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘"})
    assert resp.status_code == 200
    sys_text = fake_llm["client"].last_kwargs["messages"][0]["content"]
    assert "회차 브리프" in sys_text
    assert "장면 유형" in sys_text
    # 구형 절대 규칙 — 보편 수치 지침은 남아 있으면 안 된다
    assert "전체 분량의 35~50%는 대사다" not in sys_text
    assert "한 문단은 1~2문장" not in sys_text
    assert "첫 500자" not in sys_text


def test_review_system_prompt_lenses_and_markers(client, fake_llm):
    """감수 system 프롬프트 — 5개 감수 관점과 [감수]/[수정본] 마커를 유지한다."""
    ep = client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://x/v1", "default_model": "m"}).json()
    fake_llm["client"].set_chunks(["[감수]\n- 문제\n", "[수정본]\n수정 원고"])
    resp = client.post("/api/v1/ai/generate", json={
        "endpoint_id": ep["id"], "prompt_override": "이어서 써줘", "review": {}})
    assert resp.status_code == 200
    sys_text = fake_llm["client"].last_kwargs["messages"][0]["content"]
    for keyword in ("구조", "캐릭터", "연속성", "문장", "플랫폼", "[감수]", "[수정본]"):
        assert keyword in sys_text
