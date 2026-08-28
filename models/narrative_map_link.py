"""User-created, integrity-safe links between narrative map cards."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class NarrativeMapLink(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "narrative_map_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name="fk_narrative_map_links_source_chapter_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_narrative_map_links_source_scene_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_narrative_map_links_source_character_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_narrative_map_links_source_section_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name="fk_narrative_map_links_target_chapter_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_narrative_map_links_target_scene_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_narrative_map_links_target_character_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_narrative_map_links_target_section_project",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(CASE WHEN source_chapter_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN source_scene_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN source_character_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN source_section_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_source",
        ),
        CheckConstraint(
            "(CASE WHEN target_chapter_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_scene_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_character_id IS NULL THEN 0 ELSE 1 END + "
            "CASE WHEN target_section_id IS NULL THEN 0 ELSE 1 END) = 1",
            name="one_target",
        ),
        UniqueConstraint(
            "project_id",
            "connection_key",
            name="uq_narrative_map_links_project_connection_key",
        ),
        Index("ix_narrative_map_links_project_connection", "project_id", "connection_key"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    connection_key: Mapped[str] = mapped_column(String(180), nullable=False)
    source_chapter_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_scene_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    source_section_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_chapter_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_scene_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_section_id: Mapped[UUID | None] = mapped_column(nullable=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    directed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
