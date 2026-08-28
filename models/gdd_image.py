"""Compressed image attached to one GDD section."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKeyConstraint, Index, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class GddSectionImage(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gdd_section_images"
    __table_args__ = (
        ForeignKeyConstraint(
            ["section_id", "project_id"],
            ["gdd_sections.id", "gdd_sections.project_id"],
            name="fk_gdd_section_images_section_project",
            ondelete="CASCADE",
        ),
        Index(
            "ix_gdd_section_images_project_section_position",
            "project_id",
            "section_id",
            "position",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(nullable=False)
    section_id: Mapped[UUID] = mapped_column(nullable=False)
    caption: Mapped[str | None] = mapped_column(String(240), nullable=True)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
