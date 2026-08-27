"""Environment configuration tests."""

import pytest

import config.settings as settings_module
from config.settings import ConfigurationError, load_settings, normalize_postgres_url


@pytest.mark.parametrize(
    ("source", "expected_prefix"),
    [
        ("postgres://user:pass@host/db", "postgresql+psycopg://"),
        ("postgresql://user:pass@host/db", "postgresql+psycopg://"),
        ("postgresql+psycopg://user:pass@host/db", "postgresql+psycopg://"),
    ],
)
def test_postgres_urls_use_psycopg_driver(source: str, expected_prefix: str) -> None:
    assert normalize_postgres_url(source).startswith(expected_prefix)


def test_missing_database_url_is_an_explicit_state() -> None:
    settings = load_settings({})

    assert settings.database_url is None
    assert settings.migration_url is None
    assert not settings.is_database_configured
    assert settings.database_label == "Não configurado"


def test_direct_url_is_preferred_for_migrations() -> None:
    settings = load_settings(
        {
            "DATABASE_URL": "postgresql://runtime:secret@pooler.example/db",
            "DATABASE_DIRECT_URL": "postgresql://migration:secret@direct.example/db",
        }
    )

    assert "direct.example" in (settings.migration_url or "")
    assert settings.database_label == "pooler.example/db"
    assert "secret" not in settings.database_label
    assert "secret" not in repr(settings)


def test_invalid_scheme_is_rejected_without_echoing_url() -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_settings({"DATABASE_URL": "sqlite:///local.db"})


def test_pool_values_must_be_positive_integers() -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_POOL_SIZE"):
        load_settings({"DATABASE_POOL_SIZE": "0"})


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="LOG_LEVEL"):
        load_settings({"LOG_LEVEL": "verbose"})


def test_workspace_owner_has_stable_valid_defaults_and_normalization() -> None:
    defaults = load_settings({})
    configured = load_settings(
        {"GDD_OWNER_NAME": "Jhonny", "GDD_OWNER_EMAIL": "JHONNY@EXAMPLE.COM"}
    )

    assert defaults.owner_email == "creator@gdd.local"
    assert configured.owner_name == "Jhonny"
    assert configured.owner_email == "jhonny@example.com"


@pytest.mark.parametrize("email", ["", "invalid", "@example.com", "name@"])
def test_invalid_workspace_owner_email_is_rejected(email: str) -> None:
    with pytest.raises(ConfigurationError, match="GDD_OWNER_EMAIL"):
        load_settings({"GDD_OWNER_EMAIL": email})


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:pass@host:not-a-port/db",
        "postgresql://user:pass@/db",
        "postgresql://user:pass@[broken/db",
        "postgresql://user:pass@host",
    ],
)
def test_malformed_postgres_url_is_rejected(database_url: str) -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_settings({"DATABASE_URL": database_url})


def test_local_dotenv_is_reread_without_overriding_real_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_DIRECT_URL", raising=False)
    dotenv_data = {
        "DATABASE_URL": "postgresql://user:first@first.example/db",
    }
    monkeypatch.setattr(settings_module, "dotenv_values", lambda: dotenv_data)

    first = load_settings()
    dotenv_data["DATABASE_URL"] = "postgresql://user:second@second.example/db"
    second = load_settings()

    assert first.database_label == "first.example/db"
    assert second.database_label == "second.example/db"

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:environment@environment.example/db",
    )
    assert load_settings().database_label == "environment.example/db"
