import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.deps import get_optional_user, get_super_admin
from app.models import School, Team, User
from app.schemas import SchoolImportOut, SchoolIn, SchoolOut, SchoolUpdate, TeamOut
from app.services.catalog import SCHOOL_IMPORT_TEMPLATE, SchoolImportError, load_schools_csv, school_out, team_out

router = APIRouter(prefix="/api", tags=["teams"])

IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}
MEDIA_NAME = re.compile(r"^[a-f0-9]{32}\.(png|jpg|jpeg|webp|gif)$")


def _apply_sports(db: Session, school: School, sports: list[str]) -> None:
    desired = set(sports)
    existing = {team.sport: team for team in school.teams}
    for sport, team in existing.items():
        team.active = sport in desired
    for sport in desired - set(existing):
        school.teams.append(Team(school_id=school.id, sport=sport, active=True))
    db.flush()


@router.get("/teams", response_model=list[TeamOut])
def list_teams(
    sport: str,
    include_inactive: bool = False,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    query = select(Team).options(joinedload(Team.school)).where(Team.sport == sport).order_by(Team.id)
    if not (include_inactive and user and user.role == "super_admin"):
        query = query.where(Team.active.is_(True))
    return [team_out(team) for team in db.scalars(query).all()]


@router.get("/schools", response_model=list[SchoolOut])
def list_schools(_: User = Depends(get_super_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(School).options(joinedload(School.teams)).order_by(School.name)).unique().all()
    return [school_out(school) for school in rows]


@router.get("/schools/import-template")
def school_import_template(_: User = Depends(get_super_admin)):
    return Response(
        content=SCHOOL_IMPORT_TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="teams-template.csv"'},
    )


@router.post("/schools/import", response_model=SchoolImportOut)
async def import_schools(
    file: UploadFile = File(...),
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
):
    data = await file.read(1_000_001)
    if len(data) > 1_000_000:
        raise HTTPException(status_code=400, detail="The file must be 1 MB or smaller.")
    try:
        result = load_schools_csv(db, data)
        db.commit()
    except SchoolImportError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A school with that name already exists.") from exc
    return result


@router.post("/schools", response_model=SchoolOut)
def create_school(body: SchoolIn, _: User = Depends(get_super_admin), db: Session = Depends(get_db)):
    school = School(
        name=body.name.strip(),
        abbreviation=body.abbreviation,
        mascot=body.mascot.strip(),
        primary_color=body.primary_color,
        secondary_color=body.secondary_color,
        logo_url=body.logo_url,
    )
    db.add(school)
    try:
        db.flush()
        _apply_sports(db, school, list(body.sports))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A school with that name already exists.") from exc
    db.refresh(school)
    return school_out(school)


@router.patch("/schools/{school_id}", response_model=SchoolOut)
def update_school(
    school_id: int,
    body: SchoolUpdate,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
):
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found.")
    if body.name is not None:
        school.name = body.name.strip()
    if body.abbreviation is not None:
        school.abbreviation = body.abbreviation
    if body.mascot is not None:
        school.mascot = body.mascot.strip()
    if body.primary_color is not None:
        school.primary_color = body.primary_color
    if body.secondary_color is not None:
        school.secondary_color = body.secondary_color
    if body.logo_url == "":
        school.logo_url = None
    elif body.logo_url is not None:
        school.logo_url = body.logo_url
    try:
        if body.sports is not None:
            _apply_sports(db, school, list(body.sports))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A school with that name already exists.") from exc
    db.refresh(school)
    return school_out(school)


@router.post("/schools/{school_id}/logo", response_model=SchoolOut)
async def upload_logo(
    school_id: int,
    file: UploadFile = File(...),
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
):
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found.")
    extension = IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPEG, WEBP, or GIF logo.")
    data = await file.read()
    if len(data) > 2_000_000:
        raise HTTPException(status_code=400, detail="Logo must be 2 MB or smaller.")
    key = f"{uuid4().hex}.{extension}"
    path = get_settings().storage_path() / key
    path.write_bytes(data)
    if school.logo_file_key:
        previous = get_settings().storage_path() / school.logo_file_key
        if previous.is_file():
            previous.unlink()
    school.logo_file_key = key
    db.commit()
    db.refresh(school)
    return school_out(school)


@router.get("/media/{key}")
def media(key: str):
    if not MEDIA_NAME.fullmatch(key):
        raise HTTPException(status_code=404, detail="File not found.")
    path = get_settings().storage_path() / key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)
