from collections import defaultdict
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AuditLog,
    Ballot,
    League,
    Membership,
    OfficialEntry,
    OfficialPoll,
    Season,
    Team,
    User,
    Week,
    WeekScore,
    utcnow,
)
from app.schemas import (
    EntryIn,
    EntryOut,
    HistoryOut,
    PollOut,
    ScoreOut,
    SeasonOut,
    StandingOut,
    WeekOut,
)
from app.services.catalog import load_team_map, team_out
from app.services.scoring import score_ballot
from app.services.standings import PlayerMeta, ScoreLine, rank_players


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def week_out(week: Week) -> WeekOut:
    season = week.season
    return WeekOut(
        id=week.id,
        season_id=season.id,
        season_name=season.name,
        season_status=season.status,
        sport=season.sport,
        number=week.number,
        deadline_at=week.deadline_at,
        status=week.status,
        scores_stale=week.scores_stale,
    )


def season_out(season: Season) -> SeasonOut:
    return SeasonOut(id=season.id, sport=season.sport, name=season.name, status=season.status)


def refresh_week(week: Week, now: datetime | None = None) -> bool:
    current = now or utcnow()
    if week.status == "open" and current >= aware(week.deadline_at):
        week.status = "locked"
        return True
    return False


def ballot_lock_reason(week: Week, ballot: Ballot | None, now: datetime | None = None) -> str | None:
    current = now or utcnow()
    if week.season.status == "archived":
        return "This season is archived."
    if ballot and ballot.status == "submitted":
        return "These picks are submitted and cannot be changed."
    if week.status == "published" or current >= aware(week.deadline_at):
        return "The deadline for this week has passed."
    return None


def _teams_for_sport(db: Session, sport: str, team_ids: set[int]) -> dict[int, Team]:
    if not team_ids:
        return {}
    rows = db.scalars(
        select(Team).options(joinedload(Team.school)).where(Team.id.in_(team_ids), Team.sport == sport)
    ).all()
    return {team.id: team for team in rows}


def validate_entries(db: Session, sport: str, entries: list[EntryIn]) -> None:
    ranked = [entry for entry in entries if entry.placement == "ranked"]
    also = [entry for entry in entries if entry.placement == "also_receiving"]
    if len(ranked) != 25:
        raise HTTPException(status_code=400, detail="The official poll needs exactly 25 ranked teams.")
    ranks = [entry.rank for entry in ranked]
    if sorted(ranks) != list(range(1, 26)):
        raise HTTPException(status_code=400, detail="Ranks must be 1 through 25 with no gaps.")
    if any(entry.rank is not None for entry in also):
        raise HTTPException(status_code=400, detail="Teams receiving points outside the poll do not get a rank.")
    ids = [entry.team_id for entry in entries]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="A team can only appear once.")
    found = _teams_for_sport(db, sport, set(ids))
    if set(found) != set(ids):
        raise HTTPException(status_code=400, detail="Every team must belong to this sport.")


def replace_poll_entries(db: Session, poll: OfficialPoll, entries: list[EntryIn]) -> None:
    poll.entries.clear()
    db.flush()
    for entry in entries:
        poll.entries.append(
            OfficialEntry(
                poll_id=poll.id,
                team_id=entry.team_id,
                placement=entry.placement,
                rank=entry.rank if entry.placement == "ranked" else None,
                votes=entry.votes,
                first_place_votes=entry.first_place_votes,
            )
        )
    db.flush()


def score_week(db: Session, week: Week) -> int:
    poll = week.poll
    if poll is None or poll.published_at is None:
        raise HTTPException(status_code=400, detail="Publish the poll before scoring.")
    stored = db.scalars(select(OfficialEntry).where(OfficialEntry.poll_id == poll.id)).all()
    ranked = {
        entry.team_id: entry.rank
        for entry in stored
        if entry.placement == "ranked" and entry.rank is not None
    }
    also = {entry.team_id for entry in stored if entry.placement == "also_receiving"}
    db.query(WeekScore).filter(WeekScore.week_id == week.id).delete()
    ballots = db.scalars(
        select(Ballot).options(joinedload(Ballot.picks)).where(Ballot.week_id == week.id, Ballot.status == "submitted")
    ).unique().all()
    for ballot in ballots:
        picks = {pick.team_id: pick.rank for pick in ballot.picks}
        result = score_ballot(picks, ranked, also)
        db.add(
            WeekScore(
                user_id=ballot.user_id,
                week_id=week.id,
                total_points=result.total_points,
                proximity_points=result.proximity_points,
                bubble_points=result.bubble_points,
                exact_count=result.exact_count,
                distance_sum=result.distance_sum,
                overlap_count=result.overlap_count,
                breakdown=result.breakdown,
            )
        )
    week.scores_stale = False
    return len(ballots)


