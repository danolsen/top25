from app.services.scoring import bubble_points, proximity_points, score_ballot


def test_proximity_table():
    assert [proximity_points(distance) for distance in range(9)] == [10, 8, 6, 4, 2, 1, 1, 1, 0]


def test_bubble_table():
    assert bubble_points(25) == 2
    assert bubble_points(23) == 2
    assert bubble_points(22) == 1
    assert bubble_points(20) == 1
    assert bubble_points(19) == 0
    assert bubble_points(8) == 0


def test_perfect_week_is_250():
    ranked = {team_id: team_id for team_id in range(1, 26)}
    result = score_ballot(ranked, ranked, set())
    assert result.proximity_points == 250
    assert result.bubble_points == 0
    assert result.total_points == 250
    assert result.exact_count == 25
    assert result.distance_sum == 0


def test_swap_and_missing_team():
    ranked = {team_id: team_id for team_id in range(1, 26)}
    picks = dict(ranked)
    picks[1], picks[2] = 2, 1
    result = score_ballot(picks, ranked, set())
    assert result.exact_count == 23
    assert result.proximity_points == 23 * 10 + 8 + 8


def test_bubble_near_miss_and_high_miss():
    ranked = {team_id: team_id for team_id in range(1, 26)}
    picks = {team_id: team_id for team_id in range(1, 25)}
    picks[100] = 25
    picks[101] = 8
    del picks[8]
    result = score_ballot(picks, ranked, {100, 101})
    bubble = {row["team_id"]: row["points"] for row in result.breakdown["bubble"]}
    assert bubble[100] == 2
    assert bubble[101] == 0
    assert result.bubble_points == 2
    assert all(row["points"] >= 0 for row in result.breakdown["proximity"])


def test_team_with_no_votes_scores_zero():
    ranked = {1: 1}
    result = score_ballot({1: 1, 9: 25}, ranked, set())
    assert result.breakdown["ignored"][0]["team_id"] == 9
    assert result.breakdown["ignored"][0]["points"] == 0
    assert result.total_points == 10


def test_fringe_slots_cap_at_nine():
    ranked = {team_id: team_id for team_id in range(1, 26)}
    picks = {team_id: team_id for team_id in range(1, 20)}
    outsiders = {200 + offset: 20 + offset for offset in range(6)}
    picks.update(outsiders)
    result = score_ballot(picks, ranked, set(outsiders))
    assert result.bubble_points == 9
