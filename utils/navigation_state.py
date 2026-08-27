"""Query-parameter navigation that always stays on the root app route."""

from __future__ import annotations

import streamlit as st


def go_to_page(key: str, **query_params: str) -> None:
    st.query_params.clear()
    st.query_params.update({"view": key, **query_params})
    st.rerun()
