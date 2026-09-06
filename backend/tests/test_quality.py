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
