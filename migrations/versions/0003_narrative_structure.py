"""Add chapters and scenes.

Revision ID: 0003_narrative_structure
Revises: 0002_characters
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_narrative_structure"
down_revision: str | None = "0002_characters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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


def upgrade() -> None:
    op.create_table(
        "chapters",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_chapters_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chapters"),
        sa.UniqueConstraint("id", "project_id", name="uq_chapters_id_project_id"),
    )
    op.create_index(
        "ix_chapters_project_position", "chapters", ["project_id", "position"]
    )

    op.create_table(
        "scenes",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("chapter_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("timeline_order", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name="fk_scenes_chapter_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_scenes_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenes"),
    )
    op.create_index("ix_scenes_chapter_position", "scenes", ["chapter_id", "position"])
    op.create_index(
        "ix_scenes_project_timeline", "scenes", ["project_id", "timeline_order"]
    )


def downgrade() -> None:
    op.drop_index("ix_scenes_project_timeline", table_name="scenes")
    op.drop_index("ix_scenes_chapter_position", table_name="scenes")
    op.drop_table("scenes")
    op.drop_index("ix_chapters_project_position", table_name="chapters")
    op.drop_table("chapters")
