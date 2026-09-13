"""장편 기억 provenance/revision/time-scope contract tests."""
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, MemoryEntry, Project
from app.services.long_memory import (
    create_memory_entry,
    format_context_memory,
    select_context_memory,
    validate_visibility_transition,
)


def _session(tmp_path: Path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'memory.db'}")
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def _project_with_chapters(db):
    project = Project(title="memory project")
    other = Project(title="other project")
    db.add_all([project, other])
    db.flush()
    current = Chapter(project_id=project.id, sort_order=2, title="current", content_md="current", revision=3)
    future = Chapter(project_id=project.id, sort_order=3, title="future", content_md="future", revision=1)
    db.add_all([current, future])
    db.commit()
    return project, other, current, future


def test_select_context_memory_excludes_stale_future_wrong_project_and_retired(tmp_path):
    engine, db = _session(tmp_path)
    project, other, current, future = _project_with_chapters(db)
    create_memory_entry(db, project_id=project.id, chapter_id=current.id, source_revision=3,
                        source_text=current.content_md, kind="fact", body="현재 정본", visibility="approved")
    create_memory_entry(db, project_id=project.id, chapter_id=current.id, source_revision=2,
                        source_text=current.content_md, kind="fact", body="오래된 기억", visibility="approved")
    create_memory_entry(db, project_id=project.id, chapter_id=future.id, source_revision=1,
                        source_text=future.content_md, kind="fact", body="미래 기억", visibility="approved")
    create_memory_entry(db, project_id=other.id, chapter_id=None, source_revision=None,
                        source_text=None, kind="fact", body="다른 작품", visibility="approved")
    create_memory_entry(db, project_id=project.id, chapter_id=current.id, source_revision=3,
                        source_text=current.content_md, kind="fact", body="폐기 기억", visibility="retired")
    db.commit()

    entries = select_context_memory(db, project_id=project.id, target_chapter_id=current.id)

    assert [entry.body for entry in entries] == ["현재 정본"]
    db.close(); engine.dispose()


def test_memory_service_rejects_invalid_inputs_and_target_ownership(tmp_path):
    engine, db = _session(tmp_path)
    project, other, current, _future = _project_with_chapters(db)
    foreign_chapter = Chapter(project_id=other.id, sort_order=1, title="foreign", content_md="foreign")
    db.add(foreign_chapter)
    db.commit()

    invalid_cases = [
        {"kind": "unknown", "body": "body"},
        {"kind": "fact", "body": "   "},
        {"kind": "fact", "body": "body", "visibility": "unknown"},
        {"kind": "fact", "body": "body", "chapter_id": 99999},
        {"kind": "fact", "body": "body", "source_revision": 1},
        {"kind": "fact", "body": "body", "chapter_id": foreign_chapter.id},
        {"kind": "fact", "body": "body", "effective_from_sort_order": 3, "effective_to_sort_order": 2},
        {"kind": "fact", "body": "body", "effective_from_sort_order": float("nan")},
        {"kind": "fact", "body": "body", "effective_to_sort_order": float("inf")},
    ]
    for values in invalid_cases:
        with pytest.raises(ValueError):
            create_memory_entry(
                db,
                project_id=project.id,
                chapter_id=values.pop("chapter_id", None),
                source_revision=values.pop("source_revision", None),
                source_text=current.content_md,
                **values,
            )

    with pytest.raises(ValueError, match="target chapter not found"):
        select_context_memory(db, project.id, 99999)
    with pytest.raises(ValueError, match="belongs to another project"):
        select_context_memory(db, project.id, foreign_chapter.id)
    with pytest.raises(ValueError):
        validate_visibility_transition("retired", "approved")
    db.close(); engine.dispose()


def test_memory_effective_range_and_draft_policy(tmp_path):
    engine, db = _session(tmp_path)
    project, _other, current, _future = _project_with_chapters(db)
    create_memory_entry(db, project_id=project.id, chapter_id=current.id, source_revision=3,
                        source_text=current.content_md, kind="summary", body="visible", visibility="approved",
                        effective_from_sort_order=2, effective_to_sort_order=2)
    create_memory_entry(db, project_id=project.id, chapter_id=current.id, source_revision=3,
                        source_text=current.content_md, kind="summary", body="draft", visibility="draft")
    create_memory_entry(db, project_id=project.id, chapter_id=current.id, source_revision=3,
                        source_text=current.content_md, kind="summary", body="after", visibility="approved",
                        effective_from_sort_order=3)
    db.commit()

    assert [entry.body for entry in select_context_memory(db, project.id, current.id)] == ["visible"]
    selected_with_draft = select_context_memory(db, project.id, current.id, include_draft=True)
    assert [entry.body for entry in selected_with_draft] == ["visible", "draft"]
    rendered = format_context_memory(selected_with_draft)
    assert "[approved]" in rendered and "[draft]" in rendered
    db.close(); engine.dispose()
