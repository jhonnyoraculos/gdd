"""Reusable project library views."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.cards import render_empty_state
from components.project_card import render_project_card
from components.project_form import show_create_project_dialog
from config.settings import get_settings
from services.project_service import ProjectSort, list_projects
from services.user_service import owner_from_settings
from utils.constants import PROJECT_STATUSES
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    key: str
    eyebrow: str
    title: str
    description: str
    archived: bool | None = False
    favorite: bool | None = None
    page_size: int = 12
    empty_icon: str = "◫"
    empty_title: str = "Nenhum projeto encontrado"
    empty_body: str = "Crie um projeto para começar seu próximo mundo."
    show_filters: bool = True


PROJECTS_COLLECTION = CollectionSpec(
    key="projects",
    eyebrow="Sua biblioteca",
    title="Projetos",
    description="Todos os jogos ativos, organizados em um só lugar.",
)
RECENT_COLLECTION = CollectionSpec(
    key="recent",
    eyebrow="Continue criando",
    title="Recentes",
    description="Projetos ativos ordenados pela última alteração.",
    page_size=12,
    empty_icon="◷",
    empty_title="Nenhum projeto recente",
    empty_body="Assim que você criar ou editar um jogo, ele aparecerá aqui.",
    show_filters=False,
)
FAVORITES_COLLECTION = CollectionSpec(
    key="favorites",
    eyebrow="Acesso rápido",
    title="Favoritos",
    description="Os projetos importantes que você quer manter por perto.",
    archived=None,
    favorite=True,
    empty_icon="☆",
    empty_title="Nenhum favorito ainda",
    empty_body="Use a estrela de um projeto para fixá-lo nesta área.",
)
ARCHIVED_COLLECTION = CollectionSpec(
    key="archived",
    eyebrow="Biblioteca preservada",
    title="Arquivados",
    description="Projetos fora do fluxo ativo, disponíveis para consulta ou restauração.",
    archived=True,
    empty_icon="□",
    empty_title="O arquivo está vazio",
    empty_body="Projetos arquivados poderão ser restaurados a qualquer momento.",
)

_SORT_OPTIONS = {
    "Editados recentemente": ProjectSort.UPDATED_DESC,
    "Editados há mais tempo": ProjectSort.UPDATED_ASC,
    "Nome: A–Z": ProjectSort.NAME_ASC,
    "Nome: Z–A": ProjectSort.NAME_DESC,
}


def _header(spec: CollectionSpec) -> None:
    text_col, action_col = st.columns([1, 0.3], vertical_alignment="bottom")
    with text_col:
        st.html(
            '<section class="gdd-page-intro">'
            f'<div class="gdd-page-intro__eyebrow">{spec.eyebrow}</div>'
            f"<h1>{spec.title}</h1><p>{spec.description}</p>"
            "</section>"
        )
    with action_col:
        if st.button(
            "Novo projeto",
            key=f"new-project-{spec.key}",
            type="primary",
            icon=":material/add:",
            use_container_width=True,
        ):
            show_create_project_dialog(owner_from_settings(get_settings()))


def _filters(spec: CollectionSpec) -> tuple[str | None, str | None, ProjectSort]:
    if not spec.show_filters:
        return None, None, ProjectSort.UPDATED_DESC
    search_col, status_col, sort_col = st.columns([1.4, 0.8, 0.9])
    with search_col:
        search = st.text_input(
            "Pesquisar projetos",
            key=f"project-search-{spec.key}",
            placeholder="Nome, codinome ou gênero...",
            icon=":material/search:",
            label_visibility="collapsed",
        )
    status_options = [None, *(option.value for option in PROJECT_STATUSES)]
    labels = {None: "Todos os status", **{o.value: o.label for o in PROJECT_STATUSES}}
    with status_col:
        status = st.selectbox(
            "Filtrar por status",
            status_options,
            key=f"project-status-{spec.key}",
            format_func=lambda value: labels[value],
            label_visibility="collapsed",
        )
    with sort_col:
        sort_label = st.selectbox(
            "Ordenar projetos",
            list(_SORT_OPTIONS),
            key=f"project-sort-{spec.key}",
            label_visibility="collapsed",
        )
    return search, status, _SORT_OPTIONS[sort_label]


def _render_pagination(spec: CollectionSpec, current: int, total_pages: int) -> None:
    if total_pages <= 1:
        return
    previous, counter, following = st.columns([0.3, 1, 0.3], vertical_alignment="center")
    with previous:
        if st.button(
            "Anterior",
            key=f"previous-{spec.key}",
            disabled=current <= 1,
            use_container_width=True,
        ):
            st.session_state[f"project-page-{spec.key}"] = current - 1
            st.rerun()
    with counter:
        st.caption(f"Página {current} de {total_pages}")
    with following:
        if st.button(
            "Próxima",
            key=f"next-{spec.key}",
            disabled=current >= total_pages,
            use_container_width=True,
        ):
            st.session_state[f"project-page-{spec.key}"] = current + 1
            st.rerun()


def render_project_collection(spec: CollectionSpec) -> None:
    owner = owner_from_settings(get_settings())
    _header(spec)
    search, status, sort = _filters(spec)
    page_key = f"project-page-{spec.key}"
    current_page = int(st.session_state.get(page_key, 1))
    try:
        result = list_projects(
            owner,
            archived=spec.archived,
            favorite=spec.favorite,
            search=search,
            status=status,
            sort=sort,
            page=current_page,
            page_size=spec.page_size,
        )
    except SQLAlchemyError:
        incident = uuid4().hex[:8]
        LOGGER.exception("Project list failed | incident=%s", incident)
        st.error(f"Não foi possível carregar os projetos agora. Código: {incident}")
        return

    if current_page > result.total_pages:
        st.session_state[page_key] = result.total_pages
        st.rerun()
    st.caption(f"{result.total} projeto{'s' if result.total != 1 else ''}")
    if not result.items:
        render_empty_state(spec.empty_icon, spec.empty_title, spec.empty_body)
        if spec.key != "projects" and st.button("Ver todos os projetos", use_container_width=True):
            go_to_page("projects")
        return

    columns = st.columns(3, gap="medium")
    for index, project in enumerate(result.items):
        with columns[index % len(columns)]:
            render_project_card(project, owner)
    _render_pagination(spec, result.page, result.total_pages)
