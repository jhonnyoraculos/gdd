"""Streamlit entrypoint smoke test without Neon credentials."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import config.settings as settings_module
from config.settings import get_settings


@pytest.mark.parametrize(
    "invalid_environment",
    [
        {},
        {"DATABASE_URL": "postgresql://user:pass@host:not-a-port/db"},
        {"LOG_LEVEL": "verbose"},
    ],
)
def test_app_starts_with_missing_or_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch,
    invalid_environment: dict[str, str],
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_DIRECT_URL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.setattr(settings_module, "dotenv_values", lambda: {})
    for key, value in invalid_environment.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=15).run()

    assert not app.exception
    assert len(app.sidebar.get("page_link")) == 7
