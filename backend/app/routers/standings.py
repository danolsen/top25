from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_ready_user
from app.models import Season, User
from app.schemas import HistoryOut, StandingOut
from app.services.game import history_for, standings_for

router = APIRouter(prefix="/api/standings", tags=["standings"])


def _season(db: Session, season_id: int) -> Season:
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found.")
    return season


@router.get("/global", response_model=list[StandingOut])
def global_standings(season_id: int, _: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    _season(db, season_id)
    return standings_for(db, season_id, candidate_ids=None, require_activity=True)


@router.get("/me/history", response_model=list[HistoryOut])
def my_history(season_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    _season(db, season_id)
    return history_for(db, season_id, user.id, candidate_ids=None, require_activity=True)
