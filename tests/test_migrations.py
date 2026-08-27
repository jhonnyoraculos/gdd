"""PostgreSQL migration compilation tests without external credentials."""

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_initial_migration_compiles_with_expected_constraint_names() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output = StringIO()
    config = Config(str(project_root / "alembic.ini"), output_buffer=output)
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql+psycopg://user:password@example.invalid/gdd",
    )

    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()

    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE gdd_sections" in sql
    assert "CREATE TABLE characters" in sql
    assert "CREATE TABLE chapters" in sql
    assert "CREATE TABLE scenes" in sql
    assert "CREATE TABLE scene_characters" in sql
    assert "CREATE TABLE character_relationships" in sql
    assert "CONSTRAINT fk_scenes_chapter_project FOREIGN KEY" in sql
    assert "CONSTRAINT fk_scene_characters_scene_project FOREIGN KEY" in sql
    assert "CONSTRAINT fk_scene_characters_character_project FOREIGN KEY" in sql
    assert "CONSTRAINT fk_character_relationships_source_project FOREIGN KEY" in sql
    assert "CONSTRAINT fk_character_relationships_target_project FOREIGN KEY" in sql
    assert "CONSTRAINT ck_character_relationships_source_not_target CHECK" in sql
    assert "CONSTRAINT ck_character_relationships_intensity_range CHECK" in sql
    assert "CONSTRAINT uq_character_relationships_project_source_target UNIQUE" in sql
    assert "CONSTRAINT uq_characters_project_normalized_name UNIQUE" in sql
    assert "CONSTRAINT ck_gdd_sections_parent_not_self CHECK" in sql
    assert "CONSTRAINT ck_ideas_converted_timestamp_consistent CHECK" in sql
    assert "ck_gdd_sections_ck_gdd_sections" not in sql
    assert "ck_ideas_ck_ideas" not in sql
