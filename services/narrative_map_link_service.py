"""Owner-scoped manual connections created in the narrative map."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Chapter, Character, GddSection, NarrativeMapLink, Project, Scene
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner


class MapEntityType(StrEnum):
    CHAPTER = "chapter"
    SCENE = "scene"
    CHARACTER = "character"
    SECTION = "section"


class NarrativeMapLinkServiceError(RuntimeError):
    """Base error safe for visual editor flows."""


class NarrativeMapLinkNotFoundError(NarrativeMapLinkServiceError):
    """Raised when a project, endpoint or link is outside the owner scope."""


class NarrativeMapLinkValidationError(NarrativeMapLinkServiceError):
    """Raised when a manual connection is invalid or duplicated."""


@dataclass(frozen=True, slots=True)
class NarrativeMapLinkInput:
    source_type: MapEntityType
    source_id: UUID
    target_type: MapEntityType
    target_id: UUID
    label: str | None = None
    directed: bool = False


def parse_node_key(value: str) -> tuple[MapEntityType, UUID]:
    """Parse an editable ``type:uuid`` map key."""

    node_type, separator, raw_id = value.partition(":")
    if not separator:
        raise NarrativeMapLinkValidationError("Card do mapa inválido.")
    try:
        return MapEntityType(node_type), UUID(raw_id)
    except (ValueError, TypeError) as exc:
        raise NarrativeMapLinkValidationError("Card do mapa inválido.") from exc


def _owned_project(session: Session, owner: OwnerIdentity, project_id: UUID) -> Project:
    user = get_or_create_owner(session, owner)
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise NarrativeMapLinkNotFoundError("Projeto não encontrado.")
    return project


def _endpoint_exists(
    session: Session,
    project_id: UUID,
    node_type: MapEntityType,
    entity_id: UUID,
) -> bool:
    model = {
        MapEntityType.CHAPTER: Chapter,
        MapEntityType.SCENE: Scene,
        MapEntityType.CHARACTER: Character,
        MapEntityType.SECTION: GddSection,
    }[node_type]
    return (
        session.scalar(
            select(model.id).where(model.id == entity_id, model.project_id == project_id)
        )
        is not None
    )


def _endpoint_values(prefix: str, node_type: MapEntityType, entity_id: UUID) -> dict[str, UUID]:
    return {f"{prefix}_{node_type.value}_id": entity_id}


def _connection_key(data: NarrativeMapLinkInput) -> str:
    source = f"{data.source_type.value}:{data.source_id}"
    target = f"{data.target_type.value}:{data.target_id}"
    endpoints = (source, target) if data.directed else tuple(sorted((source, target)))
    return f"{'d' if data.directed else 'u'}:{endpoints[0]}>{endpoints[1]}"


def _validated(data: NarrativeMapLinkInput) -> NarrativeMapLinkInput:
    if data.source_type == data.target_type and data.source_id == data.target_id:
        raise NarrativeMapLinkValidationError("Escolha dois cards diferentes.")
    label = data.label.strip() if data.label else None
    if label and (len(label) > 120 or "\x00" in label):
        raise NarrativeMapLinkValidationError(
            "O nome da ligação deve ter no máximo 120 caracteres válidos."
        )
    return NarrativeMapLinkInput(
        data.source_type,
        data.source_id,
        data.target_type,
        data.target_id,
        label,
        bool(data.directed),
    )


def create_narrative_map_link(
    owner: OwnerIdentity,
    project_id: UUID,
    data: NarrativeMapLinkInput,
    engine: Engine | None = None,
) -> UUID:
    """Create a durable visual connection with FK-protected endpoints."""

    data = _validated(data)
    try:
        with session_scope(engine) as session:
            project = _owned_project(session, owner, project_id)
            for node_type, entity_id in (
                (data.source_type, data.source_id),
                (data.target_type, data.target_id),
            ):
                if not _endpoint_exists(session, project_id, node_type, entity_id):
                    raise NarrativeMapLinkNotFoundError(
                        "Um dos cards não pertence mais a este projeto."
                    )
            link = NarrativeMapLink(
                project_id=project_id,
                connection_key=_connection_key(data),
                label=data.label,
                directed=data.directed,
                **_endpoint_values("source", data.source_type, data.source_id),
                **_endpoint_values("target", data.target_type, data.target_id),
            )
            session.add(link)
            project.updated_at = datetime.now(UTC)
            session.flush()
            return link.id
    except IntegrityError as exc:
        raise NarrativeMapLinkValidationError("Esta ligação já existe no mapa.") from exc


def delete_narrative_map_link(
    owner: OwnerIdentity,
    project_id: UUID,
    link_id: UUID,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        project = _owned_project(session, owner, project_id)
        link = session.scalar(
            select(NarrativeMapLink).where(
                NarrativeMapLink.id == link_id,
                NarrativeMapLink.project_id == project_id,
            )
        )
        if link is None:
            raise NarrativeMapLinkNotFoundError("Ligação não encontrada.")
        session.delete(link)
        project.updated_at = datetime.now(UTC)


def delete_links_for_node(
    owner: OwnerIdentity,
    project_id: UUID,
    node_type: MapEntityType,
    entity_id: UUID,
    engine: Engine | None = None,
) -> None:
    """Remove links before deleting a card; FK cascades provide a second safety net."""

    source_column = getattr(NarrativeMapLink, f"source_{node_type.value}_id")
    target_column = getattr(NarrativeMapLink, f"target_{node_type.value}_id")
    with session_scope(engine) as session:
        project = _owned_project(session, owner, project_id)
        session.execute(
            delete(NarrativeMapLink).where(
                NarrativeMapLink.project_id == project_id,
                (source_column == entity_id) | (target_column == entity_id),
            )
        )
        project.updated_at = datetime.now(UTC)
