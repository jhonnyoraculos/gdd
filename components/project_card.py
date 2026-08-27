"""Interactive project card backed by persistent commands."""

from __future__ import annotations

import logging
from html import escape
from uuid import uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from services.project_service import (
    ProjectServiceError,
    ProjectSummary,
    set_project_archived,
    toggle_project_favorite,
)
from services.user_service import OwnerIdentity
from utils.formatting import project_status_label, relative_datetime
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


def _cover_markup(project: ProjectSummary) -> str:
    if project.cover_url:
        return (
            '<img class="gdd-project-card__cover-image" '
            f'src="{escape(project.cover_url, quote=True)}" '
            f'alt="Capa de {escape(project.name, quote=True)}" loading="lazy">'
        )
    initial = escape(project.name[:1].upper() or "G")
    return (
        '<div class="gdd-project-card__cover-fallback" '
        f'style="--project-accent:{escape(project.accent_color, quote=True)}">'
        f"<span>{initial}</span></div>"
    )


def _safe_action(action: object, success: str) -> bool:
    try:
        action()  # type: ignore[operator]
    except (ProjectServiceError, SQLAlchemyError):
        incident = uuid4().hex[:8]
        LOGGER.exception("Project card action failed | incident=%s", incident)
        st.error(f"Não foi possível concluir a ação. Código: {incident}")
        return False
    set_flash(success)
    st.rerun()
    return True


def render_project_card(project: ProjectSummary, owner: OwnerIdentity) -> None:
    metadata = " · ".join(part for part in (project.genre, project.platform) if part)
    metadata = metadata or "Detalhes a definir"
    favorite_icon = ":material/star:" if project.favorite else ":material/star_outline:"
    favorite_help = "Remover dos favoritos" if project.favorite else "Adicionar aos favoritos"
    with st.container(key=f"project-card-{project.id}", border=False):
        status_label = escape(project_status_label(project.status))
        st.html(
            '<article class="gdd-project-card__visual">'
            f'<div class="gdd-project-card__cover">{_cover_markup(project)}</div>'
            '<div class="gdd-project-card__content">'
            '<div class="gdd-project-card__status-row">'
            f'<span class="gdd-project-status">{status_label}</span>'
            f"<span>{escape(relative_datetime(project.updated_at))}</span>"
            "</div>"
            f"<h3>{escape(project.name)}</h3>"
            f"<p>{escape(metadata)}</p>"
            '<div class="gdd-project-card__progress-label">'
            f"<span>Progresso do GDD</span><strong>{project.progress}%</strong>"
            "</div>"
            '<div class="gdd-project-card__progress" role="progressbar" '
            f'aria-valuenow="{project.progress}" aria-valuemin="0" aria-valuemax="100">'
            f'<span style="width:{project.progress}%;--project-accent:'
            f'{escape(project.accent_color, quote=True)}"></span></div>'
            "</div></article>"
        )
        open_col, favorite_col, archive_col = st.columns([1, 0.22, 0.22], gap="small")
        with open_col:
            if st.button(
                "Abrir projeto",
                key=f"open-project-{project.id}",
                type="primary",
                icon=":material/arrow_forward:",
                use_container_width=True,
            ):
                go_to_page("project_detail", id=str(project.id))
        with favorite_col:
            if st.button(
                "",
                key=f"favorite-project-{project.id}",
                icon=favorite_icon,
                help=favorite_help,
                use_container_width=True,
            ):
                _safe_action(
                    lambda: toggle_project_favorite(owner, project.id),
                    "Favoritos atualizados.",
                )
        with archive_col:
            archive_icon = ":material/unarchive:" if project.archived else ":material/archive:"
            archive_help = "Restaurar projeto" if project.archived else "Arquivar projeto"
            if st.button(
                "",
                key=f"archive-project-{project.id}",
                icon=archive_icon,
                help=archive_help,
                use_container_width=True,
            ):
                verb = "restaurado" if project.archived else "arquivado"
                _safe_action(
                    lambda: set_project_archived(owner, project.id, not project.archived),
                    f"Projeto {verb}.",
                )
