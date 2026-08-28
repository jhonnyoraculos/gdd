"""Project CRUD, ownership, filtering and aggregate tests."""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import Engine, select

from models import Chapter, Character, GddSection, Project, Scene, User
from services.database import session_scope
from services.project_service import (
    ProjectInput,
    ProjectNotFoundError,
    ProjectSort,
    ProjectValidationError,
    create_project,
    delete_project,
    get_project,
    list_projects,
    set_project_archived,
    toggle_project_favorite,
    update_project,
)
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER_OWNER = OwnerIdentity("Outra pessoa", "other@example.com")


def _png_bytes(width: int = 1200, height: int = 900) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "#6D45E8").save(output, format="PNG")
    return output.getvalue()


def test_project_crud_round_trip_is_scoped_to_owner(sqlite_engine: Engine) -> None:
    project_id = create_project(
        OWNER,
        ProjectInput(
            name=" Encouraçado ",
            genre=" Horror ",
            platform=" PC ",
            start_date=date(2026, 8, 27),
        ),
        sqlite_engine,
    )

    project = get_project(OWNER, project_id, sqlite_engine)
    assert project.name == "Encouraçado"
    assert project.genre == "Horror"
    assert project.platform == "PC"
    assert project.start_date == date(2026, 8, 27)

    with pytest.raises(ProjectNotFoundError):
        get_project(OTHER_OWNER, project_id, sqlite_engine)

    update_project(
        OWNER,
        project_id,
        ProjectInput(name="Encouraçado II", status="concept", accent_color="#112233"),
        sqlite_engine,
    )
    updated = get_project(OWNER, project_id, sqlite_engine)
    assert updated.name == "Encouraçado II"
    assert updated.status == "concept"
    assert updated.accent_color == "#112233"

    delete_project(OWNER, project_id, sqlite_engine)
    with pytest.raises(ProjectNotFoundError):
        get_project(OWNER, project_id, sqlite_engine)


def test_list_filters_sort_and_pagination(sqlite_engine: Engine) -> None:
    for name, genre in (("Zênite", "RPG"), ("Aurora", "Aventura"), ("Projeto 100%", "Puzzle")):
        create_project(OWNER, ProjectInput(name=name, genre=genre), sqlite_engine)

    first_page = list_projects(
        OWNER,
        sort=ProjectSort.NAME_ASC,
        page=1,
        page_size=2,
        engine=sqlite_engine,
    )
    assert first_page.total == 3
    assert first_page.total_pages == 2
    assert [item.name for item in first_page.items] == ["Aurora", "Projeto 100%"]

    literal_percent = list_projects(OWNER, search="100%", engine=sqlite_engine)
    assert [item.name for item in literal_percent.items] == ["Projeto 100%"]

    by_genre = list_projects(OWNER, search="aventura", engine=sqlite_engine)
    assert [item.name for item in by_genre.items] == ["Aurora"]


def test_favorite_and_archive_views_are_persistent(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Favorito"), sqlite_engine)

    assert toggle_project_favorite(OWNER, project_id, sqlite_engine)
    favorites = list_projects(
        OWNER,
        archived=None,
        favorite=True,
        engine=sqlite_engine,
    )
    assert [project.id for project in favorites.items] == [project_id]

    set_project_archived(OWNER, project_id, True, sqlite_engine)
    assert list_projects(OWNER, engine=sqlite_engine).total == 0
    archived = list_projects(OWNER, archived=True, engine=sqlite_engine)
    assert archived.total == 1
    assert archived.items[0].archived
    assert get_project(OWNER, project_id, sqlite_engine).archived_at is not None

    set_project_archived(OWNER, project_id, False, sqlite_engine)
    assert list_projects(OWNER, engine=sqlite_engine).total == 1
    assert get_project(OWNER, project_id, sqlite_engine).archived_at is None


def test_project_aggregates_and_progress(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Com conteúdo"), sqlite_engine)
    with session_scope(sqlite_engine) as session:
        project = session.get(Project, project_id)
        assert project is not None
        chapter = Chapter(project=project, title="Capítulo")
        session.add_all(
            [
                GddSection(project=project, title="Visão", status="finished"),
                GddSection(project=project, title="Gameplay", status="draft"),
                Character(
                    project=project,
                    name="Protagonista",
                    normalized_name="protagonista",
                ),
                chapter,
                Scene(project=project, chapter=chapter, title="Cena", timeline_order=1000),
            ]
        )

    project = get_project(OWNER, project_id, sqlite_engine)
    assert project.section_count == 2
    assert project.finished_section_count == 1
    assert project.progress == 50
    assert project.character_count == 1
    assert project.chapter_count == 1
    assert project.scene_count == 1


def test_uploaded_cover_round_trip_and_source(sqlite_engine: Engine) -> None:
    image = _png_bytes()
    project_id = create_project(
        OWNER,
        ProjectInput(
            name="Projeto com capa",
            cover_image=image,
            cover_image_mime="application/octet-stream",
        ),
        sqlite_engine,
    )

    project = get_project(OWNER, project_id, sqlite_engine)
    assert project.cover_url is None
    assert project.cover_image is not None
    assert project.cover_image != image
    assert project.cover_image_mime == "image/webp"
    assert project.cover_source is not None
    assert project.cover_source.startswith("data:image/webp;base64,")
    with Image.open(BytesIO(project.cover_image)) as stored:
        assert stored.size == (640, 480)

    listed = list_projects(OWNER, engine=sqlite_engine).items[0]
    assert listed.cover_image == project.cover_image
    assert listed.cover_source == project.cover_source


@pytest.mark.parametrize(
    "data",
    [
        ProjectInput(name=""),
        ProjectInput(name="Projeto", status="unknown"),
        ProjectInput(name="Projeto", accent_color="red"),
        ProjectInput(name="Projeto", cover_url="javascript:alert(1)"),
        ProjectInput(name="Projeto", cover_image=b"not-an-image"),
        ProjectInput(
            name="Projeto",
            cover_image=b"x" * (10 * 1024 * 1024 + 1),
        ),
    ],
)
def test_invalid_project_input_is_rejected(
    sqlite_engine: Engine,
    data: ProjectInput,
) -> None:
    with pytest.raises(ProjectValidationError):
        create_project(OWNER, data, sqlite_engine)

    with session_scope(sqlite_engine) as session:
        assert (
            session.scalar(select(User).where(User.email_normalized == OWNER.normalized_email))
            is None
        )
