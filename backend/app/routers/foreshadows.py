"""복선(foreshadow) 라우터 — 고도화 G-020~G-022·G-045·G-046.

복선은 "설치 → 회수" 상태로 관리하며, 미회수(설치) 복선은
POST /ai/generate의 context.auto_foreshadow로 자동 주입된다(G-022).
suggest 엔드포인트(G-046)는 회차 본문에서 복선으로 보이는 떡밥을
LLM 1콜로 추출해 후보만 반환한다(자동 등록 없음 — 작가가 선택해 등록).
"""
import openai
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, Foreshadow, Project
from app.schemas import (ForeshadowCreate, ForeshadowOut, ForeshadowSuggestRequest,
                         ForeshadowSuggestResponse, ForeshadowUpdate)
from app.services import injection, llm, usage as usage_service
from app.services.bootstrap import (NoEndpointError, _extract_json,
                                    resolve_endpoint)

router = APIRouter()

VALID_STATUS = ("설치", "회수", "보류")

_SUGGEST_SYSTEM = (
    "너는 웹소설 연재 편집장이다. 회차 본문에서 '아직 해결되지 않은 떡밥·복선'을 "
    "추려낸다. 이미 회차 안에서 완전히 해결된 사건은 후보에서 제외한다. "
    "반드시 단일 유효한 JSON 객체만 출력하고 코드펜스·설명은 절대 출력하지 않는다. "
    "떡밥이 없으면 빈 배열을 반환한다."
)


@router.get("/projects/{pid}/foreshadows/match")
def match_foreshadows(pid: int, chapter_id: int, db: Session = Depends(get_db)):
    """본문에 언급된 복선 매칭 (고도화 G-047).

    title·keywords가 현재 회차 본문에 등장하는 복선(전체 상태)을
    로어 자동 주입과 동일한 부분 일치 방식으로 선정해 반환한다.
    AI 패널이 "이 화에서 건드리고 있는 복선" 배지를 표시하는 데 쓴다.
    """
    _get_project_or_404(pid, db)
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.project_id != pid:
        raise HTTPException(status_code=404, detail="chapter not found")
    rows = db.scalars(
        select(Foreshadow).where(Foreshadow.project_id == pid)).all()
    text = chapter.content_md or ""
    matched = []
    for row in rows:
        terms: list[str] = []
        title = (row.title or "").strip()
        if len(title) >= injection._MIN_TERM_LEN and injection._occurrences(text, title) > 0:
            terms.append(title)
        for kw in row.keywords or []:
            if not isinstance(kw, str):
                continue
            kw = kw.strip()
            if len(kw) >= injection._MIN_TERM_LEN and injection._occurrences(text, kw) > 0:
                terms.append(kw)
        if terms:
            matched.append({"id": row.id, "title": row.title, "status": row.status,
                            "audience_knows": row.audience_knows,
                            "matched_terms": sorted(set(terms))[:4]})
    return matched


