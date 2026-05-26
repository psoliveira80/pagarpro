import asyncio
from logging.config import fileConfig

from alembic import context
import sqlalchemy as sa
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import *  # noqa: F401,F403 — import all models for metadata
from app.infrastructure.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _include_object(obj: object, name: str, type_: str, reflected: bool, compare_to: object) -> bool:
    # Exclude alembic's own version tracking table
    if type_ == "table" and name == "alembic_version":
        return False
    # Exclude index comparison — indexes are managed by explicit migrations, not models
    if type_ == "index":
        return False
    return True


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=_include_object,
        compare_type=False,
        compare_server_default=False,
        # Bypass RLS for migrations — no tenant context during schema changes
        version_table_schema="public",
    )
    connection.execute(sa.text("SET row_security = off"))
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
