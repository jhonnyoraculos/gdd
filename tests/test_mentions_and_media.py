"""Automatic @mention connections and compressed GDD media tests."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import Engine

from components.narrative_map import narrative_map_document
from services.appearance_service import (
    get_project_appearance_index,
    sync_scene_characters,
)
from services.character_service import CharacterInput, create_character
from services.gdd_service import (
    GddNotFoundError,
    SectionInput,
    add_section_image,
    create_section,
    delete_section_image,
    get_section,
    list_section_images,
    update_section_content,
)
from services.mention_service import (
    ContentEntityType,
    ContentSourceType,
    list_mention_targets,
    list_source_connections,
)
from services.narrative_map_service import MapEdgeType, MapNodeType, get_narrative_map
from services.narrative_service import (
    ChapterInput,
    SceneInput,
    create_chapter,
    create_scene,
    list_narrative,
    update_scene,
)
from services.project_service import ProjectInput, create_project
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER = OwnerIdentity("Outro", "other@example.com")


def _png(width: int = 1600, height: int = 900) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "#8B2635").save(output, format="PNG")
    return output.getvalue()


def _connected_project(engine: Engine):
    project_id = create_project(OWNER, ProjectInput(name="Jogo"), engine)
    section_id = create_section(OWNER, project_id, SectionInput("Visão Geral"), engine)
    character_id = create_character(
        OWNER,
        project_id,
        CharacterInput(name="CORPO SECO"),
        engine=engine,
    )
    chapter_id = create_chapter(OWNER, project_id, ChapterInput("Capítulo 1"), engine)
    scene_id = create_scene(
        OWNER,
        project_id,
        SceneInput(chapter_id, "Cena 1"),
        engine,
    )
    return project_id, section_id, character_id, scene_id


def test_gdd_mentions_connect_all_supported_entities(sqlite_engine: Engine) -> None:
    project_id, section_id, character_id, scene_id = _connected_project(sqlite_engine)
    section = get_section(OWNER, project_id, section_id, sqlite_engine)

    update_section_content(
        OWNER,
        project_id,
        section_id,
        "O encontro de @corposeco acontece em @cena1.",
        section.revision,
        sqlite_engine,
    )

    connections = list_source_connections(
        OWNER,
        project_id,
        ContentSourceType.SECTION,
        section_id,
        sqlite_engine,
    )
    assert {(item.target_type, item.target_id) for item in connections} == {
        (ContentEntityType.CHARACTER, character_id),
        (ContentEntityType.SCENE, scene_id),
    }
    character_target = next(
        item
        for item in list_mention_targets(OWNER, project_id, sqlite_engine)
        if item.id == character_id
    )
    assert character_target.token == "@corposeco"

    graph = get_narrative_map(OWNER, project_id, sqlite_engine)
    assert graph.count(MapNodeType.SECTION) == 1
    assert any(edge.edge_type is MapEdgeType.MENTION for edge in graph.edges)
    document = narrative_map_document(graph, "light")
    assert "node-section" in document
    assert "edge-mention" in document


def test_scene_mention_adds_and_safely_removes_generated_cast(sqlite_engine: Engine) -> None:
    project_id, _section_id, character_id, scene_id = _connected_project(sqlite_engine)
    scene = list_narrative(OWNER, project_id, sqlite_engine)[0].scenes[0]
    update_scene(
        OWNER,
        project_id,
        scene_id,
        SceneInput(scene.chapter_id, scene.title, content="Entra @corposeco."),
        expected_revision=scene.revision,
        engine=sqlite_engine,
    )
    assert [
        item.character_id
        for item in get_project_appearance_index(OWNER, project_id, sqlite_engine).cast_for(
            scene_id
        )
    ] == [character_id]

    mentioned_scene = list_narrative(OWNER, project_id, sqlite_engine)[0].scenes[0]
    update_scene(
        OWNER,
        project_id,
        scene_id,
        SceneInput(mentioned_scene.chapter_id, mentioned_scene.title, content="Cena vazia."),
        expected_revision=mentioned_scene.revision,
        engine=sqlite_engine,
    )
    assert not get_project_appearance_index(OWNER, project_id, sqlite_engine).cast_for(scene_id)

    refreshed = list_narrative(OWNER, project_id, sqlite_engine)[0].scenes[0]
    update_scene(
        OWNER,
        project_id,
        scene_id,
        SceneInput(refreshed.chapter_id, refreshed.title, content="@corposeco"),
        expected_revision=refreshed.revision,
        engine=sqlite_engine,
    )
    sync_scene_characters(
        OWNER,
        project_id,
        scene_id,
        [character_id],
        engine=sqlite_engine,
    )
    manual = list_narrative(OWNER, project_id, sqlite_engine)[0].scenes[0]
    update_scene(
        OWNER,
        project_id,
        scene_id,
        SceneInput(manual.chapter_id, manual.title, content="Sem menção."),
        expected_revision=manual.revision,
        engine=sqlite_engine,
    )
    assert get_project_appearance_index(OWNER, project_id, sqlite_engine).cast_for(scene_id)


def test_gdd_images_are_converted_to_480p_webp(sqlite_engine: Engine) -> None:
    project_id, section_id, _character_id, _scene_id = _connected_project(sqlite_engine)
    image_id = add_section_image(
        OWNER,
        project_id,
        section_id,
        _png(),
        "Referência",
        sqlite_engine,
    )

    images = list_section_images(OWNER, project_id, section_id, sqlite_engine)
    assert len(images) == 1
    assert images[0].mime_type == "image/webp"
    assert images[0].width <= 854
    assert images[0].height <= 480
    assert images[0].caption == "Referência"
    with Image.open(BytesIO(images[0].image_data)) as stored:
        assert stored.format == "WEBP"
        assert stored.width <= 854
        assert stored.height <= 480

    with pytest.raises(GddNotFoundError):
        list_section_images(OTHER, project_id, section_id, sqlite_engine)
    delete_section_image(OWNER, project_id, section_id, image_id, sqlite_engine)
    assert list_section_images(OWNER, project_id, section_id, sqlite_engine) == ()
