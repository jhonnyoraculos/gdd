"""Narrative graph aggregation and safe interactive document tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from components.narrative_map import narrative_map_document
from services.appearance_service import sync_scene_characters
from services.character_service import CharacterInput, create_character
from services.narrative_map_service import (
    MapEdgeType,
    MapMetric,
    MapNodeType,
    NarrativeMapEdge,
    NarrativeMapGraph,
    NarrativeMapNode,
    NarrativeMapNotFoundError,
    get_narrative_map,
)
from services.narrative_service import (
    ChapterInput,
    SceneInput,
    create_chapter,
    create_scene,
)
from services.project_service import ProjectInput, create_project
from services.relationship_service import RelationshipInput, create_relationship
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER = OwnerIdentity("Outro", "other@example.com")


def _graph_structure(engine: Engine):
    project_id = create_project(
        OWNER,
        ProjectInput(
            name="Encouraçado",
            codename="Projeto E",
            description="Terror brasileiro.",
            accent_color="#8B2635",
        ),
        engine,
    )
    chapter_id = create_chapter(
        OWNER,
        project_id,
        ChapterInput("Capítulo 1", "A investigação começa."),
        engine,
    )
    scene_id = create_scene(
        OWNER,
        project_id,
        SceneInput(
            chapter_id,
            "Igreja",
            "Primeiro encontro.",
            "## Interior\n\nO sino toca e o personagem entra.",
        ),
        engine,
    )
    protagonist = create_character(
        OWNER,
        project_id,
        CharacterInput(name="Protagonista", role="Protagonista"),
        engine,
    )
    creature = create_character(
        OWNER,
        project_id,
        CharacterInput(name="Encouraçado", role="Antagonista"),
        engine,
    )
    sync_scene_characters(
        OWNER,
        project_id,
        scene_id,
        [protagonist, creature],
        engine=engine,
    )
    relationship_id = create_relationship(
        OWNER,
        project_id,
        protagonist,
        creature,
        RelationshipInput("Inimigo", intensity=5, relationship_status="Ativa"),
        engine,
    )
    return project_id, chapter_id, scene_id, protagonist, creature, relationship_id


def test_map_assembles_real_nodes_edges_and_panel_details(sqlite_engine: Engine) -> None:
    project_id, chapter_id, scene_id, protagonist, creature, relationship_id = _graph_structure(
        sqlite_engine
    )

    graph = get_narrative_map(OWNER, project_id, sqlite_engine)

    assert graph.project_name == "Encouraçado"
    assert graph.accent_color == "#8B2635"
    assert graph.count(MapNodeType.PROJECT) == 1
    assert graph.count(MapNodeType.CHAPTER) == 1
    assert graph.count(MapNodeType.SCENE) == 1
    assert graph.count(MapNodeType.CHARACTER) == 2
    assert sum(edge.edge_type == MapEdgeType.HIERARCHY for edge in graph.edges) == 2
    assert sum(edge.edge_type == MapEdgeType.APPEARANCE for edge in graph.edges) == 2
    assert sum(edge.edge_type == MapEdgeType.RELATIONSHIP for edge in graph.edges) == 1

    chapter = next(node for node in graph.nodes if node.entity_id == chapter_id)
    assert chapter.items == ("Igreja",)
    assert f"chapter={chapter_id}" in chapter.href
    scene = next(node for node in graph.nodes if node.entity_id == scene_id)
    assert scene.items == ("Encouraçado", "Protagonista")
    assert scene.content == "## Interior\n\nO sino toca e o personagem entra."
    assert f"scene={scene_id}" in scene.href
    protagonist_node = next(node for node in graph.nodes if node.entity_id == protagonist)
    assert protagonist_node.items == ("Igreja",)
    assert protagonist_node.metrics == (
        MapMetric("Aparições", "1"),
        MapMetric("Relações", "1"),
    )
    relationship = next(
        edge for edge in graph.edges if edge.key == f"relationship:{relationship_id}"
    )
    assert relationship.source == f"character:{protagonist}"
    assert relationship.target == f"character:{creature}"
    assert relationship.label == "Inimigo"
    assert relationship.directed


def test_map_is_owner_scoped_and_empty_project_still_has_root(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Projeto vazio"), sqlite_engine)
    graph = get_narrative_map(OWNER, project_id, sqlite_engine)

    assert len(graph.nodes) == 1
    assert graph.nodes[0].node_type == MapNodeType.PROJECT
    assert graph.edges == ()
    with pytest.raises(NarrativeMapNotFoundError):
        get_narrative_map(OTHER, project_id, sqlite_engine)
    with pytest.raises(NarrativeMapNotFoundError):
        get_narrative_map(OWNER, uuid4(), sqlite_engine)


def test_map_connects_scenes_in_exact_narrative_order(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Cronologia"), sqlite_engine)
    first_act = create_chapter(OWNER, project_id, ChapterInput("Ato 1", "Início"), sqlite_engine)
    second_act = create_chapter(
        OWNER, project_id, ChapterInput("Ato 2", "Continuação"), sqlite_engine
    )
    first_scene = create_scene(
        OWNER,
        project_id,
        SceneInput(first_act, "Cena 1", "Primeiro fato", "Acontece primeiro."),
        sqlite_engine,
    )
    second_scene = create_scene(
        OWNER,
        project_id,
        SceneInput(first_act, "Cena 2", "Consequência", "Acontece depois."),
        sqlite_engine,
    )
    third_scene = create_scene(
        OWNER,
        project_id,
        SceneInput(second_act, "Cena 3", "Novo ato", "A história continua."),
        sqlite_engine,
    )

    graph = get_narrative_map(OWNER, project_id, sqlite_engine)
    sequence = [edge for edge in graph.edges if edge.edge_type == MapEdgeType.SEQUENCE]

    assert [(edge.source, edge.target) for edge in sequence] == [
        (f"scene:{first_scene}", f"scene:{second_scene}"),
        (f"scene:{second_scene}", f"scene:{third_scene}"),
    ]
    assert all(edge.directed and edge.label == "Próxima cena" for edge in sequence)
    second_scene_node = next(node for node in graph.nodes if node.entity_id == second_scene)
    assert [connection.subtitle for connection in second_scene_node.connections[:2]] == [
        "Sequência narrativa · Cena anterior",
        "Sequência narrativa · Próxima cena",
    ]


def test_interactive_document_encodes_user_content_and_has_controls() -> None:
    project_id = UUID("11111111-1111-1111-1111-111111111111")
    graph = NarrativeMapGraph(
        project_id=project_id,
        project_name="</script><script>alert(1)</script>",
        accent_color="not-a-color",
        nodes=(
            NarrativeMapNode(
                key=f"project:{project_id}",
                entity_id=project_id,
                node_type=MapNodeType.PROJECT,
                label="</script><img src=x onerror=alert(1)>",
                subtitle=None,
                description=None,
                href=f"/?view=project_detail&id={project_id}",
            ),
        ),
        edges=(
            NarrativeMapEdge(
                key="safe-edge",
                source=f"project:{project_id}",
                target=f"project:{project_id}",
                edge_type=MapEdgeType.HIERARCHY,
            ),
        ),
    )

    document = narrative_map_document(graph, "light")

    assert "</script><script>alert(1)</script>" not in document
    assert "\\u003c/script\\u003e" in document
    assert "--accent: #7C5CFC" in document
    assert 'data-theme="light"' in document
    assert 'id="zoomIn"' in document
    assert 'id="zoomOut"' in document
    assert 'id="fit"' in document
    assert 'id="reorganize"' in document
    assert "edge-sequence" in document
    assert "gdd-map-editor:v2" in document
    assert "pointerdown" in document
    assert "selectNode" in document
    assert "Conteúdo completo da cena" in document
    assert "Limpar seleção" in document
    assert 'svg.addEventListener("click"' not in document
