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
    user_msg = sent["messages"][0]["content"]
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
