"""Antigravity CLI(agy) 감수 provider.

생성은 고정 GPT OAuth 브릿지 계약을 유지하고, 감수만 로컬 `agy` CLI를
subprocess로 호출해 Gemini 등 다른 모델이 수행하도록 라우팅한다.
credential은 agy의 ~/.gemini OAuth 저장소가 소유하며 앱 코드에는 비밀이
없다 — 브릿지와 같은 '앱에는 credential 없음' 경계다. agy는 샌드박스
모드로 실행해 감수 중 로컬 파일/명령 접근을 차단한다.

활성화: JIPPEEL_REVIEW_PROVIDER=agy
  JIPPEEL_AGY_MODEL     감수 모델 (기본 gemini-3.8-flash-high)
  JIPPEEL_AGY_BIN       agy 바이너리 (기본 agy → 미발견 시 ~/.local/bin/agy)
  JIPPEEL_AGY_TIMEOUT_S 감수 호출 제한시간 초 (기본 300)

백엔드가 Windows 프로세스(prod.sh가 .venv/Scripts/python.exe로 기동)일
때는 wsl.exe 경유로 WSL의 agy를 호출한다. 큰 프롬프트는 Windows argv
길이 제한을 피하기 위해 argv 대신 stdin 파이프로 전달한다
(bash -c 'agy -p "$(cat)"').
"""

import asyncio
import json
import os
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass

PROVIDER_NAME = "antigravity-agy"
DEFAULT_AGY_MODEL = "gemini-3.8-flash-high"
DEFAULT_TIMEOUT_S = 300


class AgyReviewError(RuntimeError):
    """agy 감수 호출 실패 — transport/프로세스 수준 오류."""


@dataclass(frozen=True)
class AgyReviewConfig:
    bin_path: str
    model: str
    timeout_s: int


def get_agy_review_config() -> AgyReviewConfig | None:
    """JIPPEEL_REVIEW_PROVIDER=agy일 때만 감수 라우팅 설정을 반환한다."""
    if os.environ.get("JIPPEEL_REVIEW_PROVIDER", "").strip().lower() != "agy":
        return None
    bin_path = os.environ.get("JIPPEEL_AGY_BIN", "agy")
    if os.name != "nt":
        resolved = shutil.which(bin_path) or (
            os.path.expanduser("~/.local/bin/agy")
            if os.path.isfile(os.path.expanduser("~/.local/bin/agy"))
            else bin_path
        )
        bin_path = resolved
    model = os.environ.get("JIPPEEL_AGY_MODEL", DEFAULT_AGY_MODEL)
    try:
        timeout_s = int(os.environ.get("JIPPEEL_AGY_TIMEOUT_S", DEFAULT_TIMEOUT_S))
    except ValueError:
        timeout_s = DEFAULT_TIMEOUT_S
    return AgyReviewConfig(bin_path=bin_path, model=model, timeout_s=timeout_s)


def flatten_messages(messages: list[dict]) -> str:
    """chat 메시지 목록을 agy -p 단일 프롬프트로 평탄화한다."""
    parts = []
    for m in messages:
        role = {"system": "시스템 지시", "user": "작업"}.get(m.get("role"), "메시지")
        parts.append(f"[{role}]\n{m.get('content') or ''}")
    return "\n\n".join(parts)


def _agy_parse_event(line: bytes) -> dict:
    """NDJSON 라인을 이벤트 dict로 파싱한다 — 불가/비-dict면 {}."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return {}
    return event if isinstance(event, dict) else {}


def _agy_event_text_delta(event: dict) -> str | None:
    """step_update 이벤트에서 agent_response text_delta만 추출한다."""
    if event.get("event") != "step_update":
        return None
    su = event.get("step_update") or {}
    if su.get("step_type") != "agent_response":
        return None
    return su.get("text_delta") or None


def _agy_result_error(event: dict) -> str | None:
    """result 이벤트가 SUCCESS가 아니면 에러 상세를, 정상/무관이면 None을 반환한다."""
    if event.get("event") != "result":
        return None
    result = event.get("result") or {}
    if result.get("status") == "SUCCESS":
        return None
    return str(result.get("error") or result.get("response")
               or result.get("status") or "unknown")


async def stream_agy_chat(
    cfg: AgyReviewConfig, model: str, messages: list[dict],
) -> AsyncIterator[str]:
    """llm.stream_chat과 같은 '텍스트 델타 async generator' 계약.

    agy를 --output-format stream-json으로 실행하고 step_update의
    agent_response text_delta를 그대로 yield한다. result 이벤트의
    status가 SUCCESS가 아니면 AgyReviewError를 던진다.
    """
    prompt = flatten_messages(messages)
    if os.name == "nt":
        # 백엔드는 Windows 프로세스 — WSL의 agy를 wsl.exe 경유로 호출.
        # 프롬프트는 stdin 파이프로 전달해 Windows argv 길이 제한을 피한다.
        argv = [
            "wsl.exe", "-e", "bash", "-lc",
            'exec "$3" -p "$(cat)" --model "$1" --output-format stream-json '
            '--print-timeout "$2s" --sandbox',
            "agy-review", model, str(cfg.timeout_s), cfg.bin_path,
        ]
        stdin_mode = asyncio.subprocess.PIPE
    else:
        argv = [
            cfg.bin_path, "-p", prompt,
            "--model", model,
            "--output-format", "stream-json",
            "--print-timeout", f"{cfg.timeout_s}s",
            "--sandbox",
        ]
        stdin_mode = asyncio.subprocess.DEVNULL
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=stdin_mode,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError as exc:
        raise AgyReviewError(f"agy 실행 실패: {exc}") from exc

    result_status: str | None = None
    result_detail = ""
    try:
        if os.name == "nt" and proc.stdin is not None:
            proc.stdin.write(prompt.encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()
        assert proc.stdout is not None
        while True:
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=cfg.timeout_s + 30)
            except TimeoutError as exc:
                raise AgyReviewError("agy 감수 시간 초과") from exc
            if not line:
                break
            event = _agy_parse_event(line)
            delta = _agy_event_text_delta(event)
            if delta:
                yield delta
            if event.get("event") == "result":
                err = _agy_result_error(event)
                result_status = "ERROR" if err is not None else "SUCCESS"
                result_detail = err or ""
        await proc.wait()
        if result_status != "SUCCESS":
            raise AgyReviewError(
                f"agy 감수 실패(status={result_status or proc.returncode})"
                f"{': ' + result_detail[:300] if result_detail else ''}")
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
