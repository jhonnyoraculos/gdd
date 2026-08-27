"""Quick-idea inbox model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.project import Project
    from models.section import GddSection
    from models.tag import Tag
    from models.user import User


class Idea(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ideas"
    __table_args__ = (
        CheckConstraint(
            "(converted = false AND converted_at IS NULL) OR "
            "(converted = true AND converted_at IS NOT NULL)",
            name="converted_timestamp_consistent",
        ),
        Index("ix_ideas_user_converted_created", "user_id", "converted", "created_at"),
        Index("ix_ideas_project_created", "project_id", "created_at"),
        Index("ix_ideas_converted_section", "converted_section_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    converted_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("gdd_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    converted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()
    project: Mapped[Project | None] = relationship(back_populates="ideas")
    converted_section: Mapped[GddSection | None] = relationship(back_populates="converted_ideas")
    tags: Mapped[list[Tag]] = relationship(
        secondary="idea_tags",
        back_populates="ideas",
    )
