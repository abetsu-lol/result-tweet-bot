"""Synthetic match-v5 match / timeline payloads (only the fields the bot reads)."""
from datetime import datetime, timezone

ME = "puuid-me"
POSITIONS = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def participant(pid, team, position, *, puuid=None, champion="Champ", kills=0, deaths=0, assists=0, win=False):
    return {
        "participantId": pid, "teamId": team, "teamPosition": position, "puuid": puuid or f"puuid-{pid}",
        "championName": champion, "kills": kills, "deaths": deaths, "assists": assists, "win": win,
    }


def match(*, end=datetime(2026, 10, 19, 1, 0, tzinfo=timezone.utc), duration=1800, queue=420,
          me_position="MIDDLE", me_kills=3, me_assists=4, ally_kills=None, win=True):
    """Me is participant 3 (team 100, MIDDLE); my opponent is participant 8 (team 200, MIDDLE)."""
    ally_kills = ally_kills if ally_kills is not None else [1, 2, 3, 2, 1]
    people = []
    for i, pos in enumerate(POSITIONS):
        pid = i + 1
        if pid == 3:
            people.append(participant(pid, 100, me_position, puuid=ME, champion="Ahri",
                                      kills=me_kills, assists=me_assists, win=win))
        else:
            people.append(participant(pid, 100, pos, kills=ally_kills[i], win=win))
    for i, pos in enumerate(POSITIONS):
        people.append(participant(i + 6, 200, pos, champion="Zed" if pos == "MIDDLE" else "Enemy", win=not win))
    end_ms = int(end.timestamp() * 1000)
    return {"metadata": {"matchId": "JP1_1"}, "info": {
        "gameStartTimestamp": end_ms - duration * 1000, "gameEndTimestamp": end_ms,
        "gameDuration": duration, "queueId": queue, "gameVersion": "16.20.1", "participants": people,
    }}


def frame(timestamp, gold=None, cs=None, events=()):
    gold, cs = gold or {}, cs or {}
    return {"timestamp": timestamp, "events": list(events), "participantFrames": {
        str(pid): {"totalGold": gold.get(pid, 5000), "minionsKilled": cs.get(pid, 100), "jungleMinionsKilled": 0}
        for pid in range(1, 11)
    }}


def kill(timestamp, killer, victim, assists=()):
    return {"type": "CHAMPION_KILL", "timestamp": timestamp, "killerId": killer, "victimId": victim,
            "assistingParticipantIds": list(assists)}


def timeline(*, minutes=30, gold15=None, cs15=None, events=()):
    """One frame per minute; gold15 / cs15 set the 15:00 frame; events go into the frame they fall in."""
    frames = []
    for m in range(minutes + 1):
        ts = m * 60_000 + (37 if m else 0)  # real frames are a few ms past the minute
        in_frame = [e for e in events if (m - 1) * 60_000 < e["timestamp"] <= m * 60_000 + 37]
        frames.append(frame(ts, gold15 if m == 15 else None, cs15 if m == 15 else None, in_frame))
    return {"info": {"frameInterval": 60000, "frames": frames}}
