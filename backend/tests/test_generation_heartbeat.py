"""생성 heartbeat와 long-running 호출의 회귀 테스트."""
import asyncio
import json

from app.routers import ai_panel


def test_generation_heartbeat_does_not_cancel_slow_source():
    async def exercise():
        async def source():
            await asyncio.sleep(0.03)
            yield {"event": "done", "data": "[DONE]"}

        old_interval = ai_panel.GENERATION_HEARTBEAT_INTERVAL_SECONDS
        ai_panel.GENERATION_HEARTBEAT_INTERVAL_SECONDS = 0.01
        try:
            return [event async for event in ai_panel._with_generation_heartbeat(source(), "draft")]
        finally:
            ai_panel.GENERATION_HEARTBEAT_INTERVAL_SECONDS = old_interval

    events = asyncio.run(exercise())

    assert any(event["event"] == "heartbeat" for event in events)
    heartbeat = next(event for event in events if event["event"] == "heartbeat")
    data = json.loads(heartbeat["data"])
    assert data["stage"] == "draft"
    assert data["elapsed_seconds"] >= 0
    assert events[-1] == {"event": "done", "data": "[DONE]"}


def test_generation_heartbeat_cancels_source_when_client_stops_reading():
    async def exercise():
        cancelled = asyncio.Event()

        async def source():
            try:
                await asyncio.Event().wait()
                yield {"event": "done", "data": "[DONE]"}
            finally:
                cancelled.set()

        generator = ai_panel._with_generation_heartbeat(source(), "draft")
        await generator.__anext__()
        await generator.aclose()
        return cancelled.is_set()

    assert asyncio.run(exercise())


def test_bootstrap_heartbeat_has_status_only_payload():
    async def exercise():
        async def slow_queue():
            await asyncio.sleep(0.03)
            yield None

        # bootstrap route uses the same cancellation-safe queue pattern; helper
        # contract is tested independently here to keep this test provider-free.
        return [event async for event in ai_panel._with_generation_heartbeat(slow_queue(), "generating")]

    old_interval = ai_panel.GENERATION_HEARTBEAT_INTERVAL_SECONDS
    ai_panel.GENERATION_HEARTBEAT_INTERVAL_SECONDS = 0.01
    try:
        events = asyncio.run(exercise())
    finally:
        ai_panel.GENERATION_HEARTBEAT_INTERVAL_SECONDS = old_interval

    heartbeat = next(event for event in events if event["event"] == "heartbeat")
    assert set(json.loads(heartbeat["data"])) == {"stage", "elapsed_seconds"}
