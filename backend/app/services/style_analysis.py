"""레퍼런스 텍스트 스타일 분석 — 작가 지목 텍스트 → 문체 프로파일 초안.

외부 인기작 크롤링은 하지 않는다(저작권·플랫폼 약관). 작가가 직접
붙여넣은 텍스트만 분석 대상이다. 지표 측정은 순수 Python으로 결정적이고,
지표 + 원문 샘플을 LLM이 해석해 style_profile 초안 문장으로 합성한다.
초안은 작가 검토 후에만 project.style_profile에 적용된다 — 자동 적용 없음.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

# 문장 종결 — 따옴표·괄호까지 포함해 문장 경계로 본다(치환 후 \n 분리).
_SENT_END = re.compile(r"([.!?…][\"'”’)\]]?)\s+")
# 대화문 시작 패턴 — 쌍따옴표·홑따옴표·줄표로 시작하는 단락.
_DIALOGUE_LINE = re.compile(r"^\s*[\"'“‘—\-–]")
# 종결어미: 문장 끝 단어의 마지막 어미를 대표 패턴으로 분류한다.
_TERMINAL_ENDINGS = re.compile(
    r"(다|습니다|였다|었다|았다|겠다|는다|ㄴ다|니|까|냐|라|지|군|네|요|데|죠|거든|련다)"
    r"[.!?…\"'”’)\]]*\s*$")
_CONNECTIVE_ENDINGS = re.compile(
    r'(고|며|는데|지만|서|니|니까|러|도록|면서|더니|거든|는 바|자)[,—~]*\s*$')
# 시점 힌트 — 1인칭/3인칭 대명사 밀도.
_FIRST_PERSON = re.compile(r'나는|내가|나를|나의|나에게|내게|우리는|우리가')
_THIRD_PERSON = re.compile(r'그는|그녀는|그가|그녀가|그를|그녀를|그의|그녀의|그에게|그녀에게')

STYLE_ANALYSIS_SYSTEM = (
    "너는 한국 웹소설 문체 분석가다. 아래 원문 샘플과 측정 지표를 바탕으로, "
    "이 문체를 재현하기 위한 '문체 프로파일' 초안을 한국어로 작성한다.\n"
    "[출력 형식]\n"
    "- 5~9개의 짧은 지시문 목록 ('- '으로 시작). 각 항목은 생성 모델이 따를 수 있는 "
    "구체적 지시여야 한다 (예: '문장 평균 25자 내외, 단문과 장문을 번갈아 배치').\n"
    "- 지표에 있는 수치를 그대로 활용하고, 지표로 측정 불가한 것(장르적 분위기·훅 패턴·"
    "인물 서사 구조)은 원문에서 관찰된 것만 쓴다. 추측성 일반론 금지.\n"
    "- 머리말·설명·메타 코멘트 없이 목록만 출력한다."
)

_MAX_SAMPLE_CHARS = 6000


@dataclass
class StyleMetrics:
    chars: int = 0
    paragraphs: int = 0
    sentences: int = 0
    dialogue_paragraphs: int = 0
    sent_len_avg: float = 0.0
    sent_len_median: float = 0.0
    sent_len_p90: float = 0.0
    short_sentences: int = 0   # 10자 미만
    long_sentences: int = 0    # 60자 초과
    terminal_endings: int = 0
    connective_endings: int = 0
    first_person_hits: int = 0
    third_person_hits: int = 0
    top_endings: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        sents = max(self.sentences, 1)
        paras = max(self.paragraphs, 1)
        return {
            "chars": self.chars,
            "paragraphs": self.paragraphs,
            "sentences": self.sentences,
            "dialogue_ratio": round(self.dialogue_paragraphs / paras, 3),
            "sent_len_avg": round(self.sent_len_avg, 1),
            "sent_len_median": round(self.sent_len_median, 1),
            "sent_len_p90": round(self.sent_len_p90, 1),
            "short_sentence_ratio": round(self.short_sentences / sents, 3),
            "long_sentence_ratio": round(self.long_sentences / sents, 3),
            "connective_ending_ratio": round(
                self.connective_endings / max(self.terminal_endings + self.connective_endings, 1), 3),
            "pov_guess": self._pov_guess(),
            "top_endings": self.top_endings[:8],
            "sentences_per_paragraph": round(self.sentences / paras, 2),
        }

    def _pov_guess(self) -> str:
        if self.first_person_hits > self.third_person_hits * 2:
            return "1인칭"
        if self.third_person_hits > self.first_person_hits:
            return "3인칭"
        return "불명"


def _split_sentences(paragraph: str) -> list[str]:
    marked = _SENT_END.sub(r"\1\n", paragraph.strip())
    return [s for s in marked.split("\n") if s.strip()]


def _ending_morph(sentence: str) -> str:
    """문장 끝 어미 추출 — 마지막 한글 구간 앞 조사까지 2자."""
    tail = re.search(r"([가-힣]{1,4})[.!?…\"'”’)\]]*\s*$", sentence)
    return tail.group(1) if tail else ""


def analyze_text(text: str) -> StyleMetrics:
    """원문 텍스트의 결정적 스타일 지표를 측정한다."""
    m = StyleMetrics(chars=len(text))
    paras = [p.strip() for p in re.split(r'\n+', text) if p.strip()]
    m.paragraphs = len(paras)
    m.dialogue_paragraphs = sum(1 for p in paras if _DIALOGUE_LINE.match(p))
    lengths: list[int] = []
    endings: dict[str, int] = {}
    for p in paras:
        for s in _split_sentences(p):
            m.sentences += 1
            slen = len(s.strip())
            lengths.append(slen)
            if slen < 10:
                m.short_sentences += 1
            elif slen > 60:
                m.long_sentences += 1
            if _CONNECTIVE_ENDINGS.search(s):
                m.connective_endings += 1
            elif _TERMINAL_ENDINGS.search(s):
                m.terminal_endings += 1
            morph = _ending_morph(s)
            if morph:
                endings[morph] = endings.get(morph, 0) + 1
        m.first_person_hits += len(_FIRST_PERSON.findall(p))
        m.third_person_hits += len(_THIRD_PERSON.findall(p))
    if lengths:
        m.sent_len_avg = statistics.fmean(lengths)
        m.sent_len_median = statistics.median(lengths)
        idx = min(int(len(lengths) * 0.9), len(lengths) - 1)
        m.sent_len_p90 = sorted(lengths)[idx]
    m.top_endings = sorted(endings.items(), key=lambda kv: -kv[1])
    return m


def build_analysis_messages(text: str, metrics: StyleMetrics) -> list[dict]:
    """지표 + 원문 샘플로 LLM 합성 메시지를 만든다."""
    import json
    sample = text[:_MAX_SAMPLE_CHARS]
    if len(text) > _MAX_SAMPLE_CHARS:
        sample += "\n[… 이하 생략 — 샘플은 앞부분만 사용]"
    return [
        {"role": "system", "content": STYLE_ANALYSIS_SYSTEM},
        {"role": "user", "content": (
            f"[측정 지표]\n{json.dumps(metrics.to_dict(), ensure_ascii=False, indent=1)}\n\n"
            f"[원문 샘플]\n{sample}")},
    ]
