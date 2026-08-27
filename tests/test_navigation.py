"""Navigation registry invariants."""

from components.navigation import PAGE_SPECS


def test_navigation_has_one_default_and_unique_routes() -> None:
    assert sum(spec.default for spec in PAGE_SPECS) == 1
    assert len({spec.key for spec in PAGE_SPECS}) == len(PAGE_SPECS)
    assert len({spec.url_path for spec in PAGE_SPECS}) == len(PAGE_SPECS)


def test_database_free_routes_are_explicit() -> None:
    database_free = {spec.key for spec in PAGE_SPECS if not spec.requires_database}
    assert database_free == {"home", "settings"}
