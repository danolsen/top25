from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_ready_user
from app.limits import client_ip, hit
from app.models import League, Membership, Season, Team, User
from app.schemas import (
    HistoryOut,
    JoinIn,
    LeagueIn,
    LeagueOut,
    LeagueRename,
    MemberAction,
    MemberOut,
    SchoolJoinIn,
    SchoolLeagueOut,
    StandingOut,
)
from app.security import new_join_code
from app.services.catalog import team_out
from app.services.game import history_for, league_member_ids, standings_for

router = APIRouter(prefix="/api", tags=["leagues"])


def _membership(db: Session, league_id: int, user_id: int) -> Membership | None:
    return db.scalar(select(Membership).where(Membership.league_id == league_id, Membership.user_id == user_id))


def _require_member(db: Session, league: League, user: User) -> Membership:
    row = _membership(db, league.id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="League not found.")
    return row


def _league_out(db: Session, league: League, viewer: User, *, with_members: bool) -> LeagueOut:
    membership = _membership(db, league.id, viewer.id)
    is_owner = league.owner_id == viewer.id
    members = None
    if with_members and membership is not None and not membership.kicked:
        rows = db.scalars(select(Membership).where(Membership.league_id == league.id)).all()
        if not is_owner:
            rows = [row for row in rows if not row.kicked]
        user_ids = [row.user_id for row in rows]
        users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
        members = [
            MemberOut(
                user_id=row.user_id,
                display_name=users[row.user_id].display_name if row.user_id in users else "Player",
                kicked=row.kicked,
                is_owner=row.user_id == league.owner_id,
            )
            for row in rows
        ]
    return LeagueOut(
        id=league.id,
        season_id=league.season_id,
        season_name=league.season.name,
        sport=league.sport,
        kind=league.kind,
        name=league.name,
        owner_id=league.owner_id,
        team_id=league.team_id,
        join_code=league.join_code if is_owner else None,
        is_owner=is_owner,
        kicked=bool(membership and membership.kicked),
        members=members,
    )


def _mint_code(db: Session) -> str:
    for _ in range(20):
        code = new_join_code()
        if db.scalar(select(League.id).where(League.join_code == code)) is None:
            return code
    raise HTTPException(status_code=500, detail="Could not create a join code.")


def _get_league(db: Session, league_id: int) -> League:
    league = db.get(League, league_id)
    if league is None:
        raise HTTPException(status_code=404, detail="League not found.")
    return league


