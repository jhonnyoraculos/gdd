"""Owner-scoped chapters, scenes and narrative ordering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, selectinload

from models import Chapter, Project, Scene
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner

MAX_SUMMARY_LENGTH = 20_000
MAX_SCENE_CONTENT_LENGTH = 2_000_000


class NarrativeServiceError(RuntimeError):
    """Base error safe for narrative UI flows."""


class NarrativeNotFoundError(NarrativeServiceError):
    """Raised when a project, chapter or scene is outside the active scope."""


class NarrativeConflictError(NarrativeServiceError):
    """Raised when stale data would overwrite a newer revision."""


class NarrativeDirection(StrEnum):
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class ChapterInput:
    title: str
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class SceneInput:
    chapter_id: UUID
    title: str
    summary: str | None = None
    content: str | None = None


@dataclass(frozen=True, slots=True)
class SceneDetails:
    id: UUID
    project_id: UUID
    chapter_id: UUID
    title: str
    summary: str | None
    content: str | None
    position: int
    timeline_order: int
    revision: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChapterDetails:
    id: UUID
    project_id: UUID
    title: str
    summary: str | None
    position: int
    revision: int
    updated_at: datetime
    scenes: tuple[SceneDetails, ...]


def _clean_text(value: str | None, maximum: int, label: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise NarrativeServiceError(f"{label} excede o limite de {maximum} caracteres.")
    return cleaned


def _validate_chapter(data: ChapterInput) -> ChapterInput:
    title = data.title.strip()
    if not title or len(title) > 180:
        raise NarrativeServiceError("O título do capítulo deve ter entre 1 e 180 caracteres.")
    return ChapterInput(title, _clean_text(data.summary, MAX_SUMMARY_LENGTH, "O resumo"))


def _validate_scene(data: SceneInput) -> SceneInput:
    title = data.title.strip()
    if not title or len(title) > 180:
        raise NarrativeServiceError("O título da cena deve ter entre 1 e 180 caracteres.")
    return SceneInput(
        chapter_id=data.chapter_id,
        title=title,
        summary=_clean_text(data.summary, MAX_SUMMARY_LENGTH, "O resumo"),
        content=_clean_text(data.content, MAX_SCENE_CONTENT_LENGTH, "O conteúdo"),
    )


def _project(session: Session, owner: OwnerIdentity, project_id: UUID) -> Project:
    user = get_or_create_owner(session, owner)
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise NarrativeNotFoundError("Projeto não encontrado.")
    return project


def _chapter(session: Session, project_id: UUID, chapter_id: UUID) -> Chapter:
    chapter = session.scalar(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id)
    )
    if chapter is None:
        raise NarrativeNotFoundError("Capítulo não encontrado.")
    return chapter


def _scene(session: Session, project_id: UUID, scene_id: UUID) -> Scene:
    scene = session.scalar(
        select(Scene).where(Scene.id == scene_id, Scene.project_id == project_id)
    )
    if scene is None:
        raise NarrativeNotFoundError("Cena não encontrada.")
    return scene


def _scene_details(scene: Scene) -> SceneDetails:
    return SceneDetails(
        id=scene.id,
        project_id=scene.project_id,
        chapter_id=scene.chapter_id,
        title=scene.title,
        summary=scene.summary,
        content=scene.content,
        position=scene.position,
        timeline_order=scene.timeline_order,
        revision=scene.revision,
        updated_at=scene.updated_at,
    )


def _resequence_timeline(session: Session, project_id: UUID) -> None:
    scenes = session.scalars(
        select(Scene)
        .join(Chapter, Chapter.id == Scene.chapter_id)
        .where(Scene.project_id == project_id)
        .order_by(Chapter.position, Scene.position, Scene.id)
    ).all()
    for index, scene in enumerate(scenes, start=1):
        scene.timeline_order = index * 1000


def list_narrative(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> tuple[ChapterDetails, ...]:
    with session_scope(engine) as session:
        _project(session, owner, project_id)
        chapters = session.scalars(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .options(selectinload(Chapter.scenes))
            .order_by(Chapter.position, Chapter.id)
        ).all()
        return tuple(
            ChapterDetails(
                id=chapter.id,
                project_id=chapter.project_id,
                title=chapter.title,
                summary=chapter.summary,
                position=chapter.position,
                revision=chapter.revision,
                updated_at=chapter.updated_at,
                scenes=tuple(_scene_details(scene) for scene in chapter.scenes),
            )
            for chapter in chapters
        )


def create_chapter(
    owner: OwnerIdentity,
    project_id: UUID,
    data: ChapterInput,
    engine: Engine | None = None,
) -> UUID:
    validated = _validate_chapter(data)
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        max_position = (
            session.scalar(
                select(func.max(Chapter.position)).where(Chapter.project_id == project_id)
            )
            or 0
        )
        chapter = Chapter(
            project_id=project_id,
            title=validated.title,
            summary=validated.summary,
            position=max_position + 1000,
        )
        project.updated_at = datetime.now(UTC)
        session.add(chapter)
        session.flush()
        return chapter.id


def update_chapter(
    owner: OwnerIdentity,
    project_id: UUID,
    chapter_id: UUID,
    data: ChapterInput,
    *,
    expected_revision: int,
    engine: Engine | None = None,
) -> None:
    validated = _validate_chapter(data)
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        chapter = _chapter(session, project_id, chapter_id)
        if chapter.revision != expected_revision:
            raise NarrativeConflictError("O capítulo foi alterado. Recarregue antes de salvar.")
        chapter.title = validated.title
        chapter.summary = validated.summary
        project.updated_at = datetime.now(UTC)


def move_chapter(
    owner: OwnerIdentity,
    project_id: UUID,
    chapter_id: UUID,
    direction: NarrativeDirection,
    engine: Engine | None = None,
) -> bool:
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        chapter = _chapter(session, project_id, chapter_id)
        siblings = session.scalars(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.position, Chapter.id)
        ).all()
        index = next(i for i, item in enumerate(siblings) if item.id == chapter.id)
        target_index = index - 1 if direction is NarrativeDirection.UP else index + 1
        if target_index < 0 or target_index >= len(siblings):
            return False
        target = siblings[target_index]
        chapter.position, target.position = target.position, chapter.position
        session.flush()
        _resequence_timeline(session, project_id)
        project.updated_at = datetime.now(UTC)
        return True


def delete_chapter(
    owner: OwnerIdentity,
    project_id: UUID,
    chapter_id: UUID,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        chapter = _chapter(session, project_id, chapter_id)
        session.delete(chapter)
        session.flush()
        _resequence_timeline(session, project_id)
        project.updated_at = datetime.now(UTC)


def create_scene(
    owner: OwnerIdentity,
    project_id: UUID,
    data: SceneInput,
    engine: Engine | None = None,
) -> UUID:
    validated = _validate_scene(data)
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        _chapter(session, project_id, validated.chapter_id)
        max_position = (
            session.scalar(
                select(func.max(Scene.position)).where(Scene.chapter_id == validated.chapter_id)
            )
            or 0
        )
        scene = Scene(
            project_id=project_id,
            chapter_id=validated.chapter_id,
            title=validated.title,
            summary=validated.summary,
            content=validated.content,
            position=max_position + 1000,
            timeline_order=0,
        )
        session.add(scene)
        session.flush()
        _resequence_timeline(session, project_id)
        project.updated_at = datetime.now(UTC)
        return scene.id


def update_scene(
    owner: OwnerIdentity,
    project_id: UUID,
    scene_id: UUID,
    data: SceneInput,
    *,
    expected_revision: int,
    engine: Engine | None = None,
) -> None:
    validated = _validate_scene(data)
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        scene = _scene(session, project_id, scene_id)
        if scene.revision != expected_revision:
            raise NarrativeConflictError("A cena foi alterada. Recarregue antes de salvar.")
        _chapter(session, project_id, validated.chapter_id)
        if scene.chapter_id != validated.chapter_id:
            max_position = (
                session.scalar(
                    select(func.max(Scene.position)).where(Scene.chapter_id == validated.chapter_id)
                )
                or 0
            )
            scene.chapter_id = validated.chapter_id
            scene.position = max_position + 1000
        scene.title = validated.title
        scene.summary = validated.summary
        scene.content = validated.content
        session.flush()
        _resequence_timeline(session, project_id)
        project.updated_at = datetime.now(UTC)


def move_scene(
    owner: OwnerIdentity,
    project_id: UUID,
    scene_id: UUID,
    direction: NarrativeDirection,
    engine: Engine | None = None,
) -> bool:
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        scene = _scene(session, project_id, scene_id)
        siblings = session.scalars(
            select(Scene)
            .where(Scene.chapter_id == scene.chapter_id)
            .order_by(Scene.position, Scene.id)
        ).all()
        index = next(i for i, item in enumerate(siblings) if item.id == scene.id)
        target_index = index - 1 if direction is NarrativeDirection.UP else index + 1
        if target_index < 0 or target_index >= len(siblings):
            return False
        target = siblings[target_index]
        scene.position, target.position = target.position, scene.position
        session.flush()
        _resequence_timeline(session, project_id)
        project.updated_at = datetime.now(UTC)
        return True


def delete_scene(
    owner: OwnerIdentity,
    project_id: UUID,
    scene_id: UUID,
    engine: Engine | None = None,
) -> None:
    with session_scope(engine) as session:
        project = _project(session, owner, project_id)
        scene = _scene(session, project_id, scene_id)
        session.delete(scene)
        session.flush()
        _resequence_timeline(session, project_id)
        project.updated_at = datetime.now(UTC)
