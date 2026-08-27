"""Per-project reference library model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.project import Project
    from models.tag import Tag


class ProjectReference(UuidPrimaryKeyMixin, TimestampMixin, Base):
    # "references" is a SQL keyword, so the physical table uses an explicit safe name.
    __tablename__ = "project_references"
    __table_args__ = (Index("ix_project_references_project_type", "project_id", "type"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="references")
    tags: Mapped[list[Tag]] = relationship(
        secondary="reference_tags",
        back_populates="references",
    )
