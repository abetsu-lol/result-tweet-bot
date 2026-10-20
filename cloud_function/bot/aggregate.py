"""Per-champion aggregation for the "summary" layout."""
from .text import average


def by_champion(records):
    """One row per champion played, most played first."""
    groups = {}
    for record in records:
        groups.setdefault(record["metrics"]["champion"], []).append(record["metrics"])
    rows = []
    for champion, games in groups.items():
        wins = sum(1 for m in games if m["win"])
        rows.append({
            "champion": champion,
            "games": len(games),
            "wins": wins,
            "losses": len(games) - wins,
            "gold_diff_15": average([m["gold_diff_15"] for m in games]),
            "cs_diff_15": average([m["cs_diff_15"] for m in games]),
            "kill_participation": average([m["kill_participation"] for m in games]),
        })
    return sorted(rows, key=lambda r: (-r["games"], -r["wins"], r["champion"]))
