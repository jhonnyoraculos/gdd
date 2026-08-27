"""Friendly database setup and failure states."""

from __future__ import annotations

from collections.abc import Callable
from html import escape

import streamlit as st

from services.database import DatabaseHealth, DatabaseState


def render_database_feedback(
    health: DatabaseHealth,
    on_retry: Callable[[], None],
) -> None:
    if health.state is DatabaseState.MISSING_CONFIG:
        icon = "⌁"
        title = "Conecte seu espaço permanente"
        detail = "Crie um arquivo .env a partir de .env.example e adicione a URL do Neon."
        command = "Copie .env.example para .env"
    elif health.state is DatabaseState.MIGRATION_REQUIRED:
        icon = "↻"
        title = "Estrutura pronta para ser aplicada"
        detail = "A conexão funcionou. Falta executar a migration versionada uma única vez."
        command = "python -m scripts.init_db"
    else:
        icon = "!"
        title = "Não conseguimos alcançar o banco"
        detail = "Confira a conexão e tente novamente. Nenhum dado local foi criado."
        command = "python -m scripts.check_database"

    incident = ""
    if health.incident_id:
        incident = f"<p>ID do incidente: {escape(health.incident_id)}</p>"

    st.html(
        '<section class="gdd-empty-state gdd-database-panel">'
        f'<div class="gdd-empty-state__icon" aria-hidden="true">{escape(icon)}</div>'
        f"<h1>{escape(title)}</h1>"
        f"<p>{escape(health.public_message)}</p>"
        f"<p>{escape(detail)}</p>"
        f'<code class="gdd-code">{escape(command)}</code>'
        f"{incident}"
        "</section>"
    )

    _, button_column, _ = st.columns([1, 1.2, 1])
    with button_column:
        st.button(
            "Tentar novamente",
            icon=":material/refresh:",
            on_click=on_retry,
            use_container_width=True,
        )
