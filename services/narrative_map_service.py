"""Read-only narrative graph assembled from relational project data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import Engine, select

from models import (
    Chapter,
    Character,
    CharacterRelationship,
    Project,
    Scene,
    SceneCharacter,
)
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner


class NarrativeMapServiceError(RuntimeError):
    """Base error safe for map UI flows."""


class NarrativeMapNotFoundError(NarrativeMapServiceError):
    """Raised when the requested project is outside the owner scope."""


class MapNodeType(StrEnum):
    PROJECT = "project"
    CHAPTER = "chapter"
    SCENE = "scene"
    CHARACTER = "character"


class MapEdgeType(StrEnum):
    HIERARCHY = "hierarchy"
    APPEARANCE = "appearance"
    RELATIONSHIP = "relationship"


@dataclass(frozen=True, slots=True)
class MapMetric:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class NarrativeMapNode:
    key: str
    entity_id: UUID
    node_type: MapNodeType
    label: str
    subtitle: str | None
    description: str | None
    href: str
    metrics: tuple[MapMetric, ...] = ()
    items_title: str | None = None
    items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NarrativeMapEdge:
    key: str
    source: str
    target: str
    edge_type: MapEdgeType
    label: str | None = None
    directed: bool = False


@dataclass(frozen=True, slots=True)
class NarrativeMapGraph:
    project_id: UUID
    project_name: str
    accent_color: str
    nodes: tuple[NarrativeMapNode, ...]
    edges: tuple[NarrativeMapEdge, ...]

    def count(self, node_type: MapNodeType) -> int:
        return sum(node.node_type == node_type for node in self.nodes)


def _href(view: str, **params: str) -> str:
    return f"/?{urlencode({'view': view, **params})}"


def _key(node_type: MapNodeType, entity_id: UUID) -> str:
    return f"{node_type.value}:{entity_id}"


def get_narrative_map(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> NarrativeMapGraph:
    """Return one deterministic project-scoped graph without ORM objects."""

    with session_scope(engine) as session:
        user = get_or_create_owner(session, owner)
        project = session.scalar(
            select(Project).where(Project.id == project_id, Project.user_id == user.id)
        )
        if project is None:
            raise NarrativeMapNotFoundError("Projeto não encontrado.")

        chapters = session.scalars(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.position, Chapter.id)
        ).all()
        scenes = session.scalars(
            select(Scene)
            .where(Scene.project_id == project_id)
            .order_by(Scene.timeline_order, Scene.position, Scene.id)
        ).all()
        characters = session.scalars(
            select(Character)
            .where(Character.project_id == project_id)
            .order_by(Character.name, Character.id)
        ).all()
        appearances = session.scalars(
            select(SceneCharacter)
            .where(SceneCharacter.project_id == project_id)
            .order_by(SceneCharacter.scene_id, SceneCharacter.character_id)
        ).all()
        relationships = session.scalars(
            select(CharacterRelationship)
            .where(CharacterRelationship.project_id == project_id)
            .order_by(
                CharacterRelationship.source_character_id,
                CharacterRelationship.target_character_id,
                CharacterRelationship.id,
            )
        ).all()

        scenes_by_chapter: defaultdict[UUID, list[Scene]] = defaultdict(list)
        for scene in scenes:
            scenes_by_chapter[scene.chapter_id].append(scene)
        chapter_by_id = {chapter.id: chapter for chapter in chapters}
        scene_by_id = {scene.id: scene for scene in scenes}
        character_by_id = {character.id: character for character in characters}

        cast_by_scene: defaultdict[UUID, list[Character]] = defaultdict(list)
        scenes_by_character: defaultdict[UUID, list[Scene]] = defaultdict(list)
        for appearance in appearances:
            scene = scene_by_id.get(appearance.scene_id)
            character = character_by_id.get(appearance.character_id)
            if scene is None or character is None:
                continue
            cast_by_scene[scene.id].append(character)
            scenes_by_character[character.id].append(scene)

        relationship_count: defaultdict[UUID, int] = defaultdict(int)
        for relationship in relationships:
            relationship_count[relationship.source_character_id] += 1
            relationship_count[relationship.target_character_id] += 1

        nodes: list[NarrativeMapNode] = [
            NarrativeMapNode(
                key=_key(MapNodeType.PROJECT, project.id),
                entity_id=project.id,
                node_type=MapNodeType.PROJECT,
                label=project.name,
                subtitle=project.codename or project.genre or "Projeto",
                description=project.description,
                href=_href("project_detail", id=str(project.id)),
                metrics=(
                    MapMetric("Capítulos", str(len(chapters))),
                    MapMetric("Cenas", str(len(scenes))),
                    MapMetric("Personagens", str(len(characters))),
                ),
                items_title="Capítulos",
                items=tuple(chapter.title for chapter in chapters),
            )
        ]
        edges: list[NarrativeMapEdge] = []

        for chapter in chapters:
            chapter_scenes = scenes_by_chapter[chapter.id]
            nodes.append(
                NarrativeMapNode(
                    key=_key(MapNodeType.CHAPTER, chapter.id),
                    entity_id=chapter.id,
                    node_type=MapNodeType.CHAPTER,
                    label=chapter.title,
                    subtitle=f"{len(chapter_scenes)} cena{'s' if len(chapter_scenes) != 1 else ''}",
                    description=chapter.summary,
                    href=_href(
                        "narrative",
                        project=str(project_id),
                        chapter=str(chapter.id),
                    ),
                    metrics=(MapMetric("Cenas", str(len(chapter_scenes))),),
                    items_title="Cenas",
                    items=tuple(scene.title for scene in chapter_scenes),
                )
            )
            edges.append(
                NarrativeMapEdge(
                    key=f"project-chapter:{chapter.id}",
                    source=_key(MapNodeType.PROJECT, project.id),
                    target=_key(MapNodeType.CHAPTER, chapter.id),
                    edge_type=MapEdgeType.HIERARCHY,
                )
            )

        for scene in scenes:
            cast = sorted(cast_by_scene[scene.id], key=lambda item: (item.name, item.id))
            nodes.append(
                NarrativeMapNode(
                    key=_key(MapNodeType.SCENE, scene.id),
                    entity_id=scene.id,
                    node_type=MapNodeType.SCENE,
                    label=scene.title,
                    subtitle=(
                        chapter_by_id[scene.chapter_id].title
                        if scene.chapter_id in chapter_by_id
                        else "Cena"
                    ),
                    description=scene.summary,
                    href=_href(
                        "narrative",
                        project=str(project_id),
                        scene=str(scene.id),
                    ),
                    metrics=(
                        MapMetric("Ordem", str(max(1, scene.timeline_order // 1000))),
                        MapMetric("Personagens", str(len(cast))),
                    ),
                    items_title="Personagens",
                    items=tuple(character.name for character in cast),
                )
            )
            edges.append(
                NarrativeMapEdge(
                    key=f"chapter-scene:{scene.id}",
                    source=_key(MapNodeType.CHAPTER, scene.chapter_id),
                    target=_key(MapNodeType.SCENE, scene.id),
                    edge_type=MapEdgeType.HIERARCHY,
                )
            )

        for character in characters:
            character_scenes = sorted(
                scenes_by_character[character.id],
                key=lambda item: (item.timeline_order, item.position, item.id),
            )
            nodes.append(
                NarrativeMapNode(
                    key=_key(MapNodeType.CHARACTER, character.id),
                    entity_id=character.id,
                    node_type=MapNodeType.CHARACTER,
                    label=character.name,
                    subtitle=character.role or "Papel a definir",
                    description=character.short_description,
                    href=_href(
                        "character_detail",
                        project=str(project_id),
                        id=str(character.id),
                    ),
                    metrics=(
                        MapMetric("Aparições", str(len(character_scenes))),
                        MapMetric("Relações", str(relationship_count[character.id])),
                    ),
                    items_title="Cenas",
                    items=tuple(scene.title for scene in character_scenes),
                )
            )

        for appearance in appearances:
            if (
                appearance.scene_id not in scene_by_id
                or appearance.character_id not in character_by_id
            ):
                continue
            edges.append(
                NarrativeMapEdge(
                    key=f"appearance:{appearance.id}",
                    source=_key(MapNodeType.SCENE, appearance.scene_id),
                    target=_key(MapNodeType.CHARACTER, appearance.character_id),
                    edge_type=MapEdgeType.APPEARANCE,
                    label=appearance.role_in_scene,
                )
            )

        for relationship in relationships:
            if (
                relationship.source_character_id not in character_by_id
                or relationship.target_character_id not in character_by_id
            ):
                continue
            edges.append(
                NarrativeMapEdge(
                    key=f"relationship:{relationship.id}",
                    source=_key(MapNodeType.CHARACTER, relationship.source_character_id),
                    target=_key(MapNodeType.CHARACTER, relationship.target_character_id),
                    edge_type=MapEdgeType.RELATIONSHIP,
                    label=relationship.relationship_type,
                    directed=True,
                )
            )

        return NarrativeMapGraph(
            project_id=project.id,
            project_name=project.name,
            accent_color=project.accent_color,
            nodes=tuple(nodes),
            edges=tuple(edges),
        )
