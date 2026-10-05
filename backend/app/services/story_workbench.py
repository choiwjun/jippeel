"""Read-only, source-labelled links for the current chapter writing workspace."""
from collections import defaultdict
import re

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chapter, Character, Scene, EventImpact, MemoryEntry, LoreEntry
from app.services.long_memory import content_sha256
from app.services import story_map_evidence


class CastMember(BaseModel):
    id: int
    name: str
    role: str | None
    mentioned: bool
    excerpt: str | None
    scene_ids: list[int]
    event_ids: list[int]
    profile: dict[str, str | None]


class WorkScene(BaseModel):
    id: int
    title: str
    position: int
    excerpt: str
    character_ids: list[int]


class WorkEvent(BaseModel):
    id: int
    label: str
    state_after: str | None
    character_ids: list[int]
    foreshadow_ids: list[int]


class WorkForeshadow(BaseModel):
    id: str
    label: str
    registered_status: str | None
    disposition: str | None = None
    planted: dict | None
    planned: dict | None
    resolved: dict | None
    character_ids: list[int]
    at_chapter: bool


class WorkLore(BaseModel):
    id: int
    title: str
    category: str | None
    excerpt: str


class WorkbenchOut(BaseModel):
    project_id: int
    chapter_id: int
    revision: int
    summary: str | None
    summary_id: int | None
    characters: list[CastMember]
    scenes: list[WorkScene]
    events: list[WorkEvent]
    relations: list[dict]
    foreshadows: list[WorkForeshadow]
    lore: list[WorkLore]
    ambiguous_terms: list[str]


def build(db: Session, pid: int, chapter: Chapter) -> WorkbenchOut:
    characters = db.scalars(select(Character).where(Character.project_id == pid).order_by(Character.id)).all()
    ids = {c.id for c in characters}
    owners = defaultdict(set)
    for c in characters:
        card = c.card_json if isinstance(c.card_json, dict) else {}
        data = card.get("data") if isinstance(card.get("data"), dict) else {}
        aliases = c.aliases if isinstance(c.aliases, list) else []
        extra = data.get("aliases") if isinstance(data.get("aliases"), list) else []
        for term in [c.name, *aliases, *extra]:
            if isinstance(term, str) and term.strip():
                owners[term.strip()].add(c.id)
    # Shared names/aliases cannot establish identity. Keep them unassigned.
    terms = {term: next(iter(own)) for term, own in owners.items() if len(own) == 1}
    ambiguous = sorted(term for term, own in owners.items() if len(own) > 1)
    name_pattern = re.compile('|'.join(re.escape(t) for t in sorted(owners, key=lambda t: (-len(t), t)))) if owners else None

    def mentions(body):
        text = body or ""
        matches = {}
        # Prefer the longest matching name, including ambiguous names, so a
        # shorter name embedded in another person's name is not also assigned.
        for match in name_pattern.finditer(text) if name_pattern else []:
            cid = terms.get(match.group())
            if cid is not None and cid not in matches:
                matches[cid] = text[max(0, match.start() - 35):match.end() + 65]
        return matches

    manuscript_mentions = mentions(chapter.content_md)
    scene_rows = db.scalars(select(Scene).where(Scene.chapter_id == chapter.id).order_by(Scene.sort_order, Scene.id)).all()
    scenes = [WorkScene(id=s.id, title=s.title, position=i + 1, excerpt=(s.content_md or "")[:350],
                        character_ids=sorted(mentions(s.content_md))) for i, s in enumerate(scene_rows)]
    digest = content_sha256(chapter.content_md)
    provenance = db.scalars(select(EventImpact.provenance_json).where(EventImpact.project_id == pid)).all()
    superseded = {p['supersedes_id'] for p in provenance if isinstance(p, dict)
                  and type(p.get('supersedes_id')) is int}
    event_rows = db.scalars(select(EventImpact).where(
        EventImpact.project_id == pid, EventImpact.chapter_id == chapter.id,
        EventImpact.visibility == 'approved', EventImpact.source_sha256 == digest,
    ).order_by(EventImpact.id)).all()
    refs = story_map_evidence.chapter_refs(db, pid)
    foreshadows = story_map_evidence.foreshadows(db, pid, chapter, refs)
    foreshadow_ids = {int(f['id'].split('-')[1]) for f in foreshadows}
    events = []
    for e in event_rows:
        if e.id in superseded:
            continue
        involved = set()
        for delta in e.character_deltas_json or []:
            if isinstance(delta, dict) and type(delta.get('character_id')) is int and delta['character_id'] in ids:
                involved.add(delta['character_id'])
        for delta in e.relationship_deltas_json or []:
            pair = delta.get('pair') if isinstance(delta, dict) else None
            if isinstance(pair, list) and len(pair) == 2 and all(type(v) is int and v in ids for v in pair):
                involved.update(pair)
        fids = {d['foreshadow_id'] for d in (e.foreshadow_deltas_json or []) if isinstance(d, dict)
                and type(d.get('foreshadow_id')) is int and d['foreshadow_id'] in foreshadow_ids}
        events.append(WorkEvent(id=e.id, label=e.label, state_after=e.state_after,
                                character_ids=sorted(involved), foreshadow_ids=sorted(fids)))
    cast = [CastMember(id=c.id, name=c.name, role=c.role, mentioned=c.id in manuscript_mentions,
                       excerpt=manuscript_mentions.get(c.id),
                       scene_ids=[s.id for s in scenes if c.id in s.character_ids],
                       event_ids=[e.id for e in events if c.id in e.character_ids],
                       profile={field: getattr(c, field) for field in
                                ('appearance', 'personality', 'speech_style', 'background', 'lifecycle_status', 'lifecycle_note')}) for c in characters]
    # Direct approved chapter summaries only; no unverified prose is promoted to a synopsis.
    summary = db.scalar(select(MemoryEntry).where(
        MemoryEntry.project_id == pid, MemoryEntry.chapter_id == chapter.id,
        MemoryEntry.kind == 'summary', MemoryEntry.visibility == 'approved',
        MemoryEntry.source_revision == chapter.revision, MemoryEntry.source_sha256 == digest,
    ).order_by(MemoryEntry.updated_at.desc(), MemoryEntry.id.desc()).limit(1))
    linked = []
    for f in foreshadows:
        fid = int(f['id'].split('-')[1])
        involved = sorted({cid for e in events if fid in e.foreshadow_ids for cid in e.character_ids})
        linked.append(WorkForeshadow(**{k: f.get(k) for k in ('id', 'label', 'registered_status', 'disposition', 'planted', 'planned', 'resolved')},
                                     character_ids=involved,
                                     at_chapter=any(f.get(k) and f[k]['id'] == chapter.id for k in ('planted', 'planned', 'resolved'))))
    lore_rows = db.scalars(select(LoreEntry).where(LoreEntry.project_id == pid).order_by(LoreEntry.id)).all()
    lore = []
    for entry in lore_rows:
        tokens = [entry.title, *(entry.keywords if isinstance(entry.keywords, list) else [])]
        if any(isinstance(t, str) and t.strip() and t.strip() in (chapter.content_md or '') for t in tokens):
            lore.append(WorkLore(id=entry.id, title=entry.title, category=entry.category, excerpt=(entry.content or '')[:350]))
    return WorkbenchOut(project_id=pid, chapter_id=chapter.id, revision=chapter.revision,
                        summary=summary.body if summary else None, summary_id=summary.id if summary else None,
                        characters=cast, scenes=scenes, events=events,
                        relations=story_map_evidence.relations(db, pid, chapter, refs), foreshadows=linked,
                        lore=lore, ambiguous_terms=ambiguous)
