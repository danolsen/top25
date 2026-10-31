from datetime import UTC, datetime, timedelta

from app.services.standings import PlayerMeta, ScoreLine, rank_players


def player(user_id: int, name: str, submits: list[tuple[int, datetime]] | None = None) -> PlayerMeta:
    return PlayerMeta(user_id=user_id, display_name=name, submits=submits or [])


def test_points_then_recent_week_then_exact_then_distance():
    now = datetime.now(UTC)
    players = [
        player(1, "Ada", [(0, now)]),
        player(2, "Bea", [(0, now + timedelta(minutes=5))]),
        player(3, "Cy", [(0, now + timedelta(minutes=1))]),
    ]
    lines = [
            ScoreLine(1, 0, 100, 4, 10, 10),
            ScoreLine(2, 0, 70, 4, 3, 10),
            ScoreLine(3, 0, 80, 2, 1, 8),
            ScoreLine(1, 1, 10, 1, 4, 4),
            ScoreLine(2, 1, 40, 2, 2, 6),
            ScoreLine(3, 1, 10, 1, 1, 5),
        ]
    table = rank_players(players, lines, 1, require_activity=True)
    assert [row.display_name for row in table] == ["Bea", "Ada", "Cy"]
    assert [row.rank for row in table] == [1, 2, 3]
    assert table[1].tiebreak == "most recent week"


def test_empty_overlap_loses_distance_tiebreak():
    now = datetime.now(UTC)
    players = [player(1, "None", [(0, now)]), player(2, "Some", [(0, now)])]
    lines = [
        ScoreLine(1, 0, 10, 1, 0, 0),
        ScoreLine(2, 0, 10, 1, 12, 2),
    ]
    table = rank_players(players, lines, 0, require_activity=True)
    assert table[0].display_name == "Some"
    assert table[1].tiebreak == "closer ranks"


def test_earlier_submission_then_user_id():
    now = datetime.now(UTC)
    players = [
        player(5, "Late", [(0, now + timedelta(hours=1))]),
        player(2, "Early", [(0, now)]),
        player(9, "Same", [(0, now)]),
    ]
    lines = [ScoreLine(user_id, 0, 50, 2, 4, 4) for user_id in (5, 2, 9)]
    table = rank_players(players, lines, 0, require_activity=True)
    assert [row.user_id for row in table] == [2, 9, 5]
    assert table[1].tiebreak == "account order"
    assert table[2].tiebreak == "earlier submission"


def test_inactive_players_drop_when_activity_is_required():
    players = [player(1, "Played"), player(2, "Waiting")]
    lines = [ScoreLine(1, 1, 20, 1, 1, 1)]
    early = rank_players(players, lines, 0, require_activity=True)
    assert early == []
    later = rank_players(players, lines, 1, require_activity=False)
    assert [row.display_name for row in later] == ["Played", "Waiting"]
