"""Interactive narrative map route."""

from __future__ import annotations

import logging
from html import escape
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.cards import InfoCard, render_card_grid, render_empty_state
from components.narrative_map import render_narrative_map
from config.settings import get_settings
from services.narrative_map_service import (
    MapEdgeType,
    MapNodeType,
    NarrativeMapNotFoundError,
    get_narrative_map,
)
from services.user_service import owner_from_settings
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


def _project_id() -> UUID | None:
    raw = st.query_params.get("project")
    try:
        return UUID(raw) if raw else None
    except (TypeError, ValueError):
        return None


def render() -> None:
    project_id = _project_id()
    if project_id is None:
        render_empty_state(
            "?",
            "Projeto não identificado",
            "Abra o mapa pelo workspace de um projeto.",
        )
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return

    owner = owner_from_settings(get_settings())
    try:
        graph = get_narrative_map(owner, project_id)
    except NarrativeMapNotFoundError:
        render_empty_state(
            "?",
            "Mapa não encontrado",
            "O projeto pode ter sido removido ou não pertence a este workspace.",
        )
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return
    except SQLAlchemyError:
        incident = uuid4().hex[:8]
        LOGGER.exception("Narrative map load failed | incident=%s", incident)
        st.error(f"Não foi possível carregar o mapa narrativo. Código: {incident}")
        return

    back, narrative = st.columns([1, 1], vertical_alignment="center")
    with back:
        if st.button("Projeto", icon=":material/arrow_back:"):
            go_to_page("project_detail", id=str(project_id))
    with narrative, st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Editar narrativa", icon=":material/account_tree:"):
            go_to_page("narrative", project=str(project_id))

    st.html(
        '<div class="gdd-page-intro">'
        "<span>Base de conhecimento visual</span>"
        f"<h1>Mapa Narrativo · {escape(graph.project_name)}</h1>"
        "<p>Explore capítulos, cenas, personagens, aparições e relações reais do projeto.</p>"
        "</div>"
    )

    relationship_edges = sum(edge.edge_type == MapEdgeType.RELATIONSHIP for edge in graph.edges)
    render_card_grid(
        (
            InfoCard(
                "§",
                "Capítulos",
                str(graph.count(MapNodeType.CHAPTER)),
                "Estruturas principais da história.",
            ),
            InfoCard(
                "◇",
                "Cenas",
                str(graph.count(MapNodeType.SCENE)),
                "Momentos organizados na linha narrativa.",
            ),
            InfoCard(
                "♙",
                "Personagens",
                str(graph.count(MapNodeType.CHARACTER)),
                "Entidades conectadas ao mapa.",
            ),
            InfoCard(
                "↗",
                "Relações",
                str(relationship_edges),
                "Conexões direcionais entre personagens.",
            ),
        )
    )
    if len(graph.nodes) == 1:
        st.info(
            "O projeto ainda não possui capítulos, cenas ou personagens. "
            "O mapa crescerá automaticamente conforme a narrativa for criada."
        )

    st.caption(
        "Arraste para mover o mapa ou os nós, use a roda do mouse para zoom e selecione um nó."
    )
    render_narrative_map(graph, st.context.theme.type)
