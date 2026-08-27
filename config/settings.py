"""Environment-backed configuration for GDD Studio.

Secrets are loaded from the process environment (and ``.env`` in local
development) and never copied into Streamlit session state.
"""

from __future__ import annotations

import os
from collections import ChainMap
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urlsplit

from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class ConfigurationError(ValueError):
    """Raised when an application setting is present but invalid."""


def normalize_postgres_url(value: str | None) -> str | None:
    """Return a SQLAlchemy psycopg URL without exposing or altering credentials."""

    if value is None or not value.strip():
        return None

    url = value.strip()
    if url.startswith("postgres://"):
        normalized = "postgresql+psycopg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://"):
        normalized = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    elif url.startswith("postgresql+psycopg://"):
        normalized = url
    else:
        raise ConfigurationError(
            "DATABASE_URL deve usar postgres://, postgresql:// ou postgresql+psycopg://."
        )

    try:
        standard_url = urlsplit(normalized)
        _ = standard_url.hostname
        parsed = make_url(normalized)
        # Accessing port also validates malformed numeric values.
        _ = parsed.port
    except (ArgumentError, ValueError) as exc:
        raise ConfigurationError("DATABASE_URL possui um formato inválido.") from exc

    if not parsed.host or not parsed.database:
        raise ConfigurationError("DATABASE_URL deve informar host e database.")
    return normalized


def _read_int(source: Mapping[str, str], key: str, default: int) -> int:
    raw_value = source.get(key, str(default))
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{key} deve ser um número inteiro.") from exc
    if value < 1:
        raise ConfigurationError(f"{key} deve ser maior que zero.")
    return value


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Immutable application configuration."""

    app_name: str = "GDD Studio"
    environment: str = "development"
    database_url: str | None = field(default=None, repr=False)
    database_direct_url: str | None = field(default=None, repr=False)
    database_sslmode: str = "require"
    database_pool_size: int = 3
    database_max_overflow: int = 2
    database_connect_timeout: int = 5
    log_level: str = "INFO"
    owner_name: str = "Criador"
    owner_email: str = "creator@gdd.local"

    @property
    def is_database_configured(self) -> bool:
        return self.database_url is not None

    @property
    def migration_url(self) -> str | None:
        return self.database_direct_url or self.database_url

    @property
    def database_label(self) -> str:
        """Return a credential-free database label safe for the interface and logs."""

        if self.database_url is None:
            return "Não configurado"
        parsed = make_url(self.database_url)
        host = parsed.host or "PostgreSQL"
        database = parsed.database or "database"
        return f"{host}/{database}"


def load_settings(environ: Mapping[str, str] | None = None) -> AppSettings:
    """Build settings from an explicit mapping or from ``os.environ``.

    Passing a mapping keeps tests deterministic and intentionally skips ``.env``.
    """

    if environ is None:
        file_values = {key: value for key, value in dotenv_values().items() if value is not None}
        # Real environment variables (including Streamlit secrets) always win.
        # dotenv_values does not mutate os.environ, so a cache clear can reread
        # an edited local .env file safely.
        source: Mapping[str, str] = ChainMap(os.environ, file_values)
    else:
        source = environ

    database_url = normalize_postgres_url(source.get("DATABASE_URL"))
    direct_url = normalize_postgres_url(
        source.get("DATABASE_DIRECT_URL") or source.get("DATABASE_MIGRATION_URL")
    )

    sslmode = source.get("DATABASE_SSLMODE", "require").strip().lower()
    if sslmode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise ConfigurationError("DATABASE_SSLMODE possui um valor inválido.")

    log_level = source.get("LOG_LEVEL", "INFO").strip().upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigurationError("LOG_LEVEL possui um valor inválido.")

    owner_name = source.get("GDD_OWNER_NAME", "Criador").strip()
    owner_email = source.get("GDD_OWNER_EMAIL", "creator@gdd.local").strip().casefold()
    if not owner_name or len(owner_name) > 120:
        raise ConfigurationError("GDD_OWNER_NAME deve ter entre 1 e 120 caracteres.")
    if (
        not owner_email
        or len(owner_email) > 320
        or "@" not in owner_email
        or owner_email.startswith("@")
        or owner_email.endswith("@")
    ):
        raise ConfigurationError("GDD_OWNER_EMAIL possui um valor inválido.")

    return AppSettings(
        app_name=source.get("APP_NAME", "GDD Studio").strip() or "GDD Studio",
        environment=source.get("APP_ENV", "development").strip().lower(),
        database_url=database_url,
        database_direct_url=direct_url,
        database_sslmode=sslmode,
        database_pool_size=_read_int(source, "DATABASE_POOL_SIZE", 3),
        database_max_overflow=_read_int(source, "DATABASE_MAX_OVERFLOW", 2),
        database_connect_timeout=_read_int(source, "DATABASE_CONNECT_TIMEOUT", 5),
        log_level=log_level,
        owner_name=owner_name,
        owner_email=owner_email,
    )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return process-wide settings without re-reading ``.env`` on every rerun."""

    return load_settings()
