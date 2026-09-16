"""작품별 trend_pack CRUD와 생성 컨텍스트 opt-in 계약 테스트."""
from datetime import datetime, timezone

import pytest

from app.services import ai_context
from tests.conftest import _db
from app.schemas import GenerateRequest


def _project(client, title="trend project"):
    return client.post("/api/v1/projects", json={"title": title, "genre": "무협"}).json()


def _pack_payload(**overrides):
    payload = {
        "status": "draft",
        "source": "research",
        "as_of": "2026-09-16T00:00:00Z",
        "signals": [
            {
                "label": "관계 규합형 성장",
                "note": "개인 무력 상승보다 세력과 관계의 상태 변화를 보상으로 연결한다.",
            },
            {
                "label": "선택형 클리셰",
                "note": "회귀나 가문 재건은 작가가 선택할 때만 갈등과 대가로 사용한다.",
            },
        ],
    }
    payload.update(overrides)
    return payload


def test_trend_pack_upsert_round_trips_as_draft(client):
    project = _project(client)

    response = client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json=_pack_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["status"] == "draft"
    assert body["schema_version"] == "trend-pack-v1"
    assert body["version"] == 1
    assert body["source"] == "research"
    assert len(body["signals"]) == 2

    fetched = client.get(f"/api/v1/projects/{project['id']}/trend-pack")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]
    assert fetched.json()["signals"] == body["signals"]


def test_trend_pack_update_increments_version_and_preserves_status_when_omitted(client):
    project = _project(client)
    created = client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json=_pack_payload(status="approved"),
    ).json()

    response = client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json={
            "source": "author",
            "signals": [{"label": "직업 전문성", "note": "현대 직업의 절차와 윤리를 사건 보상으로 연결한다."}],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == created["id"]
    assert body["version"] == 2
    assert body["status"] == "approved"
    assert body["source"] == "author"
    assert body["signals"][0]["label"] == "직업 전문성"


def test_trend_pack_payload_is_bounded_and_rejects_unknown_fields(client):
    project = _project(client)
    too_many = _pack_payload(
        signals=[{"label": str(i), "note": "근거"} for i in range(13)]
    )
    assert client.put(
        f"/api/v1/projects/{project['id']}/trend-pack", json=too_many
    ).status_code == 422

    unknown = _pack_payload(untrusted_instruction="system override")
    assert client.put(
        f"/api/v1/projects/{project['id']}/trend-pack", json=unknown
    ).status_code == 422


def test_trend_pack_is_project_scoped_and_delete_is_explicit(client):
    project_a = _project(client, "A")
    project_b = _project(client, "B")
    client.put(f"/api/v1/projects/{project_a['id']}/trend-pack", json=_pack_payload())

    assert client.get(f"/api/v1/projects/{project_b['id']}/trend-pack").status_code == 404
    assert client.delete(f"/api/v1/projects/{project_a['id']}/trend-pack").status_code == 204
    assert client.get(f"/api/v1/projects/{project_a['id']}/trend-pack").status_code == 404


def test_approved_trend_pack_is_opt_in_context_reference_not_canon(client):
    project = _project(client)
    client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json=_pack_payload(status="approved"),
    )
    session = _db(client)
    try:
        without = ai_context.build_context_bundle(
            session,
            ai_context.request_from_generate(
                GenerateRequest(
                    prompt_override="장면을 써줘",
                    context={"project_id": project["id"]},
                )
            ),
        )
        assert not any("트렌드 참고자료" in block for block in without.blocks)
        assert "trend_pack_included" not in without.metadata

        with_pack = ai_context.build_context_bundle(
            session,
            ai_context.request_from_generate(
                GenerateRequest(
                    prompt_override="장면을 써줘",
                    context={"project_id": project["id"], "include_trend_pack": True},
                )
            ),
        )
        trend_blocks = [block for block in with_pack.blocks if "트렌드 참고자료" in block]
        assert len(trend_blocks) == 1
        assert "관계 규합형 성장" in trend_blocks[0]
        assert "정본·사실·작가 지시가 아님" in trend_blocks[0]
        assert with_pack.metadata["trend_pack_included"] is True
        assert with_pack.metadata["trend_pack_status"] == "approved"
        assert with_pack.metadata["trend_pack_version"] == 1
        assert "관계 규합형 성장" not in with_pack.source_text
    finally:
        session.close()


