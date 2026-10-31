from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, default=None)
    role: Mapped[str] = mapped_column(String(32), default="user")
    display_name: Mapped[str] = mapped_column(String(24))
    display_name_key: Mapped[str] = mapped_column(String(24), unique=True)
    display_name_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    theme: Mapped[str] = mapped_column(String(16), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MagicLink(Base):
    __tablename__ = "magic_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    abbreviation: Mapped[str] = mapped_column(String(8))
    mascot: Mapped[str] = mapped_column(String(40))
    primary_color: Mapped[str] = mapped_column(String(7))
    secondary_color: Mapped[str] = mapped_column(String(7))
    logo_url: Mapped[str | None] = mapped_column(String(500), default=None)
    logo_file_key: Mapped[str | None] = mapped_column(String(64), default=None)
    teams: Mapped[list["Team"]] = relationship(back_populates="school", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("school_id", "sport", name="uq_team_school_sport"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    school: Mapped[School] = relationship(back_populates="teams")


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="upcoming")
    weeks: Mapped[list["Week"]] = relationship(back_populates="season", cascade="all, delete-orphan")


class Week(Base):
    __tablename__ = "weeks"
    __table_args__ = (UniqueConstraint("season_id", "number", name="uq_week_season_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="open")
    scores_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    season: Mapped[Season] = relationship(back_populates="weeks", lazy="joined")
    poll: Mapped["OfficialPoll | None"] = relationship(
        back_populates="week", cascade="all, delete-orphan", uselist=False
    )


class Ballot(Base):
    __tablename__ = "ballots"
    __table_args__ = (UniqueConstraint("user_id", "week_id", name="uq_ballot_user_week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_id: Mapped[int] = mapped_column(ForeignKey("weeks.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    picks: Mapped[list["BallotPick"]] = relationship(
        back_populates="ballot", cascade="all, delete-orphan", order_by="BallotPick.rank"
    )


class BallotPick(Base):
    __tablename__ = "ballot_picks"
    __table_args__ = (
        UniqueConstraint("ballot_id", "rank", name="uq_pick_rank"),
        UniqueConstraint("ballot_id", "team_id", name="uq_pick_team"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ballot_id: Mapped[int] = mapped_column(ForeignKey("ballots.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    ballot: Mapped[Ballot] = relationship(back_populates="picks")


class OfficialPoll(Base):
    __tablename__ = "official_polls"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_id: Mapped[int] = mapped_column(ForeignKey("weeks.id", ondelete="CASCADE"), unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    week: Mapped[Week] = relationship(back_populates="poll")
    entries: Mapped[list["OfficialEntry"]] = relationship(
        back_populates="poll", cascade="all, delete-orphan"
    )


class OfficialEntry(Base):
    __tablename__ = "official_entries"
    __table_args__ = (
        UniqueConstraint("poll_id", "team_id", name="uq_official_team"),
        UniqueConstraint("poll_id", "rank", name="uq_official_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("official_polls.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    placement: Mapped[str] = mapped_column(String(32))
    rank: Mapped[int | None] = mapped_column(Integer, default=None)
    votes: Mapped[int] = mapped_column(Integer, default=0)
    first_place_votes: Mapped[int] = mapped_column(Integer, default=0)
    poll: Mapped[OfficialPoll] = relationship(back_populates="entries")


class WeekScore(Base):
    __tablename__ = "week_scores"
    __table_args__ = (UniqueConstraint("user_id", "week_id", name="uq_score_user_week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_id: Mapped[int] = mapped_column(ForeignKey("weeks.id", ondelete="CASCADE"), index=True)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    proximity_points: Mapped[int] = mapped_column(Integer, default=0)
    bubble_points: Mapped[int] = mapped_column(Integer, default=0)
    exact_count: Mapped[int] = mapped_column(Integer, default=0)
    distance_sum: Mapped[int] = mapped_column(Integer, default=0)
    overlap_count: Mapped[int] = mapped_column(Integer, default=0)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="CASCADE"), index=True)
    sport: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(40))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), default=None, index=True)
    join_code: Mapped[str | None] = mapped_column(String(10), unique=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    season: Mapped[Season] = relationship(lazy="joined")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "league_id", name="uq_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    kicked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    week_id: Mapped[int | None] = mapped_column(ForeignKey("weeks.id"), default=None, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
