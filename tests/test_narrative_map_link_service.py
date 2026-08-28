"""Manual visual connections stay scoped, unique and cascade safely."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import Engine

from services.character_service import CharacterInput, create_character
from services.gdd_service import SectionInput, create_section
from services.narrative_map_link_service import (
    MapEntityType,
    NarrativeMapLinkInput,
    NarrativeMapLinkNotFoundError,
    NarrativeMapLinkValidationError,
    create_narrative_map_link,
    delete_narrative_map_link,
    parse_node_key,
)
from services.narrative_map_service import MapEdgeType, get_narrative_map
from services.narrative_service import (
    ChapterInput,
    SceneInput,
    create_chapter,
    create_scene,
    delete_scene,
)
from services.project_service import ProjectInput, create_project
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER = OwnerIdentity("Outro", "other@example.com")


def _project_nodes(engine: Engine):
    project_id = create_project(OWNER, ProjectInput(name="Projeto"), engine)
    chapter_id = create_chapter(OWNER, project_id, ChapterInput("Capítulo"), engine)
    scene_id = create_scene(
        OWNER,
        project_id,
        SceneInput(chapter_id, "Cena"),
        engine,
    )
    character_id = create_character(
        OWNER,
        project_id,
        CharacterInput(name="Personagem"),
        engine=engine,
    )
    section_id = create_section(
        OWNER,
        project_id,
        SectionInput("Seção"),
        engine,
    )
    return project_id, scene_id, character_id, section_id


def test_manual_link_round_trip_and_inverse_duplicate(sqlite_engine: Engine) -> None:
    project_id, scene_id, character_id, _section_id = _project_nodes(sqlite_engine)
    link_id = create_narrative_map_link(
        OWNER,
        project_id,
        NarrativeMapLinkInput(
            MapEntityType.SCENE,
            scene_id,
            MapEntityType.CHARACTER,
            character_id,
            "  observa  ",
        ),
        sqlite_engine,
    )

    graph = get_narrative_map(OWNER, project_id, sqlite_engine)
    edge = next(item for item in graph.edges if item.key == f"manual:{link_id}")
    assert edge.edge_type is MapEdgeType.MANUAL
    assert edge.label == "observa"
    assert edge.removable
    scene = next(item for item in graph.nodes if item.entity_id == scene_id)
    assert any(item.edge_key == edge.key for item in scene.connections)

    with pytest.raises(NarrativeMapLinkValidationError):
        create_narrative_map_link(
            OWNER,
            project_id,
            NarrativeMapLinkInput(
                MapEntityType.CHARACTER,
                character_id,
                MapEntityType.SCENE,
                scene_id,
            ),
            sqlite_engine,
        )

    delete_narrative_map_link(OWNER, project_id, link_id, sqlite_engine)
    refreshed = get_narrative_map(OWNER, project_id, sqlite_engine)
    assert all(item.key != f"manual:{link_id}" for item in refreshed.edges)


def test_manual_link_validates_owner_endpoints_and_self(sqlite_engine: Engine) -> None:
    project_id, scene_id, _character_id, section_id = _project_nodes(sqlite_engine)
    other_project = create_project(OWNER, ProjectInput(name="Outro projeto"), sqlite_engine)
    other_section = create_section(
        OWNER,
        other_project,
        SectionInput("Fora"),
        sqlite_engine,
    )

    with pytest.raises(NarrativeMapLinkNotFoundError):
        create_narrative_map_link(
            OTHER,
            project_id,
            NarrativeMapLinkInput(
                MapEntityType.SCENE,
                scene_id,
                MapEntityType.SECTION,
                section_id,
            ),
            sqlite_engine,
        )
    with pytest.raises(NarrativeMapLinkNotFoundError):
        create_narrative_map_link(
            OWNER,
            project_id,
            NarrativeMapLinkInput(
                MapEntityType.SCENE,
                scene_id,
                MapEntityType.SECTION,
                other_section,
            ),
            sqlite_engine,
        )
    with pytest.raises(NarrativeMapLinkValidationError):
        create_narrative_map_link(
            OWNER,
            project_id,
            NarrativeMapLinkInput(
                MapEntityType.SCENE,
                scene_id,
                MapEntityType.SCENE,
                scene_id,
            ),
            sqlite_engine,
        )
    with pytest.raises(NarrativeMapLinkValidationError):
        parse_node_key(f"project:{uuid4()}")


def test_manual_link_is_deleted_when_card_is_deleted(sqlite_engine: Engine) -> None:
    project_id, scene_id, _character_id, section_id = _project_nodes(sqlite_engine)
    link_id = create_narrative_map_link(
        OWNER,
        project_id,
        NarrativeMapLinkInput(
            MapEntityType.SCENE,
            scene_id,
            MapEntityType.SECTION,
            section_id,
            directed=True,
        ),
        sqlite_engine,
    )

    delete_scene(OWNER, project_id, scene_id, sqlite_engine)
    graph = get_narrative_map(OWNER, project_id, sqlite_engine)
    assert all(item.key != f"manual:{link_id}" for item in graph.edges)
