"""고도화 G-030~G-031 — 회차 품질 진단(규칙 기반) 테스트."""
from app.services.quality import analyze_chapter, analyze_text, score_and_suggest


BAD_TEXT = (
    "그러나 그는 조용히 걸었다. 하지만 마음은 복잡했다. 한편 성의 종이 울렸다.\n"
    "그는 오랫동안 생각했다. 이것은 그가 어릴 적부터 해온 상상이었다. 그것은 운명이었다.\n"
    "그러나 다시 한번 문을 두드렸다. 하지만 아무도 없었다. 그리고 그는 돌아섰다.\n"
    "그는 오랫동안 생각했다. 이것은 그가 어릴 적부터 해온 상상이었다. 그것은 운명이었다.\n"
    "그러나 다시 한번 문을 두드렸다. 하지만 아무도 없었다. 그리고 그는 돌아섰다.\n"
    "그렇게 모든 것이 끝났다. 조용히 문이 닫혔고, 그는 멀어졌다. 아무 일도 일어나지 않았다.\n"
    "그날 이후 아무도 그를 찾지 않았다. 마을은 평온했다. 모두가 잊었다. 끝났다."
)


def test_analyze_text_metrics_present():
    m = analyze_text("첫 문단이다.\n\n「비켜라.」 그가 말했다.\n\n칼이 번개처럼 빠졌다. 순간, 그의 손목이 꺾였다.")
    assert m["para_count"] == 3
    assert 0.0 < m["dialogue_ratio"] < 1.0
    assert m["chars_novelpia"] > 0
    assert isinstance(m["hook_present"], bool)


def test_bad_text_gets_low_score_and_suggestions():
    result = analyze_chapter(BAD_TEXT)
    assert result["score"] < 60
    # 나쁜 샘플의 원인별 제안이 나온다
    joined = " ".join(result["suggestions"])
    assert "어미 반복" in joined or "접속사" in joined
    assert "후크" in joined  # 마지막 문장에 후크 시그널 없음
    assert "장 끝 후크" in result["suggested_preset_names"]


def test_good_text_gets_high_score():
    text = (
        "「네가 누구야.」\n\n검이 그의 목 앞에서 멈췄다. 그는 웃었다.\n\n"
        "「기억 안 나? 네가 죽인 그 집 아들인데.」\n\n"
        "손끝이 떨렸다. 기억이 번개처럼 돌아왔다. 그날 밤, 불타는 저택.\n\n"
        "「이제 알겠네.」 그가 검을 뽑았다.\n\n"
        "칼끝이 흔들렸다. 그리고 — 대문이 박살 나는 소리가 들려왔다."
    )
    result = analyze_chapter(text)
    assert result["score"] >= 70
    assert result["metrics"]["hook_present"] is True
    assert "장 끝 후크" not in result["suggested_preset_names"]


def test_empty_text_safe():
    result = analyze_chapter("")
    assert result["score"] >= 0
    assert result["metrics"]["para_count"] == 0


def test_score_capped():
    m = {"dialogue_ratio": 0.0, "avg_para_chars": 999, "ending_repeat_per_1k": 99,
         "connector_per_1k": 99, "para_opener_variety": 0.0, "para_count": 10,
         "hook_present": False, "chars_novelpia": 0}
    score, suggestions, presets = score_and_suggest(m)
    assert score <= 20  # 전 항목 위반 → 최하위권
    assert len(suggestions) >= 4


def test_series_finale_does_not_penalize_missing_hook():
    text = "모든 싸움이 끝났다. 그는 검을 내려놓았다.\n\n문은 닫혔고, 남은 사람들은 서로를 바라보았다."
    serial = analyze_chapter(text, episode_purpose="serial")
    finale = analyze_chapter(text, episode_purpose="series_finale")
    assert serial["metrics"]["hook_score_applicable"] is True
    assert finale["metrics"]["hook_score_applicable"] is False
    assert finale["score"] >= serial["score"]
    assert "장 끝 후크" in serial["suggested_preset_names"]
    assert "장 끝 후크" not in finale["suggested_preset_names"]
    assert not any("다음 화" in s and "클릭" in s for s in finale["suggestions"])


def test_quality_history_dedup_includes_purpose_not_hash(client):
    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "완결", "sort_order": 99}).json()
    client.put(f"/api/v1/chapters/{ch['id']}/content", json={"content_md": "끝났다. 그는 웃었다.", "expected_revision": 0})
    assert client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=serial").status_code == 200
    assert client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=serial").status_code == 200
    assert client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=series_finale").status_code == 200
    assert client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=serial").status_code == 200
    rows = client.get(f"/api/v1/chapters/{ch['id']}/quality/history").json()
    purposes = [row["metrics_json"]["episode_purpose"] for row in rows]
    assert sorted(purposes) == ["serial", "series_finale"]


def test_quality_history_legacy_rows_without_purpose_are_serial_compatible(client):
    import hashlib

    from app.database import get_db
    from app.models import QualityCheck

    pid = client.post("/api/v1/projects", json={"title": "P"}).json()["id"]
    ch = client.post(f"/api/v1/projects/{pid}/chapters", json={"title": "1화"}).json()
    text = "끝났다. 그는 웃었다."
    client.put(
        f"/api/v1/chapters/{ch['id']}/content",
        json={"content_md": text, "expected_revision": 0},
    )
    db = next(iter(client.app.dependency_overrides[get_db]()))
    db.add(QualityCheck(
        chapter_id=ch["id"],
        score=80,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        metrics_json={"hook_present": False},
        suggestions_json=[],
        presets_json=[],
    ))
    db.commit()

    resp = client.get(f"/api/v1/chapters/{ch['id']}/quality?episode_purpose=serial")
    assert resp.status_code == 200
    assert resp.json()["recorded"] is False
    rows = client.get(f"/api/v1/chapters/{ch['id']}/quality/history").json()
    assert len(rows) == 1
