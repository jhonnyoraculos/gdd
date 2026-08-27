"""Current workspace owner resolution.

Authentication is intentionally outside the current stage. Until it exists,
every database operation is scoped to one stable owner configured by the
environment, keeping the service boundary ready for an authenticated user id.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import AppSettings
from models import User


@dataclass(frozen=True, slots=True)
class OwnerIdentity:
    name: str
    email: str

    @property
    def normalized_email(self) -> str:
        return self.email.strip().casefold()


def owner_from_settings(settings: AppSettings) -> OwnerIdentity:
    return OwnerIdentity(name=settings.owner_name, email=settings.owner_email)


def get_or_create_owner(session: Session, identity: OwnerIdentity) -> User:
    """Return the configured owner, creating it in the current transaction."""

    owner = session.scalar(select(User).where(User.email_normalized == identity.normalized_email))
    if owner is not None:
        if owner.name != identity.name or owner.email != identity.email:
            owner.name = identity.name
            owner.email = identity.email
        return owner

    owner = User(
        name=identity.name,
        email=identity.email,
        email_normalized=identity.normalized_email,
    )
    session.add(owner)
    session.flush()
    return owner
