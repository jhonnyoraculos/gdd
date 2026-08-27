"""Character CRUD, ownership, validation and listing tests."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import Engine

from services.character_service import (
    CharacterConflictError,
    CharacterInput,
    CharacterNotFoundError,
    CharacterSort,
    CharacterValidationError,
    create_character,
    delete_character,
    get_character,
    list_character_roles,
    list_characters,
    update_character,
)
from services.project_service import ProjectInput, create_project
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER_OWNER = OwnerIdentity("Outra pessoa", "other@example.com")


def _project(engine: Engine, name: str = "Encouraçado"):
    return create_project(OWNER, ProjectInput(name=name), engine)


def test_character_crud_round_trip_and_revision(sqlite_engine: Engine) -> None:
    project_id = _project(sqlite_engine)
    character_id = create_character(
        OWNER,
        project_id,
        CharacterInput(
            name=" Encouraçado ",
            full_name="A Entidade Encouraçada",
            nickname="Couraça",
            role="Antagonista",
            age=137,
            birth_date=date(1889, 5, 7),
            story="Uma história extensa.",
            external_goal="Abrir o portal.",
            image_url="https://example.com/character.png",
        ),
        sqlite_engine,
    )

    created = get_character(OWNER, project_id, character_id, sqlite_engine)
    assert created.name == "Encouraçado"
    assert created.profile.role == "Antagonista"
    assert created.profile.birth_date == date(1889, 5, 7)
    assert created.revision == 1

    update_character(
        OWNER,
        project_id,
        character_id,
        CharacterInput(name="Encouraçado", role="Criatura", story="História revisada."),
        expected_revision=created.revision,
        engine=sqlite_engine,
    )
    updated = get_character(OWNER, project_id, character_id, sqlite_engine)
    assert updated.profile.role == "Criatura"
    assert updated.profile.story == "História revisada."
    assert updated.revision == 2

    with pytest.raises(CharacterConflictError):
        update_character(
            OWNER,
            project_id,
            character_id,
            CharacterInput(name="Versão antiga"),
            expected_revision=created.revision,
            engine=sqlite_engine,
        )

    delete_character(OWNER, project_id, character_id, sqlite_engine)
    with pytest.raises(CharacterNotFoundError):
        get_character(OWNER, project_id, character_id, sqlite_engine)


def test_character_access_is_scoped_to_project_owner(sqlite_engine: Engine) -> None:
    project_id = _project(sqlite_engine)
    character_id = create_character(
        OWNER, project_id, CharacterInput(name="Protagonista"), sqlite_engine
    )

    with pytest.raises(CharacterNotFoundError):
        get_character(OTHER_OWNER, project_id, character_id, sqlite_engine)
    with pytest.raises(CharacterNotFoundError):
        list_characters(OTHER_OWNER, project_id, engine=sqlite_engine)


def test_character_search_roles_sort_and_pagination(sqlite_engine: Engine) -> None:
    project_id = _project(sqlite_engine)
    create_character(
        OWNER,
        project_id,
        CharacterInput(name="Zara", role="Aliado", codename="Aurora"),
        sqlite_engine,
    )
    create_character(
        OWNER,
        project_id,
        CharacterInput(name="Álvaro", role="Antagonista", nickname="Chefe"),
        sqlite_engine,
    )

    result = list_characters(
        OWNER,
        project_id,
        sort=CharacterSort.NAME_DESC,
        page_size=1,
        engine=sqlite_engine,
    )
    assert result.total == 2
    assert result.total_pages == 2
    assert len(result.items) == 1

    search = list_characters(OWNER, project_id, search="Aurora", engine=sqlite_engine)
    assert [item.name for item in search.items] == ["Zara"]
    filtered = list_characters(OWNER, project_id, role="Antagonista", engine=sqlite_engine)
    assert [item.name for item in filtered.items] == ["Álvaro"]
    assert list_character_roles(OWNER, project_id, sqlite_engine) == (
        "Aliado",
        "Antagonista",
    )


@pytest.mark.parametrize(
    "data",
    [
        CharacterInput(name=""),
        CharacterInput(name="Personagem", age=-1),
        CharacterInput(name="Personagem", age=1000),
        CharacterInput(name="Personagem", image_url="javascript:alert(1)"),
    ],
)
def test_invalid_character_input_is_rejected(
    sqlite_engine: Engine,
    data: CharacterInput,
) -> None:
    project_id = _project(sqlite_engine)
    with pytest.raises(CharacterValidationError):
        create_character(OWNER, project_id, data, sqlite_engine)


def test_duplicate_character_names_are_rejected_case_insensitively(
    sqlite_engine: Engine,
) -> None:
    project_id = _project(sqlite_engine)
    create_character(OWNER, project_id, CharacterInput(name="Exu Caveira"), sqlite_engine)

    with pytest.raises(CharacterValidationError):
        create_character(OWNER, project_id, CharacterInput(name="exu caveira"), sqlite_engine)
