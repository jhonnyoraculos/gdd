"""Create and edit dialogs for complete character profiles."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from services.character_service import (
    CharacterDetails,
    CharacterInput,
    CharacterServiceError,
    create_character,
    update_character,
)
from services.user_service import OwnerIdentity
from utils.constants import CHARACTER_ROLES
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)
_CUSTOM_ROLE = "Outro / personalizado"


def _value(character: CharacterDetails | None, field: str) -> object:
    return getattr(character.profile, field) if character else None


def _text(
    label: str,
    character: CharacterDetails | None,
    field: str,
    *,
    max_chars: int = 240,
    placeholder: str | None = None,
) -> str:
    return st.text_input(
        label,
        value=str(_value(character, field) or ""),
        max_chars=max_chars,
        placeholder=placeholder,
    )


def _area(
    label: str,
    character: CharacterDetails | None,
    field: str,
    *,
    height: int = 110,
    placeholder: str | None = None,
) -> str:
    return st.text_area(
        label,
        value=str(_value(character, field) or ""),
        max_chars=100_000,
        height=height,
        placeholder=placeholder,
    )


def _profile_fields(
    character: CharacterDetails | None,
    form_key: str,
) -> CharacterInput | None:
    current_role = str(_value(character, "role") or "")
    selected_role = (
        current_role if current_role in CHARACTER_ROLES else _CUSTOM_ROLE if current_role else None
    )
    role_options = [None, *CHARACTER_ROLES, _CUSTOM_ROLE]
    values: dict[str, object] = {}

    with st.form(form_key, border=False):
        identity, overview, history, mind, journey, visual, gameplay = st.tabs(
            [
                "Identificação",
                "Visão geral",
                "História",
                "Personalidade",
                "Objetivos e arco",
                "Aparência",
                "Gameplay",
            ]
        )
        with identity:
            values["name"] = st.text_input(
                "Nome *",
                value=str(_value(character, "name") or ""),
                max_chars=160,
                placeholder="Ex.: Encouraçado",
            )
            first, second = st.columns(2)
            with first:
                values["full_name"] = _text("Nome completo", character, "full_name")
                values["nickname"] = _text("Apelido", character, "nickname", max_chars=160)
                values["codename"] = _text("Codinome", character, "codename", max_chars=160)
                role_choice = st.selectbox(
                    "Papel narrativo",
                    role_options,
                    index=role_options.index(selected_role),
                    format_func=lambda value: value or "Não definido",
                )
                values["role"] = (
                    _text(
                        "Papel personalizado",
                        character,
                        "role",
                        max_chars=100,
                        placeholder="Ex.: Guardião do limiar",
                    )
                    if role_choice == _CUSTOM_ROLE
                    else role_choice
                )
            with second:
                values["age"] = st.number_input(
                    "Idade",
                    min_value=0,
                    max_value=999,
                    value=_value(character, "age"),
                    step=1,
                )
                values["birth_date"] = st.date_input(
                    "Data de nascimento",
                    value=_value(character, "birth_date"),
                    format="DD/MM/YYYY",
                )
                values["gender"] = _text("Gênero", character, "gender", max_chars=100)
                values["species"] = _text("Espécie", character, "species", max_chars=120)
                values["occupation"] = _text("Ocupação", character, "occupation", max_chars=160)
                values["origin"] = _text("Local de origem", character, "origin", max_chars=200)
                values["current_status"] = _text(
                    "Estado atual", character, "current_status", max_chars=120
                )
            values["image_url"] = _text(
                "URL da imagem",
                character,
                "image_url",
                max_chars=2048,
                placeholder="https://...",
            )
            st.caption("Use uma imagem hospedada em uma URL pública HTTPS.")

        with overview:
            values["short_description"] = _area(
                "Descrição curta", character, "short_description", height=90
            )
            values["summary"] = _area(
                "Resumo",
                character,
                "summary",
                height=180,
                placeholder="Quem é este personagem e qual sua função na experiência?",
            )
            first, second = st.columns(2)
            with first:
                values["game_role"] = _area("Papel no jogo", character, "game_role")
            with second:
                values["narrative_importance"] = _area(
                    "Importância narrativa", character, "narrative_importance"
                )

        with history:
            values["story"] = _area("História do personagem", character, "story", height=260)
            first, second = st.columns(2)
            with first:
                values["childhood"] = _area("Infância", character, "childhood")
                values["past"] = _area("Passado", character, "past")
            with second:
                values["important_events"] = _area(
                    "Acontecimentos importantes", character, "important_events"
                )
                values["current_situation"] = _area(
                    "Situação atual", character, "current_situation"
                )

        with mind:
            values["personality"] = _area("Personalidade", character, "personality", height=180)
            first, second = st.columns(2)
            with first:
                values["qualities"] = _area("Qualidades", character, "qualities")
                values["fears"] = _area("Medos", character, "fears")
                values["motivations"] = _area("Motivações", character, "motivations")
                values["beliefs"] = _area("Crenças", character, "beliefs")
                values["habits"] = _area("Manias", character, "habits")
            with second:
                values["flaws"] = _area("Defeitos", character, "flaws")
                values["desires"] = _area("Desejos", character, "desires")
                values["traumas"] = _area("Traumas", character, "traumas")
                values["values"] = _area("Valores", character, "values")

        with journey:
            st.subheader("Objetivos")
            values["external_goal"] = _area("Objetivo externo", character, "external_goal")
            values["internal_goal"] = _area("Objetivo interno", character, "internal_goal")
            values["conflict"] = _area("Conflito", character, "conflict")
            st.subheader("Arco narrativo")
            first, second = st.columns(2)
            with first:
                values["arc_beginning"] = _area("Estado inicial", character, "arc_beginning")
                values["arc_breaking_point"] = _area(
                    "Ponto de ruptura", character, "arc_breaking_point"
                )
            with second:
                values["arc_transformation"] = _area(
                    "Transformação", character, "arc_transformation"
                )
                values["arc_ending"] = _area("Estado final", character, "arc_ending")

        with visual:
            values["appearance"] = _area("Descrição visual", character, "appearance", height=180)
            first, second = st.columns(2)
            with first:
                values["height"] = _text("Altura", character, "height", max_chars=80)
                values["body_description"] = _area("Corpo", character, "body_description")
                values["hair"] = _text("Cabelo", character, "hair")
                values["eyes"] = _text("Olhos", character, "eyes")
            with second:
                values["clothing"] = _area("Roupas", character, "clothing")
                values["distinctive_features"] = _area(
                    "Características marcantes", character, "distinctive_features"
                )

        with gameplay:
            first, second = st.columns(2)
            with first:
                values["health"] = _area("Vida", character, "health")
                values["abilities"] = _area("Habilidades", character, "abilities")
                values["weaknesses"] = _area("Fraquezas", character, "weaknesses")
                values["attacks"] = _area("Ataques", character, "attacks")
            with second:
                values["behavior"] = _area("Comportamento", character, "behavior")
                values["ai_description"] = _area("IA", character, "ai_description")
                values["equipment"] = _area("Equipamentos", character, "equipment")
                values["weapons"] = _area("Armas", character, "weapons")

        submitted = st.form_submit_button(
            "Salvar personagem" if character else "Criar personagem",
            type="primary",
            icon=":material/check:",
            use_container_width=True,
        )
    return CharacterInput(**values) if submitted else None


def _render_action_error(exc: Exception) -> None:
    if isinstance(exc, CharacterServiceError):
        st.error(str(exc))
        return
    incident = uuid4().hex[:8]
    LOGGER.exception("Character write failed | incident=%s", incident)
    st.error(f"Não foi possível salvar o personagem agora. Código: {incident}")


@st.dialog("Novo personagem", width="large", icon=":material/person_add:")
def show_create_character_dialog(owner: OwnerIdentity, project_id: UUID) -> None:
    st.caption(
        "Preencha apenas o que fizer sentido agora. Todos os campos são opcionais, exceto o nome."
    )
    data = _profile_fields(None, f"create-character-{project_id}")
    if data is None:
        return
    try:
        character_id = create_character(owner, project_id, data)
    except (CharacterServiceError, SQLAlchemyError) as exc:
        _render_action_error(exc)
        return
    set_flash("Personagem criado e salvo no Neon.")
    go_to_page("character_detail", project=str(project_id), id=str(character_id))


@st.dialog("Editar personagem", width="large", icon=":material/edit:")
def show_edit_character_dialog(owner: OwnerIdentity, character: CharacterDetails) -> None:
    data = _profile_fields(character, f"edit-character-{character.id}-{character.revision}")
    if data is None:
        return
    try:
        update_character(
            owner,
            character.project_id,
            character.id,
            data,
            expected_revision=character.revision,
        )
    except (CharacterServiceError, SQLAlchemyError) as exc:
        _render_action_error(exc)
        return
    set_flash("Ficha do personagem atualizada.")
    st.rerun()
