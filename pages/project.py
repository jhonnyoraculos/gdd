"""Individual project dashboard route."""

from __future__ import annotations

import logging
from html import escape
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.cards import InfoCard, render_card_grid, render_empty_state
from components.feedback import set_flash
from components.project_form import show_edit_project_dialog
from config.settings import get_settings
from services.project_service import (
    ProjectDetails,
    ProjectNotFoundError,
    delete_project,
    get_project,
    set_project_archived,
    toggle_project_favorite,
)
from services.user_service import OwnerIdentity, owner_from_settings
from utils.formatting import project_status_label, relative_datetime
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


def _project_id() -> UUID | None:
    raw_value = st.query_params.get("id")
    try:
        return UUID(raw_value) if raw_value else None
    except (TypeError, ValueError):
        return None


def _cover(project: ProjectDetails) -> str:
    if project.cover_url:
        return (
            '<img class="gdd-project-hero__image" '
            f'src="{escape(project.cover_url, quote=True)}" '
            f'alt="Capa de {escape(project.name, quote=True)}">'
        )
    return (
        '<div class="gdd-project-hero__fallback" '
        f'style="--project-accent:{escape(project.accent_color, quote=True)}">'
        f"<span>{escape(project.name[:1].upper())}</span></div>"
    )


def _hero(project: ProjectDetails) -> None:
    metadata = " · ".join(
        part for part in (project.genre, project.subgenre, project.platform, project.engine) if part
    )
    description = escape(project.description or "Sem descrição ainda.")
    st.html(
        '<section class="gdd-project-hero">'
        f'<div class="gdd-project-hero__cover">{_cover(project)}</div>'
        '<div class="gdd-project-hero__content">'
        f'<span class="gdd-project-status">{escape(project_status_label(project.status))}</span>'
        f"<h1>{escape(project.name)}</h1>"
        f'<p class="gdd-project-hero__meta">{escape(metadata or "Detalhes a definir")}</p>'
        f'<p class="gdd-project-hero__description">{description}</p>'
        "</div></section>"
    )


def _run_action(action: object, message: str, destination: str | None = None) -> None:
    try:
        action()  # type: ignore[operator]
    except (ProjectNotFoundError, SQLAlchemyError):
        incident = uuid4().hex[:8]
        LOGGER.exception("Project detail action failed | incident=%s", incident)
        st.error(f"Não foi possível concluir a ação. Código: {incident}")
        return
    set_flash(message)
    if destination:
        go_to_page(destination)
    st.rerun()


@st.dialog("Excluir projeto", icon=":material/delete_forever:")
def _confirm_delete(owner: OwnerIdentity, project: ProjectDetails) -> None:
    st.warning("Esta ação é permanente e também remove os dados vinculados ao projeto.")
    confirmation = st.text_input(
        f'Digite "{project.name}" para confirmar',
        key=f"delete-confirmation-{project.id}",
    )
    if st.button(
        "Excluir definitivamente",
        type="primary",
        disabled=confirmation != project.name,
        use_container_width=True,
    ):
        _run_action(
            lambda: delete_project(owner, project.id),
            "Projeto excluído permanentemente.",
            "projects",
        )


def _toolbar(owner: OwnerIdentity, project: ProjectDetails) -> None:
    back, actions = st.columns([1, 1], vertical_alignment="center")
    with back:
        if st.button("Projetos", icon=":material/arrow_back:"):
            go_to_page("projects")
    with (
        actions,
        st.container(
            key="project-toolbar-actions",
            horizontal=True,
            horizontal_alignment="right",
            wrap=False,
            gap="small",
        ),
    ):
        if st.button(
            "",
            icon=":material/star:" if project.favorite else ":material/star_outline:",
            help="Remover dos favoritos" if project.favorite else "Adicionar aos favoritos",
        ):
            _run_action(
                lambda: toggle_project_favorite(owner, project.id),
                "Favoritos atualizados.",
            )
        if st.button(
            "",
            icon=":material/unarchive:" if project.archived else ":material/archive:",
            help="Restaurar projeto" if project.archived else "Arquivar projeto",
        ):
            _run_action(
                lambda: set_project_archived(owner, project.id, not project.archived),
                "Projeto restaurado." if project.archived else "Projeto arquivado.",
            )
        if st.button("", icon=":material/edit:", help="Editar projeto"):
            show_edit_project_dialog(owner, project)
        if st.button("", icon=":material/delete:", help="Excluir projeto"):
            _confirm_delete(owner, project)


def _actions(project_id: UUID) -> None:
    st.html(
        '<div class="gdd-section-heading"><h2>Workspace do projeto</h2>'
        "<p>Abra o documento do jogo ou desenvolva seu elenco narrativo.</p></div>"
    )
    gdd_col, characters_col = st.columns(2)
    with gdd_col:
        if st.button(
            "Abrir GDD",
            icon=":material/article:",
            type="primary",
            use_container_width=True,
        ):
            go_to_page("gdd_editor", project=str(project_id))
    with characters_col:
        if st.button(
            "Personagens",
            icon=":material/groups:",
            type="primary",
            use_container_width=True,
        ):
            go_to_page("characters", project=str(project_id))
    labels = (
        ("Nova nota", ":material/note_add:", "Disponível na Etapa 5"),
        ("Referências", ":material/collections_bookmark:", "Disponível na Etapa 6"),
        ("Histórico", ":material/history:", "Disponível na Etapa 7"),
    )
    columns = st.columns(3)
    for column, (label, icon, help_text) in zip(columns, labels, strict=True):
        with column:
            st.button(
                label,
                icon=icon,
                disabled=True,
                help=help_text,
                use_container_width=True,
            )


def render() -> None:
    project_id = _project_id()
    if project_id is None:
        render_empty_state("?", "Projeto não identificado", "Volte à biblioteca e abra um projeto.")
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return
    owner = owner_from_settings(get_settings())
    try:
        project = get_project(owner, project_id)
    except ProjectNotFoundError:
        render_empty_state(
            "?",
            "Projeto não encontrado",
            "Ele pode ter sido removido ou não pertence a este workspace.",
        )
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return
    except SQLAlchemyError:
        incident = uuid4().hex[:8]
        LOGGER.exception("Project detail load failed | incident=%s", incident)
        st.error(f"Não foi possível carregar o projeto agora. Código: {incident}")
        return

    _toolbar(owner, project)
    _hero(project)
    render_card_grid(
        (
            InfoCard(
                "◔", "GDD", f"{project.progress}%", "Progresso calculado pelas seções finalizadas."
            ),
            InfoCard(
                "§",
                "Seções",
                str(project.section_count),
                f"{project.finished_section_count} finalizadas",
            ),
            InfoCard("✎", "Notas", str(project.note_count), "Notas vinculadas a este projeto."),
            InfoCard(
                "♙",
                "Personagens",
                str(project.character_count),
                "Fichas do elenco deste jogo.",
            ),
            InfoCard(
                "◇", "Referências", str(project.reference_count), "Itens da biblioteca do projeto."
            ),
            InfoCard(
                "◷",
                "Última edição",
                relative_datetime(project.updated_at),
                "Alteração mais recente registrada.",
            ),
        )
    )
    _actions(project.id)
