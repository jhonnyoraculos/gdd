"""Add project characters.

Revision ID: 0002_characters
Revises: 0001_initial_schema
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_characters"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "characters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("full_name", sa.String(length=240), nullable=True),
        sa.Column("nickname", sa.String(length=160), nullable=True),
        sa.Column("codename", sa.String(length=160), nullable=True),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=100), nullable=True),
        sa.Column("species", sa.String(length=120), nullable=True),
        sa.Column("occupation", sa.String(length=160), nullable=True),
        sa.Column("origin", sa.String(length=200), nullable=True),
        sa.Column("current_status", sa.String(length=120), nullable=True),
        sa.Column("short_description", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("game_role", sa.Text(), nullable=True),
        sa.Column("narrative_importance", sa.Text(), nullable=True),
        sa.Column("story", sa.Text(), nullable=True),
        sa.Column("childhood", sa.Text(), nullable=True),
        sa.Column("past", sa.Text(), nullable=True),
        sa.Column("important_events", sa.Text(), nullable=True),
        sa.Column("current_situation", sa.Text(), nullable=True),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("qualities", sa.Text(), nullable=True),
        sa.Column("flaws", sa.Text(), nullable=True),
        sa.Column("fears", sa.Text(), nullable=True),
        sa.Column("desires", sa.Text(), nullable=True),
        sa.Column("motivations", sa.Text(), nullable=True),
        sa.Column("traumas", sa.Text(), nullable=True),
        sa.Column("beliefs", sa.Text(), nullable=True),
        sa.Column("values", sa.Text(), nullable=True),
        sa.Column("habits", sa.Text(), nullable=True),
        sa.Column("external_goal", sa.Text(), nullable=True),
        sa.Column("internal_goal", sa.Text(), nullable=True),
        sa.Column("conflict", sa.Text(), nullable=True),
        sa.Column("arc_beginning", sa.Text(), nullable=True),
        sa.Column("arc_transformation", sa.Text(), nullable=True),
        sa.Column("arc_breaking_point", sa.Text(), nullable=True),
        sa.Column("arc_ending", sa.Text(), nullable=True),
        sa.Column("appearance", sa.Text(), nullable=True),
        sa.Column("height", sa.String(length=80), nullable=True),
        sa.Column("body_description", sa.Text(), nullable=True),
        sa.Column("hair", sa.String(length=240), nullable=True),
        sa.Column("eyes", sa.String(length=240), nullable=True),
        sa.Column("clothing", sa.Text(), nullable=True),
        sa.Column("distinctive_features", sa.Text(), nullable=True),
        sa.Column("health", sa.Text(), nullable=True),
        sa.Column("abilities", sa.Text(), nullable=True),
        sa.Column("weaknesses", sa.Text(), nullable=True),
        sa.Column("attacks", sa.Text(), nullable=True),
        sa.Column("behavior", sa.Text(), nullable=True),
        sa.Column("ai_description", sa.Text(), nullable=True),
        sa.Column("equipment", sa.Text(), nullable=True),
        sa.Column("weapons", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_characters_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_characters"),
        sa.UniqueConstraint(
            "project_id",
            "normalized_name",
            name="uq_characters_project_normalized_name",
        ),
    )
    op.create_index("ix_characters_project_name", "characters", ["project_id", "name"])
    op.create_index("ix_characters_project_role", "characters", ["project_id", "role"])
    op.create_index(
        "ix_characters_project_updated",
        "characters",
        ["project_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_characters_project_updated", table_name="characters")
    op.drop_index("ix_characters_project_role", table_name="characters")
    op.drop_index("ix_characters_project_name", table_name="characters")
    op.drop_table("characters")
