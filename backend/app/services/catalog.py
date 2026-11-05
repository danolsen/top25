import csv
import io

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import BallotPick, OfficialEntry, OfficialPoll, School, Team
from app.schemas import SchoolImportOut, SchoolIn, SchoolOut, SchoolTeamOut, TeamOut

COLUMNS = ("name", "abbreviation", "mascot", "primary_color", "secondary_color", "logo_url", "football", "basketball")
YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0", ""}
MAX_IMPORT_ROWS = 500

SCHOOL_IMPORT_TEMPLATE = (
    "\ufeff"
    "name,abbreviation,mascot,primary_color,secondary_color,logo_url,football,basketball\r\n"
    "Example State,EXST,Eagles,#003087,#FFFFFF,,yes,no\r\n"
)


class SchoolImportError(Exception):
    pass


def logo_file_url(key: str | None) -> str | None:
    if not key:
        return None
    return f"/api/media/{key}"


def team_out(team: Team) -> TeamOut:
    school = team.school
    return TeamOut(
        id=team.id,
        sport=team.sport,
        active=team.active,
        school_id=school.id,
        name=school.name,
        abbreviation=school.abbreviation,
        mascot=school.mascot,
        primary_color=school.primary_color,
        secondary_color=school.secondary_color,
        logo_url=school.logo_url,
        logo_file_url=logo_file_url(school.logo_file_key),
    )


def team_usage(db: Session, team_ids: list[int]) -> dict[int, tuple[bool, bool]]:
    if not team_ids:
        return {}
    published = set(
        db.scalars(
            select(OfficialEntry.team_id)
            .join(OfficialPoll, OfficialPoll.id == OfficialEntry.poll_id)
            .where(OfficialEntry.team_id.in_(team_ids), OfficialPoll.published_at.is_not(None))
        ).all()
    )
    picked = set(db.scalars(select(BallotPick.team_id).where(BallotPick.team_id.in_(team_ids))).all())
    return {team_id: (team_id in published, team_id in picked) for team_id in team_ids}


def school_out(school: School, usage: dict[int, tuple[bool, bool]] | None = None) -> SchoolOut:
    flags = usage or {}
    teams = []
    for team in school.teams:
        on_published_poll, on_ballot = flags.get(team.id, (False, False))
        teams.append(SchoolTeamOut(**team_out(team).model_dump(), on_published_poll=on_published_poll, on_ballot=on_ballot))
    return SchoolOut(
        id=school.id,
        name=school.name,
        abbreviation=school.abbreviation,
        mascot=school.mascot,
        primary_color=school.primary_color,
        secondary_color=school.secondary_color,
        logo_url=school.logo_url,
        logo_file_url=logo_file_url(school.logo_file_key),
        teams=teams,
    )


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error["loc"] if item != "body")
        message = str(error["msg"]).removeprefix("Value error, ")
        parts.append(f"{loc}: {message}" if loc else message)
    return "; ".join(parts)


def _flag(value: str, label: str) -> bool:
    cleaned = value.strip().lower()
    if cleaned in YES:
        return True
    if cleaned in NO:
        return False
    raise ValueError(f"{label} must be yes or no")


