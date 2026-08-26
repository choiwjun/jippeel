"""회차 CRUD · 상태 변경 · 본문 저장 통합 테스트."""


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "테스트 작품"}).json()["id"]


def _mk_chapter(client, pid: int, **kwargs) -> dict:
    return client.post(f"/api/v1/projects/{pid}/chapters", json=kwargs).json()


def test_create_chapter_defaults(client):
    pid = _mk_project(client)
    body = _mk_chapter(client, pid, title="프롤로그")
    assert body["volume"] == 1
    assert body["status"] == "초고"
    assert body["content_md"] == ""
    assert body["word_count_cache"] == 0


def test_chapter_tree_ordered_and_lightweight(client):
    pid = _mk_project(client)
    _mk_chapter(client, pid, title="B", volume=2)
    _mk_chapter(client, pid, title="A", volume=1)
    items = client.get(f"/api/v1/projects/{pid}/chapters").json()
    assert [c["title"] for c in items] == ["A", "B"]
    # 트리 응답은 본문 미포함(경량화)
    assert "content_md" not in items[0]


def test_volume_filter(client):
    pid = _mk_project(client)
    _mk_chapter(client, pid, volume=1)
    _mk_chapter(client, pid, volume=2)
    r = client.get(f"/api/v1/projects/{pid}/chapters", params={"volume": 2})
    assert len(r.json()) == 1


def test_invalid_status_rejected(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.patch(f"/api/v1/chapters/{cid}", json={"status": "출간"})
    assert r.status_code == 422


def test_status_change_flow(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    for st in ("수정중", "완료"):
        r = client.patch(f"/api/v1/chapters/{cid}", json={"status": st})
        assert r.status_code == 200 and r.json()["status"] == st


def test_put_content_updates_word_count(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]

    content = "첫 문장입니다.\n\n둘째 문장!"
    r = client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": content})
    assert r.status_code == 200
    body = r.json()
    assert body["content_md"] == content
    assert body["word_count_cache"] == 12  # 공백 제외


def test_post_content_beacon_alias_matches_put(client):
    """sendBeacon(POST) 언로드 플러시 수용 — QA Minor #1 해소."""
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]

    r = client.post(f"/api/v1/chapters/{cid}/content",
                    json={"content_md": "언로드 직전 저장"})
    assert r.status_code == 200
    body = r.json()
    assert body["content_md"] == "언로드 직전 저장"
    assert body["word_count_cache"] > 0

    # PUT과 동일하게 캐시가 갱신됐는지 재조회로 확인
    got = client.get(f"/api/v1/chapters/{cid}").json()
    assert got["word_count_cache"] == body["word_count_cache"]


def test_patch_memo_and_title(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    r = client.patch(
        f"/api/v1/chapters/{cid}", json={"memo": "다음 화 복선 메모", "title": "1화"}
    )
    assert r.json()["memo"] == "다음 화 복선 메모"
    assert r.json()["title"] == "1화"


def test_delete_chapter(client):
    pid = _mk_project(client)
    cid = _mk_chapter(client, pid)["id"]
    assert client.delete(f"/api/v1/chapters/{cid}").status_code == 204
    assert client.get(f"/api/v1/chapters/{cid}").status_code == 404


def test_create_chapter_on_missing_project_404(client):
    r = client.post("/api/v1/projects/9999/chapters", json={})
    assert r.status_code == 404
