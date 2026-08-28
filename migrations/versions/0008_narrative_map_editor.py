"""Add user-created links for the visual narrative editor.

Revision ID: 0008_narrative_map_editor
Revises: 0007_gdd_media_mentions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_narrative_map_editor"
down_revision: str | None = "0007_gdd_media_mentions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_COLUMNS = (
    "source_chapter_id",
    "source_scene_id",
    "source_character_id",
    "source_section_id",
)
_TARGET_COLUMNS = (
    "target_chapter_id",
    "target_scene_id",
    "target_character_id",
    "target_section_id",
)


def _one(columns: tuple[str, ...]) -> str:
    return " + ".join(
        f"CASE WHEN {column} IS NULL THEN 0 ELSE 1 END" for column in columns
    ) + " = 1"


def upgrade() -> None:
    columns = [
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("connection_key", sa.String(length=180), nullable=False),
        *(sa.Column(name, sa.Uuid(), nullable=True) for name in _SOURCE_COLUMNS),
        *(sa.Column(name, sa.Uuid(), nullable=True) for name in _TARGET_COLUMNS),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("directed", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]
    constraints = [
        sa.CheckConstraint(_one(_SOURCE_COLUMNS), name="one_source"),
        sa.CheckConstraint(_one(_TARGET_COLUMNS), name="one_target"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_narrative_map_links_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_narrative_map_links"),
        sa.UniqueConstraint(
            "project_id",
            "connection_key",
            name="uq_narrative_map_links_project_connection_key",
        ),
    ]
    for side in ("source", "target"):
        for entity, table in (
            ("chapter", "chapters"),
            ("scene", "scenes"),
            ("character", "characters"),
            ("section", "gdd_sections"),
        ):
            constraints.append(
                sa.ForeignKeyConstraint(
                    [f"{side}_{entity}_id", "project_id"],
                    [f"{table}.id", f"{table}.project_id"],
                    name=f"fk_narrative_map_links_{side}_{entity}_project",
                    ondelete="CASCADE",
                )
            )
    op.create_table("narrative_map_links", *columns, *constraints)
    op.create_index(
        "ix_narrative_map_links_project_connection",
        "narrative_map_links",
        ["project_id", "connection_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_narrative_map_links_project_connection",
        table_name="narrative_map_links",
    )
    op.drop_table("narrative_map_links")
