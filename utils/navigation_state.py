"""Small navigation registry shared by interactive page components."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st

_PAGES_KEY = "_gdd_navigation_pages"


def register_navigation_pages(pages: Mapping[str, Any]) -> None:
    st.session_state[_PAGES_KEY] = dict(pages)


def go_to_page(key: str, **query_params: str) -> None:
    page = st.session_state.get(_PAGES_KEY, {}).get(key)
    if page is None:
        raise RuntimeError(f"Navigation target is not registered: {key}")
    st.switch_page(page, query_params=query_params or None)
