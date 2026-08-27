"""Hierarchical GDD section model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
    from models.idea import Idea
    from models.project import Project
    from models.tag import Tag


class GddSection(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gdd_sections"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_gdd_sections_id_project_id"),
        ForeignKeyConstraint(
            ["parent_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_gdd_sections_parent_project",
            ondelete="CASCADE",
        ),
        CheckConstraint("parent_id IS NULL OR parent_id != id", name="parent_not_self"),
        Index(
            "ix_gdd_sections_project_parent_position",
            "project_id",
            "parent_id",
            "position",
        ),
        Index("ix_gdd_sections_project_status", "project_id", "status"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    section_type: Mapped[str] = mapped_column(String(30), nullable=False, default="page")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", deferred=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[Project] = relationship(
        back_populates="sections",
        foreign_keys=[project_id],
        overlaps="children,parent",
    )
    parent: Mapped[GddSection | None] = relationship(
        back_populates="children",
        remote_side="[GddSection.id, GddSection.project_id]",
        foreign_keys="[GddSection.parent_id, GddSection.project_id]",
        overlaps="project,sections",
    )
    children: Mapped[list[GddSection]] = relationship(
        back_populates="parent",
        passive_deletes="all",
        order_by="GddSection.position",
        foreign_keys="[GddSection.parent_id, GddSection.project_id]",
        overlaps="project,sections",
    )
    converted_ideas: Mapped[list[Idea]] = relationship(
        back_populates="converted_section",
        passive_deletes=True,
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary="section_tags",
        back_populates="sections",
    )

    def __repr__(self) -> str:
        return f"GddSection(id={self.id!s}, title={self.title!r})"

    __mapper_args__ = {"version_id_col": revision}
