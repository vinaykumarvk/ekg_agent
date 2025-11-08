"""Security helpers for the admin experience."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True when the plain password matches the stored hash."""

    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:
        # Raised if the hash format is invalid
        return False


def hash_password(plain_password: str) -> str:
    """Helper for generating bcrypt hashes (used in documentation/tests)."""

    if not plain_password:
        raise ValueError("Password cannot be empty")
    return pwd_context.hash(plain_password)


def generate_session_identifier() -> str:
    """Generate a cryptographically secure session identifier."""

    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    """Return a CSRF token for embedding into forms."""

    return secrets.token_urlsafe(32)


def token_is_fresh(created_at: datetime, max_age_seconds: int = 3600) -> bool:
    """Simple helper to determine if a token is still fresh."""

    return datetime.utcnow() - created_at <= timedelta(seconds=max_age_seconds)
