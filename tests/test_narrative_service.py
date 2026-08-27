"""Narrative chapter/scene CRUD and ordering tests."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine

from services.narrative_service import (
    ChapterInput,
    NarrativeConflictError,
    NarrativeDirection,
    NarrativeNotFoundError,
    NarrativeServiceError,
    SceneInput,
    create_chapter,
    create_scene,
    delete_chapter,
    delete_scene,
    list_narrative,
    move_chapter,
    move_scene,
    update_chapter,
    update_scene,
)
from services.project_service import ProjectInput, create_project
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER = OwnerIdentity("Outro", "other@example.com")


def _project(engine: Engine):
    return create_project(OWNER, ProjectInput(name="Encouraçado"), engine)


def test_chapter_and_scene_crud_with_revisions(sqlite_engine: Engine) -> None:
    project_id = _project(sqlite_engine)
    chapter_id = create_chapter(
        OWNER,
        project_id,
        ChapterInput(" Capítulo 1 ", " O início. "),
        sqlite_engine,
    )
    scene_id = create_scene(
        OWNER,
        project_id,
        SceneInput(chapter_id, " Igreja ", " Primeiro encontro. ", "# Roteiro"),
        sqlite_engine,
    )

    chapter = list_narrative(OWNER, project_id, sqlite_engine)[0]
    assert chapter.title == "Capítulo 1"
    assert chapter.summary == "O início."
    assert len(chapter.scenes) == 1
    scene = chapter.scenes[0]
    assert scene.id == scene_id
    assert scene.title == "Igreja"
    assert scene.timeline_order == 1000

    update_chapter(
        OWNER,
        project_id,
        chapter_id,
        ChapterInput("Capítulo Um", "Revisado"),
        expected_revision=chapter.revision,
        engine=sqlite_engine,
    )
    update_scene(
        OWNER,
        project_id,
        scene_id,
        SceneInput(chapter_id, "Igreja abandonada", "Resumo", "Conteúdo"),
        expected_revision=scene.revision,
        engine=sqlite_engine,
    )
    updated = list_narrative(OWNER, project_id, sqlite_engine)[0]
    assert updated.title == "Capítulo Um"
    assert updated.scenes[0].title == "Igreja abandonada"

    with pytest.raises(NarrativeConflictError):
        update_chapter(
            OWNER,
            project_id,
            chapter_id,
            ChapterInput("Versão antiga"),
            expected_revision=chapter.revision,
            engine=sqlite_engine,
        )

    delete_scene(OWNER, project_id, scene_id, sqlite_engine)
    assert list_narrative(OWNER, project_id, sqlite_engine)[0].scenes == ()
    delete_chapter(OWNER, project_id, chapter_id, sqlite_engine)
    assert list_narrative(OWNER, project_id, sqlite_engine) == ()


def test_chapter_and_scene_order_resequences_timeline(sqlite_engine: Engine) -> None:
    project_id = _project(sqlite_engine)
    first = create_chapter(OWNER, project_id, ChapterInput("Primeiro"), sqlite_engine)
    second = create_chapter(OWNER, project_id, ChapterInput("Segundo"), sqlite_engine)
    scene_a = create_scene(OWNER, project_id, SceneInput(first, "A"), sqlite_engine)
    scene_b = create_scene(OWNER, project_id, SceneInput(first, "B"), sqlite_engine)
    create_scene(OWNER, project_id, SceneInput(second, "C"), sqlite_engine)

    assert move_scene(OWNER, project_id, scene_b, NarrativeDirection.UP, sqlite_engine)
    assert move_chapter(OWNER, project_id, second, NarrativeDirection.UP, sqlite_engine)
    chapters = list_narrative(OWNER, project_id, sqlite_engine)
    assert [chapter.title for chapter in chapters] == ["Segundo", "Primeiro"]
    assert [scene.title for scene in chapters[1].scenes] == ["B", "A"]
    timeline = sorted(
        (scene for chapter in chapters for scene in chapter.scenes),
        key=lambda scene: scene.timeline_order,
    )
    assert [scene.title for scene in timeline] == ["C", "B", "A"]
    assert [scene.timeline_order for scene in timeline] == [1000, 2000, 3000]
    assert not move_scene(OWNER, project_id, scene_a, NarrativeDirection.DOWN, sqlite_engine)


def test_scene_can_move_between_owned_chapters(sqlite_engine: Engine) -> None:
    project_id = _project(sqlite_engine)
    first = create_chapter(OWNER, project_id, ChapterInput("Um"), sqlite_engine)
    second = create_chapter(OWNER, project_id, ChapterInput("Dois"), sqlite_engine)
    scene_id = create_scene(OWNER, project_id, SceneInput(first, "Cena"), sqlite_engine)
    scene = list_narrative(OWNER, project_id, sqlite_engine)[0].scenes[0]

    update_scene(
        OWNER,
        project_id,
        scene_id,
        SceneInput(second, "Cena movida"),
        expected_revision=scene.revision,
        engine=sqlite_engine,
    )
    chapters = list_narrative(OWNER, project_id, sqlite_engine)
    assert chapters[0].scenes == ()
    assert chapters[1].scenes[0].title == "Cena movida"


def test_narrative_is_owner_scoped_and_chapter_delete_cascades(
    sqlite_engine: Engine,
) -> None:
    project_id = _project(sqlite_engine)
    chapter_id = create_chapter(OWNER, project_id, ChapterInput("Um"), sqlite_engine)
    create_scene(OWNER, project_id, SceneInput(chapter_id, "Cena"), sqlite_engine)

    with pytest.raises(NarrativeNotFoundError):
        list_narrative(OTHER, project_id, sqlite_engine)

    delete_chapter(OWNER, project_id, chapter_id, sqlite_engine)
    assert list_narrative(OWNER, project_id, sqlite_engine) == ()


@pytest.mark.parametrize(
    "chapter",
    [ChapterInput(""), ChapterInput("x" * 181), ChapterInput("Válido", "x" * 20_001)],
)
def test_invalid_chapter_is_rejected(
    sqlite_engine: Engine,
    chapter: ChapterInput,
) -> None:
    with pytest.raises(NarrativeServiceError):
        create_chapter(OWNER, _project(sqlite_engine), chapter, sqlite_engine)


def test_invalid_scene_and_cross_project_chapter_are_rejected(
    sqlite_engine: Engine,
) -> None:
    project_id = _project(sqlite_engine)
    other_project = create_project(OWNER, ProjectInput(name="Outro"), sqlite_engine)
    other_chapter = create_chapter(OWNER, other_project, ChapterInput("Externo"), sqlite_engine)
    with pytest.raises(NarrativeNotFoundError):
        create_scene(
            OWNER,
            project_id,
            SceneInput(other_chapter, "Inválida"),
            sqlite_engine,
        )
    with pytest.raises(NarrativeServiceError):
        create_scene(
            OWNER,
            project_id,
            SceneInput(other_chapter, ""),
            sqlite_engine,
        )
