"""ORM model registry.

Importing this package registers every table in :class:`models.base.Base`.
"""

from models.base import Base
from models.chapter import Chapter
from models.character import Character
from models.character_relationship import CharacterRelationship
from models.content_link import ContentLink
from models.gdd_image import GddSectionImage
from models.idea import Idea
from models.narrative_map_link import NarrativeMapLink
from models.note import Note
from models.project import Project
from models.reference import ProjectReference
from models.roadmap import RoadmapItem
from models.scene import Scene
from models.scene_character import SceneCharacter
from models.section import GddSection
from models.tag import Tag, idea_tags, note_tags, project_tags, reference_tags, section_tags
from models.user import User
from models.version import ProjectVersion

__all__ = [
    "Base",
    "Character",
    "CharacterRelationship",
    "Chapter",
    "ContentLink",
    "GddSection",
    "GddSectionImage",
    "Idea",
    "Note",
    "NarrativeMapLink",
    "Project",
    "ProjectReference",
    "ProjectVersion",
    "RoadmapItem",
    "Scene",
    "SceneCharacter",
    "Tag",
    "User",
    "idea_tags",
    "note_tags",
    "project_tags",
    "reference_tags",
    "section_tags",
]
