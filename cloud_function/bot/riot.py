"""Riot Games API: account-v1 and match-v5."""
from urllib.parse import quote

from .http import new_session, request

SOLO_DUO_QUEUE = 420
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
