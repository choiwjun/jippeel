"""E2E용 가짜 OpenAI 호환 LLM 서버 (:1234).

LM Studio 대역 — GET /v1/models, POST /v1/chat/completions(SSE 스트리밍).
응답 본문은 app-flow.spec.ts의 FAKE_LLM_OUTPUT과 일치해야 한다.

실행: python scripts/fake_llm_server.py  (포트 1234)
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

FAKE_OUTPUT = "안녕하세요, 테스트응답입니다."
CHUNK_SIZE = 4  # 한글자음 단위 스트림 흉내


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send_json(200, {"data": [{"id": "fake-model"}]})
        else:
            self._send_json(404, {"detail": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._send_json(404, {"detail": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(0, len(FAKE_OUTPUT), CHUNK_SIZE):
            chunk = {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"content": FAKE_OUTPUT[i:i + CHUNK_SIZE]},
                             "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):  # 테스트 출력 오염 방지
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 1234), Handler).serve_forever()
