"""세계관 보강 스크립트 — 기존 프로젝트의 캐릭터·관계·로어를 심화 파이프라인으로 재생성.

부트스트랩 4콜 구조(bootstrap._characters_messages·_relations_lore_messages)를
기존 작품에 적용한다. 회차·본문은 건드리지 않고 캐릭터/관계/로어만 교체하며,
기존 인물의 이름과 정체성은 유지 지시로 보존한다.

LLM 생성 결과는 ~/.jippeel-logs/enrich_cache_<pid>.json 에 캐시된다 —
적용 단계가 실패해도 재실행 시 LLM 재호출 없이 이어서 적용된다(--fresh로 강제 재생성).

사용: backend/.venv/bin/python scripts/enrich_world.py <project_id>
"""
import asyncio
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import SessionLocal  # noqa: E402  # pyright: ignore[reportMissingImports]
from app.models import Project  # noqa: E402  # pyright: ignore[reportMissingImports]
from app.services import bootstrap as bs  # noqa: E402  # pyright: ignore[reportMissingImports]
from app.services import gpt_oauth, llm  # noqa: E402  # pyright: ignore[reportMissingImports]

API = "http://localhost:8000/api/v1"


def _project_id_from_argv() -> int:
    if len(sys.argv) <= 1:
        return 2
    try:
        project_id = int(sys.argv[1])
    except ValueError as exc:
        raise SystemExit("project_id는 양의 정수여야 합니다.") from exc
    if project_id < 1:
        raise SystemExit("project_id는 양의 정수여야 합니다.")
    return project_id


PID = _project_id_from_argv()
CACHE = Path.home() / ".jippeel-logs" / f"enrich_cache_{PID}.json"


def api(path, method="GET", body=None) -> Any:
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    raw = urllib.request.urlopen(req).read()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"API 응답이 JSON이 아닙니다: {path}") from exc


