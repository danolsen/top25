from dataclasses import dataclass

PROXIMITY = {0: 10, 1: 8, 2: 6, 3: 4, 4: 2, 5: 1, 6: 1, 7: 1}


def proximity_points(distance: int) -> int:
    return PROXIMITY.get(distance, 0)


def bubble_points(user_rank: int) -> int:
    if 23 <= user_rank <= 25:
        return 2
    if 20 <= user_rank <= 22:
        return 1
    return 0


@dataclass
class ScoreResult:
    total_points: int
    proximity_points: int
    bubble_points: int
    exact_count: int
    distance_sum: int
    overlap_count: int
    breakdown: dict


def score_ballot(
    user_picks: dict[int, int],
    ranked: dict[int, int],
    also_receiving: set[int],
) -> ScoreResult:
    proximity_rows: list[dict] = []
    proximity = 0
    exact = 0
    distance_sum = 0
    overlap = 0
    for team_id, official_rank in sorted(ranked.items(), key=lambda item: item[1]):
        user_rank = user_picks.get(team_id)
        if user_rank is None:
            points = 0
            distance = None
        else:
            distance = abs(user_rank - official_rank)
            points = proximity_points(distance)
            overlap += 1
            distance_sum += distance
            if distance == 0:
                exact += 1
        proximity += points
        proximity_rows.append(
            {
                "team_id": team_id,
                "official_rank": official_rank,
                "user_rank": user_rank,
                "distance": distance,
                "points": points,
            }
        )

    bubble_rows: list[dict] = []
    ignored: list[dict] = []
    bubble = 0
    for team_id, user_rank in sorted(user_picks.items(), key=lambda item: item[1]):
        if team_id in ranked:
            continue
        if team_id in also_receiving:
            points = bubble_points(user_rank)
            bubble += points
            bubble_rows.append({"team_id": team_id, "user_rank": user_rank, "points": points})
        else:
            ignored.append(
                {"team_id": team_id, "user_rank": user_rank, "points": 0, "reason": "no_votes"}
            )

    return ScoreResult(
        total_points=proximity + bubble,
        proximity_points=proximity,
        bubble_points=bubble,
        exact_count=exact,
        distance_sum=distance_sum,
        overlap_count=overlap,
        breakdown={"proximity": proximity_rows, "bubble": bubble_rows, "ignored": ignored},
    )
