"""Flash messages that survive Streamlit page switches."""

from __future__ import annotations

import streamlit as st

_FLASH_KEY = "_gdd_flash_message"


def set_flash(message: str, icon: str = "✅") -> None:
    st.session_state[_FLASH_KEY] = (message, icon)


def render_flash() -> None:
    payload = st.session_state.pop(_FLASH_KEY, None)
    if payload:
        message, icon = payload
        st.toast(message, icon=icon)
