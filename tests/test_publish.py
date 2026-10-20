from datetime import datetime, timedelta, timezone

import pytest

from bot import collect, config, period, publish
from fakes import FakeBucket, FakeChampions, FakeX
from test_config import ENV
from test_collect import ACCOUNT

JST = period.JST
NOW = datetime(2026, 10, 20, 12, 5, tzinfo=JST)  # a Tuesday; boundary 10/20 12:00
END = datetime(2026, 10, 20, 12, tzinfo=JST)


def settings(**env):
    return config.Settings.from_env({**ENV, **env})


def game(match_id, end, *, win=True, champion="Ahri"):
    return {"match_id": match_id, "day": period.day_of(end), "game_end": end.astimezone(timezone.utc).isoformat(),
            "metrics": {"win": win, "champion": champion, "opponent_champion": "Zed", "gold_diff_15": 100,
                        "cs_diff_15": 5, "kill_participation": 0.5, "kda_15": {"kills": 1, "deaths": 0, "assists": 1},
                        "position": "MIDDLE"}}


def bucket_with(games, **state):
    bucket = FakeBucket()
    for g in games:
        bucket.objects.setdefault(collect.metrics_path("main", g["day"]), []).append(g)
    bucket.objects["state/main.json"] = {"last_collected_end": END.isoformat(), **state}
    return bucket


def run(bucket, x=None, **env):
    x = x or FakeX()
    result = publish.publish(ACCOUNT, settings(**env), bucket, FakeChampions(), lambda account: x, NOW)
    return result, x


@pytest.mark.parametrize("schedule,expected", [("daily", True), ("weekly:TUE", True), ("weekly:MON", False)])
def test_post_day(schedule, expected):
    assert publish.is_post_day(schedule, END) is expected


def test_posts_one_day_as_a_reply_to_the_pinned_post_and_records_the_chain():
    bucket = bucket_with([game("JP1_1", datetime(2026, 10, 19, 20, tzinfo=JST))])
    result, x = run(bucket, DRY_RUN="false")
    assert (result.status, result.games, result.posts) == ("posted", 1, 1)
    assert x.posts[0]["reply_to"] == ACCOUNT.x.root_post_id
    assert x.posts[0]["text"].startswith("10/19 ソロランク 1勝0敗")
    assert x.posts[0]["media_ids"] == ["media-1"] and x.uploads[0].startswith(b"\x89PNG")
    state = bucket.objects["state/main.json"]
    assert state["last_post_id"] == "post-1" and state["last_post_end"] == END.isoformat()


def test_next_post_replies_to_the_previous_one():
    bucket = bucket_with([game("JP1_1", datetime(2026, 10, 19, 20, tzinfo=JST))], last_post_id="post-0",
                         last_post_end=(END - timedelta(days=1)).isoformat())
    _, x = run(bucket, DRY_RUN="false")
    assert x.posts[0]["reply_to"] == "post-0"


def test_dry_run_saves_previews_and_never_calls_x():
    bucket = bucket_with([game("JP1_1", datetime(2026, 10, 19, 20, tzinfo=JST))])
    x = FakeX()
    result, _ = run(bucket, x)
    assert result.status == "previewed" and x.posts == [] and x.uploads == []
    assert bucket.objects["previews/main/2026-10-20/post-1.txt"].decode().startswith("10/19 ソロランク")
    assert bucket.objects["previews/main/2026-10-20/post-1-image-1.png"].startswith(b"\x89PNG")
    assert "last_post_id" not in bucket.objects["state/main.json"]
    assert bucket.objects["state/main.json"]["last_post_end"] == END.isoformat()


def test_no_games_skips_posting_but_advances():
    bucket = bucket_with([])
    result, x = run(bucket, DRY_RUN="false")
    assert result.status == "no_games" and x.posts == []
    assert bucket.objects["state/main.json"]["last_post_end"] == END.isoformat()


def test_waits_when_collection_has_not_reached_the_boundary():
    bucket = bucket_with([game("JP1_1", datetime(2026, 10, 19, 20, tzinfo=JST))],
                         last_collected_end=(END - timedelta(days=1)).isoformat())
    result, x = run(bucket, DRY_RUN="false")
    assert result.status == "waiting_for_collection" and x.posts == []
    assert "last_post_end" not in bucket.objects["state/main.json"]


def test_does_not_post_twice_for_the_same_boundary():
    bucket = bucket_with([game("JP1_1", datetime(2026, 10, 19, 20, tzinfo=JST))], last_post_end=END.isoformat())
    result, x = run(bucket, DRY_RUN="false")
    assert result.status == "already_posted" and x.posts == []


def test_weekly_posts_only_on_its_day_and_covers_everything_since_the_last_post():
    games = [game("JP1_a", datetime(2026, 10, 15, 20, tzinfo=JST)), game("JP1_b", datetime(2026, 10, 19, 20, tzinfo=JST)),
             game("JP1_old", datetime(2026, 10, 12, 20, tzinfo=JST))]  # before the last post
    bucket = bucket_with(games, last_post_end=datetime(2026, 10, 13, 12, tzinfo=JST).isoformat())
    result, _ = run(bucket, DRY_RUN="false", POST_SCHEDULE="weekly:MON")
    assert result.status == "not_post_day"

    result, x = run(bucket, DRY_RUN="false", POST_SCHEDULE="weekly:TUE")
    assert (result.status, result.games) == ("posted", 2)
    assert x.posts[0]["text"].startswith("10/13〜10/19 ソロランク 2勝0敗")


