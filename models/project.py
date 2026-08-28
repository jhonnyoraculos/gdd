"""Game project model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from utils.constants import DEFAULT_ACCENT_COLOR

if TYPE_CHECKING:
    from models.chapter import Chapter
    from models.character import Character
    from models.idea import Idea
    from models.note import Note
    from models.reference import ProjectReference
    from models.roadmap import RoadmapItem
    from models.scene import Scene
    from models.section import GddSection
    from models.tag import Tag
    from models.user import User
    from models.version import ProjectVersion


class Project(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_user_archived_updated", "user_id", "archived", "updated_at"),
        Index("ix_projects_user_favorite_updated", "user_id", "favorite", "updated_at"),
        Index("ix_projects_user_status", "user_id", "status"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    codename: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(80), nullable=True)
    subgenre: Mapped[str | None] = mapped_column(String(80), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(120), nullable=True)
    engine: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="idea")
    template_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cover_image: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cover_image_mime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    accent_color: Mapped[str] = mapped_column(
        String(9),
        nullable=False,
        default=DEFAULT_ACCENT_COLOR,
    )
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="projects")
    sections: Mapped[list[GddSection]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GddSection.position",
    )
    characters: Mapped[list[Character]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Character.name",
    )
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chapter.position",
    )
    scenes: Mapped[list[Scene]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Scene.project_id",
        overlaps="chapter,scenes",
    )
    notes: Mapped[list[Note]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ideas: Mapped[list[Idea]] = relationship(
        back_populates="project",
        passive_deletes=True,
    )
    references: Mapped[list[ProjectReference]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    versions: Mapped[list[ProjectVersion]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    roadmap_items: Mapped[list[RoadmapItem]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary="project_tags",
        back_populates="projects",
    )

    def __repr__(self) -> str:
        return f"Project(id={self.id!s}, name={self.name!r})"
