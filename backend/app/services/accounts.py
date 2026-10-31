from datetime import timedelta
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.emailer import send_email
from app.models import MagicLink, PasswordReset, User, utcnow
from app.models import Session as DbSession
from app.schemas import UserOut
from app.security import (
    hash_password,
    hash_token,
    new_csrf,
    new_token,
    safe_eq,
    session_expiry,
    suggest_display_name,
)


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        display_name_set=user.display_name_set_at is not None,
        theme=user.theme,
        has_password=user.password_hash is not None,
        google_connected=user.google_sub is not None,
    )


def _name_taken(db: Session, key: str, ignore_id: int | None = None) -> bool:
    query = select(User.id).where(User.display_name_key == key)
    if ignore_id is not None:
        query = query.where(User.id != ignore_id)
    return db.scalar(query) is not None


def reserve_display_name(db: Session, preferred: str | None) -> tuple[str, str]:
    if preferred:
        key = preferred.casefold()
        if _name_taken(db, key):
            raise HTTPException(status_code=409, detail="That display name is taken")
        return preferred, key
    for _ in range(25):
        suggestion = suggest_display_name()
        key = suggestion.casefold()
        if not _name_taken(db, key):
            return suggestion, key
    raise HTTPException(status_code=500, detail="Could not suggest a display name")


def create_user(
    db: Session,
    email: str,
    *,
    password: str | None = None,
    google_sub: str | None = None,
    display_name: str | None = None,
) -> User:
    name, key = reserve_display_name(db, display_name)
    user = User(
        email=email.casefold(),
        password_hash=hash_password(password) if password else None,
        google_sub=google_sub,
        display_name=name,
        display_name_key=key,
        role="user",
    )
    db.add(user)
    db.flush()
    return user


def confirm_display_name(db: Session, user: User, display_name: str) -> None:
    key = display_name.casefold()
    if _name_taken(db, key, ignore_id=user.id):
        raise HTTPException(status_code=409, detail="That display name is taken")
    user.display_name = display_name
    user.display_name_key = key
    user.display_name_set_at = utcnow()


def start_session(db: Session, user: User) -> tuple[str, str]:
    token = new_token()
    csrf = new_csrf()
    db.add(
        DbSession(
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token=csrf,
            expires_at=session_expiry(),
        )
    )
    db.flush()
    return token, csrf


def csrf_ok(db: Session, raw_token: str | None, csrf_value: str | None) -> bool:
    if not raw_token or not csrf_value:
        return False
    row = db.scalar(select(DbSession).where(DbSession.token_hash == hash_token(raw_token)))
    if row is None:
        return False
    return safe_eq(row.csrf_token, csrf_value)


def session_for_token(db: Session, token: str | None) -> DbSession | None:
    if not token:
        return None
    row = db.scalar(select(DbSession).where(DbSession.token_hash == hash_token(token)))
    if row is None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        from datetime import UTC

        expires = expires.replace(tzinfo=UTC)
    if expires < utcnow():
        return None
    remaining = expires - utcnow()
    if remaining < timedelta(days=15):
        row.expires_at = session_expiry()
    return row


def issue_magic_link(db: Session, email: str) -> None:
    address = email.casefold()
    token = new_token()
    db.query(MagicLink).filter(MagicLink.email == address, MagicLink.used_at.is_(None)).delete()
    db.add(
        MagicLink(
            email=address,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(minutes=15),
        )
    )
    link = f"{get_settings().frontend_url}/magic?token={quote(token)}"
    send_email(
        address,
        "Your Top 25 sign-in link",
        "Use this link to sign in to Top 25. It expires in 15 minutes.\n\n"
        f"{link}\n\nIf you did not ask for this, you can ignore the email.",
    )


def consume_magic_link(db: Session, token: str) -> User:
    row = db.scalar(select(MagicLink).where(MagicLink.token_hash == hash_token(token)))
    if row is None or row.used_at is not None:
        raise HTTPException(status_code=400, detail="This sign-in link is invalid.")
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=utcnow().tzinfo)
    if expires < utcnow():
        raise HTTPException(status_code=400, detail="This sign-in link has expired.")
    row.used_at = utcnow()
    user = db.scalar(select(User).where(User.email == row.email))
    if user is None:
        user = create_user(db, row.email)
    return user


def issue_password_reset(db: Session, email: str) -> None:
    address = email.casefold()
    user = db.scalar(select(User).where(User.email == address))
    if user is None:
        return
    token = new_token()
    db.query(PasswordReset).filter(PasswordReset.email == address, PasswordReset.used_at.is_(None)).delete()
    db.add(
        PasswordReset(
            email=address,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(minutes=15),
        )
    )
    link = f"{get_settings().frontend_url}/reset?token={quote(token)}"
    send_email(
        address,
        "Reset your Top 25 password",
        "Use this link to set a new password. It expires in 15 minutes.\n\n"
        f"{link}\n\nIf you did not ask for this, you can ignore the email.",
    )


def consume_password_reset(db: Session, token: str, password: str) -> User:
    row = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_token(token)))
    if row is None or row.used_at is not None:
        raise HTTPException(status_code=400, detail="This reset link is invalid.")
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=utcnow().tzinfo)
    if expires < utcnow():
        raise HTTPException(status_code=400, detail="This reset link has expired.")
    user = db.scalar(select(User).where(User.email == row.email))
    if user is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid.")
    row.used_at = utcnow()
    user.password_hash = hash_password(password)
    return user


def user_from_google(db: Session, subject: str, email: str) -> User:
    address = email.casefold()
    by_subject = db.scalar(select(User).where(User.google_sub == subject))
    if by_subject:
        return by_subject
    by_email = db.scalar(select(User).where(User.email == address))
    if by_email:
        if by_email.google_sub and by_email.google_sub != subject:
            raise HTTPException(status_code=400, detail="This email is already linked to another Google account.")
        by_email.google_sub = subject
        return by_email
    return create_user(db, address, google_sub=subject)


def link_google(db: Session, user: User, subject: str) -> None:
    taken = db.scalar(select(User).where(User.google_sub == subject, User.id != user.id))
    if taken:
        raise HTTPException(status_code=400, detail="That Google account is already in use.")
    user.google_sub = subject
