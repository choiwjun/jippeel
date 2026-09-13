"""SPA fallback — 운영 모드(uvicorn 정적 서빙)에서 클라이언트 라우트
(/settings, /projects/1/write) 직접 접근·새로고침은 index.html을 반환하고,
API 경로 404는 JSON으로 유지돼야 한다 (G04 실제 브라우저 검증에서 발견)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import _SPAStaticFiles


def _app(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>SPA-SHELL</body></html>")
    (tmp_path / "asset.txt").write_text("ASSET-OK")
    app = FastAPI()

    @app.get("/api/v1/healthcheck")
    def _hc():
        return {"ok": True}

    app.mount("/", _SPAStaticFiles(directory=tmp_path, html=True), name="frontend")
    return TestClient(app)


def test_deep_client_route_returns_index(tmp_path):
    c = _app(tmp_path)
    for route in ("/settings", "/projects/1/write", "/projects/2/lore"):
        r = c.get(route)
        assert r.status_code == 200, route
        assert "SPA-SHELL" in r.text, route
        assert "text/html" in r.headers["content-type"]


def test_real_file_still_served(tmp_path):
    c = _app(tmp_path)
    r = c.get("/asset.txt")
    assert r.status_code == 200 and r.text == "ASSET-OK"


def test_api_404_stays_json(tmp_path):
    c = _app(tmp_path)
    r = c.get("/api/v1/no-such-endpoint")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_api_route_unaffected(tmp_path):
    c = _app(tmp_path)
    assert c.get("/api/v1/healthcheck").json() == {"ok": True}


def test_head_request_fallback(tmp_path):
    c = _app(tmp_path)
    r = c.head("/settings")
    assert r.status_code == 200
