from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.limits import client_ip, hit
from app.models import User
from app.schemas import EmailIn, LoginIn, MagicConsumeIn, RegisterIn, ResetIn, UserOut
from app.security import clear_session_cookies, new_token, set_session_cookies, verify_password
from app.services.accounts import (
    consume_magic_link,
    consume_password_reset,
    create_user,
    issue_magic_link,
    issue_password_reset,
    link_google,
    start_session,
    user_from_google,
    user_out,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_response(db: Session, user: User) -> JSONResponse:
    token, csrf = start_session(db, user)
    db.commit()
    response = JSONResponse(user_out(user).model_dump())
    set_session_cookies(response, token, csrf)
    return response


@router.post("/register", response_model=UserOut)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    hit(f"register:{client_ip(request)}", 10, 600)
    existing = db.scalar(select(User).where(User.email == body.email.casefold()))
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    try:
        user = create_user(db, str(body.email), password=body.password, display_name=body.display_name)
        return _auth_response(db, user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from exc


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    hit(f"login:{client_ip(request)}", 10, 600)
    user = db.scalar(select(User).where(User.email == body.email.casefold()))
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return _auth_response(db, user)


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    from app.models import Session as DbSession
    from app.security import hash_token

    token = request.cookies.get("session")
    if token:
        row = db.scalar(select(DbSession).where(DbSession.token_hash == hash_token(token)))
        if row:
            db.delete(row)
            db.commit()
    response = Response(status_code=204)
    clear_session_cookies(response)
    return response


@router.post("/magic-link")
def magic_link(body: EmailIn, request: Request, db: Session = Depends(get_db)):
    hit(f"magic:{body.email.casefold()}", 5, 900)
    try:
        issue_magic_link(db, str(body.email))
        db.commit()
    except OSError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Could not send email.") from exc
    return {"ok": True}


@router.post("/magic-link/consume", response_model=UserOut)
def magic_consume(body: MagicConsumeIn, db: Session = Depends(get_db)):
    user = consume_magic_link(db, body.token)
    return _auth_response(db, user)


@router.post("/password/forgot")
def forgot_password(body: EmailIn, request: Request, db: Session = Depends(get_db)):
    hit(f"reset:{client_ip(request)}", 5, 900)
    try:
        issue_password_reset(db, str(body.email))
        db.commit()
    except OSError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Could not send email.") from exc
    return {"ok": True}


@router.post("/password/reset", response_model=UserOut)
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    user = consume_password_reset(db, body.token, body.password)
    return _auth_response(db, user)


def _google_start_on_callback_host(request: Request, redirect_uri: str) -> str | None:
    expected = urlparse(redirect_uri)
    host = request.headers.get("host", "")
    if not expected.netloc or host == expected.netloc:
        return None
    target = f"{expected.scheme}://{expected.netloc}{request.url.path}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return target


@router.get("/google/start")
def google_start(request: Request):
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        return RedirectResponse(f"{settings.frontend_url}/login?error=google")
    aligned = _google_start_on_callback_host(request, settings.google_redirect_uri)
    if aligned:
        return RedirectResponse(aligned)
    state = new_token()
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email",
            "state": state,
            "prompt": "select_account",
        }
    )
    response = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")
    response.set_cookie("oauth_state", state, httponly=True, max_age=600, samesite="lax", path="/")
    if request.query_params.get("link") == "1" and request.cookies.get("session"):
        response.set_cookie("oauth_link", "1", httponly=True, max_age=600, samesite="lax", path="/")
    return response


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    if not state or state != request.cookies.get("oauth_state") or not code:
        return RedirectResponse(f"{settings.frontend_url}/login?error=google")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]
            info_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            info_response.raise_for_status()
            info = info_response.json()
    except (httpx.HTTPError, KeyError):
        return RedirectResponse(f"{settings.frontend_url}/login?error=google")
    if not info.get("email") or not info.get("email_verified") or not info.get("sub"):
        return RedirectResponse(f"{settings.frontend_url}/login?error=google")

    linking = request.cookies.get("oauth_link") == "1"
    try:
        if linking:
            from app.services.accounts import session_for_token

            row = session_for_token(db, request.cookies.get("session"))
            if row is None:
                return RedirectResponse(f"{settings.frontend_url}/login?error=google")
            current = db.get(User, row.user_id)
            if current is None:
                return RedirectResponse(f"{settings.frontend_url}/login?error=google")
            link_google(db, current, info["sub"])
            user = current
        else:
            user = user_from_google(db, info["sub"], info["email"])
        token, csrf = start_session(db, user)
        db.commit()
    except HTTPException:
        db.rollback()
        return RedirectResponse(f"{settings.frontend_url}/login?error=google")

    destination = "/setup" if user.display_name_set_at is None else "/"
    response = RedirectResponse(f"{settings.frontend_url}{destination}")
    set_session_cookies(response, token, csrf)
    response.delete_cookie("oauth_state", path="/")
    response.delete_cookie("oauth_link", path="/")
    return response


@router.post("/google/disconnect")
def google_disconnect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="Set a password before disconnecting Google.")
    user.google_sub = None
    db.commit()
    return user_out(user)

