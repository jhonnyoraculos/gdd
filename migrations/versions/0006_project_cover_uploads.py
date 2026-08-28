"""Store uploaded project cover images.

Revision ID: 0006_project_cover_uploads
Revises: 0005_character_relationships
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_project_cover_uploads"
down_revision: str | None = "0005_character_relationships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("cover_image", sa.LargeBinary(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("cover_image_mime", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "cover_image_mime")
    op.drop_column("projects", "cover_image")
