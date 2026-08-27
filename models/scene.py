"""Ordered scene model within a narrative chapter."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.chapter import Chapter
    from models.project import Project


class Scene(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_scenes_id_project_id"),
        ForeignKeyConstraint(
            ["chapter_id", "project_id"],
            ["chapters.id", "chapters.project_id"],
            name="fk_scenes_chapter_project",
            ondelete="CASCADE",
        ),
        Index("ix_scenes_chapter_position", "chapter_id", "position"),
        Index("ix_scenes_project_timeline", "project_id", "timeline_order"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    timeline_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[Project] = relationship(
        back_populates="scenes", foreign_keys=[project_id], overlaps="chapter,scenes"
    )
    chapter: Mapped[Chapter] = relationship(
        back_populates="scenes",
        foreign_keys="[Scene.chapter_id, Scene.project_id]",
        overlaps="project,scenes",
    )

    __mapper_args__ = {"version_id_col": revision}

    def __repr__(self) -> str:
        return f"Scene(id={self.id!s}, title={self.title!r})"
