from datetime import datetime, timedelta, timezone

from bot import period

JST = period.JST


def test_latest_boundary_before_and_after_noon():
    assert period.latest_boundary(datetime(2026, 10, 19, 12, 5, tzinfo=JST)) == datetime(2026, 10, 19, 12, tzinfo=JST)
    assert period.latest_boundary(datetime(2026, 10, 19, 11, 59, tzinfo=JST)) == datetime(2026, 10, 18, 12, tzinfo=JST)


def test_day_is_named_after_the_noon_it_starts_at():
    assert period.day_of(datetime(2026, 10, 18, 12, 0, tzinfo=JST)) == "2026-10-18"
    assert period.day_of(datetime(2026, 10, 19, 11, 59, tzinfo=JST)) == "2026-10-18"
    assert period.day_of(datetime(2026, 10, 19, 12, 0, tzinfo=JST)) == "2026-10-19"
    # UTC input is converted: 2026-10-19 02:00 UTC = 11:00 JST
    assert period.day_of(datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc)) == "2026-10-18"


def test_window_continues_from_last_collected_end():
    now = datetime(2026, 10, 20, 12, 5, tzinfo=JST)
    last = datetime(2026, 10, 19, 12, tzinfo=JST)
    assert period.collection_window(now, last) == (last, datetime(2026, 10, 20, 12, tzinfo=JST))


def test_first_run_and_long_outage_are_capped():
    now = datetime(2026, 10, 20, 12, 5, tzinfo=JST)
    end = datetime(2026, 10, 20, 12, tzinfo=JST)
    capped = end - timedelta(days=period.MAX_CATCH_UP_DAYS)
    assert period.collection_window(now, None) == (capped, end)
    assert period.collection_window(now, end - timedelta(days=30)) == (capped, end)


def test_rerun_within_the_same_day_collects_nothing():
    now = datetime(2026, 10, 20, 18, 0, tzinfo=JST)
    end = datetime(2026, 10, 20, 12, tzinfo=JST)
    start, stop = period.collection_window(now, end)
    assert start == stop
