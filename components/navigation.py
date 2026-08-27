"""Official Streamlit routing plus custom sidebar content."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

import streamlit as st

from pages import archived, editor, favorites, home, ideas, project, projects, recent, settings
from services.database import DatabaseHealth
from utils.navigation_state import register_navigation_pages


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


@dataclass(frozen=True, slots=True)
class NavigationEntry:
    spec: PageSpec
    page: Any


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
        "settings": partial(settings.render, health, on_retry),
    }


def build_navigation(
    health: DatabaseHealth,
    on_retry: Callable[[], None],
) -> tuple[NavigationEntry, ...]:
    renderers = _renderers(health, on_retry)
    entries = tuple(
        NavigationEntry(
            spec=spec,
            page=st.Page(
                renderers[spec.key],
                title=spec.title,
                icon=spec.icon,
                url_path=spec.url_path,
                default=spec.default,
            ),
        )
        for spec in PAGE_SPECS
    )
    register_navigation_pages({entry.spec.key: entry.page for entry in entries})
    return entries


def get_entry_for_page(
    entries: tuple[NavigationEntry, ...],
    current_page: Any,
) -> NavigationEntry:
    for entry in entries:
        if entry.page.url_path == current_page.url_path:
            return entry
    return entries[0]


def _render_page_links(entries: tuple[NavigationEntry, ...], group: str) -> None:
    for entry in entries:
        if entry.spec.group == group:
            st.page_link(
                entry.page,
                label=entry.spec.label,
                icon=entry.spec.icon,
                use_container_width=True,
            )


def render_sidebar(entries: tuple[NavigationEntry, ...]) -> None:
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
            _render_page_links(entries, "workspace")
            st.html('<div class="gdd-nav-label">Biblioteca</div>')
            _render_page_links(entries, "library")

        st.write("")
        with st.container(key="secondary-navigation"):
            _render_page_links(entries, "system")
        st.caption("Editor GDD · Etapa 3")
