"""Alembic орчин — engine-ийг core.orm-оос (SQLite/Postgres, DATABASE_URL) авна."""
from alembic import context

import core.orm as orm
import core.orm.models  # noqa: F401  (autogenerate-д бүх model бүртгэгдэнэ)
from core.orm.base import Base

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=orm._url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = context.config.attributes.get("connection")
    if connectable is not None:              # bootstrap.migrate() өөрийн холболтоо дамжуулна
        _run(connectable)
        return
    with orm.engine().connect() as conn:
        _run(conn)


def _run(conn):
    context.configure(connection=conn, target_metadata=target_metadata,
                      render_as_batch=conn.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
