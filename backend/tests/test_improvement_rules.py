"""E4/E6 — 작품별 개선 규칙 생명주기 + 승인 규칙 컨텍스트 주입 테스트.

핵심 안전 단정:
- 제안→승인→적용 순서만 허용(상태 기계·409)
- 규칙 본문은 승인 후 불변(PATCH 409)
- 작품 완전 분리 — 다른 작품 규칙은 404이며 컨텍스트에도 들어가지 않음
- approved만 주입, 규칙 없으면 컨텍스트가 바이트 단위로 동일
"""
import pytest
from sqlalchemy import select

from app.models import GenerationRun, ImprovementRule
from app.schemas import GenerateContext, GenerateRequest
from app.services.ai_context import build_context_bundle, request_from_generate
from tests.conftest import _db
from tests.test_generation_runs import _saved_event
from tests.test_ai_generate_stream import _parse_sse


@pytest.fixture()
def proj(client):
    return client.post("/api/v1/projects", json={"title": "p"}).json()


def _create(client, pid, **kw):
    body = {"category": "style", "rule_text": "설명 문단이 연달아 놓이지 않는다"}
    body.update(kw)
    return client.post(f"/api/v1/projects/{pid}/improvement-rules", json=body)


# ---------- 생명주기 ----------

def test_create_proposed_and_approve(client, proj):
    r = _create(client, proj["id"])
    assert r.status_code == 201
    rule = r.json()
    assert rule["status"] == "proposed" and rule["source"] == "author_written"
    assert rule["status_events_json"][0]["to"] == "proposed"

    r = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}/decision",
        json={"decision": "approve"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["decided_at"] is not None
    assert [e["to"] for e in r.json()["status_events_json"]] == ["proposed", "approved"]


def test_create_directly_approved_author_written(client, proj):
    r = _create(client, proj["id"], status="approved")
    assert r.status_code == 201
    assert r.json()["status"] == "approved"
    assert r.json()["decided_at"] is not None


def test_decision_state_machine_rejects_invalid(client, proj):
    rule = _create(client, proj["id"]).json()
    # approved가 아닌 규칙은 retire 불가
    r = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}/decision",
        json={"decision": "retire"})
    assert r.status_code == 409
    # reject 후 종결 — 재전이 불가
    client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}/decision",
        json={"decision": "reject"})
    for decision in ("approve", "reject", "retire"):
        r = client.post(
            f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}/decision",
            json={"decision": decision})
        assert r.status_code == 409


def test_approved_rule_retire_path(client, proj):
    rule = _create(client, proj["id"], status="approved").json()
    r = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}/decision",
        json={"decision": "retire"})
    assert r.status_code == 200 and r.json()["status"] == "retired"


def test_patch_only_while_proposed(client, proj):
    rule = _create(client, proj["id"]).json()
    r = client.patch(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}",
        json={"rule_text": "바꾼 규칙"})
    assert r.status_code == 200 and r.json()["rule_text"] == "바꾼 규칙"
    client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}/decision",
        json={"decision": "approve"})
    r = client.patch(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rule['id']}",
        json={"rule_text": "또 바꿈"})
    assert r.status_code == 409


def test_project_isolation(client, proj):
    other = client.post("/api/v1/projects", json={"title": "other"}).json()
    rule = _create(client, proj["id"]).json()
    r = client.get(f"/api/v1/projects/{other['id']}/improvement-rules/{rule['id']}")
    assert r.status_code == 404
    r = client.post(
        f"/api/v1/projects/{other['id']}/improvement-rules/{rule['id']}/decision",
        json={"decision": "approve"})
    assert r.status_code == 404
    # 목록도 분리
    assert client.get(f"/api/v1/projects/{other['id']}/improvement-rules").json() == []


def test_evidence_validation(client, proj):
    r = _create(client, proj["id"], evidence=[{"kind": "chapter"}])  # id 없음
    assert r.status_code == 422
    r = _create(client, proj["id"],
                evidence=[{"kind": "note", "text": "삽입 후 매번 고침"}])
    assert r.status_code == 201
    assert r.json()["evidence_json"][0]["kind"] == "note"


