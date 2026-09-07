"""작품 부트스트랩 서비스 — 입력 하나로 작품 전체 구조를 AI 생성해 일괄 저장.

흐름 (POST /api/v1/projects/bootstrap):
  1. LLM 4회 호출 (app.services.llm 재용)
     ① 제목 후보 5개 + 로그라인 + 주제의식
     ② 권·회차 목차 (각 회차 제목 + 2문단 시놉시스 + 핵심 사건)
     ③ 캐릭터 4~6명 + 관계 쌍 + 로어북 8~12개(keywords[] 포함)
  2. JSON 파싱 실패 시 repair prompt로 1회 재시도, 그래도 실패하면
     규칙 기반 폴백(템플릿 생성) — 라우터가 502로 응답
  3. Project + Chapter + Character + Relationship + LoreEntry를
     단일 트랜잭션으로 bulk insert
"""
import json
import logging
from dataclasses import dataclass, field

import openai
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (AiEndpoint, Chapter, Character, Foreshadow, LoreEntry,
                        Project, Relationship, VolumeNote)
from app.services import llm, usage as usage_service

logger = logging.getLogger(__name__)

DEFAULT_TITLE_STYLE = "웹소설식 긴 제목"

# 후속 부트스트랩 콜에 전달하는 목차 앵커의 입력 상한.
# 대형 요청(최대 50권 × 200화)에서도 프롬프트가 무제한으로 커지지 않게 한다.
OUTLINE_ANCHOR_MAX_CHARS = 12_000
_OUTLINE_ANCHOR_TITLE_MAX_CHARS = 200
_OUTLINE_ANCHOR_FIELD_MAX_CHARS = 600

# LLM 호출 온도 — 엔드포인트 설정 값을 그대로 사용한다.
# None이면 temperature 파라미터를 전송하지 않는다(Codex 계열 모델은 거부함).

LORE_CATEGORIES = ("용어", "장소", "세력", "기타")


class BootstrapAIError(Exception):
    """LLM 응답을 유효한 JSON으로 못 받음(재시도 포함) → 폴백 대상."""


class NoEndpointError(Exception):
    """use_ai=True인데 사용 가능한 AI 엔드포인트/모델이 없음 → 400."""


# --------------------------------------------------------------------------
# JSON 파싱
# --------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """코드펜스·앞뒤 설명이 섞여도 첫 '{'~마지막 '}' 구간을 파싱한다."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON 객체를 찾지 못했습니다")
    return json.loads(text[start:end + 1])


async def _call_json(client, model: str, messages: list[dict],
                     temperature: float | None,
                     reasoning_effort: str | None = None) -> dict:
    """1회 호출 + 파싱. 실패 시 repair prompt로 1회 재시도."""
    raw = ""
    try:
        raw = await llm.complete_chat(client, model, messages, temperature=temperature,
                                      reasoning_effort=reasoning_effort)
        return _extract_json(raw)
    except (openai.APIError, ValueError, json.JSONDecodeError) as first_err:
        logger.warning("bootstrap JSON 1차 시도 실패: %s", first_err)
        repaired_messages = list(messages) + [
            {"role": "assistant", "content": raw if isinstance(raw, str) else "(응답 없음)"},
            {"role": "user",
             "content": "직전 응답은 유효한 JSON이 아니었다. 다른 설명·코드펜스 없이 "
                        "요청된 형식 그대로의 유효한 JSON만 다시 출력하라."},
        ]
        try:
            raw = await llm.complete_chat(
                client, model, repaired_messages, temperature=temperature,
                reasoning_effort=reasoning_effort)
            return _extract_json(raw)
        except (openai.APIError, ValueError, json.JSONDecodeError) as second_err:
            raise BootstrapAIError(f"JSON 재시도 실패: {second_err}") from second_err
    finally:
        usage_service.record(
            kind="bootstrap", model=model, endpoint_name=None,
            prompt_chars=sum(len(str(m.get("content") or "")) for m in messages),
            completion_chars=len(raw) if isinstance(raw, str) else 0)


