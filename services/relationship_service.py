"""Owner-scoped directional relationships between project characters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine, and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.exc import StaleDataError

from models import Character, CharacterRelationship, Project
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner

MAX_RELATIONSHIP_DESCRIPTION = 20_000


class RelationshipServiceError(RuntimeError):
    """Base error safe for relationship UI flows."""


class RelationshipNotFoundError(RelationshipServiceError):
    """Raised when a project, character or relationship is outside the owner scope."""


class RelationshipValidationError(RelationshipServiceError):
    """Raised when relationship data is invalid or duplicated."""


class RelationshipConflictError(RelationshipServiceError):
    """Raised when stale data would overwrite or remove a newer revision."""


@dataclass(frozen=True, slots=True)
class RelationshipInput:
    relationship_type: str
    description: str | None = None
    intensity: int | None = None
    relationship_status: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipCharacterChoice:
    id: UUID
    name: str
    role: str | None
    nickname: str | None
    codename: str | None
    image_url: str | None


@dataclass(frozen=True, slots=True)
class CharacterRelationshipSummary:
    id: UUID
    source_character_id: UUID
    source_name: str
    source_role: str | None
    target_character_id: UUID
    target_name: str
    target_role: str | None
    relationship_type: str
    description: str | None
    intensity: int | None
    relationship_status: str | None
    updated_at: datetime
    revision: int


@dataclass(frozen=True, slots=True)
class CharacterRelationshipDetails:
    id: UUID
    project_id: UUID
    source_character_id: UUID
    source_name: str
    source_role: str | None
    target_character_id: UUID
    target_name: str
    target_role: str | None
    relationship_type: str
    description: str | None
    intensity: int | None
    relationship_status: str | None
    created_at: datetime
    updated_at: datetime
    revision: int


@dataclass(frozen=True, slots=True)
class CharacterRelationshipIndex:
    character_id: UUID
    choices: tuple[RelationshipCharacterChoice, ...]
    outgoing: tuple[CharacterRelationshipSummary, ...]
    incoming: tuple[CharacterRelationshipSummary, ...]

    @property
    def total(self) -> int:
        return len(self.outgoing) + len(self.incoming)


@dataclass(frozen=True, slots=True)
class ProjectRelationshipIndex:
    choices: tuple[RelationshipCharacterChoice, ...]
    relationships: tuple[CharacterRelationshipSummary, ...]

    def outgoing_for(self, character_id: UUID) -> tuple[CharacterRelationshipSummary, ...]:
        return tuple(
            item for item in self.relationships if item.source_character_id == character_id
        )

    def incoming_for(self, character_id: UUID) -> tuple[CharacterRelationshipSummary, ...]:
        return tuple(
            item for item in self.relationships if item.target_character_id == character_id
        )


def _validate_input(data: RelationshipInput) -> RelationshipInput:
    relationship_type = data.relationship_type.strip()
    if not relationship_type:
        raise RelationshipValidationError("Informe o tipo da relação.")
    if "\x00" in relationship_type:
        raise RelationshipValidationError("O tipo da relação contém um caractere inválido.")
    if len(relationship_type) > 120:
        raise RelationshipValidationError("O tipo da relação deve ter no máximo 120 caracteres.")
    if data.description and "\x00" in data.description:
        raise RelationshipValidationError("A descrição contém um caractere inválido.")
    description = data.description.strip() if data.description else None
    if description and len(description) > MAX_RELATIONSHIP_DESCRIPTION:
        raise RelationshipValidationError(
            "A descrição da relação excede o limite de 20.000 caracteres."
        )
    if data.intensity is not None and (
        isinstance(data.intensity, bool)
        or not isinstance(data.intensity, int)
        or not 1 <= data.intensity <= 5
    ):
        raise RelationshipValidationError("A intensidade deve ser um número inteiro entre 1 e 5.")
    if data.relationship_status and "\x00" in data.relationship_status:
        raise RelationshipValidationError("O estado da relação contém um caractere inválido.")
    relationship_status = data.relationship_status.strip() if data.relationship_status else None
    if relationship_status and len(relationship_status) > 80:
        raise RelationshipValidationError("O estado da relação deve ter no máximo 80 caracteres.")
    return RelationshipInput(
        relationship_type=relationship_type,
        description=description or None,
        intensity=data.intensity,
        relationship_status=relationship_status or None,
    )


def _project(session: Session, owner: OwnerIdentity, project_id: UUID) -> Project:
    user = get_or_create_owner(session, owner)
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise RelationshipNotFoundError("Projeto não encontrado.")
    return project


def _character(
    session: Session,
    project_id: UUID,
    character_id: UUID,
) -> Character:
    character = session.scalar(
        select(Character).where(
            Character.id == character_id,
            Character.project_id == project_id,
        )
    )
    if character is None:
        raise RelationshipNotFoundError("Personagem não encontrado neste projeto.")
    return character


def _relationship(
    session: Session,
    project_id: UUID,
    relationship_id: UUID,
) -> CharacterRelationship:
    relationship = session.scalar(
        select(CharacterRelationship).where(
            CharacterRelationship.id == relationship_id,
            CharacterRelationship.project_id == project_id,
        )
    )
    if relationship is None:
        raise RelationshipNotFoundError("Relação não encontrada.")
    return relationship


def _choices(session: Session, project_id: UUID) -> tuple[RelationshipCharacterChoice, ...]:
    characters = session.scalars(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.name, Character.id)
    ).all()
    return tuple(
        RelationshipCharacterChoice(
            id=item.id,
            name=item.name,
            role=item.role,
            nickname=item.nickname,
            codename=item.codename,
            image_url=item.image_url,
        )
        for item in characters
    )


def _relationship_rows(
    session: Session,
    project_id: UUID,
    relationship_id: UUID | None = None,
    character_id: UUID | None = None,
) -> list[tuple[CharacterRelationship, Character, Character]]:
    source = aliased(Character, name="source_character")
    target = aliased(Character, name="target_character")
    statement = (
        select(CharacterRelationship, source, target)
        .join(
            source,
            and_(
                source.id == CharacterRelationship.source_character_id,
                source.project_id == CharacterRelationship.project_id,
            ),
        )
        .join(
            target,
            and_(
                target.id == CharacterRelationship.target_character_id,
                target.project_id == CharacterRelationship.project_id,
            ),
        )
        .where(CharacterRelationship.project_id == project_id)
    )
    if relationship_id is not None:
        statement = statement.where(CharacterRelationship.id == relationship_id)
    if character_id is not None:
        statement = statement.where(
            or_(
                CharacterRelationship.source_character_id == character_id,
                CharacterRelationship.target_character_id == character_id,
            )
        )
    statement = statement.order_by(source.name, target.name, CharacterRelationship.id)
    return list(session.execute(statement).tuples())


def _summary(
    relationship: CharacterRelationship,
    source: Character,
    target: Character,
) -> CharacterRelationshipSummary:
    return CharacterRelationshipSummary(
        id=relationship.id,
        source_character_id=source.id,
        source_name=source.name,
        source_role=source.role,
        target_character_id=target.id,
        target_name=target.name,
        target_role=target.role,
        relationship_type=relationship.relationship_type,
        description=relationship.description,
        intensity=relationship.intensity,
        relationship_status=relationship.relationship_status,
        updated_at=relationship.updated_at,
        revision=relationship.revision,
    )


def create_relationship(
    owner: OwnerIdentity,
    project_id: UUID,
    source_character_id: UUID,
    target_character_id: UUID,
    data: RelationshipInput,
    engine: Engine | None = None,
) -> UUID:
    validated = _validate_input(data)
    if source_character_id == target_character_id:
        raise RelationshipValidationError(
            "Escolha dois personagens diferentes para criar a relação."
        )

    try:
        with session_scope(engine) as session:
            project = _project(session, owner, project_id)
            _character(session, project_id, source_character_id)
            _character(session, project_id, target_character_id)
            duplicate = session.scalar(
                select(CharacterRelationship.id).where(
                    CharacterRelationship.project_id == project_id,
                    CharacterRelationship.source_character_id == source_character_id,
                    CharacterRelationship.target_character_id == target_character_id,
                )
            )
            if duplicate is not None:
                raise RelationshipValidationError(
                    "Já existe uma relação nesta direção entre esses personagens."
                )
            relationship = CharacterRelationship(
                project_id=project_id,
                source_character_id=source_character_id,
                target_character_id=target_character_id,
                relationship_type=validated.relationship_type,
                description=validated.description,
                intensity=validated.intensity,
                relationship_status=validated.relationship_status,
            )
            project.updated_at = datetime.now(UTC)
            session.add(relationship)
            session.flush()
            return relationship.id
    except IntegrityError as exc:
        raise RelationshipValidationError(
            "Já existe uma relação nesta direção entre esses personagens."
        ) from exc


def get_relationship(
    owner: OwnerIdentity,
    project_id: UUID,
    relationship_id: UUID,
    engine: Engine | None = None,
) -> CharacterRelationshipDetails:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        rows = _relationship_rows(session, project_id, relationship_id)
        if not rows:
            raise RelationshipNotFoundError("Relação não encontrada.")
        relationship, source, target = rows[0]
        return CharacterRelationshipDetails(
            id=relationship.id,
            project_id=relationship.project_id,
            source_character_id=source.id,
            source_name=source.name,
            source_role=source.role,
            target_character_id=target.id,
            target_name=target.name,
            target_role=target.role,
            relationship_type=relationship.relationship_type,
            description=relationship.description,
            intensity=relationship.intensity,
            relationship_status=relationship.relationship_status,
            created_at=relationship.created_at,
            updated_at=relationship.updated_at,
            revision=relationship.revision,
        )


def update_relationship(
    owner: OwnerIdentity,
    project_id: UUID,
    relationship_id: UUID,
    data: RelationshipInput,
    *,
    expected_revision: int,
    engine: Engine | None = None,
) -> None:
    validated = _validate_input(data)
    try:
        with session_scope(engine) as session:
            project = _project(session, owner, project_id)
            relationship = _relationship(session, project_id, relationship_id)
            if relationship.revision != expected_revision:
                raise RelationshipConflictError(
                    "A relação foi alterada em outra sessão. Recarregue antes de salvar."
                )
            relationship.relationship_type = validated.relationship_type
            relationship.description = validated.description
            relationship.intensity = validated.intensity
            relationship.relationship_status = validated.relationship_status
            project.updated_at = datetime.now(UTC)
    except StaleDataError as exc:
        raise RelationshipConflictError(
            "A relação foi alterada em outra sessão. Recarregue antes de salvar."
        ) from exc


def delete_relationship(
    owner: OwnerIdentity,
    project_id: UUID,
    relationship_id: UUID,
    *,
    expected_revision: int,
    engine: Engine | None = None,
) -> None:
    try:
        with session_scope(engine) as session:
            project = _project(session, owner, project_id)
            relationship = _relationship(session, project_id, relationship_id)
            if relationship.revision != expected_revision:
                raise RelationshipConflictError(
                    "A relação foi alterada em outra sessão. Recarregue antes de excluir."
                )
            project.updated_at = datetime.now(UTC)
            session.delete(relationship)
    except StaleDataError as exc:
        raise RelationshipConflictError(
            "A relação foi alterada em outra sessão. Recarregue antes de excluir."
        ) from exc


def list_character_relationships(
    owner: OwnerIdentity,
    project_id: UUID,
    character_id: UUID,
    engine: Engine | None = None,
) -> CharacterRelationshipIndex:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        _character(session, project_id, character_id)
        relationships = tuple(
            _summary(relationship, source, target)
            for relationship, source, target in _relationship_rows(
                session,
                project_id,
                character_id=character_id,
            )
        )
        return CharacterRelationshipIndex(
            character_id=character_id,
            choices=_choices(session, project_id),
            outgoing=tuple(
                item for item in relationships if item.source_character_id == character_id
            ),
            incoming=tuple(
                item for item in relationships if item.target_character_id == character_id
            ),
        )


def list_project_relationships(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> ProjectRelationshipIndex:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        return ProjectRelationshipIndex(
            choices=_choices(session, project_id),
            relationships=tuple(
                _summary(relationship, source, target)
                for relationship, source, target in _relationship_rows(session, project_id)
            ),
        )
