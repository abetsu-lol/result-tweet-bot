"""Builds and posts an account's results as replies under its pinned post.

A post covers the games from the previous post's period end up to the latest 12:00 JST
boundary, read from the stored metrics (not from Riot), so changing POST_SCHEDULE between
daily and weekly neither skips nor repeats games.

state/<account id>.json (shared with collect.py) gains:
  last_post_end  end of the period last posted (or skipped for having no games)
  last_post_id   newest post of the reply chain; the next post replies to it
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import aggregate, period, render, text
from .collect import metrics_path, rank_path, state_path

IMAGES_PER_POST = 4  # X's limit for photos on one post
MAX_IMAGE_ROWS = IMAGES_PER_POST * render.MAX_ROWS_PER_IMAGE  # rows one post can show
MAX_SPAN = timedelta(days=7)  # a post never covers more than this, however long ago the last one was
WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


@dataclass
class Post:
    text: str
    images: list = field(default_factory=list)  # PNG bytes


@dataclass
class PublishResult:
    account_id: str
    status: str  # posted | previewed | no_games | not_post_day | waiting_for_collection | already_posted
    period_start: str = ""
    period_end: str = ""
    games: int = 0
    posts: int = 0


def is_post_day(schedule, boundary):
    """daily, or weekly:<DAY> where DAY is the JST weekday of the run (the boundary's date)."""
    if schedule == "daily":
        return True
    return WEEKDAYS[boundary.astimezone(period.JST).weekday()] == schedule.split(":", 1)[1]


def default_span(schedule):
    return timedelta(days=1 if schedule == "daily" else 7)


def load_records(bucket, account_id, start, end):
    """Stored games that ended in [start, end), oldest first."""
    records, day = [], period.day_of(start)
    last_day = period.day_of(end - timedelta(microseconds=1))
    while day <= last_day:
        records += bucket.read_ndjson(metrics_path(account_id, day))
        day = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
    in_window = [r for r in records if start <= datetime.fromisoformat(r["game_end"]) < end]
    return sorted(in_window, key=lambda r: r["game_end"])


def paginate(rows):
    """Splits rows over at most IMAGES_PER_POST images, as evenly as possible.

    ROWS_PER_IMAGE rows per image while that is enough; beyond that images get taller (up to
    MAX_ROWS_PER_IMAGE), so a period's results fit on a single post. Callers keep rows within
    MAX_IMAGE_ROWS.
    """
    count = min(IMAGES_PER_POST, -(-len(rows) // render.ROWS_PER_IMAGE))
    size = -(-len(rows) // count)
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def build_posts(settings, records, champions, label, rank_snapshot=None):
    summary = text.summary(label, records, rank_snapshot)
    rows = aggregate.by_champion(records) if settings.post_layout == "summary" else records

    if settings.post_format == "text":
        if settings.post_layout == "summary":
            lines = [f"{champions.name(r['champion'])} {r['wins']}-{r['losses']} "
                     f"GD{text.signed(None if r['gold_diff_15'] is None else round(r['gold_diff_15']))} "
                     f"KP{text.percent(r['kill_participation'])}" for r in rows]
        else:
            lines = [text.game_line(r, champions) for r in rows]
        return [Post(t) for t in text.split_into_posts(summary, lines)]

    draw = render.champions_image if settings.post_layout == "summary" else render.games_image
    if len(rows) > MAX_IMAGE_ROWS:  # only the newest fit on one post; the summary still counts every game
        rows = rows[-MAX_IMAGE_ROWS:]
        summary += f"\n（画像は直近{MAX_IMAGE_ROWS}試合）"
    pages = paginate(rows)
    images = [draw(f"{label} ソロランク" + (f"（{n}/{len(pages)}）" if len(pages) > 1 else ""), page, champions)
              for n, page in enumerate(pages, start=1)]
    return [Post(summary, images)]


def publish(account, settings, bucket, champions, x_client_factory, now):
    state = bucket.read_json(state_path(account.id)) or {}
    end = period.latest_boundary(now)
    result = PublishResult(account.id, "not_post_day", period_end=end.isoformat())
    if not is_post_day(settings.post_schedule, end):
        return result

    collected = state.get("last_collected_end")
    if not collected or datetime.fromisoformat(collected) < end:
        result.status = "waiting_for_collection"
        return result

    last = state.get("last_post_end")
    start = datetime.fromisoformat(last) if last else end - default_span(settings.post_schedule)
    start = max(start, end - MAX_SPAN)
    result.period_start = start.isoformat()
    if start >= end:
        result.status = "already_posted"
        return result

    records = load_records(bucket, account.id, start, end)
    result.games = len(records)
    if records:
        label = text.period_label(period.day_of(start), period.day_of(end - timedelta(microseconds=1)))
        posts = build_posts(settings, records, champions, label, bucket.read_json(rank_path(account.id, end)))
        result.posts = len(posts)
        if settings.dry_run:
            result.status = "previewed"
            save_previews(bucket, account.id, end, posts)
        else:
            result.status = "posted"
            state["last_post_id"] = post_chain(x_client_factory(account), posts,
                                               reply_to=state.get("last_post_id") or account.x.root_post_id)
    else:
        result.status = "no_games"

    state["last_post_end"] = end.isoformat()
    bucket.write_json(state_path(account.id), state)
    return result


def post_chain(client, posts, *, reply_to):
    """Posts each Post as a reply to the previous one; returns the last post's id."""
    for post in posts:
        media_ids = [client.upload_png(image) for image in post.images]
        reply_to = client.post(post.text, reply_to=reply_to, media_ids=media_ids)
    return reply_to


def save_previews(bucket, account_id, end, posts):
    """DRY_RUN: what would have been posted, under previews/<account id>/<boundary date>/."""
    base = f"previews/{account_id}/{end.astimezone(period.JST).date().isoformat()}"
    for n, post in enumerate(posts, start=1):
        bucket.write_bytes(f"{base}/post-{n}.txt", post.text.encode("utf-8"), "text/plain; charset=utf-8")
        for i, image in enumerate(post.images, start=1):
            bucket.write_bytes(f"{base}/post-{n}-image-{i}.png", image, "image/png")
