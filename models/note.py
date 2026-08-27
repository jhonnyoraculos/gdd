"""Project note model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.project import Project
    from models.tag import Tag


class Note(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notes"
    __table_args__ = (Index("ix_notes_project_updated", "project_id", "updated_at"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", deferred=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[Project] = relationship(back_populates="notes")
    tags: Mapped[list[Tag]] = relationship(
        secondary="note_tags",
        back_populates="notes",
    )

    __mapper_args__ = {"version_id_col": revision}
