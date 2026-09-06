"""A-038 GET /projects/{pid}/plus-status (F-033) 테스트.

결정사항_G4 Q3: 프로젝트 내 회차 수 ≥15회.
글자 수: '완료' 회차가 1개 이상이고 그 모든 회차 word_count_cache ≥ 3,000.
"""


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "연작"}).json()["id"]


def _mk_chapter(client, pid: int, title="회차", cache=None, status=None) -> dict:
    body = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": title}).json()
    cid = body["id"]
    if cache is not None:
        # PUT content가 word_count_cache(공백제외)를 계산·저장한다
        r = client.put(f"/api/v1/chapters/{cid}/content", json={"content_md": "가" * cache})
        assert r.json()["word_count_cache"] == cache
    if status is not None:
        r = client.patch(f"/api/v1/chapters/{cid}", json={"status": status})
        assert r.status_code == 200
    return body


def test_plus_status_404_unknown_project(client):
    assert client.get("/api/v1/projects/9999/plus-status").status_code == 404


def test_plus_status_empty_project(client):
    pid = _mk_project(client)
    body = client.get(f"/api/v1/projects/{pid}/plus-status").json()
    assert body == {
        "chapter_count": 0,
        "chapter_count_met": False,
        "done_chapter_count": 0,
        "done_chapters_3000": 0,
        "done_chars_met": False,
        "eligible": False,
    }


def test_plus_status_counts_and_eligibility(client):
    pid = _mk_project(client)
    for i in range(15):
        _mk_chapter(client, pid, f"{i + 1}화", cache=3500, status="완료")
    body = client.get(f"/api/v1/projects/{pid}/plus-status").json()
    assert body["chapter_count"] == 15
    assert body["chapter_count_met"] is True
    assert body["done_chapter_count"] == 15
    assert body["done_chapters_3000"] == 15
    assert body["done_chars_met"] is True
    assert body["eligible"] is True


def test_plus_status_fails_below_15_chapters(client):
    pid = _mk_project(client)
    for i in range(14):
        _mk_chapter(client, pid, f"{i + 1}화", cache=4000, status="완료")
    body = client.get(f"/api/v1/projects/{pid}/plus-status").json()
    assert body["chapter_count_met"] is False
    assert body["done_chars_met"] is True
    assert body["eligible"] is False


def test_plus_status_fails_when_done_under_3000(client):
    pid = _mk_project(client)
    for i in range(14):
        _mk_chapter(client, pid, f"{i + 1}화", cache=3500, status="완료")
    _mk_chapter(client, pid, "15화", cache=2999, status="완료")
    body = client.get(f"/api/v1/projects/{pid}/plus-status").json()
    assert body["chapter_count_met"] is True
    assert body["done_chapters_3000"] == 14
    assert body["done_chars_met"] is False
    assert body["eligible"] is False


def test_plus_status_no_done_chapters_means_not_met(client):
    pid = _mk_project(client)
    for i in range(16):
        _mk_chapter(client, pid, f"{i + 1}화", cache=5000)  # 전부 초고
    body = client.get(f"/api/v1/projects/{pid}/plus-status").json()
    assert body["chapter_count_met"] is True
    assert body["done_chars_met"] is False
    assert body["eligible"] is False


def test_plus_status_partial_done_mixed(client):
    """완료 아닌 회차는 글자 수 판정 대상에서 제외."""
    pid = _mk_project(client)
    for i in range(15):
        _mk_chapter(client, pid, f"{i + 1}화", cache=3200, status="완료")
    _mk_chapter(client, pid, "16화", cache=100)  # 초고
    body = client.get(f"/api/v1/projects/{pid}/plus-status").json()
    assert body["chapter_count"] == 16
    assert body["done_chapter_count"] == 15
    assert body["eligible"] is True
