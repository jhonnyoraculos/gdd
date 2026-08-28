"""Structured chapters and scenes route."""

from __future__ import annotations

import logging
from html import escape
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.appearance_forms import (
    show_edit_appearance_dialog,
    show_manage_scene_cast_dialog,
)
from components.cards import render_empty_state
from components.feedback import set_flash
from components.narrative_forms import (
    show_create_chapter_dialog,
    show_create_scene_dialog,
    show_edit_chapter_dialog,
    show_edit_scene_dialog,
)
from config.settings import get_settings
from services.appearance_service import (
    AppearanceServiceError,
    ProjectAppearanceIndex,
    get_project_appearance_index,
)
from services.narrative_service import (
    ChapterDetails,
    NarrativeDirection,
    NarrativeNotFoundError,
    NarrativeServiceError,
    SceneDetails,
    delete_chapter,
    delete_scene,
    list_narrative,
    move_chapter,
    move_scene,
)
from services.project_service import ProjectNotFoundError, get_project
from services.user_service import OwnerIdentity, owner_from_settings
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


def _project_id() -> UUID | None:
    raw = st.query_params.get("project")
    try:
        return UUID(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _action(action: object, success: str) -> None:
    try:
        changed = action()  # type: ignore[operator]
    except (NarrativeServiceError, SQLAlchemyError):
        incident = uuid4().hex[:8]
        LOGGER.exception("Narrative action failed | incident=%s", incident)
        st.error(f"Não foi possível concluir a ação. Código: {incident}")
        return
    if changed is False:
        return
    set_flash(success)
    st.rerun()


@st.dialog("Excluir capítulo", icon=":material/delete_forever:")
def _confirm_chapter_delete(owner: OwnerIdentity, chapter: ChapterDetails) -> None:
    count = len(chapter.scenes)
    st.warning(
        f"Excluir {chapter.title}? {count} cena{'s' if count != 1 else ''} "
        "também será removida permanentemente."
    )
    confirmation = st.text_input(f'Digite "{chapter.title}" para confirmar')
    if st.button(
        "Excluir capítulo",
        type="primary",
        disabled=confirmation != chapter.title,
        use_container_width=True,
    ):
        _action(
            lambda: delete_chapter(owner, chapter.project_id, chapter.id),
            "Capítulo excluído.",
        )


@st.dialog("Excluir cena", icon=":material/delete_forever:")
def _confirm_scene_delete(owner: OwnerIdentity, scene: SceneDetails) -> None:
    st.warning(f"Excluir a cena {scene.title}? Esta ação é permanente.")
    if st.button("Excluir cena", type="primary", use_container_width=True):
        _action(
            lambda: delete_scene(owner, scene.project_id, scene.id),
            "Cena excluída.",
        )


def _scene_card(
    owner: OwnerIdentity,
    scene: SceneDetails,
    chapters: tuple[ChapterDetails, ...],
    index: int,
    total: int,
    appearance_index: ProjectAppearanceIndex,
) -> None:
    with st.container(key=f"narrative-scene-{scene.id}", border=False):
        info, actions = st.columns([1, 0.52], vertical_alignment="center")
        with info:
            st.html(
                '<div class="gdd-scene-heading">'
                f"<span>Cena {index + 1} · Ordem {scene.timeline_order // 1000}</span>"
                f"<h3>{escape(scene.title)}</h3>"
                "</div>"
            )
        with actions, st.container(horizontal=True, horizontal_alignment="right"):
            if st.button(
                "",
                key=f"scene-up-{scene.id}",
                icon=":material/arrow_upward:",
                help="Mover cena para cima",
                disabled=index == 0,
            ):
                _action(
                    lambda: move_scene(owner, scene.project_id, scene.id, NarrativeDirection.UP),
                    "Ordem atualizada.",
                )
            if st.button(
                "",
                key=f"scene-down-{scene.id}",
                icon=":material/arrow_downward:",
                help="Mover cena para baixo",
                disabled=index == total - 1,
            ):
                _action(
                    lambda: move_scene(owner, scene.project_id, scene.id, NarrativeDirection.DOWN),
                    "Ordem atualizada.",
                )
            if st.button("", key=f"scene-edit-{scene.id}", icon=":material/edit:", help="Editar"):
                show_edit_scene_dialog(owner, scene, chapters)
            if st.button(
                "", key=f"scene-delete-{scene.id}", icon=":material/delete:", help="Excluir"
            ):
                _confirm_scene_delete(owner, scene)
        if scene.summary:
            st.caption(scene.summary)
        if scene.content:
            with st.expander("Ver conteúdo da cena"):
                st.markdown(scene.content)
        cast = appearance_index.cast_for(scene.id)
        with st.expander(f"Personagens da cena ({len(cast)})", expanded=bool(cast)):
            if not cast:
                st.caption("Nenhum personagem vinculado.")
            for member in cast:
                name_col, details_col = st.columns([1, 0.18], vertical_alignment="center")
                with name_col:
                    label = member.role_in_scene or member.role or "Papel a definir"
                    if st.button(
                        f"{member.name} · {label}",
                        key=f"open-cast-character-{scene.id}-{member.character_id}",
                        icon=":material/person:",
                        use_container_width=True,
                    ):
                        go_to_page(
                            "character_detail",
                            project=str(scene.project_id),
                            id=str(member.character_id),
                        )
                with details_col:
                    if st.button(
                        "",
                        key=f"edit-appearance-{scene.id}-{member.character_id}",
                        icon=":material/edit:",
                        help="Editar papel e notas desta participação",
                        use_container_width=True,
                    ):
                        show_edit_appearance_dialog(owner, scene, member)
            if st.button(
                "Gerenciar personagens",
                key=f"manage-scene-cast-{scene.id}",
                icon=":material/group_add:",
                type="primary",
                use_container_width=True,
            ):
                show_manage_scene_cast_dialog(owner, scene, appearance_index)


def _chapter_card(
    owner: OwnerIdentity,
    chapter: ChapterDetails,
    chapters: tuple[ChapterDetails, ...],
    index: int,
    appearance_index: ProjectAppearanceIndex,
) -> None:
    with st.container(key=f"narrative-chapter-{chapter.id}", border=False):
        info, actions = st.columns([1, 0.58], vertical_alignment="center")
        with info:
            st.html(
                '<div class="gdd-chapter-heading">'
                f"<span>Capítulo {index + 1}</span>"
                f"<h2>{escape(chapter.title)}</h2>"
                f"<p>{escape(chapter.summary or 'Resumo a definir.')}</p>"
                "</div>"
            )
        with actions, st.container(horizontal=True, horizontal_alignment="right"):
            if st.button(
                "",
                key=f"chapter-up-{chapter.id}",
                icon=":material/arrow_upward:",
                help="Mover capítulo para cima",
                disabled=index == 0,
            ):
                _action(
                    lambda: move_chapter(
                        owner, chapter.project_id, chapter.id, NarrativeDirection.UP
                    ),
                    "Ordem atualizada.",
                )
            if st.button(
                "",
                key=f"chapter-down-{chapter.id}",
                icon=":material/arrow_downward:",
                help="Mover capítulo para baixo",
                disabled=index == len(chapters) - 1,
            ):
                _action(
                    lambda: move_chapter(
                        owner, chapter.project_id, chapter.id, NarrativeDirection.DOWN
                    ),
                    "Ordem atualizada.",
                )
            if st.button(
                "", key=f"chapter-edit-{chapter.id}", icon=":material/edit:", help="Editar"
            ):
                show_edit_chapter_dialog(owner, chapter)
            if st.button(
                "", key=f"chapter-delete-{chapter.id}", icon=":material/delete:", help="Excluir"
            ):
                _confirm_chapter_delete(owner, chapter)
        if st.button(
            "Nova cena",
            key=f"new-scene-{chapter.id}",
            icon=":material/add:",
            use_container_width=True,
        ):
            show_create_scene_dialog(owner, chapter.project_id, chapters, chapter.id)
        if not chapter.scenes:
            st.caption("Nenhuma cena neste capítulo.")
        for scene_index, scene in enumerate(chapter.scenes):
            _scene_card(
                owner,
                scene,
                chapters,
                scene_index,
                len(chapter.scenes),
                appearance_index,
            )


def render() -> None:
    project_id = _project_id()
    if project_id is None:
        render_empty_state("?", "Projeto não identificado", "Abra a narrativa por um projeto.")
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return

    owner = owner_from_settings(get_settings())
    try:
        project = get_project(owner, project_id)
        chapters = list_narrative(owner, project_id)
        appearance_index = get_project_appearance_index(owner, project_id)
    except (ProjectNotFoundError, NarrativeNotFoundError, AppearanceServiceError):
        render_empty_state("?", "Projeto não encontrado", "Este projeto não está disponível.")
        return
    except SQLAlchemyError:
        incident = uuid4().hex[:8]
        LOGGER.exception("Narrative load failed | incident=%s", incident)
        st.error(f"Não foi possível carregar a narrativa. Código: {incident}")
        return

    if st.button(project.name, icon=":material/arrow_back:"):
        go_to_page("project_detail", id=str(project_id))
    intro, action = st.columns([1, 0.32], vertical_alignment="bottom")
    with intro:
        st.html(
            '<section class="gdd-page-intro">'
            '<div class="gdd-page-intro__eyebrow">Estrutura narrativa</div>'
            "<h1>Capítulos e cenas</h1>"
            f"<p>Organize a progressão narrativa de {escape(project.name)}.</p>"
            "</section>"
        )
    with action:
        if st.button(
            "Novo capítulo",
            icon=":material/book_2:",
            type="primary",
            use_container_width=True,
        ):
            show_create_chapter_dialog(owner, project_id)
        if st.button(
            "Mapa Narrativo",
            icon=":material/hub:",
            use_container_width=True,
        ):
            go_to_page("narrative_map", project=str(project_id))

    scene_count = sum(len(chapter.scenes) for chapter in chapters)
    st.caption(
        f"{len(chapters)} capítulo{'s' if len(chapters) != 1 else ''} · "
        f"{scene_count} cena{'s' if scene_count != 1 else ''}"
    )
    if not chapters:
        render_empty_state(
            "§",
            "A história ainda não tem capítulos",
            "Crie o primeiro capítulo para começar a organizar suas cenas.",
        )
        return
    for index, chapter in enumerate(chapters):
        _chapter_card(owner, chapter, chapters, index, appearance_index)
