from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

SPORTS = ("mens_football", "mens_basketball")
Sport = Literal["mens_football", "mens_basketball"]
Theme = Literal["light", "dark", "system"]
Role = Literal["user", "admin", "super_admin"]
Placement = Literal["ranked", "also_receiving"]


def clean_display_name(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not 3 <= len(cleaned) <= 24:
        raise ValueError("Display name must be 3 to 24 characters")
    return cleaned


def clean_color(value: str) -> str:
    color = value.strip().upper()
    if len(color) != 7 or not color.startswith("#"):
        raise ValueError("Use a color like #003087")
    try:
        int(color[1:], 16)
    except ValueError as exc:
        raise ValueError("Use a color like #003087") from exc
    return color


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = None

    @field_validator("display_name")
    @classmethod
    def check_name(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return clean_display_name(value)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class EmailIn(BaseModel):
    email: EmailStr


class MagicConsumeIn(BaseModel):
    token: str = Field(min_length=10, max_length=256)


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class DisplayNameIn(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        return clean_display_name(value)


class ProfileIn(BaseModel):
    display_name: str | None = None
    theme: Theme | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def check_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_display_name(value)


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    display_name: str
    display_name_set: bool
    theme: str
    has_password: bool
    google_connected: bool


class TeamOut(BaseModel):
    id: int
    sport: str
    active: bool
    school_id: int
    name: str
    abbreviation: str
    mascot: str
    primary_color: str
    secondary_color: str
    logo_url: str | None
    logo_file_url: str | None


class SchoolIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    abbreviation: str = Field(min_length=2, max_length=8)
    mascot: str = Field(min_length=2, max_length=40)
    primary_color: str
    secondary_color: str
    logo_url: str | None = Field(default=None, max_length=500)
    sports: list[Sport] = Field(default_factory=list)

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def check_color(cls, value: str) -> str:
        return clean_color(value)

    @field_validator("abbreviation")
    @classmethod
    def check_abbr(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not 2 <= len(cleaned) <= 8:
            raise ValueError("Abbreviation must be 2 to 8 characters")
        return cleaned

    @field_validator("logo_url")
    @classmethod
    def check_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("Logo URL must start with http:// or https://")
        return cleaned


class SchoolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    abbreviation: str | None = None
    mascot: str | None = Field(default=None, min_length=2, max_length=40)
    primary_color: str | None = None
    secondary_color: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    sports: list[Sport] | None = None

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def check_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_color(value)

    @field_validator("abbreviation")
    @classmethod
    def check_abbr(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not 2 <= len(cleaned) <= 8:
            raise ValueError("Abbreviation must be 2 to 8 characters")
        return cleaned

    @field_validator("logo_url")
    @classmethod
    def check_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return ""
        cleaned = value.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("Logo URL must start with http:// or https://")
        return cleaned


class SchoolOut(BaseModel):
    id: int
    name: str
    abbreviation: str
    mascot: str
    primary_color: str
    secondary_color: str
    logo_url: str | None
    logo_file_url: str | None
    teams: list[TeamOut]


class SchoolImportOut(BaseModel):
    created: int
    updated: int


class SeasonIn(BaseModel):
    sport: Sport
    name: str = Field(min_length=2, max_length=80)
    status: Literal["upcoming", "active", "archived"] = "upcoming"


class SeasonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    status: Literal["upcoming", "active", "archived"] | None = None


class SeasonOut(BaseModel):
    id: int
    sport: str
    name: str
    status: str


class WeekIn(BaseModel):
    deadline_at: datetime


class WeekUpdate(BaseModel):
    deadline_at: datetime


class WeekOut(BaseModel):
    id: int
    season_id: int
    season_name: str
    season_status: str
    sport: str
    number: int
    deadline_at: datetime
    status: str
    scores_stale: bool


class PickIn(BaseModel):
    team_id: int
    rank: int = Field(ge=1, le=25)


class BallotIn(BaseModel):
    picks: list[PickIn] = Field(max_length=25)


class PickOut(BaseModel):
    team: TeamOut
    rank: int


class BallotOut(BaseModel):
    week: WeekOut
    status: Literal["none", "draft", "submitted"]
    submitted_at: datetime | None
    editable: bool
    locked_reason: str | None
    picks: list[PickOut]


class EntryIn(BaseModel):
    team_id: int
    placement: Placement
    rank: int | None = Field(default=None, ge=1, le=25)
    votes: int = Field(ge=0)
    first_place_votes: int = Field(ge=0)


class PollIn(BaseModel):
    entries: list[EntryIn] = Field(min_length=25, max_length=80)


class EntryOut(BaseModel):
    team: TeamOut
    placement: str
    rank: int | None
    votes: int
    first_place_votes: int
    user_rank: int | None = None
    points: int | None = None


class PollOut(BaseModel):
    week: WeekOut
    published: bool
    source: Literal["draft", "previous", "empty", "current"]
    entries: list[EntryOut]
    scores_stale: bool


class ScoreOut(BaseModel):
    total_points: int
    proximity_points: int
    bubble_points: int
    exact_count: int
    distance_sum: int
    breakdown: dict


class ResultsOut(BaseModel):
    week: WeekOut
    entries: list[EntryOut]
    score: ScoreOut | None


class StandingOut(BaseModel):
    rank: int
    user_id: int
    display_name: str
    points: int
    last_week_points: int
    exact_count: int
    tiebreak: str | None


class HistoryOut(BaseModel):
    week_id: int
    week_number: int
    week_points: int | None
    cumulative_points: int
    rank: int | None
    previous_rank: int | None


class LeagueIn(BaseModel):
    season_id: int
    name: str = Field(min_length=1, max_length=40)


class LeagueRename(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=16)


class MemberAction(BaseModel):
    user_id: int


class MemberOut(BaseModel):
    user_id: int
    display_name: str
    kicked: bool
    is_owner: bool


class LeagueOut(BaseModel):
    id: int
    season_id: int
    season_name: str
    sport: str
    kind: str
    name: str
    owner_id: int | None
    team_id: int | None
    join_code: str | None
    is_owner: bool
    kicked: bool
    members: list[MemberOut] | None = None


class SchoolJoinIn(BaseModel):
    season_id: int
    team_id: int


class SchoolLeagueOut(BaseModel):
    team: TeamOut
    league_id: int | None
    joined: bool


class RoleIn(BaseModel):
    role: Literal["user", "admin"]


class AdminUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    display_name_set: bool


class AuditOut(BaseModel):
    id: int
    actor_id: int
    actor_name: str
    action: str
    week_id: int | None
    payload: dict
    created_at: datetime
