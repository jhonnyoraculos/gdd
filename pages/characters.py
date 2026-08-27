"""Project character library route."""

from __future__ import annotations

import logging
from html import escape
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.cards import render_empty_state
from components.character_card import render_character_card
from components.character_form import show_create_character_dialog
from config.settings import get_settings
from services.character_service import (
    CharacterNotFoundError,
    CharacterSort,
    list_character_roles,
    list_characters,
)
from services.project_service import ProjectNotFoundError, get_project
from services.user_service import owner_from_settings
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)
_SORT_OPTIONS = {
    "Nome: A–Z": CharacterSort.NAME_ASC,
    "Nome: Z–A": CharacterSort.NAME_DESC,
    "Editados recentemente": CharacterSort.UPDATED_DESC,
}


def _project_id() -> UUID | None:
    raw = st.query_params.get("project")
    try:
        return UUID(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _pagination(project_id: UUID, current: int, total_pages: int) -> None:
    if total_pages <= 1:
        return
    previous, counter, following = st.columns([0.3, 1, 0.3], vertical_alignment="center")
    with previous:
        if st.button("Anterior", disabled=current <= 1, use_container_width=True):
            st.session_state[f"character-page-{project_id}"] = current - 1
            st.rerun()
    with counter:
        st.caption(f"Página {current} de {total_pages}")
    with following:
        if st.button("Próxima", disabled=current >= total_pages, use_container_width=True):
            st.session_state[f"character-page-{project_id}"] = current + 1
            st.rerun()


def render() -> None:
    project_id = _project_id()
    if project_id is None:
        render_empty_state(
            "?", "Projeto não identificado", "Abra Personagens dentro de um projeto."
        )
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return

    owner = owner_from_settings(get_settings())
    try:
        project = get_project(owner, project_id)
        roles = list_character_roles(owner, project_id)
    except (ProjectNotFoundError, CharacterNotFoundError):
        render_empty_state("?", "Projeto não encontrado", "Este projeto não está disponível.")
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return
    except SQLAlchemyError:
        incident = uuid4().hex[:8]
        LOGGER.exception("Character library bootstrap failed | incident=%s", incident)
        st.error(f"Não foi possível carregar os personagens. Código: {incident}")
        return

    if st.button(project.name, icon=":material/arrow_back:"):
        go_to_page("project_detail", id=str(project_id))

    intro, action = st.columns([1, 0.32], vertical_alignment="bottom")
    with intro:
        st.html(
            '<section class="gdd-page-intro">'
            '<div class="gdd-page-intro__eyebrow">Base de conhecimento</div>'
            "<h1>Personagens</h1>"
            f"<p>Elenco narrativo de {escape(project.name)}.</p>"
            "</section>"
        )
    with action:
        if st.button(
            "Novo personagem",
            icon=":material/person_add:",
            type="primary",
            use_container_width=True,
        ):
            show_create_character_dialog(owner, project_id)

    search_col, role_col, sort_col = st.columns([1.35, 0.8, 0.85])
    with search_col:
        search = st.text_input(
            "Pesquisar personagem",
            placeholder="Nome, apelido, codinome ou papel...",
            icon=":material/search:",
            label_visibility="collapsed",
        )
    with role_col:
        selected_role = st.selectbox(
            "Papel narrativo",
            [None, *roles],
            format_func=lambda value: value or "Todos os papéis",
            label_visibility="collapsed",
        )
    with sort_col:
        sort_label = st.selectbox(
            "Ordenar",
            list(_SORT_OPTIONS),
            label_visibility="collapsed",
        )

    page_key = f"character-page-{project_id}"
    current_page = int(st.session_state.get(page_key, 1))
    try:
        result = list_characters(
            owner,
            project_id,
            search=search,
            role=selected_role,
            sort=_SORT_OPTIONS[sort_label],
            page=current_page,
        )
    except (CharacterNotFoundError, SQLAlchemyError):
        incident = uuid4().hex[:8]
        LOGGER.exception("Character list failed | incident=%s", incident)
        st.error(f"Não foi possível carregar os personagens. Código: {incident}")
        return

    if current_page > result.total_pages:
        st.session_state[page_key] = result.total_pages
        st.rerun()
    st.caption(f"{result.total} personagem{'s' if result.total != 1 else ''}")
    if not result.items:
        render_empty_state(
            "♙",
            "Nenhum personagem encontrado",
            "Crie o primeiro personagem ou ajuste os filtros da busca.",
        )
        return

    columns = st.columns(3, gap="medium")
    for index, character in enumerate(result.items):
        with columns[index % len(columns)]:
            render_character_card(character)
    _pagination(project_id, result.page, result.total_pages)
