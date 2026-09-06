"""시맨틱 로어 매칭 v2 — 부록06 §4 설계의 근사 구현 (G-070).

설계 원칙(부록06 §4)을 따른다:
  - 하이브리드: FTS5/키워드 점수(v1, 고유명사에 강점) + 시맨틱 점수 가중 합산
  - 폴백: "선택 적용" 패턴 — 임베딩 모델이 없어도 동작해야 한다

현재 구현은 **문자 2-gram 코사인 유사도**(표준 라이브러리 전용, 결정적)로
형태소 변형·부분 지칭("그 펜던트" ↔ "펜던트")을 키워드 부분 일치보다 넓게 잡는다.
sqlite-vec + 한국어 ONNX 임베딩(bge-m3 등)으로 교체할 때는
`semantic_score(query, doc) -> float` 인터페이스만 유지하면 된다.
"""
from collections import Counter
import re

_STRIP_RE = re.compile(r"[\s\W_]+", re.UNICODE)  # 공백·기호 제거


def char_bigrams(text: str) -> Counter:
    """문자 2-gram 카운터 — 한국어 형태소 변형에 강건한 근사 벡터."""
    text = _STRIP_RE.sub("", (text or "").casefold())
    if len(text) < 2:
        return Counter({text}) if text else Counter()
    return Counter(text[i:i + 2] for i in range(len(text) - 1))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def semantic_score(query: str, doc: str) -> float:
    """query(본문) ↔ doc(로어 항목) 근사 유사도 0~1."""
    return cosine(char_bigrams(query), char_bigrams(doc))


def hybrid_score(keyword_score: int, query: str, doc: str,
                 keyword_norm: float, semantic_weight: float = 0.5) -> float:
    """v1 키워드 점수(정규화) + 시맨틱 점수 가중 합산.

    keyword_score: v1 점수(제목 3×출현 + 키워드 2×출현)
    keyword_norm: 이 배치에서 정규화 기준(최대 점수) — 0이면 시맨틱만 사용
    """
    kw = (keyword_score / keyword_norm) if keyword_norm > 0 else 0.0
    return kw + semantic_weight * semantic_score(query, doc)
