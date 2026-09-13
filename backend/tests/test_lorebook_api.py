"""로어북 API 테스트 (FR-301~305 / Sprint 2)."""


def _create_project(client) -> int:
    res = client.post("/api/v1/projects", json={"title": "로어북 테스트"})
    assert res.status_code == 201
    return res.json()["id"]


def _create_entry(client, pid: int, title: str, **kwargs) -> dict:
    res = client.post(f"/api/v1/projects/{pid}/lore", json={"title": title, **kwargs})
    assert res.status_code == 201
    return res.json()


class TestLoreCRUD:
    def test_create_get_update_delete(self, client):
        pid = _create_project(client)
        entry = _create_entry(
            client, pid, "검기(劍氣)", category="용어", content="검에서 뿜어나오는 기운", keywords=["검기"]
        )
        lid = entry["id"]
        assert entry["category"] == "용어"

        assert client.get(f"/api/v1/lore/{lid}").status_code == 200

        res = client.patch(f"/api/v1/lore/{lid}", json={"content": "수정된 설명"})
        assert res.status_code == 200
        assert res.json()["content"] == "수정된 설명"
        assert res.json()["title"] == "검기(劍氣)"

        assert client.delete(f"/api/v1/lore/{lid}").status_code == 204
        assert client.get(f"/api/v1/lore/{lid}").status_code == 404

    def test_category_filter(self, client):
        pid = _create_project(client)
        _create_entry(client, pid, "북부산맥", category="장소")
        _create_entry(client, pid, "철혈단", category="세력")
        _create_entry(client, pid, "기타항목")

        res = client.get(f"/api/v1/projects/{pid}/lore", params={"category": "장소"})
        assert [e["title"] for e in res.json()] == ["북부산맥"]

    def test_missing_project_404(self, client):
        assert client.get("/api/v1/projects/9999/lore").status_code == 404


class TestKeywords:
    def test_put_keywords_replaces_and_dedupes(self, client):
        pid = _create_project(client)
        lid = _create_entry(client, pid, "마력", keywords=["마법"])["id"]

        res = client.put(f"/api/v1/lore/{lid}/keywords", json={"keywords": ["mana", "마력", "mana"]})
        assert res.status_code == 200
        assert res.json()["keywords"] == ["mana", "마력"]  # 중복 제거 + 전체 교체

    def test_keywords_in_create(self, client):
        pid = _create_project(client)
        entry = _create_entry(client, pid, "항목", keywords=["a", "b"])
        assert entry["keywords"] == ["a", "b"]


class TestSearch:
    def test_fts_search_matches_content_and_prefix(self, client):
        """FTS5 인덱스 경유 검색 — 조사 결합형 토큰도 접두어 매치(FR-304)."""
        pid = _create_project(client)
        hit = _create_entry(
            client, pid, "기운 강화", content="주인공이 검기를 휘두른다", keywords=["검"]
        )["id"]
        _create_entry(client, pid, "무관 항목", content="전혀 다른 이야기")

        # 본문 단어의 접두어 매치
        res = client.get(f"/api/v1/projects/{pid}/lore/search", params={"q": "검기"})
        assert res.status_code == 200
        assert [e["id"] for e in res.json()] == [hit]

        # 키워드 정확 매치
        res = client.get(f"/api/v1/projects/{pid}/lore/search", params={"q": "검"})
        assert [e["id"] for e in res.json()] == [hit]

    def test_search_limit_is_applied_after_project_scope(self, client):
        first_pid = _create_project(client)
        target_pid = _create_project(client)
        _create_entry(client, first_pid, "공통검색어 A", content="공통검색어")
        target = _create_entry(client, target_pid, "공통검색어 B", content="공통검색어")

        response = client.get(
            f"/api/v1/projects/{target_pid}/lore/search",
            params={"q": "공통검색어", "limit": 1},
        )

        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [target["id"]]

    def test_search_limit_is_applied_after_category_scope(self, client):
        pid = _create_project(client)
        _create_entry(client, pid, "공통검색어 장소", category="장소", content="공통검색어")
        target = _create_entry(client, pid, "공통검색어 용어", category="용어", content="공통검색어")

        response = client.get(
            f"/api/v1/projects/{pid}/lore/search",
            params={"q": "공통검색어", "category": "용어", "limit": 1},
        )

        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [target["id"]]


    def test_search_no_match_returns_empty(self, client):
        pid = _create_project(client)
        _create_entry(client, pid, "항목", content="내용")
        res = client.get(f"/api/v1/projects/{pid}/lore/search", params={"q": "존재하지않는단어"})
        assert res.status_code == 200
        assert res.json() == []

    def test_search_scoped_to_project(self, client):
        pid1 = _create_project(client)
        pid2 = _create_project(client)
        _create_entry(client, pid1, "공통제목", content="매직")
        _create_entry(client, pid2, "다른항목", content="매직")

        res = client.get(f"/api/v1/projects/{pid2}/lore/search", params={"q": "매직"})
        assert len(res.json()) == 1
        assert res.json()[0]["project_id"] == pid2

    def test_search_requires_q(self, client):
        pid = _create_project(client)
        assert client.get(f"/api/v1/projects/{pid}/lore/search").status_code == 422

    def test_index_sync_on_update_and_delete(self, client):
        pid = _create_project(client)
        lid = _create_entry(client, pid, "초기제목", content="낡은설정")["id"]

        client.patch(f"/api/v1/lore/{lid}", json={"content": "새로운설정"})
        res = client.get(f"/api/v1/projects/{pid}/lore/search", params={"q": "새로운"})
        assert [e["id"] for e in res.json()] == [lid]

        client.delete(f"/api/v1/lore/{lid}")
        res = client.get(f"/api/v1/projects/{pid}/lore/search", params={"q": "새로운"})
        assert res.json() == []


