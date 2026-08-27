"""Scene cast management and calculated character appearances."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from uuid import UUID

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from models import Chapter, Character, Project, Scene, SceneCharacter
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner

MAX_APPEARANCE_NOTES = 20_000


class AppearanceServiceError(RuntimeError):
    """Base error safe for appearance UI flows."""


class AppearanceNotFoundError(AppearanceServiceError):
    """Raised when a scoped project, scene, character or link is missing."""


class AppearanceConflictError(AppearanceServiceError):
    """Raised when a stale cast selection would overwrite newer changes."""


@dataclass(frozen=True, slots=True)
class CharacterChoice:
    id: UUID
    name: str
    role: str | None


@dataclass(frozen=True, slots=True)
class SceneCastMember:
    character_id: UUID
    name: str
    role: str | None
    role_in_scene: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class ProjectAppearanceIndex:
    choices: tuple[CharacterChoice, ...]
    cast_by_scene: Mapping[UUID, tuple[SceneCastMember, ...]]

    def cast_for(self, scene_id: UUID) -> tuple[SceneCastMember, ...]:
        return self.cast_by_scene.get(scene_id, ())


@dataclass(frozen=True, slots=True)
class CharacterAppearance:
    scene_id: UUID
    scene_title: str
    chapter_id: UUID
    chapter_title: str
    chapter_position: int
    scene_position: int
    timeline_order: int
    role_in_scene: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class CharacterTimeline:
    items: tuple[CharacterAppearance, ...]

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def first(self) -> CharacterAppearance | None:
        return self.items[0] if self.items else None

    @property
    def last(self) -> CharacterAppearance | None:
        return self.items[-1] if self.items else None

    @property
    def chapter_count(self) -> int:
        return len({item.chapter_id for item in self.items})


def _project(session: Session, owner: OwnerIdentity, project_id: UUID) -> Project:
    user = get_or_create_owner(session, owner)
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise AppearanceNotFoundError("Projeto não encontrado.")
    return project


def _scene(session: Session, project_id: UUID, scene_id: UUID) -> Scene:
    scene = session.scalar(
        select(Scene).where(Scene.id == scene_id, Scene.project_id == project_id)
    )
    if scene is None:
        raise AppearanceNotFoundError("Cena não encontrada.")
    return scene


def _character(session: Session, project_id: UUID, character_id: UUID) -> Character:
    character = session.scalar(
        select(Character).where(
            Character.id == character_id,
            Character.project_id == project_id,
        )
    )
    if character is None:
        raise AppearanceNotFoundError("Personagem não encontrado.")
    return character


def get_project_appearance_index(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> ProjectAppearanceIndex:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        characters = session.scalars(
            select(Character)
            .where(Character.project_id == project_id)
            .order_by(Character.name, Character.id)
        ).all()
        rows = session.execute(
            select(SceneCharacter, Character)
            .join(Character, Character.id == SceneCharacter.character_id)
            .where(SceneCharacter.project_id == project_id)
            .order_by(Character.name, Character.id)
        ).all()
        cast: defaultdict[UUID, list[SceneCastMember]] = defaultdict(list)
        for link, character in rows:
            cast[link.scene_id].append(
                SceneCastMember(
                    character_id=character.id,
                    name=character.name,
                    role=character.role,
                    role_in_scene=link.role_in_scene,
                    notes=link.notes,
                )
            )
        return ProjectAppearanceIndex(
            choices=tuple(CharacterChoice(item.id, item.name, item.role) for item in characters),
            cast_by_scene=MappingProxyType(
                {scene_id: tuple(members) for scene_id, members in cast.items()}
            ),
        )


def sync_scene_characters(
    owner: OwnerIdentity,
    project_id: UUID,
    scene_id: UUID,
    character_ids: tuple[UUID, ...] | list[UUID] | set[UUID],
    *,
    expected_character_ids: frozenset[UUID] | None = None,
    engine: Engine | None = None,
) -> None:
    requested = set(character_ids)
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        scene = _scene(session, project_id, scene_id)
        links = session.scalars(
            select(SceneCharacter).where(
                SceneCharacter.project_id == project_id,
                SceneCharacter.scene_id == scene_id,
            )
        ).all()
        current = {link.character_id for link in links}
        if expected_character_ids is not None and current != set(expected_character_ids):
            raise AppearanceConflictError(
                "O elenco desta cena foi alterado em outra sessão. Recarregue antes de salvar."
            )

        if requested:
            owned_ids = set(
                session.scalars(
                    select(Character.id).where(
                        Character.project_id == project_id,
                        Character.id.in_(requested),
                    )
                ).all()
            )
            if owned_ids != requested:
                raise AppearanceNotFoundError(
                    "Um dos personagens selecionados não pertence a este projeto."
                )

        removed = current - requested
        if removed:
            session.execute(
                delete(SceneCharacter).where(
                    SceneCharacter.project_id == project_id,
                    SceneCharacter.scene_id == scene_id,
                    SceneCharacter.character_id.in_(removed),
                )
            )
        for character_id in requested - current:
            session.add(
                SceneCharacter(
                    project_id=project_id,
                    scene_id=scene_id,
                    character_id=character_id,
                )
            )
        if current != requested:
            now = datetime.now(UTC)
            scene.updated_at = now
            project.updated_at = now


def update_appearance_details(
    owner: OwnerIdentity,
    project_id: UUID,
    scene_id: UUID,
    character_id: UUID,
    *,
    role_in_scene: str | None,
    notes: str | None,
    engine: Engine | None = None,
) -> None:
    role = role_in_scene.strip() if role_in_scene else None
    clean_notes = notes.strip() if notes else None
    if role and len(role) > 120:
        raise AppearanceServiceError("O papel na cena deve ter no máximo 120 caracteres.")
    if clean_notes and len(clean_notes) > MAX_APPEARANCE_NOTES:
        raise AppearanceServiceError("As notas excedem o limite de 20.000 caracteres.")
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        scene = _scene(session, project_id, scene_id)
        _character(session, project_id, character_id)
        link = session.scalar(
            select(SceneCharacter).where(
                SceneCharacter.project_id == project_id,
                SceneCharacter.scene_id == scene_id,
                SceneCharacter.character_id == character_id,
            )
        )
        if link is None:
            raise AppearanceNotFoundError("Este personagem não está vinculado à cena.")
        link.role_in_scene = role or None
        link.notes = clean_notes or None
        now = datetime.now(UTC)
        scene.updated_at = now
        project.updated_at = now


def get_character_timeline(
    owner: OwnerIdentity,
    project_id: UUID,
    character_id: UUID,
    engine: Engine | None = None,
) -> CharacterTimeline:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        _character(session, project_id, character_id)
        rows = session.execute(
            select(SceneCharacter, Scene, Chapter)
            .join(Scene, Scene.id == SceneCharacter.scene_id)
            .join(Chapter, Chapter.id == Scene.chapter_id)
            .where(
                SceneCharacter.project_id == project_id,
                SceneCharacter.character_id == character_id,
            )
            .order_by(
                Scene.timeline_order,
                Chapter.position,
                Scene.position,
                Scene.id,
            )
        ).all()
        return CharacterTimeline(
            items=tuple(
                CharacterAppearance(
                    scene_id=scene.id,
                    scene_title=scene.title,
                    chapter_id=chapter.id,
                    chapter_title=chapter.title,
                    chapter_position=chapter.position,
                    scene_position=scene.position,
                    timeline_order=scene.timeline_order,
                    role_in_scene=link.role_in_scene,
                    notes=link.notes,
                )
                for link, scene, chapter in rows
            )
        )
