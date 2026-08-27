"""Design-system structure and accessibility safeguards."""

from styles.loader import STYLESHEETS, stylesheets_for_theme


def test_all_stylesheets_exist_and_are_nonempty() -> None:
    assert all(path.is_file() and path.stat().st_size > 0 for path in STYLESHEETS)


def test_responsive_and_reduced_motion_rules_are_present() -> None:
    css = "\n".join(path.read_text(encoding="utf-8") for path in STYLESHEETS)
    assert "@media (max-width: 640px)" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "min-height: 44px" in css


def test_glass_has_a_non_blur_fallback() -> None:
    glass_css = next(path for path in STYLESHEETS if path.name == "liquid_glass.css")
    content = glass_css.read_text(encoding="utf-8")
    fallback_position = content.index("background: var(--gdd-glass-strong)")
    enhancement_position = content.index("@supports")
    assert fallback_position < enhancement_position


def test_theme_loader_selects_exactly_one_palette() -> None:
    dark_files = stylesheets_for_theme("dark")
    light_files = stylesheets_for_theme("light")

    assert any(path.name == "theme_dark.css" for path in dark_files)
    assert not any(path.name == "theme_light.css" for path in dark_files)
    assert any(path.name == "theme_light.css" for path in light_files)
    assert not any(path.name == "theme_dark.css" for path in light_files)
