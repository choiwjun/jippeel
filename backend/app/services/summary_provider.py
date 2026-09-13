"""D04 — summary job용 실제 provider 어댑터.

`run_pending_summary_jobs`에 주입할 `SummaryProvider`를 고정 GPT OAuth
브릿지 경로로 만든다. 어댑터는 요청을 조립해 `llm.complete_chat`으로
전달할 뿐 — 실제 브릿지 호출·비용·운영 적용은 G02 승인 게이트 대상이다.

결정:
- 프롬프트는 job의 `prompt_version`과 무관하게 이 모듈의
  ``SUMMARY_PROMPT_VERSION`` 템플릿으로 고정한다. job의 prompt_version은
  매니페스트 무결성(idempotency) 목적이며, 어댑터는 자기 템플릿 버전이
  job과 다르면 fail-fast해 조용한 프롬프트 드리프트를 막는다.
- 원문은 ``MAX_SOURCE_CHARS``로 절단해 단일 호출 비용·컨텍스트를 상한한다.
- provider 실패는 그대로 전파 — worker가 ``provider_error``(재시도 가능)로
  기록한다.
"""
from __future__ import annotations

import asyncio
from typing import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.models import Chapter, SummaryJob
from app.services import llm
from app.services.gpt_oauth import get_provider
from app.services.summary_worker import SummaryProvider

SUMMARY_PROMPT_VERSION = "summary-v1"

# 단일 호출 상한 — 장문 원고 전체를 그대로 보내지 않는다.
MAX_SOURCE_CHARS = 60_000

_SYSTEM_PROMPT = (
    "당신은 한국 웹소설 회차의 요약을 작성하는 보조 도구입니다. "
    "아래 회차 본문을 읽고, 이후 집필 맥락으로 재사용할 수 있게 핵심 사건·"
    "인물 행동·설정 정보를 한국어로 간결하게 요약하세요. "
    "창작하지 말고 본문에 있는 사실만 요약하세요."
)


def _build_messages(job: SummaryJob, source_text: str, chapter_title: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"회차 제목: {chapter_title}\n"
                f"회차 ID: {job.chapter_id}\n\n"
                f"본문:\n{source_text[:MAX_SOURCE_CHARS]}"
            ),
        },
    ]


def make_gpt_summary_provider(
    *,
    session_factory: sessionmaker | None = None,
    client_factory: Callable[[], object] | None = None,
) -> SummaryProvider:
    """`run_pending_summary_jobs`에 주입할 실제 provider callable을 만든다.

    session_factory/client_factory는 테스트에서 합성 DB·fake transport를
    주입하기 위한 경계다. 기본값은 운영 SessionLocal과 고정 OAuth 브릿지다.
    """
    factory = session_factory or SessionLocal

    def provider(job: SummaryJob) -> str:
        if job.prompt_version != SUMMARY_PROMPT_VERSION:
            raise ValueError(
                f"unsupported prompt_version {job.prompt_version!r} "
                f"(adapter expects {SUMMARY_PROMPT_VERSION!r})"
            )
        with factory() as db:
            chapter = db.get(Chapter, job.chapter_id)
            if chapter is None:
                raise ValueError(f"chapter {job.chapter_id} not found")
            title = chapter.title or ""
            source = chapter.content_md or ""

        resolved = get_provider()
        client = (
            client_factory()
            if client_factory is not None
            else llm.make_client(resolved.base_url, None)
        )
        return asyncio.run(
            llm.complete_chat(
                client,  # type: ignore[arg-type]
                resolved.default_model,
                _build_messages(job, source, title),
                reasoning_effort=resolved.reasoning_effort,
            )
        )

    return provider
