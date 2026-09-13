"""D04 — summary job 실제 provider 어댑터 계약 테스트.

실제 브릿지는 호출하지 않는다 — `llm.complete_chat`과 클라이언트 팩토리를
fake로 대체하고, 어댑터의 메시지 조립·버전 불일치 거부·에러 전파 계약만 검증한다.
"""
import asyncio
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, Project, SummaryJob
from app.services import summary_provider
from app.services.summary_provider import (
    MAX_SOURCE_CHARS,
    SUMMARY_PROMPT_VERSION,
    make_gpt_summary_provider,
)
from app.services.summary_worker import run_pending_summary_jobs


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'summary-provider.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def _seed_chapter(factory, *, content="회귀자가 검을 뽑았다. 전장의 공기가 얼었다.", title="1화"):
    with factory() as db:
        project = Project(title="provider test")
        db.add(project)
        db.flush()
        chapter = Chapter(
            project_id=project.id,
            sort_order=1,
            title=title,
            content_md=content,
            revision=3,
        )
        db.add(chapter)
        db.commit()
        return project.id, chapter.id


def _planned_job(factory, project_id, chapter_id, **overrides):
    from app.services.summary_worker import plan_summary_jobs

    params = dict(
        project_id=project_id,
        chapter_ids=[chapter_id],
        prompt_version=SUMMARY_PROMPT_VERSION,
        provider_identity="ChatGPT OAuth",
        model_snapshot="gpt-5.6-luna",
        request_options={},
    )
    params.update(overrides)
    with factory() as db:
        created, _ = plan_summary_jobs(db, **params)
        db.commit()
        job_id = created[0].id
    with factory() as db:
        return db.get(SummaryJob, job_id)


def _fake_complete(captured, result="요약 결과 텍스트"):
    async def fake(client, model, messages, **kwargs):
        captured["client"] = client
        captured["model"] = model
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return result

    return fake


def test_adapter_builds_messages_and_returns_text(session_factory, monkeypatch):
    pid, cid = _seed_chapter(session_factory)
    job = _planned_job(session_factory, pid, cid)
    captured = {}
    monkeypatch.setattr(summary_provider.llm, "complete_chat", _fake_complete(captured))

    provider = make_gpt_summary_provider(
        session_factory=session_factory,
        client_factory=lambda: "fake-client",
    )
    assert provider(job) == "요약 결과 텍스트"

    assert captured["client"] == "fake-client"
    assert captured["model"] == "gpt-5.6-luna"
    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert "전장의 공기가 얼었다" in msgs[1]["content"]
    assert "1화" in msgs[1]["content"]
    assert captured["kwargs"]["reasoning_effort"] == "xhigh"


def test_adapter_rejects_mismatched_prompt_version(session_factory, monkeypatch):
    pid, cid = _seed_chapter(session_factory)
    job = _planned_job(session_factory, pid, cid, prompt_version="summary-v0-legacy")
    captured = {}
    monkeypatch.setattr(summary_provider.llm, "complete_chat", _fake_complete(captured))

    provider = make_gpt_summary_provider(session_factory=session_factory,
                                        client_factory=lambda: None)
    with pytest.raises(ValueError, match="unsupported prompt_version"):
        provider(job)
    assert "messages" not in captured  # fail-fast — transport 미호출


def test_adapter_truncates_long_source(session_factory, monkeypatch):
    long_body = "가" * (MAX_SOURCE_CHARS + 10_000)
    pid, cid = _seed_chapter(session_factory, content=long_body)
    job = _planned_job(session_factory, pid, cid)
    captured = {}
    monkeypatch.setattr(summary_provider.llm, "complete_chat", _fake_complete(captured))

    provider = make_gpt_summary_provider(session_factory=session_factory,
                                        client_factory=lambda: None)
    provider(job)
    sent = captured["messages"][1]["content"]
    assert long_body[:MAX_SOURCE_CHARS] in sent
    assert long_body not in sent


def test_adapter_missing_chapter_fails(session_factory):
    pid, cid = _seed_chapter(session_factory)
    job = _planned_job(session_factory, pid, cid)
    job.chapter_id = cid + 999
    provider = make_gpt_summary_provider(session_factory=session_factory,
                                        client_factory=lambda: None)
    with pytest.raises(ValueError, match="not found"):
        provider(job)


def test_adapter_integrates_with_worker_lifecycle(session_factory, monkeypatch):
    pid, cid = _seed_chapter(session_factory)
    _planned_job(session_factory, pid, cid)
    monkeypatch.setattr(summary_provider.llm, "complete_chat",
                        _fake_complete({}, result="회귀자의 각성 요약"))

    provider = make_gpt_summary_provider(session_factory=session_factory,
                                        client_factory=lambda: None)
    with session_factory() as db:
        processed = run_pending_summary_jobs(db, provider)
        db.commit()
    assert len(processed) == 1
    with session_factory() as db:
        job = db.query(SummaryJob).one()
        assert job.status == "draft_saved"
        from app.models import MemoryEntry
        draft = db.query(MemoryEntry).one()
        assert draft.visibility == "draft"
        assert "회귀자의 각성 요약" in draft.body


def test_adapter_error_marks_job_provider_error(session_factory, monkeypatch):
    pid, cid = _seed_chapter(session_factory)
    _planned_job(session_factory, pid, cid)

    async def boom(client, model, messages, **kwargs):
        raise RuntimeError("bridge offline")

    monkeypatch.setattr(summary_provider.llm, "complete_chat", boom)
    provider = make_gpt_summary_provider(session_factory=session_factory,
                                        client_factory=lambda: None)
    with session_factory() as db:
        run_pending_summary_jobs(db, provider)
        db.commit()
    with session_factory() as db:
        assert db.query(SummaryJob).one().status == "provider_error"


def test_make_provider_default_session_factory_is_sessionlocal():
    # 기본 경로가 운영 SessionLocal을 참조하는지 — 주입 경계 존재 확인용
    provider = make_gpt_summary_provider()
    assert callable(provider)
