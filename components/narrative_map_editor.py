"""Dialogs and dispatchers used by the bidirectional narrative map."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from components.feedback import set_flash
from services.appearance_service import (
    AppearanceServiceError,
    get_project_appearance_index,
    sync_scene_characters,
    update_appearance_details,
)
from services.character_service import CharacterServiceError, delete_character
from services.gdd_service import (
    GddConflictError,
    GddServiceError,
    SectionDocument,
    SectionInput,
    SectionNode,
    create_section,
    delete_section,
    get_section,
    update_section_content,
    update_section_metadata,
)
from services.narrative_map_link_service import (
    NarrativeMapLinkInput,
    NarrativeMapLinkServiceError,
    create_narrative_map_link,
    delete_narrative_map_link,
    parse_node_key,
)
from services.narrative_map_service import (
    MapEdgeType,
    MapNodeType,
    NarrativeMapEdge,
    NarrativeMapGraph,
    NarrativeMapNode,
)
from services.narrative_service import (
    ChapterDetails,
    NarrativeServiceError,
    SceneDetails,
    delete_chapter,
    delete_scene,
)
from services.relationship_service import (
    RelationshipInput,
    RelationshipServiceError,
    create_relationship,
    delete_relationship,
    get_relationship,
)
from services.user_service import OwnerIdentity
from utils.constants import SECTION_STATUSES

LOGGER = logging.getLogger(__name__)
_TYPE_LABELS = {
    MapNodeType.CHAPTER: "Capítulo",
    MapNodeType.SCENE: "Cena",
    MapNodeType.CHARACTER: "Personagem",
    MapNodeType.SECTION: "Seção GDD",
}
_SECTION_TYPES = {"page": "Página", "category": "Categoria", "group": "Grupo"}
_STATUS_LABELS = {status.value: status.label for status in SECTION_STATUSES}


def _error(exc: Exception, action: str) -> None:
    known = (
        AppearanceServiceError,
        CharacterServiceError,
        GddServiceError,
        NarrativeMapLinkServiceError,
        NarrativeServiceError,
        RelationshipServiceError,
    )
    if isinstance(exc, known):
        st.error(str(exc))
        return
    incident = uuid4().hex[:8]
    LOGGER.exception("Map editor %s failed | incident=%s", action, incident)
    st.error(f"Não foi possível concluir a ação. Código: {incident}")


def _editable_nodes(graph: NarrativeMapGraph) -> tuple[NarrativeMapNode, ...]:
    return tuple(node for node in graph.nodes if node.node_type is not MapNodeType.PROJECT)


def _node_label(node: NarrativeMapNode) -> str:
    return f"{_TYPE_LABELS[node.node_type]} · {node.label}"


@st.dialog("Nova seção do GDD", width="large", icon=":material/note_add:")
def show_create_map_section_dialog(
    owner: OwnerIdentity,
    project_id: UUID,
    sections: tuple[SectionNode, ...],
) -> None:
    parent_options: list[UUID | None] = [None, *(section.id for section in sections)]
    parent_labels = {None: "Raiz do GDD", **{section.id: section.title for section in sections}}
    with st.form(f"map-create-section-{project_id}", border=False):
        title = st.text_input("Título *", max_chars=180, placeholder="Ex.: Missão secundária")
        first, second = st.columns(2)
        with first:
            section_type = st.selectbox(
                "Tipo",
                list(_SECTION_TYPES),
                format_func=_SECTION_TYPES.get,
            )
        with second:
            icon = st.text_input("Ícone", max_chars=40, placeholder="Ex.: ✦")
        parent_id = st.selectbox("Dentro de", parent_options, format_func=parent_labels.get)
        submitted = st.form_submit_button(
            "Criar card no mapa",
            icon=":material/add:",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    try:
        section_id = create_section(
            owner,
            project_id,
            SectionInput(title, icon, section_type, parent_id),
        )
        created = get_section(owner, project_id, section_id)
        update_section_content(
            owner,
            project_id,
            section_id,
            f"# {created.title}\n\n",
            created.revision,
        )
    except (GddServiceError, SQLAlchemyError) as exc:
        _error(exc, "create section")
        return
    set_flash("Seção criada no GDD e adicionada ao mapa.")
    st.rerun()


@st.dialog("Editar seção do GDD", width="large", icon=":material/edit_note:")
def show_edit_map_section_dialog(
    owner: OwnerIdentity,
    project_id: UUID,
    section: SectionDocument,
) -> None:
    status_values = list(_STATUS_LABELS)
    with st.form(f"map-edit-section-{section.id}-{section.revision}", border=False):
        title = st.text_input("Título *", value=section.title, max_chars=180)
        first, second, third = st.columns(3)
        with first:
            section_type = st.selectbox(
                "Tipo",
                list(_SECTION_TYPES),
                index=list(_SECTION_TYPES).index(section.section_type),
                format_func=_SECTION_TYPES.get,
            )
        with second:
            status = st.selectbox(
                "Status",
                status_values,
                index=status_values.index(section.status),
                format_func=_STATUS_LABELS.get,
            )
        with third:
            icon = st.text_input("Ícone", value=section.icon or "", max_chars=40)
        content = st.text_area(
            "Conteúdo",
            value=section.content,
            height=420,
            max_chars=2_000_000,
            placeholder="Escreva em Markdown...",
        )
        submitted = st.form_submit_button(
            "Salvar alterações",
            icon=":material/save:",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    try:
        if content != section.content:
            update_section_content(
                owner,
                project_id,
                section.id,
                content,
                section.revision,
            )
        update_section_metadata(
            owner,
            project_id,
            section.id,
            SectionInput(title, icon, section_type, section.parent_id, status),
        )
    except (GddConflictError, GddServiceError, SQLAlchemyError) as exc:
        _error(exc, "edit section")
        return
    set_flash("Seção atualizada pelo mapa.")
    st.rerun()


def _create_smart_connection(
    owner: OwnerIdentity,
    project_id: UUID,
    source: NarrativeMapNode,
    target: NarrativeMapNode,
    label: str,
    directed: bool,
    smart: bool,
) -> str:
    pair = {source.node_type, target.node_type}
    if smart and pair == {MapNodeType.SCENE, MapNodeType.CHARACTER}:
        scene = source if source.node_type is MapNodeType.SCENE else target
        character = source if source.node_type is MapNodeType.CHARACTER else target
        appearance_index = get_project_appearance_index(owner, project_id)
        current = appearance_index.cast_for(scene.entity_id)
        current_ids = frozenset(member.character_id for member in current)
        if character.entity_id in current_ids:
            raise NarrativeMapLinkServiceError("Este personagem já participa da cena selecionada.")
        sync_scene_characters(
            owner,
            project_id,
            scene.entity_id,
            [*current_ids, character.entity_id],
            expected_character_ids=current_ids,
        )
        if label:
            update_appearance_details(
                owner,
                project_id,
                scene.entity_id,
                character.entity_id,
                role_in_scene=label,
                notes=None,
            )
        return "Personagem conectado à cena e incluído no elenco."

    if smart and pair == {MapNodeType.CHARACTER}:
        create_relationship(
            owner,
            project_id,
            source.entity_id,
            target.entity_id,
            RelationshipInput(label or "Relacionado a"),
        )
        return "Relação entre personagens criada."

    source_type, source_id = parse_node_key(source.key)
    target_type, target_id = parse_node_key(target.key)
    create_narrative_map_link(
        owner,
        project_id,
        NarrativeMapLinkInput(
            source_type,
            source_id,
            target_type,
            target_id,
            label,
            directed,
        ),
    )
    return "Ligação visual criada e salva no Neon."


@st.dialog("Criar ligação", width="large", icon=":material/add_link:")
def show_create_map_link_dialog(
    owner: OwnerIdentity,
    graph: NarrativeMapGraph,
    source_key: str | None = None,
) -> None:
    nodes = _editable_nodes(graph)
    if len(nodes) < 2:
        st.info("Crie pelo menos dois cards antes de adicionar uma ligação.")
        return
    keys = [node.key for node in nodes]
    node_by_key = {node.key: node for node in nodes}
    source_index = keys.index(source_key) if source_key in node_by_key else 0
    default_target = next(index for index, key in enumerate(keys) if key != keys[source_index])
    with st.form(f"map-create-link-{graph.project_id}-{source_key}", border=False):
        st.caption(
            "A conexão inteligente transforma Cena ↔ Personagem em elenco e "
            "Personagem → Personagem em relação narrativa. As demais viram ligações visuais."
        )
        source = st.selectbox(
            "Card de origem *",
            keys,
            index=source_index,
            format_func=lambda value: _node_label(node_by_key[value]),
        )
        target = st.selectbox(
            "Card de destino *",
            keys,
            index=default_target,
            format_func=lambda value: _node_label(node_by_key[value]),
        )
        label = st.text_input(
            "Nome ou função da ligação",
            max_chars=120,
            placeholder="Ex.: investiga, encontra, depende de...",
        )
        first, second = st.columns(2)
        with first:
            smart = st.checkbox("Conexão inteligente", value=True)
        with second:
            directed = st.checkbox("Mostrar direção (origem → destino)")
        submitted = st.form_submit_button(
            "Criar ligação",
            icon=":material/add_link:",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    if source == target:
        st.warning("Escolha dois cards diferentes.")
        return
    try:
        message = _create_smart_connection(
            owner,
            graph.project_id,
            node_by_key[source],
            node_by_key[target],
            label.strip(),
            directed,
            smart,
        )
    except (
        AppearanceServiceError,
        NarrativeMapLinkServiceError,
        RelationshipServiceError,
        SQLAlchemyError,
    ) as exc:
        _error(exc, "create link")
        return
    set_flash(message)
    st.rerun()


@st.dialog("Excluir ligação", icon=":material/link_off:")
def show_delete_map_edge_dialog(
    owner: OwnerIdentity,
    graph: NarrativeMapGraph,
    edge: NarrativeMapEdge,
) -> None:
    node_by_key = {node.key: node for node in graph.nodes}
    source = node_by_key.get(edge.source)
    target = node_by_key.get(edge.target)
    if source is None or target is None:
        st.error("Os cards desta ligação não estão mais disponíveis.")
        return
    st.warning(
        f"Excluir a ligação entre “{source.label}” e “{target.label}”? "
        "Os cards continuarão existindo."
    )
    if edge.edge_type is MapEdgeType.APPEARANCE:
        st.caption("O personagem também será retirado do elenco da cena.")
    if not st.button(
        "Excluir ligação",
        icon=":material/link_off:",
        type="primary",
        use_container_width=True,
    ):
        return
    try:
        record_id = UUID(edge.key.partition(":")[2])
        if edge.edge_type is MapEdgeType.MANUAL:
            delete_narrative_map_link(owner, graph.project_id, record_id)
        elif edge.edge_type is MapEdgeType.RELATIONSHIP:
            relationship = get_relationship(owner, graph.project_id, record_id)
            delete_relationship(
                owner,
                graph.project_id,
                record_id,
                expected_revision=relationship.revision,
            )
        elif edge.edge_type is MapEdgeType.APPEARANCE:
            scene = source if source.node_type is MapNodeType.SCENE else target
            character = source if source.node_type is MapNodeType.CHARACTER else target
            appearance_index = get_project_appearance_index(owner, graph.project_id)
            current_ids = frozenset(
                member.character_id for member in appearance_index.cast_for(scene.entity_id)
            )
            sync_scene_characters(
                owner,
                graph.project_id,
                scene.entity_id,
                current_ids - {character.entity_id},
                expected_character_ids=current_ids,
            )
        else:
            raise NarrativeMapLinkServiceError(
                "Esta ligação é automática. Edite sua origem para removê-la."
            )
    except (
        AppearanceServiceError,
        NarrativeMapLinkServiceError,
        RelationshipServiceError,
        SQLAlchemyError,
        ValueError,
    ) as exc:
        _error(exc, "delete link")
        return
    set_flash("Ligação excluída.")
    st.rerun()


@st.dialog("Excluir card", icon=":material/delete_forever:")
def show_delete_map_node_dialog(
    owner: OwnerIdentity,
    project_id: UUID,
    node: NarrativeMapNode,
    chapter: ChapterDetails | None = None,
    scene: SceneDetails | None = None,
    section: SectionDocument | None = None,
) -> None:
    if node.node_type is MapNodeType.CHAPTER and chapter:
        warning = f"O capítulo e suas {len(chapter.scenes)} cenas serão excluídos."
    elif node.node_type is MapNodeType.SECTION:
        warning = "A seção, suas subseções, imagens e ligações serão excluídas."
    else:
        warning = "O card e suas ligações serão excluídos permanentemente."
    st.warning(f"Excluir “{node.label}”? {warning}")
    confirmation = st.text_input(f'Digite "{node.label}" para confirmar')
    if not st.button(
        "Excluir definitivamente",
        icon=":material/delete_forever:",
        type="primary",
        disabled=confirmation != node.label,
        use_container_width=True,
    ):
        return
    try:
        if node.node_type is MapNodeType.CHAPTER and chapter:
            delete_chapter(owner, chapter.project_id, chapter.id)
        elif node.node_type is MapNodeType.SCENE and scene:
            delete_scene(owner, scene.project_id, scene.id)
        elif node.node_type is MapNodeType.CHARACTER:
            delete_character(owner, project_id, node.entity_id)
        elif node.node_type is MapNodeType.SECTION and section:
            delete_section(owner, project_id, section.id)
        else:
            raise NarrativeMapLinkServiceError("Card inválido para exclusão.")
    except (
        CharacterServiceError,
        GddServiceError,
        NarrativeServiceError,
        SQLAlchemyError,
    ) as exc:
        _error(exc, "delete node")
        return
    set_flash("Card excluído do projeto.")
    st.rerun()
