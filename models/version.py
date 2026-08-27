"""Immutable project snapshot metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.project import Project


JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class ProjectVersion(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "project_versions"
    __table_args__ = (Index("ix_project_versions_project_created", "project_id", "created_at"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON_DOCUMENT,
        nullable=False,
        deferred=True,
    )
    schema_version: Mapped[int] = mapped_column(nullable=False, default=1)

    project: Mapped[Project] = relationship(back_populates="versions")
