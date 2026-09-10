import json
import pytest
from fastapi import HTTPException

from app.schemas import CanonCheckRequest, GenerateContext, GenerateRequest
from app.services.ai_context import build_context_bundle, request_from_canon, request_from_generate
from tests.test_ai_generate_stream import DEFAULT_CHUNKS, FakeAsyncOpenAI, _parse_sse


def _db(client):
    from app.database import get_db
    return next(iter(client.app.dependency_overrides[get_db]()))


def _project_with_chapter(client, title="P", body="본문"):
    pid = client.post("/api/v1/projects", json={"title": title}).json()["id"]
    chapter = client.post(
        f"/api/v1/projects/{pid}/chapters",
        json={"title": "1화", "sort_order": 1},
    ).json()
    client.put(
        f"/api/v1/chapters/{chapter['id']}/content",
        json={"content_md": body, "expected_revision": 0},
    )
    return pid, client.get(f"/api/v1/chapters/{chapter['id']}").json()


def _endpoint(client):
    return client.post(
        "/api/v1/ai/endpoints",
        json={"name": "e", "base_url": "http://x/v1", "default_model": "m"},
    ).json()


def _patch_stream_llm(monkeypatch):
    from app.routers import ai_panel

    spec = {"chunks": list(DEFAULT_CHUNKS), "exc": None}
    holder = {"client": None}

    def _make_client(base_url, api_key_encrypted):
        holder["client"] = FakeAsyncOpenAI(base_url=base_url, api_key="x", spec=spec)
        return holder["client"]

    monkeypatch.setattr(ai_panel.llm, "make_client", _make_client)
    _make_client("http://x/v1", None)
    return holder


