"""Small, safe HTML components for the design system."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st


@dataclass(frozen=True, slots=True)
class InfoCard:
    icon: str
    label: str
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class Step:
    number: str
    title: str
    body: str


def render_card_grid(cards: tuple[InfoCard, ...] | list[InfoCard]) -> None:
    items = "".join(
        (
            '<article class="gdd-card">'
            f'<div class="gdd-card__icon" aria-hidden="true">{escape(card.icon)}</div>'
            f'<div class="gdd-card__label">{escape(card.label)}</div>'
            f'<h3 class="gdd-card__title">{escape(card.title)}</h3>'
            f'<p class="gdd-card__body">{escape(card.body)}</p>'
            "</article>"
        )
        for card in cards
    )
    st.html(f'<div class="gdd-card-grid">{items}</div>')


def render_steps(steps: tuple[Step, ...] | list[Step]) -> None:
    items = "".join(
        (
            '<article class="gdd-step">'
            f'<div class="gdd-step__number">{escape(step.number)}</div>'
            "<div>"
            f'<h3 class="gdd-step__title">{escape(step.title)}</h3>'
            f'<p class="gdd-step__body">{escape(step.body)}</p>'
            "</div>"
            "</article>"
        )
        for step in steps
    )
    st.html(f'<div class="gdd-step-list">{items}</div>')


def render_empty_state(icon: str, title: str, body: str) -> None:
    st.html(
        '<section class="gdd-empty-state">'
        f'<div class="gdd-empty-state__icon" aria-hidden="true">{escape(icon)}</div>'
        f"<h1>{escape(title)}</h1>"
        f"<p>{escape(body)}</p>"
        "</section>"
    )