# ---------- E6 컨텍스트 주입 ----------

def _bundle(client, pid, chapter_id=None, target="generate"):
    ctx = GenerateContext(project_id=pid, chapter_id=chapter_id)
    req = GenerateRequest(prompt_override="써줘", context=ctx)
    bundle_req = request_from_generate(req)
    object.__setattr__(bundle_req, "target", target)
    return build_context_bundle(_db(client), bundle_req)


def test_approved_rules_injected_only_for_generate(client, proj):
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    approved = _create(client, proj["id"], status="approved",
                       rule_text="한 문장은 60자를 넘기지 않는다").json()
    _create(client, proj["id"], rule_text="미승인 규칙은 들어가면 안 된다")  # proposed
    rejected = _create(client, proj["id"], rule_text="거절된 규칙").json()
    client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{rejected['id']}/decision",
        json={"decision": "reject"})

    bundle = _bundle(client, proj["id"], chapter["id"])
    joined = "\n\n".join(bundle.blocks)
    assert "[작가 승인 규칙" in joined
    assert "한 문장은 60자를 넘기지 않는다" in joined
    assert "미승인 규칙" not in joined
    assert "거절된 규칙" not in joined
    assert bundle.metadata["applied_rule_ids"] == [approved["id"]]

    # canon 대상에는 주입하지 않는다
    canon_bundle = _bundle(client, proj["id"], chapter["id"], target="canon")
    assert "[작가 승인 규칙" not in "\n\n".join(canon_bundle.blocks)
    assert canon_bundle.metadata["applied_rule_ids"] == []


def test_rules_byte_identical_when_none(client, proj):
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    bundle = _bundle(client, proj["id"], chapter["id"])
    joined = "\n\n".join(bundle.blocks)
    assert "[작가 승인 규칙" not in joined
    assert bundle.metadata["applied_rule_ids"] == []


def test_other_project_rules_never_injected(client, proj):
    other = client.post("/api/v1/projects", json={"title": "other"}).json()
    _create(client, other["id"], status="approved", rule_text="타 작품 규칙")
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    bundle = _bundle(client, proj["id"], chapter["id"])
    assert "타 작품 규칙" not in "\n\n".join(bundle.blocks)


def test_generate_run_records_applied_rules(
        client, fake_llm_for_gen, endpoint_for_gen, proj):
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    _create(client, proj["id"], status="approved", rule_text="말투 규칙")
    r = client.post("/api/v1/ai/generate", json={
        "prompt_override": "써줘",
        "context": {"project_id": proj["id"], "chapter_id": chapter["id"]}})
    assert r.status_code == 200
    saved = _saved_event(_parse_sse(r.text))
    db = _db(client)
    run = db.get(GenerationRun, saved["run_id"])
    assert run.applied_rules_json is not None and len(run.applied_rules_json) == 1


@pytest.fixture()
def fake_llm_for_gen(monkeypatch):
    from tests.test_ai_generate_stream import FakeAsyncOpenAI
    from app.routers import ai_panel
    spec = {"chunks": ["초안."], "exc": None}
    monkeypatch.setattr(
        ai_panel.llm, "make_client",
        lambda *a, **k: FakeAsyncOpenAI(base_url="http://x", api_key="k", spec=spec))
    return spec


@pytest.fixture()
def endpoint_for_gen(client):
    return client.post("/api/v1/ai/endpoints", json={
        "name": "e", "base_url": "http://localhost:1234/v1",
        "api_key": "secret", "default_model": "m-1"}).json()


# ---------- E5 제안 job — 결정론 신호 → proposed 초안만 ----------

