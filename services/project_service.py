"""Owner-scoped project queries and transactional commands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import Engine, Select, func, or_, select
from sqlalchemy.orm import Session

from models import Character, GddSection, Note, Project, ProjectReference
from services.database import session_scope
from services.gdd_templates import add_complete_template
from services.user_service import OwnerIdentity, get_or_create_owner
from utils.constants import DEFAULT_ACCENT_COLOR, PROJECT_STATUSES

MAX_PROJECTS_PER_PAGE = 48
_VALID_STATUSES = {option.value for option in PROJECT_STATUSES}
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")


class ProjectServiceError(RuntimeError):
    """Base error safe for project-flow handling."""


class ProjectNotFoundError(ProjectServiceError):
    """Raised when a project is missing or belongs to another owner."""


class ProjectValidationError(ProjectServiceError):
    """Raised before invalid project data reaches persistence."""


class ProjectSort(StrEnum):
    UPDATED_DESC = "updated_desc"
    UPDATED_ASC = "updated_asc"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"


@dataclass(frozen=True, slots=True)
class ProjectInput:
    name: str
    codename: str | None = None
    description: str | None = None
    genre: str | None = None
    subgenre: str | None = None
    platform: str | None = None
    engine: str | None = None
    status: str = "idea"
    start_date: date | None = None
    cover_url: str | None = None
    accent_color: str = DEFAULT_ACCENT_COLOR
    template_key: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    id: UUID
    name: str
    codename: str | None
    genre: str | None
    platform: str | None
    status: str
    cover_url: str | None
    accent_color: str
    archived: bool
    favorite: bool
    updated_at: datetime
    section_count: int
    finished_section_count: int

    @property
    def progress(self) -> int:
        if self.section_count == 0:
            return 0
        return round(self.finished_section_count * 100 / self.section_count)


@dataclass(frozen=True, slots=True)
class ProjectDetails(ProjectSummary):
    description: str | None
    subgenre: str | None
    engine: str | None
    start_date: date | None
    archived_at: datetime | None
    created_at: datetime
    note_count: int
    reference_count: int
    character_count: int
    template_key: str | None


@dataclass(frozen=True, slots=True)
class ProjectPage:
    items: tuple[ProjectSummary, ...]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)


def _clean_optional(value: str | None, maximum: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise ProjectValidationError(f"{field} deve ter no máximo {maximum} caracteres.")
    return cleaned


def validate_project_input(data: ProjectInput) -> ProjectInput:
    name = data.name.strip()
    if not name:
        raise ProjectValidationError("Informe o nome do jogo.")
    if len(name) > 160:
        raise ProjectValidationError("O nome deve ter no máximo 160 caracteres.")
    if data.status not in _VALID_STATUSES:
        raise ProjectValidationError("Selecione um status válido.")
    if data.template_key not in {None, "complete"}:
        raise ProjectValidationError("Template de GDD inválido.")

    accent_color = data.accent_color.strip()
    if not _HEX_COLOR.fullmatch(accent_color):
        raise ProjectValidationError("Selecione uma cor de projeto válida.")

    cover_url = _clean_optional(data.cover_url, 2048, "A URL da capa")
    if cover_url:
        parsed = urlsplit(cover_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProjectValidationError("A capa deve usar uma URL http ou https válida.")

    return ProjectInput(
        name=name,
        codename=_clean_optional(data.codename, 120, "O codinome"),
        description=_clean_optional(data.description, 10_000, "A descrição"),
        genre=_clean_optional(data.genre, 80, "O gênero"),
        subgenre=_clean_optional(data.subgenre, 80, "O subgênero"),
        platform=_clean_optional(data.platform, 120, "A plataforma"),
        engine=_clean_optional(data.engine, 80, "A engine"),
        status=data.status,
        start_date=data.start_date,
        cover_url=cover_url,
        accent_color=accent_color.upper(),
        template_key=data.template_key,
    )


def _project_values(data: ProjectInput) -> dict[str, object]:
    return {
        "name": data.name,
        "codename": data.codename,
        "description": data.description,
        "genre": data.genre,
        "subgenre": data.subgenre,
        "platform": data.platform,
        "engine": data.engine,
        "status": data.status,
        "start_date": data.start_date,
        "cover_url": data.cover_url,
        "accent_color": data.accent_color,
        "template_key": data.template_key,
    }


def _owned_project(session: Session, owner_id: UUID, project_id: UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == owner_id)
    )
    if project is None:
        raise ProjectNotFoundError("Projeto não encontrado.")
    return project


def create_project(
    owner: OwnerIdentity,
    data: ProjectInput,
    engine: Engine | None = None,
) -> UUID:
    validated = validate_project_input(data)
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        project = Project(user_id=user.id, **_project_values(validated))
        session.add(project)
        session.flush()
        if validated.template_key == "complete":
            add_complete_template(session, project.id)
        return project.id


def update_project(
    owner: OwnerIdentity,
    project_id: UUID,
    data: ProjectInput,
    engine: Engine | None = None,
) -> None:
    validated = validate_project_input(data)
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        project = _owned_project(session, user.id, project_id)
        for field, value in _project_values(validated).items():
            setattr(project, field, value)


def set_project_archived(
    owner: OwnerIdentity,
    project_id: UUID,
    archived: bool,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        project = _owned_project(session, user.id, project_id)
        project.archived = archived
        project.archived_at = datetime.now(UTC) if archived else None


def toggle_project_favorite(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> bool:
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        project = _owned_project(session, user.id, project_id)
        project.favorite = not project.favorite
        session.flush()
        return project.favorite


def delete_project(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        project = _owned_project(session, user.id, project_id)
        session.delete(project)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(
    statement: Select[tuple[Project]],
    owner_id: UUID,
    *,
    archived: bool | None,
    favorite: bool | None,
    search: str | None,
    status: str | None,
) -> Select[tuple[Project]]:
    statement = statement.where(Project.user_id == owner_id)
    if archived is not None:
        statement = statement.where(Project.archived.is_(archived))
    if favorite is not None:
        statement = statement.where(Project.favorite.is_(favorite))
    if status:
        statement = statement.where(Project.status == status)
    if search and search.strip():
        pattern = f"%{_escape_like(search.strip().casefold())}%"
        statement = statement.where(
            or_(
                func.lower(Project.name).like(pattern, escape="\\"),
                func.lower(func.coalesce(Project.codename, "")).like(pattern, escape="\\"),
                func.lower(func.coalesce(Project.genre, "")).like(pattern, escape="\\"),
            )
        )
    return statement


def _counts() -> tuple[object, object]:
    section_count = (
        select(func.count(GddSection.id))
        .where(GddSection.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    finished_count = (
        select(func.count(GddSection.id))
        .where(
            GddSection.project_id == Project.id,
            GddSection.status == "finished",
        )
        .correlate(Project)
        .scalar_subquery()
    )
    return section_count, finished_count


def list_projects(
    owner: OwnerIdentity,
    *,
    archived: bool | None = False,
    favorite: bool | None = None,
    search: str | None = None,
    status: str | None = None,
    sort: ProjectSort = ProjectSort.UPDATED_DESC,
    page: int = 1,
    page_size: int = 12,
    engine: Engine | None = None,
) -> ProjectPage:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_PROJECTS_PER_PAGE)
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        filtered = _apply_filters(
            select(Project),
            user.id,
            archived=archived,
            favorite=favorite,
            search=search,
            status=status,
        )
        total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
        section_count, finished_count = _counts()
        statement = _apply_filters(
            select(Project, section_count, finished_count),
            user.id,
            archived=archived,
            favorite=favorite,
            search=search,
            status=status,
        )
        order = {
            ProjectSort.UPDATED_DESC: (Project.updated_at.desc(), Project.id.desc()),
            ProjectSort.UPDATED_ASC: (Project.updated_at.asc(), Project.id.asc()),
            ProjectSort.NAME_ASC: (Project.name.asc(), Project.id.asc()),
            ProjectSort.NAME_DESC: (Project.name.desc(), Project.id.desc()),
        }[sort]
        rows = session.execute(
            statement.order_by(*order).offset((page - 1) * page_size).limit(page_size)
        ).all()
        items = tuple(
            ProjectSummary(
                id=project.id,
                name=project.name,
                codename=project.codename,
                genre=project.genre,
                platform=project.platform,
                status=project.status,
                cover_url=project.cover_url,
                accent_color=project.accent_color,
                archived=project.archived,
                favorite=project.favorite,
                updated_at=project.updated_at,
                section_count=section_total,
                finished_section_count=finished_total,
            )
            for project, section_total, finished_total in rows
        )
        return ProjectPage(items=items, total=total, page=page, page_size=page_size)


def get_project(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> ProjectDetails:
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        section_count, finished_count = _counts()
        note_count = (
            select(func.count(Note.id))
            .where(Note.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )
        reference_count = (
            select(func.count(ProjectReference.id))
            .where(ProjectReference.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )
        character_count = (
            select(func.count(Character.id))
            .where(Character.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
        )
        row = session.execute(
            select(
                Project,
                section_count,
                finished_count,
                note_count,
                reference_count,
                character_count,
            ).where(Project.id == project_id, Project.user_id == user.id)
        ).one_or_none()
        if row is None:
            raise ProjectNotFoundError("Projeto não encontrado.")
        (
            project,
            section_total,
            finished_total,
            notes_total,
            references_total,
            characters_total,
        ) = row
        return ProjectDetails(
            id=project.id,
            name=project.name,
            codename=project.codename,
            description=project.description,
            genre=project.genre,
            subgenre=project.subgenre,
            platform=project.platform,
            engine=project.engine,
            status=project.status,
            cover_url=project.cover_url,
            accent_color=project.accent_color,
            start_date=project.start_date,
            archived=project.archived,
            archived_at=project.archived_at,
            favorite=project.favorite,
            created_at=project.created_at,
            updated_at=project.updated_at,
            section_count=section_total,
            finished_section_count=finished_total,
            note_count=notes_total,
            reference_count=references_total,
            character_count=characters_total,
            template_key=project.template_key,
        )