# --------------------------------------------------------------------------
# 프롬프트 · 3단계 생성
# --------------------------------------------------------------------------

_SYSTEM_JSON = (
    "너는 한국 웹소설 연재 기획 전문가다. 반드시 단일 유효한 JSON 객체만 출력한다. "
    "코드펜스·주석·JSON 외 설명 문자열은 절대 출력하지 않는다."
)


def _idea_messages(genre: str, premise: str | None, title_style: str) -> list[dict]:
    p = premise.strip() if premise and premise.strip() \
        else "(없음 — 네가 직접 발상하여 제시하라)"
    user = f"""장르: {genre}
프리미스: {p}
제목 스타일: {title_style}

다음 JSON 형식으로 출력하라:
{{"titles": ["차별화된 제목 후보 정확히 5개"], "logline": "한 줄 로그라인", "theme": "주제의식",
 "protagonist_name": "주인공 이름(한국식 2~3자, 웹소설파닫기 쉬운 이름)"}}"""
    return [{"role": "system", "content": _SYSTEM_JSON},
            {"role": "user", "content": user}]


def _outline_messages(genre: str, idea: dict, volume_count: int,
                      chapters_per_volume: int) -> list[dict]:
    titles = [_as_str(t) for t in _as_list(idea.get("titles"))]
    title = titles[0] if titles else genre
    protagonist = _as_str(idea.get("protagonist_name"))
    protagonist_line = ""
    if protagonist:
        protagonist_line = f"""주인공 이름: {protagonist}
- 목차의 모든 시놉시스에서 주인공은 반드시 "{protagonist}"로 지칭한다(다른 이름 금지)

"""
    user = f"""작품: {title}
장르: {genre}
로그라인: {_as_str(idea.get('logline'))}
주제의식: {_as_str(idea.get('theme'))}
{protagonist_line}
권 {volume_count}권, 각 권당 회차 {chapters_per_volume}화 목차를 짜라.
각 회차는 제목 + 2문단 시놉시스 + 핵심 사건 1개를 포함한다.
각 권에는 서사 레이어(개요·감정 곡선·고봉)도 함께 설계한다:
- overview: 권 전체 흐름 2~3문장(주인공이 어디서 시작해 어디로 가는가)
- emotion_curve: 고조↔완충 배치(예: "3화 고조, 4화 완충, 7화 반전 고조")
- climax_note: 권의 클라이맥스(언제·누구와·무엇이 걸리는가 1~2문장)
다음 JSON 형식으로 출력하라:
{{"volumes": [{{"volume": 1, "title": "권 제목",
  "overview": "권 개요 2~3문장", "emotion_curve": "감정 곡선 배치",
  "climax_note": "권 고봉 설계", "chapters": [
  {{"order": 1, "title": "회차 제목", "synopsis": "2문단 시놉시스", "key_event": "핵심 사건"}}]}}]}}"""
    return [{"role": "system", "content": _SYSTEM_JSON},
            {"role": "user", "content": user}]


