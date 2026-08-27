"""Hierarchical GDD service tests."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine

from services.gdd_service import (
    GddConflictError,
    GddNotFoundError,
    MoveDirection,
    SectionInput,
    create_section,
    delete_section,
    get_section,
    initialize_complete_template,
    list_sections,
    move_section,
    update_section_content,
    update_section_metadata,
)
from services.gdd_templates import COMPLETE_GDD_TEMPLATE
from services.project_service import ProjectInput, create_project, get_project
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER = OwnerIdentity("Outro", "other@example.com")


def test_complete_template_is_created_once(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Jogo"), sqlite_engine)
    initialize_complete_template(OWNER, project_id, sqlite_engine)

    sections = list_sections(OWNER, project_id, sqlite_engine)
    expected_total = len(COMPLETE_GDD_TEMPLATE) + sum(
        len(children) for _, _, children in COMPLETE_GDD_TEMPLATE
    )
    assert len([section for section in sections if section.parent_id is None]) == 16
    assert len(sections) == expected_total
    assert get_project(OWNER, project_id, sqlite_engine).template_key == "complete"

    with pytest.raises(GddConflictError):
        initialize_complete_template(OWNER, project_id, sqlite_engine)


def test_project_creation_can_include_template(sqlite_engine: Engine) -> None:
    project_id = create_project(
        OWNER,
        ProjectInput(name="Pronto", template_key="complete"),
        sqlite_engine,
    )
    assert len(list_sections(OWNER, project_id, sqlite_engine)) > 16


def test_section_crud_and_owner_scope(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Jogo"), sqlite_engine)
    category_id = create_section(
        OWNER,
        project_id,
        SectionInput("Personagens", "♟", "category"),
        sqlite_engine,
    )
    page_id = create_section(
        OWNER,
        project_id,
        SectionInput("Protagonista", parent_id=category_id),
        sqlite_engine,
    )
    update_section_metadata(
        OWNER,
        project_id,
        page_id,
        SectionInput("Heroína", "✦", "page", category_id, "draft"),
        sqlite_engine,
    )
    assert get_section(OWNER, project_id, page_id, sqlite_engine).title == "Heroína"

    with pytest.raises(GddNotFoundError):
        get_section(OTHER, project_id, page_id, sqlite_engine)

    delete_section(OWNER, project_id, category_id, sqlite_engine)
    assert list_sections(OWNER, project_id, sqlite_engine) == ()


def test_content_update_uses_optimistic_revision(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Jogo"), sqlite_engine)
    section_id = create_section(OWNER, project_id, SectionInput("História"), sqlite_engine)
    original = get_section(OWNER, project_id, section_id, sqlite_engine)

    new_revision = update_section_content(
        OWNER,
        project_id,
        section_id,
        "# História\n\nEra uma vez.",
        original.revision,
        sqlite_engine,
    )
    assert new_revision == original.revision + 1
    assert get_section(OWNER, project_id, section_id, sqlite_engine).content.startswith(
        "# História"
    )

    with pytest.raises(GddConflictError):
        update_section_content(
            OWNER,
            project_id,
            section_id,
            "conteúdo antigo",
            original.revision,
            sqlite_engine,
        )


def test_sibling_order_can_move_up_and_down(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Jogo"), sqlite_engine)
    first = create_section(OWNER, project_id, SectionInput("Primeira"), sqlite_engine)
    second = create_section(OWNER, project_id, SectionInput("Segunda"), sqlite_engine)

    assert move_section(OWNER, project_id, second, MoveDirection.UP, sqlite_engine)
    ordered = sorted(
        list_sections(OWNER, project_id, sqlite_engine), key=lambda item: item.position
    )
    assert [item.id for item in ordered] == [second, first]
    assert move_section(OWNER, project_id, second, MoveDirection.DOWN, sqlite_engine)
    assert not move_section(OWNER, project_id, second, MoveDirection.DOWN, sqlite_engine)
