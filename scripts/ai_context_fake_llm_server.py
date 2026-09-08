#!/usr/bin/env python3
r"""Deterministic OpenAI-compatible provider for AI context Task 4.

This server is QA-only. It binds to 127.0.0.1, returns protocol-valid
OpenAI-compatible chat/model responses, and writes every chat request payload to
JSONL before responding. The JSONL payload.messages entries are the assertion
source for integration tests.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import time
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
MODEL_ID = "ai-context-fake"

PLANNER_RESPONSE = {
    "scenes": [
        {
            "order": 1,
            "title": "장면 1 — 닫을 문 앞",
            "purpose": "시리즈 갈등을 닫기 전에 선택을 확인한다",
            "objective": "문 앞에 선다",
            "choice": "복수보다 구출을 택한다",
            "cost": "왕좌를 포기한다",
            "required_beats": ["문 앞에 선다", "강무진을 먼저 부른다"],
            "characters": ["한서윤", "강무진"],
            "opening_state": "결전 직후",
            "closing_hook": "마지막 선택의 대가가 드러난다",
            "ending_intent": None,
        },
        {
            "order": 2,
            "title": "장면 2 — 끝내는 손",
            "purpose": "시리즈 핵심 갈등과 감정선을 닫는다",
            "objective": "구출을 끝낸다",
            "choice": "살아갈 쪽을 고른다",
            "cost": "왕좌와 복수의 명분을 내려놓는다",
            "required_beats": ["구출한다", "대가를 받아들인다"],
            "characters": ["한서윤", "강무진"],
            "opening_state": "문이 열린 뒤",
            "closing_hook": None,
            "ending_intent": "두 인물이 선택의 대가를 받아들이고 이야기를 닫는다",
        },
    ]
}

RESPONSES = {
    "draft": "AI_CONTEXT_DRAFT\n한서윤은 강무진의 손을 놓지 않았다.",
    "worker_1": "AI_CONTEXT_PARALLEL_SCENE_1\n한서윤은 문 앞에서 강무진의 이름을 불렀다.",
    "worker_2": "AI_CONTEXT_PARALLEL_SCENE_2\n강무진은 돌아왔고, 두 사람은 왕좌보다 살아갈 내일을 골랐다.",
    "single_review": "[감수]\n- AI_CONTEXT_SINGLE_REVIEW 목적·관계·복선 허용 범위를 확인했다.\n[수정본]\nAI_CONTEXT_REFINED\n한서윤은 강무진의 손을 놓지 않았다.",
    "parallel_review": "[감수]\n- AI_CONTEXT_PARALLEL_REVIEW 장면 순서와 최종화 목적을 확인했다.",
    "canon": json.dumps({"issues": []}, ensure_ascii=False),
}


def _message_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.append(json.dumps(content, ensure_ascii=False))
        else:
            parts.append(str(content))
    return "\n".join(parts)


def classify(messages: list[dict[str, Any]]) -> tuple[str, str]:
    """Classify route phase before generic draft/review fallback."""
    text = _message_text(messages)
    last_user = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            last_user = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            break

    if "[병렬 Planner" in last_user:
        return "planner", json.dumps(PLANNER_RESPONSE, ensure_ascii=False)
    if "[병렬 Worker" in text:
        # Pick a deterministic worker body from the scene contract/order in the full provider payload.
        # Worker requests run concurrently, so logging must not depend on arrival order.
        if re.search(r'"order"\s*:\s*2', text):
            return "worker", RESPONSES["worker_2"]
        return "worker", RESPONSES["worker_1"]
    if "설정 모순을 검사하라" in text or "연속성 검수" in text:
        return "canon", RESPONSES["canon"]
    if "장면별 조립 원고" in last_user:
        return "parallel_review", RESPONSES["parallel_review"]
    if "[초안 원고]" in last_user:
        return "single_review", RESPONSES["single_review"]
    return "draft", RESPONSES["draft"]


class Handler(BaseHTTPRequestHandler):
    prompt_log: Path
    log_lock = threading.Lock()

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        clean_path = self.path.split("?", 1)[0].rstrip("/")
        if clean_path in ("/health", "/v1/health"):
            self._send_json(200, {"status": "ok"})
            return
        if clean_path in ("/models", "/v1/models"):
            self._send_json(200, {"object": "list", "data": [{"id": MODEL_ID, "object": "model"}]})
            return
        self._send_json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        clean_path = self.path.split("?", 1)[0].rstrip("/")
        if clean_path not in ("/chat/completions", "/v1/chat/completions"):
            self._send_json(404, {"detail": "not found"})
            return
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"detail": "invalid json"})
            return
        messages = payload.get("messages") or []
        kind, content = classify(messages if isinstance(messages, list) else [])
        self.prompt_log.parent.mkdir(parents=True, exist_ok=True)
        with self.log_lock:
            with self.prompt_log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": time.time(),
                    "kind": kind,
                    "path": clean_path,
                    "payload": payload,
                    "response_content": content,
                }, ensure_ascii=False) + "\n")

        model = payload.get("model") or MODEL_ID
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("content-type", "text/event-stream; charset=utf-8")
            self.send_header("cache-control", "no-cache")
            self.send_header("connection", "close")
            self.end_headers()
            chunks = [content]
            for delta in chunks:
                frame = {
                    "id": f"chatcmpl-{kind}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(frame, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
            done = {
                "id": f"chatcmpl-{kind}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            self.wfile.write(f"data: {json.dumps(done, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return

        self._send_json(200, {
            "id": f"chatcmpl-{kind}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
        })

    def log_message(self, *_args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="AI context Task 4 fake OpenAI provider")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--prompt-log", type=Path, required=True)
    args = parser.parse_args()
    Handler.prompt_log = args.prompt_log
    with ThreadingHTTPServer((HOST, args.port), Handler) as server:
        with contextlib.suppress(Exception):
            args.prompt_log.parent.mkdir(parents=True, exist_ok=True)
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
