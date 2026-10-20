"""Day boundaries: a "day" runs from 12:00 to 12:00 JST and is named after its start date."""
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))  # no daylight saving time, so a fixed offset is exact
BOUNDARY_HOUR = 12
MIN_DURATION_SECONDS = 15 * 60  # shorter games (remakes, early surrenders) are excluded
MAX_CATCH_UP_DAYS = 7  # how far back the first run, or a run after an outage, looks
MAX_GAME_SECONDS = 2 * 60 * 60  # match-v5 filters by game start, so look back this much further


def latest_boundary(now):
    """The most recent 12:00 JST at or before now."""
    local = now.astimezone(JST)
    boundary = local.replace(hour=BOUNDARY_HOUR, minute=0, second=0, microsecond=0)
    if local < boundary:
        boundary -= timedelta(days=1)
    return boundary


def day_of(moment):
    """The day (start date, YYYY-MM-DD) a moment belongs to."""
    return (moment.astimezone(JST) - timedelta(hours=BOUNDARY_HOUR)).date().isoformat()


def collection_window(now, last_collected_end=None):
    """[start, end) of the games to collect: from the previous run's end up to the latest boundary."""
    end = latest_boundary(now)
    earliest = end - timedelta(days=MAX_CATCH_UP_DAYS)
    start = earliest if last_collected_end is None else max(last_collected_end, earliest)
    return start, end


def to_epoch_seconds(moment):
    return int(moment.timestamp())


def from_epoch_millis(millis):
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
