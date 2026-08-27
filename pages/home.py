"""Foundation-aware home page."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from components.cards import InfoCard, Step, render_card_grid, render_empty_state, render_steps
from services.database import DatabaseHealth, DatabaseState


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Bom dia"
    if hour < 18:
        return "Boa tarde"
    return "Boa noite"


def _database_card(health: DatabaseHealth) -> InfoCard:
    if health.state is DatabaseState.READY:
        return InfoCard(
            "✓",
            "Persistência",
            "Neon conectado",
            "Estrutura versionada e pronta para dados permanentes.",
        )
    if health.state is DatabaseState.MIGRATION_REQUIRED:
        return InfoCard(
            "↻",
            "Persistência",
            "Migration pendente",
            "A conexão está válida; aplique a estrutura inicial do banco.",
        )
    if health.state is DatabaseState.UNAVAILABLE:
        return InfoCard(
            "!",
            "Persistência",
            "Conexão indisponível",
            "A interface permanece segura sem criar um banco alternativo local.",
        )
    return InfoCard(
        "⌁",
        "Persistência",
        "Conecte o Neon",
        "DATABASE_URL será a única fonte permanente dos seus documentos.",
    )


def render(health: DatabaseHealth) -> None:
    st.html(
        '<section class="gdd-hero">'
        '<div class="gdd-hero__kicker">Seu workspace criativo</div>'
        f'<h1>{_greeting()} <span aria-hidden="true">👋</span></h1>'
        "<p>Continue criando seus mundos. Ideias, decisões e documentos terão um "
        "só lugar para crescer.</p>"
        "</section>"
    )

    render_card_grid(
        (
            _database_card(health),
            InfoCard(
                "◫",
                "Estrutura",
                "Documentos organizados",
                "Projetos, seções hierárquicas, notas e versões já possuem uma base consistente.",
            ),
            InfoCard(
                "◇",
                "Experiência",
                "Feito para qualquer tela",
                "A navegação adapta-se ao desktop, tablet e celular sem fluxo paralelo.",
            ),
        )
    )

    st.html(
        '<div class="gdd-section-heading">'
        "<h2>Primeiros passos</h2>"
        "<p>Uma configuração curta antes de criar o primeiro jogo.</p>"
        "</div>"
    )

    if health.state is DatabaseState.READY:
        render_empty_state(
            "✦",
            "Seu workspace está pronto",
            "Abra Projetos para criar, editar e organizar seus jogos com persistência no Neon.",
        )
        return

    render_steps(
        (
            Step(
                "01",
                "Conecte o Neon",
                "Copie .env.example para .env e preencha DATABASE_URL sem colocar "
                "a credencial no código.",
            ),
            Step(
                "02",
                "Aplique a estrutura",
                "Execute python -m scripts.init_db para criar as tabelas versionadas.",
            ),
            Step(
                "03",
                "Valide a conexão",
                "Use python -m scripts.check_database e reinicie o aplicativo.",
            ),
        )
    )
