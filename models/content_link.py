"""Automatic links created from @mentions in project content."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class ContentLink(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "content_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_content_links_source_section_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_content_links_source_scene_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_content_links_target_character_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_content_links_target_scene_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name="fk_content_links_target_chapter_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_content_links_target_section_project",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(CASE WHEN source_section_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN source_scene_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_source",
        ),
        CheckConstraint(
            "(CASE WHEN target_character_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_scene_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_chapter_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_section_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_target",
        ),
        Index("ix_content_links_project_source_section", "project_id", "source_section_id"),
        Index("ix_content_links_project_source_scene", "project_id", "source_scene_id"),
        Index("ix_content_links_project_target_character", "project_id", "target_character_id"),
        Index("ix_content_links_project_target_scene", "project_id", "target_scene_id"),
        Index("ix_content_links_project_target_chapter", "project_id", "target_chapter_id"),
        Index("ix_content_links_project_target_section", "project_id", "target_section_id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_section_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_scene_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_scene_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_chapter_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_section_id: Mapped[UUID | None] = mapped_column(nullable=True)
    mention_token: Mapped[str] = mapped_column(String(220), nullable=False)
