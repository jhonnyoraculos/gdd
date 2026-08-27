"""Query-parameter navigation that always stays on the root app route."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import streamlit as st

_ROOT_PAGE: ContextVar[Any] = ContextVar("gdd_root_page")


def set_root_page(page: Any) -> None:
    _ROOT_PAGE.set(page)


def go_to_page(key: str, **query_params: str) -> None:
    st.switch_page(_ROOT_PAGE.get(), query_params={"view": key, **query_params})
