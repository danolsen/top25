from dataclasses import dataclass
from datetime import UTC, datetime


def aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.max.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass
class ScoreLine:
    user_id: int
    week_index: int
    points: int
    exact: int
    distance: int
    overlap: int


@dataclass
class PlayerMeta:
    user_id: int
    display_name: str
    submits: list[tuple[int, datetime]]


def _first_submit(player: PlayerMeta, through_index: int) -> datetime | None:
    times = [stamp for index, stamp in player.submits if index <= through_index and stamp is not None]
    if not times:
        return None
    return min(times)


@dataclass
class Standing:
    rank: int
    user_id: int
    display_name: str
    points: int
    last_week_points: int
    exact_count: int
    tiebreak: str | None


def _distance_key(overlap: int, distance: int) -> int:
    if overlap <= 0:
        return 10**9
    return distance


def _tiebreak_label(ahead: dict, behind: dict) -> str | None:
    if ahead["points"] != behind["points"]:
        return None
    if ahead["recent"] != behind["recent"]:
        return "most recent week"
    if ahead["exact"] != behind["exact"]:
        return "more exact picks"
    if _distance_key(ahead["overlap"], ahead["distance"]) != _distance_key(
        behind["overlap"], behind["distance"]
    ):
        return "closer ranks"
    if aware(ahead["first_submit"]) != aware(behind["first_submit"]):
        return "earlier submission"
    return "account order"


def rank_players(
    candidates: list[PlayerMeta],
    lines: list[ScoreLine],
    through_index: int,
    *,
    require_activity: bool,
) -> list[Standing]:
    grouped: dict[int, list[ScoreLine]] = {}
    for line in lines:
        if line.week_index <= through_index:
            grouped.setdefault(line.user_id, []).append(line)

    rows: list[dict] = []
    for player in candidates:
        player_lines = grouped.get(player.user_id, [])
        if require_activity and not player_lines:
            continue
        recent = 0
        for line in player_lines:
            if line.week_index == through_index:
                recent = line.points
                break
        rows.append(
            {
                "user_id": player.user_id,
                "display_name": player.display_name,
                "points": sum(line.points for line in player_lines),
                "recent": recent,
                "exact": sum(line.exact for line in player_lines),
                "distance": sum(line.distance for line in player_lines),
                "overlap": sum(line.overlap for line in player_lines),
                "first_submit": _first_submit(player, through_index),
            }
        )

    rows.sort(
        key=lambda row: (
            -row["points"],
            -row["recent"],
            -row["exact"],
            _distance_key(row["overlap"], row["distance"]),
            aware(row["first_submit"]),
            row["user_id"],
        )
    )
    standings: list[Standing] = []
    for index, row in enumerate(rows):
        tiebreak = None
        if index > 0:
            tiebreak = _tiebreak_label(rows[index - 1], row)
        standings.append(
            Standing(
                rank=index + 1,
                user_id=row["user_id"],
                display_name=row["display_name"],
                points=row["points"],
                last_week_points=row["recent"],
                exact_count=row["exact"],
                tiebreak=tiebreak,
            )
        )
    return standings
