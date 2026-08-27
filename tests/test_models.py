"""Portable schema and core integrity tests."""

from __future__ import annotations

from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError

from models import Base, Character, GddSection, Project, User
from services.database import session_scope

EXPECTED_TABLES = {
    "users",
    "projects",
    "gdd_sections",
    "notes",
    "ideas",
    "project_references",
    "tags",
    "project_tags",
    "section_tags",
    "note_tags",
    "idea_tags",
    "reference_tags",
    "project_versions",
    "roadmap_items",
    "characters",
    "chapters",
    "scenes",
    "scene_characters",
}


def test_all_foundation_tables_are_registered_and_created(sqlite_engine: Engine) -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert set(inspect(sqlite_engine).get_table_names()) == EXPECTED_TABLES


def test_project_and_hierarchical_section_round_trip(sqlite_engine: Engine) -> None:
    with session_scope(sqlite_engine) as session:
        user = User(
            name="Criador",
            email="Creator@Example.com",
            email_normalized="creator@example.com",
        )
        project = Project(user=user, name="Encouraçado")
        root = GddSection(project=project, title="Visão Geral", section_type="category")
        child = GddSection(project=project, parent=root, title="High Concept", position=1000)
        session.add_all([user, project, root, child])

    with session_scope(sqlite_engine) as session:
        persisted = session.query(Project).filter_by(name="Encouraçado").one()
        assert persisted.user.email_normalized == "creator@example.com"
        assert len(persisted.sections) == 2


def test_parent_section_cannot_belong_to_another_project(sqlite_engine: Engine) -> None:
    with session_scope(sqlite_engine) as session:
        user = User(
            name="Criador",
            email="creator@example.com",
            email_normalized="creator@example.com",
        )
        first = Project(user=user, name="Primeiro")
        second = Project(user=user, name="Segundo")
        parent = GddSection(project=first, title="Mundo")
        session.add_all([user, first, second, parent])

    try:
        with session_scope(sqlite_engine) as session:
            projects = {project.name: project for project in session.query(Project).all()}
            parent = session.query(GddSection).filter_by(title="Mundo").one()
            invalid = GddSection(
                project_id=projects["Segundo"].id,
                parent_id=parent.id,
                title="Região inválida",
            )
            session.add(invalid)
    except IntegrityError:
        pass
    else:
        raise AssertionError("A FK composta deveria impedir hierarquia entre projetos.")


def test_duplicate_normalized_email_is_rejected(sqlite_engine: Engine) -> None:
    try:
        with session_scope(sqlite_engine) as session:
            session.add_all(
                [
                    User(
                        name="A",
                        email="Player@Example.com",
                        email_normalized="player@example.com",
                    ),
                    User(
                        name="B",
                        email="player@example.com",
                        email_normalized="player@example.com",
                    ),
                ]
            )
    except IntegrityError:
        pass
    else:
        raise AssertionError("Emails normalizados duplicados deveriam ser rejeitados.")


def test_loaded_section_children_are_deleted_by_database_cascade(
    sqlite_engine: Engine,
) -> None:
    with session_scope(sqlite_engine) as session:
        user = User(
            name="Criador",
            email="creator@example.com",
            email_normalized="creator@example.com",
        )
        project = Project(user=user, name="Projeto")
        parent = GddSection(project=project, title="Personagens")
        child = GddSection(project=project, parent=parent, title="Protagonista")
        session.add_all([user, project, parent, child])

    with session_scope(sqlite_engine) as session:
        parent = session.query(GddSection).filter_by(title="Personagens").one()
        assert len(parent.children) == 1
        session.delete(parent)

    with session_scope(sqlite_engine) as session:
        assert session.query(GddSection).count() == 0


def test_characters_are_deleted_with_their_project(sqlite_engine: Engine) -> None:
    with session_scope(sqlite_engine) as session:
        user = User(
            name="Criador",
            email="creator@example.com",
            email_normalized="creator@example.com",
        )
        project = Project(user=user, name="Projeto")
        character = Character(
            project=project,
            name="Protagonista",
            normalized_name="protagonista",
        )
        session.add_all([user, project, character])

    with session_scope(sqlite_engine) as session:
        project = session.query(Project).one()
        session.delete(project)

    with session_scope(sqlite_engine) as session:
        assert session.query(Character).count() == 0
