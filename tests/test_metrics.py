import factories as f
from bot import metrics


def context(match=None, timeline=None):
    return metrics.GameContext(match or f.match(), timeline or f.timeline(), f.ME)


def test_champions_and_opponent_by_position():
    result = metrics.compute(context())
    assert result["champion"] == "Ahri"
    assert result["opponent_champion"] == "Zed"
    assert result["position"] == "MIDDLE"
    assert result["win"] is True


def test_gold_and_cs_diff_at_15_against_lane_opponent():
    ctx = context(timeline=f.timeline(gold15={3: 6200, 8: 5600}, cs15={3: 130, 8: 118}))
    assert metrics.gold_diff_15(ctx) == 600
    assert metrics.cs_diff_15(ctx) == 12


def test_kda_15_counts_only_events_until_15_minutes():
    events = [
        f.kill(5 * 60_000, killer=3, victim=8),
        f.kill(9 * 60_000, killer=2, victim=7, assists=[3]),
        f.kill(12 * 60_000, killer=8, victim=3),
        f.kill(14 * 60_000, killer=3, victim=6, assists=[1]),
        f.kill(16 * 60_000, killer=3, victim=8),  # after 15:00
    ]
    ctx = context(timeline=f.timeline(events=events))
    assert metrics.kda_15(ctx) == {"kills": 2, "deaths": 1, "assists": 1}


def test_kill_participation_uses_team_kills():
    # team kills = 1 + 2 + 6 + 2 + 1 = 12; my kills + assists = 6 + 3 = 9
    ctx = context(match=f.match(me_kills=6, me_assists=3, ally_kills=[1, 2, 0, 2, 1]))
    assert metrics.kill_participation(ctx) == 0.75


def test_kill_participation_without_team_kills_is_zero():
    ctx = context(match=f.match(me_kills=0, me_assists=0, ally_kills=[0, 0, 0, 0, 0]))
    assert metrics.kill_participation(ctx) == 0.0


def test_unknown_position_leaves_lane_metrics_empty():
    result = metrics.compute(context(match=f.match(me_position="")))
    assert result["opponent_champion"] is None
    assert result["gold_diff_15"] is None
    assert result["cs_diff_15"] is None