def _characters_messages(genre: str, idea: dict, outline_summary: str) -> list[dict]:
    """콜 3 — 등장인물 심층 설계. 서사 기능(목표·결핍·비밀·변화)을 강제한다."""
    titles = [_as_str(t) for t in _as_list(idea.get("titles"))]
    title = titles[0] if titles else genre
    protagonist = _as_str(idea.get("protagonist_name"))
    protagonist_rule = ""
    if protagonist:
        protagonist_rule = f'- 주연 1명의 name은 반드시 "{protagonist}"를 그대로 사용한다(변형·변경 금지)\n'
    user = f"""작품: {title}
장르: {genre}
로그라인: {_as_str(idea.get('logline'))}
주제의식: {_as_str(idea.get('theme'))}
1권 목차:
{outline_summary}

위 목차를 관통하는 등장인물 6~8명을 심층 설계하라.
- 구성: 주인공 1명, 핵심 조연 2~3명, 대립자 1~2명, 주변인 1~2명
{protagonist_rule}- 주인공은 표면 목표와 내면 결핍이 충돌하고, 1권 내내 숨길 비밀이 하나 있어야 한다
- 대립자는 단순 악인이 아니라 '그 나름의 정의'로 움직이는 이유가 있어야 한다
- background는 배경 2문장 + 목표 + 숨긴 비밀까지 3문장 이상
- speech_style은 실제 대사로 바로 쓸 수 있을 만큼 구체적으로(어투·호칭 포함)
- personality는 성격과 함께 1권에서 변해갈 방향을 포함

다음 JSON 형식으로 출력하라:
{{"characters": [{{"name": "이름", "alias": "별칭", "role": "주연|조연|단역|기타",
  "appearance": "외형 1문장", "personality": "성격+1권 변화 방향 2문장",
  "speech_style": "구체적 말투", "background": "배경+목표+비밀 3문장 이상"}}]}}"""
    return [{"role": "system", "content": _SYSTEM_JSON},
            {"role": "user", "content": user}]


def _relations_lore_messages(genre: str, idea: dict, outline_summary: str,
                             character_names: list[str]) -> list[dict]:
    """콜 4 — 관계망(긴장·변화 포함)과 상호 연결된 세계관 설계."""
    titles = [_as_str(t) for t in _as_list(idea.get("titles"))]
    title = titles[0] if titles else genre
    names = ", ".join(character_names) or "(없음)"
    user = f"""작품: {title}
장르: {genre}
줄거리 요약:
{outline_summary}

등장인물: {names}

이 인물들을 기준으로 관계망과 세계관을 설계하라.

[관계] 정확히 8쌍 이상
- label은 2~6자(예: 주군-가신, 계약자-감시자)
- note는 "현재 관계 + 1권에서 어떻게 변하는지" 2문장
- 동맹만 쓰지 말 것 — 대립·오해·서로 모르는 숨은 과거를 포함
- 주인공 관계뿐 아니라 조연 사이의 관계도 최소 2쌍
- from·to는 위 등장인물 이름만 사용

[세계관 로어북] 12~18개
- category는 용어|장소|세력|기타
- content는 2~3문장: 설정이 무엇인지 + 누구에게 유리하고 누구를 억눌렀는지 + 1권 목차의 어느 사건과 맞물리는지
- keywords는 본문 자동 매칭용 — 인물 이름·호칭·약칭·장소 약칭을 반드시 포함
- 인물 이름과 직결되는 항목 3개 이상, 서로 대립하는 진영의 시점 항목 2개 이상

다음 JSON 형식으로 출력하라:
{{"relationships": [{{"from": "이름", "to": "이름", "label": "2~6자", "note": "2문장"}}],
 "lore_entries": [{{"category": "용어", "title": "항목 제목", "content": "2~3문장",
  "keywords": ["키워드1", "키워드2"]}}]}}"""
    return [{"role": "system", "content": _SYSTEM_JSON},
            {"role": "user", "content": user}]


# --------------------------------------------------------------------------
# 생성 결과 정규화
# --------------------------------------------------------------------------

@dataclass
class OutlineChapter:
    volume: int
    order: int
    sort_order: float
    title: str
    synopsis: str
    key_event: str


@dataclass
class OutlineCharacter:
    name: str
    alias: str | None = None
    role: str | None = None
    appearance: str | None = None
    personality: str | None = None
    speech_style: str | None = None
    background: str | None = None


@dataclass
class OutlineLore:
    category: str = "기타"
    title: str = ""
    content: str | None = None
    keywords: list[str] = field(default_factory=list)


