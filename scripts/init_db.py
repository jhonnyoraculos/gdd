"""Apply all database migrations."""

from __future__ import annotations

from config.settings import ConfigurationError, get_settings
from services.database import DatabaseNotConfiguredError, upgrade_database


def main() -> int:
    try:
        settings = get_settings()
        upgrade_database(settings)
    except (ConfigurationError, DatabaseNotConfiguredError) as exc:
        print(f"Configuração inválida: {exc}")
        return 1
    except Exception as exc:  # The CLI may expose the type, never the connection URL.
        print(f"Não foi possível atualizar o banco ({type(exc).__name__}).")
        return 1

    print("Banco atualizado com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
