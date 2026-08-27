"""Projects route placeholder for the next approved stage."""

from components.cards import render_empty_state


def render() -> None:
    render_empty_state(
        "◫",
        "Espaço preparado para seus jogos",
        "Criação, edição, arquivamento, favoritos e cards de projeto serão "
        "implementados na Etapa 2.",
    )
