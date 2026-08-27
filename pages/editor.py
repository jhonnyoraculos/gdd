"""Responsive Markdown GDD editor."""

from __future__ import annotations

import logging
from collections import defaultdict
from html import escape
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from config.settings import get_settings
from services.gdd_service import (
    GddConflictError,
    GddNotFoundError,
    GddServiceError,
    MoveDirection,
    SectionDocument,
    SectionInput,
    SectionNode,
    create_section,
    delete_section,
    get_section,
    initialize_complete_template,
    list_sections,
    move_section,
    update_section_content,
    update_section_metadata,
)
from services.project_service import ProjectNotFoundError, get_project
from services.user_service import OwnerIdentity, owner_from_settings
from utils.constants import SECTION_STATUSES
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)
_STATUS_LABELS = {item.value: item.label for item in SECTION_STATUSES}
_STATUS_VALUES = list(_STATUS_LABELS)
_TYPE_LABELS = {"page": "Página", "category": "Categoria", "group": "Grupo"}


def _uuid_param(name: str) -> UUID | None:
    raw = st.query_params.get(name)
    try:
        return UUID(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _flatten(nodes: tuple[SectionNode, ...]) -> tuple[tuple[SectionNode, int], ...]:
    children: dict[UUID | None, list[SectionNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)
    output: list[tuple[SectionNode, int]] = []

    def visit(parent_id: UUID | None, depth: int) -> None:
        for node in children[parent_id]:
            output.append((node, depth))
            visit(node.id, depth + 1)

    visit(None, 0)
    return tuple(output)


def _run(action: object, message: str, rerun: bool = True) -> bool:
    try:
        action()  # type: ignore[operator]
    except GddConflictError as exc:
        st.warning(str(exc))
        return False
    except (GddServiceError, SQLAlchemyError):
        incident = uuid4().hex[:8]
        LOGGER.exception("GDD action failed | incident=%s", incident)
        st.error(f"Não foi possível concluir a ação. Código: {incident}")
        return False
    set_flash(message)
    if rerun:
        st.rerun()
    return True


@st.dialog("Nova seção", icon=":material/add:")
def _new_section(owner: OwnerIdentity, project_id: UUID, nodes: tuple[SectionNode, ...]) -> None:
    parent_options: list[UUID | None] = [None, *(node.id for node in nodes)]
    names = {None: "Raiz do GDD", **{node.id: node.title for node in nodes}}
    with st.form("new-gdd-section", border=False):
        title = st.text_input("Título *", max_chars=180)
        icon = st.text_input("Ícone", max_chars=40, placeholder="Ex.: ✦")
        section_type = st.selectbox(
            "Tipo",
            ["page", "category", "group"],
            format_func=_TYPE_LABELS.get,
        )
        parent_id = st.selectbox("Dentro de", parent_options, format_func=names.get)
        submitted = st.form_submit_button("Criar seção", type="primary", use_container_width=True)
    if submitted:
        created: list[UUID] = []

        def action() -> None:
            created.append(
                create_section(
                    owner,
                    project_id,
                    SectionInput(title, icon, section_type, parent_id),
                )
            )

        if _run(action, "Seção criada.", rerun=False):
            go_to_page("gdd_editor", project=str(project_id), section=str(created[0]))


@st.dialog("Editar seção", icon=":material/edit:")
def _edit_section(owner: OwnerIdentity, project_id: UUID, section: SectionDocument) -> None:
    with st.form(f"edit-gdd-section-{section.id}", border=False):
        title = st.text_input("Título *", value=section.title, max_chars=180)
        icon = st.text_input("Ícone", value=section.icon or "", max_chars=40)
        types = ["page", "category", "group"]
        section_type = st.selectbox(
            "Tipo",
            types,
            index=types.index(section.section_type),
            format_func=_TYPE_LABELS.get,
        )
        submitted = st.form_submit_button("Salvar", type="primary", use_container_width=True)
    if submitted:
        _run(
            lambda: update_section_metadata(
                owner,
                project_id,
                section.id,
                SectionInput(title, icon, section_type, section.parent_id, section.status),
            ),
            "Seção atualizada.",
        )


@st.dialog("Excluir seção", icon=":material/delete:")
def _delete_section(owner: OwnerIdentity, project_id: UUID, section: SectionDocument) -> None:
    st.warning("Subseções dentro desta seção também serão excluídas.")
    confirmed = st.checkbox(f"Excluir “{section.title}” definitivamente")
    if st.button(
        "Excluir seção", type="primary", disabled=not confirmed, use_container_width=True
    ) and _run(
        lambda: delete_section(owner, project_id, section.id),
        "Seção excluída.",
        rerun=False,
    ):
        go_to_page("gdd_editor", project=str(project_id))


def _outline(
    owner: OwnerIdentity,
    project_id: UUID,
    nodes: tuple[SectionNode, ...],
    selected_id: UUID,
) -> None:
    flat = _flatten(nodes)
    node_by_id = {node.id: node for node, _ in flat}
    labels = {node.id: f"{'↳ ' * depth}{node.icon or '·'} {node.title}" for node, depth in flat}
    selected_index = next((i for i, (node, _) in enumerate(flat) if node.id == selected_id), 0)
    selected = st.selectbox(
        "Estrutura do GDD",
        [node.id for node, _ in flat],
        index=selected_index,
        format_func=labels.get,
        key=f"gdd-outline-{project_id}",
    )
    if selected != selected_id:
        go_to_page("gdd_editor", project=str(project_id), section=str(selected))
    st.caption(f"{len(nodes)} seções")
    if st.button("Nova seção", icon=":material/add:", use_container_width=True):
        _new_section(owner, project_id, nodes)
    up, down = st.columns(2)
    with up:
        if st.button("Subir", icon=":material/arrow_upward:", use_container_width=True):
            _run(
                lambda: move_section(owner, project_id, selected_id, MoveDirection.UP),
                "Ordem atualizada.",
            )
    with down:
        if st.button("Descer", icon=":material/arrow_downward:", use_container_width=True):
            _run(
                lambda: move_section(owner, project_id, selected_id, MoveDirection.DOWN),
                "Ordem atualizada.",
            )
    node = node_by_id[selected_id]
    st.html(
        '<div class="gdd-outline-current">'
        f"<strong>{escape(node.icon or '·')} {escape(node.title)}</strong>"
        f"<span>{escape(_STATUS_LABELS[node.status])}</span></div>"
    )


def _save_pending(owner: OwnerIdentity, project_id: UUID, section: SectionDocument) -> None:
    key = f"gdd-content-{section.id}-{section.revision}"
    pending = st.session_state.get(key)
    if pending is None or pending == section.content:
        return
    if _run(
        lambda: update_section_content(owner, project_id, section.id, pending, section.revision),
        "Seção salva automaticamente.",
        rerun=False,
    ):
        st.rerun()


def _document_editor(owner: OwnerIdentity, project_id: UUID, section: SectionDocument) -> None:
    _save_pending(owner, project_id, section)
    title_col, status_col = st.columns([1, 0.42], vertical_alignment="bottom")
    with title_col:
        st.html(
            '<div class="gdd-editor-title">'
            f"<span>{escape(section.icon or '§')}</span>"
            f"<div><small>{escape(_TYPE_LABELS[section.section_type])}</small>"
            f"<h1>{escape(section.title)}</h1></div></div>"
        )
    with status_col:
        status = st.selectbox(
            "Status",
            _STATUS_VALUES,
            index=_STATUS_VALUES.index(section.status),
            format_func=_STATUS_LABELS.get,
            key=f"gdd-status-{section.id}-{section.revision}",
        )
    if status != section.status:
        _run(
            lambda: update_section_metadata(
                owner,
                project_id,
                section.id,
                SectionInput(
                    section.title,
                    section.icon,
                    section.section_type,
                    section.parent_id,
                    status,
                ),
            ),
            "Status atualizado.",
        )

    mode_col, action_col = st.columns([1, 0.5], vertical_alignment="center")
    with mode_col:
        mode = st.segmented_control(
            "Modo",
            ["Editar", "Visualizar"],
            default="Editar",
            label_visibility="collapsed",
            key=f"gdd-mode-{section.id}",
        )
    with action_col, st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("", icon=":material/edit:", help="Editar título e ícone"):
            _edit_section(owner, project_id, section)
        if st.button("", icon=":material/delete:", help="Excluir seção"):
            _delete_section(owner, project_id, section)

    if mode == "Visualizar":
        with st.container(key="gdd-preview", border=False):
            if section.content.strip():
                st.markdown(section.content)
            else:
                st.caption("Esta seção ainda está vazia.")
        return

    content_key = f"gdd-content-{section.id}-{section.revision}"
    st.caption("Salvo ✓ · autosave ao pausar a edição ou sair do campo")
    content = st.text_area(
        "Conteúdo Markdown",
        value=section.content,
        height=560,
        key=content_key,
        placeholder=(
            "# Comece a escrever\n\nUse Markdown para títulos, listas, checklists e tabelas."
        ),
        label_visibility="collapsed",
    )
    if content != section.content:
        _save_pending(owner, project_id, section)
    if st.button("Salvar agora", icon=":material/save:", type="primary"):
        _save_pending(owner, project_id, section)


def _empty_gdd(owner: OwnerIdentity, project_id: UUID) -> None:
    st.html(
        '<section class="gdd-empty-state"><div class="gdd-empty-state__icon">§</div>'
        "<h1>Seu GDD começa aqui</h1>"
        "<p>Crie uma estrutura completa ou comece com uma seção em branco.</p></section>"
    )
    complete, blank = st.columns(2)
    with complete:
        if st.button("Criar GDD completo", type="primary", use_container_width=True):
            _run(
                lambda: initialize_complete_template(owner, project_id),
                "Estrutura completa criada.",
            )
    with blank:
        if st.button("Começar vazio", use_container_width=True):
            _new_section(owner, project_id, ())


def render() -> None:
    project_id = _uuid_param("project")
    if project_id is None:
        st.error("Projeto não identificado.")
        return
    owner = owner_from_settings(get_settings())
    try:
        project = get_project(owner, project_id)
        nodes = list_sections(owner, project_id)
    except (ProjectNotFoundError, GddNotFoundError):
        st.error("Projeto não encontrado.")
        return
    except SQLAlchemyError:
        st.error("Não foi possível carregar o GDD agora.")
        return

    top_left, top_right = st.columns([1, 0.4], vertical_alignment="center")
    with top_left:
        if st.button(project.name, icon=":material/arrow_back:"):
            go_to_page("project_detail", id=str(project.id))
    with top_right:
        st.progress(project.progress / 100, text=f"GDD {project.progress}%")
    if not nodes:
        _empty_gdd(owner, project_id)
        return

    flat = _flatten(nodes)
    requested = _uuid_param("section")
    selected_id = requested if requested in {node.id for node, _ in flat} else flat[0][0].id
    try:
        document = get_section(owner, project_id, selected_id)
    except (GddNotFoundError, SQLAlchemyError):
        st.error("Não foi possível abrir esta seção.")
        return
    outline, editor = st.columns([0.3, 0.7], gap="large")
    with outline, st.container(key="gdd-outline", border=False):
        _outline(owner, project_id, nodes, selected_id)
    with editor, st.container(key="gdd-document", border=False):
        _document_editor(owner, project_id, document)