def write_audit(db: Session, actor: User, action: str, week: Week, payload: dict) -> None:
    db.add(AuditLog(actor_id=actor.id, action=action, week_id=week.id, payload=payload))


def save_poll(db: Session, week: Week, actor: User, entries: list[EntryIn], *, publish: bool) -> OfficialPoll:
    refresh_week(week)
    validate_entries(db, week.season.sport, entries)
    if week.status == "published":
        if actor.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only a super admin can edit a published poll.")
        if publish:
            raise HTTPException(status_code=400, detail="This week is already published. Save the correction, then rerun scoring.")
    elif publish and utcnow() < aware(week.deadline_at):
        raise HTTPException(status_code=400, detail="You can publish after the deadline.")
    elif week.season.status == "archived":
        raise HTTPException(status_code=400, detail="This season is archived.")

    poll = week.poll
    if poll is None:
        poll = OfficialPoll(week_id=week.id, published_by=actor.id)
        db.add(poll)
        db.flush()
        week.poll = poll
    replace_poll_entries(db, poll, entries)
    if week.status == "published":
        week.scores_stale = True
        write_audit(db, actor, "poll_edit", week, {"entries": [entry.model_dump() for entry in entries]})
    elif publish:
        poll.published_at = utcnow()
        poll.published_by = actor.id
        week.status = "published"
        scored = score_week(db, week)
        write_audit(
            db,
            actor,
            "poll_publish",
            week,
            {"entries": [entry.model_dump() for entry in entries], "ballots_scored": scored},
        )
    return poll


def rescore(db: Session, week: Week, actor: User) -> int:
    if actor.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only a super admin can rerun scoring.")
    if week.status != "published":
        raise HTTPException(status_code=400, detail="Publish the week before rerunning scores.")
    count = score_week(db, week)
    write_audit(db, actor, "week_rescore", week, {"ballots_scored": count})
    return count


def ordered_entries(entries: list[OfficialEntry], names: dict[int, str]) -> list[OfficialEntry]:
    ranked = sorted((entry for entry in entries if entry.placement == "ranked"), key=lambda entry: entry.rank or 0)
    also = sorted(
        (entry for entry in entries if entry.placement == "also_receiving"),
        key=lambda entry: (-entry.votes, -entry.first_place_votes, names.get(entry.team_id, "")),
    )
    return ranked + also


def entries_out(
    db: Session,
    entries: list[OfficialEntry],
    user_picks: dict[int, int] | None = None,
    points_by_team: dict[int, int] | None = None,
) -> list[EntryOut]:
    teams = load_team_map(db, {entry.team_id for entry in entries})
    names = {team_id: team.school.name for team_id, team in teams.items()}
    rows: list[EntryOut] = []
    for entry in ordered_entries(entries, names):
        team = teams.get(entry.team_id)
        if team is None:
            continue
        rows.append(
            EntryOut(
                team=team_out(team),
                placement=entry.placement,
                rank=entry.rank,
                votes=entry.votes,
                first_place_votes=entry.first_place_votes,
                user_rank=None if user_picks is None else user_picks.get(entry.team_id),
                points=None if points_by_team is None else points_by_team.get(entry.team_id, 0),
            )
        )
    return rows


def points_from_breakdown(breakdown: dict | None) -> dict[int, int]:
    if not breakdown:
        return {}
    points: dict[int, int] = {}
    for row in breakdown.get("proximity", []):
        points[row["team_id"]] = row["points"]
    for row in breakdown.get("bubble", []):
        points[row["team_id"]] = row["points"]
    for row in breakdown.get("ignored", []):
        points[row["team_id"]] = 0
    return points


def poll_view(db: Session, week: Week, source: str) -> PollOut:
    entries = week.poll.entries if week.poll else []
    return PollOut(
        week=week_out(week),
        published=week.status == "published",
        source=source,  # type: ignore[arg-type]
        entries=entries_out(db, entries),
        scores_stale=week.scores_stale,
    )


def previous_published_week(db: Session, week: Week) -> Week | None:
    return db.scalar(
        select(Week)
        .where(
            Week.season_id == week.season_id,
            Week.number < week.number,
            Week.status == "published",
        )
        .order_by(Week.number.desc())
    )


def prefill(db: Session, week: Week) -> PollOut:
    if week.poll and week.poll.entries:
        source = "current" if week.status == "published" else "draft"
        return poll_view(db, week, source)
    previous = previous_published_week(db, week)
    if previous and previous.poll:
        cloned = [
            OfficialEntry(
                team_id=entry.team_id,
                placement=entry.placement,
                rank=entry.rank,
                votes=entry.votes,
                first_place_votes=entry.first_place_votes,
            )
            for entry in previous.poll.entries
        ]
        view = PollOut(
            week=week_out(week),
            published=False,
            source="previous",
            entries=entries_out(db, cloned),
            scores_stale=False,
        )
        return view
    return PollOut(week=week_out(week), published=False, source="empty", entries=[], scores_stale=False)