async def generate(db):
    project = db.get(Project, PID)
    genre = project.genre or "판타지"
    try:
        memo_data = json.loads(project.memo or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("프로젝트 memo가 유효한 JSON이 아닙니다.") from exc
    if not isinstance(memo_data, dict):
        raise RuntimeError("프로젝트 memo 형식이 올바르지 않습니다.")
    memo = memo_data.get("bootstrap", {})
    if not isinstance(memo, dict):
        memo = {}
    summary = memo.get("outline_summary") or project.synopsis or ""
    idea = {"titles": [project.title], "logline": project.synopsis or "",
            "theme": memo.get("theme", "")}

    chars = sorted(project.characters, key=lambda c: c.id)
    desc = "\n".join(f"- {c.name}({c.role or '조연'}): {(c.background or '')[:80]}"
                     for c in chars)

    provider = gpt_oauth.get_provider()
    client = llm.make_client(provider.base_url, None)
    model = provider.default_model

    # 콜 3 — 캐릭터 심화 (이름·정체성 유지 지시)
    chars_msgs = bs._characters_messages(genre, idea, summary)
    chars_msgs[-1]["content"] += (
        f"\n\n[중요] 아래 기존 인물의 이름·역할·정체성은 유지하고 깊이만 보강하라:\n{desc}\n"
        "필요하면 단역 1~2명을 추가할 수 있다. 본명/가명 이중 이름 설정이 있다면 유지한다.")
    characters = await bs._call_json(client, model, chars_msgs,
                                     reasoning_effort=provider.reasoning_effort)

    # 콜 4 — 관계망 + 세계관
    names = [c.get("name") for c in characters.get("characters", [])
             if isinstance(c, dict) and bs._as_str(c.get("name"))]
    rellore_msgs = bs._relations_lore_messages(genre, idea, summary, names)
    rellore = await bs._call_json(client, model, rellore_msgs,
                                  reasoning_effort=provider.reasoning_effort)
    return characters, rellore


def apply(characters, rellore):
    """기존 데이터 교체(관계→캐릭터→로어 순) 후 심화 결과 삽입."""
    for c in api(f"/projects/{PID}/characters"):
        for rel in api(f"/characters/{c['id']}/relations"):
            api(f"/relations/{rel['id']}", method="DELETE")
        api(f"/characters/{c['id']}", method="DELETE")
    for l in api(f"/projects/{PID}/lore"):
        api(f"/lore/{l['id']}", method="DELETE")

    ids = {}
    for c in characters.get("characters", []):
        created = api(f"/projects/{PID}/characters", method="POST", body={
            "name": c.get("name"),
            "aliases": [c["alias"]] if c.get("alias") else [],
            "role": c.get("role") if c.get("role") in ("주연", "조연", "단역", "기타") else "조연",
            "appearance": c.get("appearance"),
            "personality": c.get("personality"),
            "speech_style": c.get("speech_style"),
            "background": c.get("background"),
            "card_json": bs._character_card_json(
                bs.OutlineCharacter(
                    name=c.get("name"), alias=c.get("alias"), role=c.get("role"),
                    appearance=c.get("appearance"), personality=c.get("personality"),
                    speech_style=c.get("speech_style"), background=c.get("background"))),
        })
        ids[c["name"]] = created["id"]

    rel_count = 0
    for r in rellore.get("relationships", []):
        if r.get("from") in ids and r.get("to") in ids:
            api(f"/projects/{PID}/characters/relations", method="POST", body={
                "from_character_id": ids[r["from"]],
                "to_character_id": ids[r["to"]],
                "label": r.get("label"), "note": r.get("note")})
            rel_count += 1

    lore_count = 0
    for l in rellore.get("lore_entries", []):
        api(f"/projects/{PID}/lore", method="POST", body={
            "category": l.get("category") if l.get("category") in ("용어", "장소", "세력", "기타") else "기타",
            "title": l.get("title"), "content": l.get("content"),
            "keywords": l.get("keywords") or [l.get("title") or ""]})
        lore_count += 1

    # ---- 이름 정합화: 본문(1~5화)이 사용하는 이름으로 교정 ----
    # (LLM이 이름 유지 지시를 무시하고 새 캐스트를 만드는 경우 대비)
    RENAME = {"서이현": "유진서", "서연화": "백련화"}
    ALIAS_ADD = {"유진서": ["진서"]}
    for c in api(f"/projects/{PID}/characters"):
        body = {}
        new_name = RENAME.get(c["name"])
        if new_name:
            body["name"] = new_name
            if new_name in ALIAS_ADD:
                body["aliases"] = ALIAS_ADD[new_name]
        if body:
            api(f"/characters/{c['id']}", method="PATCH", body=body)

    def fix_text(t):
        for old_n, new_n in RENAME.items():
            t = t.replace(old_n, new_n)
        return t.replace("이현", "진서")

    for l in api(f"/projects/{PID}/lore"):
        content = fix_text(l.get("content") or "")
        keywords = [fix_text(str(k)) for k in (l.get("keywords") or [])]
        if content != (l.get("content") or ""):
            api(f"/lore/{l['id']}", method="PATCH", body={"content": content})
        if keywords != (l.get("keywords") or []):
            api(f"/lore/{l['id']}/keywords", method="PUT", body={"keywords": keywords})

    # 본문에 등장하지만 카드가 없는 인물 복원 (유채령 — 떠돌이 칼잡이)
    names_now = {c["name"] for c in api(f"/projects/{PID}/characters")}
    if "유채령" not in names_now:
        api(f"/projects/{PID}/characters", method="POST", body={
            "name": "유채령", "role": "조연",
            "appearance": "낡은 도포에 무명검을 등에 멘 떠돌이",
            "personality": "털털하고 눈치가 빠르다. 돈닥쟁이처럼 보이지만 약자는 못 본다.",
            "speech_style": "퉁명한 반말, 사람을 별명으로 부른다",
            "background": "폐허가 된 검각 주변을 떠돌며 유물을 회수해 파는 칼잡이. "
                          "검각 재조사 의뢰를 받고 유진서와 합류하며, 그의 검 읽는 능력을 "
                          "처음으로 목격하고도 도망치지 않는 유일한 동행이 된다."})
        print("유채령 카드 복원", flush=True)

    print(f"적용 완료 — 캐릭터 {len(ids)} / 관계 {rel_count} / 로어 {lore_count} + 이름 정합화", flush=True)


async def main():
    db = SessionLocal()
    cached_result = None
    if CACHE.exists() and "--fresh" not in sys.argv:
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            cached_result = cached["characters"], cached["rellore"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"캐시를 읽지 못해 새로 생성합니다: {type(exc).__name__}", flush=True)
    if cached_result is not None:
        characters, rellore = cached_result
        print("캐시에서 로드(재개)", flush=True)
        db.close()
    else:
        characters, rellore = await generate(db)
        db.close()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({"characters": characters, "rellore": rellore},
                                    ensure_ascii=False), encoding="utf-8")
        print("생성 완료 — 캐시 저장", flush=True)

    print(f"캐릭터 {len(characters.get('characters', []))}명 · 관계 {len(rellore.get('relationships', []))}쌍 · "
          f"로어 {len(rellore.get('lore_entries', []))}개", flush=True)
    apply(characters, rellore)


if __name__ == "__main__":
    asyncio.run(main())