def test_approved_memory_is_injected_and_stale_memory_is_excluded(client):
    from app.services.long_memory import create_memory_entry

    pid, chapter = _project_with_chapter(client, body="현재 원문")
    db = _db(client)
    current = db.get(__import__("app.models", fromlist=["Chapter"]).Chapter, chapter["id"])
    current_revision = current.revision
    create_memory_entry(
        db, project_id=pid, chapter_id=current.id, source_revision=current_revision,
        source_text=current.content_md, kind="fact", body="현재 승인 기억", visibility="approved",
    )
    create_memory_entry(
        db, project_id=pid, chapter_id=current.id, source_revision=current_revision - 1,
        source_text=current.content_md, kind="fact", body="오래된 기억", visibility="approved",
    )
    db.commit()

    payload = GenerateRequest(
        endpoint_id=1, prompt_override="이어 써줘",
        context=GenerateContext(project_id=pid, chapter_id=current.id),
    )
    bundle = build_context_bundle(db, request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert "현재 승인 기억" in joined
    assert "오래된 기억" not in joined
    assert bundle.metadata["included_memory_entry_ids"]

    disabled = GenerateRequest(
        endpoint_id=1, prompt_override="이어 써줘",
        context=GenerateContext(
            project_id=pid, chapter_id=current.id, include_memory=False,
        ),
    )
    disabled_bundle = build_context_bundle(db, request_from_generate(disabled))
    assert "현재 승인 기억" not in "\n\n".join(disabled_bundle.blocks)
    assert disabled_bundle.metadata["included_memory_entry_ids"] == []


def test_legacy_chapter_id_includes_body_by_default(client):
    pid, chapter = _project_with_chapter(client, body="레거시 본문")
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="이어 써줘",
        context=GenerateContext(chapter_id=chapter["id"]),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert bundle.project_id == pid
    assert bundle.chapter_id == chapter["id"]
    assert bundle.metadata["include_chapter_content"] is True
    assert "[현재 회차: 1화]" in joined
    assert "레거시 본문" in joined


def test_current_identity_survives_body_opt_out(client):
    pid, chapter = _project_with_chapter(client, body="보내면 안 되는 본문")
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="새 장면을 제안해줘",
        context=GenerateContext(
            project_id=pid,
            chapter_id=chapter["id"],
            include_chapter_content=False,
            expected_revision=chapter["revision"],
            auto_outline=True,
        ),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert bundle.project_id == pid
    assert bundle.chapter_id == chapter["id"]
    assert bundle.chapter_revision == chapter["revision"]
    assert bundle.metadata["include_chapter_content"] is False
    assert "보내면 안 되는 본문" not in joined
    assert bundle.metadata["outline"].get("current") is not True


def test_project_chapter_mismatch_rejected(client):
    pid_a, _chapter_a = _project_with_chapter(client, title="A")
    _pid_b, chapter_b = _project_with_chapter(client, title="B")
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="이어 써줘",
        context=GenerateContext(project_id=pid_a, chapter_id=chapter_b["id"]),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422
    assert "project" in str(exc.value.detail).lower() or "작품" in str(exc.value.detail)


def test_selected_character_wrong_project_rejected(client):
    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    wrong_char = client.post(
        f"/api/v1/projects/{pid_b}/characters", json={"name": "타작품 인물"}
    ).json()
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="이어 써줘",
        context=GenerateContext(
            project_id=pid_a,
            chapter_id=chapter_a["id"],
            character_ids=[wrong_char["id"]],
        ),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422


def test_stale_expected_revision_rejected(client):
    pid, chapter = _project_with_chapter(client)
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="이어 써줘",
        context=GenerateContext(project_id=pid, chapter_id=chapter["id"], expected_revision=0),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "revision_conflict"
    assert exc.value.detail["current_revision"] == chapter["revision"]


def test_selected_lore_wrong_project_rejected_probe_a1(client):
    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    wrong_lore = client.post(
        f"/api/v1/projects/{pid_b}/lore",
        json={
            "category": "용어",
            "title": "B_INTRUDER_LORE_TITLE",
            "content": "B_INTRUDER_LORE_CONTENT",
        },
    ).json()
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="selected mismatch prompt",
        context=GenerateContext(
            project_id=pid_a, chapter_id=chapter_a["id"], lore_ids=[wrong_lore["id"]]
        ),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422


def test_explicit_project_b_cannot_mix_with_chapter_a_probe_a2(client):
    pid_a, chapter_a = _project_with_chapter(
        client, title="A", body="A_PID_CHAPTER_BODY_ONLY"
    )
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    client.post(
        f"/api/v1/projects/{pid_b}/lore",
        json={
            "category": "용어",
            "title": "B_AUTO_LORE_TITLE",
            "keywords": ["B_AUTO"],
            "content": "B_AUTO_LORE_CONTENT",
        },
    )
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="B_AUTO",
        context=GenerateContext(
            project_id=pid_b, chapter_id=chapter_a["id"], auto_lore=True, auto_foreshadow=True
        ),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422


def test_generate_422_does_not_create_provider_client(client, monkeypatch):
    from app.routers import ai_panel

    ep = _endpoint(client)
    pid_a, _chapter_a = _project_with_chapter(client, title="A")
    _pid_b, chapter_b = _project_with_chapter(client, title="B")
    touched = {"make_client": False}

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after validation failure")

    monkeypatch.setattr(ai_panel.llm, "make_client", fail_make_client)
    resp = client.post(
        "/api/v1/ai/generate",
        json={
            "endpoint_id": ep["id"],
            "prompt_override": "should reject before provider",
            "context": {"project_id": pid_a, "chapter_id": chapter_b["id"]},
        },
    )
    assert resp.status_code == 422
    assert touched["make_client"] is False


def test_generate_409_does_not_create_provider_client(client, monkeypatch):
    from app.routers import ai_panel

    ep = _endpoint(client)
    pid, chapter = _project_with_chapter(client, title="A")
    touched = {"make_client": False}

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after revision conflict")

    monkeypatch.setattr(ai_panel.llm, "make_client", fail_make_client)
    resp = client.post(
        "/api/v1/ai/generate",
        json={
            "endpoint_id": ep["id"],
            "prompt_override": "should reject stale revision",
            "context": {
                "project_id": pid,
                "chapter_id": chapter["id"],
                "expected_revision": 0,
            },
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "revision_conflict"
    assert touched["make_client"] is False


def test_canon_409_does_not_resolve_endpoint_or_create_provider_client(client, monkeypatch):
    from app.routers import quality as quality_router

    _pid, chapter = _project_with_chapter(client, title="A")
    touched = {"resolve_endpoint": False, "make_client": False}

    def fail_resolve_endpoint(*_args, **_kwargs):
        touched["resolve_endpoint"] = True
        raise AssertionError("endpoint resolution must not run after revision conflict")

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after revision conflict")

    monkeypatch.setattr(quality_router, "resolve_endpoint", fail_resolve_endpoint)
    monkeypatch.setattr(quality_router.llm, "make_client", fail_make_client)
    resp = client.post(
        "/api/v1/canon-check",
        json={"chapter_id": chapter["id"], "expected_revision": 0},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "revision_conflict"
    assert touched == {"resolve_endpoint": False, "make_client": False}


def test_canon_422_does_not_resolve_endpoint_for_wrong_project_approved_foreshadow(
    client, monkeypatch
):
    from app.routers import quality as quality_router

    _pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    fs_b = client.post(
        f"/api/v1/projects/{pid_b}/foreshadows", json={"title": "B_ONLY_FORESHADOW"}
    ).json()
    touched = {"resolve_endpoint": False, "make_client": False}

    def fail_resolve_endpoint(*_args, **_kwargs):
        touched["resolve_endpoint"] = True
        raise AssertionError("endpoint resolution must not run after ownership failure")

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created after ownership failure")

    monkeypatch.setattr(quality_router, "resolve_endpoint", fail_resolve_endpoint)
    monkeypatch.setattr(quality_router.llm, "make_client", fail_make_client)
    resp = client.post(
        "/api/v1/canon-check",
        json={"chapter_id": chapter_a["id"], "approved_foreshadow_ids": [fs_b["id"]]},
    )
    assert resp.status_code == 422
    assert touched == {"resolve_endpoint": False, "make_client": False}


def test_selected_relationships_include_only_both_selected_endpoints(client):
    pid, chapter = _project_with_chapter(client)
    a = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "한서윤"}).json()
    b = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "강무진"}).json()
    c = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "남궁린"}).json()
    rel_ab = client.post(
        f"/api/v1/projects/{pid}/characters/relations",
        json={
            "from_character_id": a["id"],
            "to_character_id": b["id"],
            "label": "사제",
            "note": "공개적으로 감싸지 못한다",
        },
    ).json()
    client.post(
        f"/api/v1/projects/{pid}/characters/relations",
        json={
            "from_character_id": a["id"],
            "to_character_id": c["id"],
            "label": "동료",
            "note": "임시 동맹",
        },
    )
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="대화 장면",
        context=GenerateContext(
            project_id=pid,
            chapter_id=chapter["id"],
            character_ids=[b["id"], a["id"]],
            include_relationships=True,
        ),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert "[인물 관계" in joined
    assert "한서윤" in joined and "강무진" in joined
    assert "남궁린" not in joined
    assert bundle.metadata["included_character_ids"] == [b["id"], a["id"]]
    assert bundle.metadata["included_relationship_ids"] == [rel_ab["id"]]


