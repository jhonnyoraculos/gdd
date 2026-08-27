"""Favorite projects."""

from components.project_collection import FAVORITES_COLLECTION, render_project_collection


def render() -> None:
    render_project_collection(FAVORITES_COLLECTION)
