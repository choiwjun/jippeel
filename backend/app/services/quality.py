"""회차 품질 진단 — 고도화 G-030 (로컬 규칙 기반, LLM 불필요).

웹소설(노벨피아·문피아 상위권) 관례를 지표화한다:
  - 대사 비율(목표 35~50%)
  - 초단문 리듬(평균 문단 길이)
  - 어미 반복(~했다·이었다·하게 된다 등)
  - 전환 접속사 남발(그러나·한편·그리고)
  - 문단 첫머리 다양성
  - 후크 진단(마지막 300자: 다음 화 클릭 유도 시그널)
  - 노벨피아 공백제외 글자 수

외부 의존 0(순수 규칙)이므로 결정적·테스트 가능하다.
metrics_v2(im-not-ai) 정량 엔진 재사용은 후속 경로.
"""
import re

from app.services.wordcount import count_novelpia_chars

_DIALOGUE_RE = re.compile(r'[“"『「]([^”"』」]{1,200}?)[”"』」]')
CONNECTORS = ("그러나", "하지만", "한편", "그리고", "그래서", "그런데")
WEAK_ENDINGS = ("~하게 된다", "~것이었다", "~일 뿐이다", "~기도 했다")
PLAIN_PAST = ("했다", "이었다", "였다")
HOOK_SIGNALS = ("?", "!", "…", "…", "순간", "눈을 떠", "소리가", "돌아서", "참견",
                "알아차리", "들려왔다", "나타났", "움켜쥐", "훅", "덮치", "말이었다",
                "그런데 그", "반짝", "번개", "빙글")


def analyze_text(text: str) -> dict:
    """텍스트 → 지표 딕셔너리(결정적). 빈 텍스트도 안전하게 처리한다."""
    text = (text or "").strip()
    metrics: dict = {}
    if not text:
        return {"chars_novelpia": 0, "dialogue_ratio": 0.0, "avg_para_chars": 0.0,
                "ending_repeat_per_1k": 0.0, "connector_per_1k": 0.0,
                "para_opener_variety": 0.0, "hook_present": False,
                "para_count": 0}

    per_1k = max(len(text) / 1000, 0.001)

    # 1) 대사 비율
    dialogue_chars = sum(len(m) for m in _DIALOGUE_RE.findall(text))
    metrics["dialogue_ratio"] = round(dialogue_chars / len(text), 4)
    metrics["chars_novelpia"] = count_novelpia_chars(text)

    # 2) 초단문 리듬 — 문단 평균 길이
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    metrics["para_count"] = len(paras)
    metrics["avg_para_chars"] = round(len(text) / max(len(paras), 1), 1)

    # 3) 어미 반복 (1,000자당)
    ending_count = sum(text.count(w) for w in PLAIN_PAST)
    ending_count += sum(text.count(w) for w in WEAK_ENDINGS)
    metrics["ending_repeat_per_1k"] = round(ending_count / per_1k, 2)

    # 4) 전환 접속사 (1,000자당)
    connector_count = sum(text.count(w) for w in CONNECTORS)
    metrics["connector_per_1k"] = round(connector_count / per_1k, 2)

    # 5) 문단 첫머리 다양성 (앞 2글자 기준 고유 비율)
    openers = [p[:2] for p in paras]
    metrics["para_opener_variety"] = round(
        len(set(openers)) / max(len(openers), 1), 3)

    # 6) 후크 진단 — 마지막 300자
    tail = text[-300:]
    metrics["hook_present"] = any(sig in tail for sig in HOOK_SIGNALS)

    return metrics


def score_and_suggest(metrics: dict) -> tuple[int, list[str], list[str]]:
    """지표 → (0~100 점수, 개선 제안, 제안 프리셋 이름)."""
    suggestions: list[str] = []
    presets: list[str] = []
    penalty = 0

    dialogue = metrics.get("dialogue_ratio", 0.0)
    if dialogue < 0.20:
        penalty += 15
        suggestions.append(
            f"대사 비율이 {dialogue * 100:.0f}%로 낮습니다. 35~50%가 연재 관례입니다 — "
            "설명을 대사·행동으로 바꿔보세요.")
        presets.append("장면 확장")
    elif dialogue > 0.70:
        penalty += 10
        suggestions.append("대사 비율이 지나치게 높습니다. 묘사·심리가 거의 없습니다.")

    avg_para = metrics.get("avg_para_chars", 0.0)
    if metrics.get("para_count", 0) >= 5 and avg_para > 180:
        penalty += 15
        suggestions.append(
            f"평균 문단이 {avg_para:.0f}자로 깁니다. 초단문(1~2문장) 리듬으로 쪼개세요.")

    ending = metrics.get("ending_repeat_per_1k", 0.0)
    if ending > 12:
        penalty += 15
        suggestions.append(
            f"어미 반복이 1,000자당 {ending:.0f}회입니다. '~했다·~이었다'를 줄이고 "
            "문장 끝을 다양화하세요.")
        presets.append("AI 티 제거 스타일")

    connector = metrics.get("connector_per_1k", 0.0)
    if connector > 5:
        penalty += 10
        suggestions.append(
            f"전환 접속사(그러나·한편 등)가 1,000자당 {connector:.0f}회 남발됩니다 — "
            "장면 전환을 사건으로 하세요.")

    variety = metrics.get("para_opener_variety", 1.0)
    if metrics.get("para_count", 0) >= 5 and variety < 0.5:
        penalty += 10
        suggestions.append("문단 첫머리가 단조롭습니다. 시작 패턴을 다양화하세요.")

    if not metrics.get("hook_present", False):
        penalty += 20
        suggestions.append(
            "마지막 300자에 후크(질문·위기·반전 시그널)가 없습니다 — 다음 화를 "
            "클릭하게 만드는 문장으로 끝내세요.")
        presets.append("장 끝 후크")

    if metrics.get("chars_novelpia", 0) < 3000:
        suggestions.append(
            f"공백제외 글자 수 {metrics.get('chars_novelpia', 0):,}자 — 노벨피아 PLUS "
            "3,000자 기준 미달입니다.")
        presets.append("이어쓰기")

    score = max(0, min(100, 100 - penalty))
    return score, suggestions, presets


def analyze_chapter(text: str) -> dict:
    """라우터용 편의 함수 — analyze_text + score_and_suggest 통합."""
    metrics = analyze_text(text)
    score, suggestions, presets = score_and_suggest(metrics)
    return {"score": score, "metrics": metrics,
            "suggestions": suggestions, "suggested_preset_names": presets}
