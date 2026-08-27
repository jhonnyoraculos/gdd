"""Deterministic stylesheet loader."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

STYLE_ROOT = Path(__file__).resolve().parent
BASE_STYLESHEETS: tuple[Path, ...] = (STYLE_ROOT / "variables.css",)
THEME_STYLESHEETS: dict[str, Path] = {
    "dark": STYLE_ROOT / "theme_dark.css",
    "light": STYLE_ROOT / "theme_light.css",
}
COMPONENT_STYLESHEETS: tuple[Path, ...] = (
    STYLE_ROOT / "base.css",
    STYLE_ROOT / "layout.css",
    STYLE_ROOT / "components.css",
    STYLE_ROOT / "liquid_glass.css",
    STYLE_ROOT / "mobile.css",
    STYLE_ROOT / "streamlit_overrides.css",
)
STYLESHEETS: tuple[Path, ...] = (
    *BASE_STYLESHEETS,
    *THEME_STYLESHEETS.values(),
    *COMPONENT_STYLESHEETS,
)


def stylesheets_for_theme(theme: str | None) -> tuple[Path, ...]:
    active_theme = theme if theme in THEME_STYLESHEETS else "dark"
    return (
        *BASE_STYLESHEETS,
        THEME_STYLESHEETS[active_theme],
        *COMPONENT_STYLESHEETS,
    )


def load_styles(theme: str | None = None) -> None:
    """Load local CSS files in design-token-to-overrides order."""

    missing = [path.name for path in STYLESHEETS if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Stylesheets ausentes: {', '.join(missing)}")

    for stylesheet in stylesheets_for_theme(theme):
        st.html(stylesheet)
