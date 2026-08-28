"""Many-to-many appearance between one scene and one character."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKeyConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin, UuidPrimaryKeyMixin


class SceneCharacter(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "scene_characters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scene_id", "project_id"],
            ["scenes.id", "scenes.project_id"],
            name="fk_scene_characters_scene_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["character_id", "project_id"],
            ["characters.id", "characters.project_id"],
            name="fk_scene_characters_character_project",
            ondelete="CASCADE",
        ),
        UniqueConstraint("scene_id", "character_id", name="uq_scene_characters_scene_character"),
        Index("ix_scene_characters_character_scene", "character_id", "scene_id"),
        Index("ix_scene_characters_project_scene", "project_id", "scene_id"),
    )

    project_id: Mapped[UUID] = mapped_column(nullable=False)
    scene_id: Mapped[UUID] = mapped_column(nullable=False)
    character_id: Mapped[UUID] = mapped_column(nullable=False)
    role_in_scene: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"SceneCharacter(scene_id={self.scene_id!s}, character_id={self.character_id!s})"
