"""Scene cast synchronization and calculated appearance timeline tests."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from models import SceneCharacter
from services.appearance_service import (
    AppearanceConflictError,
    AppearanceNotFoundError,
    AppearanceServiceError,
    get_character_timeline,
    get_project_appearance_index,
    sync_scene_characters,
    update_appearance_details,
)
from services.character_service import CharacterInput, create_character, delete_character
from services.database import session_scope
from services.narrative_service import (
    ChapterInput,
    NarrativeDirection,
    SceneInput,
    create_chapter,
    create_scene,
    delete_chapter,
    delete_scene,
    move_chapter,
    move_scene,
)
from services.project_service import ProjectInput, create_project
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER = OwnerIdentity("Outro", "other@example.com")


def _structure(engine: Engine):
    project_id = create_project(OWNER, ProjectInput(name="Projeto"), engine)
    chapter_id = create_chapter(OWNER, project_id, ChapterInput("Capítulo"), engine)
    scene_id = create_scene(OWNER, project_id, SceneInput(chapter_id, "Cena"), engine)
    first = create_character(OWNER, project_id, CharacterInput(name="Ana"), engine)
    second = create_character(OWNER, project_id, CharacterInput(name="Beto"), engine)
    return project_id, chapter_id, scene_id, first, second


def test_sync_scene_cast_adds_preserves_and_removes_links(sqlite_engine: Engine) -> None:
    project_id, _, scene_id, first, second = _structure(sqlite_engine)
    sync_scene_characters(
        OWNER,
        project_id,
        scene_id,
        [first, first],
        expected_character_ids=frozenset(),
        engine=sqlite_engine,
    )
    index = get_project_appearance_index(OWNER, project_id, sqlite_engine)
    assert [member.character_id for member in index.cast_for(scene_id)] == [first]

    update_appearance_details(
        OWNER,
        project_id,
        scene_id,
        first,
        role_in_scene="Protagoniza",
        notes="Primeira entrada.",
        engine=sqlite_engine,
    )
    sync_scene_characters(
        OWNER,
        project_id,
        scene_id,
        [first, second],
        expected_character_ids=frozenset({first}),
        engine=sqlite_engine,
    )
    cast = get_project_appearance_index(OWNER, project_id, sqlite_engine).cast_for(scene_id)
    assert {member.character_id for member in cast} == {first, second}
    preserved = next(member for member in cast if member.character_id == first)
    assert preserved.role_in_scene == "Protagoniza"
    assert preserved.notes == "Primeira entrada."

    sync_scene_characters(
        OWNER,
        project_id,
        scene_id,
        [second],
        expected_character_ids=frozenset({first, second}),
        engine=sqlite_engine,
    )
    assert [
        member.character_id
        for member in get_project_appearance_index(OWNER, project_id, sqlite_engine).cast_for(
            scene_id
        )
    ] == [second]

    sync_scene_characters(
        OWNER,
        project_id,
        scene_id,
        [],
        expected_character_ids=frozenset({second}),
        engine=sqlite_engine,
    )
    assert not get_project_appearance_index(OWNER, project_id, sqlite_engine).cast_for(scene_id)


def test_stale_cast_and_cross_project_character_are_rejected(
    sqlite_engine: Engine,
) -> None:
    project_id, _, scene_id, first, _ = _structure(sqlite_engine)
    sync_scene_characters(OWNER, project_id, scene_id, [first], engine=sqlite_engine)

    with pytest.raises(AppearanceConflictError):
        sync_scene_characters(
            OWNER,
            project_id,
            scene_id,
            [],
            expected_character_ids=frozenset(),
            engine=sqlite_engine,
        )

    other_project = create_project(OWNER, ProjectInput(name="Outro"), sqlite_engine)
    foreign = create_character(OWNER, other_project, CharacterInput(name="Externo"), sqlite_engine)
    with pytest.raises(AppearanceNotFoundError):
        sync_scene_characters(
            OWNER,
            project_id,
            scene_id,
            [first, foreign],
            expected_character_ids=frozenset({first}),
            engine=sqlite_engine,
        )
    assert [
        member.character_id
        for member in get_project_appearance_index(OWNER, project_id, sqlite_engine).cast_for(
            scene_id
        )
    ] == [first]

    with pytest.raises(AppearanceNotFoundError):
        get_project_appearance_index(OTHER, project_id, sqlite_engine)


def test_character_timeline_follows_narrative_order(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Projeto"), sqlite_engine)
    first_chapter = create_chapter(OWNER, project_id, ChapterInput("Primeiro"), sqlite_engine)
    second_chapter = create_chapter(OWNER, project_id, ChapterInput("Segundo"), sqlite_engine)
    scene_a = create_scene(OWNER, project_id, SceneInput(first_chapter, "Delegacia"), sqlite_engine)
    scene_b = create_scene(OWNER, project_id, SceneInput(first_chapter, "Igreja"), sqlite_engine)
    scene_c = create_scene(OWNER, project_id, SceneInput(second_chapter, "Hospital"), sqlite_engine)
    character = create_character(
        OWNER, project_id, CharacterInput(name="Protagonista"), sqlite_engine
    )
    for scene_id in (scene_a, scene_b, scene_c):
        sync_scene_characters(OWNER, project_id, scene_id, [character], engine=sqlite_engine)

    timeline = get_character_timeline(OWNER, project_id, character, sqlite_engine)
    assert [item.scene_title for item in timeline.items] == [
        "Delegacia",
        "Igreja",
        "Hospital",
    ]
    assert timeline.total == 3
    assert timeline.chapter_count == 2
    assert timeline.first and timeline.first.scene_title == "Delegacia"
    assert timeline.last and timeline.last.scene_title == "Hospital"

    move_scene(OWNER, project_id, scene_b, NarrativeDirection.UP, sqlite_engine)
    move_chapter(OWNER, project_id, second_chapter, NarrativeDirection.UP, sqlite_engine)
    reordered = get_character_timeline(OWNER, project_id, character, sqlite_engine)
    assert [item.scene_title for item in reordered.items] == [
        "Hospital",
        "Igreja",
        "Delegacia",
    ]


@pytest.mark.parametrize("target", ["character", "scene", "chapter"])
def test_links_are_deleted_by_database_cascade(
    sqlite_engine: Engine,
    target: str,
) -> None:
    project_id, chapter_id, scene_id, character_id, _ = _structure(sqlite_engine)
    sync_scene_characters(OWNER, project_id, scene_id, [character_id], engine=sqlite_engine)

    if target == "character":
        delete_character(OWNER, project_id, character_id, sqlite_engine)
    elif target == "scene":
        delete_scene(OWNER, project_id, scene_id, sqlite_engine)
    else:
        delete_chapter(OWNER, project_id, chapter_id, sqlite_engine)

    with session_scope(sqlite_engine) as session:
        assert session.scalar(select(SceneCharacter.id)) is None


def test_database_rejects_cross_project_link(sqlite_engine: Engine) -> None:
    project_id, _, scene_id, _, _ = _structure(sqlite_engine)
    other_project = create_project(OWNER, ProjectInput(name="Outro"), sqlite_engine)
    foreign = create_character(OWNER, other_project, CharacterInput(name="Externo"), sqlite_engine)

    with pytest.raises(IntegrityError), session_scope(sqlite_engine) as session:
        session.add(
            SceneCharacter(
                project_id=project_id,
                scene_id=scene_id,
                character_id=foreign,
            )
        )


def test_appearance_metadata_validation(sqlite_engine: Engine) -> None:
    project_id, _, scene_id, character_id, _ = _structure(sqlite_engine)
    sync_scene_characters(OWNER, project_id, scene_id, [character_id], engine=sqlite_engine)
    with pytest.raises(AppearanceServiceError):
        update_appearance_details(
            OWNER,
            project_id,
            scene_id,
            character_id,
            role_in_scene="x" * 121,
            notes=None,
            engine=sqlite_engine,
        )
