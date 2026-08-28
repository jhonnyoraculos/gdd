"""Project-scoped @mention resolution and automatic content links."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from models import (
    Chapter,
    Character,
    ContentLink,
    GddSection,
    Project,
    Scene,
    SceneCharacter,
)
from services.database import session_scope
from services.user_service import OwnerIdentity, get_or_create_owner

_MENTION_PATTERN = re.compile(
    r"(?<!\w)@(?:(personagem|cena|capitulo|secao):)?([\w-]+)",
    re.IGNORECASE,
)


class ContentEntityType(StrEnum):
    CHARACTER = "character"
    SCENE = "scene"
    CHAPTER = "chapter"
    SECTION = "section"


class ContentSourceType(StrEnum):
    SECTION = "section"
    SCENE = "scene"


_PREFIXES = {
    ContentEntityType.CHARACTER: "personagem",
    ContentEntityType.SCENE: "cena",
    ContentEntityType.CHAPTER: "capitulo",
    ContentEntityType.SECTION: "secao",
}
_TYPE_LABELS = {
    ContentEntityType.CHARACTER: "Personagem",
    ContentEntityType.SCENE: "Cena",
    ContentEntityType.CHAPTER: "Capítulo",
    ContentEntityType.SECTION: "Seção do GDD",
}


class MentionServiceError(RuntimeError):
    """Safe error for mention flows."""


@dataclass(frozen=True, slots=True)
class MentionTarget:
    id: UUID
    entity_type: ContentEntityType
    label: str
    token: str

    @property
    def type_label(self) -> str:
        return _TYPE_LABELS[self.entity_type]


@dataclass(frozen=True, slots=True)
class ContentConnection:
    source_type: ContentSourceType
    source_id: UUID
    target_type: ContentEntityType
    target_id: UUID
    target_label: str
    mention_token: str

    @property
    def type_label(self) -> str:
        return _TYPE_LABELS[self.target_type]


@dataclass(frozen=True, slots=True)
class MentionContext:
    targets: tuple[MentionTarget, ...]
    connections: tuple[ContentConnection, ...]


@dataclass(frozen=True, slots=True)
class _TargetRecord:
    id: UUID
    entity_type: ContentEntityType
    label: str
    aliases: tuple[str, ...]


def mention_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if character.isalnum())


def _owned_project(session: Session, owner: OwnerIdentity, project_id: UUID) -> Project:
    user = get_or_create_owner(session, owner)
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        raise MentionServiceError("Projeto não encontrado.")
    return project


def _target_records(session: Session, project_id: UUID) -> tuple[_TargetRecord, ...]:
    characters = session.scalars(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.name, Character.id)
    ).all()
    scenes = session.scalars(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.title, Scene.id)
    ).all()
    chapters = session.scalars(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.position, Chapter.id)
    ).all()
    sections = session.scalars(
        select(GddSection)
        .where(GddSection.project_id == project_id)
        .order_by(GddSection.position, GddSection.id)
    ).all()

    records: list[_TargetRecord] = []
    for character in characters:
        aliases = tuple(
            dict.fromkeys(
                key
                for value in (character.name, character.nickname, character.codename)
                if value and (key := mention_key(value))
            )
        )
        records.append(
            _TargetRecord(
                character.id,
                ContentEntityType.CHARACTER,
                character.name,
                aliases,
            )
        )
    records.extend(
        _TargetRecord(item.id, entity_type, item.title, (mention_key(item.title),))
        for entity_type, items in (
            (ContentEntityType.SCENE, scenes),
            (ContentEntityType.CHAPTER, chapters),
            (ContentEntityType.SECTION, sections),
        )
        for item in items
        if mention_key(item.title)
    )
    return tuple(records)


def _resolution_maps(
    records: tuple[_TargetRecord, ...],
) -> tuple[
    dict[str, list[_TargetRecord]],
    dict[tuple[str, str], list[_TargetRecord]],
]:
    plain: defaultdict[str, list[_TargetRecord]] = defaultdict(list)
    qualified: defaultdict[tuple[str, str], list[_TargetRecord]] = defaultdict(list)
    for record in records:
        prefix = _PREFIXES[record.entity_type]
        for alias in record.aliases:
            plain[alias].append(record)
            qualified[(prefix, alias)].append(record)
            qualified[(prefix, f"{alias}-{record.id.hex[:8]}")].append(record)
    return dict(plain), dict(qualified)


def _resolved_mentions(
    records: tuple[_TargetRecord, ...], content: str
) -> tuple[tuple[_TargetRecord, str], ...]:
    plain, qualified = _resolution_maps(records)
    resolved: dict[tuple[ContentEntityType, UUID], tuple[_TargetRecord, str]] = {}
    for match in _MENTION_PATTERN.finditer(content):
        prefix = match.group(1).casefold() if match.group(1) else None
        raw_key = match.group(2)
        if prefix is None:
            candidates = plain.get(mention_key(raw_key), [])
        else:
            candidates = qualified.get((prefix, raw_key.casefold()), [])
            if not candidates:
                candidates = qualified.get((prefix, mention_key(raw_key)), [])
        unique = {(item.entity_type, item.id): item for item in candidates}
        if len(unique) != 1:
            continue
        record = next(iter(unique.values()))
        resolved[(record.entity_type, record.id)] = (record, match.group(0))
    return tuple(resolved.values())


def _source_filter(source_type: ContentSourceType, source_id: UUID):
    if source_type is ContentSourceType.SECTION:
        return ContentLink.source_section_id == source_id
    return ContentLink.source_scene_id == source_id


def _link_values(target: _TargetRecord) -> dict[str, UUID]:
    field = {
        ContentEntityType.CHARACTER: "target_character_id",
        ContentEntityType.SCENE: "target_scene_id",
        ContentEntityType.CHAPTER: "target_chapter_id",
        ContentEntityType.SECTION: "target_section_id",
    }[target.entity_type]
    return {field: target.id}


def sync_content_links(
    session: Session,
    project_id: UUID,
    source_type: ContentSourceType,
    source_id: UUID,
    content: str,
) -> None:
    """Replace automatic links for one source inside its existing transaction."""

    records = _target_records(session, project_id)
    mentions = list(_resolved_mentions(records, content))
    mentions = [
        (target, token)
        for target, token in mentions
        if not (
            target.id == source_id
            and (
                (
                    source_type is ContentSourceType.SECTION
                    and target.entity_type is ContentEntityType.SECTION
                )
                or (
                    source_type is ContentSourceType.SCENE
                    and target.entity_type is ContentEntityType.SCENE
                )
            )
        )
    ]
    session.execute(
        delete(ContentLink).where(
            ContentLink.project_id == project_id,
            _source_filter(source_type, source_id),
        )
    )
    source_values = (
        {"source_section_id": source_id}
        if source_type is ContentSourceType.SECTION
        else {"source_scene_id": source_id}
    )
    for target, token in mentions:
        session.add(
            ContentLink(
                project_id=project_id,
                mention_token=token,
                **source_values,
                **_link_values(target),
            )
        )

    if source_type is ContentSourceType.SCENE:
        mentioned_characters = {
            target.id
            for target, _token in mentions
            if target.entity_type is ContentEntityType.CHARACTER
        }
        appearance_links = session.scalars(
            select(SceneCharacter).where(
                SceneCharacter.project_id == project_id,
                SceneCharacter.scene_id == source_id,
            )
        ).all()
        current_ids = {link.character_id for link in appearance_links}
        generated_to_remove = [
            link
            for link in appearance_links
            if link.mention_generated and link.character_id not in mentioned_characters
        ]
        for link in generated_to_remove:
            session.delete(link)
        for character_id in mentioned_characters - current_ids:
            session.add(
                SceneCharacter(
                    project_id=project_id,
                    scene_id=source_id,
                    character_id=character_id,
                    mention_generated=True,
                )
            )


def list_mention_targets(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> tuple[MentionTarget, ...]:
    with session_scope(engine) as session:
        _owned_project(session, owner, project_id)
        records = _target_records(session, project_id)
        return _mention_targets(records)


def _mention_targets(records: tuple[_TargetRecord, ...]) -> tuple[MentionTarget, ...]:
    plain, qualified = _resolution_maps(records)
    targets: list[MentionTarget] = []
    for record in records:
        base = record.aliases[0]
        if len({(item.entity_type, item.id) for item in plain.get(base, [])}) == 1:
            token = f"@{base}"
        else:
            prefix = _PREFIXES[record.entity_type]
            same_type = qualified.get((prefix, base), [])
            suffix = f"-{record.id.hex[:8]}" if len(same_type) > 1 else ""
            token = f"@{prefix}:{base}{suffix}"
        targets.append(MentionTarget(record.id, record.entity_type, record.label, token))
    return tuple(sorted(targets, key=lambda item: (item.entity_type.value, item.label.casefold())))


def _connections(
    links: list[ContentLink], records: tuple[_TargetRecord, ...]
) -> tuple[ContentConnection, ...]:
    labels = {(item.entity_type, item.id): item.label for item in records}
    output: list[ContentConnection] = []
    for link in links:
        source_type = (
            ContentSourceType.SECTION
            if link.source_section_id is not None
            else ContentSourceType.SCENE
        )
        source_id = link.source_section_id or link.source_scene_id
        target_fields = (
            (ContentEntityType.CHARACTER, link.target_character_id),
            (ContentEntityType.SCENE, link.target_scene_id),
            (ContentEntityType.CHAPTER, link.target_chapter_id),
            (ContentEntityType.SECTION, link.target_section_id),
        )
        target_type, target_id = next(
            (entity_type, entity_id)
            for entity_type, entity_id in target_fields
            if entity_id is not None
        )
        label = labels.get((target_type, target_id))
        if source_id is None or label is None:
            continue
        output.append(
            ContentConnection(
                source_type,
                source_id,
                target_type,
                target_id,
                label,
                link.mention_token,
            )
        )
    return tuple(output)


def list_project_connections(
    owner: OwnerIdentity,
    project_id: UUID,
    engine: Engine | None = None,
) -> tuple[ContentConnection, ...]:
    with session_scope(engine) as session:
        _owned_project(session, owner, project_id)
        links = session.scalars(
            select(ContentLink)
            .where(ContentLink.project_id == project_id)
            .order_by(ContentLink.created_at, ContentLink.id)
        ).all()
        records = _target_records(session, project_id)
        return _connections(links, records)


def get_mention_context(
    owner: OwnerIdentity,
    project_id: UUID,
    source_type: ContentSourceType,
    source_id: UUID,
    engine: Engine | None = None,
) -> MentionContext:
    with session_scope(engine) as session:
        _owned_project(session, owner, project_id)
        records = _target_records(session, project_id)
        links = session.scalars(
            select(ContentLink)
            .where(
                ContentLink.project_id == project_id,
                _source_filter(source_type, source_id),
            )
            .order_by(ContentLink.created_at, ContentLink.id)
        ).all()
        return MentionContext(_mention_targets(records), _connections(links, records))


def list_source_connections(
    owner: OwnerIdentity,
    project_id: UUID,
    source_type: ContentSourceType,
    source_id: UUID,
    engine: Engine | None = None,
) -> tuple[ContentConnection, ...]:
    return tuple(
        item
        for item in list_project_connections(owner, project_id, engine)
        if item.source_type is source_type and item.source_id == source_id
    )
