"""Reliable scene-cast selection and appearance metadata dialogs."""

from __future__ import annotations

import logging
from uuid import uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from services.appearance_service import (
    AppearanceServiceError,
    ProjectAppearanceIndex,
    SceneCastMember,
    sync_scene_characters,
    update_appearance_details,
)
from services.narrative_service import SceneDetails
from services.user_service import OwnerIdentity
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


def _error(exc: Exception) -> None:
    if isinstance(exc, AppearanceServiceError):
        st.error(str(exc))
        return
    incident = uuid4().hex[:8]
    LOGGER.exception("Appearance write failed | incident=%s", incident)
    st.error(f"Não foi possível salvar os vínculos. Código: {incident}")


@st.dialog("Personagens desta cena", width="large", icon=":material/groups:")
def show_manage_scene_cast_dialog(
    owner: OwnerIdentity,
    scene: SceneDetails,
    appearance_index: ProjectAppearanceIndex,
) -> None:
    if not appearance_index.choices:
        st.info("Crie personagens no projeto antes de vinculá-los a uma cena.")
        if st.button(
            "Ir para Personagens",
            icon=":material/person_add:",
            type="primary",
            use_container_width=True,
        ):
            go_to_page("characters", project=str(scene.project_id))
        return

    current = appearance_index.cast_for(scene.id)
    current_ids = frozenset(member.character_id for member in current)
    choices = [choice.id for choice in appearance_index.choices]
    labels = {
        choice.id: f"{choice.name} — {choice.role}" if choice.role else choice.name
        for choice in appearance_index.choices
    }
    with st.form(f"scene-cast-{scene.id}", border=False):
        selected = st.multiselect(
            "Selecione o elenco",
            choices,
            default=[choice_id for choice_id in choices if choice_id in current_ids],
            format_func=lambda value: labels[value],
            placeholder="Pesquisar personagem...",
        )
        st.caption(
            "A seleção representa exatamente os personagens vinculados à cena. "
            "Remover um nome remove sua aparição."
        )
        submitted = st.form_submit_button(
            "Salvar vínculos",
            icon=":material/check:",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    try:
        sync_scene_characters(
            owner,
            scene.project_id,
            scene.id,
            selected,
            expected_character_ids=current_ids,
        )
    except (AppearanceServiceError, SQLAlchemyError) as exc:
        _error(exc)
        return
    set_flash("Personagens da cena atualizados.")
    st.rerun()


@st.dialog("Detalhes da participação", icon=":material/badge:")
def show_edit_appearance_dialog(
    owner: OwnerIdentity,
    scene: SceneDetails,
    member: SceneCastMember,
) -> None:
    st.caption(f"{member.name} em {scene.title}")
    with st.form(f"appearance-details-{scene.id}-{member.character_id}", border=False):
        role = st.text_input(
            "Papel nesta cena",
            value=member.role_in_scene or "",
            max_chars=120,
            placeholder="Ex.: Confronta o protagonista",
        )
        notes = st.text_area(
            "Notas",
            value=member.notes or "",
            max_chars=20_000,
            height=160,
            placeholder="Observações específicas desta aparição...",
        )
        submitted = st.form_submit_button(
            "Salvar detalhes",
            icon=":material/check:",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    try:
        update_appearance_details(
            owner,
            scene.project_id,
            scene.id,
            member.character_id,
            role_in_scene=role,
            notes=notes,
        )
    except (AppearanceServiceError, SQLAlchemyError) as exc:
        _error(exc)
        return
    set_flash("Detalhes da participação atualizados.")
    st.rerun()
