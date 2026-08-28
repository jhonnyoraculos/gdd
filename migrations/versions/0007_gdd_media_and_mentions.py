"""Add compressed GDD images and automatic content mentions.

Revision ID: 0007_gdd_media_mentions
Revises: 0006_project_cover_uploads
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_gdd_media_mentions"
down_revision: str | None = "0006_project_cover_uploads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scene_characters",
        sa.Column(
            "mention_generated",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.alter_column("scene_characters", "mention_generated", server_default=None)

    op.create_table(
        "gdd_section_images",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("caption", sa.String(length=240), nullable=True),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
            ["section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_gdd_section_images_section_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_gdd_section_images"),
    )
    op.create_index(
        "ix_gdd_section_images_project_section_position",
        "gdd_section_images",
        ["project_id", "section_id", "position"],
    )

    op.create_table(
        "content_links",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_section_id", sa.Uuid(), nullable=True),
        sa.Column("source_scene_id", sa.Uuid(), nullable=True),
        sa.Column("target_character_id", sa.Uuid(), nullable=True),
        sa.Column("target_scene_id", sa.Uuid(), nullable=True),
        sa.Column("target_chapter_id", sa.Uuid(), nullable=True),
        sa.Column("target_section_id", sa.Uuid(), nullable=True),
        sa.Column("mention_token", sa.String(length=220), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(CASE WHEN source_section_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN source_scene_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_source",
        ),
        sa.CheckConstraint(
            "(CASE WHEN target_character_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_scene_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_chapter_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_section_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_target",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_content_links_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_content_links_source_section_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_content_links_source_scene_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_content_links_target_character_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_content_links_target_scene_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name="fk_content_links_target_chapter_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_content_links_target_section_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_links"),
    )
    for suffix, column in (
        ("source_section", "source_section_id"),
        ("source_scene", "source_scene_id"),
        ("target_character", "target_character_id"),
        ("target_scene", "target_scene_id"),
        ("target_chapter", "target_chapter_id"),
        ("target_section", "target_section_id"),
    ):
        op.create_index(
            f"ix_content_links_project_{suffix}",
            "content_links",
            ["project_id", column],
        )


def downgrade() -> None:
    op.drop_table("content_links")
    op.drop_index(
        "ix_gdd_section_images_project_section_position",
        table_name="gdd_section_images",
    )
    op.drop_table("gdd_section_images")
    op.drop_column("scene_characters", "mention_generated")
