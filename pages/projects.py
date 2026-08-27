"""Active project library."""

from components.project_collection import PROJECTS_COLLECTION, render_project_collection


def render() -> None:
    render_project_collection(PROJECTS_COLLECTION)
