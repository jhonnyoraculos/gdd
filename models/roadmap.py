"""Simple project roadmap item model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.project import Project


class RoadmapItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roadmap_items"
    __table_args__ = (
        Index("ix_roadmap_items_project_status_position", "project_id", "status", "position"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ideas")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[Project] = relationship(back_populates="roadmap_items")

    __mapper_args__ = {"version_id_col": revision}
