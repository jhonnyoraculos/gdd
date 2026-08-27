"""Archived project library."""

from components.project_collection import ARCHIVED_COLLECTION, render_project_collection


def render() -> None:
    render_project_collection(ARCHIVED_COLLECTION)
