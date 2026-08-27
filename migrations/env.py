"""Alembic environment configured from DATABASE_DIRECT_URL/DATABASE_URL."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from config.settings import get_settings
from models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
EXTERNAL_TABLES = {"playing_with_neon"}


def _include_object(
    _object: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Keep Neon sample tables outside GDD Studio's migration ownership."""

    is_external_table = (
        type_ == "table" and reflected and compare_to is None and name in EXTERNAL_TABLES
    )
    return not is_external_table


def _database_url() -> str:
    configured_url = config.get_main_option("sqlalchemy.url").strip()
    if configured_url:
        return configured_url

    settings = get_settings()
    if settings.migration_url is None:
        raise RuntimeError(
            "Configure DATABASE_URL (e opcionalmente DATABASE_DIRECT_URL) "
            "antes de executar as migrations."
        )
    return settings.migration_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings = get_settings()
    parsed_url = make_url(_database_url())
    connect_args: dict[str, object] = {
        "connect_timeout": settings.database_connect_timeout,
        "application_name": "gdd_studio_migrations",
    }
    if "sslmode" not in parsed_url.query:
        connect_args["sslmode"] = settings.database_sslmode

    connectable = create_engine(
        parsed_url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args=connect_args,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
