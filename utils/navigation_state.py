"""Query-parameter navigation that always stays on the root app route."""

from __future__ import annotations

from typing import Any

import streamlit as st

_ROOT_PAGE_KEY = "_gdd_root_page"


def set_root_page(page: Any) -> None:
    st.session_state[_ROOT_PAGE_KEY] = page


def go_to_page(key: str, **query_params: str) -> None:
    root_page = st.session_state.get(_ROOT_PAGE_KEY)
    if root_page is None:
        st.query_params.clear()
        st.query_params.update({"view": key, **query_params})
        st.rerun(scope="app")
    st.switch_page(root_page, query_params={"view": key, **query_params})
