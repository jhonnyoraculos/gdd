"""Official Streamlit routing plus custom sidebar content."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

import streamlit as st

from pages import (
    archived,
    character,
    characters,
    editor,
    favorites,
    home,
    ideas,
    narrative,
    narrative_map,
    project,
    projects,
    recent,
    settings,
)
from services.database import DatabaseHealth
from utils.navigation_state import go_to_page


@dataclass(frozen=True, slots=True)
class PageSpec:
    key: str
    label: str
    title: str
    icon: str
    url_path: str
    group: str
    requires_database: bool = True
    default: bool = False


PAGE_SPECS: tuple[PageSpec, ...] = (
    PageSpec("home", "Início", "Início", ":material/home:", "home", "workspace", False, True),
    PageSpec("projects", "Projetos", "Projetos", ":material/grid_view:", "projects", "workspace"),
    PageSpec("recent", "Recentes", "Recentes", ":material/schedule:", "recent", "library"),
    PageSpec("favorites", "Favoritos", "Favoritos", ":material/star:", "favorites", "library"),
    PageSpec("ideas", "Ideias", "Ideias", ":material/lightbulb:", "ideas", "library"),
    PageSpec("archived", "Arquivados", "Arquivados", ":material/archive:", "archived", "library"),
    PageSpec(
        "project_detail",
        "Projeto",
        "Projeto",
        ":material/sports_esports:",
        "project",
        "detail",
    ),
    PageSpec("gdd_editor", "Editor", "Editor GDD", ":material/article:", "gdd", "detail"),
    PageSpec(
        "characters",
        "Personagens",
        "Personagens",
        ":material/groups:",
        "characters",
        "detail",
    ),
    PageSpec(
        "character_detail",
        "Personagem",
        "Ficha do personagem",
        ":material/person:",
        "character",
        "detail",
    ),
    PageSpec(
        "narrative",
        "Narrativa",
        "Estrutura narrativa",
        ":material/account_tree:",
        "narrative",
        "detail",
    ),
    PageSpec(
        "narrative_map",
        "Mapa Narrativo",
        "Mapa Narrativo",
        ":material/hub:",
        "narrative-map",
        "detail",
    ),
    PageSpec(
        "settings",
        "Configurações",
        "Configurações",
        ":material/settings:",
        "settings",
        "system",
        False,
    ),
)


def _renderers(
    health: DatabaseHealth,
    on_retry: Callable[[], None],
) -> dict[str, Callable[[], None]]:
    return {
        "home": partial(home.render, health),
        "projects": projects.render,
        "recent": recent.render,
        "favorites": favorites.render,
        "ideas": ideas.render,
        "archived": archived.render,
        "project_detail": project.render,
        "gdd_editor": editor.render,
        "characters": characters.render,
        "character_detail": character.render,
        "narrative": narrative.render,
        "narrative_map": narrative_map.render,
        "settings": partial(settings.render, health, on_retry),
    }


def page_renderers(
    health: DatabaseHealth,
    on_retry: Callable[[], None],
) -> dict[str, Callable[[], None]]:
    return _renderers(health, on_retry)


def current_page_spec() -> PageSpec:
    requested = st.query_params.get("view", "home")
    return next((spec for spec in PAGE_SPECS if spec.key == requested), PAGE_SPECS[0])


def _render_page_links(current_key: str, group: str) -> None:
    for spec in PAGE_SPECS:
        if spec.group == group and st.button(
            spec.label,
            key=f"nav-{spec.key}",
            icon=spec.icon,
            type="primary" if spec.key == current_key else "secondary",
            use_container_width=True,
        ):
            go_to_page(spec.key)


def render_sidebar(current_key: str) -> None:
    with st.sidebar:
        st.html(
            '<div class="gdd-brand">'
            '<div class="gdd-brand__mark" aria-hidden="true">G</div>'
            "<div>"
            '<div class="gdd-brand__name">GDD Studio</div>'
            '<div class="gdd-brand__tagline">Crie mundos com clareza</div>'
            "</div>"
            "</div>"
        )
        with st.container(key="primary-navigation"):
            st.html('<div class="gdd-nav-label">Workspace</div>')
            _render_page_links(current_key, "workspace")
            st.html('<div class="gdd-nav-label">Biblioteca</div>')
            _render_page_links(current_key, "library")

        st.write("")
        with st.container(key="secondary-navigation"):
            _render_page_links(current_key, "system")
        st.caption("GDD Studio · Base narrativa")