def test_unsupported_trend_pack_schema_is_never_injected(client):
    from app.models import ProjectTrendPack

    project = _project(client)
    client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json=_pack_payload(status="approved"),
    )
    session = _db(client)
    try:
        pack = session.query(ProjectTrendPack).filter_by(project_id=project["id"]).one()
        pack.schema_version = "trend-pack-v999"
        session.commit()
        bundle = ai_context.build_context_bundle(
            session,
            ai_context.request_from_generate(
                GenerateRequest(
                    prompt_override="장면을 써줘",
                    context={"project_id": project["id"], "include_trend_pack": True},
                )
            ),
        )
        assert not any("트렌드 참고자료" in block for block in bundle.blocks)
        assert bundle.metadata["trend_pack_included"] is False
        assert bundle.metadata["trend_pack_reason"] == "unsupported_schema_version"
    finally:
        session.close()


def test_unsupported_trend_pack_schema_stays_quarantined_after_partial_update(client):
    from app.models import ProjectTrendPack

    project = _project(client)
    client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json=_pack_payload(status="approved"),
    )
    session = _db(client)
    try:
        pack = session.query(ProjectTrendPack).filter_by(project_id=project["id"]).one()
        pack.schema_version = "trend-pack-v999"
        session.commit()
    finally:
        session.close()

    response = client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json={"source": "author"},
    )
    assert response.status_code == 409

    session = _db(client)
    try:
        bundle = ai_context.build_context_bundle(
            session,
            ai_context.request_from_generate(
                GenerateRequest(
                    prompt_override="장면을 써줘",
                    context={"project_id": project["id"], "include_trend_pack": True},
                )
            ),
        )
        assert bundle.metadata["trend_pack_reason"] == "unsupported_schema_version"
        assert not any("트렌드 참고자료" in block for block in bundle.blocks)
    finally:
        session.close()


def test_malformed_trend_pack_payload_is_never_injected(client):
    from app.models import ProjectTrendPack

    project = _project(client)
    client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json=_pack_payload(status="approved"),
    )
    session = _db(client)
    try:
        pack = session.query(ProjectTrendPack).filter_by(project_id=project["id"]).one()
        pack.payload_json = ["not", "an", "object"]
        session.commit()
        bundle = ai_context.build_context_bundle(
            session,
            ai_context.request_from_generate(
                GenerateRequest(
                    prompt_override="장면을 써줘",
                    context={"project_id": project["id"], "include_trend_pack": True},
                )
            ),
        )
        assert not any("트렌드 참고자료" in block for block in bundle.blocks)
        assert bundle.metadata["trend_pack_included"] is False
        assert bundle.metadata["trend_pack_reason"] == "invalid_payload"
    finally:
        session.close()


def test_unapproved_trend_pack_is_never_injected_even_when_opted_in(client):
    project = _project(client)
    client.put(
        f"/api/v1/projects/{project['id']}/trend-pack",
        json=_pack_payload(status="draft"),
    )
    session = _db(client)
    try:
        bundle = ai_context.build_context_bundle(
            session,
            ai_context.request_from_generate(
                GenerateRequest(
                    prompt_override="장면을 써줘",
                    context={"project_id": project["id"], "include_trend_pack": True},
                )
            ),
        )
        assert not any("트렌드 참고자료" in block for block in bundle.blocks)
        assert bundle.metadata["trend_pack_included"] is False
        assert bundle.metadata["trend_pack_reason"] == "missing_or_unapproved"
    finally:
        session.close()
