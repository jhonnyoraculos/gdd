"""Recent projects route placeholder."""

from components.cards import render_empty_state


def render() -> None:
    render_empty_state(
        "◷",
        "Seus projetos recentes aparecerão aqui",
        "Esta visualização será alimentada por atualizações reais do banco a partir da Etapa 2.",
    )
