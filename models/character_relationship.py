"""Directional relationship between two characters in the same project."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class CharacterRelationship(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "character_relationships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_character_relationships_source_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_character_relationships_target_project",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "source_character_id != target_character_id",
            name="source_not_target",
        ),
        CheckConstraint(
            "intensity IS NULL OR intensity BETWEEN 1 AND 5",
            name="intensity_range",
        ),
        UniqueConstraint(
            "project_id",
            "source_character_id",
            "target_character_id",
            name="uq_character_relationships_project_source_target",
        ),
        Index(
            "ix_character_relationships_project_source",
            "project_id",
            "source_character_id",
        ),
        Index(
            "ix_character_relationships_project_target",
            "project_id",
            "target_character_id",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(nullable=False)
    source_character_id: Mapped[UUID] = mapped_column(nullable=False)
    target_character_id: Mapped[UUID] = mapped_column(nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    intensity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relationship_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": revision}

    def __repr__(self) -> str:
        return (
            "CharacterRelationship("
            f"source_character_id={self.source_character_id!s}, "
            f"target_character_id={self.target_character_id!s}, "
            f"relationship_type={self.relationship_type!r})"
        )
