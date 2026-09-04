"""Add ordered 480p media to narrative-map connections.

Revision ID: 0009_map_edge_media
Revises: 0008_narrative_map_editor
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_map_edge_media"
down_revision: str | None = "0008_narrative_map_editor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "narrative_map_edge_decorations",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("edge_key", sa.String(length=220), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("caption", sa.String(length=240), nullable=True),
        sa.Column("image_data", sa.LargeBinary(), nullable=True),
        sa.Column("image_mime", sa.String(length=32), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
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
            name="fk_narrative_map_edge_decorations_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_narrative_map_edge_decorations"),
        sa.UniqueConstraint(
            "project_id",
            "edge_key",
            name="uq_narrative_map_edge_decorations_project_edge",
        ),
    )
    op.create_index(
        "ix_narrative_map_edge_decorations_project_order",
        "narrative_map_edge_decorations",
        ["project_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_narrative_map_edge_decorations_project_order",
        table_name="narrative_map_edge_decorations",
    )
    op.drop_table("narrative_map_edge_decorations")
