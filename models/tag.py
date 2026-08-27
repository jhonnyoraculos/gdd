"""User-scoped tags and integrity-safe association tables."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, ForeignKey, Index, String, Table, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.idea import Idea
    from models.note import Note
    from models.project import Project
    from models.reference import ProjectReference
    from models.section import GddSection
    from models.user import User


def _tag_association(name: str, entity_table: str, entity_column: str) -> Table:
    table = Table(
        name,
        Base.metadata,
        Column(
            entity_column,
            Uuid(as_uuid=True),
            ForeignKey(f"{entity_table}.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        Column(
            "tag_id",
            Uuid(as_uuid=True),
            ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    Index(f"ix_{name}_tag_entity", table.c.tag_id, table.c[entity_column])
    return table


project_tags = _tag_association("project_tags", "projects", "project_id")
section_tags = _tag_association("section_tags", "gdd_sections", "section_id")
note_tags = _tag_association("note_tags", "notes", "note_id")
idea_tags = _tag_association("idea_tags", "ideas", "idea_id")
reference_tags = _tag_association(
    "reference_tags",
    "project_references",
    "reference_id",
)


class Tag(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_tags_user_normalized_name"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(80), nullable=False)

    user: Mapped[User] = relationship(back_populates="tags")
    projects: Mapped[list[Project]] = relationship(
        secondary=project_tags,
        back_populates="tags",
    )
    sections: Mapped[list[GddSection]] = relationship(
        secondary=section_tags,
        back_populates="tags",
    )
    notes: Mapped[list[Note]] = relationship(
        secondary=note_tags,
        back_populates="tags",
    )
    ideas: Mapped[list[Idea]] = relationship(
        secondary=idea_tags,
        back_populates="tags",
    )
    references: Mapped[list[ProjectReference]] = relationship(
        secondary=reference_tags,
        back_populates="tags",
    )
