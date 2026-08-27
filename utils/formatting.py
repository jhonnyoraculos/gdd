"""Presentation-only formatting helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from utils.constants import PROJECT_STATUSES

_STATUS_LABELS = {option.value: option.label for option in PROJECT_STATUSES}


def project_status_label(value: str) -> str:
    return _STATUS_LABELS.get(value, value.replace("_", " ").title())


def relative_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    seconds = max(0, int((datetime.now(UTC) - value).total_seconds()))
    if seconds < 60:
        return "agora"
    minutes = seconds // 60
    if minutes < 60:
        return f"há {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"há {hours} h"
    days = hours // 24
    if days == 1:
        return "ontem"
    if days < 30:
        return f"há {days} dias"
    return value.astimezone().strftime("%d/%m/%Y")
