"""ORM model registry.

Importing this package registers every table in :class:`models.base.Base`.
"""

from models.base import Base
from models.character import Character
from models.idea import Idea
from models.note import Note
from models.project import Project
from models.reference import ProjectReference
from models.roadmap import RoadmapItem
from models.section import GddSection
from models.tag import Tag, idea_tags, note_tags, project_tags, reference_tags, section_tags
from models.user import User
from models.version import ProjectVersion

__all__ = [
    "Base",
    "Character",
    "GddSection",
    "Idea",
    "Note",
    "Project",
    "ProjectReference",
    "ProjectVersion",
    "RoadmapItem",
    "Tag",
    "User",
    "idea_tags",
    "note_tags",
    "project_tags",
    "reference_tags",
    "section_tags",
]
