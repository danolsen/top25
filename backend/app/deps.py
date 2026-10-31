from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Week
from app.services.accounts import session_for_token
from app.services.game import refresh_week


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    row = session_for_token(db, request.cookies.get("session"))
    if row is None:
        return None
    db.commit()
    return db.get(User, row.user_id)


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return user


def get_ready_user(user: User = Depends(get_current_user)) -> User:
    if user.display_name_set_at is None:
        raise HTTPException(status_code=403, detail="Confirm a display name before continuing.")
    return user


def get_admin(user: User = Depends(get_ready_user)) -> User:
    if user.role not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return user


def get_super_admin(user: User = Depends(get_ready_user)) -> User:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access is required.")
    return user


def get_week(week_id: int, db: Session = Depends(get_db)) -> Week:
    week = db.get(Week, week_id)
    if week is None:
        raise HTTPException(status_code=404, detail="Week not found.")
    if refresh_week(week):
        db.commit()
    return week
