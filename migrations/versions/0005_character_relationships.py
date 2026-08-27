"""Add directional relationships between characters.

Revision ID: 0005_character_relationships
Revises: 0004_scene_characters
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_character_relationships"
down_revision: str | None = "0004_scene_characters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "character_relationships",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_character_id", sa.Uuid(), nullable=False),
        sa.Column("target_character_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("intensity", sa.Integer(), nullable=True),
        sa.Column("relationship_status", sa.String(length=80), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "source_character_id != target_character_id",
            name="source_not_target",
        ),
        sa.CheckConstraint(
            "intensity IS NULL OR intensity BETWEEN 1 AND 5",
            name="intensity_range",
        ),
        sa.ForeignKeyConstraint(
            ["source_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_character_relationships_source_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_character_relationships_target_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_character_relationships"),
        sa.UniqueConstraint(
            "project_id",
            "source_character_id",
            "target_character_id",
            name="uq_character_relationships_project_source_target",
        ),
    )
    op.create_index(
        "ix_character_relationships_project_source",
        "character_relationships",
        ["project_id", "source_character_id"],
    )
    op.create_index(
        "ix_character_relationships_project_target",
        "character_relationships",
        ["project_id", "target_character_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_character_relationships_project_target",
        table_name="character_relationships",
    )
    op.drop_index(
        "ix_character_relationships_project_source",
        table_name="character_relationships",
    )
    op.drop_table("character_relationships")
