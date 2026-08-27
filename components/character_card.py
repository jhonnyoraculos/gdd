"""Liquid Glass character card."""

from __future__ import annotations

from html import escape

import streamlit as st

from services.character_service import CharacterSummary
from utils.navigation_state import go_to_page


def _portrait(character: CharacterSummary) -> str:
    if character.image_url:
        return (
            '<img class="gdd-character-card__image" '
            f'src="{escape(character.image_url, quote=True)}" '
            f'alt="Retrato de {escape(character.name, quote=True)}" loading="lazy">'
        )
    return (
        '<div class="gdd-character-card__fallback" aria-hidden="true">'
        f"{escape(character.name[:1].upper() or 'P')}</div>"
    )


def render_character_card(character: CharacterSummary) -> None:
    alternate_name = character.nickname or character.codename
    with st.container(key=f"character-card-{character.id}", border=False):
        st.html(
            '<article class="gdd-character-card__visual">'
            f'<div class="gdd-character-card__portrait">{_portrait(character)}</div>'
            '<div class="gdd-character-card__content">'
            f'<span class="gdd-character-role">{escape(character.role or "Papel a definir")}</span>'
            f"<h3>{escape(character.name)}</h3>"
            f'<p class="gdd-character-card__alias">{escape(alternate_name or "Sem apelido")}</p>'
            f'<p class="gdd-character-card__description">'
            f"{escape(character.short_description or 'Ficha pronta para ser desenvolvida.')}</p>"
            "</div></article>"
        )
        if st.button(
            "Abrir personagem",
            key=f"open-character-{character.id}",
            icon=":material/arrow_forward:",
            type="primary",
            use_container_width=True,
        ):
            go_to_page(
                "character_detail",
                project=str(character.project_id),
                id=str(character.id),
            )
