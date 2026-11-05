from datetime import UTC, datetime, timedelta

from app.db import SessionLocal
from app.models import Ballot, BallotPick, League, OfficialEntry, OfficialPoll, School, Season, Team, User, Week
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from tests.conftest import call
from tests.test_api import promote, register

HEADER = "name,abbreviation,mascot,primary_color,secondary_color,logo_url,football,basketball"


def super_admin(client: TestClient) -> None:
    register(client, "boss@example.com")
    promote("boss@example.com")


def csv_bytes(*rows: str) -> bytes:
    return ("\n".join((HEADER, *rows)) + "\n").encode()


def upload(client: TestClient, raw: bytes, name: str = "teams.csv"):
    return call(client, "post", "/api/schools/import", files={"file": (name, raw, "text/csv")})


def test_template_downloads_for_super_admin(client):
    super_admin(client)
    response = client.get("/api/schools/import-template")
    assert response.status_code == 200
    assert "teams-template.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    assert text.splitlines()[0] == HEADER
    assert "Example State,EXST,Eagles,#003087,#FFFFFF,,yes,no" in text


def test_import_creates_then_updates_the_same_school(client):
    super_admin(client)
    created = upload(client, csv_bytes("Coastal,COAST,Seahawks,#003087,#FFFFFF,https://example.com/old.png,yes,no"))
    assert created.status_code == 200, created.text
    assert created.json() == {"created": 1, "updated": 0}

    updated = upload(client, csv_bytes("Coastal,CST,Gulls,#111111,#222222,,yes,yes"))
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"created": 0, "updated": 1}

    same = upload(client, csv_bytes("Coastal,CST,Gulls,#111111,#222222,,yes,yes"))
    assert same.json() == {"created": 0, "updated": 0}

    db = SessionLocal()
    school = db.scalars(select(School).options(joinedload(School.teams)).where(School.name == "Coastal")).unique().one()
    assert school.abbreviation == "CST"
    assert school.mascot == "Gulls"
    assert school.primary_color == "#111111"
    assert school.secondary_color == "#222222"
    assert school.logo_url == "https://example.com/old.png"
    assert len(school.teams) == 2
    assert {team.sport for team in school.teams if team.active} == {"mens_football", "mens_basketball"}
    db.close()


def test_import_reactivates_a_sport(client):
    super_admin(client)
    db = SessionLocal()
    school = School(name="Inland", abbreviation="INL", mascot="Owls", primary_color="#112233", secondary_color="#FFFFFF")
    db.add(school)
    db.flush()
    db.add(Team(school_id=school.id, sport="mens_basketball", active=False))
    db.commit()
    db.close()

    response = upload(client, csv_bytes("Inland,INL,Owls,#112233,#FFFFFF,,no,yes"))
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 0, "updated": 1}
    db = SessionLocal()
    team = db.scalar(select(Team).join(School).where(School.name == "Inland"))
    assert team is not None
    assert team.active is True
    db.close()


def test_import_rejects_the_file_without_saving_valid_rows(client):
    super_admin(client)
    response = upload(
        client,
        csv_bytes(
            "Good School,GOOD,Hawks,#112233,#FFFFFF,,yes,no",
            "Bad School,BAD,Hawks,blue,#FFFFFF,,yes,no",
        ),
    )
    assert response.status_code == 400
    assert "Row 3" in response.json()["detail"]
    assert client.get("/api/schools").json() == []


