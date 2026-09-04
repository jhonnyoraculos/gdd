"""Connection image and user-defined ordering tests."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import Engine

from services.narrative_map_edge_service import (
    NarrativeMapEdgeMediaError,
    list_edge_decorations,
    reorder_edges,
    save_edge_decoration,
)
from services.narrative_map_service import MapEdgeType, get_narrative_map
from services.narrative_service import ChapterInput, SceneInput, create_chapter, create_scene
from services.project_service import ProjectInput, create_project
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "edge-media@example.com")


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1600, 900), "#336699").save(output, format="PNG")
    return output.getvalue()


def test_edge_image_is_480p_and_connections_follow_chosen_order(
    sqlite_engine: Engine,
) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Mapa"), sqlite_engine)
    chapter_id = create_chapter(OWNER, project_id, ChapterInput("Ato 1"), sqlite_engine)
    first = create_scene(OWNER, project_id, SceneInput(chapter_id, "Cena 1"), sqlite_engine)
    create_scene(OWNER, project_id, SceneInput(chapter_id, "Cena 2"), sqlite_engine)
    graph = get_narrative_map(OWNER, project_id, sqlite_engine)
    scene = next(node for node in graph.nodes if node.entity_id == first)
    valid = frozenset(edge.key for edge in graph.edges)
    hierarchy = next(
        item.edge_key for item in scene.connections if item.edge_key.startswith("chapter-scene:")
    )
    sequence = next(edge.key for edge in graph.edges if edge.edge_type is MapEdgeType.SEQUENCE)

    save_edge_decoration(
        OWNER,
        project_id,
        hierarchy,
        valid,
        caption="Referência da passagem",
        image_data=_png_bytes(),
        engine=sqlite_engine,
    )
    reorder_edges(
        OWNER,
        project_id,
        (hierarchy, sequence),
        valid,
        sqlite_engine,
    )

    decoration = next(
        item
        for item in list_edge_decorations(OWNER, project_id, sqlite_engine)
        if item.edge_key == hierarchy
    )
    assert decoration.image_mime == "image/webp"
    assert decoration.image_width is not None and decoration.image_width <= 854
    assert decoration.image_height is not None and decoration.image_height <= 480
    refreshed = get_narrative_map(OWNER, project_id, sqlite_engine)
    refreshed_scene = next(node for node in refreshed.nodes if node.entity_id == first)
    assert [item.edge_key for item in refreshed_scene.connections[:2]] == [
        hierarchy,
        sequence,
    ]
    assert refreshed_scene.connections[0].image_source.startswith("data:image/webp;base64,")


def test_edge_decoration_rejects_unknown_edge(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Mapa"), sqlite_engine)
    with pytest.raises(NarrativeMapEdgeMediaError):
        save_edge_decoration(
            OWNER,
            project_id,
            "manual:inexistente",
            frozenset(),
            image_data=_png_bytes(),
            engine=sqlite_engine,
        )
