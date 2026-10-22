"""Collects an account's new solo/duo games and stores raw data and metrics in the data bucket.

Layout (paths are derived, never listed):
  raw/matches/<match id>.json.gz       {"match": ..., "timeline": ...}, written once per match
  metrics/<account id>/<day>.ndjson    one record per game of that day (see period.day_of)
  ranks/<account id>/<date>.json       solo/duo rank right after the 12:00 JST boundary of <date>
  state/<account id>.json              how far collection / posting have got

The PUUID is looked up on every run instead of being stored: PUUIDs are encrypted per API key,
so a stored one stops working when the key changes. Records keep the player's participant_id,
which identifies them in the raw data whatever key it was fetched with.
"""
from dataclasses import dataclass, field
from datetime import datetime

from . import metrics, period
from .http import HttpError

SCHEMA_VERSION = 1
OBSOLETE_STATE_KEYS = ("riot_id", "puuid", "puuid_key_id", "previous_puuids")  # from the old PUUID cache


def raw_path(match_id):
    return f"raw/matches/{match_id}.json.gz"


def metrics_path(account_id, day):
    return f"metrics/{account_id}/{day}.ndjson"


def rank_path(account_id, boundary):
    return f"ranks/{account_id}/{boundary.astimezone(period.JST).date().isoformat()}.json"


def state_path(account_id):
    return f"state/{account_id}.json"


@dataclass
class CollectResult:
    account_id: str
    window_start: str
    window_end: str
    collected: int = 0
    skipped_short: int = 0
    days: list = field(default_factory=list)
    rank: str = ""  # stored | unranked | failed: <reason>


def game_end(info):
    """End of the game; older matches lack gameEndTimestamp."""
    millis = info.get("gameEndTimestamp") or info["gameStartTimestamp"] + info["gameDuration"] * 1000
    return period.from_epoch_millis(millis)


def build_record(account_id, match_id, match, timeline, puuid):
    info = match["info"]
    end = game_end(info)
    context = metrics.GameContext(match, timeline, puuid)
    return {
        "schema_version": SCHEMA_VERSION,
        "account_id": account_id,
        "match_id": match_id,
        "day": period.day_of(end),
        "game_start": period.from_epoch_millis(info["gameStartTimestamp"]).isoformat(),
        "game_end": end.isoformat(),
        "duration_seconds": info["gameDuration"],
        "queue_id": info["queueId"],
        "game_version": info.get("gameVersion"),
        # identifies the player in the raw data even after the PUUID changes with a new API key
        "participant_id": context.me["participantId"],
        "metrics": metrics.compute(context),
    }


def collect(account, riot, bucket, now):
    state = bucket.read_json(state_path(account.id)) or {}
    last = state.get("last_collected_end")
    start, end = period.collection_window(now, datetime.fromisoformat(last) if last else None)
    result = CollectResult(account.id, start.isoformat(), end.isoformat())

    by_day = {}
    if start < end:
        puuid = riot.puuid(account.riot)
        ids = riot.match_ids(account.riot.region, puuid,
                             start_time=period.to_epoch_seconds(start) - period.MAX_GAME_SECONDS,
                             end_time=period.to_epoch_seconds(end))
        for match_id in ids:
            match = riot.match(account.riot.region, match_id)
            if not start <= game_end(match["info"]) < end:
                continue  # belongs to another window
            if match["info"]["gameDuration"] < period.MIN_DURATION_SECONDS:
                result.skipped_short += 1
                continue
            timeline = riot.timeline(account.riot.region, match_id)
            bucket.write_gzip_json_once(raw_path(match_id), {"match": match, "timeline": timeline})
            record = build_record(account.id, match_id, match, timeline, puuid)
            by_day.setdefault(record["day"], []).append(record)
            result.collected += 1

    for day, records in sorted(by_day.items()):
        merged = {r["match_id"]: r for r in bucket.read_ndjson(metrics_path(account.id, day))}
        merged.update({r["match_id"]: r for r in records})
        bucket.write_ndjson(metrics_path(account.id, day), sorted(merged.values(), key=lambda r: r["game_end"]))
        result.days.append(day)

    if start < end:
        result.rank = store_rank(account, riot, bucket, puuid, end, now)

    # Only advance after everything is stored, so a failed run is simply redone next time
    kept = {k: v for k, v in state.items() if k not in OBSOLETE_STATE_KEYS}
    bucket.write_json(state_path(account.id), {**kept, "last_collected_end": end.isoformat()})
    return result


def store_rank(account, riot, bucket, puuid, boundary, now):
    """Saves the current solo/duo rank for the post of this boundary.

    A failure is reported but does not fail the collection: the post is then made without a rank.
    """
    try:
        rank = riot.solo_duo_rank(account.riot.platform, puuid)
    except HttpError as error:
        return f"failed: {error}"
    bucket.write_json(rank_path(account.id, boundary), {"fetched_at": now.isoformat(), "solo_duo": rank})
    return "stored" if rank else "unranked"