def _generate_and_insert_trimmed(client, proj_id, chapter_id, count=3):
    """draft를 생성하고 작가가 '둘째 줄.'을 지운 채 반영한 이력을 만든다."""
    output_ids = []
    for _ in range(count):
        r = client.post("/api/v1/ai/generate", json={
            "prompt_override": "써줘",
            "context": {"project_id": proj_id, "chapter_id": chapter_id}})
        assert r.status_code == 200
        saved = _saved_event(_parse_sse(r.text))
        oid = saved["outputs"]["draft"]
        client.post(f"/api/v1/generation-outputs/{oid}/outcome", json={
            "outcome": "inserted", "landed_text": "초안 한 줄."})
        output_ids.append(oid)
    return output_ids


def test_propose_creates_proposed_drafts_with_evidence(
        client, fake_llm_for_gen, endpoint_for_gen, proj):
    """반복 삭제 표현 + 과장 초안 신호가 proposed 규칙 초안만 만든다."""
    fake_llm_for_gen["chunks"] = ["초안 한 줄.", " 둘째 줄."]
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    _generate_and_insert_trimmed(client, proj["id"], chapter["id"], count=3)

    r = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/propose")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created_count"] >= 1
    for rule in body["created"]:
        # 절대 자동 승인하지 않는다
        assert rule["status"] == "proposed"
        assert rule["source"] == "system_proposal"
        assert rule["evidence_json"]
        assert rule["rationale"]
    cats = {rule["category"] for rule in body["created"]}
    assert "deleted_expression" in cats
    assert "length" in cats  # 7/13 ≈ 0.54 < 0.7 — 작가가 크게 줄임


def test_propose_is_idempotent(client, fake_llm_for_gen, endpoint_for_gen, proj):
    fake_llm_for_gen["chunks"] = ["초안 한 줄.", " 둘째 줄."]
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    _generate_and_insert_trimmed(client, proj["id"], chapter["id"], count=3)
    first = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/propose").json()
    assert first["created_count"] >= 1
    second = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/propose").json()
    assert second["created_count"] == 0
    assert second["skipped_existing"] == second["signals_evaluated"]


def test_propose_never_reproposes_rejected(
        client, fake_llm_for_gen, endpoint_for_gen, proj):
    """작가가 거절한 규칙은 같은 신호가 남아 있어도 재제안하지 않는다."""
    fake_llm_for_gen["chunks"] = ["초안 한 줄.", " 둘째 줄."]
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    _generate_and_insert_trimmed(client, proj["id"], chapter["id"], count=3)
    first = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/propose").json()
    target = next(r for r in first["created"]
                  if r["category"] == "deleted_expression")
    client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/{target['id']}/decision",
        json={"decision": "reject"})
    second = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/propose").json()
    assert all(r["category"] != "deleted_expression"
               or r["rule_text"] != target["rule_text"]
               for r in second["created"])


def test_propose_below_threshold_creates_nothing(
        client, fake_llm_for_gen, endpoint_for_gen, proj):
    """표본이 얕으면 아무 제안도 만들지 않는다(작가 주의력 보호)."""
    fake_llm_for_gen["chunks"] = ["초안 한 줄.", " 둘째 줄."]
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    _generate_and_insert_trimmed(client, proj["id"], chapter["id"], count=1)
    body = client.post(
        f"/api/v1/projects/{proj['id']}/improvement-rules/propose").json()
    assert body["created_count"] == 0


def test_proposed_rules_not_injected_until_approved(
        client, fake_llm_for_gen, endpoint_for_gen, proj):
    """proposed 규칙은 컨텍스트에 주입되지 않는다 — 승인 게이트가 유일 경로."""
    fake_llm_for_gen["chunks"] = ["초안 한 줄.", " 둘째 줄."]
    chapter = client.post(
        f"/api/v1/projects/{proj['id']}/chapters", json={"title": "1화"}).json()
    _generate_and_insert_trimmed(client, proj["id"], chapter["id"], count=3)
    client.post(f"/api/v1/projects/{proj['id']}/improvement-rules/propose")
    bundle = _bundle(client, proj["id"], chapter["id"])
    assert "[작가 승인 규칙" not in "\n\n".join(bundle.blocks)
    assert bundle.metadata["applied_rule_ids"] == []
