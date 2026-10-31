from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import SessionLocal
from app.routers import admin, auth, ballots, catalog, leagues, me, seasons, standings
from app.services.accounts import csrf_ok, session_for_token

DOC_PATHS = {"/api/docs", "/api/redoc", "/api/openapi.json"}
CSRF_EXEMPT = {
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/magic-link",
    "/api/auth/magic-link/consume",
    "/api/auth/password/forgot",
    "/api/auth/password/reset",
}

app = FastAPI(
    title="Top 25",
    description=(
        "Independent fan game API. Sign in with a cookie session. "
        "Send the csrf cookie value in the X-CSRF-Token header on POST, PUT, PATCH, and DELETE."
    ),
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(catalog.router)
app.include_router(seasons.router)
app.include_router(ballots.router)
app.include_router(standings.router)
app.include_router(leagues.router)
app.include_router(admin.router)


@app.middleware("http")
async def guard_requests(request: Request, call_next):
    path = request.url.path
    settings = get_settings()
    if path in DOC_PATHS and not settings.docs_public:
        db = SessionLocal()
        try:
            row = session_for_token(db, request.cookies.get("session"))
            user_role = None
            if row is not None:
                from app.models import User

                user = db.get(User, row.user_id)
                user_role = user.role if user else None
        finally:
            db.close()
        if user_role not in {"admin", "super_admin"}:
            return JSONResponse({"detail": "Not found"}, status_code=404)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and path not in CSRF_EXEMPT:
        csrf_header = request.headers.get("x-csrf-token")
        csrf_cookie = request.cookies.get("csrf")
        db = SessionLocal()
        try:
            allowed = csrf_ok(db, request.cookies.get("session"), csrf_cookie) and csrf_header == csrf_cookie
        finally:
            db.close()
        if not allowed:
            return JSONResponse({"detail": "CSRF check failed"}, status_code=403)
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/openapi.json", include_in_schema=False)
def openapi():
    return JSONResponse(app.openapi())


@app.get("/api/docs", include_in_schema=False)
def swagger():
    return get_swagger_ui_html(openapi_url="/api/openapi.json", title="Top 25 API")


@app.get("/api/redoc", include_in_schema=False)
def redoc():
    return get_redoc_html(openapi_url="/api/openapi.json", title="Top 25 API")
