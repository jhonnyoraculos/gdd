"""Chapter and scene dialogs for the structured narrative."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from services.narrative_service import (
    ChapterDetails,
    ChapterInput,
    NarrativeServiceError,
    SceneDetails,
    SceneInput,
    create_chapter,
    create_scene,
    update_chapter,
    update_scene,
)
from services.user_service import OwnerIdentity

LOGGER = logging.getLogger(__name__)


def _error(exc: Exception) -> None:
    if isinstance(exc, NarrativeServiceError):
        st.error(str(exc))
        return
    incident = uuid4().hex[:8]
    LOGGER.exception("Narrative write failed | incident=%s", incident)
    st.error(f"Não foi possível salvar agora. Código: {incident}")


def _chapter_fields(chapter: ChapterDetails | None, key: str) -> ChapterInput | None:
    with st.form(key, border=False):
        title = st.text_input(
            "Título do capítulo *",
            value=chapter.title if chapter else "",
            max_chars=180,
            placeholder="Ex.: Capítulo 1 — O chamado",
        )
        summary = st.text_area(
            "Resumo",
            value=(chapter.summary or "") if chapter else "",
            max_chars=20_000,
            height=170,
            placeholder="O que acontece neste capítulo?",
        )
        submitted = st.form_submit_button(
            "Salvar capítulo" if chapter else "Criar capítulo",
            type="primary",
            icon=":material/check:",
            use_container_width=True,
        )
    return ChapterInput(title, summary) if submitted else None


def _scene_fields(
    scene: SceneDetails | None,
    chapters: tuple[ChapterDetails, ...],
    default_chapter_id: UUID,
    key: str,
) -> SceneInput | None:
    chapter_ids = [chapter.id for chapter in chapters]
    selected = scene.chapter_id if scene else default_chapter_id
    labels = {chapter.id: chapter.title for chapter in chapters}
    with st.form(key, border=False):
        chapter_id = st.selectbox(
            "Capítulo *",
            chapter_ids,
            index=chapter_ids.index(selected),
            format_func=lambda value: labels[value],
        )
        title = st.text_input(
            "Título da cena *",
            value=scene.title if scene else "",
            max_chars=180,
            placeholder="Ex.: Igreja",
        )
        summary = st.text_area(
            "Resumo da cena",
            value=(scene.summary or "") if scene else "",
            max_chars=20_000,
            height=120,
            placeholder="Qual é a função desta cena?",
        )
        content = st.text_area(
            "Roteiro / conteúdo",
            value=(scene.content or "") if scene else "",
            max_chars=2_000_000,
            height=310,
            placeholder="Escreva a cena em Markdown...",
        )
        st.caption("O conteúdo é salvo somente ao confirmar, nunca a cada tecla.")
        submitted = st.form_submit_button(
            "Salvar cena" if scene else "Criar cena",
            type="primary",
            icon=":material/check:",
            use_container_width=True,
        )
    return SceneInput(chapter_id, title, summary, content) if submitted else None


@st.dialog("Novo capítulo", width="large", icon=":material/book_2:")
def show_create_chapter_dialog(owner: OwnerIdentity, project_id: UUID) -> None:
    data = _chapter_fields(None, f"create-chapter-{project_id}")
    if data is None:
        return
    try:
        create_chapter(owner, project_id, data)
    except (NarrativeServiceError, SQLAlchemyError) as exc:
        _error(exc)
        return
    set_flash("Capítulo criado.")
    st.rerun()


@st.dialog("Editar capítulo", width="large", icon=":material/edit:")
def show_edit_chapter_dialog(owner: OwnerIdentity, chapter: ChapterDetails) -> None:
    data = _chapter_fields(chapter, f"edit-chapter-{chapter.id}-{chapter.revision}")
    if data is None:
        return
    try:
        update_chapter(
            owner,
            chapter.project_id,
            chapter.id,
            data,
            expected_revision=chapter.revision,
        )
    except (NarrativeServiceError, SQLAlchemyError) as exc:
        _error(exc)
        return
    set_flash("Capítulo atualizado.")
    st.rerun()


@st.dialog("Nova cena", width="large", icon=":material/movie:")
def show_create_scene_dialog(
    owner: OwnerIdentity,
    project_id: UUID,
    chapters: tuple[ChapterDetails, ...],
    chapter_id: UUID,
) -> None:
    data = _scene_fields(None, chapters, chapter_id, f"create-scene-{chapter_id}")
    if data is None:
        return
    try:
        create_scene(owner, project_id, data)
    except (NarrativeServiceError, SQLAlchemyError) as exc:
        _error(exc)
        return
    set_flash("Cena criada.")
    st.rerun()


@st.dialog("Editar cena", width="large", icon=":material/edit_note:")
def show_edit_scene_dialog(
    owner: OwnerIdentity,
    scene: SceneDetails,
    chapters: tuple[ChapterDetails, ...],
) -> None:
    data = _scene_fields(
        scene,
        chapters,
        scene.chapter_id,
        f"edit-scene-{scene.id}-{scene.revision}",
    )
    if data is None:
        return
    try:
        update_scene(
            owner,
            scene.project_id,
            scene.id,
            data,
            expected_revision=scene.revision,
        )
    except (NarrativeServiceError, SQLAlchemyError) as exc:
        _error(exc)
        return
    set_flash("Cena atualizada.")
    st.rerun()
