"""Project-scoped character knowledge-base model."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from models.project import Project


class Character(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_characters_id_project_id"),
        UniqueConstraint(
            "project_id",
            "normalized_name",
            name="uq_characters_project_normalized_name",
        ),
        Index("ix_characters_project_name", "project_id", "name"),
        Index("ix_characters_project_role", "project_id", "role"),
        Index("ix_characters_project_updated", "project_id", "updated_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(160), nullable=True)
    codename: Mapped[str | None] = mapped_column(String(160), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(100), nullable=True)
    species: Mapped[str | None] = mapped_column(String(120), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_status: Mapped[str | None] = mapped_column(String(120), nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    game_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_importance: Mapped[str | None] = mapped_column(Text, nullable=True)
    story: Mapped[str | None] = mapped_column(Text, nullable=True)
    childhood: Mapped[str | None] = mapped_column(Text, nullable=True)
    past: Mapped[str | None] = mapped_column(Text, nullable=True)
    important_events: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    qualities: Mapped[str | None] = mapped_column(Text, nullable=True)
    flaws: Mapped[str | None] = mapped_column(Text, nullable=True)
    fears: Mapped[str | None] = mapped_column(Text, nullable=True)
    desires: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivations: Mapped[str | None] = mapped_column(Text, nullable=True)
    traumas: Mapped[str | None] = mapped_column(Text, nullable=True)
    beliefs: Mapped[str | None] = mapped_column(Text, nullable=True)
    values: Mapped[str | None] = mapped_column(Text, nullable=True)
    habits: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict: Mapped[str | None] = mapped_column(Text, nullable=True)
    arc_beginning: Mapped[str | None] = mapped_column(Text, nullable=True)
    arc_transformation: Mapped[str | None] = mapped_column(Text, nullable=True)
    arc_breaking_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    arc_ending: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    height: Mapped[str | None] = mapped_column(String(80), nullable=True)
    body_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hair: Mapped[str | None] = mapped_column(String(240), nullable=True)
    eyes: Mapped[str | None] = mapped_column(String(240), nullable=True)
    clothing: Mapped[str | None] = mapped_column(Text, nullable=True)
    distinctive_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    health: Mapped[str | None] = mapped_column(Text, nullable=True)
    abilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses: Mapped[str | None] = mapped_column(Text, nullable=True)
    attacks: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    equipment: Mapped[str | None] = mapped_column(Text, nullable=True)
    weapons: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project: Mapped[Project] = relationship(back_populates="characters")

    __mapper_args__ = {"version_id_col": revision}

    def __repr__(self) -> str:
        return f"Character(id={self.id!s}, name={self.name!r})"
