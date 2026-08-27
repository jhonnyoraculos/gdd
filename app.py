"""GDD Studio Streamlit entrypoint and shared application shell."""

from __future__ import annotations

import logging

import streamlit as st

from components.app_shell import render_topbar
from components.database_feedback import render_database_feedback
from components.navigation import build_navigation, get_entry_for_page, render_sidebar
from config.settings import AppSettings, ConfigurationError, get_settings
from services.database import (
    DatabaseHealth,
    DatabaseState,
    check_database_health,
    dispose_engine,
)
from styles.loader import load_styles
from utils.logging_config import configure_logging

st.set_page_config(
    page_title="GDD Studio",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="auto",
)


@st.cache_data(ttl=15, show_spinner=False)
def _cached_database_health(_settings: AppSettings) -> DatabaseHealth:
    return check_database_health(_settings)


def _retry_database() -> None:
    dispose_engine()
    get_settings.cache_clear()
    _cached_database_health.clear()
    st.rerun()


def _load_health() -> DatabaseHealth:
    try:
        settings = get_settings()
        configure_logging(settings.log_level)
        return _cached_database_health(settings)
    except ConfigurationError as exc:
        configure_logging("INFO")
        logging.getLogger(__name__).error(
            "Invalid application configuration: %s", type(exc).__name__
        )
        return DatabaseHealth(
            state=DatabaseState.MISSING_CONFIG,
            public_message=(
                "A configuração do banco possui um valor inválido. Revise o arquivo .env."
            ),
            database_label="Não configurado",
        )


def main() -> None:
    load_styles(st.context.theme.type)
    health = _load_health()

    entries = build_navigation(health, _retry_database)
    current_page = st.navigation(
        [entry.page for entry in entries],
        position="hidden",
    )
    current_entry = get_entry_for_page(entries, current_page)

    render_sidebar(entries)
    render_topbar(current_entry.spec.title, health)

    if current_entry.spec.requires_database and not health.is_ready:
        render_database_feedback(health, _retry_database)
        st.stop()

    current_page.run()


main()
