"""로어북 FTS5 인덱스 서비스 (사양 FR-304 / 부록05 §L4).

SQLite FTS5를 "선택 적용"한다:
  - 빌드된 SQLite에 FTS5가 있으면 가상 테이블(lore_entries_fts)로 MATCH 검색
  - 없으면 LIKE 폴백 검색
인덱스 동기화는 애플리케이션 레벨에서 수행(외부 컨텐츠 트리거 대신 명시적 갱신).
"""
import json
import sqlite3

from sqlalchemy import text
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.models import LoreEntry

_FTS_TABLE = "lore_entries_fts"


def _fts_supported(conn) -> bool:
    try:
        conn.exec_driver_sql(f"CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_TABLE} USING fts5(title, content, keywords)")
        return True
    except sqlite3.OperationalError:
        return False


def _is_session(obj) -> bool:
    return isinstance(obj, Session)


def _conn_of(db_or_conn):
    """Session이면 내부 Connection을, Connection이면 그대로 반환."""
    return db_or_conn.connection() if _is_session(db_or_conn) else db_or_conn


def ensure_fts_index(db: Session) -> None:
    """FTS5 가상 테이블이 없으면 생성(선택 적용). 지원하지 않는 빌드면 조용히 건너뛴다."""
    conn = _conn_of(db)
    if not _fts_supported(conn):
        return
    # 기존 항목 색인 (멱등: 전부 지우고 다시 채움)
    conn.exec_driver_sql(f"DELETE FROM {_FTS_TABLE}")
    rows = conn.execute(
        text("SELECT id, title, COALESCE(content,''), keywords FROM lore_entries")
    ).fetchall()
    for row_id, title, content, keywords in rows:
        _fts_insert(conn, row_id, title, content, keywords)


def _keywords_text(keywords) -> str:
    """JSON 배열 → 공백 결합 문자열 (토크나이저 친화)."""
    if not keywords:
        return ""
    if isinstance(keywords, str):
        try:
            keywords = json.loads(keywords)
        except (TypeError, ValueError):
            return keywords
    return " ".join(str(k) for k in keywords)


def _fts_insert(conn, row_id: int, title: str, content: str, keywords) -> None:
    conn.execute(
        text(
            f"INSERT INTO {_FTS_TABLE}(rowid, title, content, keywords) "
            "VALUES (:rid, :title, :content, :kw)"
        ),
        {"rid": row_id, "title": title or "", "content": content or "", "kw": _keywords_text(keywords)},
    )


def sync_fts_entry(db: Session, entry: LoreEntry) -> None:
    """항목 1건을 인덱스에 반영 (생성/수정 공용)."""
    conn = _conn_of(db)
    if not _fts_supported(conn):
        return
    conn.exec_driver_sql(f"DELETE FROM {_FTS_TABLE} WHERE rowid={int(entry.id)}")
    _fts_insert(conn, entry.id, entry.title, entry.content or "", entry.keywords)


def delete_fts_entry(db: Session, entry_id: int) -> None:
    conn = _conn_of(db)
    if not _fts_supported(conn):
        return
    conn.exec_driver_sql(f"DELETE FROM {_FTS_TABLE} WHERE rowid={int(entry_id)}")


def _build_fts_query(query: str) -> str | None:
    """사용자 입력을 FTS5 접두어 질의로 변환.

    - 공백 분리 각 항을 따옴표로 감싸 특수문자·컬럼명 오해 방지
    - 접미어 * 로 조사 결합형 토큰("검기를")도 "검기"로 매치
      (unicode61은 한국어 형태소를 분리하지 않음)
    """
    terms = [t.strip() for t in query.split() if t.strip()]
    if not terms:
        return None
    return " ".join('\"%s\"*' % t.replace('"', '\"\"') for t in terms)


def search_entry_ids(
    db: Session,
    query: str,
    limit: int = 100,
    project_id: int | None = None,
    category: str | None = None,
) -> list[int] | None:
    """MATCH 검색. 지정된 scope를 적용한 뒤 limit한다."""
    conn = _conn_of(db)
    if not _fts_supported(conn):
        return None
    fts_query = _build_fts_query(query)
    if fts_query is None:
        return []
    try:
        if project_id is None and category is None:
            statement = (
                f"SELECT rowid FROM {_FTS_TABLE} WHERE {_FTS_TABLE} MATCH :q "
                "ORDER BY rank LIMIT :limit"
            )
            params = {"q": fts_query, "limit": limit}
        else:
            conditions = [f"{_FTS_TABLE} MATCH :q"]
            params = {"q": fts_query, "limit": limit}
            if project_id is not None:
                conditions.append("e.project_id = :project_id")
                params["project_id"] = project_id
            if category is not None:
                conditions.append("e.category = :category")
                params["category"] = category
            statement = (
                f"SELECT f.rowid FROM {_FTS_TABLE} AS f "
                "JOIN lore_entries AS e ON e.id = f.rowid "
                f"WHERE {' AND '.join(conditions)} "
                "ORDER BY f.rank LIMIT :limit"
            )
        rows = conn.execute(text(statement), params).fetchall()
    except sqlite3.OperationalError:
        # 문법 오류 등은 폴백 검색으로 처리
        return None
    return [r[0] for r in rows]
