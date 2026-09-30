from sqlalchemy.orm import sessionmaker

from app.database import Base, create_db_engine
from app.models import LoreEntry, Project
from app.routers import lorebook
import app.services.fts as fts


engine = create_db_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)
session = sessionmaker(bind=engine)()
try:
    project = Project(title="fallback QA")
    session.add(project)
    session.commit()
    session.add_all(
        [
            LoreEntry(
                project_id=project.id,
                category="용어",
                title="fallback needle",
                content="needle",
            ),
            LoreEntry(
                project_id=project.id,
                category="장소",
                title="other needle",
                content="needle",
            ),
        ]
    )
    session.commit()
    fts._fts_supported = lambda _conn: False
    rows = lorebook.search_lore(project.id, "needle", "용어", 1, session)
    print([(row.id, row.category, row.title) for row in rows])
finally:
    session.close()
    engine.dispose()
