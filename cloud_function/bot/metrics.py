"""Per-game metrics.

Each metric is a function of a GameContext registered with @metric. Adding a metric is
adding one function here; it is then stored with every collected game. Raw match and
timeline data are kept too, so new metrics can be computed for past games later.
"""
from dataclasses import dataclass
from functools import cached_property

SNAPSHOT_MILLIS = 15 * 60 * 1000  # the "@15" metrics are taken at 15:00

REGISTRY = {}


def metric(name):
    def register(fn):
        REGISTRY[name] = fn
        return fn
    return register


@dataclass
class GameContext:
    match: dict
    timeline: dict
    puuid: str

    @cached_property
    def participants(self):
        return self.match["info"]["participants"]

    @cached_property
    def me(self):
        return next(p for p in self.participants if p["puuid"] == self.puuid)

    @cached_property
    def opponent(self):
        """The enemy in the same position (laning opponent), or None if positions are unknown."""
        position = self.me.get("teamPosition")
        if not position:
            return None
        return next((p for p in self.participants
                     if p["teamId"] != self.me["teamId"] and p.get("teamPosition") == position), None)

    @cached_property
    def snapshot(self):
        """participantFrames of the timeline frame at 15:00 (frames are taken every minute)."""
        frames = [f for f in self.timeline["info"]["frames"] if f["timestamp"] >= SNAPSHOT_MILLIS]
        return frames[0]["participantFrames"] if frames else None

    def frame_of(self, participant):
        return self.snapshot[str(participant["participantId"])] if self.snapshot and participant else None

    @cached_property
    def kills_until_snapshot(self):
        return [e for f in self.timeline["info"]["frames"] for e in f["events"]
                if e["type"] == "CHAMPION_KILL" and e["timestamp"] <= SNAPSHOT_MILLIS]


def _cs(frame):
    return frame["minionsKilled"] + frame["jungleMinionsKilled"]


@metric("win")
def win(ctx):
    return bool(ctx.me["win"])


@metric("champion")
def champion(ctx):
    return ctx.me["championName"]


@metric("position")
def position(ctx):
    return ctx.me.get("teamPosition") or None


@metric("opponent_champion")
def opponent_champion(ctx):
    return ctx.opponent["championName"] if ctx.opponent else None


@metric("gold_diff_15")
def gold_diff_15(ctx):
    mine, theirs = ctx.frame_of(ctx.me), ctx.frame_of(ctx.opponent)
    return mine["totalGold"] - theirs["totalGold"] if mine and theirs else None


@metric("cs_diff_15")
def cs_diff_15(ctx):
    mine, theirs = ctx.frame_of(ctx.me), ctx.frame_of(ctx.opponent)
    return _cs(mine) - _cs(theirs) if mine and theirs else None


@metric("kda_15")
def kda_15(ctx):
    """Kills, deaths and assists up to 15:00, from the timeline's CHAMPION_KILL events."""
    pid = ctx.me["participantId"]
    events = ctx.kills_until_snapshot
    return {
        "kills": sum(1 for e in events if e.get("killerId") == pid),
        "deaths": sum(1 for e in events if e.get("victimId") == pid),
        "assists": sum(1 for e in events if pid in e.get("assistingParticipantIds", [])),
    }


@metric("kill_participation")
def kill_participation(ctx):
    """(kills + assists) / team kills over the whole game, 0..1."""
    team_kills = sum(p["kills"] for p in ctx.participants if p["teamId"] == ctx.me["teamId"])
    if team_kills == 0:
        return 0.0
    return round((ctx.me["kills"] + ctx.me["assists"]) / team_kills, 4)


def compute(ctx):
    return {name: fn(ctx) for name, fn in REGISTRY.items()}
