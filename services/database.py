"""SQLAlchemy engine, transaction and schema-migration boundaries."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from config.settings import AppSettings, get_settings

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG_PATH = PROJECT_ROOT / "alembic.ini"

_engine: Engine | None = None
_engine_key: tuple[object, ...] | None = None
_engine_lock = Lock()


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a database operation is requested without a URL."""


class DatabaseState(StrEnum):
    READY = "ready"
    MISSING_CONFIG = "missing_config"
    UNAVAILABLE = "unavailable"
    MIGRATION_REQUIRED = "migration_required"


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    state: DatabaseState
    public_message: str
    database_label: str
    current_revision: str | None = None
    expected_revision: str | None = None
    incident_id: str | None = None

    @property
    def is_ready(self) -> bool:
        return self.state is DatabaseState.READY

    @property
    def is_reachable(self) -> bool:
        return self.state in {DatabaseState.READY, DatabaseState.MIGRATION_REQUIRED}


def _engine_configuration_key(settings: AppSettings) -> tuple[object, ...]:
    return (
        settings.database_url,
        settings.database_sslmode,
        settings.database_pool_size,
        settings.database_max_overflow,
        settings.database_connect_timeout,
    )


def _create_engine(settings: AppSettings) -> Engine:
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL não foi configurada.")

    parsed_url = make_url(settings.database_url)
    connect_args: dict[str, object] = {
        "connect_timeout": settings.database_connect_timeout,
        "application_name": "gdd_studio",
    }
    if "sslmode" not in parsed_url.query:
        connect_args["sslmode"] = settings.database_sslmode

    return create_engine(
        parsed_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=10,
        pool_recycle=600,
        pool_use_lifo=True,
        hide_parameters=True,
        connect_args=connect_args,
    )


def get_engine(settings: AppSettings | None = None) -> Engine:
    """Return one thread-safe engine per process and active configuration."""

    global _engine, _engine_key

    active_settings = settings or get_settings()
    key = _engine_configuration_key(active_settings)
    if _engine is not None and _engine_key == key:
        return _engine

    with _engine_lock:
        if _engine is not None and _engine_key == key:
            return _engine
        if _engine is not None:
            _engine.dispose()
        _engine = _create_engine(active_settings)
        _engine_key = key
        return _engine


def dispose_engine() -> None:
    """Dispose cached connections, mainly for retry flows and tests."""

    global _engine, _engine_key

    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _engine_key = None


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Open one short transaction and always close its session.

    Domain services should receive this session and let this boundary commit or
    roll back the complete user action.
    """

    active_engine = engine or get_engine()
    session_factory = sessionmaker(
        bind=active_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    with session_factory.begin() as session:
        yield session


def _alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(ALEMBIC_CONFIG_PATH))
    if database_url:
        # Alembic's ConfigParser treats percent signs as interpolation tokens.
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def get_expected_schema_revision() -> str:
    scripts = ScriptDirectory.from_config(_alembic_config())
    expected_revision = scripts.get_current_head()
    if expected_revision is None:
        raise RuntimeError("Nenhuma migration Alembic foi encontrada.")
    return expected_revision


def check_database_health(settings: AppSettings | None = None) -> DatabaseHealth:
    """Probe connectivity and compare the database revision with Alembic head."""

    active_settings = settings or get_settings()
    if not active_settings.is_database_configured:
        return DatabaseHealth(
            state=DatabaseState.MISSING_CONFIG,
            public_message=(
                "A conexão com o banco ainda não foi configurada. "
                "Adicione DATABASE_URL ao arquivo .env."
            ),
            database_label=active_settings.database_label,
        )

    try:
        engine = get_engine(active_settings)
        expected_revision = get_expected_schema_revision()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current_revision = MigrationContext.configure(connection).get_current_revision()

        if current_revision != expected_revision:
            return DatabaseHealth(
                state=DatabaseState.MIGRATION_REQUIRED,
                public_message=(
                    "O banco está conectado, mas a estrutura precisa ser atualizada. "
                    "Execute a migration inicial antes de continuar."
                ),
                database_label=active_settings.database_label,
                current_revision=current_revision,
                expected_revision=expected_revision,
            )

        return DatabaseHealth(
            state=DatabaseState.READY,
            public_message="Banco de dados conectado e estrutura atualizada.",
            database_label=active_settings.database_label,
            current_revision=current_revision,
            expected_revision=expected_revision,
        )
    except (SQLAlchemyError, OSError, RuntimeError, ValueError) as exc:
        incident_id = uuid4().hex[:8]
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        LOGGER.error(
            "Database health check failed | incident=%s | type=%s | sqlstate=%s",
            incident_id,
            type(exc).__name__,
            sqlstate or "unknown",
        )
        return DatabaseHealth(
            state=DatabaseState.UNAVAILABLE,
            public_message=(
                "Não foi possível acessar o banco de dados agora. Seus dados não foram alterados."
            ),
            database_label=active_settings.database_label,
            incident_id=incident_id,
        )


def upgrade_database(settings: AppSettings | None = None, revision: str = "head") -> None:
    """Apply migrations explicitly; this is never called on a Streamlit rerun."""

    active_settings = settings or get_settings()
    migration_url = active_settings.migration_url
    if migration_url is None:
        raise DatabaseNotConfiguredError("DATABASE_URL não foi configurada.")
    command.upgrade(_alembic_config(migration_url), revision)
