"""Engine-independent database boundary tests."""

from sqlalchemy import Engine

from config.settings import load_settings
from models import User
from services.database import DatabaseState, check_database_health, session_scope


def test_missing_database_configuration_does_not_create_fallback() -> None:
    health = check_database_health(load_settings({}))

    assert health.state is DatabaseState.MISSING_CONFIG
    assert not health.is_ready
    assert not health.is_reachable


def test_session_scope_commits_one_complete_action(sqlite_engine: Engine) -> None:
    with session_scope(sqlite_engine) as session:
        session.add(
            User(
                name="Criador",
                email="creator@example.com",
                email_normalized="creator@example.com",
            )
        )

    with session_scope(sqlite_engine) as session:
        assert session.query(User).count() == 1


def test_session_scope_rolls_back_failed_action(sqlite_engine: Engine) -> None:
    try:
        with session_scope(sqlite_engine) as session:
            session.add(
                User(
                    name="Criador",
                    email="creator@example.com",
                    email_normalized="creator@example.com",
                )
            )
            raise RuntimeError("simulated action failure")
    except RuntimeError:
        pass

    with session_scope(sqlite_engine) as session:
        assert session.query(User).count() == 0
