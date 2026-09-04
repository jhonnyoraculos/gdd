"""Ordered images and captions for narrative-map connections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine, func, select

from models import NarrativeMapEdgeDecoration, Project
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner
from utils.image_processing import ImageProcessingError, process_image_480p


class NarrativeMapEdgeMediaError(RuntimeError):
    """Safe validation error for connection media and ordering."""


@dataclass(frozen=True, slots=True)
class EdgeDecorationDetails:
    edge_key: str
    sort_order: int
    caption: str | None
    image_data: bytes | None
    image_mime: str | None
    image_width: int | None
    image_height: int | None


def _project(session, owner: OwnerIdentity, project_id: UUID) -> Project:  # type: ignore[no-untyped-def]
    user = get_or_create_owner(session, owner)
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise NarrativeMapEdgeMediaError("Projeto não encontrado.")
    return project


def _validate_edge(edge_key: str, valid_edge_keys: frozenset[str]) -> None:
    if edge_key not in valid_edge_keys or len(edge_key) > 220:
        raise NarrativeMapEdgeMediaError("Ligação inválida para este projeto.")


def list_edge_decorations(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> tuple[EdgeDecorationDetails, ...]:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        records = session.scalars(
            select(NarrativeMapEdgeDecoration)
            .where(NarrativeMapEdgeDecoration.project_id == project_id)
            .order_by(
                NarrativeMapEdgeDecoration.sort_order,
                NarrativeMapEdgeDecoration.edge_key,
            )
        ).all()
        return tuple(
            EdgeDecorationDetails(
                record.edge_key,
                record.sort_order,
                record.caption,
                record.image_data,
                record.image_mime,
                record.image_width,
                record.image_height,
            )
            for record in records
        )


def save_edge_decoration(
    owner: OwnerIdentity,
    project_id: UUID,
    edge_key: str,
    valid_edge_keys: frozenset[str],
    *,
    caption: str | None = None,
    image_data: bytes | None = None,
    remove_image: bool = False,
    engine: Engine | None = None,
) -> None:
    _validate_edge(edge_key, valid_edge_keys)
    clean_caption = caption.strip() if caption else None
    if clean_caption and len(clean_caption) > 240:
        raise NarrativeMapEdgeMediaError("A legenda deve ter no máximo 240 caracteres.")
    processed = None
    if image_data:
        try:
            processed = process_image_480p(image_data)
        except ImageProcessingError as exc:
            raise NarrativeMapEdgeMediaError(str(exc)) from exc

    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        record = session.scalar(
            select(NarrativeMapEdgeDecoration).where(
                NarrativeMapEdgeDecoration.project_id == project_id,
                NarrativeMapEdgeDecoration.edge_key == edge_key,
            )
        )
        if record is None:
            max_order = (
                session.scalar(
                    select(func.max(NarrativeMapEdgeDecoration.sort_order)).where(
                        NarrativeMapEdgeDecoration.project_id == project_id
                    )
                )
                or 0
            )
            record = NarrativeMapEdgeDecoration(
                project_id=project_id,
                edge_key=edge_key,
                sort_order=max_order + 1000,
            )
            session.add(record)
        record.caption = clean_caption
        if remove_image:
            record.image_data = None
            record.image_mime = None
            record.image_width = None
            record.image_height = None
        if processed is not None:
            record.image_data = processed.data
            record.image_mime = processed.mime_type
            record.image_width = processed.width
            record.image_height = processed.height
        project.updated_at = datetime.now(UTC)


def reorder_edges(
    owner: OwnerIdentity,
    project_id: UUID,
    ordered_edge_keys: tuple[str, ...],
    valid_edge_keys: frozenset[str],
    engine: Engine | None = None,
) -> None:
    if not ordered_edge_keys or len(set(ordered_edge_keys)) != len(ordered_edge_keys):
        raise NarrativeMapEdgeMediaError("A ordem das ligações é inválida.")
    for edge_key in ordered_edge_keys:
        _validate_edge(edge_key, valid_edge_keys)

    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        existing = {
            record.edge_key: record
            for record in session.scalars(
                select(NarrativeMapEdgeDecoration).where(
                    NarrativeMapEdgeDecoration.project_id == project_id,
                    NarrativeMapEdgeDecoration.edge_key.in_(ordered_edge_keys),
                )
            ).all()
        }
        for index, edge_key in enumerate(ordered_edge_keys, start=1):
            record = existing.get(edge_key)
            if record is None:
                record = NarrativeMapEdgeDecoration(
                    project_id=project_id,
                    edge_key=edge_key,
                )
                session.add(record)
            record.sort_order = index * 1000
        project.updated_at = datetime.now(UTC)
