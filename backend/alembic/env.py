"""Alembic 마이그레이션 환경 (Sprint 2).

- 대상 메타데이터: app.models (SQLAlchemy 2.x)
- DB URL: DATABASE_URL 환경변수 우선 → app.database 기본값
- 접속 프라그마는 app.database.create_db_engine 경유로 표준 적용(부록05 §⑤-4)
"""
import os
from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401  (모델 등록)
from app.database import DATABASE_URL, Base, create_db_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata

_db_url = os.environ.get("DATABASE_URL") or DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite ALTER 제약 회피
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_db_engine(_db_url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite ALTER 제약 회피
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
