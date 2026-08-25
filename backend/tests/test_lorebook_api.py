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