def score_out(row: WeekScore | None) -> ScoreOut | None:
    if row is None:
        return None
    return ScoreOut(
        total_points=row.total_points,
        proximity_points=row.proximity_points,
        bubble_points=row.bubble_points,
        exact_count=row.exact_count,
        distance_sum=row.distance_sum,
        breakdown=row.breakdown,
    )


def published_weeks(db: Session, season_id: int) -> list[Week]:
    return list(
        db.scalars(
            select(Week).where(Week.season_id == season_id, Week.status == "published").order_by(Week.number)
        ).all()
    )


def _metas_and_lines(
    db: Session, weeks: list[Week], candidate_ids: set[int] | None
) -> tuple[list[PlayerMeta], list[ScoreLine]]:
    if not weeks:
        return [], []
    week_ids = [week.id for week in weeks]
    index = {week_id: position for position, week_id in enumerate(week_ids)}
    score_query = select(WeekScore).where(WeekScore.week_id.in_(week_ids))
    if candidate_ids is not None:
        if not candidate_ids:
            return [], []
        score_query = score_query.where(WeekScore.user_id.in_(candidate_ids))
    scores = db.scalars(score_query).all()
    user_ids = set(candidate_ids or [])
    user_ids.update(score.user_id for score in scores)
    if not user_ids:
        return [], []
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    ballot_rows = db.execute(
        select(Ballot.user_id, Ballot.week_id, Ballot.submitted_at).where(
            Ballot.week_id.in_(week_ids),
            Ballot.status == "submitted",
            Ballot.user_id.in_(user_ids),
        )
    ).all()
    submits: dict[int, list[tuple[int, datetime]]] = defaultdict(list)
    for user_id, week_id, submitted in ballot_rows:
        if submitted is not None:
            submits[user_id].append((index[week_id], submitted))
    metas = [
        PlayerMeta(user_id=user.id, display_name=user.display_name, submits=submits.get(user.id, []))
        for user in users
    ]
    lines = [
        ScoreLine(
            user_id=score.user_id,
            week_index=index[score.week_id],
            points=score.total_points,
            exact=score.exact_count,
            distance=score.distance_sum,
            overlap=score.overlap_count,
        )
        for score in scores
    ]
    return metas, lines


def standings_for(
    db: Session,
    season_id: int,
    *,
    candidate_ids: set[int] | None,
    require_activity: bool,
) -> list[StandingOut]:
    weeks = published_weeks(db, season_id)
    if not weeks:
        return []
    metas, lines = _metas_and_lines(db, weeks, candidate_ids)
    if candidate_ids is not None:
        allowed = {meta.user_id for meta in metas}
        missing = candidate_ids - allowed
        if missing and not require_activity:
            extra_users = db.scalars(select(User).where(User.id.in_(missing))).all()
            metas.extend(
                PlayerMeta(user_id=user.id, display_name=user.display_name, submits=[])
                for user in extra_users
            )
    table = rank_players(metas, lines, len(weeks) - 1, require_activity=require_activity)
    return [StandingOut(**row.__dict__) for row in table]


def history_for(
    db: Session,
    season_id: int,
    user_id: int,
    *,
    candidate_ids: set[int] | None,
    require_activity: bool,
) -> list[HistoryOut]:
    weeks = published_weeks(db, season_id)
    if not weeks:
        return []
    metas, lines = _metas_and_lines(db, weeks, candidate_ids)
    if candidate_ids is not None and not require_activity:
        present = {meta.user_id for meta in metas}
        missing = candidate_ids - present
        if missing:
            extra_users = db.scalars(select(User).where(User.id.in_(missing))).all()
            metas.extend(
                PlayerMeta(user_id=user.id, display_name=user.display_name, submits=[])
                for user in extra_users
            )
    my_lines = {line.week_index: line for line in lines if line.user_id == user_id}
    rows: list[HistoryOut] = []
    previous_rank: int | None = None
    cumulative = 0
    for index, week in enumerate(weeks):
        table = rank_players(metas, lines, index, require_activity=require_activity)
        mine = next((item for item in table if item.user_id == user_id), None)
        week_line = my_lines.get(index)
        if week_line:
            cumulative += week_line.points
        rank = mine.rank if mine else None
        rows.append(
            HistoryOut(
                week_id=week.id,
                week_number=week.number,
                week_points=None if week_line is None else week_line.points,
                cumulative_points=cumulative,
                rank=rank,
                previous_rank=previous_rank,
            )
        )
        previous_rank = rank
    return rows


def league_member_ids(db: Session, league: League, *, include_kicked: bool = False) -> set[int]:
    query = select(Membership.user_id).where(Membership.league_id == league.id)
    if not include_kicked:
        query = query.where(Membership.kicked.is_(False))
    return set(db.scalars(query).all())
