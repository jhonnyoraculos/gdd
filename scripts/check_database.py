"""Check Neon connectivity and migration state without exposing credentials."""

from __future__ import annotations

from config.settings import ConfigurationError, get_settings
from services.database import check_database_health


def main() -> int:
    try:
        health = check_database_health(get_settings())
    except ConfigurationError as exc:
        print(f"Configuração inválida: {exc}")
        return 1

    print(f"Banco: {health.database_label}")
    print(health.public_message)
    if health.incident_id:
        print(f"ID do incidente: {health.incident_id}")
    return 0 if health.is_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
