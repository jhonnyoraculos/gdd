"""Reusable UI for @mention discovery and automatic connections."""

from __future__ import annotations

from uuid import UUID

import streamlit as st

from services.mention_service import ContentConnection, ContentEntityType, MentionTarget
from utils.navigation_state import go_to_page

_ICONS = {
    ContentEntityType.CHARACTER: ":material/person:",
    ContentEntityType.SCENE: ":material/movie:",
    ContentEntityType.CHAPTER: ":material/book_2:",
    ContentEntityType.SECTION: ":material/article:",
}


def render_mention_guide(targets: tuple[MentionTarget, ...], key: str) -> None:
    with st.expander("Conectar com @menções", icon=":material/alternate_email:"):
        st.caption(
            "Digite uma menção no texto e salve. Exemplo: `@corposeco`. "
            "A conexão será criada automaticamente."
        )
        search = (
            st.text_input(
                "Buscar personagem, cena, capítulo ou seção",
                key=f"mention-search-{key}",
                placeholder="Ex.: Corpo Seco",
            )
            .strip()
            .casefold()
        )
        matches = [
            target
            for target in targets
            if not search
            or search in target.label.casefold()
            or search in target.token.casefold()
            or search in target.type_label.casefold()
        ][:30]
        if not matches:
            st.caption("Nenhuma referência encontrada.")
            return
        for target in matches:
            st.markdown(f"`{target.token}` · **{target.type_label}** — {target.label}")
        if len(targets) > len(matches):
            st.caption("Use a busca para localizar outras referências.")


def _open_connection(project_id: UUID, connection: ContentConnection) -> None:
    if connection.target_type is ContentEntityType.CHARACTER:
        go_to_page(
            "character_detail",
            project=str(project_id),
            id=str(connection.target_id),
        )
    elif connection.target_type is ContentEntityType.SCENE:
        go_to_page("narrative", project=str(project_id), scene=str(connection.target_id))
    elif connection.target_type is ContentEntityType.CHAPTER:
        go_to_page("narrative", project=str(project_id), chapter=str(connection.target_id))
    else:
        go_to_page("gdd_editor", project=str(project_id), section=str(connection.target_id))


def render_connections(
    connections: tuple[ContentConnection, ...],
    project_id: UUID,
    key: str,
) -> None:
    if not connections:
        return
    st.markdown(f"**Conexões automáticas · {len(connections)}**")
    with st.container(horizontal=True, wrap=True, gap="small"):
        for index, connection in enumerate(connections):
            if st.button(
                connection.target_label,
                icon=_ICONS[connection.target_type],
                help=f"{connection.type_label} · {connection.mention_token}",
                key=f"connection-{key}-{index}-{connection.target_id}",
            ):
                _open_connection(project_id, connection)