def test_relationships_with_one_selected_character_are_empty_not_422(client):
    pid, chapter = _project_with_chapter(client)
    a = client.post(f"/api/v1/projects/{pid}/characters", json={"name": "한서윤"}).json()
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="독백 장면",
        context=GenerateContext(
            project_id=pid,
            chapter_id=chapter["id"],
            character_ids=[a["id"]],
            include_relationships=True,
        ),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    assert "[인물 관계" not in "\n\n".join(bundle.blocks)
    assert bundle.metadata["included_relationship_ids"] == []


def test_generation_relationships_reach_provider_prompt_probe_b(client, monkeypatch):
    holder = _patch_stream_llm(monkeypatch)
    ep = _endpoint(client)
    pid, chapter = _project_with_chapter(client, body="REL_CHAPTER_BODY_ONLY")
    a = client.post(
        f"/api/v1/projects/{pid}/characters",
        json={"name": "REL_SOURCE_CHARACTER", "appearance": "source appearance"},
    ).json()
    b = client.post(
        f"/api/v1/projects/{pid}/characters",
        json={"name": "REL_TARGET_CHARACTER", "appearance": "target appearance"},
    ).json()
    rel = client.post(
        f"/api/v1/projects/{pid}/characters/relations",
        json={
            "from_character_id": a["id"],
            "to_character_id": b["id"],
            "label": "BLOOD_OATH_LABEL_777",
            "note": "HIDDEN_REL_NOTE_888",
        },
    ).json()
    resp = client.post(
        "/api/v1/ai/generate",
        json={
            "endpoint_id": ep["id"],
            "prompt_override": "relationship omission prompt",
            "context": {
                "project_id": pid,
                "chapter_id": chapter["id"],
                "character_ids": [a["id"], b["id"]],
                "include_relationships": True,
            },
        },
    )
    assert resp.status_code == 200
    user_text = holder["client"].last_kwargs["messages"][-1]["content"]
    assert "REL_SOURCE_CHARACTER" in user_text and "REL_TARGET_CHARACTER" in user_text
    assert "BLOOD_OATH_LABEL_777" in user_text
    assert "HIDDEN_REL_NOTE_888" in user_text
    start = json.loads(dict(_parse_sse(resp.text))["start"])
    assert start["context_metadata"]["included_relationship_ids"] == [rel["id"]]


