"""Owner-scoped character CRUD and profile queries."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import Engine, func, or_, select
from sqlalchemy.orm import Session

from models import Character, Project
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner

MAX_CHARACTERS_PER_PAGE = 60
MAX_PROFILE_TEXT = 100_000

_SHORT_LIMITS = {
    "full_name": 240,
    "nickname": 160,
    "codename": 160,
    "role": 100,
    "gender": 100,
    "species": 120,
    "occupation": 160,
    "origin": 200,
    "current_status": 120,
    "short_description": 500,
    "height": 80,
    "hair": 240,
    "eyes": 240,
}


class CharacterServiceError(RuntimeError):
    """Base error safe for character-flow handling."""


class CharacterNotFoundError(CharacterServiceError):
    """Raised when a character is missing or outside the owner scope."""


class CharacterValidationError(CharacterServiceError):
    """Raised before invalid character data reaches persistence."""


class CharacterConflictError(CharacterServiceError):
    """Raised when a stale profile would overwrite newer changes."""


class CharacterSort(StrEnum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    UPDATED_DESC = "updated_desc"


@dataclass(frozen=True, slots=True)
class CharacterInput:
    name: str
    full_name: str | None = None
    nickname: str | None = None
    codename: str | None = None
    role: str | None = None
    age: int | None = None
    birth_date: date | None = None
    gender: str | None = None
    species: str | None = None
    occupation: str | None = None
    origin: str | None = None
    current_status: str | None = None
    short_description: str | None = None
    summary: str | None = None
    game_role: str | None = None
    narrative_importance: str | None = None
    story: str | None = None
    childhood: str | None = None
    past: str | None = None
    important_events: str | None = None
    current_situation: str | None = None
    personality: str | None = None
    qualities: str | None = None
    flaws: str | None = None
    fears: str | None = None
    desires: str | None = None
    motivations: str | None = None
    traumas: str | None = None
    beliefs: str | None = None
    values: str | None = None
    habits: str | None = None
    external_goal: str | None = None
    internal_goal: str | None = None
    conflict: str | None = None
    arc_beginning: str | None = None
    arc_transformation: str | None = None
    arc_breaking_point: str | None = None
    arc_ending: str | None = None
    appearance: str | None = None
    height: str | None = None
    body_description: str | None = None
    hair: str | None = None
    eyes: str | None = None
    clothing: str | None = None
    distinctive_features: str | None = None
    health: str | None = None
    abilities: str | None = None
    weaknesses: str | None = None
    attacks: str | None = None
    behavior: str | None = None
    ai_description: str | None = None
    equipment: str | None = None
    weapons: str | None = None
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class CharacterSummary:
    id: UUID
    project_id: UUID
    name: str
    nickname: str | None
    codename: str | None
    role: str | None
    short_description: str | None
    image_url: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CharacterDetails:
    id: UUID
    project_id: UUID
    profile: CharacterInput
    created_at: datetime
    updated_at: datetime
    revision: int

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def role(self) -> str | None:
        return self.profile.role

    @property
    def image_url(self) -> str | None:
        return self.profile.image_url


@dataclass(frozen=True, slots=True)
class CharacterPage:
    items: tuple[CharacterSummary, ...]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)


def _clean_optional(value: str | None, maximum: int, label: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise CharacterValidationError(f"{label} deve ter no máximo {maximum} caracteres.")
    return cleaned


def validate_character_input(data: CharacterInput) -> CharacterInput:
    values = asdict(data)
    name = data.name.strip()
    if not name:
        raise CharacterValidationError("Informe o nome do personagem.")
    if len(name) > 160:
        raise CharacterValidationError("O nome deve ter no máximo 160 caracteres.")
    values["name"] = name

    if data.age is not None and not 0 <= data.age <= 999:
        raise CharacterValidationError("A idade deve estar entre 0 e 999.")

    for field_name, maximum in _SHORT_LIMITS.items():
        label = field_name.replace("_", " ").capitalize()
        values[field_name] = _clean_optional(values[field_name], maximum, label)

    for field in fields(CharacterInput):
        if field.name in {"name", "age", "birth_date", "image_url", *_SHORT_LIMITS}:
            continue
        values[field.name] = _clean_optional(
            values[field.name], MAX_PROFILE_TEXT, field.name.replace("_", " ").capitalize()
        )

    image_url = _clean_optional(data.image_url, 2048, "A URL da imagem")
    if image_url:
        parsed = urlsplit(image_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CharacterValidationError("A imagem deve usar uma URL http ou https válida.")
    values["image_url"] = image_url
    return CharacterInput(**values)


def _profile(character: Character) -> CharacterInput:
    return CharacterInput(
        **{field.name: getattr(character, field.name) for field in fields(CharacterInput)}
    )


def _details(character: Character) -> CharacterDetails:
    return CharacterDetails(
        id=character.id,
        project_id=character.project_id,
        profile=_profile(character),
        created_at=character.created_at,
        updated_at=character.updated_at,
        revision=character.revision,
    )


def _owned_project(session: Session, owner_id: UUID, project_id: UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == owner_id)
    )
    if project is None:
        raise CharacterNotFoundError("Projeto não encontrado.")
    return project


def _owned_character(
    session: Session,
    owner_id: UUID,
    project_id: UUID,
    character_id: UUID,
) -> Character:
    character = session.scalar(
        select(Character)
        .join(Project, Project.id == Character.project_id)
        .where(
            Character.id == character_id,
            Character.project_id == project_id,
            Project.user_id == owner_id,
        )
    )
    if character is None:
        raise CharacterNotFoundError("Personagem não encontrado.")
    return character


def _ensure_unique_name(
    session: Session,
    project_id: UUID,
    name: str,
    excluding_id: UUID | None = None,
) -> None:
    statement = select(Character.id).where(
        Character.project_id == project_id,
        Character.normalized_name == name.casefold(),
    )
    if excluding_id is not None:
        statement = statement.where(Character.id != excluding_id)
    if session.scalar(statement) is not None:
        raise CharacterValidationError("Já existe um personagem com esse nome no projeto.")


def create_character(
    owner: OwnerIdentity,
    project_id: UUID,
    data: CharacterInput,
    engine: Engine | None = None,
) -> UUID:
    validated = validate_character_input(data)
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        project = _owned_project(session, user.id, project_id)
        _ensure_unique_name(session, project_id, validated.name)
        values = asdict(validated)
        character = Character(
            project_id=project_id,
            normalized_name=validated.name.casefold(),
            **values,
        )
        project.updated_at = datetime.now(UTC)
        session.add(character)
        session.flush()
        return character.id


def update_character(
    owner: OwnerIdentity,
    project_id: UUID,
    character_id: UUID,
    data: CharacterInput,
    *,
    expected_revision: int | None = None,
    engine: Engine | None = None,
) -> None:
    validated = validate_character_input(data)
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        character = _owned_character(session, user.id, project_id, character_id)
        if expected_revision is not None and character.revision != expected_revision:
            raise CharacterConflictError(
                "A ficha foi alterada em outra sessão. Recarregue antes de salvar."
            )
        _ensure_unique_name(session, project_id, validated.name, excluding_id=character_id)
        for field_name, value in asdict(validated).items():
            setattr(character, field_name, value)
        character.normalized_name = validated.name.casefold()
        project = _owned_project(session, user.id, project_id)
        project.updated_at = datetime.now(UTC)


def get_character(
    owner: OwnerIdentity,
    project_id: UUID,
    character_id: UUID,
    engine: Engine | None = None,
) -> CharacterDetails:
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        return _details(_owned_character(session, user.id, project_id, character_id))


def delete_character(
    owner: OwnerIdentity,
    project_id: UUID,
    character_id: UUID,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        character = _owned_character(session, user.id, project_id, character_id)
        project = _owned_project(session, user.id, project_id)
        project.updated_at = datetime.now(UTC)
        session.delete(character)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_characters(
    owner: OwnerIdentity,
    project_id: UUID,
    *,
    search: str | None = None,
    role: str | None = None,
    sort: CharacterSort = CharacterSort.NAME_ASC,
    page: int = 1,
    page_size: int = 24,
    engine: Engine | None = None,
) -> CharacterPage:
    page = max(1, page)
    page_size = min(max(1, page_size), MAX_CHARACTERS_PER_PAGE)
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        _owned_project(session, user.id, project_id)
        statement = select(Character).where(Character.project_id == project_id)
        if role:
            statement = statement.where(Character.role == role)
        if search and search.strip():
            pattern = f"%{_escape_like(search.strip().casefold())}%"
            statement = statement.where(
                or_(
                    func.lower(Character.name).like(pattern, escape="\\"),
                    func.lower(func.coalesce(Character.full_name, "")).like(pattern, escape="\\"),
                    func.lower(func.coalesce(Character.nickname, "")).like(pattern, escape="\\"),
                    func.lower(func.coalesce(Character.codename, "")).like(pattern, escape="\\"),
                    func.lower(func.coalesce(Character.role, "")).like(pattern, escape="\\"),
                )
            )
        total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        order = {
            CharacterSort.NAME_ASC: (Character.name.asc(), Character.id.asc()),
            CharacterSort.NAME_DESC: (Character.name.desc(), Character.id.desc()),
            CharacterSort.UPDATED_DESC: (Character.updated_at.desc(), Character.id.desc()),
        }[sort]
        characters = session.scalars(
            statement.order_by(*order).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return CharacterPage(
            items=tuple(
                CharacterSummary(
                    id=item.id,
                    project_id=item.project_id,
                    name=item.name,
                    nickname=item.nickname,
                    codename=item.codename,
                    role=item.role,
                    short_description=item.short_description,
                    image_url=item.image_url,
                    updated_at=item.updated_at,
                )
                for item in characters
            ),
            total=total,
            page=page,
            page_size=page_size,
        )


def list_character_roles(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> tuple[str, ...]:
    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        _owned_project(session, user.id, project_id)
        return tuple(
            session.scalars(
                select(Character.role)
                .where(Character.project_id == project_id, Character.role.is_not(None))
                .distinct()
                .order_by(Character.role)
            ).all()
        )
