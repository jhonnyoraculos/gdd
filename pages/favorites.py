"""Favorites route placeholder."""

from components.cards import render_empty_state


def render() -> None:
    render_empty_state(
        "☆",
        "Favoritos sempre à mão",
        "Projetos, seções e notas favoritas serão conectados às suas fontes reais "
        "nas próximas etapas.",
    )