def test_canon_consumed_relationship_with_wrong_project_endpoint_is_rejected(client):
    from app.models import Chapter, Relationship

    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    a = client.post(f"/api/v1/projects/{pid_a}/characters", json={"name": "A인물"}).json()
    b = client.post(f"/api/v1/projects/{pid_b}/characters", json={"name": "B인물"}).json()
    db = _db(client)
    db.add(
        Relationship(
            from_character_id=a["id"],
            to_character_id=b["id"],
            label="깨진 관계",
            note="타작품 endpoint",
        )
    )
    db.commit()
    chapter = db.get(Chapter, chapter_a["id"])
    payload = CanonCheckRequest(chapter_id=chapter_a["id"], include_relationships=True)
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(db, request_from_canon(payload, chapter))
    assert exc.value.status_code == 422


def test_expected_revision_without_chapter_rejected_by_schema():
    with pytest.raises(ValueError):
        GenerateContext(project_id=1, expected_revision=1)



def test_approved_foreshadow_reference_project_checked_without_explicit_project(client):
    from app.models import Foreshadow

    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    db = _db(client)
    fs = Foreshadow(
        project_id=pid_b,
        title="BROKEN_REF",
        planted_chapter_id=chapter_a["id"],
        status="설치",
    )
    db.add(fs)
    db.commit()
    db.refresh(fs)
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="validate approved id references",
        context=GenerateContext(approved_foreshadow_ids=[fs.id]),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(db, request_from_generate(payload))
    assert exc.value.status_code == 422


def test_approved_foreshadow_ids_from_two_projects_are_ambiguous_without_current_identity(client):
    pid_a, _ = _project_with_chapter(client, title="A")
    pid_b, _ = _project_with_chapter(client, title="B")
    fs_a = client.post(f"/api/v1/projects/{pid_a}/foreshadows", json={"title": "A_FS"}).json()
    fs_b = client.post(f"/api/v1/projects/{pid_b}/foreshadows", json={"title": "B_FS"}).json()
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="validate approved id projects",
        context=GenerateContext(approved_foreshadow_ids=[fs_a["id"], fs_b["id"]]),
    )
    with pytest.raises(HTTPException) as exc:
        build_context_bundle(_db(client), request_from_generate(payload))
    assert exc.value.status_code == 422


def test_generate_invalid_approved_foreshadow_reference_does_not_create_provider_client(client, monkeypatch):
    from app.models import Foreshadow
    from app.routers import ai_panel

    ep = _endpoint(client)
    pid_a, chapter_a = _project_with_chapter(client, title="A")
    pid_b, _chapter_b = _project_with_chapter(client, title="B")
    db = _db(client)
    fs = Foreshadow(
        project_id=pid_b,
        title="BROKEN_REF",
        planted_chapter_id=chapter_a["id"],
        status="설치",
    )
    db.add(fs)
    db.commit()
    db.refresh(fs)
    touched = {"make_client": False}

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created")

    monkeypatch.setattr(ai_panel.llm, "make_client", fail_make_client)
    resp = client.post(
        "/api/v1/ai/generate",
        json={
            "endpoint_id": ep["id"],
            "prompt_override": "provider should not run for invalid foreshadow reference",
            "context": {"approved_foreshadow_ids": [fs.id]},
        },
    )
    assert resp.status_code == 422
    assert touched["make_client"] is False


