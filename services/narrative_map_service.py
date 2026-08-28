"""Read-only narrative graph assembled from relational project data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum
from urllib.parse import urlencode
from uuid import UUID

from sqlalchemy import Engine, or_, select
from sqlalchemy.orm import undefer

from models import (
    Chapter,
    Character,
    CharacterRelationship,
    ContentLink,
    GddSection,
    NarrativeMapLink,
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
    SECTION = "section"


class MapEdgeType(StrEnum):
    HIERARCHY = "hierarchy"
    APPEARANCE = "appearance"
    RELATIONSHIP = "relationship"
    MENTION = "mention"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class MapMetric:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class MapConnectionCard:
    edge_key: str
    node_key: str
    label: str
    subtitle: str
    removable: bool


@dataclass(frozen=True, slots=True)
class NarrativeMapNode:
    key: str
    entity_id: UUID
    node_type: MapNodeType
    label: str
    subtitle: str | None
    description: str | None
    href: str
    content: str | None = None
    metrics: tuple[MapMetric, ...] = ()
    items_title: str | None = None
    items: tuple[str, ...] = ()
    connections: tuple[MapConnectionCard, ...] = ()


@dataclass(frozen=True, slots=True)
class NarrativeMapEdge:
    key: str
    source: str
    target: str
    edge_type: MapEdgeType
    label: str | None = None
    directed: bool = False
    removable: bool = False


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
        content_links = session.scalars(
            select(ContentLink)
            .where(ContentLink.project_id == project_id)
            .order_by(ContentLink.created_at, ContentLink.id)
        ).all()
        manual_links = session.scalars(
            select(NarrativeMapLink)
            .where(NarrativeMapLink.project_id == project_id)
            .order_by(NarrativeMapLink.created_at, NarrativeMapLink.id)
        ).all()
        linked_section_ids = {
            section_id
            for link in content_links
            for section_id in (link.source_section_id, link.target_section_id)
            if section_id is not None
        }
        linked_section_ids.update(
            section_id
            for link in manual_links
            for section_id in (link.source_section_id, link.target_section_id)
            if section_id is not None
        )
        sections = session.scalars(
            select(GddSection)
            .options(undefer(GddSection.content))
            .where(
                GddSection.project_id == project_id,
                or_(
                    GddSection.content != "",
                    GddSection.id.in_(linked_section_ids),
                ),
            )
            .order_by(GddSection.position, GddSection.id)
        ).all()

        scenes_by_chapter: defaultdict[UUID, list[Scene]] = defaultdict(list)
        for scene in scenes:
            scenes_by_chapter[scene.chapter_id].append(scene)
        chapter_by_id = {chapter.id: chapter for chapter in chapters}
        scene_by_id = {scene.id: scene for scene in scenes}
        character_by_id = {character.id: character for character in characters}
        section_by_id = {section.id: section for section in sections}

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
                content=project.description,
                metrics=(
                    MapMetric("Capítulos", str(len(chapters))),
                    MapMetric("Cenas", str(len(scenes))),
                    MapMetric("Personagens", str(len(characters))),
                    MapMetric("Conexões @", str(len(content_links))),
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
                    content=chapter.summary,
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
                    content=scene.content,
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
                    content="\n\n".join(
                        text
                        for text in (
                            character.summary,
                            character.story,
                            character.personality,
                            character.external_goal,
                            character.arc_ending,
                        )
                        if text
                    )
                    or None,
                    metrics=(
                        MapMetric("Aparições", str(len(character_scenes))),
                        MapMetric("Relações", str(relationship_count[character.id])),
                    ),
                    items_title="Cenas",
                    items=tuple(scene.title for scene in character_scenes),
                )
            )

        section_connections: defaultdict[UUID, list[str]] = defaultdict(list)
        for link in content_links:
            if link.source_section_id is None:
                continue
            target_label = None
            if link.target_character_id in character_by_id:
                target_label = character_by_id[link.target_character_id].name
            elif link.target_scene_id in scene_by_id:
                target_label = scene_by_id[link.target_scene_id].title
            elif link.target_chapter_id in chapter_by_id:
                target_label = chapter_by_id[link.target_chapter_id].title
            elif link.target_section_id in section_by_id:
                target_label = section_by_id[link.target_section_id].title
            if target_label:
                section_connections[link.source_section_id].append(target_label)

        for section in sections:
            connected_labels = section_connections[section.id]
            nodes.append(
                NarrativeMapNode(
                    key=_key(MapNodeType.SECTION, section.id),
                    entity_id=section.id,
                    node_type=MapNodeType.SECTION,
                    label=section.title,
                    subtitle="Seção do GDD",
                    description=(section.content[:500] if section.content else None),
                    href=_href(
                        "gdd_editor",
                        project=str(project_id),
                        section=str(section.id),
                    ),
                    content=section.content or None,
                    metrics=(MapMetric("Conexões", str(len(connected_labels))),),
                    items_title="Referências",
                    items=tuple(connected_labels),
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
                    removable=True,
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
                    removable=True,
                )
            )

        def mention_node(link: ContentLink, source: bool) -> str | None:
            if source:
                if link.source_section_id in section_by_id:
                    return _key(MapNodeType.SECTION, link.source_section_id)
                if link.source_scene_id in scene_by_id:
                    return _key(MapNodeType.SCENE, link.source_scene_id)
                return None
            if link.target_character_id in character_by_id:
                return _key(MapNodeType.CHARACTER, link.target_character_id)
            if link.target_scene_id in scene_by_id:
                return _key(MapNodeType.SCENE, link.target_scene_id)
            if link.target_chapter_id in chapter_by_id:
                return _key(MapNodeType.CHAPTER, link.target_chapter_id)
            if link.target_section_id in section_by_id:
                return _key(MapNodeType.SECTION, link.target_section_id)
            return None

        for link in content_links:
            source = mention_node(link, True)
            target = mention_node(link, False)
            if source is None or target is None:
                continue
            edges.append(
                NarrativeMapEdge(
                    key=f"mention:{link.id}",
                    source=source,
                    target=target,
                    edge_type=MapEdgeType.MENTION,
                    label=link.mention_token,
                    directed=True,
                )
            )

        def manual_node(link: NarrativeMapLink, source: bool) -> str | None:
            prefix = "source" if source else "target"
            for node_type in (
                MapNodeType.CHAPTER,
                MapNodeType.SCENE,
                MapNodeType.CHARACTER,
                MapNodeType.SECTION,
            ):
                entity_id = getattr(link, f"{prefix}_{node_type.value}_id")
                if entity_id is not None:
                    return _key(node_type, entity_id)
            return None

        for link in manual_links:
            source = manual_node(link, True)
            target = manual_node(link, False)
            if source is None or target is None:
                continue
            edges.append(
                NarrativeMapEdge(
                    key=f"manual:{link.id}",
                    source=source,
                    target=target,
                    edge_type=MapEdgeType.MANUAL,
                    label=link.label or "Ligação visual",
                    directed=link.directed,
                    removable=True,
                )
            )

        node_by_key = {node.key: node for node in nodes}
        connections: defaultdict[str, list[MapConnectionCard]] = defaultdict(list)
        edge_labels = {
            MapEdgeType.HIERARCHY: "Estrutura",
            MapEdgeType.APPEARANCE: "Participação",
            MapEdgeType.RELATIONSHIP: "Relação",
            MapEdgeType.MENTION: "@menção automática",
            MapEdgeType.MANUAL: "Ligação visual",
        }
        for edge in edges:
            if edge.source not in node_by_key or edge.target not in node_by_key:
                continue
            for current_key, neighbor_key in (
                (edge.source, edge.target),
                (edge.target, edge.source),
            ):
                direction = ""
                if edge.directed:
                    direction = "Saída" if current_key == edge.source else "Entrada"
                details = [edge_labels[edge.edge_type]]
                if direction:
                    details.append(direction)
                if edge.label:
                    details.append(edge.label)
                connections[current_key].append(
                    MapConnectionCard(
                        edge_key=edge.key,
                        node_key=neighbor_key,
                        label=node_by_key[neighbor_key].label,
                        subtitle=" · ".join(details),
                        removable=edge.removable,
                    )
                )
        nodes = [
            replace(
                node,
                connections=tuple(
                    sorted(
                        connections[node.key],
                        key=lambda item: (item.label.casefold(), item.edge_key),
                    )
                ),
            )
            for node in nodes
        ]

        return NarrativeMapGraph(
            project_id=project.id,
            project_name=project.name,
            accent_color=project.accent_color,
            nodes=tuple(nodes),
            edges=tuple(edges),
        )
