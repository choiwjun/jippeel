"""D03-5 복선 이관 구분 — foreshadows.disposition 계약 테스트.

- disposition: resolved | intentional_unresolved | side_story | NULL(미분류).
- 불변조건: status='설치'이면 disposition IS NULL — 어긋나는 쓰기는 422.
- 자동 판정 없음 — 작가 명시 지정만.
"""


def _mk_project(client) -> int:
    return client.post("/api/v1/projects", json={"title": "이관 작품"}).json()["id"]


def _mk_foreshadow(client, pid: int, status: str = "설치", **extra) -> dict:
    r = client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "검의 주인", "status": status, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------- 생성 ----------

def test_create_persists_audience_knows(client):
    """G-045: POST가 audience_knows를 받았으면 저장해야 한다(과거 묵시적 폐기 결함)."""
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid, audience_knows=True)
    assert row["audience_knows"] is True
    row = _mk_foreshadow(client, pid)
    assert row["audience_knows"] is False


def test_create_disposition_on_closed_status(client):
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid, status="회수", disposition="resolved")
    assert row["disposition"] == "resolved"
    row = _mk_foreshadow(client, pid, status="보류", disposition="side_story")
    assert row["disposition"] == "side_story"


def test_create_defaults_to_null_and_rejects_open(client):
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid)
    assert row["disposition"] is None

    # 설치 상태에 disposition은 모순 → 422
    r = client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "x", "status": "설치", "disposition": "resolved"},
    )
    assert r.status_code == 422
    # status 생략(기본 설치)도 동일
    r = client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "x", "disposition": "intentional_unresolved"},
    )
    assert r.status_code == 422
    # 사전 외 값
    r = client.post(
        f"/api/v1/projects/{pid}/foreshadows",
        json={"title": "x", "status": "회수", "disposition": "bogus"},
    )
    assert r.status_code == 422


# ---------- 갱신 ----------

def test_patch_disposition_set_clear_and_reopen(client):
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid, status="보류")
    fid = row["id"]

    # 설정
    r = client.patch(f"/api/v1/foreshadows/{fid}", json={"disposition": "side_story"})
    assert r.status_code == 200
    assert r.json()["disposition"] == "side_story"

    # 명시적 해제
    r = client.patch(f"/api/v1/foreshadows/{fid}", json={"disposition": None})
    assert r.status_code == 200
    assert r.json()["disposition"] is None


def test_patch_disposition_rejects_open_result(client):
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid)
    fid = row["id"]

    # 설치 행에 disposition 지정 → 422, 기존 필드 불변
    r = client.patch(f"/api/v1/foreshadows/{fid}", json={"disposition": "resolved"})
    assert r.status_code == 422
    again = client.get(f"/api/v1/projects/{pid}/foreshadows").json()[0]
    assert again["status"] == "설치"
    assert again["disposition"] is None


def test_patch_reopen_requires_clearing_disposition(client):
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid, status="회수", disposition="resolved")
    fid = row["id"]

    # status만 설치로 되돌리면 결과가 불변조건 위반 → 422, 아무것도 안 바뀜
    r = client.patch(f"/api/v1/foreshadows/{fid}", json={"status": "설치"})
    assert r.status_code == 422
    again = client.get(f"/api/v1/projects/{pid}/foreshadows").json()[0]
    assert again["status"] == "회수"
    assert again["disposition"] == "resolved"

    # 같은 요청에 disposition 해제를 명시하면 허용
    r = client.patch(
        f"/api/v1/foreshadows/{fid}", json={"status": "설치", "disposition": None}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "설치"
    assert r.json()["disposition"] is None


def test_patch_rejects_unknown_disposition(client):
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid, status="보류")
    r = client.patch(
        f"/api/v1/foreshadows/{row['id']}", json={"disposition": "bogus"}
    )
    assert r.status_code == 422


def test_patch_rejects_open_status_and_disposition_in_one_request(client):
    """같은 PATCH에 설치 + disposition을 넣어도 결과 불변조건 위반으로 422."""
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid, status="회수", disposition="resolved")
    r = client.patch(
        f"/api/v1/foreshadows/{row['id']}",
        json={"status": "설치", "disposition": "resolved"},
    )
    assert r.status_code == 422
    again = client.get(f"/api/v1/projects/{pid}/foreshadows").json()[0]
    assert again["status"] == "회수"
    assert again["disposition"] == "resolved"


def test_patch_missing_foreshadow_404(client):
    pid = _mk_project(client)
    _mk_foreshadow(client, pid)
    assert (
        client.patch("/api/v1/foreshadows/999999", json={"disposition": "resolved"})
        .status_code
        == 404
    )


def test_create_closed_status_without_disposition_defaults_null(client):
    pid = _mk_project(client)
    row = _mk_foreshadow(client, pid, status="회수")
    assert row["disposition"] is None


# ---------- 목록 필터 ----------

def test_list_filters_by_disposition(client):
    pid = _mk_project(client)
    _mk_foreshadow(client, pid)  # 설치, NULL
    _mk_foreshadow(client, pid, status="회수", disposition="resolved")
    _mk_foreshadow(client, pid, status="보류", disposition="side_story")

    r = client.get(f"/api/v1/projects/{pid}/foreshadows")
    assert len(r.json()) == 3

    r = client.get(f"/api/v1/projects/{pid}/foreshadows?disposition=resolved")
    assert [f["disposition"] for f in r.json()] == ["resolved"]
    r = client.get(f"/api/v1/projects/{pid}/foreshadows?disposition=side_story")
    assert [f["disposition"] for f in r.json()] == ["side_story"]
    r = client.get(f"/api/v1/projects/{pid}/foreshadows?disposition=intentional_unresolved")
    assert r.json() == []

    # status 필터와 AND 조합
    r = client.get(
        f"/api/v1/projects/{pid}/foreshadows?status_filter=보류&disposition=side_story"
    )
    assert len(r.json()) == 1
    r = client.get(
        f"/api/v1/projects/{pid}/foreshadows?status_filter=보류&disposition=resolved"
    )
    assert r.json() == []

    assert (
        client.get(f"/api/v1/projects/{pid}/foreshadows?disposition=bogus").status_code
        == 422
    )
    # 빈 문자열도 사전 외 값으로 422
    assert (
        client.get(f"/api/v1/projects/{pid}/foreshadows?disposition=").status_code
        == 422
    )