def test_parallel_mixed_approved_foreshadows_rejects_before_provider_client(client, monkeypatch):
    from app.routers import ai_panel

    ep = _endpoint(client)
    pid_a, _ = _project_with_chapter(client, title="A")
    pid_b, _ = _project_with_chapter(client, title="B")
    fs_a = client.post(f"/api/v1/projects/{pid_a}/foreshadows", json={"title": "A_FS"}).json()
    fs_b = client.post(f"/api/v1/projects/{pid_b}/foreshadows", json={"title": "B_FS"}).json()
    touched = {"make_client": False, "complete_chat": False}

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created")

    async def fail_complete_chat(*_args, **_kwargs):
        touched["complete_chat"] = True
        raise AssertionError("provider await must not run")

    monkeypatch.setattr(ai_panel.llm, "make_client", fail_make_client)
    monkeypatch.setattr(ai_panel.llm, "complete_chat", fail_complete_chat)
    resp = client.post(
        "/api/v1/ai/generate-parallel",
        json={
            "endpoint_id": ep["id"],
            "prompt_override": "reject mixed approved ids",
            "context": {"approved_foreshadow_ids": [fs_a["id"], fs_b["id"]]},
            "worker_limit": 2,
            "review": {"reasoning_effort": "xhigh"},
        },
    )
    assert resp.status_code == 422
    assert touched == {"make_client": False, "complete_chat": False}


def test_approved_only_request_infers_project_for_style_and_auto_lore_without_leak(client):
    pid_a, _ = _project_with_chapter(client, title="A")
    pid_b, _ = _project_with_chapter(client, title="B")
    client.patch(f"/api/v1/projects/{pid_a}", json={"style_profile": "STYLE_A_ONLY"})
    client.patch(f"/api/v1/projects/{pid_b}", json={"style_profile": "STYLE_B_LEAK"})
    fs_a = client.post(f"/api/v1/projects/{pid_a}/foreshadows", json={"title": "A_APPROVED"}).json()
    client.post(
        f"/api/v1/projects/{pid_a}/lore",
        json={"category": "용어", "title": "A_AUTO_LORE", "keywords": ["TOKEN"], "content": "A_LORE_CONTENT"},
    )
    client.post(
        f"/api/v1/projects/{pid_b}/lore",
        json={"category": "용어", "title": "B_AUTO_LORE", "keywords": ["TOKEN"], "content": "B_LORE_CONTENT"},
    )
    payload = GenerateRequest(
        endpoint_id=1,
        prompt_override="TOKEN",
        context=GenerateContext(
            approved_foreshadow_ids=[fs_a["id"]],
            auto_lore=True,
            style_profile=True,
        ),
    )
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    joined = "\n\n".join(bundle.blocks)
    assert bundle.project_id == pid_a
    assert bundle.style_profile_text == "STYLE_A_ONLY"
    assert "A_AUTO_LORE" in joined
    assert "B_AUTO_LORE" not in joined
    assert bundle.metadata["approved_foreshadow_ids"] == [fs_a["id"]]


def test_legacy_unbound_request_without_identifying_ids_stays_valid(client):
    payload = GenerateRequest(endpoint_id=1, prompt_override="standalone")
    bundle = build_context_bundle(_db(client), request_from_generate(payload))
    assert bundle.project_id is None
    assert bundle.chapter_id is None
    assert bundle.blocks == []
    assert bundle.metadata["approved_foreshadow_ids"] == []



def test_generate_missing_approved_foreshadow_id_does_not_create_provider_client(client, monkeypatch):
    from app.routers import ai_panel

    ep = _endpoint(client)
    touched = {"make_client": False}

    def fail_make_client(*_args, **_kwargs):
        touched["make_client"] = True
        raise AssertionError("provider client must not be created")

    monkeypatch.setattr(ai_panel.llm, "make_client", fail_make_client)
    resp = client.post(
        "/api/v1/ai/generate",
        json={
            "endpoint_id": ep["id"],
            "prompt_override": "missing approved id",
            "context": {"approved_foreshadow_ids": [999999]},
        },
    )
    assert resp.status_code == 404
    assert touched["make_client"] is False
