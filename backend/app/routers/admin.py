from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_super_admin
from app.models import AuditLog, User
from app.schemas import AdminUserOut, AuditOut, RoleIn

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        display_name_set=user.display_name_set_at is not None,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(q: str = "", _: User = Depends(get_super_admin), db: Session = Depends(get_db)):
    query = select(User).order_by(User.id.desc()).limit(50)
    term = q.strip().casefold()
    if term:
        like = f"%{term}%"
        query = query.where(or_(func.lower(User.email).like(like), func.lower(User.display_name).like(like)))
    return [_user_out(user) for user in db.scalars(query).all()]


@router.post("/users/{user_id}/role", response_model=AdminUserOut)
def set_role(user_id: int, body: RoleIn, actor: User = Depends(get_super_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role == "super_admin":
        raise HTTPException(status_code=400, detail="Super admin access is managed from the command line.")
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role here.")
    user.role = body.role
    db.commit()
    return _user_out(user)


@router.get("/audit", response_model=list[AuditOut])
def audit(week_id: int | None = None, _: User = Depends(get_super_admin), db: Session = Depends(get_db)):
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(100)
    if week_id is not None:
        query = query.where(AuditLog.week_id == week_id)
    rows = db.scalars(query).all()
    actors = {user.id: user for user in db.scalars(select(User).where(User.id.in_({row.actor_id for row in rows}))).all()} if rows else {}
    return [
        AuditOut(
            id=row.id,
            actor_id=row.actor_id,
            actor_name=actors[row.actor_id].display_name if row.actor_id in actors else "Admin",
            action=row.action,
            week_id=row.week_id,
            payload=row.payload,
            created_at=row.created_at,
        )
        for row in rows
    ]
