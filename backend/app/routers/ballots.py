from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_admin, get_ready_user, get_super_admin, get_week
from app.models import Ballot, BallotPick, Team, User, Week, WeekScore
from app.schemas import BallotIn, BallotOut, PickOut, PollIn, PollOut, ResultsOut
from app.services.catalog import team_out
from app.services.game import (
    ballot_lock_reason,
    entries_out,
    points_from_breakdown,
    prefill,
    rescore,
    save_poll,
    score_out,
    week_out,
)

router = APIRouter(prefix="/api/weeks", tags=["ballots"])


def _load_ballot(db: Session, week_id: int, user_id: int) -> Ballot | None:
    return db.scalar(
        select(Ballot)
        .options(joinedload(Ballot.picks))
        .where(Ballot.week_id == week_id, Ballot.user_id == user_id)
    )


def _ballot_out(db: Session, week: Week, ballot: Ballot | None) -> BallotOut:
    reason = ballot_lock_reason(week, ballot)
    picks: list[PickOut] = []
    if ballot:
        team_ids = [pick.team_id for pick in ballot.picks]
        teams = {
            team.id: team
            for team in db.scalars(select(Team).options(joinedload(Team.school)).where(Team.id.in_(team_ids))).all()
        } if team_ids else {}
        for pick in sorted(ballot.picks, key=lambda item: item.rank):
            team = teams.get(pick.team_id)
            if team:
                picks.append(PickOut(team=team_out(team), rank=pick.rank))
    status = "none" if ballot is None else ballot.status
    return BallotOut(
        week=week_out(week),
        status=status,  # type: ignore[arg-type]
        submitted_at=None if ballot is None else ballot.submitted_at,
        editable=reason is None,
        locked_reason=reason,
        picks=picks,
    )


def _replace_picks(db: Session, week: Week, user: User, body: BallotIn) -> Ballot:
    ballot = _load_ballot(db, week.id, user.id)
    reason = ballot_lock_reason(week, ballot)
    if reason:
        raise HTTPException(status_code=400, detail=reason)
    team_ids = [pick.team_id for pick in body.picks]
    ranks = [pick.rank for pick in body.picks]
    if len(team_ids) != len(set(team_ids)) or len(ranks) != len(set(ranks)):
        raise HTTPException(status_code=400, detail="Ranks and teams must be unique.")
    if team_ids:
        found = db.scalars(select(Team.id).where(Team.id.in_(team_ids), Team.sport == week.season.sport)).all()
        if set(found) != set(team_ids):
            raise HTTPException(status_code=400, detail="Every pick must be a team in this sport.")
    if ballot is None:
        ballot = Ballot(user_id=user.id, week_id=week.id, status="draft")
        db.add(ballot)
        db.flush()
    ballot.picks.clear()
    db.flush()
    for pick in body.picks:
        ballot.picks.append(BallotPick(ballot_id=ballot.id, team_id=pick.team_id, rank=pick.rank))
    return ballot


@router.get("/{week_id}/ballot", response_model=BallotOut)
def get_ballot(week: Week = Depends(get_week), user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    return _ballot_out(db, week, _load_ballot(db, week.id, user.id))


@router.put("/{week_id}/ballot", response_model=BallotOut)
def save_ballot(
    body: BallotIn,
    week: Week = Depends(get_week),
    user: User = Depends(get_ready_user),
    db: Session = Depends(get_db),
):
    ballot = _replace_picks(db, week, user, body)
    db.commit()
    return _ballot_out(db, week, ballot)


@router.post("/{week_id}/ballot/submit", response_model=BallotOut)
def submit_ballot(
    week: Week = Depends(get_week),
    user: User = Depends(get_ready_user),
    db: Session = Depends(get_db),
):
    ballot = _load_ballot(db, week.id, user.id)
    reason = ballot_lock_reason(week, ballot)
    if reason:
        raise HTTPException(status_code=400, detail=reason)
    if ballot is None or len(ballot.picks) != 25:
        raise HTTPException(status_code=400, detail="Submit needs all 25 ranks filled.")
    ranks = sorted(pick.rank for pick in ballot.picks)
    if ranks != list(range(1, 26)):
        raise HTTPException(status_code=400, detail="Submit needs ranks 1 through 25.")
    from app.models import utcnow

    ballot.status = "submitted"
    ballot.submitted_at = utcnow()
    db.commit()
    return _ballot_out(db, week, ballot)


@router.get("/{week_id}/prefill", response_model=PollOut)
def get_prefill(week: Week = Depends(get_week), _: User = Depends(get_admin), db: Session = Depends(get_db)):
    return prefill(db, week)


@router.put("/{week_id}/official", response_model=PollOut)
def save_official(
    body: PollIn,
    week: Week = Depends(get_week),
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    save_poll(db, week, user, body.entries, publish=False)
    db.commit()
    return prefill(db, week)


@router.post("/{week_id}/publish", response_model=PollOut)
def publish_official(
    body: PollIn,
    week: Week = Depends(get_week),
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    save_poll(db, week, user, body.entries, publish=True)
    db.commit()
    return prefill(db, week)


@router.post("/{week_id}/rescore", response_model=PollOut)
def rerun_scores(
    week: Week = Depends(get_week),
    user: User = Depends(get_super_admin),
    db: Session = Depends(get_db),
):
    rescore(db, week, user)
    db.commit()
    return prefill(db, week)


@router.get("/{week_id}/results", response_model=ResultsOut)
def results(week: Week = Depends(get_week), user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    if week.status != "published" or week.poll is None:
        raise HTTPException(status_code=404, detail="The official poll is not published yet.")
    ballot = _load_ballot(db, week.id, user.id)
    picks = {pick.team_id: pick.rank for pick in ballot.picks} if ballot and ballot.status == "submitted" else None
    score = None
    points = None
    if picks is not None:
        score = db.scalar(select(WeekScore).where(WeekScore.week_id == week.id, WeekScore.user_id == user.id))
        points = points_from_breakdown(score.breakdown if score else None)
    return ResultsOut(
        week=week_out(week),
        entries=entries_out(db, list(week.poll.entries), picks, points),
        score=score_out(score),
    )
