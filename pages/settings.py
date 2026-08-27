"""Safe environment and database status page."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from components.cards import InfoCard, render_card_grid
from components.database_feedback import render_database_feedback
from services.database import DatabaseHealth, DatabaseState


def render(health: DatabaseHealth, on_retry: Callable[[], None]) -> None:
    st.html(
        '<section class="gdd-hero">'
        '<div class="gdd-hero__kicker">Configuração segura</div>'
        "<h1>Seu espaço, sob controle.</h1>"
        "<p>Credenciais ficam fora do código e o estado técnico é exibido sem "
        "revelar dados sensíveis.</p>"
        "</section>"
    )

    state_label = {
        DatabaseState.READY: "Pronto",
        DatabaseState.MISSING_CONFIG: "Não configurado",
        DatabaseState.UNAVAILABLE: "Indisponível",
        DatabaseState.MIGRATION_REQUIRED: "Migration pendente",
    }[health.state]
    revision = health.current_revision or "Ainda não aplicada"
    render_card_grid(
        (
            InfoCard("●", "Banco", state_label, health.database_label),
            InfoCard(
                "↗",
                "Schema",
                revision,
                "O Alembic mantém cada alteração rastreável e reproduzível.",
            ),
            InfoCard(
                "◈",
                "Segredos",
                "Variáveis de ambiente",
                "DATABASE_URL nunca é armazenada na interface ou no session_state.",
            ),
        )
    )

    if not health.is_ready:
        render_database_feedback(health, on_retry)
        return

    st.success("Banco conectado e migration atualizada.", icon="✅")
    if st.button("Verificar novamente", icon=":material/refresh:"):
        on_retry()