def _as_str(value, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _coerce_outline(data: dict, volume_count: int, cpv: int) -> list[OutlineChapter]:
    chapters: list[OutlineChapter] = []
    for vol in _as_list(data.get("volumes"))[:volume_count]:
        if not isinstance(vol, dict):
            continue
        v_raw = vol.get("volume")
        v = v_raw if isinstance(v_raw, int) and v_raw >= 1 else len(chapters) // max(cpv, 1) + 1
        pos = 0
        for ch in _as_list(vol.get("chapters"))[:cpv]:
            if not isinstance(ch, dict):
                continue
            order_raw = ch.get("order")
            order = order_raw if isinstance(order_raw, int) and order_raw >= 1 else pos + 1
            chapters.append(OutlineChapter(
                volume=v,
                order=order,
                sort_order=float((v - 1) * cpv + pos),
                title=_as_str(ch.get("title"), f"{v}권 {order}화"),
                synopsis=_as_str(ch.get("synopsis")),
                key_event=_as_str(ch.get("key_event")),
            ))
            pos += 1
    # 권·회차 수 보정 — 부족분은 템플릿으로 채운다
    while len(chapters) < volume_count * cpv:
        n = len(chapters)
        v, i = divmod(n, cpv)
        chapters.append(OutlineChapter(
            volume=v + 1, order=i + 1, sort_order=float(n),
            title=f"{v + 1}권 {i + 1}화", synopsis="", key_event=""))
    return chapters[:volume_count * cpv]


def _summarize_outline(chapters: list[OutlineChapter], volumes_index: dict) -> str:
    parts = []
    for v in sorted({c.volume for c in chapters}):
        vol_title = _as_str(volumes_index.get(v))
        head = f"{v}권. {vol_title}" if vol_title else f"{v}권"
        body = " ".join(f"{c.order}화){c.title}" for c in chapters if c.volume == v)
        parts.append(f"{head}\n{body}")
    return "\n".join(parts)


def _clip_outline_anchor(value: str, limit: int) -> str:
    """목차 앵커 한 필드를 앞·뒤 맥락을 남기며 제한한다."""
    value = _as_str(value)
    if len(value) <= limit:
        return value
    marker = " … "
    head = max((limit - len(marker)) // 2, 1)
    return value[:head] + marker + value[-head:]


def _outline_anchor_summary(chapters: list[OutlineChapter],
                           volumes_index: dict) -> str:
    """콜 2 목차의 고유명사·사건을 bounded 정본 블록으로 만든다."""
    parts = [
        "[목차가 정본 — 후속 생성 콜 공통 기준]",
        "아래 목차에 등장하는 장소·세력·용어·사건명은 표기와 관계를 그대로 유지하라.",
        "목차와 충돌하는 새 고유명사나 다른 장소명을 만들지 마라.",
    ]
    for v in sorted({c.volume for c in chapters}):
        vol_title = _clip_outline_anchor(
            _as_str(volumes_index.get(v)), _OUTLINE_ANCHOR_TITLE_MAX_CHARS)
        head = f"{v}권. {vol_title}" if vol_title else f"{v}권"
        for c in chapters:
            if c.volume != v:
                continue
            entry = [f"- {c.order}화 제목: {_clip_outline_anchor(c.title, _OUTLINE_ANCHOR_TITLE_MAX_CHARS)}"]
            if c.synopsis:
                entry.append(
                    f"  시놉시스: {_clip_outline_anchor(c.synopsis, _OUTLINE_ANCHOR_FIELD_MAX_CHARS)}")
            if c.key_event:
                entry.append(
                    f"  핵심 사건: {_clip_outline_anchor(c.key_event, _OUTLINE_ANCHOR_FIELD_MAX_CHARS)}")
            candidate = "\n".join([*parts, head, *entry])
            if len(candidate) > OUTLINE_ANCHOR_MAX_CHARS:
                marker = "… 목차 앵커 생략 (입력 상한 도달)"
                base = "\n".join(parts)
                available = OUTLINE_ANCHOR_MAX_CHARS - len(marker) - 1
                return base[:max(available, 0)].rstrip() + "\n" + marker
            parts.extend([head, *entry])
    return "\n".join(parts)


def _coerce_characters(data: dict) -> list[OutlineCharacter]:
    chars: list[OutlineCharacter] = []
    seen: set[str] = set()
    for c in _as_list(data.get("characters"))[:8]:
        if not isinstance(c, dict):
            continue
        name = _as_str(c.get("name"))
        if not name or name in seen:
            continue
        seen.add(name)
        role = _as_str(c.get("role"))
        chars.append(OutlineCharacter(
            name=name,
            alias=_as_str(c.get("alias")) or None,
            role=role if role in ("주연", "조연", "단역", "기타") else "조연",
            appearance=_as_str(c.get("appearance")) or None,
            personality=_as_str(c.get("personality")) or None,
            speech_style=_as_str(c.get("speech_style")) or None,
            background=_as_str(c.get("background")) or None,
        ))
    # 최소 4명 보장 — 부족분은 폴백 템플릿 캐릭터로 채운다
    for template in _FALLBACK_CHAR_TEMPLATES:
        if len(chars) >= 4:
            break
        if template["name"] not in seen:
            chars.append(OutlineCharacter(**template))
    return chars


def _coerce_relationships(data: dict, names: set[str]) -> list[dict]:
    rels: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()
    for r in _as_list(data.get("relationships")):
        if not isinstance(r, dict):
            continue
        src, dst = _as_str(r.get("from")), _as_str(r.get("to"))
        if src in names and dst in names and src != dst and (src, dst) not in seen_pairs:
            seen_pairs.add((src, dst))
            rels.append({"from": src, "to": dst,
                         "label": _as_str(r.get("label")) or None,
                         "note": _as_str(r.get("note")) or None})
    return rels


_FALLBACK_LORE_TEMPLATES = [
    ("용어", "고대의 각성"), ("용어", "금단의 문양"), ("장소", "시작의 마을"),
    ("장소", "무한의 탑"), ("세력", "정파 연합"), ("세력", "적대 세력"),
    ("기타", "세계 규칙: 대가의 법칙"), ("기타", "미회수 복선: 예언의 조각"),
    ("용어", "금문(禁紋)의 계약"), ("장소", "경계의 협곡"),
    ("세력", "정보를 파는 그림자 조합"), ("기타", "실패한 전승자의 유품"),
]

_FALLBACK_CHAR_TEMPLATES = [
    {"name": "차가운 검객", "alias": "검귀", "role": "주연",
     "appearance": "날카로운 눈매에 검은 장창", "personality": "과묵하고 의리 있음",
     "speech_style": "짧고 단호한 단문", "background": "멸문한 가문의 마지막 생존자"},
    {"name": "밝은 동료", "alias": "해바라기", "role": "조연",
     "appearance": "웃는 얼굴에 낡은 도복", "personality": "낙천적이고 다혈질",
     "speech_style": "반말과 농담 섞임", "background": "시골에서 오른 무술 견습생"},
    {"name": "수수께끼의 현자", "alias": "탑주", "role": "조연",
     "appearance": "백발에 은색 지팡이", "personality": "신중하고 비밀이 많음",
     "speech_style": "격식체·경구 위주", "background": "마탑에서 자란 천재 술사"},
    {"name": "그늘의 흑막", "alias": "가면", "role": "조연",
     "appearance": "검은 가면과 붉은 도포", "personality": "냉철하고 계산적",
     "speech_style": "낮은 어조의 존댓말", "background": "정체불명의 거대 세력 수장"},
]


def _coerce_lore(data: dict) -> list[OutlineLore]:
    lore: list[OutlineLore] = []
    seen: set[str] = set()
    for item in _as_list(data.get("lore_entries"))[:18]:
        if not isinstance(item, dict):
            continue
        title = _as_str(item.get("title"))
        if not title or title in seen:
            continue
        seen.add(title)
        category = _as_str(item.get("category"))
        keywords = [k.strip() for k in _as_list(item.get("keywords"))
                    if isinstance(k, str) and k.strip()]
        lore.append(OutlineLore(
            category=category if category in LORE_CATEGORIES else "기타",
            title=title,
            content=_as_str(item.get("content")) or None,
            keywords=keywords or [title],
        ))
    # 8개 미만이면 템플릿으로 보강 (8~12개 요구 충족)
    for cat, title in _FALLBACK_LORE_TEMPLATES:
        if len(lore) >= 8:
            break
        if title not in seen:
            lore.append(OutlineLore(category=cat, title=title,
                                    content=None, keywords=[title]))
    return lore


# --------------------------------------------------------------------------
# 규칙 기반 폴백 (템플릿 생성)
# --------------------------------------------------------------------------

def fallback_structure(genre: str, premise: str | None, volume_count: int,
                       cpv: int) -> dict:
    """LLM 실패/미사용 시 템플릿으로이라도 전체 구조를 만든다."""
    hook = premise.strip() if premise and premise.strip() else ""
    base_title = f"[{genre}] {hook[:18]}…" if hook else f"[{genre}] 운명의 서막"
    titles = [base_title]
    for suffix in ("–별들의 노래", ":천명을 거스르다", " 외전:잔향", "–붉은 서약"):
        candidate = base_title + suffix
        if len(candidate) <= 255:
            titles.append(candidate)

    logline = hook or f"{genre} 세계에서 평범한 이가 운명에 맞서 성장하는 이야기."
    theme = "성장과 선택, 그리고 인연의 무게"

    arcs = ["극적 도입과 상실", "첫 시련과 동료", "숨은 힘의 각성", "위기의 심화", "반격의 준비"]
    volumes = []
    for v in range(1, volume_count + 1):
        vol_chapters = []
        for i in range(1, cpv + 1):
            arc = arcs[(v + i - 2) % len(arcs)]
            vol_chapters.append({
                "order": i,
                "title": f"{v}권 {i}화. {arc}",
                "synopsis": (f"{arc} 국면의 {i}번째 이야기. 주인공은 새로운 적과 마주치고"
                             f" 지난 선택의 대가를 확인한다.\n동료와의 인연이 깊어지지만,"
                             f" 그림자 속 흑막은 다음 수를 준비하고 있다."),
                "key_event": f"{arc} — 결정적 전환점 #{(v - 1) * cpv + i}",
            })
        arc = arcs[(v - 1) % len(arcs)]
        volumes.append({"volume": v, "title": f"{v}권. {arc}",
                        "overview": f"{arc} 국면 — 주인공이 시련을 겪으며 성장하는 권.",
                        "emotion_curve": f"{max(cpv - 2, 1)}화 고조 → {max(cpv - 1, 1)}화 완충 → {cpv}화 고봉",
                        "climax_note": f"{cpv}화에서 {arc}의 결정적 대치가 벌어진다.",
                        "chapters": vol_chapters})

    characters = [dict(t) for t in _FALLBACK_CHAR_TEMPLATES]
    relationships = [
        {"from": characters[0]["name"], "to": characters[1]["name"],
         "label": "동문-동료", "note": "함께 성장하는 전우"},
        {"from": characters[0]["name"], "to": characters[2]["name"],
         "label": "제자-스승", "note": "비밀을 건네주는 인자"},
        {"from": characters[0]["name"], "to": characters[3]["name"],
         "label": "숙적", "note": "가문 멸문의 진범 추정"},
    ]
    lore_entries = [{"category": cat, "title": title, "content": None,
                     "keywords": [title]}
                    for cat, title in _FALLBACK_LORE_TEMPLATES]

    return {"titles": titles, "logline": logline, "theme": theme,
            "volumes": volumes, "characters": characters,
            "relationships": relationships, "lore_entries": lore_entries}


# --------------------------------------------------------------------------
# 영속화 — 단일 트랜잭션 bulk insert
# --------------------------------------------------------------------------

def _character_card_json(c: OutlineCharacter) -> dict:
    """SillyTavern V2 카드 호환 확장 여지를 남긴 card_json."""
    description = ", ".join(x for x in [c.appearance, c.background] if x)
    return {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": c.name,
            "aliases": [c.alias] if c.alias else [],
            "description": description,
            "personality": c.personality or "",
            "scenario": c.background or "",
            "first_mes": "",
            "mes_example": c.speech_style or "",
        },
    }


def persist_structure(db: Session, genre: str, premise: str | None,
                      structure: dict, generated_by: str,
                      volume_count: int, chapters_per_volume: int) -> dict:
    """생성 결과를 Project+Chapter+Character+Relationship+LoreEntry로 저장.

    모델 객체를 세션에 모두 쌓고 commit을 마지막 한 번만 호출해
    단일 트랜잭션으로 처리한다(Relationship FK 채움용 flush는 커밋 전).
    """
    titles = [t for t in (_as_str(x) for x in _as_list(structure.get("titles"))) if t]
    title = (titles[0] if titles else f"[{genre}] 무제")[:255]
    logline = _as_str(structure.get("logline"))
    theme = _as_str(structure.get("theme")) or None

    volumes_index: dict[int, str] = {}
    for vol in _as_list(structure.get("volumes")):
        if isinstance(vol, dict):
            volumes_index[vol.get("volume")] = _as_str(vol.get("title"))

    outline = _coerce_outline(structure, volume_count, chapters_per_volume)
    characters = _coerce_characters(structure)
    relationships = _coerce_relationships(structure, {c.name for c in characters})
    lore = _coerce_lore(structure)
    outline_summary = _summarize_outline(outline, volumes_index)

    project = Project(title=title, genre=genre, synopsis=logline or None)
    # 제목은 후보 중 1번째, 나머지 후보와 기획 메타는 memo에 보관
    project.memo = json.dumps({
        "bootstrap": {
            "generated_by": generated_by,
            "premise": premise,
            "theme": theme,
            "protagonist_name": _as_str(structure.get("protagonist_name")) or None,
            "outline_summary": outline_summary,
            "title_candidates": titles[1:],
        }
    }, ensure_ascii=False)

    for c in outline:
        memo_parts = [part for part in (
            c.synopsis,
            f"[핵심 사건] {c.key_event}" if c.key_event else "",
        ) if part]
        project.chapters.append(Chapter(
            volume=c.volume,
            sort_order=c.sort_order,
            title=c.title[:255],
            content_md="",
            status="초고",
            word_count_cache=0,
            memo="\n\n".join(memo_parts) or None,
        ))

    char_rows: dict[str, Character] = {}
    for cd in characters:
        row = Character(
            name=cd.name[:255],
            aliases=[cd.alias] if cd.alias else [],
            role=cd.role,
            appearance=cd.appearance,
            personality=cd.personality,
            speech_style=cd.speech_style,
            background=cd.background,
            card_json=_character_card_json(cd),
        )
        char_rows[cd.name] = row
        project.characters.append(row)

    for item in lore:
        project.lore_entries.append(LoreEntry(
            category=item.category,
            title=item.title[:255],
            content=item.content,
            keywords=item.keywords,
        ))

    # 권 개요 — 부트스트랩과 동시 생성(G-050 확장: 목차 콜에서 함께 설계)
    volume_note_count = 0
    seen_volumes: set[int] = set()
    for vol in _as_list(structure.get("volumes")):
        if not isinstance(vol, dict):
            continue
        v_raw = vol.get("volume")
        v = v_raw if isinstance(v_raw, int) and v_raw >= 1 else None
        if v is None or v in seen_volumes:
            continue
        seen_volumes.add(v)
        project.volume_notes.append(VolumeNote(
            volume=v,
            title=_as_str(vol.get("title"))[:255],
            overview=_as_str(vol.get("overview")) or None,
            emotion_curve=_as_str(vol.get("emotion_curve")) or None,
            climax_note=_as_str(vol.get("climax_note")) or None,
        ))
        volume_note_count += 1

    db.add(project)
    db.flush()  # FK(id) 채움 — 아직 커밋 전, 동일 트랜잭션
    for r in relationships:
        db.add(Relationship(
            from_character_id=char_rows[r["from"]].id,
            to_character_id=char_rows[r["to"]].id,
            label=r["label"],
            note=r["note"],
        ))
    db.commit()  # 단일 트랜잭션 커밋
    db.refresh(project)

    return {
        "project_id": project.id,
        "title": project.title,
        "logline": logline,
        "outline_summary": outline_summary,
        "character_count": len(characters),
        "lore_count": len(lore),
        "chapter_count": len(outline),
        "volume_count": volume_count,
        "relationship_count": len(relationships),
        "volume_note_count": volume_note_count,
        "title_candidates": titles[1:],
        "theme": theme,
        "used_ai": generated_by == "ai",
        "fallback": generated_by == "fallback",
    }


# --------------------------------------------------------------------------
# 오케스트레이션
# --------------------------------------------------------------------------

def resolve_endpoint(db: Session) -> tuple[AiEndpoint, str]:
    """기본 엔드포인트(is_default) → 아무 엔드포인트 순으로 선택한다."""
    endpoint = db.scalars(
        select(AiEndpoint).where(AiEndpoint.is_default.is_(True))).first()
    if endpoint is None:
        endpoint = db.query(AiEndpoint).first()
    model = endpoint.default_model if endpoint else None
    if endpoint is None or not model:
        raise NoEndpointError(
            "AI 엔드포인트 또는 기본 모델이 설정되지 않았습니다. "
            "설정에서 엔드포인트를 등록하거나 use_ai=false로 재요청하세요.")
    return endpoint, model


async def generate_structure(genre: str, premise: str | None, title_style: str,
                             volume_count: int, chapters_per_volume: int,
                             client, model: str,
                             temperature: float | None = None,
                             reasoning_effort: str | None = None) -> dict:
    """LLM 4회 호출로 전체 구조 JSON을 만든다. 실패 시 BootstrapAIError.

    temperature/reasoning_effort가 None이면 파라미터를 전송하지 않는다
    (Codex 계열 reasoning 모델은 temperature를 거부한다).
    """
    idea = await _call_json(
        client, model,
        _idea_messages(genre, premise, title_style), temperature,
        reasoning_effort=reasoning_effort)

    outline_msgs = _outline_messages(genre, idea, volume_count, chapters_per_volume)
    outline_data = await _call_json(client, model, outline_msgs, temperature,
                                    reasoning_effort=reasoning_effort)
    preview = _coerce_outline(outline_data, volume_count, chapters_per_volume)
    summary = _outline_anchor_summary(preview, {
        v.get("volume"): _as_str(v.get("title"))
        for v in _as_list(outline_data.get("volumes")) if isinstance(v, dict)
    })

    # 콜 3 — 캐릭터 심층 설계
    characters_data = await _call_json(
        client, model,
        _characters_messages(genre, idea, summary), temperature,
        reasoning_effort=reasoning_effort)

    # 콜 4 — 관계망 + 세계관 (캐릭터 이름과 연결)
    names = [c.get("name") for c in _as_list(characters_data.get("characters"))
             if isinstance(c, dict) and _as_str(c.get("name"))]
    rellore_data = await _call_json(
        client, model,
        _relations_lore_messages(genre, idea, summary, names), temperature,
        reasoning_effort=reasoning_effort)

    return {
        "titles": [_as_str(t) for t in _as_list(idea.get("titles"))][:5],
        "logline": _as_str(idea.get("logline")),
        "theme": _as_str(idea.get("theme")),
        "protagonist_name": _as_str(idea.get("protagonist_name")),
        "characters": characters_data.get("characters"),
        "relationships": rellore_data.get("relationships"),
        "lore_entries": rellore_data.get("lore_entries"),
        "volumes": outline_data.get("volumes"),
        "_outline_preview_summary": summary,
    }