@router.get("/leagues", response_model=list[LeagueOut])
def my_leagues(season_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    league_ids = db.scalars(select(Membership.league_id).where(Membership.user_id == user.id)).all()
    if not league_ids:
        return []
    leagues = db.scalars(
        select(League).where(League.id.in_(league_ids), League.season_id == season_id).order_by(League.name)
    ).all()
    return [_league_out(db, league, user, with_members=False) for league in leagues]


@router.post("/leagues", response_model=LeagueOut)
def create_league(body: LeagueIn, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    season = db.get(Season, body.season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found.")
    if season.status == "archived":
        raise HTTPException(status_code=400, detail="Archived seasons cannot get new leagues.")
    league = League(
        season_id=season.id,
        sport=season.sport,
        kind="private",
        name=body.name.strip(),
        owner_id=user.id,
        join_code=_mint_code(db),
    )
    db.add(league)
    db.flush()
    db.add(Membership(user_id=user.id, league_id=league.id, kicked=False))
    db.commit()
    db.refresh(league)
    return _league_out(db, league, user, with_members=True)


@router.post("/leagues/join", response_model=LeagueOut)
def join_league(body: JoinIn, request: Request, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    hit(f"join:{client_ip(request)}", 10, 600)
    code = "".join(body.code.split()).upper()
    league = db.scalar(select(League).where(League.join_code == code, League.kind == "private"))
    if league is None:
        raise HTTPException(status_code=404, detail="That join code does not match a league.")
    existing = _membership(db, league.id, user.id)
    if existing and existing.kicked:
        raise HTTPException(status_code=403, detail="The commissioner has removed you from this league.")
    if existing is None:
        db.add(Membership(user_id=user.id, league_id=league.id, kicked=False))
        db.commit()
    return _league_out(db, league, user, with_members=True)


@router.get("/leagues/{league_id}", response_model=LeagueOut)
def get_league(league_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    league = _get_league(db, league_id)
    _require_member(db, league, user)
    return _league_out(db, league, user, with_members=True)


@router.patch("/leagues/{league_id}", response_model=LeagueOut)
def rename_league(
    league_id: int,
    body: LeagueRename,
    user: User = Depends(get_ready_user),
    db: Session = Depends(get_db),
):
    league = _get_league(db, league_id)
    if league.kind != "private" or league.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the commissioner can rename this league.")
    league.name = body.name.strip()
    db.commit()
    return _league_out(db, league, user, with_members=True)


@router.post("/leagues/{league_id}/rotate-code", response_model=LeagueOut)
def rotate_code(league_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    league = _get_league(db, league_id)
    if league.kind != "private" or league.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the commissioner can change the join code.")
    league.join_code = _mint_code(db)
    db.commit()
    return _league_out(db, league, user, with_members=True)


@router.post("/leagues/{league_id}/kick", response_model=LeagueOut)
def kick_member(
    league_id: int,
    body: MemberAction,
    user: User = Depends(get_ready_user),
    db: Session = Depends(get_db),
):
    league = _get_league(db, league_id)
    if league.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the commissioner can remove a player.")
    if body.user_id == user.id:
        raise HTTPException(status_code=400, detail="Hand off the league before leaving it.")
    membership = _membership(db, league.id, body.user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="That player is not in the league.")
    membership.kicked = True
    db.commit()
    return _league_out(db, league, user, with_members=True)


@router.post("/leagues/{league_id}/restore", response_model=LeagueOut)
def restore_member(
    league_id: int,
    body: MemberAction,
    user: User = Depends(get_ready_user),
    db: Session = Depends(get_db),
):
    league = _get_league(db, league_id)
    if league.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the commissioner can allow a player back.")
    membership = _membership(db, league.id, body.user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="That player is not in the league.")
    membership.kicked = False
    db.commit()
    return _league_out(db, league, user, with_members=True)


@router.post("/leagues/{league_id}/transfer", response_model=LeagueOut)
def transfer_owner(
    league_id: int,
    body: MemberAction,
    user: User = Depends(get_ready_user),
    db: Session = Depends(get_db),
):
    league = _get_league(db, league_id)
    if league.kind != "private" or league.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the commissioner can hand off this league.")
    if body.user_id == user.id:
        raise HTTPException(status_code=400, detail="Choose another player.")
    membership = _membership(db, league.id, body.user_id)
    if membership is None or membership.kicked:
        raise HTTPException(status_code=400, detail="Choose a current player in the league.")
    league.owner_id = body.user_id
    db.commit()
    return _league_out(db, league, user, with_members=True)


@router.post("/leagues/{league_id}/leave")
def leave_league(league_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    league = _get_league(db, league_id)
    membership = _require_member(db, league, user)
    if league.owner_id == user.id:
        raise HTTPException(status_code=400, detail="Hand off the league before leaving it.")
    db.delete(membership)
    db.commit()
    return {"ok": True}


@router.get("/leagues/{league_id}/standings", response_model=list[StandingOut])
def league_standings(league_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    league = _get_league(db, league_id)
    membership = _require_member(db, league, user)
    if membership.kicked:
        raise HTTPException(status_code=403, detail="The commissioner has removed you from this league.")
    return standings_for(
        db,
        league.season_id,
        candidate_ids=league_member_ids(db, league),
        require_activity=False,
    )


@router.get("/leagues/{league_id}/history", response_model=list[HistoryOut])
def league_history(league_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    league = _get_league(db, league_id)
    membership = _require_member(db, league, user)
    if membership.kicked:
        raise HTTPException(status_code=403, detail="The commissioner has removed you from this league.")
    return history_for(
        db,
        league.season_id,
        user.id,
        candidate_ids=league_member_ids(db, league),
        require_activity=False,
    )


@router.get("/school-leagues", response_model=list[SchoolLeagueOut])
def school_leagues(season_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    season = db.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404, detail="Season not found.")
    teams = db.scalars(
        select(Team).options(joinedload(Team.school)).where(Team.sport == season.sport, Team.active.is_(True)).order_by(Team.id)
    ).all()
    leagues = db.scalars(
        select(League).where(League.season_id == season.id, League.kind == "school")
    ).all()
    by_team = {league.team_id: league for league in leagues}
    joined_ids = set(
        db.scalars(
            select(Membership.league_id).where(Membership.user_id == user.id, Membership.kicked.is_(False))
        ).all()
    )
    rows: list[SchoolLeagueOut] = []
    for team in teams:
        league = by_team.get(team.id)
        rows.append(
            SchoolLeagueOut(
                team=team_out(team),
                league_id=None if league is None else league.id,
                joined=bool(league and league.id in joined_ids),
            )
        )
    rows.sort(key=lambda row: row.team.name)
    return rows


@router.post("/school-leagues/join", response_model=LeagueOut)
def join_school_league(body: SchoolJoinIn, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    season = db.get(Season, body.season_id)
    team = db.scalar(select(Team).options(joinedload(Team.school)).where(Team.id == body.team_id))
    if season is None or team is None:
        raise HTTPException(status_code=404, detail="Season or team not found.")
    if season.status == "archived":
        raise HTTPException(status_code=400, detail="This season is archived.")
    if team.sport != season.sport or not team.active:
        raise HTTPException(status_code=400, detail="That team is not part of this season.")
    league = db.scalar(
        select(League).where(League.season_id == season.id, League.team_id == team.id, League.kind == "school")
    )
    if league is None:
        league = League(
            season_id=season.id,
            sport=season.sport,
            kind="school",
            name=team.school.name[:40],
            team_id=team.id,
        )
        db.add(league)
        db.flush()
    existing = _membership(db, league.id, user.id)
    if existing is None:
        db.add(Membership(user_id=user.id, league_id=league.id, kicked=False))
    elif existing.kicked:
        existing.kicked = False
    db.commit()
    db.refresh(league)
    return _league_out(db, league, user, with_members=True)


@router.post("/school-leagues/{league_id}/leave")
def leave_school_league(league_id: int, user: User = Depends(get_ready_user), db: Session = Depends(get_db)):
    league = _get_league(db, league_id)
    if league.kind != "school":
        raise HTTPException(status_code=400, detail="Leave a private league from its own page.")
    membership = _require_member(db, league, user)
    db.delete(membership)
    db.commit()
    return {"ok": True}
