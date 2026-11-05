from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from app.config import get_settings
from app.db import SessionLocal
from app.emailer import outbox
from app.main import app
from app.models import School, Team, User, WeekScore, utcnow
from fastapi.testclient import TestClient
from sqlalchemy import select
from tests.conftest import call

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe"
    b"\xa7Y\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_google_start_stays_on_the_proxy_host(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "client")
    monkeypatch.setattr(settings, "google_client_secret", "secret")
    monkeypatch.setattr(settings, "google_redirect_uri", "https://top25.pages.dev/api/auth/google/callback")
    response = client.get("/api/auth/google/start", headers={"host": "top25.fly.dev"}, follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "top25.pages.dev" not in location.split("?", 1)[0]


def register(client: TestClient, email: str, name: str | None = None):
    body: dict = {"email": email, "password": "password123"}
    if name:
        body["display_name"] = name
    response = call(client, "post", "/api/auth/register", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client: TestClient, name: str):
    response = call(client, "post", "/api/me/display-name", json={"display_name": name})
    assert response.status_code == 200, response.text
    return response.json()


def promote(email: str, role: str = "super_admin") -> None:
    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = role
    user.display_name_set_at = utcnow()
    db.commit()
    db.close()


def build_teams() -> list[int]:
    db = SessionLocal()
    ids: list[int] = []
    for index in range(30):
        school = School(
            name=f"School {index}",
            abbreviation=f"S{index}",
            mascot="Hawks",
            primary_color="#112233",
            secondary_color="#FFFFFF",
        )
        db.add(school)
        db.flush()
        team = Team(school_id=school.id, sport="mens_basketball", active=True)
        db.add(team)
        db.flush()
        ids.append(team.id)
    other = School(
        name="Football Only",
        abbreviation="FB",
        mascot="Tide",
        primary_color="#990000",
        secondary_color="#FFFFFF",
    )
    db.add(other)
    db.flush()
    db.add(Team(school_id=other.id, sport="mens_football", active=True))
    db.commit()
    db.close()
    return ids


def ballot_body(team_ids: list[int]) -> dict:
    return {"picks": [{"team_id": team_id, "rank": rank} for rank, team_id in enumerate(team_ids, start=1)]}


def poll_body(team_ids: list[int], outsider_id: int) -> dict:
    entries = [
        {"team_id": team_id, "placement": "ranked", "rank": rank, "votes": 500 - rank, "first_place_votes": 1 if rank == 1 else 0}
        for rank, team_id in enumerate(team_ids[:25], start=1)
    ]
    entries.append(
        {
            "team_id": outsider_id,
            "placement": "also_receiving",
            "rank": None,
            "votes": 40,
            "first_place_votes": 0,
        }
    )
    return {"entries": entries}


def test_display_name_gate_magic_link_and_docs(client: TestClient):
    created = register(client, "ada@example.com", "Ada Player")
    assert created["display_name_set"] is False
    assert created["display_name"] == "Ada Player"
    blocked = call(client, "get", "/api/seasons?sport=mens_basketball")
    assert blocked.status_code == 403
    assert client.get("/api/docs").status_code == 404

    confirm(client, "Ada Player")
    assert call(client, "get", "/api/seasons?sport=mens_basketball").status_code == 200
    promote("ada@example.com")
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").status_code == 200

    sent = call(client, "post", "/api/auth/magic-link", json={"email": "bea@example.com"})
    assert sent.status_code == 200
    link = next(line for line in outbox[-1]["body"].splitlines() if line.startswith("http"))
    token = parse_qs(urlparse(link).query)["token"][0]
    fresh = TestClient(app)
    consumed = call(fresh, "post", "/api/auth/magic-link/consume", json={"token": token})
    assert consumed.status_code == 200
    assert consumed.json()["display_name_set"] is False
    assert call(fresh, "post", "/api/me/display-name", json={"display_name": "Bea Player"}).status_code == 200


def test_week_scoring_leagues_and_logos(client: TestClient):
    register(client, "admin@example.com")
    confirm(client, "Commissioner")
    promote("admin@example.com")
    team_ids = build_teams()

    school = call(
        client,
        "post",
        "/api/schools",
        json={
            "name": "Valpo",
            "abbreviation": "VAL",
            "mascot": "Beacons",
            "primary_color": "#613318",
            "secondary_color": "#FFC72C",
            "logo_url": "https://example.com/valpo.png",
            "sports": ["mens_basketball"],
        },
    )
    assert school.status_code == 200, school.text
    logo = call(
        client,
        "post",
        f"/api/schools/{school.json()['id']}/logo",
        files={"file": ("logo.png", PNG, "image/png")},
    )
    assert logo.status_code == 200, logo.text
    assert logo.json()["logo_url"] == "https://example.com/valpo.png"
    assert logo.json()["logo_file_url"].startswith("/api/media/")
    assert client.get(logo.json()["logo_file_url"]).status_code == 200

    season = call(
        client,
        "post",
        "/api/seasons",
        json={"sport": "mens_basketball", "name": "2026 Basketball", "status": "active"},
    )
    assert season.status_code == 200, season.text
    season_id = season.json()["id"]
    deadline = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    week = call(client, "post", f"/api/seasons/{season_id}/weeks", json={"deadline_at": deadline})
    assert week.status_code == 200, week.text
    week_id = week.json()["id"]

    player = TestClient(app)
    register(player, "fan@example.com")
    confirm(player, "Fan Player")
    partial = call(player, "put", f"/api/weeks/{week_id}/ballot", json=ballot_body(team_ids[:3]))
    assert partial.status_code == 200
    assert partial.json()["status"] == "draft"
    rejected = call(player, "post", f"/api/weeks/{week_id}/ballot/submit")
    assert rejected.status_code == 400

    near_miss = team_ids[:24] + [team_ids[25]]
    saved = call(player, "put", f"/api/weeks/{week_id}/ballot", json=ballot_body(near_miss))
    assert saved.status_code == 200
    submitted = call(player, "post", f"/api/weeks/{week_id}/ballot/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    locked = call(player, "put", f"/api/weeks/{week_id}/ballot", json=ballot_body(team_ids[:25]))
    assert locked.status_code == 400

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    moved = call(client, "patch", f"/api/weeks/{week_id}", json={"deadline_at": past})
    assert moved.status_code == 200
    assert moved.json()["status"] == "locked"

    published = call(client, "post", f"/api/weeks/{week_id}/publish", json=poll_body(team_ids, team_ids[25]))
    assert published.status_code == 200, published.text
    assert published.json()["published"] is True
    also = [entry for entry in published.json()["entries"] if entry["placement"] == "also_receiving"]
    assert also[0]["votes"] == 40
    assert also[0]["team"]["id"] == team_ids[25]

    results = call(player, "get", f"/api/weeks/{week_id}/results")
    assert results.status_code == 200, results.text
    score = results.json()["score"]
    assert score["proximity_points"] == 240
    assert score["bubble_points"] == 2
    assert score["total_points"] == 242

    edited = poll_body(team_ids, team_ids[26])
    for entry in edited["entries"]:
        if entry["placement"] == "ranked" and entry["rank"] == 25:
            entry["team_id"] = team_ids[27]
    saved_edit = call(client, "put", f"/api/weeks/{week_id}/official", json=edited)
    assert saved_edit.status_code == 200
    assert saved_edit.json()["scores_stale"] is True
    rerun = call(client, "post", f"/api/weeks/{week_id}/rescore")
    assert rerun.status_code == 200
    assert rerun.json()["scores_stale"] is False

    db = SessionLocal()
    row = db.scalar(select(WeekScore).where(WeekScore.user_id != 0))
    assert row is not None
    db.close()

    audit = call(client, "get", f"/api/admin/audit?week_id={week_id}")
    assert audit.status_code == 200
    assert {item["action"] for item in audit.json()} >= {"poll_publish", "poll_edit", "week_rescore"}

    standings = call(player, "get", f"/api/standings/global?season_id={season_id}")
    assert standings.status_code == 200
    assert standings.json()[0]["rank"] == 1
    history = call(player, "get", f"/api/standings/me/history?season_id={season_id}")
    assert history.json()[0]["rank"] == 1
    assert history.json()[0]["week_points"] == standings.json()[0]["points"]

    created = call(client, "post", "/api/leagues", json={"season_id": season_id, "name": "Office Pool"})
    assert created.status_code == 200, created.text
    code = created.json()["join_code"]
    league_id = created.json()["id"]
    joined = call(player, "post", "/api/leagues/join", json={"code": code.lower()})
    assert joined.status_code == 200
    assert joined.json()["join_code"] is None
    renamed = call(client, "patch", f"/api/leagues/{league_id}", json={"name": "Desk Pool"})
    assert renamed.json()["name"] == "Desk Pool"
    kicked = call(client, "post", f"/api/leagues/{league_id}/kick", json={"user_id": joined.json()["members"][1]["user_id"]})
    assert kicked.status_code == 200
    again = call(player, "post", "/api/leagues/join", json={"code": code})
    assert again.status_code == 403
    member_id = joined.json()["members"][1]["user_id"]
    call(client, "post", f"/api/leagues/{league_id}/restore", json={"user_id": member_id})
    handed = call(client, "post", f"/api/leagues/{league_id}/transfer", json={"user_id": member_id})
    assert handed.json()["owner_id"] == member_id
    assert handed.json()["is_owner"] is False

    schools = call(player, "get", f"/api/school-leagues?season_id={season_id}")
    assert schools.status_code == 200
    target = schools.json()[0]
    fan_league = call(player, "post", "/api/school-leagues/join", json={"season_id": season_id, "team_id": target["team"]["id"]})
    assert fan_league.status_code == 200
    second = schools.json()[1]
    other = call(player, "post", "/api/school-leagues/join", json={"season_id": season_id, "team_id": second["team"]["id"]})
    assert other.status_code == 200
    mine = call(player, "get", f"/api/leagues?season_id={season_id}")
    assert sum(1 for league in mine.json() if league["kind"] == "school") == 2
    left = call(player, "post", f"/api/school-leagues/{fan_league.json()['id']}/leave")
    assert left.status_code == 200

    archived = call(client, "patch", f"/api/seasons/{season_id}", json={"status": "archived"})
    assert archived.status_code == 200
    archive_view = call(player, "get", f"/api/standings/global?season_id={season_id}")
    assert archive_view.status_code == 200
    assert archive_view.json()[0]["points"] > 0