@router.post("/projects/{pid}/foreshadows/suggest", response_model=ForeshadowSuggestResponse)
async def suggest_foreshadows(pid: int, payload: ForeshadowSuggestRequest,
                              db: Session = Depends(get_db)):
    """회차 본문에서 복선 후보 자동 추출(G-046) — 후보만 반환, 자동 등록 없음."""
    _get_project_or_404(pid, db)
    chapter = db.get(Chapter, payload.chapter_id)
    if chapter is None or chapter.project_id != pid:
        raise HTTPException(status_code=404, detail="chapter not found")
    if not (chapter.content_md or "").strip():
        raise HTTPException(status_code=422, detail="본문이 비어 있습니다")

    try:
        endpoint, model = resolve_endpoint(db)
    except NoEndpointError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 기존 복선 제목을 제외 대상으로 전달 — 중복 후보 방지
    existing = db.scalars(
        select(Foreshadow.title).where(Foreshadow.project_id == pid)).all()
    messages = [
        {"role": "system", "content": _SUGGEST_SYSTEM},
        {"role": "user", "content": (
            f"회차 본문:\n{chapter.content_md}\n\n"
            f"이미 등록된 복선(이 중에 있으면 후보에서 제외): {', '.join(existing) or '(없음)'}\n\n"
            '다음 JSON 형식으로 출력하라:\n'
            '{"candidates": [{"title": "복선 제목", "content": "어떤 떡밥인지 1~2문장", '
            '"keywords": ["본문 매칭용 키워드"]}]}')},
    ]
    client = llm.make_client(endpoint.base_url, endpoint.api_key_encrypted)
    raw = ""
    try:
        raw = await llm.complete_chat(client, model, messages,
                                      temperature=endpoint.temperature,
                                      reasoning_effort=endpoint.reasoning_effort)
        data = _extract_json(raw)
    except openai.APIError as exc:
        raise HTTPException(status_code=502,
                            detail="엔드포인트 오류: "
                                   f"{getattr(exc, 'message', None) or type(exc).__name__}") from exc
    except (ValueError, Exception) as exc:  # noqa: BLE001 — JSON 파싱 실패
        raise HTTPException(status_code=502,
                            detail=f"복선 추출 실패: {type(exc).__name__}") from exc

    usage_service.record(kind="foreshadow_suggest", model=model,
                         endpoint_name=endpoint.name,
                         prompt_chars=sum(len(m["content"]) for m in messages),
                         completion_chars=len(raw or ""))

    candidates = []
    for item in (data.get("candidates") or [])[:10]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        keywords = [str(k).strip() for k in item.get("keywords") or []
                    if isinstance(k, str) and str(k).strip()]
        candidates.append({"title": title[:255],
                           "content": str(item.get("content") or "").strip() or None,
                           "keywords": keywords})
    return ForeshadowSuggestResponse(chapter_id=chapter.id, model=model,
                                     candidates=candidates)


def _get_project_or_404(pid: int, db: Session) -> Project:
    project = db.get(Project, pid)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _get_foreshadow_or_404(fid: int, db: Session) -> Foreshadow:
    row = db.get(Foreshadow, fid)
    if row is None:
        raise HTTPException(status_code=404, detail="foreshadow not found")
    return row


def _validate_chapter_refs(payload, db: Session) -> None:
    for field in ("planted_chapter_id", "resolved_chapter_id"):
        cid = getattr(payload, field, None)
        if cid is not None and db.get(Chapter, cid) is None:
            raise HTTPException(status_code=422, detail=f"{field}가 존재하지 않는 회차입니다")


@router.get("/projects/{pid}/foreshadows", response_model=list[ForeshadowOut])
def list_foreshadows(pid: int, status_filter: str | None = None,
                     db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    stmt = select(Foreshadow).where(Foreshadow.project_id == pid).order_by(
        Foreshadow.created_at, Foreshadow.id)
    if status_filter:
        if status_filter not in VALID_STATUS:
            raise HTTPException(status_code=422,
                                detail="status는 설치|회수|보류 중 하나여야 합니다")
        stmt = stmt.where(Foreshadow.status == status_filter)
    return list(db.scalars(stmt).all())


@router.post("/projects/{pid}/foreshadows", response_model=ForeshadowOut,
             status_code=status.HTTP_201_CREATED)
def create_foreshadow(pid: int, payload: ForeshadowCreate, db: Session = Depends(get_db)):
    _get_project_or_404(pid, db)
    _validate_chapter_refs(payload, db)
    row = Foreshadow(
        project_id=pid,
        title=payload.title,
        content=payload.content,
        keywords=payload.keywords or [],
        status=payload.status,
        planted_chapter_id=payload.planted_chapter_id,
        resolved_chapter_id=payload.resolved_chapter_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/foreshadows/{fid}", response_model=ForeshadowOut)
def update_foreshadow(fid: int, payload: ForeshadowUpdate, db: Session = Depends(get_db)):
    row = _get_foreshadow_or_404(fid, db)
    data = payload.model_dump(exclude_unset=True)
    _validate_chapter_refs(payload, db)
    if "status" in data and data["status"] not in VALID_STATUS:
        raise HTTPException(status_code=422, detail="status는 설치|회수|보류 중 하나여야 합니다")
    for field, value in data.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/foreshadows/{fid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foreshadow(fid: int, db: Session = Depends(get_db)):
    row = _get_foreshadow_or_404(fid, db)
    db.delete(row)
    db.commit()
