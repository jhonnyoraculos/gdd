"""Complete character profile route."""

from __future__ import annotations

import logging
from collections import defaultdict
from html import escape
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.cards import render_empty_state
from components.character_form import show_edit_character_dialog
from components.feedback import set_flash
from config.settings import get_settings
from services.appearance_service import (
    AppearanceServiceError,
    CharacterAppearance,
    CharacterTimeline,
    get_character_timeline,
)
from services.character_service import (
    CharacterDetails,
    CharacterNotFoundError,
    delete_character,
    get_character,
)
from services.project_service import ProjectNotFoundError, get_project
from services.user_service import OwnerIdentity, owner_from_settings
from utils.navigation_state import go_to_page

LOGGER = logging.getLogger(__name__)


def _uuid_param(name: str) -> UUID | None:
    raw = st.query_params.get(name)
    try:
        return UUID(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _portrait(character: CharacterDetails) -> str:
    if character.image_url:
        return (
            '<img class="gdd-character-hero__image" '
            f'src="{escape(character.image_url, quote=True)}" '
            f'alt="Retrato de {escape(character.name, quote=True)}">'
        )
    return (
        '<div class="gdd-character-hero__fallback" aria-hidden="true">'
        f"{escape(character.name[:1].upper() or 'P')}</div>"
    )


def _hero(character: CharacterDetails) -> None:
    profile = character.profile
    identity = " · ".join(
        value for value in (profile.nickname, profile.codename, profile.species) if value
    )
    identity_label = escape(identity or "Identidade em desenvolvimento")
    st.html(
        '<section class="gdd-character-hero">'
        f'<div class="gdd-character-hero__portrait">{_portrait(character)}</div>'
        '<div class="gdd-character-hero__content">'
        f'<span class="gdd-character-role">{escape(profile.role or "Papel a definir")}</span>'
        f"<h1>{escape(character.name)}</h1>"
        f'<p class="gdd-character-hero__meta">{identity_label}</p>'
        f'<p class="gdd-character-hero__description">'
        f"{escape(profile.short_description or 'Sem descrição curta ainda.')}</p>"
        "</div></section>"
    )


def _text(value: str) -> str:
    return escape(value).replace("\n", "<br>")


def _profile_block(title: str, entries: tuple[tuple[str, str | int | None], ...]) -> None:
    populated = [(label, value) for label, value in entries if value not in (None, "")]
    if not populated:
        return
    items = "".join(
        '<div class="gdd-profile-field">'
        f"<span>{escape(label)}</span><p>{_text(str(value))}</p></div>"
        for label, value in populated
    )
    st.html(
        '<section class="gdd-profile-section">'
        f"<h2>{escape(title)}</h2>"
        f'<div class="gdd-profile-grid">{items}</div>'
        "</section>"
    )


def _arc(character: CharacterDetails) -> None:
    profile = character.profile
    steps = (
        ("Início", profile.arc_beginning),
        ("Transformação", profile.arc_transformation),
        ("Ruptura", profile.arc_breaking_point),
        ("Final", profile.arc_ending),
    )
    if not any(value for _, value in steps):
        return
    items = "".join(
        '<div class="gdd-character-arc__step">'
        f"<span>{escape(label)}</span><p>{_text(value or 'A definir')}</p></div>"
        for label, value in steps
    )
    st.html(
        '<section class="gdd-profile-section">'
        "<h2>Arco narrativo</h2>"
        f'<div class="gdd-character-arc">{items}</div>'
        "</section>"
    )


def _profile(character: CharacterDetails) -> None:
    profile = character.profile
    _profile_block(
        "Informações básicas",
        (
            ("Nome completo", profile.full_name),
            ("Apelido", profile.nickname),
            ("Codinome", profile.codename),
            ("Idade", profile.age),
            (
                "Data de nascimento",
                profile.birth_date.strftime("%d/%m/%Y") if profile.birth_date else None,
            ),
            ("Gênero", profile.gender),
            ("Espécie", profile.species),
            ("Ocupação", profile.occupation),
            ("Local de origem", profile.origin),
            ("Estado atual", profile.current_status),
        ),
    )
    _profile_block(
        "Visão geral",
        (
            ("Resumo", profile.summary),
            ("Papel no jogo", profile.game_role),
            ("Importância narrativa", profile.narrative_importance),
        ),
    )
    _profile_block(
        "História",
        (
            ("História do personagem", profile.story),
            ("Infância", profile.childhood),
            ("Passado", profile.past),
            ("Acontecimentos importantes", profile.important_events),
            ("Situação atual", profile.current_situation),
        ),
    )
    _profile_block(
        "Personalidade",
        (
            ("Personalidade", profile.personality),
            ("Qualidades", profile.qualities),
            ("Defeitos", profile.flaws),
            ("Medos", profile.fears),
            ("Desejos", profile.desires),
            ("Motivações", profile.motivations),
            ("Traumas", profile.traumas),
            ("Crenças", profile.beliefs),
            ("Valores", profile.values),
            ("Manias", profile.habits),
        ),
    )
    _profile_block(
        "Objetivos",
        (
            ("Objetivo externo", profile.external_goal),
            ("Objetivo interno", profile.internal_goal),
            ("Motivação", profile.motivations),
            ("Conflito", profile.conflict),
        ),
    )
    _arc(character)
    _profile_block(
        "Aparência",
        (
            ("Descrição visual", profile.appearance),
            ("Altura", profile.height),
            ("Corpo", profile.body_description),
            ("Cabelo", profile.hair),
            ("Olhos", profile.eyes),
            ("Roupas", profile.clothing),
            ("Características marcantes", profile.distinctive_features),
        ),
    )
    _profile_block(
        "Gameplay",
        (
            ("Vida", profile.health),
            ("Habilidades", profile.abilities),
            ("Fraquezas", profile.weaknesses),
            ("Ataques", profile.attacks),
            ("Comportamento", profile.behavior),
            ("IA", profile.ai_description),
            ("Equipamentos", profile.equipment),
            ("Armas", profile.weapons),
        ),
    )


def _appearances(timeline: CharacterTimeline, project_id: UUID) -> None:
    if not timeline.items:
        st.html(
            '<section class="gdd-profile-section gdd-profile-section--muted">'
            "<h2>Aparições</h2>"
            "<p>Este personagem ainda não foi vinculado a nenhuma cena.</p>"
            "</section>"
        )
        if st.button(
            "Abrir estrutura narrativa",
            icon=":material/account_tree:",
            use_container_width=True,
        ):
            go_to_page("narrative", project=str(project_id))
        return

    first = timeline.first
    last = timeline.last
    assert first is not None and last is not None
    st.html(
        '<section class="gdd-profile-section">'
        "<h2>Aparições</h2>"
        '<div class="gdd-appearance-metrics">'
        "<div><span>Total</span>"
        f"<strong>{timeline.total}</strong></div>"
        "<div><span>Primeira aparição</span>"
        f"<strong>{escape(first.scene_title)}</strong></div>"
        "<div><span>Última aparição</span>"
        f"<strong>{escape(last.scene_title)}</strong></div>"
        "<div><span>Capítulos</span>"
        f"<strong>{timeline.chapter_count}</strong></div>"
        "</div></section>"
    )

    grouped: defaultdict[UUID, list[CharacterAppearance]] = defaultdict(list)
    chapter_names: dict[UUID, str] = {}
    for item in timeline.items:
        grouped[item.chapter_id].append(item)
        chapter_names[item.chapter_id] = item.chapter_title
    chapters = "".join(
        '<div class="gdd-appearance-chapter">'
        f"<h3>{escape(chapter_names[chapter_id])}</h3>"
        + "".join(
            '<div class="gdd-appearance-scene">'
            f"<strong>{escape(item.scene_title)}</strong>"
            + (f"<span>{escape(item.role_in_scene)}</span>" if item.role_in_scene else "")
            + (f"<p>{_text(item.notes)}</p>" if item.notes else "")
            + "</div>"
            for item in items
        )
        + "</div>"
        for chapter_id, items in grouped.items()
    )
    timeline_nodes = "".join(
        '<div class="gdd-timeline-node">'
        f"<span>{index}</span><div><small>{escape(item.chapter_title)}</small>"
        f"<strong>{escape(item.scene_title)}</strong></div></div>"
        for index, item in enumerate(timeline.items, start=1)
    )
    st.html(
        '<section class="gdd-profile-section">'
        "<h2>Cenas por capítulo</h2>"
        f'<div class="gdd-appearance-chapters">{chapters}</div>'
        "</section>"
        '<section class="gdd-profile-section">'
        "<h2>Linha narrativa</h2>"
        f'<div class="gdd-character-timeline">{timeline_nodes}</div>'
        "</section>"
    )
    if st.button(
        "Abrir estrutura narrativa",
        icon=":material/account_tree:",
        use_container_width=True,
    ):
        go_to_page("narrative", project=str(project_id))


@st.dialog("Excluir personagem", icon=":material/delete_forever:")
def _confirm_delete(
    owner: OwnerIdentity,
    character: CharacterDetails,
    appearance_count: int,
) -> None:
    appearance_label = (
        f"{appearance_count} aparição" if appearance_count == 1 else f"{appearance_count} aparições"
    )
    st.warning(
        f"Excluir {character.name}? Esta ação é permanente. "
        f"{appearance_label} "
        "também será removida por integridade do banco."
    )
    confirmation = st.text_input(
        f'Digite "{character.name}" para confirmar',
        key=f"delete-character-confirm-{character.id}",
    )
    if st.button(
        "Excluir definitivamente",
        type="primary",
        disabled=confirmation != character.name,
        use_container_width=True,
    ):
        try:
            delete_character(owner, character.project_id, character.id)
        except (CharacterNotFoundError, SQLAlchemyError):
            incident = uuid4().hex[:8]
            LOGGER.exception("Character deletion failed | incident=%s", incident)
            st.error(f"Não foi possível excluir o personagem. Código: {incident}")
            return
        set_flash("Personagem excluído.")
        go_to_page("characters", project=str(character.project_id))


def render() -> None:
    project_id = _uuid_param("project")
    character_id = _uuid_param("id")
    if project_id is None or character_id is None:
        render_empty_state("?", "Personagem não identificado", "Abra uma ficha pela biblioteca.")
        if st.button("Voltar aos projetos", use_container_width=True):
            go_to_page("projects")
        return

    owner = owner_from_settings(get_settings())
    try:
        get_project(owner, project_id)
        character = get_character(owner, project_id, character_id)
        timeline = get_character_timeline(owner, project_id, character_id)
    except (ProjectNotFoundError, CharacterNotFoundError, AppearanceServiceError):
        render_empty_state("?", "Personagem não encontrado", "A ficha pode ter sido removida.")
        if st.button("Voltar aos personagens", use_container_width=True):
            go_to_page("characters", project=str(project_id))
        return
    except SQLAlchemyError:
        incident = uuid4().hex[:8]
        LOGGER.exception("Character detail load failed | incident=%s", incident)
        st.error(f"Não foi possível carregar a ficha. Código: {incident}")
        return

    back, actions = st.columns([1, 1], vertical_alignment="center")
    with back:
        if st.button("Personagens", icon=":material/arrow_back:"):
            go_to_page("characters", project=str(project_id))
    with actions, st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Editar", icon=":material/edit:"):
            show_edit_character_dialog(owner, character)
        if st.button("Excluir", icon=":material/delete:"):
            _confirm_delete(owner, character, timeline.total)

    _hero(character)
    _appearances(timeline, project_id)
    _profile(character)
