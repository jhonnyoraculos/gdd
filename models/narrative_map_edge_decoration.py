"""Visual metadata attached to any narrative-map edge."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class NarrativeMapEdgeDecoration(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "narrative_map_edge_decorations"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "edge_key",
            name="uq_narrative_map_edge_decorations_project_edge",
        ),
        Index(
            "ix_narrative_map_edge_decorations_project_order",
            "project_id",
            "sort_order",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    edge_key: Mapped[str] = mapped_column(String(220), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    caption: Mapped[str | None] = mapped_column(String(240), nullable=True)
    image_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_mime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
