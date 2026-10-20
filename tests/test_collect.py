import json
from datetime import datetime, timedelta

import factories as f
from bot import collect, config, period
from fakes import FakeBucket, FakeRiot

JST = period.JST
NOW = datetime(2026, 10, 20, 12, 5, tzinfo=JST)  # collects 10/19 12:00 - 10/20 12:00
ACCOUNT = config.parse_accounts(json.dumps([{
    "id": "main",
    "riot": {"game_name": "名前", "tag_line": "JP1", "platform": "jp1"},
    "x": {"access_token": "a", "access_token_secret": "b", "root_post_id": "1"},
}]))[0]


def riot_with(games):
    """games: match id -> (end time, duration seconds)"""
    matches = {mid: f.match(end=end, duration=duration) for mid, (end, duration) in games.items()}
    return FakeRiot(matches, {mid: f.timeline() for mid in games})


def test_collects_games_ending_in_window_and_stores_raw_metrics_and_state():
    riot = riot_with({
        "JP1_1": (datetime(2026, 10, 19, 20, 0, tzinfo=JST), 1800),
        "JP1_2": (datetime(2026, 10, 20, 1, 30, tzinfo=JST), 1500),
    })
    bucket = FakeBucket()
    bucket.objects["state/main.json"] = {"last_collected_end": datetime(2026, 10, 19, 12, tzinfo=JST).isoformat()}

    result = collect.collect(ACCOUNT, riot, bucket, NOW)

    assert (result.collected, result.skipped_short, result.days) == (2, 0, ["2026-10-19"])
    assert set(bucket.objects) >= {"raw/matches/JP1_1.json.gz", "raw/matches/JP1_2.json.gz",
                                   "metrics/main/2026-10-19.ndjson", "state/main.json"}
    records = bucket.objects["metrics/main/2026-10-19.ndjson"]
    assert [r["match_id"] for r in records] == ["JP1_1", "JP1_2"]  # sorted by game end
    assert records[0]["metrics"]["champion"] == "Ahri"
    assert records[0]["schema_version"] == collect.SCHEMA_VERSION
    state = bucket.objects["state/main.json"]
    assert state["last_collected_end"] == datetime(2026, 10, 20, 12, tzinfo=JST).isoformat()
    assert state["puuid"] == "puuid-me" and state["riot_id"] == "名前#JP1"


def test_skips_short_games_and_games_outside_the_window():
    riot = riot_with({
        "JP1_remake": (datetime(2026, 10, 19, 20, 0, tzinfo=JST), 14 * 60),
        "JP1_before": (datetime(2026, 10, 19, 11, 50, tzinfo=JST), 1800),  # previous day
        "JP1_after": (datetime(2026, 10, 20, 12, 1, tzinfo=JST), 1800),    # next day, not over yet
        "JP1_ok": (datetime(2026, 10, 19, 12, 10, tzinfo=JST), 1800),      # started before 12:00, ended after
    })
    bucket = FakeBucket()
    bucket.objects["state/main.json"] = {"last_collected_end": datetime(2026, 10, 19, 12, tzinfo=JST).isoformat()}

    result = collect.collect(ACCOUNT, riot, bucket, NOW)

    assert (result.collected, result.skipped_short) == (1, 1)
    assert [r["match_id"] for r in bucket.objects["metrics/main/2026-10-19.ndjson"]] == ["JP1_ok"]
    assert ("timeline", "JP1_remake") not in riot.calls  # no timeline fetched for excluded games


def test_rerun_merges_without_duplicates_and_reuses_puuid():
    end = datetime(2026, 10, 19, 20, 0, tzinfo=JST)
    riot = riot_with({"JP1_1": (end, 1800)})
    bucket = FakeBucket()
    collect.collect(ACCOUNT, riot, bucket, NOW)
    # Forget progress (e.g. the state write failed) and run again
    bucket.objects["state/main.json"]["last_collected_end"] = datetime(2026, 10, 19, 12, tzinfo=JST).isoformat()

    collect.collect(ACCOUNT, riot, bucket, NOW)

    assert [r["match_id"] for r in bucket.objects["metrics/main/2026-10-19.ndjson"]] == ["JP1_1"]
    assert sum(1 for c in riot.calls if c[0] == "puuid") == 1


def test_changed_riot_id_refreshes_puuid():
    riot = riot_with({})
    bucket = FakeBucket()
    bucket.objects["state/main.json"] = {"riot_id": "old#JP1", "puuid": "stale"}
    collect.collect(ACCOUNT, riot, bucket, NOW)
    assert bucket.objects["state/main.json"]["puuid"] == "puuid-me"


def test_match_ids_query_looks_back_for_long_games():
    riot = riot_with({})
    bucket = FakeBucket()
    start = datetime(2026, 10, 19, 12, tzinfo=JST)
    bucket.objects["state/main.json"] = {"last_collected_end": start.isoformat()}
    collect.collect(ACCOUNT, riot, bucket, NOW)
    _, start_time, end_time = next(c for c in riot.calls if c[0] == "match_ids")
    assert start_time == int(start.timestamp()) - period.MAX_GAME_SECONDS
    assert end_time == int((start + timedelta(days=1)).timestamp())


def test_failure_leaves_state_untouched():
    riot = riot_with({"JP1_1": (datetime(2026, 10, 19, 20, 0, tzinfo=JST), 1800)})
    del riot.timelines["JP1_1"]  # timeline fetch fails
    bucket = FakeBucket()
    bucket.objects["state/main.json"] = {"last_collected_end": datetime(2026, 10, 19, 12, tzinfo=JST).isoformat()}
    try:
        collect.collect(ACCOUNT, riot, bucket, NOW)
    except KeyError:
        pass
    assert bucket.objects["state/main.json"]["last_collected_end"] == datetime(2026, 10, 19, 12, tzinfo=JST).isoformat()
