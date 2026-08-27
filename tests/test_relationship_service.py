"""Directional character relationship CRUD, scoping and integrity tests."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from models import Character, CharacterRelationship
from services.character_service import CharacterInput, create_character, delete_character
from services.database import session_scope
from services.project_service import ProjectInput, create_project, get_project
from services.relationship_service import (
    RelationshipConflictError,
    RelationshipInput,
    RelationshipNotFoundError,
    RelationshipValidationError,
    create_relationship,
    delete_relationship,
    get_relationship,
    list_character_relationships,
    list_project_relationships,
    update_relationship,
)
from services.user_service import OwnerIdentity

OWNER = OwnerIdentity("Criador", "creator@example.com")
OTHER = OwnerIdentity("Outro", "other@example.com")


def _characters(engine: Engine):
    project_id = create_project(OWNER, ProjectInput(name="Projeto"), engine)
    ana = create_character(
        OWNER,
        project_id,
        CharacterInput(name="Ana", role="Protagonista"),
        engine,
    )
    beto = create_character(
        OWNER,
        project_id,
        CharacterInput(name="Beto", role="Aliado"),
        engine,
    )
    clara = create_character(
        OWNER,
        project_id,
        CharacterInput(name="Clara", role="Antagonista"),
        engine,
    )
    return project_id, ana, beto, clara


def test_relationship_crud_revision_and_project_timestamp(sqlite_engine: Engine) -> None:
    project_id, ana, beto, _ = _characters(sqlite_engine)
    previous_project_update = get_project(OWNER, project_id, sqlite_engine).updated_at
    relationship_id = create_relationship(
        OWNER,
        project_id,
        ana,
        beto,
        RelationshipInput(
            "  Melhor amiga  ",
            "  Confiança antiga.  ",
            intensity=4,
            relationship_status="  Ativa  ",
        ),
        sqlite_engine,
    )

    created = get_relationship(OWNER, project_id, relationship_id, sqlite_engine)
    assert created.source_name == "Ana"
    assert created.source_role == "Protagonista"
    assert created.target_name == "Beto"
    assert created.target_role == "Aliado"
    assert created.relationship_type == "Melhor amiga"
    assert created.description == "Confiança antiga."
    assert created.intensity == 4
    assert created.relationship_status == "Ativa"
    assert created.revision == 1
    assert get_project(OWNER, project_id, sqlite_engine).updated_at >= previous_project_update

    update_relationship(
        OWNER,
        project_id,
        relationship_id,
        RelationshipInput(
            "Rival",
            "Disputam o mesmo objetivo.",
            intensity=5,
            relationship_status="Rompida",
        ),
        expected_revision=created.revision,
        engine=sqlite_engine,
    )
    updated = get_relationship(OWNER, project_id, relationship_id, sqlite_engine)
    assert updated.relationship_type == "Rival"
    assert updated.description == "Disputam o mesmo objetivo."
    assert updated.intensity == 5
    assert updated.relationship_status == "Rompida"
    assert updated.revision == 2

    with pytest.raises(RelationshipConflictError):
        update_relationship(
            OWNER,
            project_id,
            relationship_id,
            RelationshipInput("Aliado"),
            expected_revision=created.revision,
            engine=sqlite_engine,
        )
    with pytest.raises(RelationshipConflictError):
        delete_relationship(
            OWNER,
            project_id,
            relationship_id,
            expected_revision=created.revision,
            engine=sqlite_engine,
        )

    delete_relationship(
        OWNER,
        project_id,
        relationship_id,
        expected_revision=updated.revision,
        engine=sqlite_engine,
    )
    with pytest.raises(RelationshipNotFoundError):
        get_relationship(OWNER, project_id, relationship_id, sqlite_engine)


def test_directional_lists_and_project_choices_are_calculated(
    sqlite_engine: Engine,
) -> None:
    project_id, ana, beto, clara = _characters(sqlite_engine)
    ana_to_beto = create_relationship(
        OWNER, project_id, ana, beto, RelationshipInput("Protege"), sqlite_engine
    )
    beto_to_ana = create_relationship(
        OWNER, project_id, beto, ana, RelationshipInput("Admira"), sqlite_engine
    )
    clara_to_ana = create_relationship(
        OWNER, project_id, clara, ana, RelationshipInput("Persegue"), sqlite_engine
    )

    index = list_character_relationships(OWNER, project_id, ana, sqlite_engine)
    assert [choice.name for choice in index.choices] == ["Ana", "Beto", "Clara"]
    assert [item.id for item in index.outgoing] == [ana_to_beto]
    assert {item.id for item in index.incoming} == {beto_to_ana, clara_to_ana}
    assert index.total == 3

    project_index = list_project_relationships(OWNER, project_id, sqlite_engine)
    assert len(project_index.relationships) == 3
    assert project_index.outgoing_for(ana) == index.outgoing
    assert {item.id for item in project_index.incoming_for(ana)} == {
        beto_to_ana,
        clara_to_ana,
    }


def test_relationship_choices_are_not_paginated(sqlite_engine: Engine) -> None:
    project_id = create_project(OWNER, ProjectInput(name="Elenco grande"), sqlite_engine)
    with session_scope(sqlite_engine) as session:
        characters = [
            Character(
                project_id=project_id,
                name=f"Personagem {index:02}",
                normalized_name=f"personagem {index:02}",
            )
            for index in range(65)
        ]
        session.add_all(characters)
        session.flush()
        character_id = characters[0].id

    index = list_character_relationships(OWNER, project_id, character_id, sqlite_engine)
    assert len(index.choices) == 65


def test_duplicate_self_cross_project_and_owner_access_are_rejected(
    sqlite_engine: Engine,
) -> None:
    project_id, ana, beto, _ = _characters(sqlite_engine)
    relationship_id = create_relationship(
        OWNER, project_id, ana, beto, RelationshipInput("Aliado"), sqlite_engine
    )

    with pytest.raises(RelationshipValidationError, match="direção"):
        create_relationship(
            OWNER, project_id, ana, beto, RelationshipInput("Inimigo"), sqlite_engine
        )
    inverse_id = create_relationship(
        OWNER, project_id, beto, ana, RelationshipInput("Amigo"), sqlite_engine
    )
    assert inverse_id != relationship_id

    with pytest.raises(RelationshipValidationError, match="diferentes"):
        create_relationship(OWNER, project_id, ana, ana, RelationshipInput("Eu"), sqlite_engine)

    other_project = create_project(OWNER, ProjectInput(name="Outro projeto"), sqlite_engine)
    foreign = create_character(OWNER, other_project, CharacterInput(name="Externo"), sqlite_engine)
    with pytest.raises(RelationshipNotFoundError):
        create_relationship(
            OWNER, project_id, ana, foreign, RelationshipInput("Desconhecido"), sqlite_engine
        )
    with pytest.raises(RelationshipNotFoundError):
        get_relationship(OTHER, project_id, relationship_id, sqlite_engine)
    with pytest.raises(RelationshipNotFoundError):
        list_character_relationships(OTHER, project_id, ana, sqlite_engine)


@pytest.mark.parametrize("deleted_endpoint", ["source", "target"])
def test_relationships_cascade_when_either_character_is_deleted(
    sqlite_engine: Engine,
    deleted_endpoint: str,
) -> None:
    project_id, ana, beto, _ = _characters(sqlite_engine)
    create_relationship(OWNER, project_id, ana, beto, RelationshipInput("Aliado"), sqlite_engine)

    delete_character(
        OWNER,
        project_id,
        ana if deleted_endpoint == "source" else beto,
        sqlite_engine,
    )
    with session_scope(sqlite_engine) as session:
        assert session.scalar(select(CharacterRelationship.id)) is None


def test_database_enforces_relationship_constraints(sqlite_engine: Engine) -> None:
    project_id, ana, beto, _ = _characters(sqlite_engine)
    other_project = create_project(OWNER, ProjectInput(name="Projeto externo"), sqlite_engine)
    foreign = create_character(
        OWNER,
        other_project,
        CharacterInput(name="Personagem externo"),
        sqlite_engine,
    )
    create_relationship(OWNER, project_id, ana, beto, RelationshipInput("Aliado"), sqlite_engine)

    with pytest.raises(IntegrityError), session_scope(sqlite_engine) as session:
        session.add(
            CharacterRelationship(
                project_id=project_id,
                source_character_id=ana,
                target_character_id=beto,
                relationship_type="Duplicada",
            )
        )

    with pytest.raises(IntegrityError), session_scope(sqlite_engine) as session:
        session.add(
            CharacterRelationship(
                project_id=project_id,
                source_character_id=ana,
                target_character_id=ana,
                relationship_type="Inválida",
            )
        )

    with pytest.raises(IntegrityError), session_scope(sqlite_engine) as session:
        session.add(
            CharacterRelationship(
                project_id=project_id,
                source_character_id=ana,
                target_character_id=foreign,
                relationship_type="Externa",
            )
        )

    with pytest.raises(IntegrityError), session_scope(sqlite_engine) as session:
        session.add(
            CharacterRelationship(
                project_id=project_id,
                source_character_id=beto,
                target_character_id=ana,
                relationship_type="Intensidade inválida",
                intensity=0,
            )
        )


@pytest.mark.parametrize(
    "data",
    [
        RelationshipInput(""),
        RelationshipInput("x" * 121),
        RelationshipInput("Aliado", "x" * 20_001),
        RelationshipInput("Aliado", intensity=0),
        RelationshipInput("Aliado", intensity=6),
        RelationshipInput("Aliado", intensity=True),
        RelationshipInput("Aliado", intensity=2.5),  # type: ignore[arg-type]
        RelationshipInput("Aliado", relationship_status="x" * 81),
        RelationshipInput("Aliado\x00Inimigo"),
        RelationshipInput("Aliado", "Texto\x00inválido"),
        RelationshipInput("Aliado", relationship_status="Ativa\x00Rompida"),
    ],
)
def test_relationship_input_validation(
    sqlite_engine: Engine,
    data: RelationshipInput,
) -> None:
    project_id, ana, beto, _ = _characters(sqlite_engine)
    with pytest.raises(RelationshipValidationError):
        create_relationship(OWNER, project_id, ana, beto, data, sqlite_engine)