# ---------- U02 참조 회차 (F-016) ----------

def _mk_chapter(client, pid: int, title: str, content: str, sort_order: float | None = None) -> dict:
    body: dict = {"title": title}
    if sort_order is not None:
        body["sort_order"] = sort_order
    res = client.post(f"/api/v1/projects/{pid}/chapters", json=body)
    assert res.status_code == 201
    cid = res.json()["id"]
    if content:
        put = client.put(f"/api/v1/chapters/{cid}/content", json={
            "content_md": content, "expected_revision": res.json()["revision"],
        })
        assert put.status_code == 200
    return client.get(f"/api/v1/chapters/{cid}").json()


class TestReferencingChapters:
    def test_title_match_lists_chapter(self, client):
        pid = _create_project(client)
        entry = _create_entry(client, pid, "검기(劍氣)", keywords=["검기"])
        _mk_chapter(client, pid, "1화", "주인공이 검기를 폭발시켰다.", 1.0)
        _mk_chapter(client, pid, "2화", "아무 관련 없는 이야기.", 2.0)

        res = client.get(f"/api/v1/lore/{entry['id']}/referencing-chapters")
        assert res.status_code == 200
        rows = res.json()
        assert [r["title"] for r in rows] == ["1화"]

    def test_keyword_match_and_casefold(self, client):
        pid = _create_project(client)
        entry = _create_entry(client, pid, "철혈단", keywords=["Iron Blood"])
        _mk_chapter(client, pid, "1화", "the iron blood legion marched", 1.0)
        _mk_chapter(client, pid, "2화", "철혈단이 등장했다", 2.0)

        rows = client.get(f"/api/v1/lore/{entry['id']}/referencing-chapters").json()
        assert [r["title"] for r in rows] == ["1화", "2화"]

    def test_empty_and_no_match(self, client):
        pid = _create_project(client)
        entry = _create_entry(client, pid, "미언급 용어", keywords=["미언급"])
        _mk_chapter(client, pid, "1화", "관련 없는 본문", 1.0)
        res = client.get(f"/api/v1/lore/{entry['id']}/referencing-chapters")
        assert res.status_code == 200
        assert res.json() == []

    def test_scoped_to_entry_project_and_sort_order(self, client):
        pid = _create_project(client)
        other = _create_project(client)
        entry = _create_entry(client, pid, "공통어", keywords=["공통어"])
        _mk_chapter(client, pid, "뒤번호", "공통어 언급", 2.0)
        _mk_chapter(client, pid, "앞번호", "공통어 언급", 1.0)
        _mk_chapter(client, other, "타작품", "공통어 언급", 1.0)

        rows = client.get(f"/api/v1/lore/{entry['id']}/referencing-chapters").json()
        assert [r["title"] for r in rows] == ["앞번호", "뒤번호"]

    def test_missing_entry_404(self, client):
        assert client.get("/api/v1/lore/999999/referencing-chapters").status_code == 404
