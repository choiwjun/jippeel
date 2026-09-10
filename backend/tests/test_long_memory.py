"""장편 기억 provenance/revision/time-scope contract tests."""
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, MemoryEntry, Project
from app.services.long_memory import create_memory_entry, select_context_memory


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
    assert [entry.body for entry in select_context_memory(db, project.id, current.id, include_draft=True)] == ["visible", "draft"]
    db.close(); engine.dispose()
