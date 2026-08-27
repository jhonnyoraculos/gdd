"""Dialogs for directional relationships between project characters."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from services.relationship_service import (
    CharacterRelationshipIndex,
    CharacterRelationshipSummary,
    RelationshipInput,
    RelationshipServiceError,
    create_relationship,
    delete_relationship,
    update_relationship,
)
from services.user_service import OwnerIdentity
from utils.constants import RELATIONSHIP_STATUSES, RELATIONSHIP_TYPES
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)
_CUSTOM_TYPE = "Outro / personalizado"
_CUSTOM_STATUS = "Outro / personalizado"


def _error(exc: Exception, action: str) -> None:
    if isinstance(exc, RelationshipServiceError):
        st.error(str(exc))
        return
    incident = uuid4().hex[:8]
    LOGGER.exception("Relationship %s failed | incident=%s", action, incident)
    st.error(f"Não foi possível salvar a relação. Código: {incident}")


def _type_fields(current: str | None = None) -> str:
    selected = current if current in RELATIONSHIP_TYPES else _CUSTOM_TYPE if current else None
    options = [None, *RELATIONSHIP_TYPES, _CUSTOM_TYPE]
    choice = st.selectbox(
        "Tipo da relação *",
        options,
        index=options.index(selected),
        format_func=lambda value: value or "Selecione...",
    )
    if choice == _CUSTOM_TYPE:
        return st.text_input(
            "Relação personalizada *",
            value=current or "",
            max_chars=120,
            placeholder="Ex.: Tem medo de",
        )
    return choice or ""


def _status_fields(current: str | None = None) -> str | None:
    selected = current if current in RELATIONSHIP_STATUSES else _CUSTOM_STATUS if current else None
    options = [None, *RELATIONSHIP_STATUSES, _CUSTOM_STATUS]
    choice = st.selectbox(
        "Estado da relação",
        options,
        index=options.index(selected),
        format_func=lambda value: value or "Não definido",
    )
    if choice == _CUSTOM_STATUS:
        return st.text_input(
            "Estado personalizado",
            value=current or "",
            max_chars=80,
            placeholder="Ex.: Aliança instável",
        )
    return choice


@st.dialog("Nova relação", icon=":material/add_link:")
def show_create_relationship_dialog(
    owner: OwnerIdentity,
    project_id: UUID,
    source_character_id: UUID,
    source_name: str,
    index: CharacterRelationshipIndex,
) -> None:
    used_targets = {item.target_character_id for item in index.outgoing}
    choices = [
        item
        for item in index.choices
        if item.id != source_character_id and item.id not in used_targets
    ]
    if not choices:
        if len(index.choices) <= 1:
            st.info("Crie outro personagem no projeto antes de adicionar uma relação.")
            if st.button(
                "Ir para Personagens",
                icon=":material/person_add:",
                type="primary",
                use_container_width=True,
            ):
                go_to_page("characters", project=str(project_id))
        else:
            st.info("Este personagem já possui uma relação iniciada com todos os demais.")
        return

    labels = {item.id: f"{item.name} — {item.role}" if item.role else item.name for item in choices}
    st.caption(f"A direção será: {source_name} → personagem selecionado.")
    with st.form(f"create-relationship-{source_character_id}", border=False):
        target_id = st.selectbox(
            "Personagem *",
            [item.id for item in choices],
            format_func=lambda value: labels[value],
        )
        relationship_type = _type_fields()
        relationship_status = _status_fields()
        intensity = st.selectbox(
            "Intensidade",
            [None, 1, 2, 3, 4, 5],
            format_func=lambda value: "Não definida" if value is None else f"{value}/5",
        )
        description = st.text_area(
            "Descrição",
            max_chars=20_000,
            height=150,
            placeholder="Como essa relação funciona dentro da história?",
        )
        submitted = st.form_submit_button(
            "Criar relação",
            icon=":material/check:",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    try:
        create_relationship(
            owner,
            project_id,
            source_character_id,
            target_id,
            RelationshipInput(
                relationship_type=relationship_type,
                description=description,
                intensity=intensity,
                relationship_status=relationship_status,
            ),
        )
    except (RelationshipServiceError, SQLAlchemyError) as exc:
        _error(exc, "creation")
        return
    set_flash("Relação criada.")
    st.rerun()


@st.dialog("Editar relação", icon=":material/edit:")
def show_edit_relationship_dialog(
    owner: OwnerIdentity,
    project_id: UUID,
    relationship: CharacterRelationshipSummary,
) -> None:
    st.caption(
        f"{relationship.source_name} → {relationship.target_name}. "
        "A direção entre os personagens será preservada."
    )
    with st.form(
        f"edit-relationship-{relationship.id}-{relationship.revision}",
        border=False,
    ):
        relationship_type = _type_fields(relationship.relationship_type)
        relationship_status = _status_fields(relationship.relationship_status)
        intensity_options = [None, 1, 2, 3, 4, 5]
        intensity = st.selectbox(
            "Intensidade",
            intensity_options,
            index=intensity_options.index(relationship.intensity),
            format_func=lambda value: "Não definida" if value is None else f"{value}/5",
        )
        description = st.text_area(
            "Descrição",
            value=relationship.description or "",
            max_chars=20_000,
            height=170,
        )
        submitted = st.form_submit_button(
            "Salvar relação",
            icon=":material/check:",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    try:
        update_relationship(
            owner,
            project_id,
            relationship.id,
            RelationshipInput(
                relationship_type=relationship_type,
                description=description,
                intensity=intensity,
                relationship_status=relationship_status,
            ),
            expected_revision=relationship.revision,
        )
    except (RelationshipServiceError, SQLAlchemyError) as exc:
        _error(exc, "update")
        return
    set_flash("Relação atualizada.")
    st.rerun()


@st.dialog("Excluir relação", icon=":material/link_off:")
def show_delete_relationship_dialog(
    owner: OwnerIdentity,
    project_id: UUID,
    relationship: CharacterRelationshipSummary,
) -> None:
    st.warning(
        f"Excluir a relação “{relationship.source_name} → {relationship.target_name}”? "
        "Os personagens não serão excluídos."
    )
    if not st.button(
        "Excluir relação",
        icon=":material/delete:",
        type="primary",
        use_container_width=True,
    ):
        return
    try:
        delete_relationship(
            owner,
            project_id,
            relationship.id,
            expected_revision=relationship.revision,
        )
    except (RelationshipServiceError, SQLAlchemyError) as exc:
        _error(exc, "deletion")
        return
    set_flash("Relação excluída.")
    st.rerun()
