"""openai SDK 래퍼 — OpenAI 호환 엔드포인트 호출 (사양 §2.1, 부록05 §L7).

base_url 오버라이드로 LM Studio·KoboldCpp·클라우드 등 무엇이든 호환(FR-401).
api_key는 이 계층에서만 복호화되어 프론트에 절대 노출되지 않는다(NFR-202).
"""
import json

import openai

from app.services.crypto import get_cipher

REQUEST_TIMEOUT = 120.0  # 초 — 로컬 LLM 첫 토큰 지연 감안


def make_client(base_url: str, api_key_encrypted: str | None) -> openai.AsyncOpenAI:
    """저장된 암호문을 복호화해 AsyncOpenAI 클라이언트를 만든다.

    api_key 미설정 엔드포인트(로컬 LM Studio 등)는 SDK 요구 형식 맞춤용
    더미 키("sk-local")를 쓴다. 실제 키가 유출되지 않는다.
    """
    if api_key_encrypted:
        api_key = get_cipher().decrypt(api_key_encrypted)
    else:
        api_key = "sk-local"
    return openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=REQUEST_TIMEOUT)


async def stream_chat(client: openai.AsyncOpenAI, model: str, messages: list[dict],
                      temperature: float | None = None,
                      max_tokens: int | None = None):
    """chat.completions 스트리밍 — content delta만 yield한다.

    타임아웃·연결실패 등 openai.APIError 계열은 그대로 전파하고
    라우터에서 FR-408 사용자 안내 메시지로 변환한다.
    """
    kwargs: dict = {"model": model, "messages": messages, "stream": True}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = await client.chat.completions.create(**kwargs)
    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def complete_chat(client: openai.AsyncOpenAI, model: str, messages: list[dict],
                        temperature: float | None = None,
                        max_tokens: int | None = None) -> str:
    """비(非)스트리밍 chat.completions — JSON 등 구조화 출력용.

    스트리밍이 필요 없는 내부 파이프라인(부트스트랩 등)에서 stream_chat과
    동일한 클라이언트·에러 전파 계약을 공유한다.
    """
    kwargs: dict = {"model": model, "messages": messages}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    response = await client.chat.completions.create(**kwargs)
    # 반환 계약은 "항상 str"로 고정한다. openai SDK 3.x는 호환 서버가
    # 표준 chat.completion JSON이 아닌 원문(SSE·일반 텍스트)을 돌려주면
    # 예외 대신 str을 반환하므로, 여기서 content 문자열로 정규화한다.
    if isinstance(response, str):
        assembled = _content_from_sse(response) if "data:" in response else None
        return assembled if assembled is not None else response
    if not response.choices:
        return ""
    return response.choices[0].message.content or ""


def _content_from_sse(text: str) -> str | None:
    """SSE(text/event-stream) 본문에서 chat completion content를 재조립한다.

    일부 OpenAI 호환 서버(LM Studio 등)는 stream 파라미터와 무관하게 SSE로만
    응답한다. delta.content(스트리밍 청크)와 message.content(단발 응답)를
    모두 이어 붙인다. SSE 프레임이 아니라고 판단되면 None을 반환해
    호출부가 원문을 그대로 전달하도록 한다.
    """
    parts: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            return None
        choices = chunk.get("choices") or []
        if not choices:
            continue
        content = (choices[0].get("delta") or {}).get("content")             or (choices[0].get("message") or {}).get("content")
        if isinstance(content, str):
            parts.append(content)
    return "".join(parts) if parts else None