def parse_school_csv(data: bytes) -> list[tuple[int, SchoolIn]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SchoolImportError("Save the file as UTF-8.") from exc
    try:
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames
    except csv.Error as exc:
        raise SchoolImportError("The file is not a valid CSV.") from exc
    if not fieldnames:
        raise SchoolImportError("The file needs a header row. Download the template and use that.")
    headers = [name.strip() for name in fieldnames if name and name.strip()]
    if len(headers) != len(set(headers)):
        raise SchoolImportError("The header row repeats a column. Download the template and use that.")
    if set(headers) != set(COLUMNS):
        missing = [name for name in COLUMNS if name not in headers]
        extra = [name for name in headers if name not in COLUMNS]
        detail = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("unexpected " + ", ".join(extra))
        raise SchoolImportError("The header row is " + " and ".join(detail) + ". Download the template and use that.")

    parsed: list[tuple[int, SchoolIn]] = []
    problems: list[str] = []
    try:
        for row in reader:
            line = reader.line_num
            if row is None or not any((value or "").strip() for value in row.values()):
                continue
            if len(parsed) >= MAX_IMPORT_ROWS:
                problems.append(f"The file has more than {MAX_IMPORT_ROWS} schools.")
                break
            try:
                sports = []
                if _flag(row.get("football") or "", "football"):
                    sports.append("mens_football")
                if _flag(row.get("basketball") or "", "basketball"):
                    sports.append("mens_basketball")
                if not sports:
                    raise ValueError("Choose football, basketball, or both")
                body = SchoolIn(
                    name=" ".join((row.get("name") or "").split()),
                    abbreviation=row.get("abbreviation") or "",
                    mascot=" ".join((row.get("mascot") or "").split()),
                    primary_color=row.get("primary_color") or "",
                    secondary_color=row.get("secondary_color") or "",
                    logo_url=row.get("logo_url") or None,
                    sports=sports,
                )
            except (ValidationError, ValueError) as exc:
                message = _validation_message(exc) if isinstance(exc, ValidationError) else str(exc)
                problems.append(f"Row {line}: {message}")
                continue
            parsed.append((line, body))
    except csv.Error as exc:
        raise SchoolImportError("The file is not a valid CSV.") from exc
    if problems:
        raise SchoolImportError("Fix the file before loading it. " + " ".join(problems))
    if not parsed:
        raise SchoolImportError("The file has no teams to load.")
    return parsed


def _index_schools(schools: list[School]) -> tuple[dict[str, School], dict[str, list[School]]]:
    by_name: dict[str, School] = {}
    by_abbreviation: dict[str, list[School]] = {}
    for school in schools:
        by_name.setdefault(school.name.casefold(), school)
        by_abbreviation.setdefault(school.abbreviation.casefold(), []).append(school)
    return by_name, by_abbreviation


def _remember(school: School, by_name: dict[str, School], by_abbreviation: dict[str, list[School]]) -> None:
    by_name[school.name.casefold()] = school
    matches = by_abbreviation.setdefault(school.abbreviation.casefold(), [])
    if school not in matches:
        matches.append(school)


def _forget(
    school: School,
    old_name: str,
    old_abbreviation: str,
    by_name: dict[str, School],
    by_abbreviation: dict[str, list[School]],
) -> None:
    if by_name.get(old_name.casefold()) is school:
        by_name.pop(old_name.casefold(), None)
    matches = by_abbreviation.get(old_abbreviation.casefold(), [])
    by_abbreviation[old_abbreviation.casefold()] = [item for item in matches if item is not school]


def _apply_school(school: School, body: SchoolIn) -> bool:
    changed = False
    if school.name != body.name:
        school.name = body.name
        changed = True
    if school.abbreviation != body.abbreviation:
        school.abbreviation = body.abbreviation
        changed = True
    if school.mascot != body.mascot:
        school.mascot = body.mascot
        changed = True
    if school.primary_color != body.primary_color:
        school.primary_color = body.primary_color
        changed = True
    if school.secondary_color != body.secondary_color:
        school.secondary_color = body.secondary_color
        changed = True
    if body.logo_url and school.logo_url != body.logo_url:
        school.logo_url = body.logo_url
        changed = True
    desired = set(body.sports)
    existing = {team.sport: team for team in school.teams}
    for sport, team in existing.items():
        active = sport in desired
        if team.active != active:
            team.active = active
            changed = True
    for sport in desired - set(existing):
        school.teams.append(Team(school_id=school.id, sport=sport, active=True))
        changed = True
    return changed


def load_schools_csv(db: Session, data: bytes) -> SchoolImportOut:
    rows = parse_school_csv(data)
    schools = list(db.scalars(select(School).options(joinedload(School.teams))).unique().all())
    by_name, by_abbreviation = _index_schools(schools)

    created = 0
    updated = 0
    for line, body in rows:
        name_hit = by_name.get(body.name.casefold())
        abbreviation_hits = [school for school in by_abbreviation.get(body.abbreviation.casefold(), []) if school is not name_hit]
        if name_hit is not None and abbreviation_hits:
            other = abbreviation_hits[0]
            raise SchoolImportError(
                f"Row {line}: {body.abbreviation} already belongs to {other.name}. {body.name} was not changed."
            )
        if name_hit is None and len(abbreviation_hits) > 1:
            raise SchoolImportError(f"Row {line}: {body.abbreviation} is used by more than one school.")
        school = name_hit if name_hit is not None else (abbreviation_hits[0] if abbreviation_hits else None)
        if school is None:
            school = School(
                name=body.name,
                abbreviation=body.abbreviation,
                mascot=body.mascot,
                primary_color=body.primary_color,
                secondary_color=body.secondary_color,
                logo_url=body.logo_url,
            )
            db.add(school)
            db.flush()
            for sport in body.sports:
                school.teams.append(Team(school_id=school.id, sport=sport, active=True))
            _remember(school, by_name, by_abbreviation)
            created += 1
            continue
        old_name = school.name
        old_abbreviation = school.abbreviation
        if _apply_school(school, body):
            updated += 1
        _forget(school, old_name, old_abbreviation, by_name, by_abbreviation)
        _remember(school, by_name, by_abbreviation)
    db.flush()
    return SchoolImportOut(created=created, updated=updated)


def load_team_map(db: Session, team_ids: set[int]) -> dict[int, Team]:
    if not team_ids:
        return {}
    rows = db.scalars(select(Team).options(joinedload(Team.school)).where(Team.id.in_(team_ids))).all()
    return {team.id: team for team in rows}
