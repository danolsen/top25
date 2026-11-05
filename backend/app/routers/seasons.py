from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_admin, get_ready_user, get_super_admin
from app.models import Season, User, Week
from app.schemas import RankingsOut, SeasonIn, SeasonOut, SeasonUpdate, WeekIn, WeekOut, WeekUpdate
from app.services.game import aware, rankings_for, refresh_week, season_out, utcnow, week_out

router = APIRouter(prefix="/api", tags=["seasons"])


@router.get("/seasons", response_model=list[SeasonOut])
def list_seasons(sport: str, _: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Season).where(Season.sport == sport).order_by(Season.id.desc())).all()
    return [season_out(season) for season in rows]


@router.post("/seasons", response_model=SeasonOut)
def create_season(body: SeasonIn, _: User = Depends(get_super_admin), db: Session = Depends(get_db)):
    if body.status == "active":
        current = db.scalar(select(Season).where(Season.sport == body.sport, Season.status == "active"))
        if current:
            raise HTTPException(status_code=400, detail="This sport already has an active season.")
    season = Season(sport=body.sport, name=body.name.strip(), status=body.status)
    db.add(season)
    db.commit()
    db.refresh(season)
    return season_out(season)


@router.patch("/seasons/{season_id}", response_model=SeasonOut)
def update_season(
    season_id: int,
    body: SeasonUpdate,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found.")
    if body.name is not None:
        season.name = body.name.strip()
    if body.status is not None:
        if body.status == "active":
            other = db.scalar(
                select(Season).where(
                    Season.sport == season.sport,
                    Season.status == "active",
                    Season.id != season.id,
                )
            )
            if other:
                raise HTTPException(status_code=400, detail="This sport already has an active season.")
        season.status = body.status
    db.commit()
    return season_out(season)


@router.get("/seasons/{season_id}/rankings", response_model=RankingsOut)
def season_rankings(season_id: int, week_id: int | None = None, _: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    return rankings_for(db, season_id, week_id)


@router.get("/seasons/{season_id}/weeks", response_model=list[WeekOut])
def list_weeks(season_id: int, _: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found.")
    weeks = db.scalars(select(Week).where(Week.season_id == season_id).order_by(Week.number)).all()
    changed = False
    for week in weeks:
        changed = refresh_week(week) or changed
    if changed:
        db.commit()
    return [week_out(week) for week in weeks]


@router.post("/seasons/{season_id}/weeks", response_model=WeekOut)
def create_week(
    season_id: int,
    body: WeekIn,
    _: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found.")
    if season.status == "archived":
        raise HTTPException(status_code=400, detail="Archived seasons cannot get new weeks.")
    if aware(body.deadline_at) <= utcnow():
        raise HTTPException(status_code=400, detail="The deadline must be in the future.")
    number = db.scalar(select(func.max(Week.number)).where(Week.season_id == season_id)) or 0
    week = Week(season_id=season.id, number=number + 1, deadline_at=aware(body.deadline_at), status="open")
    db.add(week)
    db.commit()
    db.refresh(week)
    return week_out(week)


@router.patch("/weeks/{week_id}", response_model=WeekOut)
def update_week(
    week_id: int,
    body: WeekUpdate,
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    week = db.get(Week, week_id)
    if week is None:
        raise HTTPException(status_code=404, detail="Week not found.")
    refresh_week(week)
    if week.status == "published":
        raise HTTPException(status_code=400, detail="A published week keeps its deadline.")
    deadline = aware(body.deadline_at)
    if user.role != "super_admin" and deadline <= utcnow():
        raise HTTPException(status_code=400, detail="The deadline must be in the future.")
    week.deadline_at = deadline
    if week.status == "locked" and deadline > utcnow():
        week.status = "open"
    refresh_week(week)
    db.commit()
    return week_out(week)
