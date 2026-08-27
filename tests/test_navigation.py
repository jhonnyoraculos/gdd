"""Navigation registry invariants."""

import pytest

import utils.navigation_state as navigation_state
from components.navigation import PAGE_SPECS


def test_navigation_has_one_default_and_unique_routes() -> None:
    assert sum(spec.default for spec in PAGE_SPECS) == 1
    assert len({spec.key for spec in PAGE_SPECS}) == len(PAGE_SPECS)
    assert len({spec.url_path for spec in PAGE_SPECS}) == len(PAGE_SPECS)


def test_database_free_routes_are_explicit() -> None:
    database_free = {spec.key for spec in PAGE_SPECS if not spec.requires_database}
    assert database_free == {"home", "settings"}


def test_root_page_survives_fragment_reruns(monkeypatch: pytest.MonkeyPatch) -> None:
    session_state: dict[str, object] = {}
    calls: list[tuple[object, dict[str, str]]] = []
    root_page = object()

    monkeypatch.setattr(navigation_state.st, "session_state", session_state)
    monkeypatch.setattr(
        navigation_state.st,
        "switch_page",
        lambda page, *, query_params: calls.append((page, query_params)),
    )

    navigation_state.set_root_page(root_page)
    navigation_state.go_to_page("character_detail", project="project-id", id="character-id")

    assert calls == [
        (
            root_page,
            {
                "view": "character_detail",
                "project": "project-id",
                "id": "character-id",
            },
        )
    ]
