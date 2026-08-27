"""Create the initial GDD Studio schema.

Revision ID: 0001_initial_schema
Revises: None
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps(*, include_updated: bool = True) -> list[sa.Column]:
    columns = [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        )
    ]
    if include_updated:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
    return columns


def _create_tag_association(
    table_name: str,
    entity_table: str,
    entity_column: str,
) -> None:
    op.create_table(
        table_name,
        sa.Column(entity_column, sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            [entity_column],
            [f"{entity_table}.id"],
            name=f"fk_{table_name}_{entity_column}_{entity_table}",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name=f"fk_{table_name}_tag_id_tags",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(entity_column, "tag_id", name=f"pk_{table_name}"),
    )
    op.create_index(
        f"ix_{table_name}_tag_entity",
        table_name,
        ["tag_id", entity_column],
        unique=False,
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
    )

    op.create_table(
        "projects",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("codename", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("genre", sa.String(length=80), nullable=True),
        sa.Column("subgenre", sa.String(length=80), nullable=True),
        sa.Column("platform", sa.String(length=120), nullable=True),
        sa.Column("engine", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("template_key", sa.String(length=80), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("cover_url", sa.String(length=2048), nullable=True),
        sa.Column("accent_color", sa.String(length=9), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("favorite", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_projects_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index(
        "ix_projects_user_archived_updated",
        "projects",
        ["user_id", "archived", "updated_at"],
    )
    op.create_index(
        "ix_projects_user_favorite_updated",
        "projects",
        ["user_id", "favorite", "updated_at"],
    )
    op.create_index("ix_projects_user_status", "projects", ["user_id", "status"])

    op.create_table(
        "gdd_sections",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=True),
        sa.Column("section_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("favorite", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id != id",
            name="parent_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_gdd_sections_parent_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_gdd_sections_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_gdd_sections"),
        sa.UniqueConstraint("id", "project_id", name="uq_gdd_sections_id_project_id"),
    )
    op.create_index(
        "ix_gdd_sections_project_parent_position",
        "gdd_sections",
        ["project_id", "parent_id", "position"],
    )
    op.create_index(
        "ix_gdd_sections_project_status",
        "gdd_sections",
        ["project_id", "status"],
    )

    op.create_table(
        "notes",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("favorite", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_notes_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notes"),
    )
    op.create_index("ix_notes_project_updated", "notes", ["project_id", "updated_at"])

    op.create_table(
        "ideas",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("converted_section_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("converted", sa.Boolean(), nullable=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "(converted = false AND converted_at IS NULL) OR "
            "(converted = true AND converted_at IS NOT NULL)",
            name="converted_timestamp_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["converted_section_id"],
            ["gdd_sections.id"],
            name="fk_ideas_converted_section_id_gdd_sections",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_ideas_project_id_projects",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_ideas_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ideas"),
    )
    op.create_index("ix_ideas_project_created", "ideas", ["project_id", "created_at"])
    op.create_index(
        "ix_ideas_converted_section",
        "ideas",
        ["converted_section_id"],
    )
    op.create_index(
        "ix_ideas_user_converted_created",
        "ideas",
        ["user_id", "converted", "created_at"],
    )

    op.create_table(
        "project_references",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_references_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_references"),
    )
    op.create_index(
        "ix_project_references_project_type",
        "project_references",
        ["project_id", "type"],
    )

    op.create_table(
        "tags",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("normalized_name", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_tags_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint(
            "user_id",
            "normalized_name",
            name="uq_tags_user_normalized_name",
        ),
    )

    snapshot_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "project_versions",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("snapshot", snapshot_type, nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(include_updated=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_versions_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_versions"),
    )
    op.create_index(
        "ix_project_versions_project_created",
        "project_versions",
        ["project_id", "created_at"],
    )

    op.create_table(
        "roadmap_items",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_roadmap_items_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_roadmap_items"),
    )
    op.create_index(
        "ix_roadmap_items_project_status_position",
        "roadmap_items",
        ["project_id", "status", "position"],
    )

    _create_tag_association("project_tags", "projects", "project_id")
    _create_tag_association("section_tags", "gdd_sections", "section_id")
    _create_tag_association("note_tags", "notes", "note_id")
    _create_tag_association("idea_tags", "ideas", "idea_id")
    _create_tag_association(
        "reference_tags",
        "project_references",
        "reference_id",
    )


def downgrade() -> None:
    op.drop_table("reference_tags")
    op.drop_table("idea_tags")
    op.drop_table("note_tags")
    op.drop_table("section_tags")
    op.drop_table("project_tags")
    op.drop_table("roadmap_items")
    op.drop_table("project_versions")
    op.drop_table("tags")
    op.drop_table("project_references")
    op.drop_table("ideas")
    op.drop_table("notes")
    op.drop_table("gdd_sections")
    op.drop_table("projects")
    op.drop_table("users")
