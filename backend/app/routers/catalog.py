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
from app.models import Ballot, BallotPick, League, OfficialEntry, OfficialPoll, School, Season, Team, User, Week
from app.schemas import SchoolImportOut, SchoolIn, SchoolOut, SchoolUpdate, TeamOut
from app.services.catalog import SCHOOL_IMPORT_TEMPLATE, SchoolImportError, load_schools_csv, school_out, team_out, team_usage

router = APIRouter(prefix="/api", tags=["teams"])

IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}
MEDIA_NAME = re.compile(r"^[a-f0-9]{32}\.(png|jpg|jpeg|webp|gif)$")


def _present_schools(db: Session, schools: list[School]) -> list[SchoolOut]:
    usage = team_usage(db, [team.id for school in schools for team in school.teams])
    return [school_out(school, usage) for school in schools]


def _sport_name(sport: str) -> str:
    return "Football" if sport == "mens_football" else "Basketball"


def _limited(lines: list[str], cap: int = 12) -> list[str]:
    if len(lines) <= cap:
        return lines
    return [*lines[:cap], f"and {len(lines) - cap} more"]


def _delete_block_reason(db: Session, team_ids: list[int]) -> str | None:
    if not team_ids:
        return None
    polls = db.execute(
        select(Season.sport, Season.name, Week.number)
        .join(Week, Week.season_id == Season.id)
        .join(OfficialPoll, OfficialPoll.week_id == Week.id)
        .join(OfficialEntry, OfficialEntry.poll_id == OfficialPoll.id)
        .where(OfficialEntry.team_id.in_(team_ids))
        .distinct()
        .order_by(Season.sport, Season.name, Week.number)
    ).all()
    picks = db.execute(
        select(User.display_name, Season.sport, Season.name, Week.number)
        .join(Ballot, Ballot.user_id == User.id)
        .join(BallotPick, BallotPick.ballot_id == Ballot.id)
        .join(Week, Week.id == Ballot.week_id)
        .join(Season, Season.id == Week.season_id)
        .where(BallotPick.team_id.in_(team_ids))
        .distinct()
        .order_by(User.display_name, Season.sport, Season.name, Week.number)
    ).all()
    leagues = db.execute(
        select(League.name, Season.sport, Season.name)
        .join(Season, Season.id == League.season_id)
        .where(League.team_id.in_(team_ids))
        .order_by(Season.sport, Season.name, League.name)
    ).all()
    sections: list[str] = []
    if polls:
        lines = [f"{_sport_name(sport)} {season}, week {number}" for sport, season, number in polls]
        sections.append("Official poll:\n" + "\n".join(_limited(lines)))
    if picks:
        lines = [f"{player}, {_sport_name(sport)} {season}, week {number}" for player, sport, season, number in picks]
        sections.append("Picks:\n" + "\n".join(_limited(lines)))
    if leagues:
        lines = [f"{name}, {_sport_name(sport)} {season}" for name, sport, season in leagues]
        sections.append("School league:\n" + "\n".join(_limited(lines)))
    if not sections:
        return None
    return "This school cannot be deleted.\n\n" + "\n\n".join(sections)


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
    return _present_schools(db, list(rows))


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
    return _present_schools(db, [school])[0]


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
    return _present_schools(db, [school])[0]


@router.delete("/schools/{school_id}", status_code=204)
def delete_school(school_id: int, _: User = Depends(get_super_admin), db: Session = Depends(get_db)):
    school = db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found.")
    reason = _delete_block_reason(db, [team.id for team in school.teams])
    if reason:
        raise HTTPException(status_code=409, detail=reason)
    logo_key = school.logo_file_key
    db.delete(school)
    db.commit()
    if logo_key:
        logo = get_settings().storage_path() / logo_key
        if logo.is_file():
            logo.unlink()
    return Response(status_code=204)


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
    return _present_schools(db, [school])[0]


@router.get("/media/{key}")
def media(key: str):
    if not MEDIA_NAME.fullmatch(key):
        raise HTTPException(status_code=404, detail="File not found.")
    path = get_settings().storage_path() / key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)
