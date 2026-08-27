"""Shared application chrome."""

from __future__ import annotations

from html import escape

import streamlit as st

from services.database import DatabaseHealth, DatabaseState


def _status_presentation(health: DatabaseHealth) -> tuple[str, str]:
    if health.state is DatabaseState.READY:
        return "ready", "Dados protegidos"
    if health.state is DatabaseState.UNAVAILABLE:
        return "error", "Banco indisponível"
    if health.state is DatabaseState.MIGRATION_REQUIRED:
        return "warning", "Atualização pendente"
    return "warning", "Configurar banco"


def render_topbar(page_title: str, health: DatabaseHealth) -> None:
    status_class, status_label = _status_presentation(health)
    st.html(
        '<header class="gdd-topbar">'
        '<div class="gdd-topbar__context">'
        '<p class="gdd-topbar__eyebrow">Game Design Workspace</p>'
        f'<h2 class="gdd-topbar__title">{escape(page_title)}</h2>'
        "</div>"
        f'<div class="gdd-status-pill gdd-status-pill--{status_class}" '
        f'title="{escape(health.public_message)}">'
        '<span class="gdd-status-pill__dot"></span>'
        f"{escape(status_label)}"
        "</div>"
        "</header>"
    )
