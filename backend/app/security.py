import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Response

from app.config import get_settings

_hasher = PasswordHasher()
JOIN_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ADJECTIVES = [
    "Swift", "Bold", "Calm", "Keen", "Bright", "Quiet", "Lucky", "Steady",
    "Nimble", "Amber", "Copper", "Silver", "Hidden", "Wild", "Clear",
]
NOUNS = [
    "Falcon", "Harbor", "Maple", "Lantern", "River", "Summit", "Badger",
    "Comet", "Prairie", "Anchor", "Cedar", "Piston", "Meadow", "Signal",
]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    pepper = get_settings().secret_pepper
    return hashlib.sha256(f"{pepper}:{token}".encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_csrf() -> str:
    return secrets.token_urlsafe(24)


def new_join_code() -> str:
    return "".join(secrets.choice(JOIN_ALPHABET) for _ in range(10))


def suggest_display_name() -> str:
    return f"{secrets.choice(ADJECTIVES)} {secrets.choice(NOUNS)} {secrets.randbelow(900) + 100}"


def safe_eq(left: str | None, right: str | None) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)


def session_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=get_settings().session_days)


def set_session_cookies(response: Response, token: str, csrf: str) -> None:
    settings = get_settings()
    max_age = settings.session_days * 24 * 60 * 60
    response.set_cookie(
        "session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        "csrf",
        csrf,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie("session", path="/")
    response.delete_cookie("csrf", path="/")
