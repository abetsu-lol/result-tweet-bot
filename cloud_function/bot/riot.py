"""Riot Games API: account-v1, match-v5 and league-v4."""
from urllib.parse import quote

from .http import new_session, request

SOLO_DUO_QUEUE = 420
SOLO_DUO_QUEUE_TYPE = "RANKED_SOLO_5x5"  # league-v4 name of queue 420
MATCH_IDS_PAGE = 100  # maximum count per match-v5 ids request


class RiotClient:
    def __init__(self, api_key, session=None, *, sleep=None):
        self._session = session or new_session()
        self._session.headers["X-Riot-Token"] = api_key
        self._request_kwargs = {"sleep": sleep} if sleep else {}

    def _get(self, region, path, params=None):
        url = f"https://{region}.api.riotgames.com{path}"
        return request(self._session, "GET", url, params=params, **self._request_kwargs).json()

    def puuid(self, account):
        path = f"/riot/account/v1/accounts/by-riot-id/{quote(account.game_name)}/{quote(account.tag_line)}"
        return self._get(account.region, path)["puuid"]

    def match_ids(self, region, puuid, *, start_time, end_time, queue=SOLO_DUO_QUEUE):
        """Ids of matches that started in [start_time, end_time] (epoch seconds), newest first."""
        ids, start = [], 0
        while True:
            page = self._get(region, f"/lol/match/v5/matches/by-puuid/{puuid}/ids", {
                "queue": queue, "startTime": start_time, "endTime": end_time,
                "start": start, "count": MATCH_IDS_PAGE,
            })
            ids.extend(page)
            if len(page) < MATCH_IDS_PAGE:
                return ids
            start += MATCH_IDS_PAGE

    def match(self, region, match_id):
        return self._get(region, f"/lol/match/v5/matches/{match_id}")

    def timeline(self, region, match_id):
        return self._get(region, f"/lol/match/v5/matches/{match_id}/timeline")

    def solo_duo_rank(self, platform, puuid):
        """Current solo/duo rank, or None when unranked. league-v4 is routed by platform (e.g. jp1)."""
        url = f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        entries = request(self._session, "GET", url, **self._request_kwargs).json()
        entry = next((e for e in entries if e.get("queueType") == SOLO_DUO_QUEUE_TYPE), None)
        if entry is None:
            return None
        return {"tier": entry["tier"], "rank": entry["rank"], "league_points": entry["leaguePoints"],
                "wins": entry["wins"], "losses": entry["losses"]}
