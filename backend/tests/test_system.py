"""GET /system/db-info — A-039 백업 안내용 DB 경로 제공 테스트."""


def test_db_info_returns_path_and_companions(client):
    r = client.get("/api/v1/system/db-info")
    assert r.status_code == 200
    body = r.json()
    assert body["path"].endswith(".db")
    for ext in ("-wal", "-shm"):
        assert any(f.endswith(ext) for f in body["companion_files"])
