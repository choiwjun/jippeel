"""Deterministic request interleavings on independent temporary SQLite sessions."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, create_db_engine
from app.models import Chapter, MemoryEntry, Project
from app.routers import memories, projects
from app.schemas import MemoryEntryCreate, MemoryEntryUpdate


@pytest.fixture()
def sessions(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'memory-races.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        project = Project(title="Race fixture")
        db.add(project)
        db.flush()
        chapter = Chapter(project_id=project.id, title="Source", sort_order=1)
        db.add(chapter)
        db.commit()
        ids = project.id, chapter.id
    yield factory, ids
    engine.dispose()


def create(db, pid, cid):
    return memories.create_memory(pid, MemoryEntryCreate(
        chapter_id=cid, kind="fact", body="Preserve this evidence",
        effective_from_sort_order=0, effective_to_sort_order=10,
    ), db)


@pytest.mark.parametrize("winner,loser", [
    ({"visibility": "retired"}, {"visibility": "approved"}),
    ({"visibility": "approved"}, {"visibility": "retired"}),
    ({"effective_from_sort_order": 8}, {"effective_to_sort_order": 5}),
    ({"effective_to_sort_order": 5}, {"effective_from_sort_order": 8}),
])
def test_patch_rejects_stale_validated_snapshot(sessions, monkeypatch, winner, loser):
    factory, (pid, cid) = sessions
    with factory() as seed:
        mid = create(seed, pid, cid).id
    original = memories._get_memory_or_404
    with factory() as stale_db, factory() as winning_db:
        def read_then_commit_winner(project_id, memory_id, db):
            snapshot = original(project_id, memory_id, db)
            if db is stale_db:
                memories.update_memory(pid, mid, MemoryEntryUpdate.model_validate(winner), winning_db)
            return snapshot
        monkeypatch.setattr(memories, "_get_memory_or_404", read_then_commit_winner)
        with pytest.raises(HTTPException) as conflict:
            memories.update_memory(pid, mid, MemoryEntryUpdate.model_validate(loser), stale_db)
        assert conflict.value.status_code == 409
    with factory() as verify:
        stored = verify.get(MemoryEntry, mid)
        assert all(getattr(stored, key) == value for key, value in winner.items())
        assert stored.effective_from_sort_order <= stored.effective_to_sort_order


def test_delete_reference_check_serializes_competing_creation(sessions, monkeypatch):
    """At the old check/delete gap, a second writer must not commit then be cascaded."""
    factory, (pid, cid) = sessions
    original = Session.delete
    competing_result = []
    with factory() as deleting_db, factory() as creating_db:
        # Fail immediately on a reserved writer lock; no sleep or scheduler race.
        creating_db.execute(text("PRAGMA busy_timeout=0"))
        def create_at_delete_gap(db, instance):
            if db is deleting_db and isinstance(instance, Chapter):
                try:
                    competing_result.append(create(creating_db, pid, cid))
                except HTTPException as exc:
                    competing_result.append(exc.status_code)
            return original(db, instance)
        monkeypatch.setattr(Session, "delete", create_at_delete_gap)
        projects.delete_chapter(cid, deleting_db)
        assert competing_result == [409], "creation must conflict, not commit evidence that DELETE cascades"
    with factory() as verify:
        assert verify.get(Chapter, cid) is None
        assert list(verify.scalars(select(MemoryEntry))) == []
        with pytest.raises(HTTPException) as missing:
            create(verify, pid, cid)
        assert missing.value.status_code == 404


def test_committed_memory_wins_before_delete_transaction(sessions, monkeypatch):
    factory, (pid, cid) = sessions
    original = Session.execute
    committed = []
    with factory() as deleting_db, factory() as creating_db:
        def commit_before_first_delete_statement(db, *args, **kwargs):
            if db is deleting_db and not committed:
                committed.append(create(creating_db, pid, cid).id)
            return original(db, *args, **kwargs)
        monkeypatch.setattr(Session, "execute", commit_before_first_delete_statement)
        with pytest.raises(HTTPException) as conflict:
            projects.delete_chapter(cid, deleting_db)
        assert conflict.value.status_code == 409
    with factory() as verify:
        assert verify.get(Chapter, cid) is not None
        assert verify.get(MemoryEntry, committed[0]) is not None


def test_delete_wins_after_create_reads_source(sessions, monkeypatch):
    factory, (pid, cid) = sessions
    original = memories._get_chapter_for_project
    with factory() as creating_db, factory() as deleting_db:
        def read_then_delete(project_id, chapter_id, db):
            source = original(project_id, chapter_id, db)
            projects.delete_chapter(cid, deleting_db)
            return source
        monkeypatch.setattr(memories, "_get_chapter_for_project", read_then_delete)
        with pytest.raises(HTTPException) as conflict:
            create(creating_db, pid, cid)
        assert conflict.value.status_code == 409
    with factory() as verify:
        assert verify.get(Chapter, cid) is None
        assert list(verify.scalars(select(MemoryEntry))) == []


def test_patch_empty_and_repeated_values_remain_successful(sessions):
    factory, (pid, cid) = sessions
    with factory() as db:
        entry = create(db, pid, cid)
        for patch in ({}, {"visibility": "draft"}, {"visibility": "retired"},
                      {"visibility": "retired"}, {"effective_to_sort_order": None}):
            result = memories.update_memory(pid, entry.id, MemoryEntryUpdate.model_validate(patch), db)
            assert result.id == entry.id
        assert result.visibility == "retired"
        assert result.effective_to_sort_order is None


@pytest.mark.parametrize("operation", ["patch", "delete"])
def test_sqlite_writer_contention_returns_conflict_without_changes(sessions, operation):
    factory, (pid, cid) = sessions
    with factory() as seed:
        mid = create(seed, pid, cid).id
    with factory() as holder, factory() as contender:
        contender.execute(text("PRAGMA busy_timeout=0"))
        holder.execute(text("BEGIN IMMEDIATE"))
        with pytest.raises(HTTPException) as conflict:
            if operation == "patch":
                memories.update_memory(pid, mid, MemoryEntryUpdate(visibility="approved"), contender)
            else:
                projects.delete_chapter(cid, contender)
        assert conflict.value.status_code == 409
        assert not contender.in_transaction(), "conflicts must roll back and release the transaction"
    with factory() as verify:
        assert verify.get(Chapter, cid) is not None
        assert verify.get(MemoryEntry, mid).visibility == "draft"


def test_patch_compares_null_bounds_and_empty_patch_does_not_write(sessions, monkeypatch):
    factory, (pid, cid) = sessions
    with factory() as seed:
        entry = memories.create_memory(pid, MemoryEntryCreate(kind="fact", body="Unbounded"), seed)
        result = memories.update_memory(pid, entry.id, MemoryEntryUpdate(), seed)
        assert result.updated_at == entry.updated_at
    original = memories._get_memory_or_404
    with factory() as stale_db, factory() as winning_db:
        def read_then_set_upper_bound(project_id, memory_id, db):
            snapshot = original(project_id, memory_id, db)
            if db is stale_db:
                memories.update_memory(pid, entry.id, MemoryEntryUpdate(effective_to_sort_order=5), winning_db)
            return snapshot
        monkeypatch.setattr(memories, "_get_memory_or_404", read_then_set_upper_bound)
        with pytest.raises(HTTPException) as conflict:
            memories.update_memory(pid, entry.id, MemoryEntryUpdate(effective_from_sort_order=8), stale_db)
        assert conflict.value.status_code == 409
    with factory() as verify:
        stored = verify.get(MemoryEntry, entry.id)
        assert stored.effective_from_sort_order is None
        assert stored.effective_to_sort_order == 5


def test_deliberate_whole_project_delete_keeps_existing_cascade_policy(sessions):
    factory, (pid, cid) = sessions
    with factory() as db:
        mid = create(db, pid, cid).id
    with factory() as deleting_db:
        projects.delete_project(pid, deleting_db)
    with factory() as verify:
        assert verify.get(Project, pid) is None
        assert verify.get(Chapter, cid) is None
        assert verify.get(MemoryEntry, mid) is None
