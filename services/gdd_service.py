"""Hierarchical GDD reads and revision-safe writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from models import GddSection, Project
from services.database import session_scope
from services.gdd_templates import add_complete_template
from services.user_service import OwnerIdentity, get_or_create_owner
from utils.constants import SECTION_STATUSES

_VALID_STATUSES = {item.value for item in SECTION_STATUSES}
_VALID_TYPES = {"category", "group", "page"}


class GddServiceError(RuntimeError):
    pass


class GddNotFoundError(GddServiceError):
    pass


class GddConflictError(GddServiceError):
    pass


class MoveDirection(StrEnum):
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class SectionInput:
    title: str
    icon: str | None = None
    section_type: str = "page"
    parent_id: UUID | None = None
    status: str = "not_started"


@dataclass(frozen=True, slots=True)
class SectionNode:
    id: UUID
    parent_id: UUID | None
    title: str
    icon: str | None
    section_type: str
    position: int
    status: str
    favorite: bool
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SectionDocument(SectionNode):
    content: str


def _project(session: Session, owner: OwnerIdentity, project_id: UUID) -> Project:
    user = get_or_create_owner(session, owner)
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise GddNotFoundError("Projeto não encontrado.")
    return project


def _section(session: Session, project_id: UUID, section_id: UUID) -> GddSection:
    section = session.scalar(
        select(GddSection).where(
            GddSection.id == section_id,
            GddSection.project_id == project_id,
        )
    )
    if section is None:
        raise GddNotFoundError("Seção não encontrada.")
    return section


def _validated(data: SectionInput) -> SectionInput:
    title = data.title.strip()
    if not title or len(title) > 180:
        raise GddServiceError("O título deve ter entre 1 e 180 caracteres.")
    icon = data.icon.strip() if data.icon else None
    if icon and len(icon) > 40:
        raise GddServiceError("O ícone deve ter no máximo 40 caracteres.")
    if data.section_type not in _VALID_TYPES:
        raise GddServiceError("Tipo de seção inválido.")
    if data.status not in _VALID_STATUSES:
        raise GddServiceError("Status de seção inválido.")
    return SectionInput(title, icon or None, data.section_type, data.parent_id, data.status)


def initialize_complete_template(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        count = session.scalar(
            select(func.count(GddSection.id)).where(GddSection.project_id == project_id)
        )
        if count:
            raise GddConflictError("O projeto já possui seções.")
        add_complete_template(session, project_id)
        project.template_key = "complete"
        project.updated_at = datetime.now(UTC)


def list_sections(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> tuple[SectionNode, ...]:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        sections = session.scalars(
            select(GddSection)
            .where(GddSection.project_id == project_id)
            .order_by(GddSection.position, GddSection.title)
        ).all()
        return tuple(
            SectionNode(
                item.id,
                item.parent_id,
                item.title,
                item.icon,
                item.section_type,
                item.position,
                item.status,
                item.favorite,
                item.revision,
                item.updated_at,
            )
            for item in sections
        )


def get_section(
    owner: OwnerIdentity,
    project_id: UUID,
    section_id: UUID,
    engine: Engine | None = None,
) -> SectionDocument:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        item = _section(session, project_id, section_id)
        return SectionDocument(
            item.id,
            item.parent_id,
            item.title,
            item.icon,
            item.section_type,
            item.position,
            item.status,
            item.favorite,
            item.revision,
            item.updated_at,
            item.content,
        )


def create_section(
    owner: OwnerIdentity,
    project_id: UUID,
    data: SectionInput,
    engine: Engine | None = None,
) -> UUID:
    data = _validated(data)
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        if data.parent_id:
            _section(session, project_id, data.parent_id)
        max_position = (
            session.scalar(
                select(func.max(GddSection.position)).where(
                    GddSection.project_id == project_id,
                    GddSection.parent_id == data.parent_id,
                )
            )
            or 0
        )
        item = GddSection(
            project_id=project_id,
            parent_id=data.parent_id,
            title=data.title,
            icon=data.icon,
            section_type=data.section_type,
            status=data.status,
            position=max_position + 1000,
        )
        session.add(item)
        project.updated_at = datetime.now(UTC)
        session.flush()
        return item.id


def update_section_metadata(
    owner: OwnerIdentity,
    project_id: UUID,
    section_id: UUID,
    data: SectionInput,
    engine: Engine | None = None,
) -> None:
    data = _validated(data)
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        item = _section(session, project_id, section_id)
        item.title = data.title
        item.icon = data.icon
        item.section_type = data.section_type
        item.status = data.status
        project.updated_at = datetime.now(UTC)


def update_section_content(
    owner: OwnerIdentity,
    project_id: UUID,
    section_id: UUID,
    content: str,
    expected_revision: int,
    engine: Engine | None = None,
) -> int:
    if len(content) > 2_000_000:
        raise GddServiceError("O conteúdo da seção excede o limite de 2 MB.")
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        item = _section(session, project_id, section_id)
        if item.revision != expected_revision:
            raise GddConflictError("Esta seção foi alterada em outra sessão. Recarregue a página.")
        item.content = content
        project.updated_at = datetime.now(UTC)
        session.flush()
        return item.revision


def move_section(
    owner: OwnerIdentity,
    project_id: UUID,
    section_id: UUID,
    direction: MoveDirection,
    engine: Engine | None = None,
) -> bool:
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        item = _section(session, project_id, section_id)
        siblings = session.scalars(
            select(GddSection)
            .where(
                GddSection.project_id == project_id,
                GddSection.parent_id == item.parent_id,
            )
            .order_by(GddSection.position, GddSection.id)
        ).all()
        index = next(i for i, sibling in enumerate(siblings) if sibling.id == item.id)
        target_index = index - 1 if direction is MoveDirection.UP else index + 1
        if target_index < 0 or target_index >= len(siblings):
            return False
        target = siblings[target_index]
        item.position, target.position = target.position, item.position
        project.updated_at = datetime.now(UTC)
        return True


def delete_section(
    owner: OwnerIdentity,
    project_id: UUID,
    section_id: UUID,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        item = _section(session, project_id, section_id)
        session.delete(item)
        project.updated_at = datetime.now(UTC)
