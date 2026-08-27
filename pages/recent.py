"""Recently edited active projects."""

from components.project_collection import RECENT_COLLECTION, render_project_collection


def render() -> None:
    render_project_collection(RECENT_COLLECTION)
