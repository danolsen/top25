from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_ready_user
from app.models import User
from app.schemas import DisplayNameIn, ProfileIn, UserOut
from app.security import hash_password, verify_password
from app.services.accounts import confirm_display_name, user_out

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/me/display-name", response_model=UserOut)
def set_display_name(body: DisplayNameIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    confirm_display_name(db, user, body.display_name)
    db.commit()
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_profile(body: ProfileIn, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    if body.display_name:
        confirm_display_name(db, user, body.display_name)
    if body.theme:
        user.theme = body.theme
    if body.new_password:
        if user.password_hash:
            if not body.current_password or not verify_password(body.current_password, user.password_hash):
                raise HTTPException(status_code=400, detail="Current password is incorrect.")
        user.password_hash = hash_password(body.new_password)
    db.commit()
    return user_out(user)