def test_import_updates_a_repeated_name_instead_of_duplicating(client):
    super_admin(client)
    response = upload(
        client,
        csv_bytes(
            "Twin,TWIN,Hawks,#112233,#FFFFFF,,yes,no",
            "twin,TWIN,Eagles,#445566,#778899,,no,yes",
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 1, "updated": 1}
    db = SessionLocal()
    schools = db.scalars(select(School).options(joinedload(School.teams)).where(School.abbreviation == "TWIN")).unique().all()
    assert len(schools) == 1
    school = schools[0]
    assert school.name == "twin"
    assert school.mascot == "Eagles"
    assert school.primary_color == "#445566"
    assert {team.sport: team.active for team in school.teams} == {"mens_football": False, "mens_basketball": True}
    db.close()


def test_import_matches_an_existing_abbreviation(client):
    super_admin(client)
    first = upload(client, csv_bytes("Coastal,COAST,Seahawks,#003087,#FFFFFF,,yes,no"))
    assert first.status_code == 200, first.text
    renamed = upload(client, csv_bytes("Coastal State,COAST,Gulls,#111111,#FFFFFF,,yes,no"))
    assert renamed.status_code == 200, renamed.text
    assert renamed.json() == {"created": 0, "updated": 1}
    listed = client.get("/api/schools").json()
    assert [school["name"] for school in listed] == ["Coastal State"]


def test_import_rejects_an_abbreviation_owned_by_another_school(client):
    super_admin(client)
    seeded = upload(
        client,
        csv_bytes(
            "Coastal,COAST,Seahawks,#003087,#FFFFFF,,yes,no",
            "Inland,INL,Owls,#112233,#FFFFFF,,no,yes",
        ),
    )
    assert seeded.status_code == 200, seeded.text
    response = upload(client, csv_bytes("Coastal,INL,Seahawks,#003087,#FFFFFF,,yes,no"))
    assert response.status_code == 400
    assert "already belongs to Inland" in response.json()["detail"]
    listed = client.get("/api/schools").json()
    coastal = next(school for school in listed if school["name"] == "Coastal")
    assert coastal["abbreviation"] == "COAST"


def school_body(name: str) -> dict:
    return {
        "name": name,
        "abbreviation": "TMP",
        "mascot": "Temps",
        "primary_color": "#111111",
        "secondary_color": "#EEEEEE",
        "logo_url": None,
        "sports": ["mens_football"],
    }


def test_delete_school_and_refuse_one_in_use(client):
    super_admin(client)
    created = call(client, "post", "/api/schools", json=school_body("Temporary State"))
    assert created.status_code == 200, created.text
    school_id = created.json()["id"]
    removed = call(client, "delete", f"/api/schools/{school_id}")
    assert removed.status_code == 204, removed.text
    listed = call(client, "get", "/api/schools")
    assert school_id not in {row["id"] for row in listed.json()}
    assert call(client, "delete", f"/api/schools/{school_id}").status_code == 404

    kept = call(client, "post", "/api/schools", json=school_body("Kept State"))
    assert kept.status_code == 200, kept.text
    team_id = kept.json()["teams"][0]["id"]
    db = SessionLocal()
    player = db.scalar(select(User).where(User.email == "boss@example.com"))
    assert player is not None
    player.display_name = "Boss Maple"
    season = Season(sport="mens_football", name="Guard", status="active")
    db.add(season)
    db.flush()
    week = Week(season_id=season.id, number=3, deadline_at=datetime.now(UTC) + timedelta(days=1), status="published")
    db.add(week)
    db.flush()
    poll = OfficialPoll(week_id=week.id, published_at=datetime.now(UTC), published_by=player.id)
    db.add(poll)
    db.flush()
    db.add(OfficialEntry(poll_id=poll.id, team_id=team_id, placement="ranked", position=1, rank=1, votes=0, first_place_votes=0))
    ballot = Ballot(user_id=player.id, week_id=week.id, status="submitted")
    db.add(ballot)
    db.flush()
    db.add(BallotPick(ballot_id=ballot.id, team_id=team_id, rank=4))
    db.add(League(season_id=season.id, sport="mens_football", kind="school", name="Kept", team_id=team_id))
    db.commit()
    db.close()
    blocked = call(client, "delete", f"/api/schools/{kept.json()['id']}")
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert "Official poll:" in detail
    assert "Football Guard, week 3" in detail
    assert "Picks:" in detail
    assert "Boss Maple, Football Guard, week 3" in detail
    assert "School league:" in detail
    assert "Kept, Football Guard" in detail


def test_import_is_super_admin_only(client):
    register(client, "fan@example.com", "Amber Maple 383")
    response = upload(client, csv_bytes("Coastal,COAST,Seahawks,#003087,#FFFFFF,,yes,no"))
    assert response.status_code == 403
    template = client.get("/api/schools/import-template")
    assert template.status_code == 403