def test_switching_from_weekly_to_daily_picks_up_where_the_last_post_ended():
    last = datetime(2026, 10, 17, 12, tzinfo=JST)  # e.g. the last weekly post
    games = [game("JP1_a", datetime(2026, 10, 18, 20, tzinfo=JST)), game("JP1_b", datetime(2026, 10, 19, 20, tzinfo=JST))]
    bucket = bucket_with(games, last_post_end=last.isoformat())
    result, x = run(bucket, DRY_RUN="false", POST_SCHEDULE="daily")
    assert result.games == 2 and x.posts[0]["text"].startswith("10/17〜10/19")


def test_many_games_fit_on_one_post_with_taller_images():
    start = datetime(2026, 10, 19, 12, 30, tzinfo=JST)
    games = [game(f"JP1_{i}", start + timedelta(minutes=30 * i)) for i in range(33)]
    bucket = bucket_with(games)
    result, x = run(bucket, DRY_RUN="false")
    assert result.posts == 1 and len(x.posts) == 1
    assert len(x.posts[0]["media_ids"]) == 4


@pytest.mark.parametrize("count,sizes", [(1, [1]), (8, [8]), (9, [5, 4]), (12, [6, 6]), (32, [8, 8, 8, 8]),
                                         (33, [9, 9, 9, 6]), (100, [25, 25, 25, 25])])
def test_paginate_spreads_rows_evenly_over_at_most_four_images(count, sizes):
    assert [len(page) for page in publish.paginate(list(range(count)))] == sizes


def test_post_never_covers_more_than_seven_days():
    games = [game("JP1_old", datetime(2026, 10, 10, 20, tzinfo=JST)),   # 10 days before the boundary
             game("JP1_new", datetime(2026, 10, 19, 20, tzinfo=JST))]
    bucket = bucket_with(games, last_post_end=datetime(2026, 10, 1, 12, tzinfo=JST).isoformat())
    result, x = run(bucket, DRY_RUN="false")
    assert result.games == 1 and result.period_start == (END - timedelta(days=7)).isoformat()
    assert x.posts[0]["text"].startswith("10/13〜10/19")


def test_summary_layout_and_text_format():
    games = [game("JP1_a", datetime(2026, 10, 19, 20, tzinfo=JST), champion="Garen"),
             game("JP1_b", datetime(2026, 10, 19, 21, tzinfo=JST), champion="Garen", win=False)]
    bucket = bucket_with(games)
    _, x = run(bucket, DRY_RUN="false", POST_FORMAT="text", POST_LAYOUT="summary")
    assert x.uploads == []
    assert x.posts[0]["text"].splitlines()[-1] == "ガレン 1-1 GD+100 KP50%"


def test_post_failure_leaves_state_for_a_retry():
    bucket = bucket_with([game("JP1_1", datetime(2026, 10, 19, 20, tzinfo=JST))])
    with pytest.raises(RuntimeError):
        run(bucket, FakeX(fail_on_post=0), DRY_RUN="false")
    assert "last_post_end" not in bucket.objects["state/main.json"]


def test_load_records_reads_each_day_and_filters_by_end_time():
    games = [game("in", datetime(2026, 10, 19, 12, tzinfo=JST)), game("out", datetime(2026, 10, 20, 12, tzinfo=JST))]
    bucket = bucket_with(games)
    records = publish.load_records(bucket, "main", datetime(2026, 10, 19, 12, tzinfo=JST), END)
    assert [r["match_id"] for r in records] == ["in"]


def test_text_format_lists_each_game():
    bucket = bucket_with([game("JP1_1", datetime(2026, 10, 19, 20, tzinfo=JST))])
    _, x = run(bucket, DRY_RUN="false", POST_FORMAT="text")
    assert x.posts[0]["text"].splitlines()[-1] == "勝 アーリ vs ゼド 1/0/1 GD+100 CS+5 KP50%"


def test_more_games_than_one_post_can_show_keeps_the_newest_and_says_so():
    start = datetime(2026, 10, 13, 12, 30, tzinfo=JST)
    games = [game(f"JP1_{i:03d}", start + timedelta(hours=1.5 * i), win=i > 0) for i in range(101)]
    records = publish.load_records(bucket_with(games), "main", END - timedelta(days=7), END)
    [post] = publish.build_posts(settings(), records, FakeChampions(), "10/13〜10/19")
    assert len(post.images) == 4
    assert all(len(page) <= 25 for page in publish.paginate(records[-publish.MAX_IMAGE_ROWS:]))
    assert post.text.startswith("10/13〜10/19 ソロランク 100勝1敗")  # the text still counts every game
    assert post.text.endswith("（画像は直近100試合）")
