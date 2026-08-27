"""Add character appearances in scenes.

Revision ID: 0004_scene_characters
Revises: 0003_narrative_structure
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_scene_characters"
down_revision: str | None = "0003_narrative_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_characters_id_project_id",
        "characters",
        ["id", "project_id"],
    )
    op.create_unique_constraint(
        "uq_scenes_id_project_id",
        "scenes",
        ["id", "project_id"],
    )
    op.create_table(
        "scene_characters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("scene_id", sa.Uuid(), nullable=False),
        sa.Column("character_id", sa.Uuid(), nullable=False),
        sa.Column("role_in_scene", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_scene_characters_character_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_scene_characters_scene_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scene_characters"),
        sa.UniqueConstraint(
            "scene_id",
            "character_id",
            name="uq_scene_characters_scene_character",
        ),
    )
    op.create_index(
        "ix_scene_characters_character_scene",
        "scene_characters",
        ["character_id", "scene_id"],
    )
    op.create_index(
        "ix_scene_characters_project_scene",
        "scene_characters",
        ["project_id", "scene_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_scene_characters_project_scene", table_name="scene_characters")
    op.drop_index("ix_scene_characters_character_scene", table_name="scene_characters")
    op.drop_table("scene_characters")
    op.drop_constraint("uq_scenes_id_project_id", "scenes", type_="unique")
    op.drop_constraint("uq_characters_id_project_id", "characters", type_="unique")
