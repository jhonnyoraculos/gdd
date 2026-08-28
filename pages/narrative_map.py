"""Full-page visual editor for the connected GDD and narrative."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from html import escape
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.cards import render_empty_state
from components.character_form import (
    show_create_character_dialog,
    show_edit_character_dialog,
)
from components.narrative_forms import (
    show_create_chapter_dialog,
    show_create_scene_dialog,
    show_edit_chapter_dialog,
    show_edit_scene_dialog,
)
from components.narrative_map import render_narrative_map
from components.narrative_map_editor import (
    show_create_map_link_dialog,
    show_create_map_section_dialog,
    show_delete_map_edge_dialog,
    show_delete_map_node_dialog,
    show_edit_map_section_dialog,
)
from config.settings import get_settings
from services.character_service import CharacterServiceError, get_character
from services.gdd_service import GddServiceError, get_section, list_sections
from services.narrative_map_service import (
    MapNodeType,
    NarrativeMapGraph,
    NarrativeMapNotFoundError,
    get_narrative_map,
)
from services.narrative_service import (
    ChapterDetails,
    NarrativeServiceError,
    SceneDetails,
    list_narrative,
)
from services.user_service import OwnerIdentity, owner_from_settings
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


def _project_id() -> UUID | None:
    raw = st.query_params.get("project")
    try:
        return UUID(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _find_narrative(
    chapters: tuple[ChapterDetails, ...],
    node_type: MapNodeType,
    entity_id: UUID,
) -> ChapterDetails | SceneDetails | None:
    if node_type is MapNodeType.CHAPTER:
        return next((chapter for chapter in chapters if chapter.id == entity_id), None)
    if node_type is MapNodeType.SCENE:
        return next(
            (scene for chapter in chapters for scene in chapter.scenes if scene.id == entity_id),
            None,
        )
    return None


def _toolbar(
    owner: OwnerIdentity,
    project_id: UUID,
    graph: NarrativeMapGraph,
    chapters: tuple[ChapterDetails, ...],
) -> None:
    sections = list_sections(owner, project_id)
    buttons = st.columns([1, 1, 1, 1, 1.05, 1], gap="small")
    with buttons[0]:
        if st.button(
            "Capítulo",
            icon=":material/book_2:",
            use_container_width=True,
            key="map-new-chapter",
        ):
            show_create_chapter_dialog(owner, project_id)
    with buttons[1]:
        if st.button(
            "Cena",
            icon=":material/movie:",
            use_container_width=True,
            disabled=not chapters,
            help="Crie um capítulo primeiro." if not chapters else None,
            key="map-new-scene",
        ):
            show_create_scene_dialog(owner, project_id, chapters, chapters[0].id)
    with buttons[2]:
        if st.button(
            "Personagem",
            icon=":material/person_add:",
            use_container_width=True,
            key="map-new-character",
        ):
            show_create_character_dialog(owner, project_id, stay_on_page=True)
    with buttons[3]:
        if st.button(
            "Seção GDD",
            icon=":material/note_add:",
            use_container_width=True,
            key="map-new-section",
        ):
            show_create_map_section_dialog(owner, project_id, sections)
    with buttons[4]:
        if st.button(
            "Criar ligação",
            icon=":material/add_link:",
            type="primary",
            use_container_width=True,
            disabled=sum(node.node_type is not MapNodeType.PROJECT for node in graph.nodes) < 2,
            key="map-new-link",
        ):
            show_create_map_link_dialog(owner, graph)
    with buttons[5]:
        if st.button(
            "Narrativa",
            icon=":material/account_tree:",
            use_container_width=True,
            key="map-open-narrative",
        ):
            go_to_page("narrative", project=str(project_id))


def _handle_component_action(
    owner: OwnerIdentity,
    project_id: UUID,
    graph: NarrativeMapGraph,
    chapters: tuple[ChapterDetails, ...],
    action: object,
) -> None:
    if not isinstance(action, Mapping):
        return
    kind = action.get("kind")
    node_key = action.get("nodeId")
    edge_key = action.get("edgeId")
    node_by_key = {node.key: node for node in graph.nodes}
    node = node_by_key.get(node_key) if isinstance(node_key, str) else None

    if kind == "create_edge" and node is not None:
        show_create_map_link_dialog(owner, graph, node.key)
        return
    if kind == "delete_edge" and isinstance(edge_key, str):
        edge = next((item for item in graph.edges if item.key == edge_key), None)
        if edge is not None and edge.removable:
            show_delete_map_edge_dialog(owner, graph, edge)
        return
    if node is None or node.node_type is MapNodeType.PROJECT:
        return

    narrative_item = _find_narrative(chapters, node.node_type, node.entity_id)
    if kind == "edit_node":
        if isinstance(narrative_item, ChapterDetails):
            show_edit_chapter_dialog(owner, narrative_item)
        elif isinstance(narrative_item, SceneDetails):
            show_edit_scene_dialog(owner, narrative_item, chapters)
        elif node.node_type is MapNodeType.CHARACTER:
            show_edit_character_dialog(owner, get_character(owner, project_id, node.entity_id))
        elif node.node_type is MapNodeType.SECTION:
            show_edit_map_section_dialog(
                owner,
                project_id,
                get_section(owner, project_id, node.entity_id),
            )
        return

    if kind == "delete_node":
        show_delete_map_node_dialog(
            owner,
            project_id,
            node,
            chapter=narrative_item if isinstance(narrative_item, ChapterDetails) else None,
            scene=narrative_item if isinstance(narrative_item, SceneDetails) else None,
            section=(
                get_section(owner, project_id, node.entity_id)
                if node.node_type is MapNodeType.SECTION
                else None
            ),
        )


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
        chapters = list_narrative(owner, project_id)
    except NarrativeMapNotFoundError:
        render_empty_state(
            "?",
            "Mapa não encontrado",
            "O projeto pode ter sido removido ou não pertence a este workspace.",
        )
        return
    except (CharacterServiceError, GddServiceError, NarrativeServiceError, SQLAlchemyError):
        incident = uuid4().hex[:8]
        LOGGER.exception("Narrative map load failed | incident=%s", incident)
        st.error(f"Não foi possível carregar o mapa narrativo. Código: {incident}")
        return

    st.html(
        "<style>"
        ".stMainBlockContainer{max-width:100%!important;padding:1rem .8rem 2rem!important;}"
        "[data-testid='stMainBlockContainer']>div{gap:.7rem;}"
        "</style>"
    )
    heading, back = st.columns([5, 1], vertical_alignment="center")
    with heading:
        st.html(
            '<div class="gdd-page-intro gdd-map-compact">'
            "<span>Editor visual conectado</span>"
            f"<h1>Mapa Narrativo · {escape(graph.project_name)}</h1>"
            "<p>Crie, edite e conecte todo o projeto diretamente pelos cards.</p>"
            "</div>"
        )
    with back:
        if st.button(
            "Projeto",
            icon=":material/arrow_back:",
            use_container_width=True,
        ):
            go_to_page("project_detail", id=str(project_id))

    try:
        _toolbar(owner, project_id, graph, chapters)
    except (GddServiceError, SQLAlchemyError):
        incident = uuid4().hex[:8]
        LOGGER.exception("Narrative map toolbar failed | incident=%s", incident)
        st.error(f"Não foi possível abrir as ferramentas. Código: {incident}")

    result = render_narrative_map(graph, st.context.theme.type)
    try:
        _handle_component_action(
            owner,
            project_id,
            graph,
            chapters,
            result.get("action"),
        )
    except (
        CharacterServiceError,
        GddServiceError,
        NarrativeServiceError,
        SQLAlchemyError,
    ):
        incident = uuid4().hex[:8]
        LOGGER.exception("Narrative map action failed | incident=%s", incident)
        st.error(f"Não foi possível abrir esta ação. Código: {incident}")
